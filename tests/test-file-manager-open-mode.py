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
    # start page: "This PC" replaces the home folder for the Super+E launch, never for a folder that was asked for
    assert run('--start-page', 'get').stdout.strip() == 'home'
    pacman = t / 'bin/pacman'; pacman.write_text('#!/bin/sh\nexit 1\n'); pacman.chmod(0o755)   # the patched Files is not installed
    gio = t / 'bin/gio'; gio.write_text('#!/bin/sh\necho "$*" >> "$STUB_OUT.gio"\n'); gio.chmod(0o755)
    assert run('--start-page', 'set', 'computer').returncode == 0 and run('--start-page', 'get').stdout.strip() == 'computer'
    assert run('--start-page', 'set', 'bogus').returncode == 2
    bookmarks = t / 'cfg/gtk-3.0/bookmarks'
    assert bookmarks.read_text().count('computer:///') == 1, 'one sidebar bookmark, added once'
    run('--start-page', 'set', 'computer'); assert bookmarks.read_text().count('computer:///') == 1
    assert 'metadata::nautilus-list-view-visible-columns name WinDoesNot::kind WinDoesNot::usage' in (t / 'out.gio').read_text()
    pacman.write_text('#!/bin/sh\nexit 0\n'); run('--start-page', 'set', 'computer'); assert 'computer:///' not in bookmarks.read_text(), 'no bookmark next to the built-in sidebar entry'
    pacman.write_text('#!/bin/sh\nexit 1\n'); run('--start-page', 'set', 'computer'); assert bookmarks.read_text().count('computer:///') == 1
    run('--open-mode', 'set', 'window')
    run('--launch'); assert (t / 'out').read_text().strip() == '--new-window computer:///', (t / 'out').read_text()
    run('--launch', '/tmp'); assert (t / 'out').read_text().strip() == '--new-window /tmp', (t / 'out').read_text()
    run('--open-mode', 'set', 'tab'); run('--launch'); assert (t / 'out').read_text().strip() == 'computer:///'
    run('--open-mode', 'set', 'window')
    run('--start-page', 'set', 'home'); run('--launch'); assert (t / 'out').read_text().strip() == '--new-window', 'back to the home folder'
    assert 'computer:///' not in bookmarks.read_text(), 'the bookmark goes away with the choice'
    # sidebar places: hide/show through gsettings (the stub keeps the value in a file)
    gs = t / 'bin/gsettings'
    gs.write_text('#!/bin/sh\nF="$STUB_OUT.gs"\ncase "$1" in\n list-keys) echo sidebar-hidden-places;;\n get) cat "$F" 2>/dev/null || echo "@as []";;\n set) echo "$4" > "$F";;\nesac\n'); gs.chmod(0o755)
    assert run('--sidebar', 'available').returncode == 0 and run('--sidebar', 'get').stdout.strip() == ''
    assert run('--sidebar', 'hide', 'recent').returncode == 0 and run('--sidebar', 'hide', 'network').returncode == 0
    assert run('--sidebar', 'get').stdout.split() == ['recent', 'network'], run('--sidebar', 'get').stdout
    run('--sidebar', 'hide', 'recent'); assert sorted(run('--sidebar', 'get').stdout.split()) == ['network', 'recent'], 'hiding twice does not duplicate'
    run('--sidebar', 'show', 'recent'); assert run('--sidebar', 'get').stdout.split() == ['network']
    run('--sidebar', 'show', 'network'); assert run('--sidebar', 'get').stdout.strip() == ''
    assert run('--sidebar', 'hide', 'bogus').returncode == 2
print('PASS: file manager open mode (window by default, tab when chosen, stored, direct calls unchanged)')
