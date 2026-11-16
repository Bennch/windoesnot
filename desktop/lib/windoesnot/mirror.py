#!/usr/bin/env python3
"""Read-only Linux inventory. Copying is not yet implemented."""
import argparse
import configparser
from contextlib import contextmanager
from datetime import datetime
import hashlib
import shutil
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import subprocess
import sys
import tempfile

PACKAGE = re.compile(r'^[a-z0-9@._+-]+$')


def partitions():
    data = json.loads(subprocess.check_output(['lsblk', '--json', '-b', '-o', 'PATH,TYPE,FSTYPE,LABEL,SIZE,MOUNTPOINTS'], text=True, timeout=20))
    result = []
    def visit(node):
        fs = (node.get('fstype') or '').lower()
        if node.get('type') == 'part' and fs in ('ext4', 'btrfs', 'xfs', 'crypto_luks'):
            result.append({'device': node['path'], 'filesystem': fs, 'size': node.get('size', 0), 'label': node.get('label') or ''})
        for child in node.get('children') or []:
            visit(child)
    for node in data.get('blockdevices', []):
        visit(node)
    return result


def safe_path(root, relative):
    """Resolve only ordinary components within root; never follow a symlink."""
    root = Path(root).resolve(strict=True)
    path = Path(relative)
    if path.is_absolute() or any(p in ('.', '..') for p in path.parts):
        raise ValueError('Unsafe relative path')
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink in path')
    if not current.resolve(strict=False).is_relative_to(root):
        raise ValueError('Path outside source')
    return current


def read_file(root, path):
    try:
        item = safe_path(root, path)
        if not item.is_file():
            return ''
        return item.read_text(encoding='utf-8', errors='replace')
    except (OSError, ValueError):
        return ''


def desc_fields(text):
    fields, key = {}, None
    for line in text.splitlines():
        if line.startswith('%') and line.endswith('%'):
            key = line[1:-1]
            fields.setdefault(key, [])
        elif line and key:
            fields[key].append(line)
    return fields


def valid_package(name):
    return isinstance(name, str) and bool(PACKAGE.fullmatch(name)) and not name.startswith('-')


def arch_packages(root):
    local = safe_path(root, 'var/lib/pacman/local')
    installed, explicit = set(), set()
    if local.is_dir():
        for entry in local.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                continue
            fields = desc_fields(read_file(root, entry.relative_to(Path(root)) / 'desc'))
            names = fields.get('NAME', [])
            if len(names) != 1 or not valid_package(names[0]):
                continue
            installed.add(names[0])
            if fields.get('REASON', ['0']) == ['0']:
                explicit.add(names[0])
    sync = safe_path(root, 'var/lib/pacman/sync')
    available, seen = set(), False
    if sync.is_dir():
        for db in sync.glob('*.db'):
            if db.is_symlink() or not db.is_file():
                continue
            try:
                with tarfile.open(db, 'r:*') as archive:
                    seen = True
                    for member in archive:
                        if member.isfile() and member.name.endswith('/desc') and member.size <= 1024 * 1024:
                            stream = archive.extractfile(member)
                            if stream:
                                fields = desc_fields(stream.read().decode('utf-8', errors='replace'))
                                available.update(n for n in fields.get('NAME', []) if valid_package(n))
            except (OSError, tarfile.TarError):
                seen = False
                break
    return sorted(explicit), sorted(installed - available) if seen else None


def deb_packages(root):
    status = read_file(root, 'var/lib/dpkg/status')
    installed = set()
    for paragraph in status.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line)
        name = fields.get('Package', '')
        if fields.get('Status') == 'install ok installed' and valid_package(name):
            installed.add(name)
    auto = set()
    for paragraph in read_file(root, 'var/lib/apt/extended_states').split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line)
        if fields.get('Auto-Installed') == '1':
            auto.add(fields.get('Package', ''))
    return sorted(installed - auto)


def measure(path):
    total, warnings = 0, set()
    def onerror(_):
        warnings.add('unreadable')
    for base, dirs, files in os.walk(path, followlinks=False, onerror=onerror):
        for name in dirs + files:
            try:
                info = (Path(base) / name).lstat()
                if stat.S_ISREG(info.st_mode):
                    total += info.st_size
                elif not (stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                    warnings.add('special_file')
            except OSError:
                warnings.add('unreadable')
    return total, sorted(warnings)


def scan_tree(root, device='fixture', filesystem='ext4'):
    root = Path(root).resolve(strict=True)
    values = {}
    os_release = read_file(root, 'etc/os-release') or read_file(root, 'usr/lib/os-release')
    for line in os_release.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            if key == 'PRETTY_NAME':
                values[key] = value.strip().strip('"\'')
    users, warnings, flatpak = [], [], set()
    for line in read_file(root, 'etc/passwd').splitlines():
        parts = line.split(':')
        if len(parts) != 7 or not parts[2].isdigit() or not parts[3].isdigit() or int(parts[2]) < 1000 or int(parts[2]) == 65534:
            continue
        home = parts[5]
        try:
            if not home.startswith('/') or home == '/':
                raise ValueError('invalid home')
            path = safe_path(root, home.lstrip('/'))
            if not path.is_dir():
                warnings.append('home_missing:' + parts[0]); continue
            size, flags = measure(path)
            users.append({'name': parts[0], 'uid': int(parts[2]), 'gid': int(parts[3]),
                          'home': home, 'bytes': size, 'warnings': flags})
            apps = safe_path(root, path.relative_to(root) / '.local/share/flatpak/app')
            if apps.is_dir():
                flatpak.update(p.name for p in apps.iterdir() if not p.is_symlink() and p.is_dir())
        except (OSError, ValueError):
            warnings.append('home_unsafe:' + parts[0])
    try:
        apps = safe_path(root, 'var/lib/flatpak/app')
        if apps.is_dir():
            flatpak.update(p.name for p in apps.iterdir() if not p.is_symlink() and p.is_dir())
        explicit, foreign = arch_packages(root)
    except (OSError, ValueError):
        explicit, foreign = [], None
        warnings.append('package_database_unsafe')
    if foreign is None:
        warnings.append('arch_foreign_unknown')
    services = []
    try:
        systemd = safe_path(root, 'etc/systemd/system')
        if systemd.is_dir():
            for wants in systemd.iterdir():
                if wants.name.endswith(('.wants', '.requires')) and not wants.is_symlink() and wants.is_dir():
                    services.extend(item.name for item in wants.iterdir() if item.is_symlink())
    except (OSError, ValueError):
        warnings.append('services_unreadable')
    return {'schema': 1, 'kind': 'linux', 'device': device, 'filesystem': filesystem,
            'system': values.get('PRETTY_NAME', 'Linux'), 'users': users,
            'packages': {'arch_explicit': explicit, 'arch_foreign': foreign,
                         'deb_manual': deb_packages(root), 'flatpak': sorted(flatpak)},
            'services': sorted(set(services)), 'source_root': str(root), 'warnings': warnings}


def command(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, timeout=30, **kwargs)


def checked(args, **kwargs):
    result = command(args, **kwargs)
    if result.returncode:
        raise RuntimeError('Command failed: ' + args[0] + ': ' + result.stderr.strip())
    return result.stdout


def unlock_luks(device, secret, mapper):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', mapper):
        raise ValueError('Invalid mapper name')
    if not secret or '\n' in secret or '\x00' in secret:
        raise ValueError('Invalid LUKS secret')
    checked(['cryptsetup', 'open', '--readonly', '--type', 'luks', '--key-file', '-', device, mapper], input=secret + '\n')
    return '/dev/mapper/' + mapper


def mount_readonly(device, path, filesystem, subvol=None):
    options = ['ro', 'nosuid', 'nodev', 'noexec']
    if filesystem == 'ext4':
        options.append('noload')
    elif filesystem == 'xfs':
        options.append('norecovery')
    elif filesystem != 'btrfs':
        raise ValueError('Unsupported filesystem')
    if subvol is not None:
        if filesystem != 'btrfs' or subvol not in ('@', '@home', '5'):
            raise ValueError('Unsupported subvolume')
        options.append(('subvolid=' if subvol == '5' else 'subvol=') + subvol)
    checked(['mount', '-t', filesystem, '-o', ','.join(options), '--', device, str(path)])


def block_id(device):
    info = os.stat(device)
    if not stat.S_ISBLK(info.st_mode):
        raise ValueError("Source is not a block device")
    return f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}"


@contextmanager
def mounted_source(device, secret=None):
    filesystem = checked(['blkid', '-s', 'TYPE', '-o', 'value', '--', device]).strip().lower()
    if filesystem == 'crypto_luks' and not secret:
        raise ValueError('LUKS password required')
    mapper = None
    mounts = []
    temporary = tempfile.TemporaryDirectory(prefix='windoesnot-mirror-')
    with temporary as temp:
        root = Path(temp) / 'root'
        top = Path(temp) / 'top'
        root.mkdir(); top.mkdir()
        try:
            source = device
            if filesystem == 'crypto_luks':
                mapper_name = 'windoesnot_mirror_' + str(os.getpid())
                source = unlock_luks(device, secret, mapper_name)
                mapper = mapper_name
                filesystem = checked(['blkid', '-s', 'TYPE', '-o', 'value', '--', source]).strip().lower()
            subvolumes = set()
            if filesystem == 'btrfs':
                mount_readonly(source, top, filesystem, '5'); mounts.append(top)
                listing = checked(['btrfs', 'subvolume', 'list', str(top)])
                subvolumes = {line.split(' path ', 1)[1] for line in listing.splitlines() if ' path ' in line}
            mount_readonly(source, root, filesystem, '@' if '@' in subvolumes else None); mounts.append(root)
            if '@home' in subvolumes:
                home = safe_path(root, 'home')
                if not home.is_dir():
                    raise ValueError('Btrfs home mountpoint missing or unsafe')
                mount_readonly(source, home, filesystem, '@home'); mounts.append(home)
            yield root, filesystem, sorted(subvolumes.intersection({'@', '@home'}))
        finally:
            cleanup_errors = []
            for path in reversed(mounts):
                result = command(['umount', str(path)])
                if result.returncode:
                    cleanup_errors.append('unmount failed: ' + str(path))
            if mapper:
                result = command(['cryptsetup', 'close', mapper])
                if result.returncode:
                    cleanup_errors.append('LUKS close failed: ' + mapper)
            if cleanup_errors:
                # Never recursively clean a directory that may still be mounted.
                temporary._finalizer.detach()
                temporary.cleanup = lambda: None
                raise RuntimeError('; '.join(cleanup_errors))


def scan_device(device, secret=None):
    identity = block_id(device)
    with mounted_source(device, secret) as (root, filesystem, subvolumes):
        result = scan_tree(root, device, filesystem)
        result['block_identity'] = identity
        result['subvolumes'] = subvolumes
        result['warnings'].append('separate_filesystems_not_scanned')
        return result


# Managed desktop trees are installed beneath ~/.config by windoesnot-initialize.
PROTECTED = tuple('.config/' + name for name in (
    'hypr', 'hyprdesk', 'quickshell', 'snappy-switcher', 'swaync',
    'ghostty', 'gtk-3.0', 'gtk-4.0', 'fish'))


def digest(path, size):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        if size <= 64 * 1024 * 1024:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
        else:
            for offset in (0, size // 2, max(0, size - 1024 * 1024)):
                stream.seek(offset)
                h.update(stream.read(min(1024 * 1024, size - offset)))
    return h.digest()


def copy_home(manifest, home, progress=None):
    if manifest.get('schema') != 1 or manifest.get('kind') != 'linux':
        raise ValueError('Invalid manifest')
    users = manifest.get('users', [])
    if len(users) != 1:
        raise ValueError('Exactly one source user required')
    user = users[0]
    name = user.get('name', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in ('.', '..'):
        raise ValueError('Invalid source user')
    root = Path(manifest['source_root']).resolve(strict=True)
    source = safe_path(root, user['home'].lstrip('/'))
    home = Path(home)
    if home.is_symlink() or not home.is_dir() or home.resolve() != home.absolute():
        raise ValueError('Unsafe target home')
    home = home.resolve()
    if source == home or source in home.parents or home in source.parents:
        raise ValueError('Source and target overlap')
    if not source.is_dir() or not user['home'].startswith('/'):
        raise ValueError('Invalid source home')
    owner = home.stat()
    archive = home / ('Umzug-' + name) / 'original'
    entries, directories, total = [], [], 0
    def walk_error(error):
        raise error
    for base, dirs, files in os.walk(source, followlinks=False, onerror=walk_error):
        for entry in dirs + files:
            item = Path(base) / entry
            rel = item.relative_to(source)
            info = item.lstat()
            if stat.S_ISDIR(info.st_mode):
                if info.st_dev != source.stat().st_dev:
                    raise ValueError('Nested filesystem: ' + str(rel))
                directories.append(rel)
                continue
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                raise ValueError('Unsupported special file: ' + str(rel))
            total += info.st_size if stat.S_ISREG(info.st_mode) else 0
            entries.append((rel, info))
    free = shutil.disk_usage(home).free
    if total > free:
        raise OSError('Not enough free space')
    if progress:
        progress({'event': 'start', 'bytes': total, 'free': free})
    def make_directories(path):
        current = home
        for part in path.relative_to(home).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError('Symlink in target directory')
            if not current.exists():
                current.mkdir()
                os.chown(current, owner.st_uid, owner.st_gid)
            elif not current.is_dir():
                raise ValueError('Target directory conflict')
    for rel in directories:
        managed = any(rel.as_posix() == p or rel.as_posix().startswith(p + '/') for p in PROTECTED)
        target = (archive if managed else home) / rel
        make_directories(target)
    jobs = {home: [], archive: []}
    for rel, info in entries:
        managed = any(rel.as_posix() == p or rel.as_posix().startswith(p + '/') for p in PROTECTED)
        dest = safe_path(home, rel.parent)
        target = dest / rel.name
        if managed or target.exists() or target.is_symlink():
            # Identical files on repeat are already complete.
            if not managed and stat.S_ISREG(info.st_mode) and target.is_file() and not target.is_symlink() and target.stat().st_size == info.st_size and digest(source / rel, info.st_size) == digest(target, info.st_size):
                continue
            destroot = archive
        else:
            destroot = home
        safe_path(home, (destroot / rel.parent).relative_to(home))
        jobs[destroot].append((rel, info))
    copied_bytes = 0
    for destroot, items in jobs.items():
        if not items:
            continue
        for rel, _ in items:
            parent = destroot / rel.parent
            safe_path(home, parent.relative_to(home))
            make_directories(parent)
            safe_path(home, parent.relative_to(home))
        with tempfile.TemporaryFile() as listing:
            for rel, _ in items:
                listing.write(os.fsencode(str(rel)) + b'\0')
            listing.seek(0)
            args = ['rsync', '-aHAX', '--numeric-ids', '--ignore-existing', '--from0',
                    '--files-from=-', '--no-implied-dirs',
                    '--usermap=' + str(user['uid']) + ':' + str(owner.st_uid),
                    '--groupmap=' + str(user['gid']) + ':' + str(owner.st_gid),
                    '--', str(source) + '/', str(destroot) + '/']
            result = subprocess.run(args, stdin=listing, capture_output=True)
            if result.returncode:
                raise RuntimeError('rsync failed: ' + result.stderr.decode(errors='replace'))
        for rel, info in items:
            safe_path(home, (destroot / rel.parent).relative_to(home))
            target = destroot / rel
            if stat.S_ISREG(info.st_mode):
                if target.is_symlink() or not target.is_file() or target.stat().st_size != info.st_size or digest(source / rel, info.st_size) != digest(target, info.st_size):
                    raise RuntimeError('Verification failed: ' + str(rel))
            elif not target.is_symlink() or os.readlink(source / rel) != os.readlink(target):
                raise RuntimeError('Verification failed: ' + str(rel))
            copied_bytes += info.st_size if stat.S_ISREG(info.st_mode) else 0
            if progress:
                progress({'event': 'file', 'path': str(rel), 'archive': destroot == archive,
                          'copied_bytes': copied_bytes, 'total_bytes': total})
    if progress:
        progress({'event': 'done', 'bytes': total})
    return {'bytes': total, 'files': len(entries)}


def archive_etc_and_wifi(source_root, state_dir, connections_dir, *, archive_etc=True, wifi=True):
    """Archive source /etc and restore nonconflicting Wi-Fi profiles.

    Callers must supply trusted, already provisioned target directories and run
    as root. Never replace an existing profile or follow source/target links.
    """
    source_root = Path(source_root).resolve(strict=True)
    etc = safe_path(source_root, 'etc')
    state_dir, connections_dir = Path(state_dir), Path(connections_dir)
    for directory in (state_dir, connections_dir):
        if not directory.is_dir() or directory.is_symlink() or directory.resolve() != directory.absolute():
            raise ValueError('Unsafe system destination')
    if not archive_etc:
        return restore_wifi(source_root, connections_dir) if wifi else 0
    archive = state_dir / 'etc-alt'
    if archive.is_symlink():
        raise ValueError('Unsafe archive')
    archive.mkdir(exist_ok=True)
    result = subprocess.run(['rsync', '-aHAX', '--numeric-ids', '--ignore-existing', '--', str(etc) + '/', str(archive) + '/'], capture_output=True)
    if result.returncode:
        raise RuntimeError('Could not archive /etc')
    return restore_wifi(source_root, connections_dir) if wifi else 0


def restore_wifi(source_root, connections_dir):
    connections_dir = Path(connections_dir)
    profiles = safe_path(source_root, 'etc/NetworkManager/system-connections')
    if not profiles.is_dir():
        return 0
    def profile(path):
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.read_string(path.read_text(encoding='utf-8'))
        return parser
    uuids = set()
    for path in connections_dir.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        try:
            value = profile(path).get('connection', 'uuid', fallback='').lower()
            if value:
                uuids.add(value)
        except (OSError, UnicodeError, configparser.Error):
            # Unknown existing profiles prevent proving UUID uniqueness.
            raise ValueError('Unreadable existing network profile')
    count = 0
    for path in profiles.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        try:
            data = profile(path)
            if not (data.has_section('wifi') or data.has_section('wifi-security')):
                continue
            uuid = data.get('connection', 'uuid', fallback='').lower()
            if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', uuid) or uuid in uuids:
                continue
            target = connections_dir / path.name
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, 'wb') as out, path.open('rb') as inp:
                    shutil.copyfileobj(inp, out)
                    os.fchown(out.fileno(), 0, 0)
                    os.fchmod(out.fileno(), 0o600)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            uuids.add(uuid)
            count += 1
        except FileExistsError:
            continue
    return count



def copy_manifest(manifest, home, target_root='/', secret=None, progress=None):
    if manifest.get('schema') != 1 or manifest.get('kind') != 'linux':
        raise ValueError('Invalid manifest')
    device = manifest.get('device')
    identity = manifest.get('block_identity')
    if not isinstance(device, str) or not device.startswith('/dev/') or block_id(device) != identity:
        raise ValueError('Source block identity changed or missing')
    target = Path(target_root)
    if not target.is_absolute() or target.resolve() != target:
        raise ValueError('Unsafe target root')
    errors, result = [], {'errors': []}
    def attempt(name, action):
        try:
            result[name] = action()
        except Exception as error:
            errors.append({'path': name, 'error': str(error)})
    with mounted_source(device, secret) as (root, filesystem, subvolumes):
        if block_id(device) != identity or filesystem != manifest.get('filesystem'):
            raise ValueError('Source block identity or filesystem changed')
        plan = dict(manifest, source_root=str(root))
        selected = [u for u in manifest.get('users', []) if u.get('selected', True)]
        plan['users'] = selected
        if selected:
            attempt('home', lambda: copy_home(plan, home, progress))
        state = safe_path(target, 'var/lib/windoesnot/mirror/' + datetime.now().strftime('%Y-%m-%d'))
        connections = safe_path(target, 'etc/NetworkManager/system-connections')
        def prepare(path):
            path.mkdir(parents=True, exist_ok=True)
            if path.resolve() != path or path.is_symlink():
                raise ValueError('Unsafe destination')
        def wifi():
            prepare(state); prepare(connections)
            return archive_etc_and_wifi(root, state, connections, archive_etc=False)
        if manifest.get('wlan_selected', False):
            attempt('wifi', wifi)
        def archive():
            prepare(state); prepare(connections)
            return archive_etc_and_wifi(root, state, connections, wifi=False)
        attempt('etc', archive)
        def write_json(filename, data):
            prepare(state)
            path = safe_path(state, filename)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False)
        def packages():
            if len(selected) != 1:
                raise ValueError('Exactly one selected user required for package report')
            groups = manifest.get('package_selection', {})
            if not isinstance(groups, dict) or any(not isinstance(v, bool) for v in groups.values()):
                raise ValueError('Invalid package selection')
            data = {'home': '/' + str(Path(home).relative_to(target)), 'source': selected[0]['name']}
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', data['source']) or data['source'] in ('.', '..'):
                raise ValueError('Invalid source user')
            for group in ('arch_explicit', 'arch_foreign', 'deb_manual', 'flatpak'):
                value = manifest.get('packages', {}).get(group)
                if not groups.get(group, False):
                    value = None if group == 'arch_foreign' else []
                if (value is None and group != 'arch_foreign') or (value is not None and (not isinstance(value, list) or any(not isinstance(n, str) or not (re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', n) and '.' in n if group == 'flatpak' else valid_package(n)) for n in value))):
                    raise ValueError('Invalid package names in ' + group)
                data[group] = value
            write_json('packages.json', data)
        attempt('packages', packages)
        def services():
            items = manifest.get('services', [])
            if not isinstance(items, list) or any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z0-9_.@:-]+', x) for x in items):
                raise ValueError('Invalid services')
            write_json('services.json', items)
        attempt('services', services)
    result['errors'] = errors
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('partitions')
    scan = sub.add_parser('scan')
    scan.add_argument('device')
    scan.add_argument('--secret-stdin', action='store_true')
    copy = sub.add_parser('copy')
    copy.add_argument('manifest')
    copy.add_argument('home')
    copy.add_argument('--progress-json', action='store_true')
    copy.add_argument('--target-root', default='/')
    copy.add_argument('--secret-stdin', action='store_true')
    args = parser.parse_args()
    if args.action == 'partitions':
        print(json.dumps(partitions(), ensure_ascii=False))
        return
    if args.action == 'copy':
        with open(args.manifest, encoding='utf-8') as stream:
            manifest = json.load(stream)
        report = (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True)) if args.progress_json else None
        secret = sys.stdin.readline().rstrip('\n') if args.secret_stdin else None
        result = copy_manifest(manifest, args.home, args.target_root, secret, report)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return
    secret = sys.stdin.readline().rstrip('\n') if args.secret_stdin else None
    print(json.dumps(scan_device(args.device, secret), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        sys.exit(str(error))
