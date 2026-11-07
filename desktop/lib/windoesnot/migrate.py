#!/usr/bin/env python3
"""Read-only Windows discovery and checked rsync migration. See docs/dev/UMZUG-MANIFEST.md."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import sys
import uuid
import xml.etree.ElementTree as ET

FOLDERS = ('Documents', 'Pictures', 'Music', 'Videos', 'Downloads', 'Desktop')
EXCLUDED = {'default', 'public', 'all users', 'default user'}
DE = {'Documents': 'Dokumente', 'Pictures': 'Bilder', 'Music': 'Musik', 'Videos': 'Videos', 'Downloads': 'Downloads', 'Desktop': 'Desktop'}
SCHEMA = 1
FIREFOX_LOCKS = ('parent.lock', '.parentlock', 'lock')


def command(argv, **kwargs):
    return subprocess.run(argv, text=True, capture_output=True, **kwargs)


def partitions():
    data = json.loads(subprocess.check_output(['lsblk', '--json', '-b', '-o', 'PATH,TYPE,FSTYPE,LABEL,SIZE,MOUNTPOINTS'], text=True))
    result = []
    def visit(node):
        fs = (node.get('fstype') or '').lower()
        if node.get('type') == 'part' and (fs in ('ntfs', 'bitlocker', 'bitlk') or 'bitlocker' in fs):
            result.append({'device': node['path'], 'filesystem': 'bitlocker' if fs in ('bitlocker', 'bitlk') or 'bitlocker' in fs else 'ntfs', 'size': node.get('size', 0), 'label': node.get('label') or ''})
        for child in node.get('children') or []:
            visit(child)
    for node in data.get('blockdevices', []):
        visit(node)
    return result


def unlock_bitlocker(device, secret, mapper):
    """Explicit call only. Secret stays on stdin, never command line or disk."""
    if not re.fullmatch(r'[A-Za-z0-9_-]+', mapper):
        raise ValueError('Invalid mapper name')
    if not secret or ('\n' in secret) or ('\x00' in secret):
        raise ValueError('Invalid BitLocker secret')
    if re.fullmatch(r'[\d-]+', secret) and len(secret.replace('-', '')) != 48:
        raise ValueError('Recovery key must contain 48 digits')
    result = subprocess.run(['cryptsetup', 'open', '--readonly', '--type', 'bitlk', '--key-file', '-', device, mapper], input=secret + '\n', text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'BitLocker unlock failed')
    return '/dev/mapper/' + mapper


LEGACY_JUNCTIONS = {'My Music', 'My Pictures', 'My Videos'}


def mount_readonly(device, mountpoint):
    errors = []
    for argv in (['mount', '-t', 'ntfs3', '-o', 'ro,nosuid,nodev,noexec', device, str(mountpoint)],
                 ['ntfs-3g', '-o', 'ro,nosuid,nodev,noexec', device, str(mountpoint)]):
        result = command(argv)
        if result.returncode == 0:
            return
        errors.append(result.stderr.strip())
    raise RuntimeError('NTFS read-only mount failed; Windows Fast Startup or hibernation may be active. ' + ' | '.join(errors))


def warning_flags(path):
    flags = []
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            flags.append('reparse_or_link')
        if hasattr(os, 'listxattr') and any('reparse' in x.lower() for x in os.listxattr(path, follow_symlinks=False)):
            flags.append('reparse_or_link')
    except OSError:
        flags.append('unreadable')
    return sorted(set(flags))


def measure(path):
    total, warnings = 0, set()
    if warning_flags(path):
        return 0, warning_flags(path)
    for base, dirs, files in os.walk(path, followlinks=False, onerror=lambda _: warnings.add('unreadable')):
        for name in list(dirs):
            flags = warning_flags(Path(base) / name)
            if flags:
                dirs.remove(name)
                warnings.update(flags)
        for name in files:
            item = Path(base) / name
            flags = warning_flags(item)
            if flags:
                warnings.update(flags)
                continue
            try:
                info = item.stat(follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    total += info.st_size
            except OSError:
                warnings.add('unreadable')
    return total, sorted(warnings)


def scan_tree(root, device='fixture', filesystem='ntfs', locale='en'):
    root = Path(root)
    profiles = []
    root_warnings = []
    try:
        handoff = read_handoff(root)
    except (OSError, ValueError, json.JSONDecodeError):
        handoff = None
        root_warnings.append('handoff_invalid')
    users = root / 'Users'
    if users.is_dir():
        for profile in sorted(users.iterdir(), key=lambda p: p.name.lower()):
            if profile.name.lower() in EXCLUDED or warning_flags(profile) or not profile.is_dir():
                continue
            items = []
            for folder in FOLDERS:
                path = profile / folder
                if not warning_flags(path) and path.is_dir():
                    size, warnings = measure(path)
                    selected = folder in handoff['profiles'].get(profile.name, []) if handoff else True
                    items.append({'kind': folder, 'source': str(path.relative_to(root)), 'bytes': size, 'selected': selected, 'warnings': warnings})
            firefox = profile / 'AppData/Roaming/Mozilla/Firefox'
            if not warning_flags(firefox) and firefox.is_dir():
                size, warnings = measure(firefox)
                try:
                    firefox_profiles(firefox)
                except ValueError as error:
                    warnings.append('firefox_unavailable')
                selected = 'Firefox' in handoff['profiles'].get(profile.name, []) if handoff else False
                items.append({'kind': 'Firefox', 'source': str(firefox.relative_to(root)), 'bytes': size, 'selected': selected, 'warnings': warnings})
            if items:
                warnings = []
                onedrive = profile / 'OneDrive'
                if onedrive.exists():
                    warnings.append('onedrive_files_may_be_online_only')
                    _, flags = measure(onedrive)
                    warnings.extend(flags)
                profiles.append({'name': profile.name, 'items': items, 'warnings': sorted(set(warnings))})
    if (root / 'hiberfil.sys').exists():
        root_warnings.append('hibernation_possible')
    return {'schema': SCHEMA, 'device': device, 'filesystem': filesystem, 'locale': locale, 'profiles': profiles,
            'handoff': {'windows_version': handoff['windows_version'], 'locale': handoff['locale'], 'wlan_exports': handoff['wlan_exports'],
                        'wlan_selected': handoff['wlan'], 'chromium_passwords': handoff['chromium_passwords']} if handoff else None,
            'warnings': root_warnings}


def scan_device(device, locale='en', secret=None):
    candidate = next((p for p in partitions() if p['device'] == device), None)
    if not candidate:
        raise ValueError('Device is not a detected Windows partition')
    if candidate['filesystem'] == 'bitlocker' and not secret:
        return {'schema': SCHEMA, 'device': device, 'filesystem': 'bitlocker', 'locale': locale, 'profiles': [], 'warnings': ['bitlocker_locked']}
    mapper = None
    mounted = False
    with tempfile.TemporaryDirectory(prefix='windoesnot-migrate-') as temp:
        try:
            source = device
            if candidate['filesystem'] == 'bitlocker':
                mapper = 'windoesnot_migrate_' + str(os.getpid())
                source = unlock_bitlocker(device, secret, mapper)
            mount_readonly(source, temp)
            mounted = True
            return scan_tree(temp, device, candidate['filesystem'], locale)
        finally:
            if mounted:
                command(['umount', temp])
            if mapper:
                command(['cryptsetup', 'close', mapper])


def target_name(kind, locale):
    if kind == 'Firefox':
        return '.mozilla/firefox'
    return DE[kind] if locale.lower().startswith('de') else kind


def firefox_target(home):
    flatpak = home / '.var/app/org.mozilla.firefox'
    return flatpak / '.mozilla/firefox' if flatpak.is_dir() and not (home / '.mozilla/firefox').exists() else home / '.mozilla/firefox'


def firefox_profiles(source):
    ini = source / 'profiles.ini'
    if not ini.is_file() or warning_flags(ini):
        raise ValueError('Firefox profiles.ini is missing or redirected')
    config = configparser.ConfigParser(interpolation=None)
    config.read(ini, encoding='utf-8-sig')
    profiles = []
    for section in config.sections():
        if not re.fullmatch(r'Profile\d+', section):
            continue
        path = Path(config.get(section, 'Path', fallback=''))
        if config.get(section, 'IsRelative', fallback='0') != '1' or len(path.parts) != 2 or path.parts[0] != 'Profiles' or path.parts[1] in ('.', '..') or any(ord(c) < 32 for c in path.parts[1]):
            raise ValueError('Unsupported Firefox profile path')
        folder = source / path
        if warning_flags(folder) or not folder.is_dir():
            raise ValueError('Firefox profile is missing or redirected')
        if any((folder / name).exists() for name in FIREFOX_LOCKS):
            raise ValueError('Firefox profile is locked; close Firefox in Windows first')
        name = config.get(section, 'Name', fallback=path.name)
        if not name or any(ord(c) < 32 for c in name):
            raise ValueError('Invalid Firefox profile name')
        profiles.append((name, folder))
    if not profiles:
        raise ValueError('No Firefox profiles found')
    return profiles


def import_wlan(source, target):
    """Import only clear-text WPA2 PSK or WPA3 SAE netsh exports."""
    source, target = Path(source), Path(target)
    result = {'imported': 0, 'errors': []}
    if warning_flags(source) or not source.is_dir():
        return result
    target.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError('NetworkManager directory is redirected')
    for xml in sorted(source.glob('WLAN-*.xml')):
        try:
            if warning_flags(xml) or xml.stat().st_size > 1048576:
                raise ValueError('Unsafe WLAN export')
            tree = ET.parse(xml)
            def field(path):
                node = tree.getroot()
                for part in path.split('/'):
                    node = next((child for child in node if child.tag.rsplit('}', 1)[-1] == part), None) if node is not None else None
                return (node.text or '').strip() if node is not None else ''
            ssid = field('name')
            auth = field('MSM/security/authEncryption/authentication')
            encryption = field('MSM/security/authEncryption/encryption')
            protected = field('MSM/security/sharedKey/protected')
            key = field('MSM/security/sharedKey/keyMaterial')
            if auth not in ('WPA2PSK', 'WPA3SAE') or encryption != 'AES' or protected.lower() != 'false':
                raise ValueError('Unsupported WLAN authentication or encryption')
            if not ssid or len(ssid.encode('utf-8')) > 32 or any(ord(c) < 32 for c in ssid):
                raise ValueError('Invalid WLAN name')
            if not (8 <= len(key) <= 63 or (auth == 'WPA2PSK' and len(key) == 64 and re.fullmatch(r'[0-9a-fA-F]{64}', key))) or any(ord(c) < 32 or ord(c) > 126 for c in key):
                raise ValueError('Invalid WLAN key')
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'windoesnot-wlan:' + ssid))
            path = target / ('windoesnot-' + hashlib.sha256(ssid.encode()).hexdigest()[:16] + '.nmconnection')
            escaped_ssid = ssid.replace('\\', '\\\\')
            content = f'[connection]\nid={escaped_ssid}\nuuid={uid}\ntype=wifi\n\n[802-11-wireless]\nssid={escaped_ssid}\nmode=infrastructure\n\n[802-11-wireless-security]\nkey-mgmt={"sae" if auth == "WPA3SAE" else "wpa-psk"}\npsk={key.replace(chr(92), chr(92) * 2)}\n\n[ipv4]\nmethod=auto\n\n[ipv6]\nmethod=auto\n'
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(content)
            result['imported'] += 1
        except (OSError, ET.ParseError, ValueError) as error:
            result['errors'].append({'path': xml.name, 'error': str(error) if isinstance(error, ValueError) else 'Could not import WLAN export'})
    return result


def read_handoff(root):
    handoff = Path(root) / 'WinDoesNotHandoff'
    manifest = handoff / 'manifest.json'
    if not manifest.exists():
        return None
    if warning_flags(handoff) or warning_flags(manifest) or manifest.stat().st_size > 65536:
        raise ValueError('Unsafe handoff manifest')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('profiles'), dict):
        raise ValueError('Unsupported handoff manifest')
    if not isinstance(data.get('locale'), str) or not re.fullmatch(r'[A-Za-z]{2,3}(?:_[A-Za-z]{2})?(?:\.UTF-8)?', data['locale']) or not isinstance(data.get('windows_version'), str) or len(data['windows_version']) > 128 or any(ord(c) < 32 for c in data['windows_version']):
        raise ValueError('Invalid handoff metadata')
    for name, folders in data['profiles'].items():
        if not isinstance(name, str) or not name or '/' in name or '\\' in name or not isinstance(folders, list) or any(folder not in (*FOLDERS, 'Firefox') for folder in folders):
            raise ValueError('Invalid handoff selection')
    if not isinstance(data.get('wlan', False), bool):
        raise ValueError('Invalid WLAN selection')
    chromium = handoff / 'chromium-passwords.csv'
    return {'locale': data['locale'], 'windows_version': data['windows_version'], 'profiles': data['profiles'],
            'wlan': data.get('wlan', False), 'wlan_exports': len(list((handoff / 'wlan').glob('WLAN-*.xml'))) if (handoff / 'wlan').is_dir() else 0,
            'chromium_passwords': chromium.is_file() and not warning_flags(chromium)}


def _valid_item(root, profile, item):
    kind = item.get('kind')
    if kind not in (*FOLDERS, 'Firefox'):
        raise ValueError('Invalid folder kind')
    expected = Path('Users') / profile / ('AppData/Roaming/Mozilla/Firefox' if kind == 'Firefox' else kind)
    if item.get('source') != str(expected) or profile.lower() in EXCLUDED or not profile or '/' in profile or '\\' in profile or profile in ('.', '..'):
        raise ValueError('Invalid source path')
    path = root / expected
    if not path.is_dir() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Source folder missing or redirected')
    current = root
    for component in expected.parts:
        current = current / component
        if warning_flags(current):
            raise ValueError('Source path has a link or reparse point')
    return path


def copy_manifest(manifest, home, source_root=None, dry_run=False, secret=None, progress=None, nm_dir=None):
    if manifest.get('schema') != SCHEMA or manifest.get('filesystem') not in ('ntfs', 'bitlocker'):
        raise ValueError('Unsupported manifest')
    home = Path(home)
    if not home.is_dir() or home.is_symlink():
        raise ValueError('Target home is missing or redirected')
    device = manifest.get('device')
    if source_root is None and not any(p['device'] == device for p in partitions()):
        raise ValueError('Windows partition is no longer available')
    mapper = None
    temporary = tempfile.TemporaryDirectory(prefix='windoesnot-migrate-') if source_root is None else None
    mounted = False
    root = Path(temporary.name if temporary else source_root)
    try:
        if temporary:
            source_device = device
            if manifest['filesystem'] == 'bitlocker':
                if not secret:
                    raise ValueError('BitLocker requires an explicit password or recovery key')
                mapper = 'windoesnot_migrate_' + str(os.getpid())
                source_device = unlock_bitlocker(device, secret, mapper)
            mount_readonly(source_device, root)
            mounted = True
        jobs = []
        def safe_target(directory):
            current = home
            for component in directory.relative_to(home).parts:
                current = current / component
                if current.is_symlink() or (current.exists() and not current.is_dir()):
                    raise ValueError('Target folder is redirected')
        def make_target(directory):
            safe_target(directory)
            current = home
            owner = home.stat()
            for component in directory.relative_to(home).parts:
                current = current / component
                if not current.exists():
                    current.mkdir()
                    os.chown(current, owner.st_uid, owner.st_gid)
        for profile in manifest.get('profiles', []):
            for item in profile.get('items', []):
                if item.get('selected'):
                    source = _valid_item(root, profile.get('name', ''), item)
                    size, flags = measure(source)
                    target = firefox_target(home) if item['kind'] == 'Firefox' else home / target_name(item['kind'], manifest.get('locale', 'en'))
                    safe_target(target)
                    jobs.append((source, target, size, flags, item['kind']))
        needed = sum(size for _, _, size, _, _ in jobs)
        free = shutil.disk_usage(home).free
        if needed > free:
            raise OSError(f'Not enough free space: need {needed} bytes, have {free} bytes')
        summary = {'bytes': needed, 'free': free, 'folders': len(jobs), 'errors': [], 'wlan_imported': 0}
        if dry_run:
            return summary
        def report(event, **fields):
            if progress:
                progress({'event': event, **fields})
        report('start', bytes=needed, free=free, folders=len(jobs))
        copied = 0
        def failed(path, message):
            error = {'path': str(path), 'error': message}
            summary['errors'].append(error)
            report('file_error', **error)
        def copy_file(entry, destination):
            safe_target(destination)
            if (destination / entry.name).is_symlink():
                failed(entry, 'target file is redirected')
                return
            make_target(destination)
            result = command(['rsync', '-a', '--no-links', '--no-devices', '--no-specials', '--no-perms', '--chown=' + str(home.stat().st_uid) + ':' + str(home.stat().st_gid), '--', str(entry), str(destination) + '/'])
            nonlocal copied
            if result.returncode:
                failed(entry, result.stderr.strip() or 'rsync failed')
            else:
                copied += entry.stat(follow_symlinks=False).st_size
                report('file', path=str(entry), copied_bytes=copied, total_bytes=needed)
        def copy_tree(source, target):
            safe_target(target)
            make_target(target)
            for base, dirs, files in os.walk(source, followlinks=False, onerror=lambda e: failed(e.filename, str(e))):
                relative = Path(base).relative_to(source)
                for name in list(dirs):
                    entry = Path(base) / name
                    if warning_flags(entry):
                        dirs.remove(name)
                        # Windows' legacy junctions point at folders copied separately.
                        if name not in LEGACY_JUNCTIONS:
                            failed(entry, 'link, reparse point or unreadable')
                    else:
                        safe_target(target / relative / name)
                        make_target(target / relative / name)
                for name in files:
                    entry = Path(base) / name
                    if warning_flags(entry) or not entry.is_file():
                        failed(entry, 'link, reparse point or unreadable')
                        continue
                    copy_file(entry, target / relative)
        for source, target, _, flags, kind in jobs:
            if kind != 'Firefox':
                copy_tree(source, target)
                continue
            try:
                profiles = firefox_profiles(source)
            except ValueError as error:
                failed(source, str(error))
                continue
            safe_target(target)
            make_target(target)
            ini = target / 'profiles.ini'
            if ini.is_symlink():
                failed(ini, 'target file is redirected')
                continue
            existing = ini.read_text(encoding='utf-8') if ini.exists() else '[General]\nStartWithLastProfile=1\n'
            parsed = configparser.ConfigParser(interpolation=None)
            parsed.optionxform = str
            try:
                parsed.read_string(existing)
            except configparser.Error as error:
                failed(ini, str(error))
                continue
            indices = [int(section[7:]) for section in parsed.sections() if re.fullmatch(r'Profile\d+', section)]
            existing_profiles = {parsed.get(section, 'Path', fallback=''): parsed.get(section, 'Name', fallback='') for section in parsed.sections() if re.fullmatch(r'Profile\d+', section)}
            additions = []
            for name, folder in profiles:
                base = folder.name + '-windows'
                candidate = base
                number = 2
                while (target / 'Profiles' / candidate).exists() and existing_profiles.get('Profiles/' + candidate) != name + ' (Windows)':
                    candidate = f'{base}-{number}'
                    number += 1
                registered = existing_profiles.get('Profiles/' + candidate) == name + ' (Windows)'
                before = len(summary['errors'])
                copy_tree(folder, target / 'Profiles' / candidate)
                if len(summary['errors']) != before:
                    continue
                if not registered:
                    index = max(indices, default=-1) + 1
                    indices.append(index)
                    additions.append(f'[Profile{index}]\nName={name} (Windows)\nIsRelative=1\nPath=Profiles/{candidate}\n')
            if additions:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target, prefix='.profiles-', delete=False) as stream:
                    stream.write(existing.rstrip() + '\n\n' + '\n'.join(additions))
                    staged = Path(stream.name)
                os.chmod(staged, 0o600)
                os.chown(staged, home.stat().st_uid, home.stat().st_gid)
                os.replace(staged, ini)
        if manifest.get('handoff') and manifest['handoff'].get('wlan_selected'):
            try:
                handoff = read_handoff(root)
                if not handoff or not handoff['wlan']:
                    raise ValueError('WLAN handoff is missing')
                if nm_dir is None:
                    raise ValueError('NetworkManager target is missing')
                wlan = import_wlan(root / 'WinDoesNotHandoff/wlan', nm_dir)
                summary['wlan_imported'] = wlan['imported']
                for error in wlan['errors']:
                    failed(error['path'], error['error'])
            except (OSError, ValueError, json.JSONDecodeError) as error:
                failed('WinDoesNotHandoff/wlan', str(error))
        report('done', copied_bytes=copied, total_bytes=needed, errors=summary['errors'])
        return summary
    finally:
        if temporary:
            if mounted:
                command(['umount', str(root)])
            temporary.cleanup()
        if mapper:
            command(['cryptsetup', 'close', mapper])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('partitions')
    scan = sub.add_parser('scan'); scan.add_argument('device'); scan.add_argument('--locale', default='en'); scan.add_argument('--secret-stdin', action='store_true')
    copy = sub.add_parser('copy'); copy.add_argument('manifest', type=Path); copy.add_argument('home', type=Path); copy.add_argument('--dry-run', action='store_true'); copy.add_argument('--secret-stdin', action='store_true'); copy.add_argument('--progress-json', action='store_true'); copy.add_argument('--nm-dir', type=Path)
    args = parser.parse_args()
    if args.action == 'partitions':
        result = partitions()
    elif args.action == 'scan':
        result = scan_device(args.device, args.locale, secret=__import__('sys').stdin.readline().strip() if args.secret_stdin else None)
    else:
        callback = (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True)) if args.progress_json else None
        result = copy_manifest(json.loads(args.manifest.read_text()), args.home, dry_run=args.dry_run, secret=sys.stdin.readline().strip() if args.secret_stdin else None, progress=callback, nm_dir=args.nm_dir)
    print(json.dumps(result if not getattr(args, 'progress_json', False) else {'event': 'summary', **result}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        # Callers show stderr to the user; a traceback would be noise.
        sys.exit(f'{error}')
