#!/usr/bin/env python3
"""Brand an existing Asahi installation, with boot backups and rollback."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boot_splash', PROJECT / 'iso/boot_splash.py')
splash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(splash)
BRAND = PROJECT / 'desktop/config/quickshell/default/img/brand'


def set_grub(text):
    updates = {'GRUB_DISTRIBUTOR': 'WinDoesNotMac',
               'GRUB_THEME': '/usr/share/grub/themes/windoesnot/theme.txt'}
    matches = re.findall(r'^GRUB_CMDLINE_LINUX_DEFAULT=(.*)$', text, re.M)
    if len(matches) != 1:
        raise ValueError('Expected one GRUB_CMDLINE_LINUX_DEFAULT assignment')
    parsed = shlex.split(matches[0])
    if len(parsed) != 1 or any(c in parsed[0] for c in '$`\\\n'):
        raise ValueError('Expected a literal GRUB kernel command line')
    updates['GRUB_CMDLINE_LINUX_DEFAULT'] = splash.quiet_commandline(parsed[0])
    for key, value in updates.items():
        assignment = key + '=' + json.dumps(value)
        if re.search(r'^' + key + '=', text, re.M):
            text = re.sub(r'^' + key + '=.*$', lambda _: assignment, text, flags=re.M)
        else:
            text += '\n' + assignment + '\n'
    return text


def stage(root, grub, hooks, hostname, hosts='', language='en'):
    root = Path(root).resolve()
    if root == Path('/'):
        raise ValueError('Staging requires an isolated directory')
    def write(name, value):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)
    write('etc/os-release', '''NAME="WinDoesNotMac"
PRETTY_NAME="WinDoesNotMac"
ID=windoesnotmac
ID_LIKE="archarm arch"
BUILD_ID=rolling
VARIANT="Apple Silicon (Asahi)"
VARIANT_ID=asahi
ANSI_COLOR="38;2;254;111;45"
HOME_URL="https://github.com/Bennch/WinDoesNotMac"
DOCUMENTATION_URL="https://github.com/Bennch/WinDoesNotMac"
SUPPORT_URL="https://github.com/Bennch/WinDoesNotMac/issues"
BUG_REPORT_URL="https://github.com/Bennch/WinDoesNotMac/issues"
LOGO=windoesnot
''')
    write('etc/default/grub', set_grub(grub))
    write('etc/mkinitcpio.conf', splash.add_hook(hooks))
    if hostname.strip() in ('alarm', 'archlinux', 'asahi', ''):
        write('etc/hostname', 'windoesnotmac\n')
        if hosts:
            write('etc/hosts', re.sub(r'(?<![\w.-])' + re.escape(hostname.strip()) + r'(?![\w.-])',
                                    'windoesnotmac', hosts) if hostname.strip() else hosts)
    splash.stage(root, PROJECT / 'iso/boot-splash', BRAND / 'windoesnot-logo-hell.png')
    theme = root / 'usr/share/grub/themes/windoesnot'
    shutil.copytree(PROJECT / 'desktop/share/grub/themes/windoesnot', theme)
    p = theme / 'theme.txt'
    value = p.read_text().replace('@KEYMAP_SHORT@', 'WinDoesNotMac')
    if language != 'de':
        value = value.replace('Automatischer Start in %d Sekunden', 'Starting in %d seconds')
    p.write_text(value)
    for size in (16, 32, 48, 64, 128, 256, 512, 1024):
        dest = root / f'usr/share/icons/hicolor/{size}x{size}/apps/windoesnot.png'
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BRAND / f'windoesnot-icon-{size}.png', dest)


def save(target, backup):
    if target.is_dir() and not target.is_symlink():
        raise ValueError(f'Expected a file: {target}')
    exists = target.exists() or target.is_symlink()
    if exists:
        out = backup / str(target).lstrip('/')
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, out, follow_symlinks=False)
    return {'path': str(target), 'existed': exists}


def restore(records, backup):
    for record in reversed(records):
        target = Path(record['path'])
        if target.exists() or target.is_symlink():
            target.unlink()
        if record['existed']:
            shutil.copy2(backup / str(target).lstrip('/'), target, follow_symlinks=False)


def atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.windoesnot-', dir=target.parent)
    os.close(fd)
    temp = Path(name)
    try:
        shutil.copy2(source, temp)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def apply():
    if os.geteuid() != 0:
        raise ValueError('Administrator authorization required')
    model = Path('/proc/device-tree/model')
    if platform.machine() != 'aarch64' or not model.read_bytes().startswith(b'Apple '):
        raise ValueError('This operation is only for Apple Silicon Asahi installations')
    for path in ('/boot/vmlinuz-linux-asahi', '/boot/initramfs-linux-asahi.img',
                 '/boot/grub/grub.cfg', '/etc/default/grub', '/etc/mkinitcpio.conf'):
        if not Path(path).is_file():
            raise ValueError(f'Required Asahi boot file missing: {path}')
    hooks = Path('/etc/mkinitcpio.conf').read_text()
    if 'asahi' not in re.search(r'^HOOKS=\((.*?)\)$', hooks, re.M).group(1).split():
        raise ValueError('Expected the Asahi initramfs hook')
    if shutil.disk_usage('/boot').free < 512 * 1024**2:
        raise ValueError('At least 512 MiB of free space is required')
    old_hostname = Path('/etc/hostname').read_text() if Path('/etc/hostname').exists() else ''
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    backup = Path('/var/backups/windoesnot-branding') / stamp
    backup.mkdir(parents=True, mode=0o700)
    records = []
    def backup_once(path):
        if not any(r['path'] == str(path) for r in records):
            records.append(save(path, backup))
            (backup / 'manifest.json').write_text(json.dumps(records, indent=2))
    initrd = Path('/boot/initramfs-linux-asahi.img')
    grubcfg = Path('/boot/grub/grub.cfg')
    backup_once(initrd)
    backup_once(grubcfg)
    print(f'Backup: {backup}', flush=True)
    new_initrd = Path('/boot') / f'.windoesnot-initramfs-{os.getpid()}.img'
    new_grub = Path('/boot/grub') / f'.windoesnot-{os.getpid()}.cfg'
    try:
        subprocess.run(['pacman', '-S', '--needed', '--noconfirm', 'plymouth'], check=True)
        with tempfile.TemporaryDirectory(prefix='windoesnot-branding-') as d:
            stage_root = Path(d)
            locale = Path('/etc/locale.conf')
            language = 'de' if locale.is_file() and 'LANG=de_' in locale.read_text() else 'en'
            stage(stage_root, Path('/etc/default/grub').read_text(), hooks, old_hostname,
                  Path('/etc/hosts').read_text(), language)
            source = stage_root / 'usr/share/plymouth/themes/spinner'
            shutil.copytree('/usr/share/plymouth/themes/spinner', source)
            splash.finish_theme(stage_root)
            shutil.rmtree(source)
            for source in sorted(stage_root.rglob('*')):
                if source.is_file():
                    target = Path('/') / source.relative_to(stage_root)
                    backup_once(target)
                    atomic_copy(source, target)
        print('Building a separate initramfs with our logo…', flush=True)
        subprocess.run(['nice', '-n', '10', 'mkinitcpio', '-k', '/boot/vmlinuz-linux-asahi',
                        '-c', '/etc/mkinitcpio.conf', '-g', str(new_initrd)], check=True)
        listing = subprocess.check_output(['lsinitcpio', str(new_initrd)], text=True)
        if 'usr/share/plymouth/themes/windoesnot/watermark.png' not in listing:
            raise ValueError('Generated initramfs is missing our boot logo')
        subprocess.run(['grub-mkconfig', '-o', str(new_grub)], check=True)
        subprocess.run(['grub-script-check', str(new_grub)], check=True)
        if 'WinDoesNotMac' not in new_grub.read_text():
            raise ValueError('Generated GRUB menu is missing our distribution name')
        new_initrd.chmod(0o600)
        new_grub.chmod(grubcfg.stat().st_mode & 0o777)
        new_initrd.replace(initrd)
        new_grub.replace(grubcfg)
        if Path('/etc/hostname').read_text() != old_hostname:
            subprocess.run(['hostnamectl', 'set-hostname', 'windoesnotmac'], check=True)
        (backup / 'SUCCESS').write_text('Boot appearance must be verified on the next restart.\n')
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        print('WinDoesNotMac branding applied. No reboot was requested.', flush=True)
    except BaseException:
        restore(records, backup)
        if old_hostname.strip():
            subprocess.run(['hostnamectl', 'set-hostname', old_hostname.strip()], check=False)
        subprocess.run(['systemctl', 'daemon-reload'], check=False)
        print(f'Branding rolled back. Backup: {backup}', flush=True)
        raise
    finally:
        new_initrd.unlink(missing_ok=True)
        new_grub.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        apply()
    else:
        print('Asahi only: OS name/icon, default alarm hostname, GRUB theme and Plymouth logo.')
        print('Root application backs up config/initramfs/GRUB and rebuilds before activating.')
        print('Apple firmware, EFI binaries, package repositories and user accounts stay intact.')
