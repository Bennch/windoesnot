#!/usr/bin/env python3
"""Tiling -> floating keeps tiled windows beside each other (each shrinks around its own centre) instead of stacking them on the monitor centre."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

script = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-transition-window-mode'
monitor = {'id': 2, 'x': 1804, 'y': 614, 'width': 2560, 'height': 1440, 'scale': 1, 'transform': 0, 'reserved': [0, 0, 0, 45]}
def client(address, x, w):
    return {'address': address, 'at': [x, 614], 'size': [w, 1395], 'floating': False, 'fullscreen': False, 'pinned': False,
            'workspace': {'id': 1}, 'class': 'app', 'monitor': 2}
clients = [client('0xa', 1804, 1270), client('0xb', 3084, 1270)]
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); log = tmp / 'dispatch.log'
    stub = tmp / 'windoesnot-hyprctl'
    stub.write_text(f'''#!/bin/sh
case "$1" in
 clients) echo '{json.dumps(clients)}';;
 monitors) echo '{json.dumps([monitor])}';;
 --batch) echo "$2" >> {log};;
 *) echo "$@" >> {log};;
esac
''')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    result = subprocess.run([sys.executable, str(script), 'floating'], env={**os.environ, 'PATH': f'{tmp}:{os.environ["PATH"]}'},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    geometry = {}
    for line in log.read_text().splitlines():
        if 'resizewindowpixel' in line:
            parts = line.split(';')
            w, h = parts[0].split('exact')[1].split(',')[0].split()
            x, y = parts[1].split('exact')[1].split(',')[0].split()
            geometry[parts[0].split('address:')[1]] = (int(x), int(y), int(w), int(h))
    assert set(geometry) == {'0xa', '0xb'}, geometry
    (ax, ay, aw, ah), (bx, by, bw, bh) = geometry['0xa'], geometry['0xb']
    assert ax + aw <= bx or bx + bw <= ax, ('the two windows must not overlap', geometry)
    assert aw < 1270 and bw < 1270, 'slightly smaller'
    assert all(1804 <= g[0] and g[0] + g[2] <= 1804 + 2560 and g[1] >= 614 and g[1] + g[3] <= 614 + 1440 for g in geometry.values()), geometry
print('PASS: tiling to floating keeps the windows beside each other')
