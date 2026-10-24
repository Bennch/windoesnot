#!/usr/bin/python3 -I
"""Fixed, root-owned pkexec entry point. Never executes caller-supplied commands."""
import json
import configparser
import os
from pathlib import Path
import re
import subprocess
import sys

CONFIG = Path('/etc/snapper/configs/root')
INSTALLATION = Path('/var/lib/windoesnot/installation.json')
SNAP_PAC = Path('/etc/snap-pac.ini')
PRE_HOOK = Path('/usr/share/libalpm/hooks/05-snap-pac-pre.hook')
SNAPSHOT_BOOT = Path('/run/windoesnot-snapshot-boot')
OVERRIDE = Path('/etc/systemd/system/snapper-timeline.timer.d/zz-windoesnot.conf')
PERIODS = ('monthly', 'weekly', 'daily', 'hourly')
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}


def run(*args):
    return subprocess.run(args, env=ENV, text=True, capture_output=True,
                          check=True, timeout=120).stdout


def config_values():
    values = {}
    for line in CONFIG.read_text().splitlines():
        match = re.fullmatch(r'([A-Z_]+)="([^"\n]*)"\s*', line.strip())
        if match:
            values[match[1]] = match[2]
    return values


def parse_snapshots(raw):
    data = json.loads(raw)
    rows = data.get('root', data.get('snapshots', [])) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError('Unexpected Snapper JSON format')
    result = []
    for row in rows:
        number = str(row.get('number', row.get('#', ''))).rstrip('*+-')
        if number.isdecimal() and int(number) > 0:
            result.append({'id': number, 'date': str(row.get('date', '')),
                           'description': str(row.get('description', '')),
                           'type': str(row.get('type', '')),
                           'cleanup': str(row.get('cleanup', '')),
                           'preId': str(row.get('pre-number') or ''),
                           'packageChange': (row.get('userdata') or {}).get('windoesnot.package-change') == 'yes'
                               if isinstance(row.get('userdata'), dict) else 'windoesnot.package-change=yes' in str(row.get('userdata') or '')})
    by_id = {row['id']: row for row in result}
    for row in result:
        linked = by_id.get(row['preId'], {})
        row['packageChange'] = row['packageChange'] or bool(re.search(r'pacman|yay|paru|update|upgrade',
            row['description'] + ' ' + linked.get('description', ''), re.I))
    return sorted(result, key=lambda row: int(row['id']), reverse=True)


def package_snapshots_enabled():
    if not PRE_HOOK.is_file():
        return False
    config = configparser.ConfigParser(interpolation=None)
    try:
        if SNAP_PAC.is_file():
            config.read_string(SNAP_PAC.read_text())
        return config.getboolean('root', 'snapshot', fallback=True)
    except (OSError, ValueError, configparser.Error):
        return False


def snapshot_boot_mode():
    if SNAPSHOT_BOOT.exists():
        return 'overlay'
    mount = subprocess.run(['/usr/bin/findmnt', '--mountpoint', '/', '-n', '-o', 'FSTYPE,SOURCE'],
                           env=ENV, text=True, capture_output=True, timeout=10)
    fields = mount.stdout.strip().split(maxsplit=1)
    if not fields:
        return ''
    if fields[0] == 'overlay':
        return 'overlay'
    source = fields[1] if len(fields) > 1 else ''
    if '/.snapshots/' in source or '/.refind-btrfs/' in source or '/@rw-snapshots/' in source:
        return 'snapshot'
    return ''


def enabled(unit):
    return subprocess.run(['/usr/bin/systemctl', 'is-enabled', '--quiet', unit],
                          env=ENV, capture_output=True).returncode == 0


def boot_status():
    try:
        data = json.loads(INSTALLATION.read_text())
        if type(data) is not dict or data.get('schema_version') != 1 or data.get('filesystem') != 'btrfs':
            return {'loader': '', 'configured': False}
        loader = data.get('bootloader', '')
    except (OSError, ValueError):
        return {'loader': '', 'configured': False}
    if loader == 'grub':
        configured = Path('/etc/grub.d/41_snapshots-btrfs').is_file() and Path('/usr/lib/windoesnot/snapshot-overlay').is_file() and (
            enabled('grub-btrfsd.service') or enabled('grub-btrfs-snapper.path'))
    elif loader == 'limine':
        configured = Path('/etc/limine-snapper-sync.conf').is_file() and enabled('limine-snapper-sync.service')
    elif loader == 'refind':
        configured = Path('/boot/EFI/refind/windoesnot-linux.conf').is_file() and enabled('refind-btrfs.service')
    else:
        configured = False
    return {'loader': loader if loader in ('grub', 'limine', 'refind', 'systemd-boot') else '',
            'configured': configured}


def status():
    if Path('/etc/windoesnot-image-build').exists():
        return {'ready': False, 'live': True}
    mode = snapshot_boot_mode()
    if mode:
        return {'ready': False, 'live': False, 'snapshotBoot': True, 'snapshotMode': mode}
    if not CONFIG.is_file() or not Path('/usr/bin/snapper').is_file():
        return {'ready': False, 'live': False}
    values = config_values()
    schedule = {}
    for period in PERIODS:
        value = values.get('TIMELINE_LIMIT_' + period.upper(), '0')
        # Snapper accepts min-max ranges. Preserve them until explicitly edited.
        schedule[period] = value
    return {'ready': True, 'live': False, 'snapshotBoot': False, 'boot': boot_status(),
            'packageSnapshots': package_snapshots_enabled(),
            'numberLimit': values.get('NUMBER_LIMIT', ''),
            'importantLimit': values.get('NUMBER_LIMIT_IMPORTANT', ''),
            'snapshots': parse_snapshots(run('/usr/bin/snapper', '--no-dbus', '--jsonout',
                '--iso', '-c', 'root', 'list', '--columns', 'number,type,pre-number,date,description,cleanup,userdata')),
            'schedule': schedule, 'timeline': values.get('TIMELINE_CREATE') == 'yes',
            'timerActive': subprocess.run(['/usr/bin/systemctl', 'is-active', '--quiet',
                'snapper-timeline.timer'], env=ENV).returncode == 0}


def validate(action, payload):
    if action in ('status', 'create'):
        if payload != {}:
            raise ValueError('This operation does not accept arguments')
    elif action == 'delete':
        if set(payload) != {'id'} or type(payload['id']) is not str or not re.fullmatch(r'[1-9][0-9]{0,9}', payload['id']):
            raise ValueError('Invalid snapshot number')
    elif action == 'schedule':
        if set(payload) != set(PERIODS):
            raise ValueError('Invalid schedule fields')
        for value in payload.values():
            if type(value) is not int or not 0 <= value <= 365:
                raise ValueError('Retention must be an integer between 0 and 365')
    else:
        raise ValueError('Unknown operation')


def apply_schedule(payload):
    old_config = CONFIG.read_bytes()
    old_override = OVERRIDE.read_bytes() if OVERRIDE.exists() else None
    timer_was_active = subprocess.run(['/usr/bin/systemctl', 'is-active', '--quiet',
        'snapper-timeline.timer'], env=ENV).returncode == 0
    enabled = any(payload.values())
    try:
        run('/usr/bin/snapper', '--no-dbus', '-c', 'root', 'set-config',
            'TIMELINE_CREATE=' + ('yes' if enabled else 'no'),
            *['TIMELINE_LIMIT_' + period.upper() + '=' + str(payload[period]) for period in PERIODS])
        # Snapper classifies hourly snapshots into retention buckets. Other configs
        # may also use this global timer; never stop it when disabling root snapshots.
        if enabled:
            OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
            OVERRIDE.write_text('[Timer]\nOnCalendar=\nOnCalendar=hourly\n')
            os.chmod(OVERRIDE, 0o644)
            run('/usr/bin/systemctl', 'daemon-reload')
            run('/usr/bin/systemctl', 'enable', '--now', 'snapper-timeline.timer', 'snapper-cleanup.timer')
            run('/usr/bin/systemctl', 'restart', 'snapper-timeline.timer')
    except Exception:
        CONFIG.write_bytes(old_config)
        if old_override is None:
            OVERRIDE.unlink(missing_ok=True)
        else:
            OVERRIDE.write_bytes(old_override)
        run('/usr/bin/systemctl', 'daemon-reload')
        if timer_was_active:
            run('/usr/bin/systemctl', 'restart', 'snapper-timeline.timer')
        raise


def main():
    if os.geteuid() != 0:
        raise PermissionError('Use the authorized pkexec entry point')
    if len(sys.argv) not in (2, 3) or len(sys.argv[-1]) > 2048:
        raise ValueError('Invalid arguments')
    action = sys.argv[1]
    payload = json.loads(sys.argv[2]) if len(sys.argv) == 3 else {}
    if type(payload) is not dict:
        raise ValueError('Arguments must be an object')
    validate(action, payload)
    if action != 'status':
        if Path('/etc/windoesnot-image-build').exists() or snapshot_boot_mode() or not CONFIG.is_file():
            raise ValueError('Snapshots are unavailable in this environment')
        if action == 'create':
            run('/usr/bin/snapper', '--no-dbus', '-c', 'root', 'create', '--description', 'manual-quickshell')
        elif action == 'delete':
            run('/usr/bin/snapper', '--no-dbus', '-c', 'root', 'delete', payload['id'])
        elif action == 'schedule':
            apply_schedule(payload)
    print(json.dumps(status()))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, PermissionError, OSError, subprocess.SubprocessError) as error:
        message = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(json.dumps({'error': message}), file=sys.stderr)
        sys.exit(1)
