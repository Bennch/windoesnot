#!/usr/bin/env python3
"""windoesnot-accessibility: choices are validated, saved and applied through Hyprland/gsettings, the magnifier steps, shaders are well formed."""
import json, os, shutil, subprocess, tempfile
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-accessibility'
with tempfile.TemporaryDirectory() as t:
    t = Path(t); bin_dir = t / 'bin'; bin_dir.mkdir(); log = t / 'calls.log'; zoom_file = t / 'zoom'; zoom_file.write_text('1.0')
    def stub(name, body):
        p = bin_dir / name; p.write_text('#!/bin/sh\n' + body); p.chmod(0o755)
    stub('windoesnot-hyprctl', f'echo "hypr $*" >> {log}\n[ "$1 $2" = "keyword cursor:zoom_factor" ] && echo "$3" > {zoom_file}\nexit 0\n')
    stub('hyprctl', f'echo "{{\\"option\\":\\"cursor:zoom_factor\\",\\"float\\":$(cat {zoom_file}),\\"set\\":true}}"\n')
    stub('gsettings', f'echo "gsettings $*" >> {log}\n[ "$1" = get ] && echo "\'Bibata\'"\nexit 0\n')
    stub('squeekboard', 'sleep 30\n')
    env = dict(os.environ, XDG_CONFIG_HOME=str(t / 'cfg'), PATH=f'{bin_dir}:' + os.environ['PATH'])
    run = lambda *a: subprocess.run([str(SCRIPT), *a], env=env, capture_output=True, text=True)
    calls = lambda: log.read_text() if log.exists() else ''
    state = json.loads(run('get').stdout)
    assert state['colorFilter'] == 'none' and state['cursorSize'] == 24 and state['textScale'] == 1.0 and state['reduceMotion'] is False and state['zoom'] == 1.0 and state['keyboardInstalled'] is True, state
    assert run('set', 'colorFilter', 'bogus').returncode == 2 and run('set', 'cursorSize', '33').returncode == 2 and run('set', 'textScale', '9').returncode == 2
    assert run('set', 'colorFilter', 'deuteranopia').returncode == 0
    shader = t / 'cfg/windoesnot/shaders/deuteranopia.frag'
    assert shader.is_file() and shader.read_text().startswith('#version 300 es') and 'fragColor' in shader.read_text()
    assert f'hypr keyword decoration:screen_shader {shader}' in calls(), calls()
    run('set', 'colorFilter', 'none'); assert 'hypr keyword decoration:screen_shader \n' in calls() or calls().rstrip().endswith('decoration:screen_shader'), calls()
    run('set', 'cursorSize', '48'); assert 'hypr setcursor Bibata 48' in calls() and 'cursor-size 48' in calls(), calls()
    run('set', 'textScale', '1.5'); assert 'text-scaling-factor 1.5' in calls()
    run('set', 'reduceMotion', 'true'); assert 'animations:enabled false' in calls()
    saved = json.loads((t / 'cfg/windoesnot/accessibility.json').read_text())
    assert saved == {'colorFilter': 'none', 'cursorSize': 48, 'textScale': 1.5, 'reduceMotion': True}, saved
    log.unlink(); assert run('apply').returncode == 0
    for needle in ('decoration:screen_shader', 'setcursor Bibata 48', 'text-scaling-factor 1.5', 'animations:enabled false'): assert needle in calls(), (needle, calls())
    fresh = dict(env, XDG_CONFIG_HOME=str(t / 'fresh')); assert subprocess.run([str(SCRIPT), 'apply'], env=fresh, capture_output=True, text=True).returncode == 0
    assert (t / 'fresh/windoesnot/accessibility.json').is_file(), 'apply writes the defaults so the desktop can watch the file'
    steps = []
    for action in ('in', 'in', 'in', 'in', 'in', 'in', 'out', 'out', 'out', 'out', 'out', 'out', 'reset'):
        steps.append(float(run('zoom', action).stdout)); 
    assert steps == [1.25, 1.5, 2.0, 3.0, 4.0, 4.0, 3.0, 2.0, 1.5, 1.25, 1.0, 1.0, 1.0], steps
    assert 'cursor:zoom_detached_camera false' in calls(), 'the view must follow the pointer so the taskbar can be reached'
    assert float(run('zoom', '2.5').stdout) == 2.5 and run('zoom', 'abc').returncode == 2
    # every shader compiles when a GLSL validator is around
    validator = shutil.which('glslangValidator')
    for name in ('grayscale', 'invert', 'contrast', 'protanopia', 'deuteranopia', 'tritanopia'):
        run('set', 'colorFilter', name); path = t / f'cfg/windoesnot/shaders/{name}.frag'
        assert path.is_file()
        if validator:
            copy = t / f'{name}.frag'; shutil.copy(path, copy)
            done = subprocess.run([validator, str(copy)], capture_output=True, text=True)
            assert done.returncode == 0, (name, done.stdout)
    assert run('keyboard', 'bogus').returncode == 2
    missing = dict(env, WINDOESNOT_OSK='definitely-not-installed')
    assert subprocess.run([str(SCRIPT), 'keyboard', 'show'], env=missing, capture_output=True, text=True).returncode == 1
print('PASS: accessibility helper (validation, saving, applying, magnifier steps, colour filter shaders%s)' % ('' if shutil.which('glslangValidator') else ', GLSL not compiled: no glslangValidator'))
