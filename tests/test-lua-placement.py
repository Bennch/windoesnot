#!/usr/bin/env python3
"""Check the actual merged Lua rules across fresh Lua states and geometries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'desktop/config/hypr/lua/bin'))
from display_geometry import window_rules
from hypr_bridge import lua
from hypr_state import encode

RUNNER = '''
local root = arg[1]
local seen = {}
local function noop() end
hl = { config=noop, monitor=noop, workspace_rule=noop, device=noop,
       gesture=noop, curve=noop, animation=noop, layer_rule=noop }
hl.window_rule = function(rule)
    assert(not (rule.move ~= nil and rule.center ~= nil),
           "conflicting move and center effects in " .. rule.name)
    seen[rule.name] = rule
end
dofile(root .. "/init.lua")
local geometry = dofile(root .. "/geometry.lua")
local count = 0
for name, expected in pairs(geometry.rules) do
    local actual = assert(seen[name], "missing geometry rule " .. name)
    assert(actual.center == nil, "center effect was not removed: " .. name)
    assert(actual.move[1] == expected.move[1] and actual.move[2] == expected.move[2])
    assert(actual.size[1] == expected.size[1] and actual.size[2] == expected.size[2])
    count = count + 1
end
print("PLACEMENT_OK " .. count)
'''

with tempfile.TemporaryDirectory(prefix='windoesnot-placement-') as temporary:
    fixture = Path(temporary)
    source = ROOT / 'desktop/config/hypr/lua'
    for name in ('reference.lua', 'init.lua'):
        shutil.copy2(source / name, fixture / name)
    (fixture / 'bindings.lua').write_text('-- Binding registration is outside this placement test.\n')
    state = json.loads((ROOT / 'desktop/defaults/hypr-state.json').read_text())
    (fixture / 'state.lua').write_text(encode(state))
    (fixture / 'host.lua').write_text('return { rules = {["startmenu-config"] = {center=true}} }\n')
    (fixture / 'runner.lua').write_text(RUNNER)
    env = {**os.environ, 'BENNI_LUA_VERIFY': '1', 'BENNI_LUA_ISOLATED': '0'}
    cases = 0
    for width, height, scale, transform in [(1280, 720, 1, 0), (2560, 1440, 1, 0), (2560, 1440, 1.25, 0), (1920, 1080, 1, 1)]:
        for alignment in ('left', 'center'):
            for sidebar in ('left', 'hidden'):
                geometry = window_rules(dict(name='Virtual-9', width=width, height=height, scale=scale, transform=transform, reserved=[0,0,0,45]), dict(taskbarAlignment=alignment, startMenuSidebarPosition=sidebar))
                for name in ('startmenu-config', 'settings-config', 'calendar-config', 'audio-config', 'bluetooth-config', 'network-config', 'nearby-config', 'docker-config', 'ollama-config'):
                    rule = geometry['rules'][name]
                    assert rule['move'][1] + rule['size'][1] == geometry['height'] - 45, name
                (fixture / 'geometry.lua').write_text('return ' + lua(geometry) + '\n')
                result = subprocess.run(['lua', fixture / 'runner.lua', fixture], env=env, capture_output=True, text=True)
                assert result.returncode == 0, result.stderr
                assert result.stdout.strip() == 'PLACEMENT_OK 13', result.stdout
                cases += 1
    # Verify the regression test really rejects the original contradictory payload.
    patched = (fixture / 'init.lua').read_text()
    (fixture / 'init.lua').write_text(patched.replace('    if copy.move ~= nil then copy.center = nil end\n', ''))
    previous = subprocess.run(['lua', fixture / 'runner.lua', fixture], env=env, capture_output=True, text=True)
    assert previous.returncode != 0 and 'conflicting move and center effects' in previous.stderr
    print(f'PASS: {cases} fresh Lua states, all 13 shell placement rules, original regression detected')
