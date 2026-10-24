#!/usr/bin/env python3
"""Configure the chosen bootloader and Btrfs snapshots in an install target."""
import argparse
import ast
import configparser
import io
import shlex
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
BTRFS_PACKAGES = {
    'grub': ['snapper', 'snap-pac', 'grub-btrfs', 'inotify-tools'],
    'refind': ['snapper', 'snap-pac', 'refind-btrfs'],
    'systemd-boot': ['snapper', 'snap-pac'],
    'limine': ['snapper', 'snap-pac', 'limine-snapper-sync', 'inotify-tools'],
}
# prepare.py imports this union to resolve every loader's complete offline closure.
BOOT_EXTRA_PACKAGES = sorted({name for packages in (*BOOT_PACKAGES.values(), *BTRFS_PACKAGES.values()) for name in packages})
SNAPPER_DEFAULTS = (
    'NUMBER_CLEANUP=yes', 'NUMBER_LIMIT=20', 'NUMBER_LIMIT_IMPORTANT=5', 'NUMBER_MIN_AGE=1800',
    'EMPTY_PRE_POST_CLEANUP=yes', 'EMPTY_PRE_POST_MIN_AGE=1800',
    'TIMELINE_CREATE=yes', 'TIMELINE_CLEANUP=yes', 'TIMELINE_LIMIT_HOURLY=0',
    'TIMELINE_LIMIT_DAILY=5', 'TIMELINE_LIMIT_WEEKLY=0', 'TIMELINE_LIMIT_MONTHLY=0',
    'TIMELINE_LIMIT_QUARTERLY=0', 'TIMELINE_LIMIT_YEARLY=0',
)


def selected_packages(bootloader, filesystem):
    if bootloader not in BOOT_PACKAGES:
        raise ValueError('Unsupported bootloader')
    return list(BOOT_PACKAGES[bootloader]) + (BTRFS_PACKAGES[bootloader] if filesystem == 'btrfs' else [])


def write_target(root, relative, text, mode=0o644):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def set_shell_value(path, key, value):
    text = path.read_text()
    pattern = r'(?m)^\s*' + re.escape(key) + r'=.*$'
    line = key + '=' + shlex.quote(value)
    path.write_text(re.sub(pattern, lambda match: line, text) if re.search(pattern, text)
                    else text.rstrip() + '\n' + line + '\n')


def enable_snapshot_hook(root, hook, remove=()):
    write_target(root, 'etc/mkinitcpio.conf.d/20-windoesnot-snapshots.conf',
        '# Keep existing hooks; add the snapshot hook exactly once.\n'
        '_wdn_hooks=()\n'
        'for _wdn_hook in "${HOOKS[@]}"; do\n'
        f'    case "$_wdn_hook" in {"|".join((*remove, hook))}) ;; *) _wdn_hooks+=("$_wdn_hook");; esac\n'
        'done\n'
        'HOOKS=("${_wdn_hooks[@]}" ' + hook + ')\n'
        'unset _wdn_hooks _wdn_hook\n')
    # Our vendor kernel presets set ALL_config=/etc/mkinitcpio.conf, disabling
    # implicit conf.d loading. Explicit sourcing works for both preset variants;
    # the drop-in is idempotent when mkinitcpio also loads it a second time.
    path = root / 'etc/mkinitcpio.conf'
    text = path.read_text()
    source = 'source /etc/mkinitcpio.conf.d/20-windoesnot-snapshots.conf'
    if source not in text.splitlines():
        path.write_text(text.rstrip() + '\n# WinDoesNot snapshot startup support\n' + source + '\n')


def configure_grub_overlay(root):
    # grub-btrfs's packaged run_latehook is for BusyBox. Our image uses systemd;
    # run after the initrd has mounted /sysroot, before switch-root (same ordering
    # as CachyOS's sd-btrfs-overlayfs). Only immutable Snapper roots get an overlay.
    write_target(root, 'usr/lib/windoesnot/snapshot-overlay', r'''#!/usr/bin/bash
set -euo pipefail
[[ $(findmnt --mountpoint /sysroot -n -o FSTYPE) == btrfs ]] || exit 0
[[ $(findmnt --mountpoint /sysroot -n -o SOURCE) == *'/.snapshots/'*'/snapshot]' ]] || exit 0
[[ $(btrfs property get -t subvol /sysroot ro) == ro=true ]] || exit 0
mkdir -p /run/windoesnot-snapshot
mount -t tmpfs -o mode=0700 tmpfs /run/windoesnot-snapshot
mkdir /run/windoesnot-snapshot/upper /run/windoesnot-snapshot/work
mount -t overlay overlay -o lowerdir=/sysroot,upperdir=/run/windoesnot-snapshot/upper,workdir=/run/windoesnot-snapshot/work /sysroot
# The root is already writable as overlay. Do not let the real-root remount
# service apply the original Btrfs-only options to this overlay filesystem.
# This edits only the RAM upper layer; the original snapshot stays immutable.
if [[ -f /sysroot/etc/fstab ]]; then
    while IFS= read -r _line || [[ -n $_line ]]; do
        read -r _source _target _options <<< "$_line"
        if [[ $_target == / ]]; then
            printf '# WinDoesNot snapshot preview: %s\n' "$_line"
        else
            printf '%s\n' "$_line"
        fi
    done < /sysroot/etc/fstab > /run/windoesnot-snapshot/fstab
    cp /run/windoesnot-snapshot/fstab /sysroot/etc/fstab
fi
printf 'overlay\n' > /run/windoesnot-snapshot-boot
''', 0o755)
    write_target(root, 'usr/lib/systemd/system/windoesnot-snapshot-overlay.service', '''[Unit]
Description=Temporary writable layer for a read-only WinDoesNot snapshot
DefaultDependencies=no
After=initrd-fs.target
Before=initrd.target
ConditionPathExists=/etc/initrd-release

[Service]
Type=oneshot
ExecStart=/usr/lib/windoesnot/snapshot-overlay
RemainAfterExit=yes
''')
    write_target(root, 'usr/lib/initcpio/install/windoesnot-snapshot-overlay', '''#!/usr/bin/bash
build() {
    add_module btrfs
    add_module overlay
    map add_binary bash btrfs findmnt mount mkdir cp
    add_file /usr/lib/windoesnot/snapshot-overlay /usr/lib/windoesnot/snapshot-overlay 755
    add_systemd_unit windoesnot-snapshot-overlay.service || return 1
    add_symlink /usr/lib/systemd/system/initrd.target.wants/windoesnot-snapshot-overlay.service /usr/lib/systemd/system/windoesnot-snapshot-overlay.service
}
help() { echo 'Temporary overlay for read-only WinDoesNot snapshots (systemd initrd).'; }
''', 0o755)
    enable_snapshot_hook(root, 'windoesnot-snapshot-overlay', ('grub-btrfs-overlayfs',))



def configure_refind_snapshots(root):
    directory = root / 'boot/EFI/refind'
    main = directory / 'refind.conf'
    # refind-btrfs needs manual source stanzas; Calamares normally uses auto-scan.
    options = None
    for line in (root / 'boot/refind_linux.conf').read_text().splitlines():
        fields = shlex.split(line, comments=True)
        if len(fields) >= 2:
            options = ' '.join(word for word in fields[1].split() if not word.startswith('initrd='))
            break
    if options is None:
        raise RuntimeError('No rEFInd kernel options available for snapshot source entries')
    entries = []
    for kernel in sorted((root / 'boot').glob('vmlinuz-*')):
        name = kernel.name.removeprefix('vmlinuz-')
        initrd = root / ('boot/initramfs-' + name + '.img')
        if not re.fullmatch(r'[A-Za-z0-9_+.-]+', name) or not initrd.is_file():
            continue
        entries.append('menuentry "WinDoesNot (' + name + ')" {\n'
                       '    loader /' + kernel.name + '\n'
                       '    initrd /' + initrd.name + '\n'
                       '    options ' + json.dumps(options) + '\n}\n')
    if not entries:
        raise RuntimeError('No kernel/initramfs pair for rEFInd snapshot source entries')
    (directory / 'windoesnot-linux.conf').write_text('\n'.join(entries))
    text = main.read_text()
    if not re.search(r'(?m)^\s*include\s+windoesnot-linux\.conf\s*$', text):
        main.write_text(text.rstrip() + '\ninclude windoesnot-linux.conf\n')
    # Leave the immutable originals alone. Keep just three writable boot copies.
    config = root / 'etc/refind-btrfs.conf'
    text = config.read_text()
    text = re.sub(r'(?m)^selection_count\s*=.*$', 'selection_count = 3', text)
    text = re.sub(r'(?m)^modify_read_only_flag\s*=.*$', 'modify_read_only_flag = false', text)
    config.write_text(text)


def configure_snapshots(bootloader, root):
    if not (root / 'etc/snapper/configs/root').exists():
        subprocess.run(['snapper', '--no-dbus', '-c', 'root', 'create-config', '/'], check=True)
    subprocess.run(['snapper', '--no-dbus', '-c', 'root', 'set-config', *SNAPPER_DEFAULTS], check=True)
    # Keep custom sections and descriptions; pre-number metadata links post points
    # (whose descriptions contain only package names) to their transaction.
    config_path = root / 'etc/snap-pac.ini'
    config = configparser.ConfigParser(interpolation=None)
    if config_path.exists():
        config.read_string(config_path.read_text())
    if not config.has_section('root'):
        config.add_section('root')
    config['root']['snapshot'] = 'True'
    config['root']['cleanup_algorithm'] = 'number'
    userdata = ast.literal_eval(config['root'].get('userdata', '[]'))
    if not isinstance(userdata, list) or any(not isinstance(item, str) for item in userdata):
        raise ValueError('Invalid snap-pac userdata configuration')
    if 'windoesnot.package-change=yes' not in userdata:
        userdata.append('windoesnot.package-change=yes')
    config['root']['userdata'] = json.dumps(userdata)
    config['root'].setdefault('important_packages', json.dumps(['linux-cachyos', 'linux-cachyos-lts', 'linux-cachyos-bore', 'linux-cachyos-rt-bore', 'linux-cachyos-eevdf', 'linux-cachyos-bmq', 'linux-cachyos-server', 'pacman', 'systemd']))
    stream = io.StringIO(); config.write(stream); config_path.write_text(stream.getvalue())
    subprocess.run(['systemctl', 'enable', 'snapper-timeline.timer', 'snapper-cleanup.timer'], check=True)
    if bootloader == 'grub':
        configure_grub_overlay(root)
        config = root / 'etc/default/grub-btrfs/config'
        set_shell_value(config, 'GRUB_BTRFS_SUBMENUNAME', 'WinDoesNot snapshots')
        set_shell_value(config, 'GRUB_BTRFS_SNAPSHOT_KERNEL_PARAMETERS', 'ro')
        subprocess.run(['systemctl', 'enable', 'grub-btrfsd.service'], check=True)
        subprocess.run(['mkinitcpio', '-P'], check=True)
    elif bootloader == 'limine':
        set_shell_value(root / 'etc/limine-snapper-sync.conf', 'TARGET_OS_NAME', 'WinDoesNot')
        set_shell_value(root / 'etc/limine-snapper-sync.conf', 'MAX_SNAPSHOT_ENTRIES', '3')
        enable_snapshot_hook(root, 'sd-btrfs-overlayfs')
        subprocess.run(['systemctl', 'enable', 'limine-snapper-sync.service'], check=True)
        subprocess.run(['mkinitcpio', '-P'], check=True)
    elif bootloader == 'refind':
        configure_refind_snapshots(root)
        subprocess.run(['systemctl', 'enable', 'refind-btrfs.service'], check=True)



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
    packages = selected_packages(bootloader, filesystem)
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
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--target', '/'], text=True).strip()
    if filesystem == 'btrfs':
        configure_snapshots(bootloader, root)
        (root / 'etc/windoesnot-image-build').unlink(missing_ok=True)
        subprocess.run(['snapper', '--no-dbus', '-c', 'root', 'create', '--description', 'WinDoesNot installation'], check=True)
    if filesystem == 'btrfs' and bootloader == 'grub':
        subprocess.run(['grub-mkconfig', '-o', '/boot/grub/grub.cfg'], check=True)
    if bootloader == 'limine':
        subprocess.run(['limine-update'], check=True)
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
