#!/usr/bin/env python3
"""Task Manager backend against a fake /proc tree, plus a real short-lived child."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('taskmgr', root / 'desktop/lib/windoesnot/taskmgr.py')
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

ME = 1000
FIREFOX = '0::/user.slice/app.slice/app-hyprland-org.mozilla.firefox-77.scope\n'


def put(base, path, text):
    file = Path(base) / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text)


def proc(base, pid, name, ppid, ticks, rss_pages, uid=ME, state='S', cmd=None, cgroup='0::/user.slice/x.service\n', start=100):
    put(base, f'{pid}/stat', f'{pid} ({name}) {state} {ppid} 1 1 0 0 0 0 0 0 0 {ticks} 0 0 0 20 0 1 0 {start} 1000 {rss_pages}\n')
    put(base, f'{pid}/status', f'Name:\t{name}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n')
    put(base, f'{pid}/statm', f'{rss_pages * 2} {rss_pages} 0 0 0 0 0\n')
    command = name if cmd is None else cmd
    put(base, f'{pid}/cmdline', command.replace(' ', '\0') + '\0' if command else '')
    put(base, f'{pid}/cgroup', cgroup)


def system(base, busy, idle, rx=0, tx=0, sectors_r=0, sectors_w=0):
    put(base, 'stat', f'cpu  {busy} 0 0 {idle} 0 0 0 0 0 0\ncpu0 {busy // 2} 0 0 {idle // 2} 0 0 0 0 0 0\ncpu1 {busy // 2} 0 0 {idle // 2} 0 0 0 0 0 0\n')
    put(base, 'meminfo', 'MemTotal: 8000000 kB\nMemFree: 1000000 kB\nMemAvailable: 3000000 kB\nSwapTotal: 2000000 kB\nSwapFree: 1500000 kB\n')
    put(base, 'uptime', '1234.50 5000.00\n')
    put(base, 'net/dev', f'Inter-|a\n face |b\n    lo: 999 1 0 0 0 0 0 0 999 1 0 0 0 0 0 0\n  eth0: {rx} 1 0 0 0 0 0 0 {tx} 1 0 0 0 0 0 0\n')
    put(base, 'diskstats', f'   8 0 sda 1 0 {sectors_r} 0 1 0 {sectors_w} 0 0 0 0\n   8 1 sda1 1 0 99999 0 1 0 99999 0 0 0 0\n   7 0 loop0 1 0 99999 0 1 0 99999 0 0 0 0\n')


with tempfile.TemporaryDirectory() as tmp:
    fake = Path(tmp) / 'proc'
    apps = Path(tmp) / 'apps'
    put(apps, 'org.mozilla.firefox.desktop', '[Desktop Entry]\nName=Firefox\nName[de]=Firefox DE\nIcon=firefox\n')
    now = [0.0]
    system(fake, 100, 900)
    proc(fake, 1, 'systemd', 0, 10, 100, uid=0)
    proc(fake, 2, 'kthreadd', 0, 0, 0, uid=0, cmd='')
    proc(fake, 3, 'rcu_gp', 2, 0, 0, uid=0, cmd='')
    proc(fake, 500, 'Hyprland', 1, 50, 200)
    proc(fake, 600, 'we ird) name', 500, 100, 300, cgroup=FIREFOX)
    proc(fake, 601, 'Web Content', 600, 40, 1000, cgroup=FIREFOX)
    proc(fake, 700, 'ghostty', 500, 10, 50)
    proc(fake, 701, 'bash', 700, 1, 20)
    proc(fake, 702, 'vim', 701, 5, 30)
    proc(fake, 800, 'sshd', 1, 0, 10, uid=0)
    put(fake, 'self/stat', 'ignored')  # non-numeric entries are ignored
    s = tm.Sampler(fake, uid=ME, own_pid=500, clock=lambda: now[0], page_size=4096, users={ME: 'me', 0: 'root'}, app_dirs=[apps])
    first = s.sample()
    assert first['system']['cpu'] == 0 and all(p['cpu'] == 0 for p in first['processes'])
    by = {p['pid']: p for p in first['processes']}
    assert by[600]['name'] == 'we ird) name' and by[600]['state'] == 'S' and by[600]['user'] == 'me'
    assert by[601]['memory'] == 1000 * 4096 and by[601]['command'] == 'Web Content'
    assert by[2]['kernel'] and by[3]['kernel'] and not by[500]['kernel'] and by[1]['user'] == 'root'
    assert by[2]['command'] == '[kthreadd]'
    groups = {g['key']: g for g in first['groups']}
    app = groups['app:hyprland-org.mozilla.firefox']
    assert app['pids'] == [600, 601] and app['name'] == 'Firefox' and app['icon'] == 'firefox'
    assert app['memory'] == 1300 * 4096
    term = groups['pid:700']  # tree fallback: ghostty > bash > vim
    assert term['pids'] == [700, 701, 702] and term['name'] == 'ghostty'
    assert groups['pid:500']['pids'] == [500]  # parent systemd is a boundary

    # second sample: 1000 more jiffies in total; firefox gets +100 and +40 ticks
    now[0] = 2.0
    system(fake, 600, 1400, rx=4000, tx=2000, sectors_r=2000, sectors_w=4000)
    proc(fake, 600, 'we ird) name', 500, 200, 300, cgroup=FIREFOX)
    proc(fake, 601, 'Web Content', 600, 80, 1000, cgroup=FIREFOX)
    second = s.sample()
    by = {p['pid']: p for p in second['processes']}
    assert abs(by[600]['cpu'] - 10.0) < 1e-6 and abs(by[601]['cpu'] - 4.0) < 1e-6
    app = {g['key']: g for g in second['groups']}['app:hyprland-org.mozilla.firefox']
    assert abs(app['cpu'] - 14.0) < 1e-6
    sysn = second['system']
    assert abs(sysn['cpu'] - 50.0) < 1e-6 and len(sysn['cores']) == 2
    assert sysn['memory_total'] == 8000000 * 1024 and sysn['memory_used'] == 5000000 * 1024
    assert sysn['swap_used'] == 500000 * 1024 and sysn['uptime'] == 1234.5
    assert sysn['net_down'] == 2000 and sysn['net_up'] == 1000  # lo ignored
    assert sysn['disk_read'] == 2000 * 512 / 2 and sysn['disk_write'] == 4000 * 512 / 2  # sda only
    # a reused pid (different start time) does not inherit the old tick count
    proc(fake, 702, 'vim', 701, 99999, 30, start=555)
    third = s.sample()
    assert {p['pid']: p for p in third['processes']}[702]['cpu'] == 0.0

    # refusal cases, nothing is ever signalled
    killed = []
    kill = lambda pid, sig: killed.append((pid, sig))
    for pid, why in [(1, 'protected'), (0, 'protected'), (-5, 'protected'), (500, 'self'), (2, 'kernel'),
                     (3, 'kernel'), (800, 'not-owner'), (4242, 'gone')]:
        assert s.end_task(pid, kill=kill, sleep=lambda x: None) == why, (pid, why)
    assert s.end_task('1', kill=kill) == 'protected' and s.end_task(True, kill=kill) == 'protected'
    assert killed == []

    # mock kill: process ignores TERM, so KILL follows after the timeout
    ticks = [0.0]
    s2 = tm.Sampler(fake, uid=ME, own_pid=500, clock=lambda: ticks[0], page_size=4096)
    def sleeper(seconds): ticks[0] += seconds
    assert s2.end_task(701, timeout=1.0, kill=kill, sleep=sleeper) == 'killed'
    assert killed == [(701, signal.SIGTERM), (701, signal.SIGKILL)]
    # mock kill: TERM works (process disappears)
    killed.clear()
    def kill_gone(pid, sig):
        killed.append((pid, sig))
        for file in (fake / str(pid)).iterdir(): file.unlink()
        (fake / str(pid)).rmdir()
    assert s2.end_task(701, timeout=1.0, kill=kill_gone, sleep=sleeper) == 'ended' and killed == [(701, signal.SIGTERM)]
    # a stale start time (pid reuse) is refused without signalling
    killed.clear()
    assert s2.end_task(600, start=1, kill=kill, sleep=sleeper) == 'gone' and killed == []

# real processes, real /proc
real = tm.Sampler()
real.sample()
assert real.sample()['system']['memory_total'] > 0
assert real.end_task(1) == 'protected' and real.end_task(os.getpid()) == 'self'
child = stubborn = None
try:
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    start = real.read_process(child.pid)['start']
    assert real.end_task(child.pid, timeout=5, start=start) == 'ended'
    assert child.wait(timeout=5) == -signal.SIGTERM
    code = 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("up", flush=True); time.sleep(60)'
    stubborn = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True)
    stubborn.stdout.readline()
    assert real.end_task(stubborn.pid, timeout=0.5) == 'killed'
    assert stubborn.wait(timeout=5) == -signal.SIGKILL
finally:
    for p in (child, stubborn):
        if p and p.poll() is None:
            p.kill(); p.wait(timeout=5)
print('ok')
