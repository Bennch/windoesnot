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
Usage (root): recovery.py list | recovery.py scan-cache | recovery.py boot DEVICE SUBVOLUME KERNEL_NAME | recovery.py menu"""
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
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
        elif argv == ['scan-cache']:
            return scan_cache()
        elif argv == ['menu']:
            return menu()
        else:
            raise SystemExit(__doc__)
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
