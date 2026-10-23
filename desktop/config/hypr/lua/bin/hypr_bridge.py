#!/usr/bin/env python3
"""Hyprland 0.56.2 IPC adapter. No shell evaluation of dynamic arguments."""

import json
import math
import re
import subprocess
import sys


def lua(value):
    """Encode data, including non-ASCII and control characters, as Lua literals."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("Non-finite number")
        return repr(value)
    if isinstance(value, str):
        return '"' + ''.join(
            '\\' + c if c in '\\"' else f'\\{ord(c):03d}' if ord(c) < 32
            else c for c in value
        ) + '"'
    if isinstance(value, list):
        return "{" + ",".join(lua(v) for v in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"[{lua(k)}]={lua(v)}" for k, v in value.items()) + "}"
    raise ValueError(f"Unsupported data type: {type(value)}")


def scalar(value):
    value = value.strip()
    if value.lower() in ("yes", "true", "on", "yes, please :)"):
        return True
    if value.lower() in ("no", "false", "off"):
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def selector(value):
    value = value.strip()
    if value.startswith("address:"):
        if not re.fullmatch(r"address:0x[0-9a-fA-F]+", value):
            raise ValueError("Invalid window address")
    elif not re.fullmatch(r"(?:title|class|initialtitle|initialclass|pid):[^\x00\n]+", value):
        raise ValueError(f"Unsupported window selector: {value!r}")
    return value


def dispatch(name, args=""):
    """Return a typed dispatcher expression, never execute it here."""
    if name != 'exec' and any(ord(c) < 32 for c in args):
        raise ValueError('Control character in dispatcher arguments')
    args = args.strip()
    simple = {
        "exec": "exec_cmd", "exit": "exit", "global": "global",
        "layoutmsg": "layout", "togglespecialworkspace": "workspace.toggle_special",
        "bringactivetotop": "window.bring_to_top",
    }
    if name in simple:
        return f"hl.dsp.{simple[name]}({lua(args) if args else ''})"
    if name == "workspace":
        return f"hl.dsp.focus({lua({'workspace': args})})"
    if name in ("movefocus", "focusmonitor", "focuswindow"):
        field = {"movefocus": "direction", "focusmonitor": "monitor", "focuswindow": "window"}[name]
        value = {"l": "left", "r": "right", "u": "up", "d": "down"}.get(args, args) if name == "movefocus" else args
        if field == "window":
            value = selector(value)
        return f"hl.dsp.focus({lua({field: value})})"
    if name in ("killactive", "closewindow", "togglefloating", "setfloating", "settiled", "pin", "fullscreen"):
        props = {}
        if name == "fullscreen":
            if args not in ("", "0", "1"):
                raise ValueError("Unsupported fullscreen arguments")
            props['mode'] = "maximized" if args == "1" else "fullscreen"
            method = "fullscreen"
        else:
            if args:
                props['window'] = selector(args)
            method = "close" if name in ("killactive", "closewindow") else "pin" if name == "pin" else "float"
            if method == "float":
                props['action'] = {"togglefloating": "toggle", "setfloating": "set", "settiled": "unset"}[name]
        return f"hl.dsp.window.{method}({lua(props)})"
    if name in ("movetoworkspace", "movetoworkspacesilent"):
        workspace, comma, win = args.partition(',')
        props = {'workspace': workspace.strip(), 'follow': name == 'movetoworkspace'}
        if not workspace.strip():
            raise ValueError("Missing workspace")
        if comma:
            props['window'] = selector(win)
        return f"hl.dsp.window.move({lua(props)})"
    if name in ("resizewindowpixel", "movewindowpixel", "resizeactive", "moveactive", "movecursor"):
        geometry, comma, win = args.partition(',')
        exact = geometry.startswith('exact ')
        if exact:
            geometry = geometry[6:]
        coords = geometry.split()
        if len(coords) != 2 or not all(re.fullmatch(r"-?\d+(?:\.\d+)?", c) for c in coords):
            raise ValueError("Expected two numeric coordinates")
        props = dict(zip(('x', 'y'), map(scalar, coords)))
        if name == 'movecursor':
            if comma:
                raise ValueError("Cursor move cannot target a window")
            return f"hl.dsp.cursor.move({lua(props)})"
        props['relative'] = not exact
        if comma:
            props['window'] = selector(win)
        method = 'resize' if name.startswith('resize') else 'move'
        return f"hl.dsp.window.{method}({lua(props)})"
    if name == 'setprop':
        win, prop, value = args.split(maxsplit=2)
        return f"hl.dsp.window.set_prop({lua({'window': selector(win), 'prop': prop, 'value': value})})"
    if name == 'tagwindow':
        tag, win = args.split(maxsplit=1)
        return f"hl.dsp.window.tag({lua({'tag': tag, 'window': selector(win)})})"
    if name in ('movewindow', 'resizewindow') and not args:
        return 'hl.dsp.window.drag()' if name == 'movewindow' else 'hl.dsp.window.resize()'
    raise ValueError(f"Dispatcher not audited: {name} {args}")


def config_value(key, value):
    if key.endswith(('gaps_in', 'gaps_out')) and (',' in value or ' ' in value):
        parts = [int(p) for p in re.split(r'[,\s]+', value.strip())]
        if len(parts) == 2:
            parts = [parts[0], parts[1], parts[0], parts[1]]
        if len(parts) != 4:
            raise ValueError("Expected 1, 2 or 4 gaps")
        return dict(zip(('top', 'right', 'bottom', 'left'), parts))
    return scalar(value)


def keyword(args):
    text = ' '.join(args)
    key, _, value = text.partition(' ')
    match = re.fullmatch(r'windowrule\[([^\]]+)\]:([\w:]+)', key)
    if match:
        name, field = match.groups()
        if field not in ('size', 'move', 'monitor', 'decorate', 'float', 'no_focus'):
            raise ValueError(f"Window rule field not audited: {field}")
        return f"hl.window_rule({lua({'name': name, field: scalar(value)})})"
    key = key.replace(':', '.').replace('-', '_')
    if not re.fullmatch(r'[a-zA-Z_][\w.-]*', key):
        raise ValueError("Invalid option key")
    return f"hl.config({lua({key: config_value(key, value)})})"


def checked_run(args):
    result = subprocess.run(['/usr/bin/hyprctl', *args], text=True, capture_output=True)
    return result


def require_ok(result):
    output = result.stdout.strip()
    if result.returncode or not output or any(line.strip() != 'ok' for line in output.splitlines()):
        raise RuntimeError(result.stderr.strip() or output or "Empty IPC response")
    return output


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == '--':
        del args[0]
    flags = []
    while args and args[0] in ('-i', '--instance'):
        flags.extend(args[:2])
        del args[:2]
    if not args:
        raise ValueError("Missing hyprctl command")
    if args[0] == '--batch':
        # Split only legacy batch commands; individual exec commands are not used
        # in this project's batches and must not be split as shell programs.
        commands = ' '.join(args[1:]).split(';')
        for command in commands:
            if not command.strip():
                continue
            parts = command.strip().split(maxsplit=2)
            if parts[0] not in ('dispatch', 'keyword'):
                raise ValueError("Only dispatch/keyword batches are supported")
            main(flags + parts)
        return
    mutation = args[0] in ('dispatch', 'keyword')
    if mutation:
        probe = checked_run(flags + ['eval', 'return true'])
        if probe.returncode:
            raise RuntimeError(probe.stderr or probe.stdout)
        if probe.stdout.strip() == 'eval is only supported with the lua config manager':
            result = checked_run(flags + args)
        else:
            require_ok(probe)
            if args[0] == 'dispatch':
                if len(args) < 2:
                    raise ValueError("Missing dispatcher")
                code = 'return hl.dispatch(' + dispatch(args[1], ' '.join(args[2:])) + ')'
            else:
                code = keyword(args[1:])
            result = checked_run(flags + ['eval', code])
        print(require_ok(result))
    else:
        result = checked_run(flags + args)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode:
            raise RuntimeError(f"hyprctl exited {result.returncode}")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f'hypr-bridge: {error}', file=sys.stderr)
        sys.exit(1)
