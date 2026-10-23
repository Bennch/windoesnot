#!/usr/bin/env python3
"""Configure the chosen bootloader and Btrfs snapshots in an install target."""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys

BASE = Path('/usr/share/windoesnot')
sys.path.insert(0, str(Path(__file__).resolve().parent / 'software'))
from repository import install_packages

BOOT_PACKAGES = {
    'grub': ['grub', 'os-prober'],
    'refind': ['refind'],
    'systemd-boot': ['systemd-boot-manager'],
    'limine': ['limine', 'limine-mkinitcpio-hook'],
}
BOOT_EXTRA_PACKAGES = sorted({name for packages in BOOT_PACKAGES.values() for name in packages} | {'snapper'})


def validate_choice(bootloader, firmware, mode):
    if bootloader not in BOOT_PACKAGES or mode not in ('offline', 'online'):
        raise ValueError('Missing or unsupported bootloader / installation mode')
    if firmware not in ('efi', 'bios'):
        raise ValueError('Unsupported firmware type')
    if firmware != 'efi' and bootloader in ('refind', 'systemd-boot'):
        raise ValueError('This bootloader requires UEFI. Choose GRUB or Limine on BIOS.')


def prepare(bootloader, firmware, mode, base=BASE, root=Path('/')):
    validate_choice(bootloader, firmware, mode)
    if firmware == 'efi':
        fs = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--target', '/boot'], text=True).strip()
        if fs != 'vfat':
            raise RuntimeError('Mount the FAT EFI system partition at /boot before installing.')
    # unpackfs copies an uninitialized keyring, not the live tmpfs keyring.
    subprocess.run(['pacman-key', '--init'], check=True)
    subprocess.run(['pacman-key', '--populate', 'archlinux', 'cachyos'], check=True)
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--target', '/'], text=True).strip()
    packages = list(BOOT_PACKAGES[bootloader])
    if filesystem == 'btrfs':
        packages.append('snapper')
    install_packages(packages, mode, base)
    record = root / 'var/lib/windoesnot/installation.json'
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({'schema_version': 1, 'mode': mode, 'bootloader': bootloader, 'firmware': firmware, 'filesystem': filesystem}, indent=2) + '\n')


def finish(bootloader, firmware, mode, root=Path('/')):
    validate_choice(bootloader, firmware, mode)
    if bootloader == 'systemd-boot':
        subprocess.run(['sdboot-manage', 'gen'], check=True)
    elif bootloader == 'limine':
        config = root / 'boot/limine.conf'
        text = config.read_text().replace('/+CachyOS', '/+WinDoesNot')
        # The entry generator otherwise targets PRETTY_NAME=CachyOS and creates
        # a second group. default_entry=2 would then select a group, not a kernel.
        text = re.sub(r'^comment: machine-id=([^\n]+)\n/\+WinDoesNot\n', r'/+WinDoesNot\ncomment: machine-id=\1\n', text, flags=re.M)
        config.write_text(text)
        defaults = root / 'etc/default/limine'
        settings = defaults.read_text()
        settings = re.sub(r'^TARGET_OS_NAME=.*\n?', '', settings, flags=re.M)
        defaults.write_text(settings.rstrip() + '\nTARGET_OS_NAME="WinDoesNot"\n')
        subprocess.run(['limine-update'], check=True)
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--target', '/'], text=True).strip()
    if filesystem == 'btrfs':
        if not (root / 'etc/snapper/configs/root').exists():
            subprocess.run(['snapper', '--no-dbus', '-c', 'root', 'create-config', '/'], check=True)
        subprocess.run(['snapper', '--no-dbus', '-c', 'root', 'set-config', 'TIMELINE_CREATE=yes', 'TIMELINE_LIMIT_HOURLY=0', 'TIMELINE_LIMIT_DAILY=5', 'TIMELINE_LIMIT_WEEKLY=0', 'TIMELINE_LIMIT_MONTHLY=0', 'TIMELINE_LIMIT_YEARLY=0'], check=True)
        subprocess.run(['systemctl', 'enable', 'snapper-timeline.timer', 'snapper-cleanup.timer'], check=True)
        (root / 'etc/windoesnot-image-build').unlink(missing_ok=True)
        subprocess.run(['snapper', '--no-dbus', '-c', 'root', 'create', '--description', 'WinDoesNot installation'], check=True)
    (root / 'var/lib/pacman/sync/windoesnot-apps.db').unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'finish'])
    parser.add_argument('--bootloader', required=True, choices=list(BOOT_PACKAGES))
    parser.add_argument('--firmware', required=True, choices=['efi', 'bios'])
    parser.add_argument('--mode', required=True, choices=['online', 'offline'])
    args = parser.parse_args()
    if os.geteuid() != 0 or os.environ.get('WINDOESNOT_INSTALL_TARGET') != '1' or not Path('/etc/windoesnot-image-build').is_file():
        raise SystemExit('Calamares installation target only')
    (prepare if args.stage == 'prepare' else finish)(args.bootloader, args.firmware, args.mode)


if __name__ == '__main__':
    main()
