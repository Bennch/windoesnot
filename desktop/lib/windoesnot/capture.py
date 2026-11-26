#!/usr/bin/env python3
"""Snipping tool and screen recorder backend: builds argv lists only, never uses a shell."""
import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

MODES = ('region', 'window', 'screen', 'monitor')
DELAYS = (0, 3, 5, 10)
MONITOR_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$')
GEOMETRY_RE = re.compile(r'^-?\d{1,6},-?\d{1,6} \d{1,6}x\d{1,6}$')
PID_NAME = 'windoesnot-capture.pid'
GERMAN = (os.environ.get('LC_ALL') or os.environ.get('LANG') or '').startswith('de')
def tr(de, en): return de if GERMAN else en


class CaptureError(Exception):
    pass


def validate_mode(mode):
    if mode not in MODES:
        raise CaptureError(f'Unknown mode: {mode!r}')
    return mode


def validate_delay(delay):
    if isinstance(delay, bool) or not isinstance(delay, int) or delay not in DELAYS:
        raise CaptureError(f'Delay must be one of {DELAYS}')
    return delay


def validate_monitor(name):
    if not isinstance(name, str) or not MONITOR_RE.fullmatch(name):
        raise CaptureError(f'Invalid monitor name: {name!r}')
    return name


def validate_geometry(geometry):
    if not isinstance(geometry, str) or not GEOMETRY_RE.fullmatch(geometry):
        raise CaptureError(f'Invalid geometry: {geometry!r}')
    width, height = (int(x) for x in geometry.split(' ')[1].split('x'))
    if width < 1 or height < 1:
        raise CaptureError('Empty geometry')
    return geometry


def timestamp(now=None):
    return (now or datetime.datetime.now()).strftime('%Y-%m-%d_%H-%M-%S')


def screenshot_dir(home=None):
    return Path(home or Path.home()) / 'Pictures/Screenshots'


def recording_dir(home=None):
    return Path(home or Path.home()) / 'Videos/Recordings'


def screenshot_path(now=None, home=None):
    return screenshot_dir(home) / f'Screenshot_{timestamp(now)}.png'


def recording_path(now=None, home=None):
    return recording_dir(home) / f'Recording_{timestamp(now)}.mp4'


def screenshot_command(mode, path, monitor=None):
    """argv for one screenshot; hyprshot for the interactive modes, grim for screens."""
    validate_mode(mode)
    path = Path(path)
    if mode == 'monitor':
        return ['grim', '-o', validate_monitor(monitor), str(path)]
    if mode == 'screen':
        return ['grim', str(path)]
    return ['hyprshot', '-m', mode, '-z', '--silent', '-o', str(path.parent), '-f', path.name]


def clipboard_command():
    return ['wl-copy', '--type', 'image/png']


def notify_command(title, body, icon, app='Capture'):
    return ['notify-send', '-a', app, '-i', str(icon), str(title), str(body)]


def record_command(path, geometry=None, audio=False):
    command = ['wf-recorder']
    if geometry is not None:
        command += ['-g', validate_geometry(geometry)]
    if audio:
        command.append('--audio')
    return command + ['-f', str(path)]


def slurp_command():
    return ['slurp', '-f', '%x,%y %wx%h']


def _notify(runner, title, body, icon):
    try:
        runner(notify_command(title, body, icon), timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def take_screenshot(mode, delay=0, clipboard=False, monitor=None, now=None, home=None,
                    runner=subprocess.run, sleep=time.sleep):
    """Run one screenshot; returns the saved Path, or None when the selection was cancelled."""
    validate_mode(mode)
    validate_delay(delay)
    if mode == 'monitor':
        validate_monitor(monitor)
    if delay:
        sleep(delay)
    path = screenshot_path(now, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = runner(screenshot_command(mode, path, monitor), timeout=120, check=False)
    if getattr(result, 'returncode', 1) != 0 and not path.is_file():
        raise CaptureError(tr('Aufnahme fehlgeschlagen.', 'Capture failed.'))
    if not path.is_file() or path.stat().st_size == 0:
        return None
    if clipboard:
        with open(path, 'rb') as image:
            runner(clipboard_command(), stdin=image, timeout=10, check=False)
    _notify(runner, tr('Bildschirmfoto gespeichert', 'Screenshot saved'), str(path), path)
    return path


def pidfile_path(runtime=None):
    return Path(runtime or os.environ.get('XDG_RUNTIME_DIR') or '/tmp') / PID_NAME


def process_alive(pid):
    try:
        cmdline = Path(f'/proc/{pid}/cmdline').read_bytes()
    except OSError:
        return False
    return Path(cmdline.split(b'\0')[0].decode(errors='replace')).name == 'wf-recorder'


def read_state(runtime=None, alive=None):
    """Return {'pid', 'file'} of a running recording, or None; stale pidfiles are removed."""
    alive = alive or process_alive
    pidfile = pidfile_path(runtime)
    try:
        data = json.loads(pidfile.read_text())
        pid = int(data['pid'])
        if pid <= 1:
            raise ValueError
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        pidfile.unlink(missing_ok=True)
        return None
    if not alive(pid):
        pidfile.unlink(missing_ok=True)
        return None
    return {'pid': pid, 'file': str(data.get('file', ''))}


def is_recording(runtime=None, alive=None):
    return read_state(runtime, alive) is not None


def select_region(runner=subprocess.run):
    """Let the user draw a rectangle; None when cancelled."""
    result = runner(slurp_command(), capture_output=True, text=True, timeout=120, check=False)
    if getattr(result, 'returncode', 1) != 0:
        return None
    return validate_geometry((result.stdout or '').strip())


def start_recording(region=False, audio=False, now=None, home=None, runtime=None,
                    runner=subprocess.run, popen=subprocess.Popen, alive=None):
    if is_recording(runtime, alive):
        raise CaptureError(tr('Es läuft bereits eine Aufnahme.', 'A recording is already running.'))
    geometry = select_region(runner) if region else None
    if region and geometry is None:
        return None
    path = recording_path(now, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    process = popen(record_command(path, geometry, audio), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True)
    pidfile_path(runtime).write_text(json.dumps({'pid': process.pid, 'file': str(path)}))
    _notify(runner, tr('Aufnahme gestartet', 'Recording started'),
            tr('Zum Beenden Win+Umschalt+R drücken.', 'Press Win+Shift+R to stop.'), 'media-record')
    return path


def stop_recording(runtime=None, alive=None, kill=os.kill, runner=subprocess.run, sleep=time.sleep, wait=5.0):
    state = read_state(runtime, alive)
    if state is None:
        return None
    alive = alive or process_alive
    kill(state['pid'], signal.SIGINT)
    remaining = wait
    while remaining > 0 and alive(state['pid']):
        sleep(0.1)
        remaining -= 0.1
    pidfile_path(runtime).unlink(missing_ok=True)
    _notify(runner, tr('Aufnahme gespeichert', 'Recording saved'), state['file'], 'media-record')
    return Path(state['file'])


def toggle_recording(region=False, audio=False, runtime=None, alive=None, **kwargs):
    """Stop a running recording, otherwise start one; returns ('stopped'|'started', path)."""
    if is_recording(runtime, alive):
        stop = {k: v for k, v in kwargs.items() if k in ('kill', 'runner', 'sleep', 'wait')}
        return 'stopped', stop_recording(runtime=runtime, alive=alive, **stop)
    start = {k: v for k, v in kwargs.items() if k in ('now', 'home', 'runner', 'popen')}
    return 'started', start_recording(region=region, audio=audio, runtime=runtime, alive=alive, **start)


USAGE = 'usage: windoesnot-capture [region|window|screen|record-toggle] [--audio] [--region] [--delay N] [--copy]'


def main(argv):
    args = list(argv)
    if not args or args[0] not in ('region', 'window', 'screen', 'record-toggle'):
        print(USAGE, file=sys.stderr)
        return 2
    action = args.pop(0)
    audio = copy = region = False
    delay = 0
    try:
        while args:
            option = args.pop(0)
            if option == '--audio': audio = True
            elif option == '--copy': copy = True
            elif option == '--region': region = True
            elif option == '--delay' and args: delay = int(args.pop(0))
            else: raise CaptureError(USAGE)
        if action == 'record-toggle':
            toggle_recording(region=region, audio=audio)
        else:
            take_screenshot(action, delay=delay, clipboard=copy)
    except (CaptureError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
