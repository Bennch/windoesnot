"""File backup ("time machine" for the home folder) to an external drive or a network share.

Layout on the target (a normal folder tree, readable without WinDoesNot):
    <target>/WinDoesNot-Backup/<host>/
        backup.json                      identity of the set (host, user, created)
        snapshots/2026-11-20_143000/     one complete-looking tree per point in time
        snapshots/.2026-11-20_153000.partial   a run in progress (never listed, removed on the next run)
Unchanged files are hard links to the previous point (rsync --link-dest), so a point costs only what changed.
Targets without hard links (exFAT, FAT, some shares) keep one mirror (`current/`) and move replaced or deleted
files to `versions/<time>/` instead; the UI then offers per-file older versions only.
Nothing here needs root. Drives are mounted through udisks, network shares through an fstab automount entry
that `windoesnot-filebackup-mount` (pkexec) writes once.
"""
import datetime
import fcntl
import collections
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time

CONFIG_DIR = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'windoesnot'
CACHE_DIR = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'windoesnot'
CONFIG_FILE = CONFIG_DIR / 'filebackup.json'
STATUS_FILE = CACHE_DIR / 'filebackup-status.json'
LOCK_FILE = CACHE_DIR / 'filebackup.lock'
SET_DIR = 'WinDoesNot-Backup'
STAMP = '%Y-%m-%d_%H%M%S'
STAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}_\d{6}')
INTERVALS = {'hourly': 3600, 'daily': 86400, 'weekly': 7 * 86400}
HARDLINK_FS = {'ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'f2fs', 'ntfs3', 'ntfs', 'zfs', 'bcachefs', 'reiserfs', 'jfs'}
DEFAULT_EXCLUDES = ['.cache/', '.local/share/Trash/', '.local/share/Steam/', '.var/app/*/cache/', 'node_modules/', '.npm/_cacache/',
                    '.cargo/registry/', '.gradle/caches/', '.thumbnails/', 'snap/', '.local/share/containers/', '.local/share/docker/',
                    '*.part', '*.crdownload', '.Trash-*/', 'WinDoesNot-Backup/']
ENGINES = ('rsync', 'restic')
RESTIC_DIR = 'windoesnot-restic'
PASSWORD_FILE = CONFIG_DIR / 'restic-password'
HEX_RE = re.compile(r'[0-9a-f]{8,64}')
DEFAULTS = {'version': 1, 'engine': 'rsync', 'enabled': False, 'target': None, 'sources': ['~'], 'excludes': DEFAULT_EXCLUDES, 'schedule': 'daily',
            'keep': {'hourly': 24, 'daily': 14, 'weekly': 8, 'monthly': 12}, 'minBattery': 30, 'system': False}


class BackupError(Exception):
    pass


def now():
    return datetime.datetime.now()


def host_name():
    return re.sub(r'[^A-Za-z0-9._-]', '_', socket.gethostname()) or 'computer'


# ---------------------------------------------------------------- configuration
def load_config():
    config = json.loads(json.dumps(DEFAULTS))
    try:
        stored = json.loads(CONFIG_FILE.read_text())
        if isinstance(stored, dict):
            config.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return config


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(config, indent=1, ensure_ascii=False))
    os.replace(tmp, CONFIG_FILE)


def validate_config(config):
    if config.get('engine', 'rsync') not in ENGINES:
        raise BackupError('Unknown backup engine')
    if config['schedule'] not in INTERVALS and config['schedule'] != 'manual':
        raise BackupError('Unknown schedule')
    if not isinstance(config['sources'], list) or not config['sources']:
        raise BackupError('Choose at least one folder')
    for source in config['sources']:
        path = expand(source)
        if not path.is_absolute() or '..' in path.parts:
            raise BackupError('Invalid folder: %s' % source)
    keep = config['keep']
    for key in ('hourly', 'daily', 'weekly', 'monthly'):
        if type(keep.get(key)) is not int or not 0 <= keep[key] <= 999:
            raise BackupError('Invalid retention')
    return config


def expand(source):
    return Path(os.path.expanduser(source))


# ---------------------------------------------------------------- targets
def run(*args, timeout=30, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)


def list_drives():
    """Mounted or mountable partitions that are not the system disk, plus configured network shares."""
    try:
        data = json.loads(run('lsblk', '-J', '-b', '-o', 'NAME,PATH,UUID,LABEL,FSTYPE,SIZE,MOUNTPOINT,RM,HOTPLUG,TYPE,PKNAME').stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    flat = []

    def walk(nodes):
        for node in nodes:
            flat.append(node)
            walk(node.get('children') or [])
    walk(data.get('blockdevices', []))
    hotplug = {n['name'] for n in flat if n.get('hotplug') or n.get('rm') in (True, '1', 1)}
    result = []
    for node in flat:
        if node.get('type') not in ('part', 'disk') or not node.get('fstype') or node['fstype'] in ('swap', 'crypto_LUKS', 'LVM2_member', 'iso9660', 'squashfs', 'vfat') and not node.get('hotplug'):
            continue
        mount = node.get('mountpoint') or ''
        if mount in ('/', '/boot', '/boot/efi', '/efi', '[SWAP]') or mount.startswith(('/run/archiso', '/boot')):
            continue
        parent = node.get('pkname') or node['name']
        external = node['name'] in hotplug or parent in hotplug
        if not external and not mount.startswith(('/run/media', '/media', '/mnt')):
            continue
        result.append({'kind': 'drive', 'uuid': node.get('uuid') or '', 'label': node.get('label') or node['name'], 'device': node['path'],
                       'filesystem': node['fstype'], 'size': int(node.get('size') or 0), 'mountpoint': mount, 'external': external})
    return result


def smb_mount_point(entry):
    text = re.sub(r'^(smb|cifs)://|^//', '', entry.get('address', 'share').strip(), flags=re.I)
    items = [p for p in text.split('/') if p][:2]   # same name the root helper derives: smb://host/share
    return Path('/mnt/windoesnot-backup') / re.sub(r'[^A-Za-z0-9]', '_', 'smb://' + '/'.join(items))


def resolve_target(target, mount=True):
    """Return (path, filesystem) of the backup root when the target is reachable, else raise BackupError('unavailable')."""
    if not target:
        raise BackupError('No target chosen')
    kind = target.get('kind')
    if kind == 'folder':
        path = Path(target['path'])
        if not path.is_dir():
            raise BackupError('unavailable')
        return path, filesystem_of(path)
    if kind == 'drive':
        for drive in list_drives():
            if drive['uuid'] and drive['uuid'] == target.get('uuid'):
                if not drive['mountpoint'] and mount:
                    result = run('udisksctl', 'mount', '-b', drive['device'], timeout=60)
                    match = re.search(r' at (/.+?)\.?\s*$', result.stdout)
                    if result.returncode or not match:
                        raise BackupError('unavailable')
                    drive['mountpoint'] = match[1]
                if not drive['mountpoint']:
                    raise BackupError('unavailable')
                return Path(drive['mountpoint']) / target.get('folder', ''), drive['filesystem']
        raise BackupError('unavailable')
    if kind == 'smb':
        path = smb_mount_point(target)
        try:
            # Touching the automount triggers the mount (mount timeout is short, so an absent NAS fails fast).
            os.listdir(path)
            if not os.path.ismount(path):
                raise BackupError('unavailable')
        except OSError:
            raise BackupError('unavailable')
        return path / target.get('folder', ''), 'cifs'
    raise BackupError('Unknown target type')


def filesystem_of(path):
    try:
        return run('findmnt', '-no', 'FSTYPE', '-T', str(path)).stdout.strip() or 'unknown'
    except (OSError, subprocess.SubprocessError):
        return 'unknown'


def supports_hardlinks(root, filesystem):
    if filesystem in HARDLINK_FS:
        return True
    if filesystem in ('exfat', 'vfat', 'msdos'):
        return False
    probe = root / ('.link-probe-%d' % os.getpid())
    try:
        probe.write_text('x')
        os.link(probe, str(probe) + '.l')
        return True
    except OSError:
        return False
    finally:
        for name in (probe, Path(str(probe) + '.l')):
            try:
                name.unlink()
            except OSError:
                pass


def set_root(base):
    return Path(base) / SET_DIR / host_name()


# ---------------------------------------------------------------- snapshots
def list_snapshots(base):
    root = set_root(base)
    snaps = root / 'snapshots'
    result = []
    if snaps.is_dir():
        for entry in sorted(snaps.iterdir(), reverse=True):
            if STAMP_RE.fullmatch(entry.name) and entry.is_dir():
                result.append({'id': entry.name, 'time': stamp_iso(entry.name), 'kind': 'full', 'path': str(entry)})
    versions = root / 'versions'
    if (root / 'current').is_dir():
        result.insert(0, {'id': 'current', 'time': datetime.datetime.fromtimestamp((root / 'current').stat().st_mtime).isoformat(timespec='seconds'),
                          'kind': 'mirror', 'path': str(root / 'current')})
    if versions.is_dir():
        for entry in sorted(versions.iterdir(), reverse=True):
            if STAMP_RE.fullmatch(entry.name) and entry.is_dir():
                result.append({'id': 'v-' + entry.name, 'time': stamp_iso(entry.name), 'kind': 'versions', 'path': str(entry)})
    return result


def stamp_iso(name):
    return datetime.datetime.strptime(name, STAMP).isoformat(timespec='seconds')


def snapshot_path(base, snapshot_id):
    for snap in list_snapshots(base):
        if snap['id'] == snapshot_id:
            return Path(snap['path'])
    raise BackupError('Unknown backup point')


def safe_relative(path):
    rel = Path(path.lstrip('/'))
    if '..' in rel.parts:
        raise BackupError('Invalid path')
    return rel


def browse(base, snapshot_id, rel=''):
    folder = snapshot_path(base, snapshot_id)
    folder = folder / safe_relative(rel) if rel else folder
    entries = []
    for entry in sorted(folder.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        try:
            st = entry.lstat()
        except OSError:
            continue
        entries.append({'name': entry.name, 'dir': entry.is_dir() and not entry.is_symlink(), 'size': st.st_size, 'modified': int(st.st_mtime)})
    return entries


# ---------------------------------------------------------------- status
def write_status(**fields):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    state = read_status()
    state.update(fields)
    tmp = STATUS_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state))
    os.replace(tmp, STATUS_FILE)


def read_status():
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, ValueError):
        return {'state': 'idle'}


# ---------------------------------------------------------------- backup run
def rsync_args(config, destination, link_dest=None, backup_dir=None, dry_run=False):
    args = ['rsync', '-aHAX', '--numeric-ids', '--delete', '--delete-excluded', '--info=progress2,stats2', '--no-inc-recursive', '--partial-dir=.rsync-partial']
    if link_dest:
        args.append('--link-dest=' + str(link_dest))
    if backup_dir:
        args += ['--backup', '--backup-dir=' + str(backup_dir)]
    for pattern in config['excludes']:
        args.append('--exclude=' + pattern)
    if dry_run:
        args.append('--dry-run')
    return args


def run_backup(config=None, progress=None, force=False):
    config = validate_config(config or load_config())
    if config.get('engine') == 'restic':
        return run_restic_backup(config, progress, interactive=force)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise BackupError('A backup is already running')
    try:
        base, filesystem = resolve_target(config['target'])
        if not os.access(base, os.W_OK):
            raise BackupError('The target is not writable')
        root = set_root(base)
        snaps = root / 'snapshots'
        snaps.mkdir(parents=True, exist_ok=True)
        (root / 'backup.json').write_text(json.dumps({'host': host_name(), 'user': os.environ.get('USER', ''), 'created': now().isoformat(timespec='seconds')}))
        hardlinks = supports_hardlinks(root, filesystem)
        stamp = now().strftime(STAMP)
        write_status(state='running', started=int(time.time()), percent=0, message='', error='', target=target_label(config['target']))
        for stale in snaps.glob('.*.partial'):
            shutil.rmtree(stale, ignore_errors=True)
        sources = [expand(s) for s in config['sources']]
        if hardlinks:
            previous = [s for s in sorted(snaps.iterdir()) if STAMP_RE.fullmatch(s.name)]
            partial = snaps / ('.%s.partial' % stamp)
            partial.mkdir()
            for source in sources:
                sub = partial / source_name(source)
                sub.mkdir(parents=True, exist_ok=True)
                link = previous[-1] / source_name(source) if previous and (previous[-1] / source_name(source)).is_dir() else None
                run_rsync(rsync_args(config, sub, link_dest=link) + [str(source) + '/', str(sub) + '/'], progress)
            os.replace(partial, snaps / stamp)
        else:
            current = root / 'current'
            versions = root / 'versions' / stamp
            for source in sources:
                sub = current / source_name(source)
                sub.mkdir(parents=True, exist_ok=True)
                run_rsync(rsync_args(config, sub, backup_dir=versions / source_name(source)) + ['--no-perms', '--no-owner', '--no-group', '-O']
                          + [str(source) + '/', str(sub) + '/'], progress, mirror=True)
            current.touch()
        prune(base, config['keep'])
        write_status(state='idle', last_success=int(time.time()), percent=100, message='', error='', mode='snapshots' if hardlinks else 'mirror')
        return {'ok': True, 'stamp': stamp, 'mode': 'snapshots' if hardlinks else 'mirror'}
    except BackupError as error:
        write_status(state='idle' if str(error) == 'unavailable' else 'error', error=str(error), percent=0)
        raise
    except Exception as error:
        write_status(state='error', error=str(error), percent=0)
        raise
    finally:
        lock.close()


def source_name(source):
    return 'home' if source == Path.home() else 'abs+' + str(source).strip('/').replace('/', '+')


def run_rsync(args, progress=None, mirror=False):
    process = subprocess.Popen(['nice', '-n', '10', 'ionice', '-c', '3'] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    # stderr is drained while rsync runs: thousands of "file has vanished" lines fill the pipe, rsync then blocks on writing and
    # never finishes while we wait for its stdout (found by the final test with files disappearing during a Flatpak download)
    error_lines = collections.deque(maxlen=50)
    def drain():
        for line in process.stderr:
            error_lines.append(line)
    drainer = threading.Thread(target=drain, daemon=True)
    drainer.start()
    last = ''
    for chunk in iter(lambda: process.stdout.readline(), ''):
        match = re.search(r'(\d+)%', chunk)
        if match:
            percent = int(match[1])
            if percent != last:
                last = percent
                write_status(percent=percent)
                if progress:
                    progress(percent)
    process.wait()
    drainer.join(timeout=5)
    errors = ''.join(error_lines)
    if process.returncode not in (0, 23, 24):   # 23/24: some files vanished or could not be read: still a usable point
        raise BackupError(errors.strip().splitlines()[-1] if errors.strip() else 'rsync failed (%d)' % process.returncode)
    if process.returncode in (23, 24):
        write_status(message='Some files could not be read and were skipped')


def target_label(target):
    return (target or {}).get('label') or (target or {}).get('path') or (target or {}).get('address') or ''


# ---------------------------------------------------------------- retention
def keep_set(stamps, keep, current=None):
    """GFS retention: the newest point per hour/day/week/month is kept for the configured number of each."""
    current = current or now()
    wanted = set()
    ordered = sorted(stamps, reverse=True)
    for period, fmt in (('hourly', '%Y-%m-%d %H'), ('daily', '%Y-%m-%d'), ('weekly', '%G-%V'), ('monthly', '%Y-%m')):
        seen = []
        for name in ordered:
            key = datetime.datetime.strptime(name, STAMP).strftime(fmt)
            if key not in seen:
                seen.append(key)
                if len(seen) <= keep.get(period, 0):
                    wanted.add(name)
    wanted.update(ordered[:3])   # the newest points always stay (several manual runs within one hour)
    return wanted


def prune(base, keep):
    root = set_root(base)
    snaps = root / 'snapshots'
    removed = []
    if snaps.is_dir():
        names = [s.name for s in snaps.iterdir() if STAMP_RE.fullmatch(s.name)]
        wanted = keep_set(names, keep)
        for name in names:
            if name not in wanted:
                shutil.rmtree(snaps / name, ignore_errors=True)
                removed.append(name)
    versions = root / 'versions'
    if versions.is_dir():
        names = [s.name for s in versions.iterdir() if STAMP_RE.fullmatch(s.name)]
        wanted = keep_set(names, keep)
        for name in names:
            if name not in wanted:
                shutil.rmtree(versions / name, ignore_errors=True)
                removed.append('v-' + name)
    return removed


def delete_snapshot(base, snapshot_id):
    path = snapshot_path(base, snapshot_id)
    if snapshot_id == 'current':
        raise BackupError('The latest mirror cannot be deleted')
    shutil.rmtree(path)


# ---------------------------------------------------------------- restore
def restore(base, snapshot_id, rel, destination=None, overwrite=True):
    """Copy a file or folder of a backup point back. Default destination is the original place; an existing file
    that differs is moved to the trash first, so a restore never destroys the newer version."""
    source_root = snapshot_path(base, snapshot_id)
    relative = safe_relative(rel)
    source = source_root / relative
    if not source.exists() and not source.is_symlink():
        raise BackupError('Not found in this backup point')
    parts = relative.parts
    if destination:
        target = Path(destination) / source.name
    else:
        # snapshots/<stamp>/<source name>/<path>: source name 'home' stands for the home folder
        if not parts:
            raise BackupError('Choose a file or folder')
        origin = Path.home() if parts[0] == 'home' else Path('/') / parts[0][4:].replace('+', '/')
        target = origin.joinpath(*parts[1:]) if parts[1:] else origin
    return place(source, target, overwrite)


def place(source, target, overwrite=True):
    """Copy source over target; an existing target goes to the trash first."""
    source, target = Path(source), Path(target)
    if '..' in target.parts:
        raise BackupError('Invalid destination')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if not overwrite:
            raise BackupError('exists')
        if run('gio', 'trash', str(target)).returncode:
            raise BackupError('Could not move the current version to the trash')
    if source.is_dir() and not source.is_symlink():
        result = run('rsync', '-aHAX', str(source) + '/', str(target) + '/', timeout=3600)
    else:
        result = run('rsync', '-aHAX', str(source), str(target), timeout=3600)
    if result.returncode not in (0, 23, 24):
        raise BackupError(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'restore failed')
    return str(target)


# ---------------------------------------------------------------- restic engine (encrypted, deduplicating)
# Repository: <target>/windoesnot-restic. The password lives only in CONFIG_DIR/restic-password (mode 0600) and is handed
# to restic through RESTIC_PASSWORD_FILE: never on a command line, never in a log. The recovery key (= that password) is
# returned once by create_password() so the user can write it down; losing it makes the backup unreadable.
def restic_repo(base):
    return Path(base) / RESTIC_DIR


def create_password():
    """Create the password file (0600) when missing and return the recovery key once; None if it already exists."""
    if PASSWORD_FILE.is_file():
        return None
    PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = '-'.join(secrets.token_hex(2) for _ in range(8))   # 8 groups of 4 hex characters = 128 bit
    fd = os.open(PASSWORD_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(key)
    return key


def set_password(key):
    """Use an existing recovery key (new computer, repository made elsewhere)."""
    key = (key or '').strip()
    if not key or '\n' in key:
        raise BackupError('Invalid recovery key')
    PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(PASSWORD_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(key)


def restic_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith('RESTIC_PASSWORD') and k != 'RESTIC_REPOSITORY'}
    env['RESTIC_PASSWORD_FILE'] = str(PASSWORD_FILE)
    env['RESTIC_CACHE_DIR'] = str(CACHE_DIR / 'restic')
    return env


def restic_run(base, *args, timeout=600, readonly=False):
    if not PASSWORD_FILE.is_file():
        raise BackupError('The recovery key for the encrypted backup is missing')
    if shutil.which('restic') is None:
        raise BackupError('restic is not installed')
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    argv = ['restic', '-r', str(restic_repo(base)), '--quiet'] + (['--no-lock'] if readonly else []) + list(args)
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=restic_env())
    except subprocess.TimeoutExpired:
        raise BackupError('restic timed out')
    if result.returncode:
        lines = [l for l in (result.stderr or '').strip().splitlines() if l.strip()]
        if result.returncode == 12 or 'wrong password' in (result.stderr or '').lower():   # exit code 12 only exists in newer restic
            raise BackupError('Wrong recovery key for this encrypted backup')
        raise BackupError(lines[-1] if lines else 'restic failed (%d)' % result.returncode)
    return result.stdout


def restic_initialized(base):
    return (restic_repo(base) / 'config').is_file()


def restic_init(base):
    if restic_initialized(base):
        return False
    restic_repo(base).parent.mkdir(parents=True, exist_ok=True)
    restic_run(base, 'init', timeout=300)
    return True


def check_snapshot_id(snapshot_id):
    if not isinstance(snapshot_id, str) or not HEX_RE.fullmatch(snapshot_id):
        raise BackupError('Unknown backup point')
    return snapshot_id


def restic_abs(rel):
    """Browser path ('home/Documents/a.txt', the scheme of the rsync engine) -> absolute path inside HOME; None for the top."""
    parts = safe_relative(rel or '').parts
    if not parts:
        return None
    if parts[0] != 'home':
        raise BackupError('Invalid path')
    home = Path.home()
    path = home.joinpath(*parts[1:])
    if '..' in path.parts or (path != home and home not in path.parents):
        raise BackupError('Invalid path')
    return path


def restic_backup_args(config, base):
    args = ['backup', '--json', '--host', host_name(), '--tag', 'windoesnot']
    for pattern in config['excludes']:
        args.append('--exclude=' + (pattern.rstrip('/') or pattern))
    args.append('--exclude=' + str(restic_repo(base)))
    return args + [str(expand(s)) for s in config['sources']]


def restic_forget_args(keep):
    args = ['forget', '--prune', '--group-by', 'host', '--keep-last', '3']   # newest three always stay, like the rsync engine
    for period in ('hourly', 'daily', 'weekly', 'monthly'):
        if keep.get(period):
            args += ['--keep-' + period, str(int(keep[period]))]
    return args


def run_restic_backup(config, progress=None, interactive=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise BackupError('A backup is already running')
    try:
        base, _ = resolve_target(config['target'])
        if not os.access(base, os.W_OK):
            raise BackupError('The target is not writable')
        recovery_key = None
        if not PASSWORD_FILE.is_file():
            if not interactive:   # a silent background run must not create a key nobody has seen
                raise BackupError('Open the backup settings once to create the recovery key')
            if restic_initialized(base):
                raise BackupError('This target already holds an encrypted backup: enter its recovery key first')
            recovery_key = create_password()
        write_status(state='running', started=int(time.time()), percent=0, message='', error='', target=target_label(config['target']))
        restic_init(base)
        run_restic(base, restic_backup_args(config, base), progress)
        restic_run(base, *restic_forget_args(config['keep']), timeout=6 * 3600)
        points = restic_points(base)
        write_status(state='idle', last_success=int(time.time()), percent=100, message='', error='', mode='restic',
                     points=len(points), newest=points[0]['time'] if points else '')
        result = {'ok': True, 'mode': 'restic'}
        if recovery_key:
            result['recovery_key'] = recovery_key
        return result
    except BackupError as error:
        write_status(state='idle' if str(error) == 'unavailable' else 'error', error=str(error), percent=0)
        raise
    except Exception as error:
        write_status(state='error', error=str(error), percent=0)
        raise
    finally:
        lock.close()


def run_restic(base, args, progress=None, deadline=24 * 3600):
    process = subprocess.Popen(['nice', '-n', '10', 'ionice', '-c', '3', 'restic', '-r', str(restic_repo(base))] + args,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=restic_env())
    timer = threading.Timer(deadline, process.kill)   # hard deadline for the whole run
    timer.start()
    error_lines = collections.deque(maxlen=50)
    drainer = threading.Thread(target=lambda: [error_lines.append(l) for l in process.stderr], daemon=True)
    drainer.start()
    last = -1
    try:
        for line in process.stdout:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get('message_type') == 'status':
                percent = int(float(message.get('percent_done', 0)) * 100)
                if percent != last:
                    last = percent
                    write_status(percent=percent)
                    if progress:
                        progress(percent)
        process.wait(timeout=60)
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        drainer.join(timeout=5)
    if process.returncode == 3:   # some files could not be read: the snapshot exists
        write_status(message='Some files could not be read and were skipped')
    elif process.returncode:
        errors = [l.strip() for l in error_lines if l.strip()]
        if process.returncode == 12 or any('wrong password' in l.lower() for l in errors):
            raise BackupError('Wrong recovery key for this encrypted backup')
        raise BackupError(errors[-1] if errors else 'restic failed (%d)' % process.returncode)


def restic_points(base):
    if not restic_initialized(base):
        return []
    data = json.loads(restic_run(base, 'snapshots', '--json', timeout=300, readonly=True) or '[]')
    result = []
    for snap in sorted(data, key=lambda s: s.get('time', ''), reverse=True):
        when = re.sub(r'(\.\d+)?(Z|[+-]\d\d:\d\d)$', '', snap.get('time', ''))
        result.append({'id': snap['id'], 'time': when[:19], 'kind': 'restic', 'path': ''})
    return result


def restic_browse(base, snapshot_id, rel=''):
    check_snapshot_id(snapshot_id)
    folder = restic_abs(rel)
    if folder is None:   # top level: only the home folder is offered
        return [{'name': 'home', 'dir': True, 'size': 0, 'modified': 0}]
    entries = []
    for line in restic_run(base, 'ls', '--json', snapshot_id, str(folder), timeout=600, readonly=True).splitlines():
        try:
            node = json.loads(line)
        except ValueError:
            continue
        path = node.get('path')
        if node.get('struct_type') != 'node' or not path or Path(path).parent != folder:
            continue
        try:
            modified = int(datetime.datetime.fromisoformat(node.get('mtime', '').replace('Z', '+00:00')).timestamp())
        except ValueError:
            modified = 0
        entries.append({'name': node['name'], 'dir': node.get('type') == 'dir', 'size': int(node.get('size', 0)), 'modified': modified})
    return sorted(entries, key=lambda e: (not e['dir'], e['name'].lower()))


def restic_restore(base, snapshot_id, rel, destination=None, overwrite=True):
    """Restore one file or folder: into a scratch folder first, then placed like the rsync engine does it
    (the file it replaces goes to the trash)."""
    check_snapshot_id(snapshot_id)
    path = restic_abs(rel)
    if path is None or path == Path.home():
        raise BackupError('Choose a file or folder')
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='restore-', dir=CACHE_DIR))
    try:
        restic_run(base, 'restore', snapshot_id, '--target', str(scratch), '--include', str(path), timeout=6 * 3600)
        source = scratch / str(path).lstrip('/')
        if not source.exists() and not source.is_symlink():
            raise BackupError('Not found in this backup point')
        return place(source, (Path(destination) / path.name) if destination else path, overwrite)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def restic_delete(base, snapshot_id):
    restic_run(base, 'forget', '--prune', check_snapshot_id(snapshot_id), timeout=6 * 3600)


def restic_check(base):
    restic_run(base, 'check', timeout=6 * 3600, readonly=True)
    return {'ok': True}


# Engine-neutral entry points used by the CLI: they follow config['engine'].
def engine_of(config=None):
    return (config or load_config()).get('engine', 'rsync')


def list_points(base, config=None):
    return restic_points(base) if engine_of(config) == 'restic' else list_snapshots(base)


def browse_point(base, snapshot_id, rel='', config=None):
    return restic_browse(base, snapshot_id, rel) if engine_of(config) == 'restic' else browse(base, snapshot_id, rel)


def restore_point(base, snapshot_id, rel, destination=None, overwrite=True, config=None):
    if engine_of(config) == 'restic':
        return restic_restore(base, snapshot_id, rel, destination, overwrite)
    return restore(base, snapshot_id, rel, destination, overwrite)


def delete_point(base, snapshot_id, config=None):
    return restic_delete(base, snapshot_id) if engine_of(config) == 'restic' else delete_snapshot(base, snapshot_id)


def prune_points(base, config=None):
    config = config or load_config()
    if engine_of(config) == 'restic':
        restic_run(base, *restic_forget_args(config['keep']), timeout=6 * 3600)
        return []
    return prune(base, config['keep'])


# ---------------------------------------------------------------- scheduling
def due(config, status=None, current=None):
    if not config.get('enabled') or config['schedule'] == 'manual' or not config.get('target'):
        return False
    status = status or read_status()
    last = status.get('last_success', 0)
    return (current or time.time()) - last >= INTERVALS[config['schedule']]


def on_battery_low(minimum):
    try:
        for supply in Path('/sys/class/power_supply').iterdir():
            if (supply / 'type').read_text().strip() != 'Battery':
                continue
            if (supply / 'status').read_text().strip() == 'Discharging' and int((supply / 'capacity').read_text()) < minimum:
                return True
    except (OSError, ValueError):
        pass
    return False


def daemon(interval=300, once=False):
    """Check every few minutes whether a backup is due and the target is reachable."""
    while True:
        config = load_config()
        if due(config) and not on_battery_low(config.get('minBattery', 30)):
            try:
                run_backup(config)
            except BackupError:
                pass
            except Exception:
                pass
        if once:
            return
        time.sleep(interval)


def status_report():
    config = load_config()
    status = read_status()
    available = False
    base = None
    try:
        base, _ = resolve_target(config['target'], mount=False)
        available = True
    except BackupError:
        pass
    restic = config.get('engine') == 'restic'
    points = list_snapshots(base) if available and not restic else []
    # restic: the point count is cached by the last run, so polling the status never opens the repository
    count, newest = (int(status.get('points', 0)), status.get('newest', '')) if restic else (len(points), points[0]['time'] if points else '')
    return {'config': config, 'status': status, 'available': available, 'points': count, 'systemAvailable': system_available(),
            'systemPoints': len(system_list(base)) if available else 0, 'hasKey': PASSWORD_FILE.is_file() if restic else False,
            'due': due(config, status), 'newest': newest}


# ---------------------------------------------------------------- system restore points
EXPORTER = Path('/usr/lib/windoesnot/snapshot_export.py')


def system_folder(base):
    return set_root(base) / 'system'


def system_available():
    """Only on an installed btrfs system with Snapper and the root helper."""
    return EXPORTER.is_file() and Path('/etc/snapper/configs/root').is_file() and not Path('/etc/windoesnot-image-build').exists()


def system_list(base):
    try:
        entries = json.loads((system_folder(base) / 'index.json').read_text())
        return entries if isinstance(entries, list) else []
    except (OSError, ValueError):
        return []


def system_export(base):
    """Copy a fresh system restore point (incremental when possible) to the target. Asks for authentication (pkexec)."""
    if not system_available():
        raise BackupError('System restore points are not available on this system')
    folder = system_folder(base)
    folder.mkdir(parents=True, exist_ok=True)
    write_status(state='running', message='system', percent=0)
    try:
        result = run('pkexec', str(EXPORTER), 'export', json.dumps({'dest': str(folder)}), timeout=6 * 3600)
        if result.returncode:
            try:
                message = json.loads(result.stderr.strip().splitlines()[-1]).get('error', '')
            except (ValueError, IndexError):
                message = ''
            raise BackupError(message or 'The system restore point could not be copied')
        write_status(state='idle', message='', percent=100, last_system=int(time.time()))
        return json.loads(result.stdout)
    except BackupError as error:
        write_status(state='error', error=str(error))
        raise
    finally:
        if read_status().get('state') == 'running':
            write_status(state='idle', message='')
