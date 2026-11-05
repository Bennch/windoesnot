#!/usr/bin/env python3
"""Point X11's primary RandR output at whatever monitor Hyprland considers
the main monitor, so the SDDM greeter (which puts the password field on the
X11 primary screen) asks for the login on the monitor the user picked in
Settings -> Monitors, instead of whatever the GPU driver enumerates first.

Run from Xsetup, as root, before the greeter's views are created.

Matching is done by EDID, not by connector name: Hyprland (wlroots) and
Xorg do not necessarily agree on what a given physical monitor is called
-- a GPU's proprietary X11 driver in particular may expose output names
that have nothing to do with the kernel DRM connector names wlroots uses.
The EDID is the one thing both read straight from the same monitor.

Best-effort throughout: any failure just leaves X11's primary output as
the driver picked it, which is today's (already working, if mismatched)
behavior -- never a reason to fail the login.
"""
import base64
import ctypes
import ctypes.util
import glob
import json
import pwd
import re
import subprocess
import sys
from pathlib import Path

LOG = Path('/var/log/windoesnot-sddm-primary.log')


def log(message):
    try:
        with LOG.open('a') as handle:
            handle.write(message + '\n')
    except OSError:
        pass


def last_user(state_conf=Path('/var/lib/sddm/state.conf')):
    try:
        text = state_conf.read_text()
    except OSError:
        return None
    match = re.search(r'^User=(.+)$', text, re.MULTILINE)
    return match.group(1).strip() if match else None


def home_dir(user):
    try:
        return Path(pwd.getpwnam(user).pw_dir)
    except KeyError:
        return None


def primary_monitor_name(home):
    state = home / '.config/hypr/lua/state.lua'
    try:
        first_line = state.read_text().splitlines()[0]
    except (OSError, IndexError):
        return None
    marker = '-- state-json:'
    if not first_line.startswith(marker):
        return None
    try:
        data = json.loads(base64.b64decode(first_line[len(marker):]))
    except (ValueError, TypeError):
        return None
    name = data.get('primary_monitor')
    return name if isinstance(name, str) and name else None


def state_data(home):
    state = home / '.config/hypr/lua/state.lua'
    try:
        first_line = state.read_text().splitlines()[0]
        marker = '-- state-json:'
        if not first_line.startswith(marker):
            return {}
        return json.loads(base64.b64decode(first_line[len(marker):]))
    except (OSError, IndexError, ValueError, TypeError):
        return {}


# Hyprland transform -> xrandr rotation (flipped variants 4-7 map to the same rotation).
ROTATIONS = {0: 'normal', 1: 'left', 2: 'inverted', 3: 'right'}


def layout_args(monitors, candidates, edid_of):
    """xrandr arguments that give every X11 output Hyprland's rotation and
    position, so the greeter looks like the desktop on every monitor."""
    args = []
    for mon in monitors or []:
        if not isinstance(mon, dict) or not isinstance(mon.get('output'), str):
            continue
        edid = edid_of(mon['output'])
        out = next((o for o, h in candidates.items() if edid and h and h.lower() == edid.lower()), None)
        if not out:
            continue
        try:
            rotate = ROTATIONS[int(mon.get('transform', 0)) % 4]
        except (TypeError, ValueError):
            rotate = 'normal'
        args += ['--output', out, '--rotate', rotate]
        match = re.match(r'^(-?\d+)x(-?\d+)$', str(mon.get('position', '')))
        if match and float(mon.get('scale') or 1) == 1:  # logical != pixel coords when scaled
            args += ['--pos', f'{match.group(1)}x{match.group(2)}']
    return args


def connector_edid_hex(name, drm_root='/sys/class/drm'):
    for path in glob.glob(f'{drm_root}/card*-{name}/edid'):
        try:
            raw = Path(path).read_bytes()
        except OSError:
            continue
        if raw:
            return raw.hex()
    return None


def xrandr_output_edids(verbose_output):
    """Parse `xrandr --verbose` text into {output_name: edid_hex}."""
    outputs = {}
    current = None
    collecting = False
    hexbuf = []

    def flush():
        if current is not None:
            outputs[current] = ''.join(hexbuf)

    for line in verbose_output.splitlines():
        head = re.match(r'^(\S+)\s+(connected|disconnected)', line)
        if head:
            flush()
            current = head.group(1) if head.group(2) == 'connected' else None
            hexbuf = []
            collecting = False
            continue
        if current is None:
            continue
        if re.match(r'^\s*EDID:\s*$', line):
            collecting = True
            continue
        if collecting and re.match(r'^\s*[0-9a-fA-F]+\s*$', line):
            hexbuf.append(line.strip())
            continue
        collecting = False
    flush()
    return outputs


def output_center(verbose_output, output):
    """Centre (x, y) of an xrandr output from its `WxH+X+Y` geometry."""
    for line in verbose_output.splitlines():
        head = re.match(r'^(\S+)\s+connected\s+(?:primary\s+)?(\d+)x(\d+)\+(\d+)\+(\d+)', line)
        if head and head.group(1) == output:
            w, h, x, y = (int(head.group(i)) for i in range(2, 6))
            return x + w // 2, y + h // 2
    return None


def warp_pointer(x, y):
    """Move the X11 pointer. Without a window manager the greeter's keyboard
    focus follows the pointer, so this decides which screen's login form
    receives the first keystrokes (no mouse hunt for the main monitor)."""
    lib = ctypes.util.find_library('X11')
    if not lib:
        log('set-primary-monitor: libX11 not found, cannot warp pointer')
        return
    xlib = ctypes.CDLL(lib)
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XDefaultRootWindow.restype = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    xlib.XWarpPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
                                  ctypes.c_int, ctypes.c_int]
    xlib.XFlush.argtypes = [ctypes.c_void_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = xlib.XOpenDisplay(None)
    if not display:
        log('set-primary-monitor: cannot open X display to warp pointer')
        return
    try:
        xlib.XWarpPointer(display, 0, xlib.XDefaultRootWindow(display), 0, 0, 0, 0, x, y)
        xlib.XFlush(display)
    finally:
        xlib.XCloseDisplay(display)


def main():
    user = last_user()
    if not user:
        log('set-primary-monitor: no last user in /var/lib/sddm/state.conf, skipping')
        return
    home = home_dir(user)
    if not home:
        log(f'set-primary-monitor: unknown user {user!r}, skipping')
        return
    name = primary_monitor_name(home)
    if not name:
        log(f'set-primary-monitor: no primary_monitor in {home}/.config/hypr/lua/state.lua, skipping')
        return
    edid = connector_edid_hex(name)
    if not edid:
        log(f'set-primary-monitor: no readable EDID under /sys/class/drm/card*-{name}/edid, skipping')
        return
    try:
        verbose = subprocess.run(['xrandr', '--verbose'], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        log(f'set-primary-monitor: xrandr --verbose failed: {exc}')
        return
    candidates = xrandr_output_edids(verbose)
    args = layout_args(state_data(home).get('monitors'), candidates, connector_edid_hex)
    if args:
        result = subprocess.run(['xrandr'] + args, capture_output=True, text=True)
        log(f'set-primary-monitor: xrandr {" ".join(args)} -> '
            f'{result.returncode} {result.stderr.strip()}')
    match = next((output for output, hexval in candidates.items() if hexval and hexval.lower() == edid.lower()), None)
    if not match:
        log(f'set-primary-monitor: no connected X11 output EDID matches Hyprland primary {name!r}; '
            f'seen outputs: {sorted(candidates)}')
        return
    result = subprocess.run(['xrandr', '--output', match, '--primary'], capture_output=True, text=True)
    if result.returncode:
        log(f'set-primary-monitor: xrandr --output {match} --primary failed: {result.stderr.strip()}')
    else:
        log(f'set-primary-monitor: set X11 primary output to {match} (Hyprland main monitor: {name})')
        try:
            verbose = subprocess.run(['xrandr', '--verbose'], capture_output=True, text=True, check=True).stdout
            center = output_center(verbose, match)
            if center:
                warp_pointer(*center)
                log(f'set-primary-monitor: pointer moved to {center[0]},{center[1]} on {match}')
        except Exception as exc:
            log(f'set-primary-monitor: pointer warp failed: {exc!r}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # pragma: no cover - must never block the greeter
        log(f'set-primary-monitor: unexpected error: {exc!r}')
    sys.exit(0)
