#!/usr/bin/python3
"""systemd-boot restore points: boot entries for the newest Snapper snapshots of the installed system.

systemd-boot (with systemd-boot-manager, ESP mounted at /boot) keeps kernel and initramfs on the ESP, so a
snapshot has none of its own and systemd-boot cannot list snapshots like grub-btrfs does. This helper
  * takes the newest MAX_ENTRIES snapshots below /.snapshots,
  * copies the kernel and initramfs that belong to each one to <ESP>/windoesnot-restore/<release>-<hash>/
    (identical copies, for example the pre and post snapshot of one transaction, share a directory),
  * writes <ESP>/loader/entries/windoesnot-restore-<N>.conf (Boot Loader Specification type 1):
        title WinDoesNot restore point <date>
        options root=UUID=<fs uuid> rootflags=subvol=<snapshot subvolume> ro ...
  * removes entries and copies of snapshots that are gone or no longer among the newest.
recovery.py (live session) reads exactly these entries (windoesnot-restore-<N>.conf).

Assumptions (explicit, not verified on a real system):
  * Kernel and initramfs are in the ESP root as vmlinuz-<pkgbase> / initramfs-<pkgbase>.img (what
    sdboot-manage and tools/bootnames expect when the ESP is /boot). Other layouts (XBOOTLDR, UKI) are skipped.
  * The files on the ESP at snapshot creation time are the ones that belong to that snapshot. That is why this
    runs in a pacman PreTransaction hook right after snap-pac's pre snapshot, and again PostTransaction; the
    copy is only made when the kernel's version equals a /usr/lib/modules/<version> directory of the snapshot.
    A snapshot whose kernel is already replaced on the ESP gets no entry (it could not load its modules).
  * The snapshot's initramfs contains the windoesnot-snapshot-overlay hook (iso/installation.py), which makes
    the read-only snapshot root usable with a RAM overlay.
  * The ESP is small: a copy is skipped when less than the size of the files plus 16 MiB is free.
Only active when /etc/windoesnot/sdboot-snapshots.conf exists (written by iso/installation.py for systemd-boot).
Usage (root): sdboot_snapshots.py sync"""
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

MAX_ENTRIES = 3
STORE = 'windoesnot-restore'
ENTRY_RE = re.compile(r'windoesnot-restore-(\d+)\.conf')
SPARE = 16 * 1024 * 1024
MARKER = Path('/etc/windoesnot/sdboot-snapshots.conf')
LOCK = Path('/run/windoesnot-sdboot-snapshots.lock')
DROP_OPTIONS = re.compile(r'(root|rootflags|rootfstype|initrd|BOOT_IMAGE)=\S*|rw|ro')


def kernel_release(path):
    """Version of an x86 bzImage ('6.12.5-2-cachyos') or ''. Same code as recovery.kernel_release (tests compare)."""
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


def read_snapshots(snapshots_dir):
    """Complete snapshots (info.xml + snapshot/), newest first: [{'number', 'date', 'path'}]."""
    found = []
    for entry in Path(snapshots_dir).iterdir() if Path(snapshots_dir).is_dir() else ():
        if not entry.name.isdigit() or not (entry / 'snapshot').is_dir() or not (entry / 'info.xml').is_file():
            continue
        try:
            date = (ET.parse(entry / 'info.xml').getroot().findtext('date') or '').strip()
        except ET.ParseError:
            continue
        found.append({'number': int(entry.name), 'date': date[:16], 'path': entry / 'snapshot'})
    return sorted(found, key=lambda s: -s['number'])


def esp_kernels(esp):
    """[(name, kernel file, initramfs file)] in the ESP root; linux-cachyos first."""
    result = []
    for kernel in Path(esp).glob('vmlinuz-linux*'):
        name = kernel.name[len('vmlinuz-'):]
        initrd = Path(esp) / f'initramfs-{name}.img'
        if kernel.is_file() and initrd.is_file() and re.fullmatch(r'linux[A-Za-z0-9_+.-]*', name):
            result.append((name, kernel, initrd))
    return sorted(result, key=lambda item: (item[0] != 'linux-cachyos', item[0]))


def pick_kernel(snapshot, esp):
    """(release, kernel, initramfs) of the ESP kernel whose version the snapshot has modules for, else None."""
    try:
        modules = {p.name for p in (Path(snapshot) / 'usr/lib/modules').iterdir() if p.is_dir()}
    except OSError:
        return None
    for _, kernel, initrd in esp_kernels(esp):
        release = kernel_release(kernel)
        if release and release in modules:
            return release, kernel, initrd
    return None


def digest(*files):
    total = hashlib.sha256()
    for file in files:
        with open(file, 'rb') as handle:
            for block in iter(lambda: handle.read(1 << 20), b''):
                total.update(block)
    return total.hexdigest()[:12]


def entry_options(base, uuid, subvolume):
    """Kernel command line of the running system's entry without root/rootflags/ro/rw, then ours."""
    if not re.fullmatch(r'[0-9A-Fa-f-]+', uuid) or not re.fullmatch(r'[\w@./+-]+', subvolume):
        raise ValueError('Unexpected characters in snapshot location')
    kept = [word for word in base.split() if not DROP_OPTIONS.fullmatch(word) and re.fullmatch(r'[\w@./:+=,-]+', word)]
    return ' '.join([f'root=UUID={uuid}', f'rootflags=subvol={subvolume}', 'ro', *kept])


def base_options(esp, cmdline=''):
    """Options of the first regular sdboot-manage entry on the ESP, else the running kernel's command line."""
    for entry in sorted((Path(esp) / 'loader/entries').glob('*.conf')):
        if ENTRY_RE.fullmatch(entry.name) or 'fallback' in entry.name:
            continue
        found = re.search(r'(?m)^options\s+(.*)$', entry.read_text())
        if found:
            return found[1]
    return cmdline


def render_entry(number, date, linux, initrd, options):
    return (f'title WinDoesNot restore point {date}\n'
            f'sort-key windoesnot-restore\n'
            f'version snapshot {number}\n'
            f'linux /{linux}\n'
            f'initrd /{initrd}\n'
            f'options {options}\n')


def existing(esp):
    """{number: store directory name} of valid entries on the ESP."""
    result = {}
    for entry in (Path(esp) / 'loader/entries').glob('windoesnot-restore-*.conf'):
        number = ENTRY_RE.fullmatch(entry.name)
        found = re.search(r'(?m)^linux\s+/' + re.escape(STORE) + r'/([^/\s]+)/vmlinuz\s*$', entry.read_text())
        if number and found and (Path(esp) / STORE / found[1] / 'vmlinuz').is_file() and (Path(esp) / STORE / found[1] / 'initramfs.img').is_file():
            result[int(number[1])] = found[1]
    return result


def choose(snapshots, esp, limit=MAX_ENTRIES):
    """Newest snapshots that already have a valid entry or can get one now. [(snapshot, kept store dir or None)]"""
    have = existing(esp)
    chosen = []
    for snapshot in snapshots:
        if len(chosen) == limit:
            break
        if snapshot['number'] in have:
            chosen.append((snapshot, have[snapshot['number']]))
        elif pick_kernel(snapshot['path'], esp):
            chosen.append((snapshot, None))
    return chosen


def remove_stale(esp, keep_numbers, keep_dirs):
    """Delete only our own entries and store directories that are not wanted."""
    removed = []
    for entry in sorted((Path(esp) / 'loader/entries').glob('windoesnot-restore-*.conf')):
        number = ENTRY_RE.fullmatch(entry.name)
        if number and int(number[1]) not in keep_numbers:
            entry.unlink()
            removed.append(entry.name)
    store = Path(esp) / STORE
    if store.is_dir() and not store.is_symlink():
        for directory in sorted(store.iterdir()):
            if directory.name not in keep_dirs and directory.is_dir() and not directory.is_symlink():
                shutil.rmtree(directory)
                removed.append(f'{STORE}/{directory.name}/')
    return removed


def copy_store(esp, kernel, initrd, release):
    """Copy kernel + initramfs into <ESP>/windoesnot-restore/<release>-<hash>/ (atomic rename); None if the ESP is too full."""
    name = f'{release}-{digest(kernel, initrd)}'
    target = Path(esp) / STORE / name
    if (target / 'vmlinuz').is_file() and (target / 'initramfs.img').is_file():
        return name
    need = kernel.stat().st_size + initrd.stat().st_size + SPARE
    if shutil.disk_usage(esp).free < need:
        return None
    temporary = target.with_name(name + '.tmp')
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    shutil.copyfile(kernel, temporary / 'vmlinuz')
    shutil.copyfile(initrd, temporary / 'initramfs.img')
    shutil.rmtree(target, ignore_errors=True)
    os.rename(temporary, target)
    return name


def sync(esp, snapshots_dir, uuid, root_subvolume, base='', limit=MAX_ENTRIES):
    """Make the ESP match the newest snapshots. Returns {'added': [...], 'removed': [...], 'skipped': [...]}."""
    esp = Path(esp)
    snapshots = read_snapshots(snapshots_dir)
    chosen = choose(snapshots, esp, limit)
    keep_numbers = {snapshot['number'] for snapshot, _ in chosen}
    keep_dirs = {directory for _, directory in chosen if directory}
    result = {'added': [], 'removed': [], 'skipped': []}
    # Removal first: it frees the space the new copy needs. Directories a new entry will use are kept below.
    for snapshot, directory in chosen:
        if not directory:
            release, kernel, initrd = pick_kernel(snapshot['path'], esp)
            keep_dirs.add(f'{release}-{digest(kernel, initrd)}')
    result['removed'] = remove_stale(esp, keep_numbers, keep_dirs)
    entries = esp / 'loader/entries'
    entries.mkdir(parents=True, exist_ok=True)
    for snapshot, directory in chosen:
        if directory:
            continue
        release, kernel, initrd = pick_kernel(snapshot['path'], esp)
        stored = copy_store(esp, kernel, initrd, release)
        if not stored:
            result['skipped'].append(snapshot['number'])
            continue
        subvolume = '/'.join(part for part in (root_subvolume.strip('/'), '.snapshots', str(snapshot['number']), 'snapshot') if part)
        text = render_entry(snapshot['number'], snapshot['date'] or f"snapshot {snapshot['number']}", f'{STORE}/{stored}/vmlinuz',
                            f'{STORE}/{stored}/initramfs.img', entry_options(base, uuid, subvolume))
        entry = entries / f"windoesnot-restore-{snapshot['number']}.conf"
        temporary = entry.with_name(entry.name + '.tmp')
        temporary.write_text(text)
        os.replace(temporary, entry)
        result['added'].append(snapshot['number'])
    return result


def run(command, timeout=20):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True).stdout.strip()


def main(argv):
    if argv != ['sync']:
        raise SystemExit(__doc__)
    if not MARKER.is_file():
        return 0
    if os.geteuid() != 0:
        raise SystemExit('Run as root')
    try:
        with open(LOCK, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if run(['findmnt', '-n', '-o', 'FSTYPE', '--target', '/']) != 'btrfs':
                return 0
            esp = run(['bootctl', '-p'])
            uuid = run(['findmnt', '-n', '-o', 'UUID', '--target', '/'])
            subvolume = run(['findmnt', '-n', '-o', 'FSROOT', '--target', '/'])
            cmdline = Path('/proc/cmdline').read_text()
            result = sync(esp, '/.snapshots', uuid, re.sub(r'\[.*\]', '', subvolume), base_options(esp, cmdline))
            for key in ('added', 'removed', 'skipped'):
                if result[key]:
                    print(f'WinDoesNot restore points, {key}: {", ".join(map(str, result[key]))}')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # A pacman hook must never fail the transaction because of a boot-menu extra.
        print(f'WinDoesNot restore points not updated: {error}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
