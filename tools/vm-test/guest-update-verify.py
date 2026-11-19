#!/usr/bin/env python3
"""Collect fail-closed update observations inside a disposable gate guest."""
import glob
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, env={**os.environ, 'LC_ALL': 'C'})


def observe(configuration='A'):
    kernel = os.uname().release
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    packages = run('pacman', '-Q', 'windoesnot-desktop', 'windoesnot-tools', 'windoesnot-plugins', 'windoesnot-components')
    package_files = run('pacman', '-Qk', 'windoesnot-desktop', 'windoesnot-tools', 'windoesnot-plugins', 'windoesnot-components')
    bootctl = run('bootctl', 'status', '--no-pager')
    mount = run('findmnt', '-rn', '-T', '/boot', '-o', 'TARGET,FSTYPE,OPTIONS')
    units = run('systemctl', '--failed', '--no-legend', '--plain')
    updates = run('pacman', '-Qu')
    sigs = list(Path('/run/user/1000/hypr').glob('*')) if Path('/run/user/1000/hypr').is_dir() else []
    plugins = run('runuser', '-u', 'maxt', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000',
                  'HYPRLAND_INSTANCE_SIGNATURE=' + sigs[0].name, 'hyprctl', 'plugin', 'list') if len(sigs) == 1 else None
    config = run('runuser', '-u', 'maxt', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000',
                 'HYPRLAND_INSTANCE_SIGNATURE=' + sigs[0].name, 'hyprctl', 'configerrors') if len(sigs) == 1 else None
    personal = Path('/home/maxt/e2e-preserve.txt')
    entries = sorted(Path('/boot/loader/entries').glob('*.conf'))
    machine_id = Path('/etc/machine-id').read_text().strip()
    kernels = []
    for p in Path('/usr/lib/modules').glob('*/pkgbase'):
        if p.read_text().strip() in ('linux-cachyos', 'linux-cachyos-lts'):
            kernels.append(p.parent.name)
    newest = None
    for candidate in kernels:
        if newest is None or run('vercmp', candidate, newest).stdout.strip() == '1':
            newest = candidate
    parsed = dict(line.split(maxsplit=1) for line in packages.stdout.splitlines() if len(line.split(maxsplit=1)) == 2)
    default_section = bootctl.stdout.split('Default Boot Loader Entry:', 1)[-1].split('\n\n', 1)[0] if 'Default Boot Loader Entry:' in bootctl.stdout else ''
    paths = re.findall(r'^\s*(?:linux|initrd):\s*(\S+)', default_section, re.M)
    default_valid = (bootctl.returncode == 0 and 'id: linux-cachyos.conf' in default_section
                     and len(paths) >= 2 and all(p.startswith('/boot/') and Path(p).is_file() for p in paths)
                     and Path('/boot/loader/entries/linux-cachyos.conf').is_file())
    mount_fields = mount.stdout.split()
    boot_mounted = mount.returncode == 0 and mount_fields[:2] == ['/boot', 'vfat'] and 'rw' in mount_fields[-1].split(',')
    old_entries_removed = bool(machine_id) and not any(p.name.startswith(machine_id + '-') for p in entries)
    if configuration in ('B', 'C'):
        grub = Path('/boot/grub/grub.cfg')
        grub_text = grub.read_text(errors='replace') if grub.is_file() else ''
        efi = Path('/sys/firmware/efi').is_dir()
        expected_efi = configuration == 'B'
        default_valid = bool(grub_text and 'menuentry ' in grub_text and re.search(r'^\s*linux\s', grub_text, re.M))
        boot_mounted = (mount.returncode == 0 and len(mount_fields) >= 3 and 'rw' in mount_fields[-1].split(',')
                        and efi == expected_efi and ((mount_fields[:2] == ['/boot', 'vfat'] and Path('/boot/EFI/WinDoesNot/grubx64.efi').is_file()) if expected_efi else mount_fields[1] != 'vfat'))
        old_entries_removed = True  # systemd-boot entries do not apply to GRUB
    checks = {
        'package_files_intact': package_files.returncode == 0,
        'target_versions': packages.returncode == 0 and len(parsed) == 4 and all(v == '0.1.0-32' for v in parsed.values()),
        'newest_kernel': bool(newest) and kernel == newest and 'lts' not in kernel and (Path('/usr/lib/modules') / kernel).is_dir(),
        'boot_mounted': boot_mounted,
        'default_valid': default_valid,
        'old_entries_removed': old_entries_removed,
        'failed_units': units.returncode == 0 and not units.stdout.strip(),
        'personal_sha256': personal.is_file() and hashlib.sha256(personal.read_bytes()).hexdigest() == 'c8de8152d7324d9c4dd0139dc190d6632b0b8ddf6ae98be16270f99ca98ef58e',
        'desktop_plugins': bool(plugins and plugins.returncode == 0 and 'Plugin hyprbars' in plugins.stdout and 'Plugin hyprdrag' in plugins.stdout),
        'configerrors': bool(config and config.returncode == 0 and not config.stdout.strip()),
        'no_pending_updates': updates.returncode in (0, 1) and not updates.stdout.strip() and not updates.stderr.strip(),
    }
    return {'boot_id': boot, 'kernel': kernel, 'newest_installed_kernel': newest, 'checks': checks,
            'packages': parsed, 'package_files': package_files.stdout, 'package_files_stderr': package_files.stderr, 'bootctl': bootctl.stdout, 'mount': mount.stdout,
            'failed_units': units.stdout, 'updates': updates.stdout, 'updates_stderr': updates.stderr,
            'plugins': plugins.stdout if plugins else '', 'configerrors': config.stdout if config else '',
            'entries': [p.name for p in entries]}

if __name__ == '__main__':
    configuration = sys.argv[1] if len(sys.argv) > 1 else 'A'
    if configuration not in ('A', 'B', 'C'):
        raise SystemExit('invalid configuration')
    print(json.dumps(observe(configuration), indent=2))
