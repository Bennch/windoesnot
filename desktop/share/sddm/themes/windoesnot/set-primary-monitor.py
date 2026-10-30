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


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # pragma: no cover - must never block the greeter
        log(f'set-primary-monitor: unexpected error: {exc!r}')
    sys.exit(0)
