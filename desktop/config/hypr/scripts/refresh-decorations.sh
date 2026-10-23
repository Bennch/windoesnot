#!/usr/bin/env bash
# Force hyprbars to redraw all window decorations.
# Uses resize for windows sharing a workspace, togglefloating for solo tiled windows.
windoesnot-hyprctl clients -j | python3 -c "
import json, sys, subprocess, time
from collections import Counter

clients = json.load(sys.stdin)

# Count tiled windows per workspace
ws_count = Counter(c['workspace']['id'] for c in clients if not c['floating'])

for c in clients:
    a = 'address:' + c['address']
    solo_tiled = not c['floating'] and ws_count[c['workspace']['id']] == 1

    if solo_tiled:
        subprocess.run(['windoesnot-hyprctl', 'dispatch', 'togglefloating', a], capture_output=True)
        time.sleep(0.05)
        subprocess.run(['windoesnot-hyprctl', 'dispatch', 'togglefloating', a], capture_output=True)
    else:
        subprocess.run(['windoesnot-hyprctl', 'dispatch', 'resizewindowpixel', '1 1,' + a], capture_output=True)
        subprocess.run(['windoesnot-hyprctl', '--', 'dispatch', 'resizewindowpixel', '-1 -1,' + a], capture_output=True)
"
