#!/usr/bin/env python3
"""windoesnot-desktop-icons toggle: signals the process named in the pid file, refuses stale pid files and other processes."""
import os, subprocess, sys, tempfile, time
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-desktop-icons'
with tempfile.TemporaryDirectory() as t:
    t = Path(t); marker = t / 'got-usr1'
    env = dict(os.environ, XDG_RUNTIME_DIR=str(t))
    run = lambda *a: subprocess.run([str(SCRIPT), *a], env=env, capture_output=True, text=True)
    assert run().returncode == 2 and run('hide').returncode == 2
    assert run('toggle').returncode == 1, 'no pid file'
    # a stand-in for hyprdesk: its command line contains "hyprdesk", it records SIGUSR1
    code = f"import signal,time,pathlib\nsignal.signal(signal.SIGUSR1, lambda *a: pathlib.Path({str(marker)!r}).write_text('x'))\nprint('ready', flush=True)\nwhile True: time.sleep(0.1)\n"
    fake = subprocess.Popen([sys.executable, '-c', code, 'hyprdesk.py'], stdout=subprocess.PIPE, text=True)
    try:
        assert fake.stdout.readline().strip() == 'ready'
        (t / 'hyprdesk.pid').write_text(f'{fake.pid}\n')
        assert run('toggle').returncode == 0
        for _ in range(30):
            if marker.exists(): break
            time.sleep(0.1)
        assert marker.exists(), 'the process did not receive SIGUSR1'
        # a pid that belongs to some other program is never signalled
        other = subprocess.Popen(['sleep', '30'])
        try:
            (t / 'hyprdesk.pid').write_text(f'{other.pid}\n')
            assert run('toggle').returncode == 1 and other.poll() is None
        finally:
            other.kill(); other.wait()
    finally:
        fake.kill(); fake.wait()
    (t / 'hyprdesk.pid').write_text('99999999\n'); assert run('toggle').returncode == 1
print('PASS: desktop icon toggle (signals hyprdesk only, stale or foreign pids refused)')
