#!/usr/bin/env python3
"""Inspect existing UEFI menus and add a chainloader without replacing them.

Operating-system discovery belongs to Calamares/os-prober. This module consumes
that result and recognises only menu layouts for which an additive edit is safe.
It never executes code from another installed operating system.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

GUID = re.compile(r'^[0-9a-fA-F-]{8,36}$')
ROOT_UUID = re.compile(r'\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b')


def command(args):
    return subprocess.check_output(args, text=True, timeout=15, env={**os.environ, 'LC_ALL': 'C'})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def devices():
    data = json.loads(command(['lsblk', '--json', '--paths', '--output', 'PATH,FSTYPE,UUID,PARTUUID']))
    def walk(rows):
        for row in rows:
            yield row
            yield from walk(row.get('children', []))
    return list(walk(data['blockdevices']))


def by_uuid(rows, field, value):
    if not isinstance(value, str) or not GUID.fullmatch(value):
        raise RuntimeError('Invalid partition identity')
    matches = {row['path']: row for row in rows if str(row.get(field, '')).lower() == value.lower()}
    if len(matches) != 1:
        raise RuntimeError('Partition identity is missing or ambiguous')
    return next(iter(matches.values()))


@contextmanager
def mounted(row, writable=False):
    fs = row.get('fstype')
    flags = 'rw' if writable else 'ro'
    if fs == 'btrfs':
        flags += ',subvolid=5' + ('' if writable else ',rescue=nologreplay')
    elif fs == 'ext4' and not writable:
        flags += ',noload'
    elif fs == 'xfs' and not writable:
        flags += ',norecovery'
    elif fs not in ('vfat', 'ext4', 'xfs'):
        raise RuntimeError('Unsupported or locked file system')
    directory = Path(tempfile.mkdtemp(prefix='windoesnot-boot-'))
    try:
        command(['mount', '-t', fs, '-o', flags + ',nosuid,nodev,noexec', row['path'], str(directory)])
        try:
            yield directory
        finally:
            command(['umount', str(directory)])
    finally:
        # Never recursively clean a mount point, including after umount failure.
        if directory.is_mount():
            command(['umount', str(directory)])
        try:
            directory.rmdir()
        except OSError:
            pass


def child(directory, relative):
    """Resolve FAT spelling without following paths outside the mounted volume."""
    current = directory
    for part in relative.replace('\\', '/').strip('/').split('/'):
        if part in ('', '.', '..'):
            raise RuntimeError('Unsafe EFI path')
        matches = [item for item in current.iterdir() if item.name.casefold() == part.casefold()]
        if len(matches) != 1:
            raise RuntimeError('EFI file missing or ambiguous')
        current = matches[0]
        if current.is_symlink():
            raise RuntimeError('Symlink in boot menu path')
    return current


def secure_boot():
    for path in Path('/sys/firmware/efi/efivars').glob('SecureBoot-*'):
        return path.read_bytes()[-1:] == b'\x01'
    return False


def is_efi():
    return Path('/sys/firmware/efi').exists()


def entries(output):
    order = []
    for line in output.splitlines():
        if line.startswith('BootOrder:'):
            order = line.partition(':')[2].strip().upper().split(',')
    found = []
    for line in output.splitlines():
        match = re.match(r'^Boot([0-9a-fA-F]{4})\*?\s+(.+?)\s+((?:HD|PciRoot|Pci|Acpi|VenHw)\(.+)$', line)
        if not match:
            continue
        location = re.search(r'HD\(\d+,GPT,([0-9a-fA-F-]+),[^)]*\)/(.*)$', match[3], re.I)
        if location:
            wrapped = re.match(r'File\(([^)]+)\)', location[2], re.I)
            path = wrapped[1] if wrapped else location[2].partition('{')[0].strip()
            if not path.startswith(('\\', '/')) or not path.lower().endswith('.efi'):
                continue
            found.append({'firmware_id': match[1].upper(), 'label': match[2].strip(),
                          'esp_partuuid': location[1].lower(), 'efi_file': path})
    return sorted(found, key=lambda row: order.index(row['firmware_id']) if row['firmware_id'] in order else len(order))


def reserved_files(esp):
    result = [path.name for path in esp.iterdir()
              if path.name.casefold() == 'grub' or path.name.casefold().startswith(('vmlinuz-', 'initramfs-'))]
    try:
        result.append(str(child(esp, 'EFI/WinDoesNot').relative_to(esp)))
    except RuntimeError:
        pass
    return result


def has_custom_include(text):
    return bool(re.search(r'(?m)^\s*source\s+["\']?\$(?:prefix|\{prefix\}|config_directory|\{config_directory\})/custom\.cfg(?:["\']|\s|$)', text))


def safe_path(directory, relative):
    current = directory
    for part in Path(relative).parts:
        if part in ('.', '..', '/'):
            raise RuntimeError('Unsafe menu path')
        current /= part
        if current.is_symlink():
            raise RuntimeError('Symlink in menu path')
    return current


def linux_root(row):
    """Support ordinary roots and @, leaving separate /boot layouts explicit."""
    with mounted(row) as volume:
        for subdir in ('', '@') if row['fstype'] == 'btrfs' else ('',):
            root = safe_path(volume, subdir) if subdir else volume
            fstab = safe_path(root, 'etc/fstab')
            grub = safe_path(root, 'boot/grub/grub.cfg')
            if not fstab.is_file() or not grub.is_file() or grub.is_symlink():
                continue
            mounts = [line.split() for line in fstab.read_text().splitlines()
                      if line.strip() and not line.lstrip().startswith('#')]
            if any(len(fields) > 1 and fields[1] == '/boot' for fields in mounts):
                continue
            if not has_custom_include(grub.read_text()):
                continue
            custom = grub.with_name('custom.cfg')
            if custom.is_symlink():
                continue
            return {'root_uuid': row['uuid'], 'root_subdir': subdir,
                    'menu_sha256': digest(grub),
                    'custom_sha256': digest(custom) if custom.exists() else None}
    raise RuntimeError('No supported GRUB custom.cfg include on the Linux root')


def probe(osprober_lines):
    result = {'candidates': [], 'unavailable': []}
    if not is_efi():
        return result
    if secure_boot():
        result['unavailable'].append('Secure Boot')
        return result
    rows = devices()
    linux = set()
    for line in osprober_lines:
        fields = line.split(':')
        if len(fields) >= 4 and fields[-1] == 'linux':
            linux.add(fields[0].split('@')[0])
    firmware = command(['efibootmgr', '-v'])
    order = re.search(r'(?m)^BootOrder:\s*([0-9a-fA-F]{4})', firmware)
    for entry in entries(firmware):
        # Extending an inactive secondary menu would not make WinDoesNot
        # reachable through the current default. Never switch menus silently.
        if order is None or entry['firmware_id'] != order[1].upper():
            continue
        try:
            esp_row = by_uuid(rows, 'partuuid', entry['esp_partuuid'])
            if esp_row['fstype'] != 'vfat':
                continue
            by_uuid(rows, 'uuid', esp_row['uuid'])
            with mounted(esp_row) as esp:
                executable = child(esp, entry['efi_file'])
                if not executable.is_file():
                    continue
                name = executable.name.casefold()
                candidate = dict(entry, esp_uuid=esp_row['uuid'])
                if name == 'systemd-bootx64.efi':
                    config = child(esp, 'loader/loader.conf')
                    candidate.update(kind='systemd-boot', menu_path=str(config.relative_to(esp)), menu_sha256=digest(config))
                elif name == 'refind_x64.efi':
                    config = child(executable.parent, 'refind.conf')
                    scan = re.findall(r'(?im)^\s*scanfor\s+([^\n#]+)', config.read_text())
                    if scan and 'manual' not in re.split(r'[\s,]+', scan[-1].strip().lower()):
                        continue
                    candidate.update(kind='refind', menu_path=str(config.relative_to(esp)), menu_sha256=digest(config))
                elif name in ('grubx64.efi', 'shimx64.efi'):
                    if name == 'shimx64.efi':
                        child(executable.parent, 'grubx64.efi')
                    stub = child(executable.parent, 'grub.cfg').read_text()
                    if '/boot/grub' not in stub or 'configfile' not in stub:
                        continue
                    identifiers = {value.lower() for value in ROOT_UUID.findall(stub)}
                    roots = [row for row in rows if row['path'] in linux
                             and str(row.get('uuid', '')).lower() in identifiers]
                    if len(roots) != 1:
                        continue
                    by_uuid(rows, 'uuid', roots[0]['uuid'])
                    candidate.update(kind='grub', **linux_root(roots[0]))
                else:
                    continue
                # Identification remains useful even when adding an entry is
                # blocked by occupied WinDoesNot paths. Do not change reuse rules.
                if osprober_lines:
                    result['detected_bootloader'] = candidate['kind']
                conflicts = reserved_files(esp)
                if conflicts:
                    result['unavailable'].append(entry['label'] + ': ' + ', '.join(conflicts))
                    continue
                candidate['id'] = hashlib.sha256(json.dumps({k: candidate.get(k) for k in
                    ('kind', 'esp_partuuid', 'efi_file', 'root_uuid', 'root_subdir')}, sort_keys=True).encode()).hexdigest()[:20]
                if candidate['id'] not in {item['id'] for item in result['candidates']}:
                    result['candidates'].append(candidate)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
            continue
    return result


def validate_plan(plan, osprober_lines):
    fresh = next((item for item in probe(osprober_lines)['candidates'] if item['id'] == plan.get('id')), None)
    if fresh is None or any(fresh.get(key) != plan.get(key) for key in
            ('kind', 'esp_uuid', 'esp_partuuid', 'efi_file', 'menu_path', 'root_uuid', 'root_subdir', 'menu_sha256', 'custom_sha256')):
        raise RuntimeError('The selected boot menu changed or is no longer safe to reuse. Return to the boot menu page.')
    return fresh


def configuration_ready(directory):
    """Never offer reuse with an older install sequence lacking its safety jobs."""
    import yaml
    try:
        directory = Path(directory)
        settings = yaml.safe_load((directory / 'settings.conf').read_text())
        execution = next(step['exec'] for step in settings['sequence'] if 'exec' in step)
        instances = {item['id']: item for item in settings['instances'] if item['module'] == 'windoesnotbootreuse'}
        for stage in ('preflight', 'guard', 'install', 'finish'):
            config = yaml.safe_load((directory / 'modules' / instances[stage]['config']).read_text())
            if config.get('stage') != stage:
                return False
        return (execution.index('windoesnotbootreuse@preflight') < execution.index('partition')
                and execution.index('mount') < execution.index('windoesnotbootreuse@guard') < execution.index('unpackfs')
                and execution.index('grubcfg') < execution.index('windoesnotbootreuse@install') < execution.index('bootloader')
                and execution.index('windoesnotfinish') < execution.index('windoesnotbootreuse@finish') < execution.index('umount')
                and yaml.safe_load((directory / 'modules/bootloader.conf').read_text()).get('efiBootLoaderVar') == 'windoesnotBootInstall')
    except (OSError, ValueError, KeyError, TypeError, StopIteration, yaml.YAMLError):
        return False


def target_esp(target):
    target = Path(target).resolve()
    if target == Path('/') or not target.is_dir():
        raise RuntimeError('Invalid installation target')
    esp = target / 'boot'
    info = json.loads(command(['findmnt', '--json', '--mountpoint', str(esp), '--output', 'FSTYPE,UUID']))['filesystems']
    if len(info) != 1 or info[0]['fstype'] != 'vfat':
        raise RuntimeError('The EFI system partition is not mounted at /boot')
    return esp, info[0]['uuid']


def guard(target, plan=None):
    esp, uuid = target_esp(target)
    if plan and uuid.lower() != plan['esp_uuid'].lower():
        raise RuntimeError('Choose the existing menu’s EFI system partition without formatting it.')
    conflicts = reserved_files(esp)
    if conflicts:
        raise RuntimeError('Existing Linux boot files would overlap: ' + ', '.join(conflicts)
                           + '. Use a separate EFI system partition; existing files were not overwritten.')
    usage = os.statvfs(esp)
    if usage.f_bavail * usage.f_frsize < 384 * 1024 * 1024:
        raise RuntimeError('The EFI partition needs at least 384 MiB free for both kernels and their startup files. Use a larger or separate EFI partition.')


def atomic_write(path, contents, metadata_from=None):
    if path.is_symlink():
        raise RuntimeError('Refusing to replace a symlink')
    original = path if path.exists() else metadata_from
    metadata = original.stat() if original is not None else None
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.windoesnot-', delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(contents.encode() if isinstance(contents, str) else contents)
            file.flush(); os.fsync(file.fileno())
            if metadata is not None:
                os.chown(temporary, metadata.st_uid, metadata.st_gid)
            temporary.chmod(metadata.st_mode & 0o777 if metadata is not None else 0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def append_menu(path, addition, token, expected):
    if path.is_symlink() or (digest(path) if path.exists() else None) != expected:
        raise RuntimeError('The existing menu changed; it was not edited.')
    before = path.read_bytes() if path.exists() else b''
    backup = path.with_name(path.name + '.before-windoesnot-' + token)
    if backup.exists():
        raise RuntimeError('A boot menu backup with this identifier already exists')
    atomic_write(backup, before, metadata_from=path if path.exists() else None)
    atomic_write(path, before + (b'\n' if before and not before.endswith(b'\n') else b'') + addition.encode())


def integrate(target, plan):
    esp, uuid = target_esp(target)
    if uuid.lower() != plan['esp_uuid'].lower():
        raise RuntimeError('The EFI partition changed')
    child(esp, 'EFI/WinDoesNot/grubx64.efi')
    root_info = json.loads(command(['findmnt', '--json', '--mountpoint', str(target), '--output', 'UUID']))['filesystems']
    token = root_info[0]['uuid']
    if not GUID.fullmatch(token):
        raise RuntimeError('Missing installation UUID')
    if plan['kind'] == 'systemd-boot':
        entry = esp / 'loader/entries' / ('windoesnot-' + token + '.conf')
        if entry.exists():
            raise RuntimeError('The new boot entry already exists')
        atomic_write(entry, 'title WinDoesNot\nefi /EFI/WinDoesNot/grubx64.efi\n')
    elif plan['kind'] == 'refind':
        config = child(esp, plan['menu_path'])
        name = 'windoesnot-' + token + '.conf'
        entry = config.with_name(name)
        if entry.exists():
            raise RuntimeError('The new boot entry already exists')
        # Validate and back up the existing configuration before adding anything.
        if digest(config) != plan['menu_sha256']:
            raise RuntimeError('The existing rEFInd configuration changed')
        atomic_write(entry, 'menuentry "WinDoesNot" {\n    loader /EFI/WinDoesNot/grubx64.efi\n}\n')
        append_menu(config, '\n# WinDoesNot\ninclude ' + name + '\n', token, plan['menu_sha256'])
    elif plan['kind'] == 'grub':
        row = by_uuid(devices(), 'uuid', plan['root_uuid'])
        with mounted(row, writable=True) as volume:
            config = safe_path(volume, ((plan['root_subdir'] + '/') if plan['root_subdir'] else '') + 'boot/grub/grub.cfg')
            if config.is_symlink() or digest(config) != plan['menu_sha256'] or not has_custom_include(config.read_text()):
                raise RuntimeError('The existing GRUB configuration changed')
            addition = ('\n# WinDoesNot ' + token + '\nmenuentry "WinDoesNot" --id windoesnot-' + token + ' {\n'
                        '    insmod part_gpt\n    insmod fat\n'
                        '    search --no-floppy --fs-uuid --set=windoesnot_esp ' + uuid + '\n'
                        '    chainloader ($windoesnot_esp)/EFI/WinDoesNot/grubx64.efi\n}\n')
            append_menu(config.with_name('custom.cfg'), addition, token, plan['custom_sha256'])
    else:
        raise RuntimeError('Unsupported existing menu')


if __name__ == '__main__':
    if os.geteuid() != 0 or not Path('/etc/windoesnot-image-build').is_file():
        raise SystemExit('Live installer only')
    try:
        import sys
        import signal
        def interrupted(*_):
            raise RuntimeError('Boot menu inspection interrupted')
        signal.signal(signal.SIGTERM, interrupted)
        data = json.load(sys.stdin)
        ready = all(configuration_ready(Path('/etc/windoesnot-calamares') / mode) for mode in ('', 'online'))
        ready = ready and Path('/usr/lib/calamares/modules/windoesnotbootreuse/main.py').is_file()
        print(json.dumps(probe(data['osprober']) if ready else {'candidates': [], 'error': 'configuration'}))
    except Exception:
        print(json.dumps({'candidates': [], 'error': True}))
