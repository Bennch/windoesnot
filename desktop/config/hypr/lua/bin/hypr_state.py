#!/usr/bin/env python3
"""Atomically persist Quickshell-controlled Lua data and check reloads."""

import argparse
import base64
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from hypr_bridge import checked_run, lua, require_ok

MARKER = '-- state-json:'


def number(value, low, high, integer=True):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError('Expected a number')
    if not low <= value <= high or (integer and value != int(value)):
        raise ValueError(f'Value outside {low}..{high}')
    return int(value) if integer else value


def boolean(value):
    if not isinstance(value, bool):
        raise ValueError('Expected a boolean')
    return value


def text(value, pattern=r'[^\x00-\x1f]{1,128}'):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('Invalid text value')
    return value


def color(value, alpha=None):
    text(value)
    if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return f'rgba({value[1:]}{alpha})' if alpha else f'rgb({value[1:]})'
    if re.fullmatch(r'(rgb\([0-9a-fA-F]{6}\)|rgba\([0-9a-fA-F]{8}\))', value):
        return value
    raise ValueError('Invalid color')


def update(state, payload):
    state = copy.deepcopy(state)
    options = state['options']
    for group, values in payload.items():
        if group == 'borders':
            options['general.col.active_border'] = color(values['active'], 'cc')
            options['general.col.inactive_border'] = color(values['inactive'], 'aa')
        elif group == 'appearance':
            radius = number(values['radius'], 0, 20)
            gaps = number(values['gaps'], 0, 100)
            options.update({'decoration.rounding': radius, 'general.gaps_in': gaps, 'general.gaps_out': {'top': 15, 'right': gaps * 2, 'bottom': gaps * 2, 'left': gaps * 2}})
        elif group == 'input':
            options.update({
                'input.sensitivity': number(values['sensitivity'], -1, 1, False),
                'input.accel_profile': text(values['accel_profile'], r'flat|adaptive'),
                'input.follow_mouse': number(values['follow_mouse'], 0, 3),
                'input.kb_layout': text(values['kb_layout'], r'[a-zA-Z0-9_,()+-]{1,128}'),
                'input.repeat_rate': number(values['repeat_rate'], 1, 200),
                'input.repeat_delay': number(values['repeat_delay'], 0, 5000),
                'input.numlock_by_default': boolean(values['numlock_by_default']),
                'input.touchpad.natural_scroll': boolean(values['natural_scroll']),
                'input.touchpad.disable_while_typing': boolean(values['disable_while_typing']),
                'input.touchpad.tap_to_click': boolean(values['tap_to_click']),
            })
        elif group == 'window_mode':
            state['window_mode'] = text(values, r'floating|tiling')
            options['general.resize_on_border'] = values == 'floating'
        elif group == 'colors':
            options['plugin.hyprbars.bar_color'] = color(values['bar'])
            options['plugin.hyprbars.col.text'] = color(values['text'])
            options['plugin.hyprbars.bar_color_inactive'] = color(values['inactive'])
            state['button_colors'] = [color(values['close']), color(values['neutral'])]
            for button in state['buttons']:
                button['fg_color'] = state['button_colors'][0 if button['icon'] == '🞨' else 1]
        elif group == 'bars':
            enabled = boolean(values['plugin_enabled'])
            height = number(values['height'], 0, 100)
            align = text(values['alignment'], r'left|right')
            options.update({
                'plugin.hyprbars.bar_height': height if enabled else 0,
                'plugin.hyprbars.bar_blur': boolean(values['blur']),
                'plugin.hyprbars.bar_text_size': number(values['text_size'], 1, 72),
                'plugin.hyprbars.bar_text_font': text(values['font']),
                'plugin.hyprbars.bar_text_align': text(values['text_align'], r'left|center|right'),
                'plugin.hyprbars.bar_title_enabled': boolean(values['title_enabled']),
                'plugin.hyprbars.bar_buttons_alignment': align,
            })
            # Padding retains the actual config values; the old UI declares a
            # different default but never persisted these fields.
            fg = state.get('button_colors', ['rgba(ffffffFF)', 'rgba(ccccccFF)'])
            bridge = 'windoesnot-hyprctl'
            buttons = []
            for key, size, icon, action in [('close', 35, '🞨', 'killactive'), ('max', 25, '◻', 'fullscreen 1'), ('min', 30, '⎯', 'movetoworkspacesilent special:minimized')]:
                if boolean(values['buttons_enabled']) and boolean(values[key]):
                    buttons.append({'bg_color': 'rgba(00000000)', 'fg_color': fg[0 if key == 'close' else 1], 'size': size, 'icon': icon, 'action': f'{bridge} dispatch {action}'})
            state['buttons'] = list(reversed(buttons)) if align == 'left' else buttons
        elif group == 'monitors':
            monitors, primary = values['monitors'], values['primary']
            if not isinstance(monitors, list) or not 1 <= len(monitors) <= 16:
                raise ValueError('Invalid monitor list')
            result = []
            names = set()
            for monitor in monitors:
                name = text(monitor['name'], r'[a-zA-Z0-9_.:-]{1,128}')
                if name in names:
                    raise ValueError('Duplicate monitor')
                names.add(name)
                disabled = boolean(monitor.get('disabled', False))
                spec = {'output': name, 'disabled': disabled}
                if not disabled:
                    width, height = (number(monitor[k], 1, 32768) for k in ('width', 'height'))
                    rate = number(monitor['refreshRate'], 1, 1000, False)
                    scale = number(monitor['scale'], 0.25, 8, False)
                    x, y = (number(monitor[k], -100000, 100000) for k in ('x', 'y'))
                    transform = number(monitor.get('transform', 0), 0, 7)
                    spec.update(mode=f'{width}x{height}@{rate:.2f}', position=f'{x}x{y}', scale=scale, transform=transform)
                    if name == primary:
                        ew, eh = ((height, width) if transform % 2 else (width, height))
                        ew, eh = round(ew / scale), round(eh / scale)
                result.append(spec)
            if not any(m['output'] == primary and not m['disabled'] for m in result):
                raise ValueError('Primary monitor must be enabled')
            state['monitors'], state['primary_monitor'] = result, primary
            positions = {
                'topbar-config': [round((ew - 853) / 2), 0],
                'mediaplayer-config': [round((ew - 853) / 2), -10],
                'startmenu-config': [round((ew - 600) / 2), eh - 700 - 45],
                'settings-config': [round((ew - 900) / 2), eh - 700 - 45],
                'calendar-config': [ew - 330, eh - 360 - 45],
                'audio-config': [ew - 330, eh - 400 - 45],
                'bluetooth-config': [ew - 330, eh - 450 - 45],
                'network-config': [ew - 330, eh - 500 - 45],
                'battery-config': [ew - 330, eh - 360 - 45],
                'nearby-config': [ew - 410, eh - 580 - 45],
                'appcontextmenu-config': [round((ew - 220) / 2), eh - 129 - 45],
                'colorpalette-config': [round((ew - 400) / 2), round((eh - 480) / 2)],
            }
            for rule, pos in positions.items():
                state['rules'].setdefault(rule, {}).update(move=pos)
            for rule in ('startmenu-config', 'settings-config', 'volume-osd-config'):
                state['rules'].setdefault(rule, {}).update(monitor=primary)
        else:
            raise ValueError(f'Unknown state group: {group}')
    return state


def encode(state):
    serialized = json.dumps(state, ensure_ascii=False, allow_nan=False).encode()
    return MARKER + base64.b64encode(serialized).decode() + '\nreturn ' + lua(state) + '\n'


def atomic_write(path, content):
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.state-', suffix='.lua', delete=False) as stream:
            temp = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        subprocess.run(['luac', '-p', str(temp)], check=True, capture_output=True)
        os.replace(temp, path)
        temp = None
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def read_state(root):
    first = (root / 'state.lua').read_text().splitlines()[0]
    return json.loads(base64.b64decode(first[len(MARKER):])) if first.startswith(MARKER) else json.loads((root / 'state.json').read_text())


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--no-reload', action='store_true')
    parser.add_argument('--print-monitors-conf', action='store_true', help='Read-only monitor data for the wallpaper editor')
    parser.add_argument('payload', nargs='?', help='JSON object; passed as one argument without a shell')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path = root / 'state.lua'
    if args.print_monitors_conf:
        monitors = read_state(root)['monitors']
        result = checked_run(['monitors', '-j'])
        if not result.returncode:
            try:
                live = json.loads(result.stdout)
                monitors = [{'output': m['name'], 'mode': f"{m['width']}x{m['height']}@{m['refreshRate']:.2f}", 'position': f"{m['x']}x{m['y']}", 'scale': m['scale'], 'transform': m.get('transform', 0)} for m in live]
            except (ValueError, KeyError, TypeError):
                pass
        for monitor in monitors:
            if not monitor.get('output'):
                continue
            if monitor.get('disabled'):
                continue
            print(f"monitor={monitor['output']},{monitor['mode']},{monitor['position']},{monitor['scale']}")
            if monitor.get('transform'):
                print(f"monitor={monitor['output']},transform,{monitor['transform']}")
        return
    if args.payload is None:
        raise ValueError('Missing state payload')
    if not args.no_reload:
        require_ok(checked_run(['eval', 'return true']))
    with (root / 'state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = path.read_text()
        state = read_state(root)
        candidate = update(state, json.loads(args.payload))
        atomic_write(path, encode(candidate))
        try:
            if not args.no_reload:
                require_ok(checked_run(['reload']))
                errors = checked_run(['configerrors'])
                if errors.returncode or errors.stdout.strip():
                    raise RuntimeError(errors.stderr or errors.stdout or 'configerrors failed')
        except (RuntimeError, OSError):
            atomic_write(path, previous)
            checked_run(['reload'])
            raise
    print('ok')


if __name__ == '__main__':
    main()
