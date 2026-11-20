#!/usr/bin/env python3
"""windoesnot-file-manager --launch (Super+E) opens a new window by default and a plain nautilus (tab) when chosen; --open-mode stores the choice."""
import os, subprocess, tempfile
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-file-manager'
with tempfile.TemporaryDirectory() as t:
    t = Path(t); (t / 'bin').mkdir()
    stub = t / 'bin/nautilus'; stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "$STUB_OUT"\n'); stub.chmod(0o755)
    env = dict(os.environ, PATH=f'{t}/bin:' + os.environ['PATH'], XDG_CONFIG_HOME=str(t / 'cfg'), STUB_OUT=str(t / 'out'), HOME=str(t))
    run = lambda *a: subprocess.run([str(SCRIPT), *a], env=env, capture_output=True, text=True)
    assert run('--open-mode', 'get').stdout.strip() == 'window'
    run('--launch'); assert (t / 'out').read_text().strip() == '--new-window', (t / 'out').read_text()
    assert run('--open-mode', 'set', 'tab').returncode == 0 and run('--open-mode', 'get').stdout.strip() == 'tab'
    run('--launch'); assert (t / 'out').read_text().strip() == '', 'tab mode must start plain nautilus'
    assert run('--open-mode', 'set', 'bogus').returncode == 2
    run('/tmp'); assert (t / 'out').read_text().strip() == '/tmp', 'direct calls are unchanged'
print('PASS: file manager open mode (window by default, tab when chosen, stored, direct calls unchanged)')
