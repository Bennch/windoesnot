#!/usr/bin/env python3
"""Read-only Windows discovery and checked rsync migration. See docs/dev/UMZUG-MANIFEST.md."""
import argparse
import configparser
import csv
import filecmp
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
DE = {'Documents': 'Dokumente', 'Pictures': 'Bilder', 'Music': 'Musik', 'Videos': 'Videos', 'Downloads': 'Downloads', 'Desktop': 'Schreibtisch'}
XDG_KEYS = {'Documents': 'DOCUMENTS', 'Pictures': 'PICTURES', 'Music': 'MUSIC', 'Videos': 'VIDEOS', 'Downloads': 'DOWNLOAD', 'Desktop': 'DESKTOP'}
SCHEMA = 1
ENVELOPE_FILES = ('chromium-chrome.igcred', 'chromium-edge.igcred', 'chromium-brave.igcred')  # written by the Setup app, one per browser
MAIL_PATHS = {'Thunderbird': 'AppData/Roaming/Thunderbird', 'Windows Live Mail': 'AppData/Local/Microsoft/Windows Live Mail', 'Windows Mail': 'AppData/Local/Microsoft/Windows Mail'}
FIREFOX_LOCKS = ('parent.lock', '.parentlock', 'lock')


def command(argv, **kwargs):
    # Device enumeration can block on a broken storage stack or disappearing USB disk.
    kwargs.setdefault('timeout', 20)
    return subprocess.run(argv, text=True, capture_output=True, **kwargs)


def partitions():
    data = json.loads(subprocess.check_output(['lsblk', '--json', '-b', '-o', 'PATH,TYPE,FSTYPE,LABEL,SIZE,MOUNTPOINTS'], text=True, timeout=20))
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
    if re.fullmatch(r'[\d-]+', secret) and not (re.fullmatch(r'\d{48}', secret) or re.fullmatch(r'(?:\d{6}-){7}\d{6}', secret)):
        raise ValueError('Recovery key must contain eight groups of six digits')
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


def is_legacy_junction(path):
    """Windows 7's 'My Pictures' junctions (localised: 'Eigene Bilder') inside Documents. They point at one of the
    profile's standard folders, which are copied on their own, so skipping them loses nothing and needs no warning."""
    if path.name in LEGACY_JUNCTIONS:
        return True
    try:
        target = os.readlink(path)
    except OSError:
        return False
    parts = [part for part in re.split(r'[\\/]', target) if part not in ('', '.', '..')]
    return len(parts) >= 3 and parts[-3].lower() == 'users' and parts[-1] in FOLDERS


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
                # Windows' legacy junctions point at folders measured and copied separately.
                if not is_legacy_junction(Path(base) / name):
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


def plain_path(root, relative):
    current = root
    for part in Path(relative).parts:
        current = current / part
        if warning_flags(current):
            return False
    return True


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
    if not warning_flags(users) and users.is_dir():
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
            if plain_path(profile, 'AppData/Roaming/Mozilla/Firefox') and firefox.is_dir():
                size, warnings = measure(firefox)
                try:
                    firefox_profiles(firefox)
                except ValueError as error:
                    warnings.append('firefox_unavailable')
                selected = 'Firefox' in handoff['profiles'].get(profile.name, []) if handoff else False
                items.append({'kind': 'Firefox', 'source': str(firefox.relative_to(root)), 'bytes': size, 'selected': selected, 'warnings': warnings})
            thunderbird = profile / MAIL_PATHS['Thunderbird']
            if plain_path(profile, MAIL_PATHS['Thunderbird']) and thunderbird.is_dir():
                size, warnings = measure(thunderbird)
                try:
                    firefox_profiles(thunderbird)
                except ValueError:
                    warnings.append('thunderbird_unavailable')
                items.append({'kind': 'Thunderbird', 'source': str(thunderbird.relative_to(root)), 'bytes': size, 'selected': True, 'warnings': warnings})
            for kind in ('Windows Live Mail', 'Windows Mail'):
                relative = MAIL_PATHS[kind]
                path = profile / relative
                if plain_path(profile, relative) and path.is_dir():
                    size, warnings = measure(path)
                    items.append({'kind': kind, 'source': str(path.relative_to(root)), 'bytes': size, 'selected': True, 'warnings': warnings})
            for relative in ('Documents/Outlook Files', 'AppData/Local/Microsoft/Outlook'):
                folder = profile / relative
                if not plain_path(profile, relative) or not folder.is_dir():
                    continue
                for base, dirs, files in os.walk(folder, followlinks=False):
                    dirs[:] = [d for d in dirs if not warning_flags(Path(base) / d)]
                    for name in sorted(files):
                        path = Path(base) / name
                        if path.suffix.lower() in ('.pst', '.ost') and not warning_flags(path) and path.is_file():
                            kind = 'Outlook PST' if path.suffix.lower() == '.pst' else 'Outlook OST'
                            items.append({'kind': kind, 'source': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'selected': kind == 'Outlook PST', 'warnings': ['outlook_ost'] if kind == 'Outlook OST' else []})
            browsers = []
            for name, relative in (('Edge', 'Microsoft/Edge'), ('Chrome', 'Google/Chrome'), ('Chromium', 'Chromium')):
                browser = profile / 'AppData/Local' / relative / 'User Data'
                if plain_path(profile, str(browser.relative_to(profile))) and browser.is_dir():
                    browsers.append(name)
            if items or browsers:
                warnings = []
                onedrive = profile / 'OneDrive'
                if onedrive.exists():
                    warnings.append('onedrive_files_may_be_online_only')
                    _, flags = measure(onedrive)
                    warnings.extend(flags)
                if browsers:
                    warnings.append('chromium_passwords_windows_export_only')
                profiles.append({'name': profile.name, 'items': items, 'warnings': sorted(set(warnings)), 'browsers': browsers})
    if hibernation_pending(root / 'hiberfil.sys'):
        root_warnings.append('hibernation_possible')
    return {'schema': SCHEMA, 'device': device, 'filesystem': filesystem, 'locale': locale, 'profiles': profiles,
            'handoff': {'windows_version': handoff['windows_version'], 'locale': handoff['locale'], 'wlan_exports': handoff['wlan_exports'],
                        'wlan_selected': handoff['wlan'], 'chromium_passwords': handoff['chromium_passwords'], 'chromium_envelope': handoff['chromium_envelope']} if handoff else None,
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


def target_name(kind, locale, home=None):
    if kind == 'Firefox':
        return '.mozilla/firefox'
    if home is not None:
        # The installed account's real folder names (e.g. Schreibtisch) win over any guess.
        try:
            text = (Path(home) / '.config/user-dirs.dirs').read_text()
        except OSError:
            text = ''
        match = re.search(r'^XDG_' + XDG_KEYS[kind] + r'_DIR="?\$HOME/([^"\n/]+)"?\s*$', text, re.M)
        if match and match.group(1) not in ('.', '..'):
            return match.group(1)
    return DE[kind] if locale.lower().startswith('de') else kind


def firefox_target(home):
    return home / '.mozilla/firefox'


def firefox_profiles(source):
    ini = source / 'profiles.ini'
    if not ini.is_file() or warning_flags(ini):
        raise ValueError('Firefox profiles.ini is missing or redirected')
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(ini, encoding='utf-8-sig')
    except (configparser.Error, UnicodeError, OSError):
        raise ValueError('Firefox profiles.ini cannot be read')
    profiles = []
    for section in config.sections():
        if not re.fullmatch(r'Profile\d+', section):
            continue
        path = Path(config.get(section, 'Path', fallback=''))
        if config.get(section, 'IsRelative', fallback='0') != '1' or len(path.parts) != 2 or path.parts[0] != 'Profiles' or path.parts[1] in ('.', '..') or any(ord(c) < 32 for c in path.parts[1]):
            raise ValueError('Unsupported Firefox profile path')
        folder = source / path
        if not plain_path(source, str(path)) or not folder.is_dir():
            raise ValueError('Firefox profile is missing or redirected')
        if any(os.path.lexists(folder / name) for name in FIREFOX_LOCKS):
            raise ValueError('Firefox profile is locked; close Firefox in Windows first')
        if any(folder.glob('*.sqlite-wal')) or any(folder.glob('*.sqlite-journal')) or any(folder.glob('*.db-wal')) or any(folder.glob('*.db-journal')) or any(folder.glob('*.sqlite-shm')) or any(folder.glob('*.db-shm')):
            raise ValueError('Firefox database journal present; close Firefox in Windows first')
        name = config.get(section, 'Name', fallback=path.name)
        if not name or any(ord(c) < 32 for c in name):
            raise ValueError('Invalid Firefox profile name')
        profiles.append((name, folder))
    if not profiles:
        raise ValueError('No Firefox profiles found')
    return profiles


def thunderbird_accounts(folder):
    """Read public account settings only; never inspect credential stores."""
    prefs = folder / 'prefs.js'
    if warning_flags(prefs) or not prefs.is_file() or prefs.stat().st_size > 4 * 1024 * 1024:
        return []
    settings = {}
    pattern = re.compile(r'^user_pref\("(mail\.(?:account|server|identity)\.[A-Za-z0-9_.-]+)",\s*("(?:[^"\\]|\\.)*"|[0-9]+)\);\s*$')
    for line in prefs.read_text(encoding='utf-8', errors='replace').splitlines():
        match = pattern.match(line)
        if match:
            try:
                settings[match.group(1)] = json.loads(match.group(2))
            except ValueError:
                continue
    accounts = []
    for key, server in settings.items():
        if not re.fullmatch(r'mail\.account\.[^.]+\.server', key) or not isinstance(server, str):
            continue
        kind = settings.get('mail.server.' + server + '.type', '')
        if kind not in ('imap', 'pop3'):
            continue
        identity = settings.get(key[:-6] + 'identities', '')
        identity = identity.split(',')[0] if isinstance(identity, str) else ''
        values = (settings.get('mail.identity.' + identity + '.useremail', ''),
                  settings.get('mail.server.' + server + '.hostname', ''), kind)
        accounts.append(tuple(re.sub(r'[\x00-\x1f\x7f]', ' ', str(v))[:256] for v in values))
    return accounts


def eml_to_mbox(source, target):
    """Convert each EML directory to a Thunderbird mbox and .sbd hierarchy."""
    def convert(folder, destination):
        entries = sorted(folder.iterdir(), key=lambda p: p.name.casefold())
        files = [p for p in entries if p.suffix.lower() == '.eml']
        children = [p for p in entries if p.is_dir() and not warning_flags(p)]
        if any(warning_flags(p) for p in entries):
            raise ValueError('Link or reparse point in mail store')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('wb') as out:
            for entry in files:
                if not entry.is_file():
                    raise ValueError('Invalid EML file')
                data = entry.read_bytes().replace(b'\r\n', b'\n').replace(b'\r', b'\n')
                out.write(b'From - Sat Jan 01 00:00:00 2000\n')
                out.write(re.sub(br'(?m)^(>*From )', br'>\1', data))
                out.write(b'\n' if data.endswith(b'\n') else b'\n\n')
        for child in children:
            if child.name in ('.', '..') or '/' in child.name or '\\' in child.name:
                raise ValueError('Invalid mail folder name')
            convert(child, Path(str(destination) + '.sbd') / child.name)
    convert(source, target)


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
            def field(path, strip=True):
                node = tree.getroot()
                for part in path.split('/'):
                    node = next((child for child in node if child.tag.rsplit('}', 1)[-1] == part), None) if node is not None else None
                value = (node.text or '') if node is not None else ''
                return value.strip() if strip else value
            # The profile name can differ from the actual wireless network.
            # Never silently connect to the profile label as if it were an SSID.
            ssid = field('SSIDConfig/SSID/name', strip=False)
            if not ssid:
                hex_ssid = field('SSIDConfig/SSID/hex')
                try:
                    ssid = bytes.fromhex(hex_ssid).decode('utf-8') if hex_ssid else ''
                except (ValueError, UnicodeDecodeError):
                    raise ValueError('Unsupported WLAN SSID')
            hidden = field('SSIDConfig/nonBroadcast').lower()
            if hidden not in ('', 'true', 'false'):
                raise ValueError('Invalid WLAN visibility')
            auth = field('MSM/security/authEncryption/authentication')
            encryption = field('MSM/security/authEncryption/encryption')
            protected = field('MSM/security/sharedKey/protected')
            key = field('MSM/security/sharedKey/keyMaterial', strip=False)
            if auth not in ('WPA2PSK', 'WPA3SAE') or encryption != 'AES' or protected.lower() != 'false':
                raise ValueError('Unsupported WLAN authentication or encryption')
            if not ssid or ssid != ssid.strip() or len(ssid.encode('utf-8')) > 32 or any(ord(c) < 32 for c in ssid):
                raise ValueError('Invalid WLAN name')
            if key != key.strip() or not (8 <= len(key) <= 63 or (auth == 'WPA2PSK' and len(key) == 64 and re.fullmatch(r'[0-9a-fA-F]{64}', key))) or any(ord(c) < 32 or ord(c) > 126 for c in key):
                raise ValueError('Invalid WLAN key')
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'windoesnot-wlan:' + ssid))
            path = target / ('windoesnot-' + hashlib.sha256(ssid.encode()).hexdigest()[:16] + '.nmconnection')
            escaped_ssid = ssid.replace('\\', '\\\\')
            content = f'[connection]\nid={escaped_ssid}\nuuid={uid}\ntype=wifi\n\n[802-11-wireless]\nssid={escaped_ssid}\nmode=infrastructure\nhidden={"true" if hidden == "true" else "false"}\n\n[802-11-wireless-security]\nkey-mgmt={"sae" if auth == "WPA3SAE" else "wpa-psk"}\npsk={key.replace(chr(92), chr(92) * 2)}\n\n[ipv4]\nmethod=auto\n\n[ipv6]\nmethod=auto\n'
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
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate handoff key')
            result[key] = value
        return result
    data = json.loads(manifest.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        raise ValueError('Invalid handoff manifest')
    if type(data.get('schema')) is not int or data.get('schema') != 1 or not isinstance(data.get('profiles'), dict):
        raise ValueError('Unsupported handoff manifest')
    if not isinstance(data.get('locale'), str) or not re.fullmatch(r'[A-Za-z]{2,3}(?:_[A-Za-z]{2})?(?:\.UTF-8)?', data['locale']) or not isinstance(data.get('windows_version'), str) or len(data['windows_version']) > 128 or any(ord(c) < 32 for c in data['windows_version']):
        raise ValueError('Invalid handoff metadata')
    for name, folders in data['profiles'].items():
        if not isinstance(name, str) or not name or name in ('.', '..') or any(ord(c) < 32 for c in name) or '/' in name or '\\' in name or not isinstance(folders, list) or any(not isinstance(folder, str) or folder not in (*FOLDERS, 'Firefox') for folder in folders) or len(set(folders)) != len(folders):
            raise ValueError('Invalid handoff selection')
    if not isinstance(data.get('wlan', False), bool):
        raise ValueError('Invalid WLAN selection')
    chromium = handoff / 'chromium-passwords.csv'
    return {'locale': data['locale'], 'windows_version': data['windows_version'], 'profiles': data['profiles'],
            'wlan': data.get('wlan', False), 'wlan_exports': len(list((handoff / 'wlan').glob('WLAN-*.xml'))) if (handoff / 'wlan').is_dir() else 0,
            'chromium_passwords': chromium.is_file() and not warning_flags(chromium),
            'chromium_envelope': any((handoff / name).is_file() and not warning_flags(handoff / name) for name in ENVELOPE_FILES)}


def export_envelope(path, home, password):
    """Authenticate the entire payload before creating a browser import file."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if warning_flags(path) or not path.is_file():
        raise ValueError('Passworthülle fehlt oder ist unsicher')
    data = path.read_bytes()
    if len(data) < 52 or data[:8] != b'IGCRD001':
        raise ValueError('Passworthülle ist beschädigt oder hat ein unbekanntes Format')
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), data[8:24], 600000, dklen=32)
    try:
        payload = json.loads(AESGCM(key).decrypt(data[24:36], data[36:], None))
        if not isinstance(payload, dict) or not isinstance(payload.get('browser'), str) or not isinstance(payload.get('logins'), list):
            raise ValueError()
        rows = []
        for login in payload['logins']:
            if not isinstance(login, dict) or any(not isinstance(login.get(k), str) for k in ('url', 'username', 'password')):
                raise ValueError()
            rows.append((login['url'], login['url'], login['username'], login['password']))
    except (InvalidTag, ValueError, UnicodeDecodeError, TypeError):
        raise ValueError('Passwort falsch oder Passworthülle beschädigt oder manipuliert') from None

    target = home / 'Umzug-Windows'
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ValueError('Zielordner ist umgeleitet')
    if not target.exists():
        target.mkdir(mode=0o700)
        os.chown(target, home.stat().st_uid, home.stat().st_gid)
    number = 1
    while True:
        filename = 'Passwoerter.csv' if number == 1 else f'Passwoerter-{number}.csv'
        destination = target / filename
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            number += 1
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), home.stat().st_uid, home.stat().st_gid)
            writer = csv.writer(stream)
            writer.writerow(('name', 'url', 'username', 'password'))
            writer.writerows(rows)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def _valid_item(root, profile, item):
    kind = item.get('kind')
    if kind not in (*FOLDERS, 'Firefox', *MAIL_PATHS, 'Outlook PST', 'Outlook OST'):
        raise ValueError('Invalid folder kind')
    if kind in ('Outlook PST', 'Outlook OST'):
        relative = Path(str(item.get('source', '')))
        prefix = Path('Users') / profile
        if (not relative.is_relative_to(prefix) or '..' in relative.parts or
                relative.suffix.lower() != ('.pst' if kind == 'Outlook PST' else '.ost') or
                not any(relative.is_relative_to(prefix / folder) for folder in ('Documents/Outlook Files', 'AppData/Local/Microsoft/Outlook'))):
            raise ValueError('Invalid Outlook source path')
        expected = relative
    else:
        expected = Path('Users') / profile / ('AppData/Roaming/Mozilla/Firefox' if kind == 'Firefox' else MAIL_PATHS.get(kind, kind))
    if item.get('source') != str(expected) or profile.lower() in EXCLUDED or not profile or '/' in profile or '\\' in profile or profile in ('.', '..'):
        raise ValueError('Invalid source path')
    path = root / expected
    if not (path.is_file() if kind in ('Outlook PST', 'Outlook OST') else path.is_dir()) or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Source folder missing or redirected')
    current = root
    for component in expected.parts:
        current = current / component
        if warning_flags(current):
            raise ValueError('Source path has a link or reparse point')
    return path


def hibernation_pending(hiberfil):
    """True if hiberfil.sys holds a saved session (hibernation or Fast Startup), so Windows files may be stale.

    Windows 7 keeps a hiberfil.sys on most PCs; its header is 'wake' or zeroes after a normal start, 'hibr'/'HIBR'/'RSTR'
    while a session is saved. An empty or unreadable file counts as pending (be careful rather than wrong).
    """
    try:
        if not hiberfil.exists():
            return False
        with hiberfil.open('rb') as stream:
            magic = stream.read(4)
    except OSError:
        return True
    return magic.lower() in (b'', b'hibr', b'rstr') or (len(magic) < 4)


def profile_folder_name(name):
    """Safe folder name for a further Windows account's files (never '.', '..' or a path)."""
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(name)).strip(' .')
    return cleaned or 'Windows'


def copy_manifest(manifest, home, source_root=None, dry_run=False, secret=None, progress=None, nm_dir=None, envelope_password=None):
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
        seen_kinds = set()
        for profile in manifest.get('profiles', []):
            for item in profile.get('items', []):
                if item.get('selected'):
                    source = _valid_item(root, profile.get('name', ''), item)
                    size, flags = (source.stat().st_size, []) if item['kind'] in ('Outlook PST', 'Outlook OST') else measure(source)
                    if item['kind'] in ('Firefox', *MAIL_PATHS, 'Outlook PST', 'Outlook OST'):
                        target = firefox_target(home) if item['kind'] == 'Firefox' else home / '.thunderbird'
                    else:
                        target = home / target_name(item['kind'], manifest.get('locale', 'en'), home)
                        # The first Windows account fills the folder directly; further accounts get their own
                        # subfolder, so same-named files of different people never collide or get dropped.
                        if item['kind'] in seen_kinds:
                            target = target / profile_folder_name(profile.get('name', ''))
                        seen_kinds.add(item['kind'])
                    safe_target(target)
                    jobs.append((source, target, size, flags, item['kind']))
        needed = sum(size for _, _, size, _, _ in jobs)
        free = shutil.disk_usage(home).free
        if needed > free:
            raise OSError(f'Not enough free space: need {needed} bytes, have {free} bytes')
        summary = {'bytes': needed, 'free': free, 'folders': len(jobs), 'errors': [], 'warnings': [], 'wlan_imported': 0, 'mail_imported': False}
        if dry_run:
            return summary
        def report(event, **fields):
            if progress:
                progress({'event': event, **fields})
        report('start', bytes=needed, free=free, folders=len(jobs))
        copied = 0
        mail_accounts = []
        def failed(path, message):
            error = {'path': str(path), 'error': message}
            summary['errors'].append(error)
            report('file_error', **error)
        def files_match(source, target):
            with source.open('rb') as left, target.open('rb') as right:
                while True:
                    chunk = left.read(1024 * 1024)
                    if chunk != right.read(1024 * 1024):
                        return False
                    if not chunk:
                        return True
        def copy_file(entry, destination):
            safe_target(destination)
            target_file = destination / entry.name
            if target_file.is_symlink():
                failed(entry, 'target file is redirected')
                return
            make_target(destination)
            # Preserve existing user files, including a file appearing between
            # the existence check and rsync. A retry may reuse identical data.
            result = command(['rsync', '-a', '--ignore-existing', '--no-links', '--no-devices', '--no-specials', '--no-perms', '--chown=' + str(home.stat().st_uid) + ':' + str(home.stat().st_gid), '--', str(entry), str(destination) + '/'])
            nonlocal copied
            if result.returncode:
                failed(entry, result.stderr.strip() or 'rsync failed')
            else:
                try:
                    if target_file.is_symlink() or not target_file.is_file() or not files_match(entry, target_file):
                        failed(entry, 'target file already exists with different contents or copy verification failed')
                        return
                    copied += entry.stat(follow_symlinks=False).st_size
                    report('file', path=str(entry), copied_bytes=copied, total_bytes=needed)
                except OSError:
                    failed(entry, 'could not verify copied file')
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
                        if not is_legacy_junction(entry):
                            failed(entry, 'link, reparse point or unreadable')
                    else:
                        safe_target(target / relative / name)
                        make_target(target / relative / name)
                for name in files:
                    if name.lower() in ('desktop.ini', 'thumbs.db'):
                        continue  # Windows folder metadata, useless on Linux
                    entry = Path(base) / name
                    if warning_flags(entry) or not entry.is_file():
                        failed(entry, 'link, reparse point or unreadable')
                        continue
                    copy_file(entry, target / relative)
        for source, target, _, flags, kind in jobs:
            if kind in ('Outlook PST', 'Outlook OST'):
                if kind == 'Outlook OST':
                    summary['warnings'].append({'path': str(source), 'error': 'OST: reconnect the server account or export a PST in Outlook'})
                    continue
                try:
                    make_target(target / 'PST-Import')
                    destination = target / 'PST-Import' / (profile_folder_name(source.stem) + '-' + hashlib.sha256(str(source.relative_to(root)).encode()).hexdigest()[:12])
                    if destination.exists() or destination.is_symlink():
                        raise ValueError('PST destination already exists')
                    with tempfile.TemporaryDirectory(prefix='.readpst-', dir=home) as temporary_pst:
                        converted = Path(temporary_pst) / 'converted'
                        converted.mkdir()
                        result = subprocess.run(['readpst', '-r', '-o', str(converted), str(source)], capture_output=True, text=True, timeout=3600)
                        if result.returncode:
                            raise ValueError('readpst failed: ' + result.stderr.strip()[:1000])
                        for base, dirs, files in os.walk(converted, followlinks=False):
                            if any(warning_flags(Path(base) / n) for n in dirs + files):
                                raise ValueError('Unsafe readpst output')
                            os.chown(base, home.stat().st_uid, home.stat().st_gid)
                            for name in files:
                                os.chown(Path(base) / name, home.stat().st_uid, home.stat().st_gid)
                        os.replace(converted, destination)
                    summary['mail_imported'] = True
                    summary['warnings'].append({'path': str(destination), 'error': 'PST converted; import the resulting mailboxes into Thunderbird'})
                except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                    summary['warnings'].append({'path': str(source), 'error': str(error)})
                continue
            if kind in ('Windows Live Mail', 'Windows Mail'):
                try:
                    safe_target(target)
                    make_target(target / 'Profiles' / 'windows-mail' / 'Mail' / 'Local Folders')
                    local = target / 'Profiles' / 'windows-mail' / 'Mail' / 'Local Folders'
                    name = profile_folder_name(source.parts[-5] if len(source.parts) >= 5 else 'Windows') + '-' + kind
                    final = local / name
                    if final.is_symlink() or Path(str(final) + '.sbd').is_symlink():
                        raise ValueError('Mail destination is redirected')
                    with tempfile.TemporaryDirectory(prefix='.mail-', dir=local) as temp:
                        staged = Path(temp) / name
                        eml_to_mbox(source, staged)
                        sub = Path(str(staged) + '.sbd')
                        final_sub = Path(str(final) + '.sbd')
                        if final.exists() or final_sub.exists():
                            def same_tree(left, right):
                                if not left.is_dir() or not right.is_dir() or warning_flags(right):
                                    return False
                                left_names = {p.name for p in left.iterdir()}
                                if left_names != {p.name for p in right.iterdir()}:
                                    return False
                                return all(same_tree(left / n, right / n) if (left / n).is_dir() else
                                           not warning_flags(right / n) and (right / n).is_file() and filecmp.cmp(left / n, right / n, shallow=False)
                                           for n in left_names)
                            if (not final.is_file() or not filecmp.cmp(staged, final, shallow=False) or
                                (sub.exists() != final_sub.exists()) or (sub.exists() and not same_tree(sub, final_sub))):
                                raise ValueError('Mail destination already exists with different contents')
                        else:
                            os.replace(staged, final)
                            if sub.exists():
                                os.replace(sub, final_sub)
                    prefs = target / 'Profiles' / 'windows-mail' / 'prefs.js'
                    if prefs.is_symlink():
                        raise ValueError('Target preferences are redirected')
                    if not prefs.exists():
                        prefs.write_text('user_pref("mail.account.account1.server", "server1");\nuser_pref("mail.accountmanager.accounts", "account1");\nuser_pref("mail.accountmanager.localfoldersserver", "server1");\nuser_pref("mail.server.server1.type", "none");\nuser_pref("mail.server.server1.name", "Local Folders");\nuser_pref("mail.server.server1.directory-rel", "[ProfD]Mail/Local Folders");\n', encoding='utf-8')
                    ini = target / 'profiles.ini'
                    if ini.is_symlink():
                        raise ValueError('Target profiles.ini is redirected')
                    existing = ini.read_text(encoding='utf-8') if ini.exists() else '[General]\nStartWithLastProfile=1\n'
                    config = configparser.ConfigParser(interpolation=None)
                    config.read_string(existing)
                    if not any(config.get(section, 'Path', fallback='') == 'Profiles/windows-mail' for section in config.sections()):
                        indices = [int(section[7:]) for section in config.sections() if re.fullmatch(r'Profile\d+', section)]
                        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target, delete=False) as stream:
                            stream.write(existing.rstrip() + f'\n\n[Profile{max(indices, default=-1)+1}]\nName=Windows Mail\nIsRelative=1\nPath=Profiles/windows-mail\n')
                            staged_ini = Path(stream.name)
                        os.chown(staged_ini, home.stat().st_uid, home.stat().st_gid)
                        os.replace(staged_ini, ini)
                    for base, dirs, files in os.walk(target / 'Profiles' / 'windows-mail'):
                        os.chown(base, home.stat().st_uid, home.stat().st_gid)
                        for file in files:
                            os.chown(Path(base) / file, home.stat().st_uid, home.stat().st_gid)
                    summary['mail_imported'] = True
                except (OSError, ValueError, configparser.Error) as error:
                    failed(source, str(error))
                continue
            if kind not in ('Firefox', 'Thunderbird'):
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
            profile_errors_before = len(summary['errors'])
            for name, folder in profiles:
                if kind == 'Thunderbird':
                    try:
                        mail_accounts.extend(thunderbird_accounts(folder))
                    except OSError:
                        failed(folder, 'Could not read account settings')
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
            if kind == 'Thunderbird' and (additions or any(existing_profiles.get('Profiles/' + folder.name + '-windows') == name + ' (Windows)' for name, folder in profiles)) and len(summary['errors']) == profile_errors_before:
                summary['mail_imported'] = True
            if additions:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target, prefix='.profiles-', delete=False) as stream:
                    stream.write(existing.rstrip() + '\n\n' + '\n'.join(additions))
                    staged = Path(stream.name)
                os.chmod(staged, 0o600)
                os.chown(staged, home.stat().st_uid, home.stat().st_gid)
                os.replace(staged, ini)
        if any(kind in (*MAIL_PATHS, 'Outlook PST', 'Outlook OST') for _, _, _, _, kind in jobs):
            try:
                report_dir = home / 'Umzug-Windows'
                make_target(report_dir)
                german = manifest.get('locale', 'en').lower().startswith('de')
                lines = (['Mail-Konten', 'Serverkonten in Thunderbird über „Konto hinzufügen“ einrichten; die Autokonfiguration kann dabei helfen.', 'Thunderbird gegebenenfalls installieren.', 'OST: Serverkonto erneut verbinden oder in Outlook als PST exportieren. Webmail und neues Outlook: Serverkonto in Thunderbird hinzufügen. PST-Ergebnisse gegebenenfalls in Thunderbird importieren.'] if german else
                         ['Mail accounts', 'Set up server accounts in Thunderbird using Add Account; automatic configuration can help.', 'Install Thunderbird if needed.', 'OST: reconnect the server account or export a PST in Outlook. Webmail and new Outlook: add the server account in Thunderbird. Import converted PST mailboxes into Thunderbird if needed.'])
                lines += [' | '.join(account) for account in sorted(set(mail_accounts))]
                for number in range(1, 10000):
                    path = report_dir / ('Mail-Konten.txt' if number == 1 else f'Mail-Konten-{number}.txt')
                    try:
                        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                            os.fchown(stream.fileno(), home.stat().st_uid, home.stat().st_gid)
                            stream.write('\n'.join(lines) + '\n')
                        break
                    except FileExistsError:
                        continue
                else:
                    raise OSError('No available account report filename')
            except (OSError, ValueError) as error:
                failed('Mail-Konten.txt', str(error))
        if manifest.get('handoff') and envelope_password:
            try:
                handoff = read_handoff(root)
                summary['password_csv'] = []
                for envelope_name in ENVELOPE_FILES:
                    envelope_path = root / 'WinDoesNotHandoff' / envelope_name
                    if not (handoff and (envelope_path.exists() or envelope_path.is_symlink())):
                        continue
                    try:
                        summary['password_csv'].append(str(export_envelope(envelope_path, home, envelope_password)))
                    except (OSError, ValueError, ImportError) as error:
                        failed('WinDoesNotHandoff/' + envelope_name, str(error))
                if summary['password_csv']:
                    summary['password_notice'] = 'Nach dem Passwortimport die CSV-Datei(en) löschen.'
                else:
                    del summary['password_csv']
            except (OSError, ValueError, json.JSONDecodeError) as error:
                failed('WinDoesNotHandoff', str(error))
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
    copy = sub.add_parser('copy'); copy.add_argument('manifest', type=Path); copy.add_argument('home', type=Path); copy.add_argument('--dry-run', action='store_true'); copy.add_argument('--secret-stdin', action='store_true'); copy.add_argument('--progress-json', action='store_true'); copy.add_argument('--nm-dir', type=Path); copy.add_argument('--envelope-password-stdin', action='store_true')
    args = parser.parse_args()
    if args.action == 'partitions':
        result = partitions()
    elif args.action == 'scan':
        result = scan_device(args.device, args.locale, secret=__import__('sys').stdin.readline().strip() if args.secret_stdin else None)
    else:
        callback = (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True)) if args.progress_json else None
        secret = sys.stdin.readline().rstrip('\r\n') if args.secret_stdin else None
        envelope_password = sys.stdin.readline().rstrip('\r\n') if args.envelope_password_stdin else None
        if args.envelope_password_stdin and not envelope_password:
            raise ValueError('Passwort für die Passworthülle fehlt')
        result = copy_manifest(json.loads(args.manifest.read_text()), args.home, dry_run=args.dry_run, secret=secret, progress=callback, nm_dir=args.nm_dir, envelope_password=envelope_password)
    print(json.dumps(result if not getattr(args, 'progress_json', False) else {'event': 'summary', **result}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        # Callers show stderr to the user; a traceback would be noise.
        sys.exit(f'{error}')
