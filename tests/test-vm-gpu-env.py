#!/usr/bin/env python3
"""VM GPU detection in desktop/config/hypr/lua/init.lua.

Runs the real init.lua with fake sysfs vendor files and records the hl.env
and hl.config calls. Real-hardware vendors (Intel, AMD, NVIDIA) must not
change anything; VMware (0x15ad) gets LIBGL_ALWAYS_SOFTWARE=1; virtio
(0x1af4) keeps its dmabuf quirk.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'desktop/config/hypr/lua'

RUNNER = r'''
local root = arg[1]
local fake = {}
local rawOpen = io.open
local idx = 0
for vendor in (os.getenv("FAKE_VENDORS") or ""):gmatch("[^,]+") do
    fake["/sys/class/drm/card" .. idx .. "/device/vendor"] = vendor
    idx = idx + 1
end
io.open = function(path, mode)
    if fake[path] then
        return {read = function() return fake[path] end, close = function() end}
    end
    if path:match("^/sys/class/drm/") then return nil end
    return rawOpen(path, mode)
end
local envs, configs, monitors = {}, {}, {}
local noop = function() end
hl = {
    config = function(options) for k, v in pairs(options) do configs[k] = v end end,
    monitor = noop, workspace_rule = noop, device = noop, gesture = noop,
    curve = noop, animation = noop, layer_rule = noop, window_rule = noop,
    permission = noop, on = noop, exec_cmd = noop,
    env = function(name, value) envs[#envs + 1] = name .. "=" .. tostring(value) end,
    plugin = {load = noop},
}
dofile(root .. "/init.lua")
local out = {env = envs, quirk = configs["quirks.skip_non_kms_dmabuf_formats"]}
local json = {}
json[#json + 1] = "{\"env\":["
for i, e in ipairs(out.env) do json[#json + 1] = (i > 1 and "," or "") .. "\"" .. e .. "\"" end
json[#json + 1] = "],\"quirk\":" .. (out.quirk == nil and "null" or tostring(out.quirk)) .. "}"
io.write(table.concat(json))
'''

CASES = {
    'intel-amd-nvidia-real-hardware': (['0x8086', '0x1002', '0x10de'], [], None),
    'vmware-vmwgfx': (['0x15ad'], ['LIBGL_ALWAYS_SOFTWARE=1'], None),
    'vmware-with-second-card': (['0x15ad', '0x8086'], ['LIBGL_ALWAYS_SOFTWARE=1'], None),
    'virtio-gpu': (['0x1af4'], [], False),
    'virtualbox-not-claimed': (['0x80ee'], [], None),
    'no-drm-devices': ([], [], None),
}


def run(fixture, vendors, verify=False):
    env = {**os.environ, 'FAKE_VENDORS': ','.join(vendors)}
    env['BENNI_LUA_VERIFY'] = '1' if verify else '0'
    env['BENNI_LUA_ISOLATED'] = '0'
    result = subprocess.run(['lua', str(fixture / 'runner.lua'), str(fixture)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    got = json.loads(result.stdout)
    # Only the variables this change owns; the reference config sets others.
    got['env'] = [entry for entry in got['env'] if entry.startswith('LIBGL_')]
    return got


def main():
    scratch = ROOT / 'build' / 'vm-gpu-env-test-tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vm-gpu-env-', dir=scratch) as temporary:
        fixture = Path(temporary)
        for name in ('reference.lua', 'init.lua'):
            shutil.copy2(SOURCE / name, fixture / name)
        (fixture / 'bindings.lua').write_text('-- stub\n')
        state = json.loads((ROOT / 'desktop/defaults/hypr-state.json').read_text())
        sys.path.insert(0, str(ROOT / 'desktop/config/hypr/lua/bin'))
        from hypr_state import encode
        (fixture / 'state.lua').write_text(encode(state))
        (fixture / 'runner.lua').write_text(RUNNER)
        for label, (vendors, expected_env, expected_quirk) in CASES.items():
            got = run(fixture, vendors)
            assert got['env'] == expected_env, (label, got)
            assert got['quirk'] == expected_quirk, (label, got)
        # Verification entry point must not set any environment at all.
        got = run(fixture, ['0x15ad'], verify=True)
        assert got['env'] == [], got
    shutil.rmtree(scratch, ignore_errors=True)
    print(f'PASS: {len(CASES)} GPU vendor cases, verify mode silent')


if __name__ == '__main__':
    main()
