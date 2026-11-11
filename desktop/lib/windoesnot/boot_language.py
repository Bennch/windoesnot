#!/usr/bin/python3
"""Keep WinDoesNot's installed boot menus in the system language.

Only installation records created by our installer authorize changes. No EFI
variables, disk detection or foreign operating system configuration is used.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile

LOADERS = ('grub', 'systemd-boot', 'refind', 'limine')
STATE = 'var/lib/windoesnot/boot-language.json'
ASSETS = 'usr/lib/windoesnot/boot-language'
NATIVE = {
    'systemd-boot': {'systemd-bootx64.efi': 'usr/lib/systemd/boot/efi/systemd-bootx64.efi'},
    'refind': {'refind_x64.efi': 'usr/share/refind/refind_x64.efi'},
    'limine': {'BOOTX64.EFI': 'usr/share/limine/BOOTX64.EFI',
               'limine-bios.sys': 'usr/share/limine/limine-bios.sys', 'limine': 'usr/bin/limine'},
}
# Native installers own these locations. Register only files that actually match
# our installed loader at initial setup; never scan and replace another OS's EFI.
EFI_PATHS = {
    'systemd-boot': ('boot/EFI/systemd/systemd-bootx64.efi', 'boot/EFI/BOOT/BOOTX64.EFI'),
    'refind': ('boot/EFI/refind/refind_x64.efi',),
    'limine': ('boot/EFI/limine/limine_x64.efi', 'boot/EFI/Limine/limine_x64.efi',
               'boot/EFI/limine/BOOTX64.EFI', 'boot/EFI/Limine/BOOTX64.EFI', 'boot/EFI/BOOT/BOOTX64.EFI'),
}


def owned_path(root, relative):
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Invalid managed path')
    result = root
    for part in Path(relative).parts:
        result = result / part
        if result.is_symlink():
            raise ValueError('Managed path contains a symlink: ' + relative)
    # Boot configuration must not escape the target through a symlink.
    if not result.resolve().is_relative_to(root.resolve()) or result.is_symlink():
        raise ValueError('Managed path is a symlink or escapes the target: ' + relative)
    return result


def atomic_write(path, data, mode=0o644):
    if isinstance(data, str):
        data = data.encode()
    if path.is_symlink():
        raise ValueError('Refusing a symlink: ' + str(path))
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.stat() if path.exists() else None
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), stat.S_IMODE(old.st_mode) if old else mode)
            if old and os.geteuid() == 0:
                os.fchown(stream.fileno(), old.st_uid, old.st_gid)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    return True


def installation(root):
    path = owned_path(root, 'var/lib/windoesnot/installation.json')
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    if record.get('schema_version') != 1 or record.get('bootloader') not in LOADERS:
        raise ValueError('Unrecognized installation record')
    return record


def language(root):
    values = {}
    path = owned_path(root, 'etc/locale.conf')
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip().startswith('#') or '=' not in line:
                continue
            key, raw = line.split('=', 1)
            words = shlex.split(raw, comments=True)
            if key.strip() in ('LANG', 'LC_MESSAGES', 'LC_ALL') and len(words) == 1:
                values[key.strip()] = words[0]
    # Match Settings' supported UI languages and English fallback. Never inherit
    # the build process or root service's unrelated environment locale.
    locale = values.get('LC_ALL') or values.get('LC_MESSAGES') or values.get('LANG', 'en_US.UTF-8')
    return 'de' if re.split(r'[_ .@-]', locale)[0].lower() == 'de' else 'en'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_state(root):
    path = owned_path(root, STATE)
    data = json.loads(path.read_text()) if path.exists() else {'schema_version': 1, 'efi_files': {}}
    if data.get('schema_version') != 1 or not isinstance(data.get('efi_files'), dict):
        raise ValueError('Invalid boot language state')
    return data


def translated_labels(text, lang, loader):
    pairs = {
        'Other systems and bootloaders': 'Weitere Systeme und Startprogramme',
        'WinDoesNot restore points': 'WinDoesNot-Wiederherstellungspunkte',
        'Boot with normal options': 'Mit normalen Optionen starten',
        'Boot into single-user mode': 'Im Einzelbenutzermodus starten',
        'Boot using default options': 'Mit Standardoptionen starten',
    }
    # Limit substitutions to titles and our own named snapshot submenu. Never
    # alter kernel parameters, UUIDs, file paths or other OS titles.
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        allowed = ((loader == 'limine' and stripped.startswith('/')) or
                   (loader == 'refind' and (stripped.startswith('menuentry ') or stripped.startswith('"'))) or
                   (loader == 'grub' and stripped.startswith('GRUB_BTRFS_SUBMENUNAME=')))
        if not allowed:
            continue
        if loader == 'grub':
            raw = shlex.split(line.split('=', 1)[1])
            if raw == ['WinDoesNot snapshots']:
                line = line.split('=', 1)[0] + "='WinDoesNot restore points'\n"
        for en, de in pairs.items():
            source, target = (en, de) if lang == 'de' else (de, en)
            # refind_linux.conf stores a quoted display title followed by kernel
            # arguments. Only operate on the first quoted field.
            if loader == 'refind' and stripped.startswith('"'):
                match = re.match(r'(\s*)"([^"\n]*)"(.*)', line)
                if match and match[2] == source:
                    line = match[1] + '"' + target + '"' + match[3] + ('\n' if line.endswith('\n') else '')
            elif loader == 'limine':
                match = re.match(r'([/+]*)([^\r\n]*)([\r\n]*)$', line)
                if match and match[2] == source:
                    line = match[1] + target + match[3]
            elif loader == 'grub':
                raw = shlex.split(line.split('=', 1)[1])
                if raw == [source]:
                    line = 'GRUB_BTRFS_SUBMENUNAME=' + shlex.quote(target) + '\n'
        lines[i] = line
    return ''.join(lines)


def prepare_binaries(root):
    """Stage native installer inputs from the version-matched packaged build.

    Called before the stock Calamares bootloader job and before native ALPM boot
    update hooks. It does not install a boot sector or change firmware entries.
    Original package files are backed up by hash and recorded for recovery.
    """
    record = installation(root)
    if not record or record['bootloader'] == 'grub':
        return
    loader = record['bootloader']
    assets = owned_path(root, ASSETS)
    manifest = json.loads((assets / 'manifest.json').read_text())['loaders'][loader]
    package = 'systemd' if loader == 'systemd-boot' else loader
    # The helper is executed inside the target, never using the host's database.
    if root != Path('/'):
        raise ValueError('Binary preparation must run inside the installation target')
    version = subprocess.check_output(['/usr/bin/pacman', '-Q', package], text=True).strip().split()[1]
    upstream = version.rsplit('-', 1)[0].split(':')[-1]
    if upstream != manifest['version']:
        raise ValueError(f'{package} {version}: rebuild the boot language package for this upstream version before deployment')
    for name, relative in NATIVE[loader].items():
        source = assets / loader / name
        if digest(source) != manifest['sha256'][name]:
            raise ValueError('Boot language artifact checksum mismatch: ' + name)
        target = owned_path(root, relative)
        if not target.is_file():
            raise ValueError('Native bootloader file is missing: ' + relative)
        if digest(target) == digest(source):
            continue
        backup = owned_path(root, 'var/lib/windoesnot/boot-language-originals/' + digest(target) + '/' + name)
        atomic_write(backup, target.read_bytes(), stat.S_IMODE(target.stat().st_mode))
        atomic_write(target, source.read_bytes(), stat.S_IMODE(target.stat().st_mode))


def sync(root=Path('/'), force=False, register=False):
    record = installation(root)
    if not record:
        return {'skipped': 'not a WinDoesNot installation'}
    loader, lang = record['bootloader'], language(root)
    state = read_state(root)
    changed = state.get('language') != lang
    if loader == 'grub':
        locale = 'de_DE.UTF-8' if lang == 'de' else 'en_US.UTF-8'
        atomic_write(owned_path(root, 'etc/default/grub.d/91-windoesnot-language.cfg'),
                     '# Managed boot language; follows /etc/locale.conf.\n'
                     f'LANG={locale}\nLC_ALL={locale}\nLANGUAGE={lang}\nexport LANG LC_ALL LANGUAGE\n')
        catalog = owned_path(root, 'usr/share/locale/' + lang + '/LC_MESSAGES/grub.mo')
        if catalog.is_file():
            atomic_write(owned_path(root, 'boot/grub/locale/' + lang + '.mo'), catalog.read_bytes())
        snapshots = owned_path(root, 'etc/default/grub-btrfs/config')
        if snapshots.exists():
            atomic_write(snapshots, translated_labels(snapshots.read_text(), lang, loader))
        if changed or force:
            if root != Path('/'):
                raise ValueError('GRUB generation must run inside the target')
            subprocess.run(['/usr/bin/grub-mkconfig', '-o', '/boot/grub/grub.cfg'], check=True,
                           env={**os.environ, 'LANG': locale, 'LC_ALL': locale, 'LANGUAGE': lang})
    elif loader == 'systemd-boot':
        atomic_write(owned_path(root, 'boot/loader/windoesnot-language'), lang + '\n')
    elif loader == 'refind':
        atomic_write(owned_path(root, 'boot/EFI/refind/windoesnot-language'), lang + '\n')
        for relative in ('boot/refind_linux.conf', 'boot/EFI/refind/windoesnot-linux.conf'):
            path = owned_path(root, relative)
            if path.is_file():
                atomic_write(path, translated_labels(path.read_text(), lang, loader))
    elif loader == 'limine':
        path = owned_path(root, 'boot/limine.conf')
        text = path.read_text()
        text = re.sub(r'(?mi)^windoesnot_language\s*:.*\n?', '', text)
        atomic_write(path, 'windoesnot_language: ' + lang + '\n' + translated_labels(text, lang, loader))
    # Register only our freshly installed matching loader. A reused menu belongs
    # to its existing OS; WinDoesNot uses its own GRUB below that menu.
    if register and loader != 'grub':
        filename = {'systemd-boot': 'systemd-bootx64.efi', 'refind': 'refind_x64.efi', 'limine': 'BOOTX64.EFI'}[loader]
        source = owned_path(root, ASSETS + '/' + loader + '/' + filename)
        for relative in EFI_PATHS[loader]:
            target = owned_path(root, relative)
            if target.is_file() and digest(target) == digest(source):
                state['efi_files'][relative] = digest(source)
    state.update(language=lang, bootloader=loader)
    atomic_write(owned_path(root, STATE), json.dumps(state, sort_keys=True, indent=2) + '\n')
    return {'language': lang, 'bootloader': loader}


def refresh_efi(root=Path('/')):
    """Refresh registered EFI copies after native package hooks, never BootOrder."""
    record = installation(root)
    if not record or record['bootloader'] == 'grub':
        return
    state = read_state(root)
    loader = record['bootloader']
    filename = {'systemd-boot': 'systemd-bootx64.efi', 'refind': 'refind_x64.efi', 'limine': 'BOOTX64.EFI'}[loader]
    source = owned_path(root, ASSETS + '/' + loader + '/' + filename)
    native = owned_path(root, NATIVE[loader][filename])
    # Never downgrade a newer upstream loader to an older translated one.
    if digest(native) != digest(source):
        raise ValueError('Native loader and translated package differ; rebuild translations before refreshing EFI')
    for relative, previous in state['efi_files'].items():
        if relative not in EFI_PATHS[loader]:
            raise ValueError('Unknown registered EFI target')
        target = owned_path(root, relative)
        if target.is_file() and digest(target) in (previous, digest(native)):
            atomic_write(target, source.read_bytes())
            state['efi_files'][relative] = digest(source)
        else:
            raise ValueError('Registered EFI target changed outside WinDoesNot: ' + relative)
    atomic_write(owned_path(root, STATE), json.dumps(state, sort_keys=True, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'sync', 'finish', 'refresh'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise PermissionError('Root is required')
    Path('/run/windoesnot-system-tools').mkdir(parents=True, exist_ok=True)
    with open('/run/windoesnot-system-tools/boot-language.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action in ('prepare', 'refresh'):
            prepare_binaries(Path('/'))
        if args.action != 'prepare':
            print(json.dumps(sync(register=args.action == 'finish', force=args.action == 'refresh')))
        if args.action == 'refresh':
            refresh_efi()
            if not Path('/etc/windoesnot-image-build').exists() and installation(Path('/')) and Path('/run/systemd/system').is_dir():
                subprocess.run(['/usr/bin/systemctl', 'enable', '--now', 'windoesnot-boot-language.path'], check=True)

if __name__ == '__main__':
    main()
