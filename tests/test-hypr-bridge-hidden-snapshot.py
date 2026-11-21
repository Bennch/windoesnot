#!/usr/bin/env python3
"""The Hyprland bridge takes a picture of a window right before it is minimized (taskbar preview of hidden windows)."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / 'desktop/config/hypr/lua/bin/hypr_bridge.py'
spec = importlib.util.spec_from_file_location('hypr_bridge_under_test', SOURCE)
bridge = importlib.util.module_from_spec(spec); spec.loader.exec_module(bridge)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); bin_dir = tmp / 'bin'; bin_dir.mkdir(); runtime = tmp / 'run'; runtime.mkdir()
    clients = [{'address': '0xabc', 'at': [10, 20], 'size': [300, 200], 'workspace': {'name': '1'}},
               {'address': '0xdef', 'at': [0, 0], 'size': [100, 100], 'workspace': {'name': 'special:minimized'}}]
    def tool(name, body):
        path = bin_dir / name; path.write_text('#!/bin/sh\n' + body); path.chmod(path.stat().st_mode | stat.S_IEXEC)
    tool('hyprctl', f"case \"$2\" in clients) echo '{json.dumps(clients)}';; activewindow) echo '{json.dumps(clients[0])}';; esac\n")
    tool('grim', 'echo "$@" > "$5.args"; : > "$5"\n')
    os.environ['PATH'] = f'{bin_dir}:{os.environ["PATH"]}'; os.environ['XDG_RUNTIME_DIR'] = str(runtime)
    folder = runtime / 'windoesnot-hidden-previews'

    bridge.snapshot_before_hide(['dispatch', 'movetoworkspacesilent', 'special:minimized,address:0xabc'])
    assert (folder / '0xabc.png').exists() and '10,20 300x200' in (folder / '0xabc.png.args').read_text()
    bridge.snapshot_before_hide(['dispatch', 'movetoworkspacesilent', 'special:minimized'])   # active window
    assert (folder / '0xabc.png').exists()
    bridge.snapshot_before_hide(['dispatch', 'movetoworkspacesilent', 'special:minimized,address:0xdef'])   # already hidden: no picture
    assert not (folder / '0xdef.png').exists()
    bridge.snapshot_before_hide(['dispatch', 'focuswindow', 'address:0xabc'])
    bridge.snapshot_before_hide(['dispatch', 'movetoworkspacesilent', '3,address:0xabc'])   # a normal workspace: nothing
    assert sorted(p.name for p in folder.glob('*.png')) == ['0xabc.png']
print('PASS: the bridge snapshots a window before it is minimized, and only then')
