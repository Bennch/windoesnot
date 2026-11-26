#!/usr/bin/env python3
"""Find WinDoesNot restore points (Snapper snapshots) on the disks and start one from the live session.

A kernel and initramfs are loaded with kexec and the snapshot is mounted read-only as the root (the initramfs
adds a RAM overlay, see iso/installation.py). Nothing on the disks is written. Where the kernel comes from:
  snapshot     GRUB installs: /boot of the snapshot holds vmlinuz-* and initramfs-*.
  esp-restore  systemd-boot installs: iso/installation.py + sdboot_snapshots.py copy kernel and initramfs of each
               restore point to the ESP and write loader/entries/windoesnot-restore-<N>.conf (layout is ours).
  esp-limine   Limine installs: limine-snapper-sync writes one boot entry per snapshot into limine.conf and keeps
               the kernel and initramfs copies on the ESP. We do not assume where it keeps them; we read the
               kernel_path/module_path lines of the entry whose cmdline names this snapshot's subvolume.
  esp-current  fallback: the newest kernel on the ESP, ONLY if its version equals a /usr/lib/modules/<version>
               directory of the snapshot (otherwise its modules would be missing and the start would fail).
Permanent rollback: `rollback DEVICE SUBVOLUME` makes a snapshot the new root; the old root is kept as
'<root>-before-restore-<time>' and `undo DEVICE ROOT` swaps it back. Only plain Btrfs layouts (root subvolume with
<root>/.snapshots/N/snapshot, no LUKS, no other nested subvolumes) are accepted.
Usage (root): recovery.py list | recovery.py scan-cache | recovery.py boot DEVICE SUBVOLUME KERNEL_NAME |
recovery.py rollback DEVICE SUBVOLUME | recovery.py undo DEVICE ROOT | recovery.py menu"""
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

KERNELS = ('linux-cachyos', 'linux-cachyos-lts')
# Kernel names accepted when the kernel comes from the ESP (any CachyOS/Arch kernel package, e.g. linux-cachyos-bore).
KERNEL_NAME = re.compile(r'linux[A-Za-z0-9_+.-]*')
ESP_PARTTYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
GERMAN = (os.environ.get('LANG') or '').startswith('de')


def tr(de, en):
    return de if GERMAN else en


def os_name(snapshot):
    try:
        text = (snapshot / 'etc/os-release').read_text()
    except OSError:
        return ''
    match = re.search(r'(?m)^PRETTY_NAME="?([^"\n]*)', text)
    return match[1] if match and 'windoesnot' in text.lower() else ''


def kernel_release(path):
    """Version string of an x86 bzImage ('6.12.5-2-cachyos'), or '' if it is not one.

    Boot protocol (Documentation/arch/x86/boot.rst): "HdrS" at 0x202, u16 at 0x20e = offset of the version
    string minus 0x200. Keep in sync with sdboot_snapshots.py (a test compares both)."""
    try:
        with open(path, 'rb') as handle:
            head = handle.read(0x210)
            if len(head) < 0x210 or head[0x202:0x206] != b'HdrS':
                return ''
            handle.seek(int.from_bytes(head[0x20e:0x210], 'little') + 0x200)
            text = handle.read(256).split(b'\0')[0].decode('ascii', 'replace')
    except OSError:
        return ''
    return text.split(' ')[0] if re.fullmatch(r'[0-9][\w.+~-]*( .*)?', text) else ''


def snapshot_modules(snapshot):
    """Kernel versions the snapshot has modules for (/usr/lib/modules/<version>)."""
    try:
        return {p.name for p in (snapshot / 'usr/lib/modules').iterdir() if p.is_dir()}
    except OSError:
        return set()


def below(base, name):
    """base/name if it stays inside base (entries come from files on the disk), else None."""
    path = (base / name.lstrip('/')).resolve()
    return path if path.is_relative_to(base.resolve()) and path.is_file() else None


def norm_subvolume(value):
    return value.strip().strip('/')


def bls_restore_entries(esp):
    """Entries written by sdboot_snapshots.py: loader/entries/windoesnot-restore-<N>.conf as {subvolume: (linux, initrd)}."""
    found = {}
    for entry in sorted((esp / 'loader/entries').glob('windoesnot-restore-*.conf')):
        number = entry.name[len('windoesnot-restore-'):-len('.conf')]
        try:
            text = entry.read_text()
        except OSError:
            continue
        linux = re.search(r'(?m)^linux\s+(\S+)', text)
        initrd = re.search(r'(?m)^initrd\s+(\S+)', text)
        options = re.search(r'(?m)^options\s+(.*)$', text)
        sub = re.search(r'rootflags=(?:\S*,)?subvol=([^\s,]+)', options[1]) if options else None
        if number.isdigit() and linux and initrd and sub:
            found[norm_subvolume(sub[1])] = (linux[1], initrd[1])
    return found


def limine_entries(esp):
    """Snapshot entries of limine.conf as {subvolume: (kernel, initramfs)}, files relative to the ESP.

    Assumption (upstream limine-snapper-sync / limine-entry-tool, NOT verified on a real system): every snapshot
    gets an entry with `kernel_path: boot():/...`, one or more `module_path: boot():/...` (initramfs, maybe
    microcode) and a `cmdline:` containing rootflags=subvol=<path of the snapshot>. Only boot():-paths are used
    (boot() is the partition limine started from, normally the ESP); anything else is ignored. Where the copies
    live below the ESP is deliberately not assumed."""
    lines = []
    for name in ('limine.conf', 'limine/limine.conf', 'EFI/limine/limine.conf', 'EFI/BOOT/limine.conf', 'boot/limine.conf'):
        if (esp / name).is_file():
            try:
                lines = (esp / name).read_text(errors='replace').splitlines()
            except OSError:
                pass
            break
    entries, current = [], None
    for line in lines:
        if line.startswith('/'):
            current = {'modules': []}
            entries.append(current)
            continue
        key, colon, value = line.strip().partition(':')
        if current is None or not colon:
            continue
        value = value.strip()
        path = re.fullmatch(r'boot\(\):\s*(/.*)', value)
        if key == 'kernel_path' and path:
            current['kernel'] = path[1]
        elif key == 'module_path' and path:
            current['modules'].append(path[1])
        elif key in ('cmdline', 'kernel_cmdline'):
            current['cmdline'] = value
    found = {}
    for entry in entries:
        sub = re.search(r'rootflags=(?:\S*,)?subvol=([^\s,]+)', entry.get('cmdline', ''))
        initrd = next((m for m in entry['modules'] if re.search(r'init(ramfs|rd)', Path(m).name)), '')
        if sub and entry.get('kernel') and initrd:
            found[norm_subvolume(sub[1])] = (entry['kernel'], initrd)
    return found


def esp_current_kernels(esp):
    """Kernels installed on the ESP (systemd-boot-manager with the ESP mounted at /boot): vmlinuz-<name> +
    initramfs-<name>.img in the ESP root. Newest first."""
    result = []
    for kernel in esp.glob('vmlinuz-linux*'):
        name = kernel.name[len('vmlinuz-'):]
        initrd = esp / f'initramfs-{name}.img'
        if kernel.is_file() and initrd.is_file() and KERNEL_NAME.fullmatch(name):
            result.append((kernel.stat().st_mtime, name, kernel, initrd))
    return [(name, kernel, initrd) for _, name, kernel, initrd in sorted(result, reverse=True)]


def no_kernel(reason):
    return {'kernel': '', 'source': '', 'esp': '', 'kernel_file': '', 'initrd_file': '', 'note': '', 'reason': reason}


def locate_kernel(snapshot, subvolume, esps):
    """Where to take kernel and initramfs from. `esps` = [(device, mounted path)] of the same disk.

    Returns a dict: kernel (name, '' = cannot start), source, esp (device or ''), kernel_file, initrd_file
    (relative to the snapshot's /boot or to the ESP), note ('current-kernel' = newest ESP kernel of the same
    version, not a copy made for this restore point) and reason (why it cannot be started)."""
    own = next((k for k in KERNELS if (snapshot / 'boot' / f'vmlinuz-{k}').is_file()
                and (snapshot / 'boot' / f'initramfs-{k}.img').is_file()), '')
    if own:
        return {'kernel': own, 'source': 'snapshot', 'esp': '', 'kernel_file': f'vmlinuz-{own}',
                'initrd_file': f'initramfs-{own}.img', 'note': '', 'reason': ''}
    if not esps:
        return no_kernel('no-kernel')
    modules = snapshot_modules(snapshot)
    sub = norm_subvolume(subvolume)
    for device, esp in esps:
        for source, entries in (('esp-restore', bls_restore_entries(esp)), ('esp-limine', limine_entries(esp))):
            if sub not in entries:
                continue
            kernel, initrd = (below(esp, rel) for rel in entries[sub])
            # A copy for another version would boot without its modules: require the snapshot to have them.
            if kernel and initrd and kernel_release(kernel) in modules:
                name = kernel.name[len('vmlinuz-'):] if kernel.name.startswith('vmlinuz-') else ''
                return {'kernel': name if KERNEL_NAME.fullmatch(name) else 'linux-cachyos', 'source': source, 'esp': device,
                        'kernel_file': str(kernel.relative_to(esp.resolve())), 'initrd_file': str(initrd.relative_to(esp.resolve())),
                        'note': '', 'reason': ''}
    for device, esp in esps:
        for name, kernel, initrd in esp_current_kernels(esp):
            if kernel_release(kernel) in modules:
                return {'kernel': name, 'source': 'esp-current', 'esp': device, 'kernel_file': kernel.name,
                        'initrd_file': initrd.name, 'note': 'current-kernel', 'reason': ''}
    return no_kernel('kernel-version-mismatch')


def find_snapshots(top, device, uuid, esps=()):
    """Snapshots below a mounted Btrfs top level (subvolid=5). `top` is the mount point.
    `esps`: [(device, mounted path)] of the EFI system partitions on the same disk (may be empty).
    `kernel` keeps its meaning (kernel package name, '' = cannot be started); the new keys say where it is."""
    found = []
    for config in sorted({*top.glob('.snapshots'), *top.glob('*/.snapshots'), *top.glob('*/*/.snapshots')}):
        for entry in sorted(config.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else -1):
            snapshot = entry / 'snapshot'
            if not entry.name.isdigit() or not snapshot.is_dir() or not (entry / 'info.xml').is_file():
                continue
            name = os_name(snapshot)
            if not name:
                continue
            try:
                info = ET.parse(entry / 'info.xml').getroot()
                text = lambda tag: (info.findtext(tag) or '').strip()
            except ET.ParseError:
                continue
            subvolume = str(snapshot.relative_to(top))
            found.append({'device': device, 'uuid': uuid, 'number': int(entry.name), 'date': text('date'),
                          'description': text('description') or text('type'), 'system': name,
                          'subvolume': subvolume, **locate_kernel(snapshot, subvolume, esps)})
    return found


def parse_block_devices(data):
    """Btrfs filesystems from `lsblk -J -p` output, each with the ESPs (vfat + ESP partition type) of its own disk."""
    seen, devices = set(), []

    def esps_below(item, out):
        if item.get('fstype') == 'vfat' and (item.get('parttype') or '').lower() == ESP_PARTTYPE:
            out.append(item['path'])
        for child in item.get('children') or []:
            esps_below(child, out)
        return out

    def walk(items, esps):
        for item in items:
            if item.get('fstype') == 'btrfs' and item.get('uuid') and item['uuid'] not in seen:
                seen.add(item['uuid'])
                devices.append({**item, 'esps': esps})
            walk(item.get('children') or [], esps)
    for disk in data['blockdevices']:
        walk([disk], esps_below(disk, []))
    return devices


def block_devices():
    data = json.loads(subprocess.check_output(['lsblk', '-J', '-p', '-o', 'PATH,FSTYPE,UUID,TYPE,PARTTYPE'], text=True, timeout=30))
    return parse_block_devices(data)


@contextmanager
def mounted(device, options='ro'):
    """Mount `device` on a temporary directory; yields the path, or None if mounting failed."""
    with tempfile.TemporaryDirectory(prefix='wdn-recovery-') as mount:
        if subprocess.run(['mount', '-o', options, device, mount], capture_output=True, timeout=120).returncode:
            yield None
            return
        try:
            yield Path(mount)
        finally:
            subprocess.run(['umount', '-l', mount], capture_output=True, timeout=60)


def scan():
    found = []
    for device in block_devices():
        with ExitStack() as stack:
            top = stack.enter_context(mounted(device['path'], 'ro,subvolid=5'))
            if top is None:
                continue
            esps = []
            for esp_device in device['esps']:
                esp = stack.enter_context(mounted(esp_device, 'ro,nodev,noexec,nosuid'))
                if esp is not None:
                    esps.append((esp_device, esp))
            found += find_snapshots(top, device['path'], device['uuid'], esps)
    return sorted(found, key=lambda s: (s['device'], -s['number']))


def command_line(uuid, subvolume):
    if not re.fullmatch(r'[0-9A-Fa-f-]+', uuid) or not re.fullmatch(r'[\w@./+-]+', subvolume):
        raise ValueError('Unexpected characters in snapshot location')
    return f'root=UUID={uuid} rootflags=subvol={subvolume} ro quiet splash'


def boot(device, subvolume, kernel):
    if kernel not in KERNELS and not KERNEL_NAME.fullmatch(kernel):
        raise ValueError('Unknown kernel')
    snapshot = next((s for s in scan() if s['device'] == device and s['subvolume'] == subvolume), None)
    if not snapshot or snapshot['kernel'] != kernel:
        raise ValueError(tr('Wiederherstellungspunkt nicht gefunden.', 'Restore point not found.'))
    if not shutil.which('kexec'):
        raise RuntimeError(tr('kexec fehlt.', 'kexec is missing.'))
    cmdline = command_line(snapshot['uuid'], subvolume)
    with ExitStack() as stack:
        top = stack.enter_context(mounted(device, 'ro,subvolid=5'))
        if top is None:
            raise RuntimeError(tr('Die Festplatte konnte nicht eingehängt werden.', 'The disk could not be mounted.'))
        if snapshot['source'] == 'snapshot':
            base = top / subvolume / 'boot'
        else:
            base = stack.enter_context(mounted(snapshot['esp'], 'ro,nodev,noexec,nosuid'))
            if base is None:
                raise RuntimeError(tr('Die EFI-Systempartition konnte nicht eingehängt werden.', 'The EFI system partition could not be mounted.'))
        kernel_file, initrd_file = below(base, snapshot['kernel_file']), below(base, snapshot['initrd_file'])
        if not kernel_file or not initrd_file:
            raise RuntimeError(tr('Kernel oder Initramfs fehlen.', 'Kernel or initramfs is missing.'))
        args = [str(kernel_file), f'--initrd={initrd_file}', f'--command-line={cmdline}']
        # kexec_file_load first: it works under lockdown with a signed kernel; the classic call is the fallback.
        # Both read the files completely, so unmounting afterwards is safe.
        if subprocess.run(['kexec', '-s', '-l', *args], capture_output=True, timeout=120).returncode and \
           subprocess.run(['kexec', '-l', *args], capture_output=True, timeout=120).returncode:
            raise RuntimeError(tr('Der Kernel konnte nicht geladen werden (Secure Boot blockiert kexec?).',
                                  'The kernel could not be loaded (does Secure Boot block kexec?).'))
    subprocess.run(['systemctl', 'kexec'], check=True, timeout=120)


# ---------------------------------------------------------------- permanent rollback
ENV = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
SUBVOLUME_RE = re.compile(r'([\w@+-][\w@.+-]*)/\.snapshots/([1-9][0-9]{0,9})/snapshot')
DEVICE_RE = re.compile(r'/dev/[\w./+-]{1,120}')
TOP_LEVEL_ID = 5


def run(args, timeout=120):
    """Run one fixed command (no shell, bounded time, fixed environment) and return its output."""
    return subprocess.run([str(a) for a in args], env=ENV, text=True, capture_output=True, check=True, timeout=timeout).stdout


def parse_subvolume(subvolume):
    """'@/.snapshots/12/snapshot' -> ('@', 12); anything else (other layouts, '..', odd characters) is refused."""
    match = SUBVOLUME_RE.fullmatch(subvolume or '')
    if not match:
        raise ValueError(tr('Unbekannte Anordnung: Nur <Wurzel>/.snapshots/N/snapshot wird dauerhaft wiederhergestellt.',
                            'Unknown layout: only <root>/.snapshots/N/snapshot can be restored permanently.'))
    return match[1], int(match[2])


def check_name(name):
    if not re.fullmatch(r'[\w@+-][\w@.+-]*', name or ''):
        raise ValueError(tr('Ungültiger Name.', 'Invalid name.'))
    return name


def listing(top):
    """Top-level names plus '<name>/.snapshots' where that exists: all the planner needs to know."""
    names = {entry.name for entry in top.iterdir()}
    return names | {f'{name}/.snapshots' for name in names if (top / name / '.snapshots').is_dir()}


def timestamp():
    return time.strftime('%Y%m%d-%H%M%S', time.gmtime())


def plan_rollback(entries, root, number, stamp):
    """Steps (kind, a, b) from a directory listing. Pure; nothing is deleted, the old root is only renamed."""
    check_name(root)
    if not re.fullmatch(r'\d{8}-\d{6}', stamp) or type(number) is not int or number < 1:
        raise ValueError('Invalid timestamp or number')
    backup = f'{root}-before-restore-{stamp}'
    if root not in entries or f'{root}/.snapshots' not in entries:
        raise ValueError(tr('Wurzel oder .snapshots fehlt.', 'Root or .snapshots is missing.'))
    if backup in entries:
        raise ValueError(tr('Sicherungsname existiert schon.', 'Backup name already exists.'))
    return [('rename', root, backup),
            ('snapshot', f'{backup}/.snapshots/{number}/snapshot', root),
            ('rmdir', f'{root}/.snapshots', ''),   # the empty stub a snapshot leaves where the nested subvolume was
            ('rename', f'{backup}/.snapshots', f'{root}/.snapshots')]


def backups_of(entries, root):
    return sorted(n for n in entries if re.fullmatch(re.escape(root) + r'-before-restore-\d{8}-\d{6}', n))


def plan_undo(entries, root, stamp):
    """Swap the newest '<root>-before-restore-*' back in; the current root is renamed, never deleted."""
    check_name(root)
    backups = backups_of(entries, root)
    if not backups:
        raise ValueError(tr('Keine Sicherung eines früheren Systems gefunden.', 'No earlier system to go back to.'))
    backup, undone = backups[-1], f'{root}-undone-{stamp}'
    if root not in entries or undone in entries or not re.fullmatch(r'\d{8}-\d{6}', stamp):
        raise ValueError(tr('Wurzel fehlt oder Name existiert schon.', 'Root is missing or the name already exists.'))
    steps = [('rename', root, undone)]
    if f'{root}/.snapshots' in entries:
        steps += [('rmdir', f'{backup}/.snapshots', ''), ('rename', f'{undone}/.snapshots', f'{backup}/.snapshots')]
    return steps + [('rename', backup, root)]


def parse_default(text):
    """`btrfs subvolume get-default`: (id, path or None)."""
    match = re.match(r'ID (\d+)(?: gen \d+ top level \d+ path (.+)|\s+\(FS_TREE\))?\s*$', text.strip())
    if not match:
        raise ValueError(tr('Standard-Subvolume nicht lesbar.', 'Cannot read the default subvolume.'))
    return int(match[1]), match[2]


def default_action(default, root):
    """None if the default is the top level, 'set' if it points at the root being replaced, else refuse."""
    ident, path = default
    if ident == TOP_LEVEL_ID:
        return None
    if path == root:
        return 'set'
    raise ValueError(tr('Das Standard-Subvolume ist weder die Wurzel noch die oberste Ebene.',
                        'The default subvolume is neither the root nor the top level.'))


def parse_subvolume_id(text):
    match = re.search(r'(?m)^\s*Subvolume ID:\s+(\d+)\s*$', text)
    if not match:
        raise ValueError('Cannot read the subvolume ID')
    return int(match[1])


def nested_problems(list_output, root):
    """Subvolumes below the root other than .snapshots (a snapshot-based rollback would lose them)."""
    bad = []
    for line in list_output.splitlines():
        path = line.partition(' path ')[2].strip()
        child = path.removeprefix(root + '/') if path else ''
        if child and child != '.snapshots' and not child.startswith('.snapshots/'):
            bad.append(path)
    return bad


def fstab_problems(text, root, exists):
    """The snapshot's fstab must name the root by subvolume NAME, not id, and every named subvolume must exist."""
    problems, has_root = [], False
    for line in text.splitlines():
        fields = line.split('#')[0].split()
        if len(fields) < 4 or fields[2] != 'btrfs':
            continue
        options = dict(o.partition('=')[::2] for o in fields[3].split(','))
        if 'subvolid' in options:
            problems.append(tr(f'{fields[1]}: subvolid wird verwendet', f'{fields[1]}: uses subvolid'))
        name = options.get('subvol', '').strip('/')
        if fields[1] == '/':
            has_root = True
            if name != root:
                problems.append(tr(f'/: subvol={name or "(fehlt)"}, erwartet {root}', f'/: subvol={name or "(missing)"}, expected {root}'))
        elif name and not exists(name):
            problems.append(tr(f'{fields[1]}: Subvolume {name} fehlt', f'{fields[1]}: subvolume {name} does not exist'))
    if not has_root:
        problems.append(tr('/ steht nicht als Btrfs in der fstab', '/ is not a Btrfs entry in fstab'))
    return problems


def check_device(device):
    if not DEVICE_RE.fullmatch(device or '') or '..' in device:
        raise ValueError(tr('Ungültiges Gerät.', 'Invalid device.'))
    if device not in [d['path'] for d in block_devices()]:
        raise ValueError(tr('Das ist kein Btrfs-Datenträger.', 'Not a Btrfs disk.'))
    chain = json.loads(run(['lsblk', '-J', '-s', '-p', '-o', 'PATH,FSTYPE,TYPE', device], timeout=30))
    def encrypted(items):
        return any(i.get('fstype') == 'crypto_LUKS' or i.get('type') == 'crypt' or encrypted(i.get('children') or []) for i in items)
    if encrypted(chain['blockdevices']):
        raise ValueError(tr('Verschlüsselte (LUKS) Datenträger werden hier nicht dauerhaft zurückgesetzt.',
                            'Encrypted (LUKS) disks are not rolled back permanently here.'))
    if subprocess.run(['findmnt', '-n', '-S', device], env=ENV, capture_output=True, timeout=10).stdout.strip():
        raise ValueError(tr('Der Datenträger ist schon eingehängt.', 'The disk is already mounted.'))


def apply_steps(top, steps, runner=None):
    """Run the steps below `top`; on failure undo the ones done so far (reverse order). The only thing ever
    deleted is the new root created here when a later step fails."""
    runner = runner or run
    done = []
    try:
        for kind, a, b in steps:
            if kind == 'rename':
                os.rename(top / a, top / b)
            elif kind == 'snapshot':
                runner(['btrfs', 'subvolume', 'snapshot', top / a, top / b])
            elif kind == 'rmdir':
                if (top / a).is_dir():
                    (top / a).rmdir()
            else:
                raise ValueError('Unknown step')
            done.append((kind, a, b))
    except Exception:
        for kind, a, b in reversed(done):
            try:
                if kind == 'rename':
                    os.rename(top / b, top / a)
                elif kind == 'snapshot':
                    runner(['btrfs', 'subvolume', 'delete', top / b])
                elif kind == 'rmdir':
                    (top / a).mkdir(exist_ok=True)
            except (OSError, subprocess.SubprocessError):
                pass
        raise


def mount_top(device, mount):
    run(['mount', '-t', 'btrfs', '-o', 'subvolid=5,nosuid,nodev', device, mount], timeout=120)


def set_default_to(top, root):
    run(['btrfs', 'subvolume', 'set-default', parse_subvolume_id(run(['btrfs', 'subvolume', 'show', top / root])), top])


def locked_top(device, work):
    """Mount the top level rw (one operation at a time), call work(top), always unmount."""
    import fcntl
    check_device(device)
    Path('/run/windoesnot').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wdn-rollback-') as mount, open('/run/windoesnot/recovery.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError(tr('Es läuft schon eine Wiederherstellung.', 'Another restore is running.'))
        mount_top(device, mount)
        try:
            return work(Path(mount))
        finally:
            run(['umount', mount], timeout=60)


def rollback(device, subvolume, stamp=None):
    """Make the snapshot the new root. Returns report lines. Raises before changing anything when the layout
    cannot be verified; a failure after the first change is rolled back."""
    root, number = parse_subvolume(subvolume)
    stamp = stamp or timestamp()
    return locked_top(device, lambda top: _rollback_mounted(top, device, root, number, stamp))


def _rollback_mounted(top, device, root, number, stamp):
    snap = next((s for s in find_snapshots(top, device, '') if s['subvolume'] == f'{root}/.snapshots/{number}/snapshot'), None)
    if not snap:
        raise ValueError(tr('Wiederherstellungspunkt nicht gefunden.', 'Restore point not found.'))
    if not snap['kernel']:
        raise ValueError(tr('Der Kernel liegt nicht im Punkt (z. B. auf der ESP); das System würde nicht booten.',
                            'The kernel is not inside the restore point (for example on the ESP); the system would not boot.'))
    point = top / snap['subvolume']
    if any(p.is_symlink() for p in (top / root, top / root / '.snapshots', point)):
        raise ValueError('Invalid path')
    if nested_problems(run(['btrfs', 'subvolume', 'list', '-o', top / root]), root):
        raise ValueError(tr('Weitere verschachtelte Subvolumes: nicht automatisch wiederherstellbar.',
                            'Additional nested subvolumes: cannot be restored automatically.'))
    problems = fstab_problems((point / 'etc/fstab').read_text(), root, lambda name: (top / name).is_dir())
    if problems:
        raise ValueError(tr('fstab des Punkts nicht verwendbar: ', 'The restore point fstab is not usable: ') + '; '.join(problems))
    action = default_action(parse_default(run(['btrfs', 'subvolume', 'get-default', top])), root)
    steps = plan_rollback(listing(top), root, number, stamp)
    backup = f'{root}-before-restore-{stamp}'
    apply_steps(top, steps)
    try:
        (top / root / 'var/lib/pacman/db.lck').unlink(missing_ok=True)
        state = top / root / 'var/lib/windoesnot/last-restore.json'
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({'schema_version': 1, 'restored_point': number, 'previous_root': backup}) + '\n')
        if action == 'set':
            set_default_to(top, root)
        run(['sync'], timeout=120)
    except Exception:
        apply_steps(top, plan_undo(listing(top), root, stamp))
        raise
    return [tr(f'Punkt {number} ist jetzt das System ({root}).', f'Restore point {number} is now the system ({root}).'),
            tr(f'Das alte System bleibt als {backup} erhalten (Rückgängig: recovery.py undo {device} {root}).',
               f'The old system is kept as {backup} (undo: recovery.py undo {device} {root}).'),
            tr('fstab und Kernel stammen aus dem Punkt; Bootloader-Einträge auf der ESP wurden nicht angefasst. Jetzt neu starten.',
               'fstab and kernel come from the point; bootloader entries on the ESP were not touched. Reboot now.')] + next_steps()


def next_steps():
    """Shown after a permanent rollback or undo. Bootloader files are not touched from the live session."""
    return [tr('Nächste Schritte: Neu starten und das wiederhergestellte System booten. Die Bootloader-Einträge (GRUB grub.cfg, '
               'Limine, rEFInd, systemd-boot-Wiederherstellungspunkte) erzeugen die Hooks des installierten Systems beim nächsten '
               'Kernel- oder Snapshot-Wechsel oder über das jeweilige Bootloader-Werkzeug neu.',
               'Next steps: reboot into the restored system. Its own hooks regenerate the bootloader entries (GRUB grub.cfg, '
               'Limine, rEFInd, systemd-boot restore point entries) on the next kernel or snapshot change, or when you run the '
               'bootloader tool.'),
            tr('Wirkt das Boot-Menü veraltet, im wiederhergestellten System ausführen: sudo snapper -c root create (löst die Hooks aus).',
               'If the boot menu looks stale, run this in the restored system: sudo snapper -c root create (this triggers the hooks).')]


def undo(device, root, stamp=None):
    check_name(root)
    stamp = stamp or timestamp()
    return locked_top(device, lambda top: _undo_mounted(top, device, root, stamp))


def _undo_mounted(top, device, root, stamp):
    entries = listing(top)
    steps = plan_undo(entries, root, stamp)
    if not os_name(top / backups_of(entries, root)[-1]):
        raise ValueError(tr('Die Sicherung ist kein WinDoesNot-System.', 'The backup is not a WinDoesNot system.'))
    action = default_action(parse_default(run(['btrfs', 'subvolume', 'get-default', top])), root)
    apply_steps(top, steps)
    if action == 'set':
        set_default_to(top, root)
    run(['sync'], timeout=120)
    return [tr(f'Das frühere System ist wieder {root}; das bisherige liegt als {root}-undone-{stamp}.',
               f'The earlier system is {root} again; the one replaced is kept as {root}-undone-{stamp}.')] + next_steps()


def menu_rollback(item):
    word = tr('WIEDERHERSTELLEN', 'RESTORE')
    try:
        root, number = parse_subvolume(item['subvolume'])
    except ValueError as error:
        print(error)
        return 1
    print(tr(f'{root} auf {item["device"]} wird durch Punkt {number} ({item["date"]}) ersetzt. Das alte System wird nur umbenannt '
             f'und bleibt als Rückgängig-Punkt erhalten.',
             f'{root} on {item["device"]} will be replaced by point {number} ({item["date"]}). The old system is only renamed '
             f'and kept as an undo point.'))
    if input(tr(f'Zur Bestätigung {word} eintippen: ', f'Type {word} to confirm: ')).strip() != word:
        return 0
    try:
        print('\n'.join(rollback(item['device'], item['subvolume'])))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(tr('Nichts wurde geändert oder es wurde zurückgerollt: ', 'Nothing was changed, or it was rolled back: ')
              + str(getattr(error, 'stderr', None) or error), file=sys.stderr)
        return 1
    return 0


BACKUP_RE = re.compile(r'(.+)-before-restore-(\d{8})-(\d{6})')


def find_backups(top, device):
    """Newest '<root>-before-restore-<time>' per root below a mounted top level: the only one `undo` swaps back."""
    names = sorted(entry.name for entry in top.iterdir() if entry.is_dir() and not entry.is_symlink())
    found = []
    for root in sorted({m[1] for m in map(BACKUP_RE.fullmatch, names) if m}):
        newest = backups_of(names, root)[-1]
        if root not in names or not os_name(top / newest):
            continue
        day, clock = BACKUP_RE.fullmatch(newest).groups()[1:]
        date = f'{day[:4]}-{day[4:6]}-{day[6:]} {clock[:2]}:{clock[2:4]}:{clock[4:]}'
        found.append({'device': device, 'root': root, 'backup': newest, 'date': date})
    return found


def scan_backups():
    found = []
    for device in block_devices():
        with mounted(device['path'], 'ro,subvolid=5') as top:
            if top is not None:
                found += find_backups(top, device['path'])
    return found


def menu_undo():
    print(tr('Suche frühere Systeme …', 'Looking for earlier systems …'))
    items = scan_backups()
    if not items:
        print(tr('Keine Sicherung einer Wiederherstellung gefunden.', 'No backup of an earlier restore found.'))
        return 1
    for index, item in enumerate(items, 1):
        print(f"{index:3}  {item['date']}  {item['backup']}  [{item['device']}]")
    choice = input(tr('Nummer zum Rückgängigmachen (leer = Abbruch): ', 'Number to undo (empty = cancel): ')).strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(items):
        return 0
    item = items[int(choice) - 1]
    word = tr('RÜCKGÄNGIG', 'UNDO')
    print(tr(f'{item["root"]} auf {item["device"]} wird durch das frühere System ({item["date"]}) ersetzt. Das aktuelle System wird nur '
             f'umbenannt und bleibt erhalten.',
             f'{item["root"]} on {item["device"]} will be replaced by the earlier system ({item["date"]}). The current system is only '
             f'renamed and kept.'))
    if input(tr(f'Zur Bestätigung {word} eintippen: ', f'Type {word} to confirm: ')).strip() != word:
        return 0
    try:
        print('\n'.join(undo(item['device'], item['root'])))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(tr('Nichts wurde geändert: ', 'Nothing was changed: ') + str(getattr(error, 'stderr', None) or error), file=sys.stderr)
        return 1
    return 0


def status_text(item):
    """Suffix for the menu line: why a restore point cannot start, or what to be aware of."""
    if item['kernel']:
        if item.get('note') == 'current-kernel':
            return '  ' + tr('(nutzt den aktuellen Kernel, Module können abweichen)', '(uses the current kernel, modules may differ)')
        return ''
    if item.get('reason') == 'kernel-version-mismatch':
        return '  ' + tr('(nicht startbar: Kernel auf der ESP passt nicht zur Version im Punkt)',
                          '(cannot start: the kernel on the ESP does not match the version in the restore point)')
    return '  ' + tr('(nicht startbar: Kernel liegt nicht im Punkt)', '(cannot start: kernel is not in the restore point)')


def menu():
    print(tr('1 = Wiederherstellungspunkt starten oder wiederherstellen', '1 = start or restore a restore point'))
    print(tr('2 = eine Wiederherstellung rückgängig machen', '2 = undo a restore'))
    top_choice = input(tr('Auswahl (leer = Abbruch): ', 'Choice (empty = cancel): ')).strip()
    if top_choice == '2':
        return menu_undo()
    if top_choice != '1':
        return 0
    print(tr('Suche Wiederherstellungspunkte …', 'Looking for restore points …'))
    items = scan()
    if not items:
        print(tr('Keine Wiederherstellungspunkte gefunden.', 'No restore points found.'))
        return 1
    for index, item in enumerate(items, 1):
        mark = status_text(item)
        print(f"{index:3}  {item['date']}  {item['description']}  [{item['system']}, {item['device']}]{mark}")
    choice = input(tr('Nummer zum Starten (leer = Abbruch): ', 'Number to start (empty = cancel): ')).strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(items):
        return 0
    item = items[int(choice) - 1]
    if not item['kernel']:
        print(tr('Dieser Punkt kann nicht direkt gestartet werden.', 'This restore point cannot be started directly.'))
        return 1
    print(tr('1 = schreibgeschützt starten (Änderungen gehen beim Ausschalten verloren)',
             '1 = boot read-only (changes are lost at shutdown)'))
    print(tr('2 = dauerhaft wiederherstellen (das aktuelle System bleibt als Sicherung erhalten)',
             '2 = restore permanently (the current system is kept as a backup)'))
    mode = input(tr('Auswahl (leer = Abbruch): ', 'Choice (empty = cancel): ')).strip()
    if mode == '2':
        return menu_rollback(item)
    if mode != '1':
        return 0
    print(tr('Der Punkt wird schreibgeschützt gestartet; Änderungen darin gehen beim Ausschalten verloren.',
             'The restore point starts read-only; changes made in it are lost at shutdown.'))
    if input(tr('Jetzt starten? [j/N] ', 'Start now? [y/N] ')).strip().lower() not in ('j', 'y'):
        return 0
    boot(item['device'], item['subvolume'], item['kernel'])
    return 0


CACHE = Path('/run/windoesnot/restore-points.json')
ENTRY = Path('/usr/share/windoesnot/recovery/windoesnot-recovery.desktop')


def scan_cache():
    """Live start: remember what was found for the settings window and show the menu entry only if there is something."""
    items = scan()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(items))
    CACHE.chmod(0o644)
    if items and ENTRY.is_file():
        for target in (Path('/usr/share/applications'), Path('/home/liveuser/Desktop')):
            if target.is_dir():
                shutil.copy2(ENTRY, target / ENTRY.name)
    return 0


def main(argv):
    if os.geteuid() != 0:
        raise SystemExit('Run as root')
    try:
        if argv[:1] == ['list'] and len(argv) == 1:
            print(json.dumps(scan()))
        elif argv[:1] == ['boot'] and len(argv) == 4:
            boot(*argv[1:])
        elif argv[:1] == ['rollback'] and len(argv) == 3:
            print('\n'.join(rollback(*argv[1:])))
        elif argv[:1] == ['undo'] and len(argv) == 3:
            print('\n'.join(undo(*argv[1:])))
        elif argv == ['scan-cache']:
            return scan_cache()
        elif argv == ['menu']:
            return menu()
        else:
            raise SystemExit(__doc__)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(getattr(error, 'stderr', None) or error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
