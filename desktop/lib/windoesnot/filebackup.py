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
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
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
DEFAULTS = {'version': 1, 'enabled': False, 'target': None, 'sources': ['~'], 'excludes': DEFAULT_EXCLUDES, 'schedule': 'daily',
            'keep': {'hourly': 24, 'daily': 14, 'weekly': 8, 'monthly': 12}, 'minBattery': 30}


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
    errors = process.stderr.read()
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
    if ordered:
        wanted.add(ordered[0])
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
    points = list_snapshots(base) if available else []
    return {'config': config, 'status': status, 'available': available, 'points': len(points),
            'due': due(config, status), 'newest': points[0]['time'] if points else ''}
