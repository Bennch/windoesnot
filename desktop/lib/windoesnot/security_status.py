#!/usr/bin/env python3
"""Read-only security overview for Settings > Security. Prints JSON
{"level": ok|warn|bad|unknown, "items": [{id, state, detail}]}. Needs no root: anything
that would need it reports "unknown". detail is a short code ("code" or "code:value")
that the page translates. Touches nothing."""
import datetime
import getpass
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/')
DAY = 86400
INTERVALS = {'hourly': 3600, 'daily': DAY, 'weekly': 7 * DAY}
PACMAN_LINE = re.compile(r'^\[(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})([+-]\d{2}:?\d{2})?\]\s+\[ALPM\]\s+upgraded\s')
LOG_TAIL = 2 * 1024 * 1024


def item(ident, state, detail):
    return {'id': ident, 'state': state, 'detail': detail}


def _text(path, limit=None):
    try:
        with open(path, 'rb') as stream:
            if limit:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - limit))
            return stream.read().decode('utf-8', 'replace')
    except OSError:
        return None


def _json(path):
    text = _text(path)
    try:
        data = json.loads(text) if text is not None else None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _efivar(root, prefix):
    """Payload of the first efivar named prefix-*, without the 4-byte attributes."""
    try:
        for entry in sorted((Path(root) / 'sys/firmware/efi/efivars').glob(prefix + '-*')):
            data = entry.read_bytes()
            if len(data) > 4:
                return data[4:]
    except OSError:
        pass
    return None


def check_firewall(root):
    state = _json(Path(root) / 'var/lib/windoesnot/firewall/state.json')
    if state is not None:
        if state.get('enabled') is True:
            profile = state.get('profile')
            profile = re.sub(r'[^A-Za-z0-9._-]', '', profile)[:32] if isinstance(profile, str) else ''
            return item('firewall', 'ok', 'profile:' + profile if profile else 'on')
        return item('firewall', 'bad', 'off')
    conf = _text(Path(root) / 'etc/ufw/ufw.conf')
    enabled = re.search(r'^ENABLED=(\w+)', conf, re.M) if conf else None
    if enabled:
        on = enabled.group(1).lower() == 'yes'
        return item('firewall', 'ok' if on else 'bad', 'on' if on else 'off')
    return item('firewall', 'unknown', 'unknown')


def check_updates(root, now):
    log = _text(Path(root) / 'var/log/pacman.log', LOG_TAIL)
    last = None
    for line in (log or '').splitlines():
        match = PACMAN_LINE.match(line)
        if match:
            last = match
    if not last:
        return item('updates', 'unknown', 'unknown')
    zone = last.group(3) or '+00:00'
    if ':' not in zone:
        zone = zone[:3] + ':' + zone[3:]
    try:
        stamp = datetime.datetime.fromisoformat(last.group(1) + 'T' + last.group(2) + zone).timestamp()
    except ValueError:
        return item('updates', 'unknown', 'unknown')
    if stamp > now:
        return item('updates', 'unknown', 'unknown')
    days = int((now - stamp) // DAY)
    return item('updates', 'ok' if days <= 30 else 'warn', 'age:%d' % days)


def check_backups(home, cache, now):
    config = _json(Path(home) / '.config/windoesnot/filebackup.json')
    if not config or config.get('enabled') is not True or not config.get('target'):
        return item('backups', 'warn', 'off')
    status = _json(Path(cache) / 'windoesnot/filebackup-status.json') or {}
    if status.get('state') == 'error':
        return item('backups', 'warn', 'error')
    last = status.get('last_success')
    if not isinstance(last, (int, float)) or last <= 0:
        return item('backups', 'warn', 'never')
    days = max(0, int((now - last) // DAY))
    fresh = now - last <= INTERVALS.get(config.get('schedule'), 30 * DAY) * 2 + DAY
    return item('backups', 'ok' if fresh else 'warn', ('ok:%d' if fresh else 'stale:%d') % days)


def check_restore_points(root):
    base = Path(root) / '.snapshots'
    try:
        count = sum(1 for entry in base.iterdir() if entry.name.isdigit())
    except PermissionError:
        return item('restore_points', 'unknown', 'unknown')
    except OSError:
        return item('restore_points', 'warn', 'none')
    return item('restore_points', 'ok', 'count:%d' % count) if count else item('restore_points', 'warn', 'none')


def _is_crypt(sys_block, name, seen=None):
    """True when the block device, or anything it is stacked on (LVM, partitions), is a dm-crypt device."""
    seen = seen if seen is not None else set()
    if name in seen or len(seen) > 32:
        return False
    seen.add(name)
    uuid = _text(sys_block / name / 'dm/uuid')
    if uuid and uuid.strip().startswith('CRYPT-'):
        return True
    try:
        return any(_is_crypt(sys_block, child.name, seen) for child in (sys_block / name / 'slaves').iterdir())
    except OSError:
        return False


def check_encryption(root):
    mounts = _text(Path(root) / 'proc/self/mountinfo')
    source = None
    for line in (mounts or '').splitlines():
        parts = line.split()
        if len(parts) > 9 and parts[4] == '/' and '-' in parts[6:]:
            tail = parts[parts.index('-', 6) + 1:]
            if len(tail) >= 2:
                source = tail[1]
    if not source or not source.startswith('/dev/'):
        return item('encryption', 'unknown', 'unknown')
    name = os.path.basename(os.path.realpath(str(Path(root) / source.lstrip('/'))))
    sys_block = Path(root) / 'sys/class/block'
    if not (sys_block / name).exists():
        return item('encryption', 'unknown', 'unknown')
    return item('encryption', 'ok', 'luks') if _is_crypt(sys_block, name) else item('encryption', 'bad', 'none')


def check_secure_boot(root):
    if not (Path(root) / 'sys/firmware/efi').is_dir():
        return item('secure_boot', 'unknown', 'no-uefi')
    secure, setup = _efivar(root, 'SecureBoot'), _efivar(root, 'SetupMode')
    if secure is None or setup is None:
        return item('secure_boot', 'unknown', 'unknown')
    if setup[0] == 1:
        return item('secure_boot', 'warn', 'setup')
    return item('secure_boot', 'ok', 'on') if secure[0] == 1 else item('secure_boot', 'warn', 'off')


def check_screen_lock(root, home):
    for path in (Path(home) / '.config/hypr/hypridle.conf', Path(root) / 'etc/hypr/hypridle.conf'):
        text = _text(path)
        if text is None:
            continue
        lines = [line.split('#', 1)[0] for line in text.splitlines()]
        # Hyprlang: a listener whose on-timeout locks, or lock_cmd in the general block.
        if any(re.search(r'\bon-timeout\s*=.*lock', line) or re.search(r'\block_cmd\s*=\s*\S', line) for line in lines):
            return item('screen_lock', 'ok', 'on')
        return item('screen_lock', 'warn', 'off')
    return item('screen_lock', 'warn', 'off')


def _passwd(user):
    result = subprocess.run(['/usr/bin/passwd', '-S', user], capture_output=True, text=True, timeout=5,
                            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    return result.stdout if result.returncode == 0 else None


def check_password(user, runner=_passwd):
    try:
        out = runner(user)
    except (OSError, subprocess.SubprocessError):
        out = None
    fields = (out or '').split()
    if len(fields) < 2 or fields[0] != user:
        return item('password', 'unknown', 'unknown')
    if fields[1] == 'P':
        return item('password', 'ok', 'set')
    if fields[1] == 'NP':
        return item('password', 'bad', 'none')
    return item('password', 'unknown', 'unknown')


def overall(items):
    states = [entry['state'] for entry in items]
    for level in ('bad', 'warn', 'ok'):
        if level in states:
            return level
    return 'unknown'


def run_checks(root=ROOT, home=None, cache=None, now=None, user=None, runner=_passwd):
    home = Path(home) if home else Path.home()
    cache = Path(cache) if cache else Path(os.environ.get('XDG_CACHE_HOME') or home / '.cache')
    now = time.time() if now is None else now
    user = user or getpass.getuser()
    items = [check_firewall(root), check_updates(root, now), check_backups(home, cache, now), check_restore_points(root),
             check_encryption(root), check_secure_boot(root), check_screen_lock(root, home), check_password(user, runner)]
    return {'level': overall(items), 'items': items}


if __name__ == '__main__':
    json.dump(run_checks(), sys.stdout)
    sys.stdout.write('\n')
