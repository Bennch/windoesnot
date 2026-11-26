#!/usr/bin/env python3
"""Task Manager backend: reads /proc (injectable root), no third-party modules, no shell.

Grouping: a process belongs to an application by (1) its systemd app scope in /proc/<pid>/cgroup
(`app-<launcher>-<desktop-id>-<n>.scope`, `app-<desktop-id>-<n>.scope`, `app-flatpak-<id>-<n>.scope`),
named from the matching .desktop file; otherwise (2) by the process tree: walk up while the parent has the
same user and is not init/systemd/the session; the topmost process is the application.
CPU % is the share of the whole machine (all cores = 100 %), from the delta of two samples.
"""
import os
from pathlib import Path
import pwd
import re
import signal
import time

DISK_RE = re.compile(r'^(sd[a-z]+|vd[a-z]+|xvd[a-z]+|hd[a-z]+|nvme\d+n\d+|mmcblk\d+)$')
SCOPE_RE = re.compile(r'^app-(.+?)(?:-\d+)?\.scope$')
BOUNDARY = {'systemd', 'init', 'sddm', 'login', 'sshd', 'hyprland', 'uwsm', 'dbus-daemon', 'dbus-broker-launch',
            'kthreadd', 'su', 'sudo', 'gdm', 'lightdm'}
APP_DIRS = ('/usr/share/applications', '/usr/local/share/applications', '/var/lib/flatpak/exports/share/applications')


def read(path, default=''):
    try:
        return Path(path).read_text(errors='replace')
    except OSError:
        return default


def username(uid, users=None):
    if users and uid in users:
        return users[uid]
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def parse_stat(text):
    """Return (name, state, ppid, ticks, starttime) from /proc/<pid>/stat; the name may contain spaces and ')'."""
    head, _, tail = text.rpartition(')')
    name = head.partition('(')[2]
    fields = tail.split()
    return name, fields[0], int(fields[1]), int(fields[11]) + int(fields[12]), int(fields[19])


def desktop_names(dirs=APP_DIRS, lang='en'):
    """Map desktop id (without .desktop) -> (Name, Icon)."""
    result = {}
    for directory in dirs:
        try:
            files = sorted(Path(directory).glob('*.desktop'))
        except OSError:
            continue
        for file in files:
            name = icon = localized = None
            for line in read(file).splitlines():
                if line.startswith('['):
                    if name is not None and line != '[Desktop Entry]':
                        break
                    continue
                if line.startswith('Name='): name = line[5:]
                elif line.startswith(f'Name[{lang}]='): localized = line.split('=', 1)[1]
                elif line.startswith('Icon='): icon = line[5:]
            if name or localized:
                result.setdefault(file.stem, (localized or name, icon or ''))
    return result


class Sampler:
    def __init__(self, root='/proc', uid=None, own_pid=None, clock=time.monotonic, page_size=None, users=None,
                 app_dirs=APP_DIRS, lang='en'):
        self.root = Path(root)
        self.uid = os.getuid() if uid is None else uid
        self.own_pid = os.getpid() if own_pid is None else own_pid
        self.clock = clock
        self.page = page_size or os.sysconf('SC_PAGE_SIZE')
        self.users = users
        self.apps = desktop_names(app_dirs, lang)
        self.previous = None

    # --- reading -------------------------------------------------------------------------------
    def cpu_times(self):
        """Return {'cpu': (busy, total), 'cpu0': ...} from /proc/stat."""
        result = {}
        for line in read(self.root / 'stat').splitlines():
            parts = line.split()
            if parts and parts[0].startswith('cpu'):
                values = [int(x) for x in parts[1:9]]
                idle = values[3] + values[4]
                result[parts[0]] = (sum(values) - idle, sum(values))
        return result

    def read_process(self, pid):
        base = self.root / str(pid)
        try:
            name, state, ppid, ticks, start = parse_stat((base / 'stat').read_text(errors='replace'))
        except (OSError, ValueError, IndexError):
            return None
        status = {}
        for line in read(base / 'status').splitlines():
            key, _, value = line.partition(':')
            status[key] = value.strip()
        uid = int(status.get('Uid', '0').split()[0] or 0)
        statm = read(base / 'statm').split()
        rss = int(statm[1]) * self.page if len(statm) > 1 else 0
        smaps = read(base / 'smaps_rollup')
        for line in smaps.splitlines():
            if line.startswith('Pss:'):
                rss = int(line.split()[1]) * 1024
                break
        cmd = read(base / 'cmdline').replace('\0', ' ').strip()
        kernel = pid == 2 or ppid == 2 or (statm[:1] == ['0'] and not cmd)
        return {'pid': pid, 'ppid': ppid, 'name': name, 'state': state, 'uid': uid, 'user': username(uid, self.users),
                'ticks': ticks, 'start': start, 'memory': rss, 'command': cmd or f'[{name}]', 'kernel': kernel,
                'cgroup': read(base / 'cgroup')}

    def app_scope(self, cgroup):
        for line in cgroup.splitlines():
            leaf = line.rsplit('/', 1)[-1]
            if leaf.startswith('app-') and leaf.endswith('.scope'):
                match = SCOPE_RE.match(leaf)
                if match:
                    return match.group(1)
        return None

    def group_key(self, proc, table):
        scope = self.app_scope(proc['cgroup'])
        if scope:
            return 'app:' + scope, scope
        current = proc
        for _ in range(64):
            parent = table.get(current['ppid'])
            if not parent or parent['uid'] != proc['uid'] or parent['name'].lower() in BOUNDARY or parent['kernel']:
                break
            current = parent
        return f"pid:{current['pid']}", current['name']

    # --- sampling ------------------------------------------------------------------------------
    def sample(self):
        """Take one snapshot. CPU numbers are 0 on the first call and deltas afterwards."""
        now = self.clock()
        cpu = self.cpu_times()
        procs = {}
        for entry in os.listdir(self.root):
            if entry.isdigit():
                proc = self.read_process(int(entry))
                if proc:
                    procs[proc['pid']] = proc
        previous = self.previous
        net, disk = self.io_counters()
        total_delta = cpu.get('cpu', (0, 0))[1] - previous['cpu'].get('cpu', (0, 0))[1] if previous else 0
        for pid, proc in procs.items():
            before = previous['ticks'].get((pid, proc['start'])) if previous else None
            proc['cpu'] = 100.0 * (proc['ticks'] - before) / total_delta if before is not None and total_delta > 0 else 0.0
            proc['cpu'] = max(0.0, min(100.0, proc['cpu']))
        groups = {}
        for proc in procs.values():
            key, fallback = self.group_key(proc, procs)
            group = groups.setdefault(key, {'key': key, 'name': fallback, 'icon': '', 'pids': [], 'cpu': 0.0, 'memory': 0,
                                            'user': proc['user'], 'own': proc['uid'] == self.uid})
            group['pids'].append(proc['pid'])
            group['cpu'] += proc['cpu']
            group['memory'] += proc['memory']
            proc['group'] = key
        for key, group in groups.items():
            if key.startswith('app:'):
                parts = key[4:].split('-')  # launcher prefixes ("hyprland-", "flatpak-") are dropped until a .desktop id matches
                for index in range(len(parts)):
                    found = self.apps.get('-'.join(parts[index:]))
                    if found:
                        group['name'], group['icon'] = found
                        break
            group['pids'].sort()
        system = self.system_numbers(cpu, previous, now, net, disk)
        self.previous = {'time': now, 'cpu': cpu, 'net': net, 'disk': disk,
                         'ticks': {(p['pid'], p['start']): p['ticks'] for p in procs.values()}}
        for proc in procs.values():
            del proc['cgroup']
        return {'processes': sorted(procs.values(), key=lambda p: p['pid']),
                'groups': sorted(groups.values(), key=lambda g: g['name'].lower()), 'system': system}

    def io_counters(self):
        net = [0, 0]
        for line in read(self.root / 'net/dev').splitlines()[2:]:
            name, _, rest = line.partition(':')
            fields = rest.split()
            if name.strip() != 'lo' and len(fields) >= 9:
                net[0] += int(fields[0]); net[1] += int(fields[8])
        disk = [0, 0]
        for line in read(self.root / 'diskstats').splitlines():
            fields = line.split()
            if len(fields) >= 10 and DISK_RE.match(fields[2]):
                disk[0] += int(fields[5]) * 512; disk[1] += int(fields[9]) * 512
        return net, disk

    def system_numbers(self, cpu, previous, now, net, disk):
        usage = {}
        elapsed = now - previous['time'] if previous else 0
        for key, (busy, total) in cpu.items():
            if previous and key in previous['cpu'] and total > previous['cpu'][key][1]:
                usage[key] = 100.0 * (busy - previous['cpu'][key][0]) / (total - previous['cpu'][key][1])
            else:
                usage[key] = 0.0
        def rate(new, old):
            return [max(0, a - b) / elapsed for a, b in zip(new, old)] if previous and elapsed > 0 else [0.0, 0.0]
        meminfo = {}
        for line in read(self.root / 'meminfo').splitlines():
            key, _, value = line.partition(':')
            parts = value.split()
            if parts: meminfo[key] = int(parts[0]) * 1024
        total = meminfo.get('MemTotal', 0)
        available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
        swap_total = meminfo.get('SwapTotal', 0)
        uptime = read(self.root / 'uptime').split()
        down, up = rate(net, previous['net'] if previous else net)
        rd, wr = rate(disk, previous['disk'] if previous else disk)
        return {'cpu': usage.get('cpu', 0.0), 'cores': [usage[k] for k in sorted((k for k in usage if k != 'cpu'), key=lambda k: int(k[3:]))],
                'memory_total': total, 'memory_used': total - available, 'swap_total': swap_total,
                'swap_used': swap_total - meminfo.get('SwapFree', swap_total),
                'net_down': down, 'net_up': up, 'disk_read': rd, 'disk_write': wr,
                'uptime': float(uptime[0]) if uptime else 0.0}

    # --- ending tasks --------------------------------------------------------------------------
    def check_endable(self, pid):
        """Return None if the process may be ended, otherwise a short reason code."""
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1:
            return 'protected'
        if pid == self.own_pid:
            return 'self'
        proc = self.read_process(pid)
        if not proc:
            return 'gone'
        if proc['kernel']:
            return 'kernel'
        if proc['uid'] != self.uid:
            return 'not-owner'
        return None

    def end_task(self, pid, timeout=5.0, kill=os.kill, sleep=time.sleep, start=None):
        """SIGTERM, then SIGKILL after `timeout` seconds. Returns 'ended', 'killed', or a refusal code.
        `start` (from a sample) guards against pid reuse."""
        reason = self.check_endable(pid)
        if reason:
            return reason
        if start is not None and self.read_process(pid)['start'] != start:
            return 'gone'
        def alive():
            proc = self.read_process(pid)
            return bool(proc) and proc['state'] not in ('Z', 'X') and (start is None or proc['start'] == start)
        try:
            kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return 'ended'
        except PermissionError:
            return 'not-owner'
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            if not alive():
                return 'ended'
            sleep(0.1)
        if not alive():
            return 'ended'
        if self.check_endable(pid):
            return 'gone'
        try:
            kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return 'ended'
        except PermissionError:
            return 'not-owner'
        return 'killed'
