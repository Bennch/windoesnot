#!/usr/bin/env python3
"""New floating windows cascade instead of stacking exactly (NewWindowCascade.js, run with node)."""
import json
import subprocess
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default/NewWindowCascade.js'
script = source.read_text().replace('.pragma library', '') + '''
var usable = {x: 8, y: 45, w: 1264, h: 702}
var out = {}
out.first = cascadePosition(usable, 600, 400, [])
out.second = cascadePosition(usable, 600, 400, [{x: out.first.x, y: out.first.y}])
out.third = cascadePosition(usable, 600, 400, [out.first, out.second])
var many = [], p
for (var i = 0; i < 30; i++) { p = cascadePosition(usable, 600, 400, many); many.push(p) }
out.many = many
out.big = cascadePosition(usable, 1264, 702, [{x: 8, y: 45}])
var clients = [
  {address: "0x1", mapped: true, floating: true, monitor: 0, workspace: {id: 1}, class: "a", title: "t", at: [100, 100]},
  {address: "0x2", mapped: true, floating: true, monitor: 0, workspace: {id: 1}, class: "quickshell", title: "x", at: [0, 0]},
  {address: "0x3", mapped: true, floating: false, monitor: 0, workspace: {id: 1}, class: "b", title: "t", at: [5, 5]},
  {address: "0x4", mapped: true, floating: true, monitor: 1, workspace: {id: 1}, class: "c", title: "t", at: [7, 7]},
  {address: "0x5", mapped: true, floating: true, monitor: 0, workspace: {id: 2}, class: "d", title: "t", at: [9, 9]},
  {address: "0x6", mapped: true, floating: true, monitor: 0, workspace: {id: 1}, class: "e", title: "quickshell-popup", at: [11, 11]},
  {address: "0x7", mapped: true, floating: true, monitor: 0, workspace: {id: 1}, class: "new", title: "t", at: [13, 13]}]
out.neighbours = neighbours(clients, clients[6])
console.log(JSON.stringify(out))
'''
result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=20)
assert result.returncode == 0, result.stderr
out = json.loads(result.stdout)
cx, cy = 8 + (1264 - 600) / 2, 45 + (702 - 400) / 2
assert out['first'] == {'x': cx, 'y': cy}, out['first']
assert out['second'] == {'x': cx + 32, 'y': cy + 32}, out['second']
assert out['third'] == {'x': cx + 64, 'y': cy + 64}
assert len({(p['x'], p['y']) for p in out['many'][:9]}) == 9, 'the first nine windows (1 + 4 down + 4 up) all have their own place'
assert all(8 <= p['x'] and p['x'] + 600 <= 8 + 1264 and 45 <= p['y'] and p['y'] + 400 <= 45 + 702 for p in out['many']), 'always on the screen'
assert out['big'] == {'x': 8, 'y': 45}, 'a window as big as the screen stays where it is'
assert out['neighbours'] == [{'x': 100, 'y': 100}], out['neighbours']
print('PASS: new floating windows cascade (first centred, then +32 px, wraps, stays on screen, only real neighbours count)')
