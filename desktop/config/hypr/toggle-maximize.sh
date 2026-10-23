#!/usr/bin/env python3
# toggle-maximize.sh — Pseudo-maximize without Hyprland fullscreen state.
# Invoked by hyprbars button and on_double_click.

import json, subprocess, os, sys

# ── Check window mode from quickshell settings ───────────────────────────────
SETTINGS = os.path.expanduser('~/.config/quickshell/default/settings.txt')
window_mode = 'floating'
try:
    with open(SETTINGS) as f:
        for line in f:
            line = line.strip()
            if line.startswith('windowMode='):
                window_mode = line.split('=', 1)[1].strip()
                break
except Exception:
    pass

# In tiling mode, fall back to normal fullscreen toggle
if window_mode != 'floating':
    subprocess.run(['windoesnot-hyprctl', 'dispatch', 'fullscreen', '1'])
    sys.exit(0)

# ── Get active window ────────────────────────────────────────────────────────
aw = json.loads(subprocess.check_output(['windoesnot-hyprctl', 'activewindow', '-j']))
addr   = aw['address']
saved  = f'/tmp/qs-maxstate-{addr}.json'

# ── Restore if already pseudo-maximized ─────────────────────────────────────
if os.path.exists(saved):
    with open(saved) as f:
        s = json.load(f)
    subprocess.run(['windoesnot-hyprctl', '--batch',
        f"dispatch movewindowpixel exact {s['x']} {s['y']},address:{addr}; "
        f"dispatch resizewindowpixel exact {s['w']} {s['h']},address:{addr}"])
    os.remove(saved)
    sys.exit(0)

# ── Find monitor by window position (robust against monitor-ID race) ─────────
monitors = json.loads(subprocess.check_output(['windoesnot-hyprctl', 'monitors', '-j']))
wx, wy   = aw['at'][0], aw['at'][1]
mon      = None
for m in monitors:
    scale = m['scale']
    mw = int(m['width']  / scale)
    mh = int(m['height'] / scale)
    if m['x'] <= wx < m['x'] + mw and m['y'] <= wy < m['y'] + mh:
        mon = m
        break
if mon is None:                          # fallback: match by monitor ID
    mon = next((m for m in monitors if m['id'] == aw['monitor']), monitors[0])

# ── Read gaps_out (format: "top right bottom left") ──────────────────────────
try:
    gd   = json.loads(subprocess.check_output(['windoesnot-hyprctl', 'getoption', 'general:gaps_out', '-j']))
    raw  = str(gd.get('custom', '') or gd.get('data', '') or '').strip()
    if not raw or raw in ('[[NULL]]', 'null', ''):
        raw = '8 8 8 8'
    parts = [int(x) for x in raw.split()]
except Exception:
    parts = [8]

if   len(parts) == 1: gt = gr = gb = gl = parts[0]
elif len(parts) == 2: gt = gb = parts[0]; gl = gr = parts[1]
elif len(parts) >= 4: gt, gr, gb, gl = parts[0], parts[1], parts[2], parts[3]
else:                 gt = gr = gb = gl = 8

# ── Reserved area from layer-shell panels ────────────────────────────────────
# windoesnot-hyprctl monitors -j returns reserved as [left, right, top, bottom]
res = mon.get('reserved', [0, 0, 0, 0])
if isinstance(res, list) and len(res) >= 4:
    rl, rr, rt, rb = res[0], res[1], res[2], res[3]
elif isinstance(res, dict):
    rl = res.get('left', 0); rr = res.get('right', 0)
    rt = res.get('top',  0); rb = res.get('bottom', 0)
else:
    rl = rr = rt = rb = 0

# ── Calculate usable content area ────────────────────────────────────────────
scale = mon['scale']
mw    = int(mon['width']  / scale)
mh    = int(mon['height'] / scale)
mx, my = mon['x'], mon['y']
BAR_H  = 30   # hyprbars title bar added above content

ux = mx + gl + rl
uy = my + gt + rt + BAR_H
uw = mw - gl - rl - gr - rr
uh = mh - gt - rt - gb - rb - BAR_H

# ── Save current geometry and apply ──────────────────────────────────────────
with open(saved, 'w') as f:
    json.dump({'x': aw['at'][0], 'y': aw['at'][1],
               'w': aw['size'][0], 'h': aw['size'][1]}, f)

subprocess.run(['windoesnot-hyprctl', '--batch',
    f"dispatch movewindowpixel exact {ux} {uy},address:{addr}; "
    f"dispatch resizewindowpixel exact {uw} {uh},address:{addr}"])
