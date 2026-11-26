#!/usr/bin/env python3
"""Find WinDoesNot restore points (Snapper snapshots) on the disks and start one from the live session.

The snapshot's own kernel and initramfs are loaded with kexec and the snapshot is mounted read-only as the
root (the initramfs adds a RAM overlay, see iso/installation.py). Nothing on the disks is written.
Usage (root): recovery.py list | recovery.py boot DEVICE SUBVOLUME KERNEL_NAME | recovery.py menu"""
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


def find_snapshots(top, device, uuid):
    """Snapshots below a mounted Btrfs top level (subvolid=5). `top` is the mount point."""
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
            kernel = next((k for k in KERNELS if (snapshot / 'boot' / f'vmlinuz-{k}').is_file()
                           and (snapshot / 'boot' / f'initramfs-{k}.img').is_file()), '')
            found.append({'device': device, 'uuid': uuid, 'number': int(entry.name), 'date': text('date'),
                          'description': text('description') or text('type'), 'system': name,
                          'subvolume': str(snapshot.relative_to(top)), 'kernel': kernel})
    return found


def block_devices():
    data = json.loads(subprocess.check_output(['lsblk', '-J', '-p', '-o', 'PATH,FSTYPE,UUID,TYPE'], text=True, timeout=30))
    seen, devices = set(), []
    def walk(items):
        for item in items:
            if item.get('fstype') == 'btrfs' and item.get('uuid') and item['uuid'] not in seen:
                seen.add(item['uuid'])
                devices.append(item)
            walk(item.get('children') or [])
    walk(data['blockdevices'])
    return devices


def scan():
    found = []
    for device in block_devices():
        with tempfile.TemporaryDirectory(prefix='wdn-recovery-') as mount:
            if subprocess.run(['mount', '-o', 'ro,subvolid=5', device['path'], mount], capture_output=True, timeout=120).returncode:
                continue
            try:
                found += find_snapshots(Path(mount), device['path'], device['uuid'])
            finally:
                subprocess.run(['umount', '-l', mount], capture_output=True, timeout=60)
    return sorted(found, key=lambda s: (s['device'], -s['number']))


def command_line(uuid, subvolume):
    if not re.fullmatch(r'[0-9A-Fa-f-]+', uuid) or not re.fullmatch(r'[\w@./+-]+', subvolume):
        raise ValueError('Unexpected characters in snapshot location')
    return f'root=UUID={uuid} rootflags=subvol={subvolume} ro quiet splash'


def boot(device, subvolume, kernel):
    if kernel not in KERNELS:
        raise ValueError('Unknown kernel')
    snapshot = next((s for s in scan() if s['device'] == device and s['subvolume'] == subvolume), None)
    if not snapshot or snapshot['kernel'] != kernel:
        raise ValueError(tr('Wiederherstellungspunkt nicht gefunden.', 'Restore point not found.'))
    if not shutil.which('kexec'):
        raise RuntimeError(tr('kexec fehlt.', 'kexec is missing.'))
    cmdline = command_line(snapshot['uuid'], subvolume)
    with tempfile.TemporaryDirectory(prefix='wdn-recovery-') as mount:
        subprocess.run(['mount', '-o', 'ro,subvolid=5', device, mount], check=True, timeout=120)
        try:
            boot_dir = Path(mount) / subvolume / 'boot'
            args = [str(boot_dir / f'vmlinuz-{kernel}'), f'--initrd={boot_dir / f"initramfs-{kernel}.img"}', f'--command-line={cmdline}']
            # kexec_file_load first: it works under lockdown with a signed kernel; the classic call is the fallback.
            if subprocess.run(['kexec', '-s', '-l', *args], capture_output=True, timeout=120).returncode and \
               subprocess.run(['kexec', '-l', *args], capture_output=True, timeout=120).returncode:
                raise RuntimeError(tr('Der Kernel konnte nicht geladen werden (Secure Boot blockiert kexec?).',
                                      'The kernel could not be loaded (does Secure Boot block kexec?).'))
        finally:
            subprocess.run(['umount', '-l', mount], capture_output=True, timeout=60)
    subprocess.run(['systemctl', 'kexec'], check=True, timeout=120)


def menu():
    print(tr('Suche Wiederherstellungspunkte …', 'Looking for restore points …'))
    items = scan()
    if not items:
        print(tr('Keine Wiederherstellungspunkte gefunden.', 'No restore points found.'))
        return 1
    for index, item in enumerate(items, 1):
        mark = '' if item['kernel'] else '  ' + tr('(nicht startbar: Kernel liegt nicht im Punkt)', '(cannot start: kernel is not in the restore point)')
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


def main(argv):
    if os.geteuid() != 0:
        raise SystemExit('Run as root')
    try:
        if argv[:1] == ['list'] and len(argv) == 1:
            print(json.dumps(scan()))
        elif argv[:1] == ['boot'] and len(argv) == 4:
            boot(*argv[1:])
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
