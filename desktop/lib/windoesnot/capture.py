#!/usr/bin/env python3
"""Snipping tool and screen recorder backend: builds argv lists only, never uses a shell."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

MODES = ('region', 'window', 'screen', 'monitor')
DELAYS = (0, 3, 5, 10)
MONITOR_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$')
GEOMETRY_RE = re.compile(r'^-?\d{1,6},-?\d{1,6} \d{1,6}x\d{1,6}$')
PID_NAME = 'windoesnot-capture.pid'
OVERLAY_PID_NAME = 'windoesnot-capture-overlay.pid'
TABS = ('screenshot', 'record')
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


def record_command(path, geometry=None, audio=False, output=None):
    command = ['wf-recorder']
    if geometry is not None and output is not None:
        raise CaptureError('Use either a geometry or an output')
    if geometry is not None:
        command += ['-g', validate_geometry(geometry)]
    if output is not None:
        command += ['-o', validate_monitor(output)]
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
    try:
        started = int(data.get('started', 0))
    except (TypeError, ValueError):
        started = 0
    return {'pid': pid, 'file': str(data.get('file', '')), 'started': started}


def is_recording(runtime=None, alive=None):
    return read_state(runtime, alive) is not None


def select_region(runner=subprocess.run):
    """Let the user draw a rectangle; None when cancelled."""
    result = runner(slurp_command(), capture_output=True, text=True, timeout=120, check=False)
    if getattr(result, 'returncode', 1) != 0:
        return None
    return validate_geometry((result.stdout or '').strip())


def start_recording(region=False, audio=False, now=None, home=None, runtime=None,
                    runner=subprocess.run, popen=subprocess.Popen, alive=None, geometry=None, output=None,
                    clock=time.time):
    if is_recording(runtime, alive):
        raise CaptureError(tr('Es läuft bereits eine Aufnahme.', 'A recording is already running.'))
    if geometry is None and output is None and region:
        geometry = select_region(runner)
        if geometry is None:
            return None
    path = recording_path(now, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    process = popen(record_command(path, geometry, audio, output), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True)
    pidfile_path(runtime).write_text(json.dumps({'pid': process.pid, 'file': str(path), 'started': int(clock())}))
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
    start = {k: v for k, v in kwargs.items() if k in ('now', 'home', 'runner', 'popen', 'geometry', 'output', 'clock')}
    return 'started', start_recording(region=region, audio=audio, runtime=runtime, alive=alive, **start)

# ---------------------------------------------------------------- overlay support (freeze frame, crop, windows)

def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def monitors_from_hyprctl(data):
    """Logical monitor rectangles (scale and rotation applied) from `hyprctl monitors -j`."""
    monitors = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        if not isinstance(name, str) or not MONITOR_RE.fullmatch(name):
            continue
        try:
            scale = float(item.get('scale', 1)) or 1.0
        except (TypeError, ValueError):
            scale = 1.0
        if not 0.1 <= scale <= 10:
            scale = 1.0
        width, height = _int(item.get('width')), _int(item.get('height'))
        if _int(item.get('transform')) % 2:
            width, height = height, width
        if width < 1 or height < 1:
            continue
        workspace = item.get('activeWorkspace') if isinstance(item.get('activeWorkspace'), dict) else {}
        special = item.get('specialWorkspace') if isinstance(item.get('specialWorkspace'), dict) else {}
        monitors.append({'name': name, 'x': _int(item.get('x')), 'y': _int(item.get('y')),
                         'width': round(width / scale), 'height': round(height / scale), 'scale': scale,
                         'focused': bool(item.get('focused')),
                         'workspace': _int(workspace.get('id')), 'special': _int(special.get('id'))})
    return monitors


def windows_from_hyprctl(clients, monitors):
    """Mapped windows on visible workspaces, topmost first (floating before tiled, then most recently focused)."""
    visible = {m['workspace'] for m in monitors} | {m['special'] for m in monitors if m['special']}
    found = []
    for item in clients if isinstance(clients, list) else []:
        if not isinstance(item, dict) or not item.get('mapped') or item.get('hidden'):
            continue
        workspace = item.get('workspace') if isinstance(item.get('workspace'), dict) else {}
        at, size = item.get('at'), item.get('size')
        if _int(workspace.get('id')) not in visible or not (isinstance(at, list) and isinstance(size, list) and len(at) == 2 and len(size) == 2):
            continue
        width, height = _int(size[0]), _int(size[1])
        if width < 1 or height < 1:
            continue
        order = (0 if item.get('floating') else 1, _int(item.get('focusHistoryID'), 9999))
        found.append((order, {'address': str(item.get('address', '')), 'title': str(item.get('title', '')),
                              'class': str(item.get('class', '')), 'x': _int(at[0]), 'y': _int(at[1]),
                              'width': width, 'height': height, 'workspace': _int(workspace.get('id'))}))
    return [window for _, window in sorted(found, key=lambda pair: pair[0])]


def bounds_of(monitors):
    left = min(m['x'] for m in monitors)
    top = min(m['y'] for m in monitors)
    return {'x': left, 'y': top, 'width': max(m['x'] + m['width'] for m in monitors) - left,
            'height': max(m['y'] + m['height'] for m in monitors) - top}


def png_size(path):
    with open(path, 'rb') as image:
        head = image.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        raise CaptureError('Not a PNG file')
    return int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')


def sidecar_path(png):
    return Path(str(png) + '.json')


def _hyprctl_json(runner, what):
    result = runner(['hyprctl', '-j', what], capture_output=True, text=True, timeout=5, check=False)
    if getattr(result, 'returncode', 1) != 0:
        raise CaptureError(f'hyprctl {what} failed')
    try:
        return json.loads(result.stdout or '[]')
    except ValueError as error:
        raise CaptureError(f'hyprctl {what}: invalid JSON') from error


def take_snapshot(out, runner=subprocess.run):
    """Freeze all outputs into `out` (PNG) and return the geometry description; also written to `out`.json."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    monitors = monitors_from_hyprctl(_hyprctl_json(runner, 'monitors'))
    if not monitors:
        raise CaptureError(tr('Kein Monitor gefunden.', 'No monitor found.'))
    windows = windows_from_hyprctl(_hyprctl_json(runner, 'clients'), monitors)
    result = runner(['grim', str(out)], timeout=30, check=False)
    if getattr(result, 'returncode', 1) != 0 or not out.is_file():
        raise CaptureError(tr('Bildschirm konnte nicht aufgenommen werden.', 'Could not grab the screen.'))
    scale = max(m['scale'] for m in monitors)
    data = {'monitors': [{k: m[k] for k in ('name', 'x', 'y', 'width', 'height', 'scale', 'focused')} for m in monitors],
            'windows': windows, 'bounds': bounds_of(monitors), 'scale': scale, 'image': str(out)}
    try:
        data['pixels'] = dict(zip(('width', 'height'), png_size(out)))
    except (OSError, CaptureError):
        pass
    sidecar_path(out).write_text(json.dumps(data))
    return data


def load_snapshot(png):
    try:
        data = json.loads(sidecar_path(png).read_text())
        bounds = {k: int(data['bounds'][k]) for k in ('x', 'y', 'width', 'height')}
        scale = float(data['scale'])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CaptureError('Snapshot data missing or invalid') from error
    if bounds['width'] < 1 or bounds['height'] < 1 or not 0.1 <= scale <= 10:
        raise CaptureError('Snapshot data invalid')
    return {'bounds': bounds, 'scale': scale}


def parse_geometry(geometry):
    position, size = validate_geometry(geometry).split(' ')
    x, y = (int(v) for v in position.split(','))
    width, height = (int(v) for v in size.split('x'))
    return x, y, width, height


def crop_rect(geometry, bounds, scale):
    """Pixel rectangle (x, y, w, h) of a logical geometry inside the frozen image; clamped to the image."""
    gx, gy, gw, gh = parse_geometry(geometry)
    max_w, max_h = round(bounds['width'] * scale), round(bounds['height'] * scale)
    x0 = min(max(round((gx - bounds['x']) * scale), 0), max_w)
    y0 = min(max(round((gy - bounds['y']) * scale), 0), max_h)
    x1 = min(max(round((gx + gw - bounds['x']) * scale), 0), max_w)
    y1 = min(max(round((gy + gh - bounds['y']) * scale), 0), max_h)
    if x1 <= x0 or y1 <= y0:
        raise CaptureError(tr('Auswahl liegt außerhalb des Bildschirms.', 'Selection is outside the screen.'))
    return x0, y0, x1 - x0, y1 - y0


def imagemagick():
    return 'magick' if shutil.which('magick') else ('convert' if shutil.which('convert') else 'magick')


def crop_command(source, target, rect, tool='magick'):
    x, y, w, h = (int(v) for v in rect)
    if min(x, y) < 0 or min(w, h) < 1:
        raise CaptureError('Invalid crop rectangle')
    return [tool, str(source), '-crop', f'{w}x{h}+{x}+{y}', '+repage', str(target)]


def fresh_command(path, geometry, pointer=False):
    command = ['grim']
    if pointer:
        command.append('-c')
    return command + ['-g', validate_geometry(geometry), str(path)]


def shoot(geometry, snapshot=None, delay=0, copy=False, pointer=False, settle=0.0, now=None, home=None,
          runner=subprocess.run, sleep=time.sleep, tool=None):
    """Save one rectangle: cropped from the frozen snapshot, or (delay / pointer / no snapshot) grabbed fresh."""
    validate_geometry(geometry)
    validate_delay(delay)
    path = screenshot_path(now, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = bool(delay) or pointer or snapshot is None
    if fresh:
        if delay or settle:
            sleep(delay + settle)
        argv = fresh_command(path, geometry, pointer)
    else:
        info = load_snapshot(snapshot)
        argv = crop_command(snapshot, path, crop_rect(geometry, info['bounds'], info['scale']), tool or imagemagick())
    result = runner(argv, timeout=60, check=False)
    if getattr(result, 'returncode', 1) != 0 or not path.is_file() or path.stat().st_size == 0:
        raise CaptureError(tr('Aufnahme fehlgeschlagen.', 'Capture failed.'))
    if copy:
        with open(path, 'rb') as image:
            runner(clipboard_command(), stdin=image, timeout=10, check=False)
    _notify(runner, tr('Bildschirmfoto gespeichert', 'Screenshot saved'), str(path), path)
    return path


def runtime_dir(runtime=None):
    return Path(runtime or os.environ.get('XDG_RUNTIME_DIR') or '/tmp')


def snapshot_path(runtime=None):
    return runtime_dir(runtime) / 'windoesnot-capture-snapshot.png'


def overlay_config(home=None, share='/usr/share/windoesnot/desktop/config/quickshell/capture'):
    """Directory holding the overlay's shell.qml: the user's copy, the packaged one, or the source tree."""
    candidates = [Path(home or Path.home()) / '.config/quickshell/capture', Path(share),
                  Path(__file__).resolve().parent.parent.parent / 'config/quickshell/capture']
    for directory in candidates:
        if (directory / 'shell.qml').is_file():
            return directory
    raise CaptureError(tr('Aufnahme-Oberfläche nicht gefunden.', 'Capture overlay not found.'))


def quickshell_alive(pid):
    try:
        cmdline = Path(f'/proc/{pid}/cmdline').read_bytes()
    except OSError:
        return False
    return Path(cmdline.split(b'\0')[0].decode(errors='replace')).name in ('quickshell', 'qs')


def read_overlay_pid(runtime=None, alive=None):
    pidfile = runtime_dir(runtime) / OVERLAY_PID_NAME
    try:
        pid = int(pidfile.read_text().strip())
        if pid <= 1:
            raise ValueError
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        pidfile.unlink(missing_ok=True)
        return None
    if not (alive or quickshell_alive)(pid):
        pidfile.unlink(missing_ok=True)
        return None
    return pid


def open_overlay(tab='screenshot', runtime=None, home=None, runner=subprocess.run, popen=subprocess.Popen,
                 alive=None, rec_alive=None, kill=os.kill, sleep=time.sleep):
    """Print / Win+Shift+S / Win+Shift+R: stop a running recording, close an open overlay, or open the overlay.

    Returns 'stopped', 'closed' or 'opened'."""
    if tab not in TABS:
        raise CaptureError(f'Unknown tab: {tab!r}')
    if is_recording(runtime, rec_alive):
        stop_recording(runtime=runtime, alive=rec_alive, kill=kill, runner=runner, sleep=sleep)
        return 'stopped'
    existing = read_overlay_pid(runtime, alive)
    if existing:
        kill(existing, signal.SIGTERM)
        (runtime_dir(runtime) / OVERLAY_PID_NAME).unlink(missing_ok=True)
        return 'closed'
    config = overlay_config(home)
    png = snapshot_path(runtime)
    take_snapshot(png, runner)
    env = dict(os.environ, WINDOESNOT_CAPTURE_TAB=tab, WINDOESNOT_CAPTURE_IMAGE=str(png),
               WINDOESNOT_CAPTURE_DATA=str(sidecar_path(png)))
    process = popen(['quickshell', '--path', str(config / 'shell.qml')], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env=env)
    (runtime_dir(runtime) / OVERLAY_PID_NAME).write_text(str(process.pid))
    return 'opened'


def status_json(runtime=None, alive=None, clock=time.time):
    state = read_state(runtime, alive)
    if state is None:
        return {'recording': False}
    return {'recording': True, 'file': state['file'], 'started': state['started'], 'now': int(clock())}


USAGE = ('usage: windoesnot-capture [overlay [--tab screenshot|record] | snapshot --out PATH | '
         'shoot --geometry G [--snapshot PNG] [--delay N] [--copy] [--pointer] [--settle S] | '
         'record-start [--geometry G | --output NAME] [--audio] | record-stop | record-status | '
         'record-toggle [--region] [--audio] | region|window|screen [--delay N] [--copy]]')
FLAGS = {  # command -> {flag: takes a value}
    'overlay': {'--tab': True}, 'snapshot': {'--out': True},
    'shoot': {'--geometry': True, '--snapshot': True, '--delay': True, '--copy': False, '--pointer': False, '--settle': True},
    'record-start': {'--geometry': True, '--output': True, '--audio': False},
    'record-stop': {}, 'record-status': {},
    'record-toggle': {'--audio': False, '--region': False},
    'region': {'--delay': True, '--copy': False}, 'window': {'--delay': True, '--copy': False},
    'screen': {'--delay': True, '--copy': False, '--audio': False, '--region': False},
}


def parse_options(command, args):
    spec, options = FLAGS[command], {}
    args = list(args)
    while args:
        flag = args.pop(0)
        if flag not in spec:
            raise CaptureError(USAGE)
        if spec[flag]:
            if not args:
                raise CaptureError(USAGE)
            options[flag] = args.pop(0)
        else:
            options[flag] = True
    return options


def main(argv):
    args = list(argv)
    if not args or args[0] not in FLAGS:
        print(USAGE, file=sys.stderr)
        return 2
    command = args.pop(0)
    try:
        o = parse_options(command, args)
        if command == 'overlay':
            print(open_overlay(o.get('--tab', 'screenshot')))
        elif command == 'snapshot':
            if '--out' not in o:
                raise CaptureError(USAGE)
            print(json.dumps(take_snapshot(o['--out'])))
        elif command == 'shoot':
            if '--geometry' not in o:
                raise CaptureError(USAGE)
            try:
                settle = float(o.get('--settle', 0))
            except ValueError as error:
                raise CaptureError(USAGE) from error
            if not 0 <= settle <= 5:
                raise CaptureError(USAGE)
            print(shoot(o['--geometry'], o.get('--snapshot'), int(o.get('--delay', 0)), bool(o.get('--copy')),
                        bool(o.get('--pointer')), settle))
        elif command == 'record-start':
            print(start_recording(audio=bool(o.get('--audio')), geometry=o.get('--geometry'), output=o.get('--output')) or '')
        elif command == 'record-stop':
            print(stop_recording() or '')
        elif command == 'record-status':
            print(json.dumps(status_json()))
        elif command == 'record-toggle':
            toggle_recording(region=bool(o.get('--region')), audio=bool(o.get('--audio')))
        else:
            take_screenshot(command, delay=int(o.get('--delay', 0)), clipboard=bool(o.get('--copy')))
    except (CaptureError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
