#!/usr/bin/env python3
"""Welcome window helpers: the apps left for later with their state, and the 'show at startup' switch."""
import importlib.machinery, importlib.util, json, os, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'desktop/bin'
with tempfile.TemporaryDirectory() as t:
    t = Path(t); (t / 'bin').mkdir(); (t / 'state/windoesnot').mkdir(parents=True); home = t / 'home'; (home / '.local/share/applications').mkdir(parents=True)
    pacman = t / 'bin/pacman'; pacman.write_text('#!/bin/sh\n[ "$2" = installed-pkg ] && exit 0\nexit 1\n'); pacman.chmod(0o755)
    pending = t / 'pending.json'
    # flatpak (done / waiting), repo app, AUR app (davinci-resolve), web app with and without launcher
    pending.write_text(json.dumps({'pending': ['krita', 'inkscape', 'ollama', 'davinci-resolve', 'netflix', 'disney-plus']}))
    (t / 'state/windoesnot/pending-apps-done.json').write_text(json.dumps({'schema_version': 1, 'done': ['krita']}))
    (home / '.local/share/applications/windoesnot-webapp-netflix.desktop').write_text('[Desktop Entry]\n')
    env = dict(os.environ, HOME=str(home), XDG_STATE_HOME=str(t / 'state'), XDG_CONFIG_HOME=str(t / 'cfg'), LANG='de_DE.UTF-8',
               WINDOESNOT_PENDING=str(pending), WINDOESNOT_BASE=str(ROOT), PATH=f"{t / 'bin'}:" + os.environ['PATH'])
    out = subprocess.run([str(BIN / 'windoesnot-pending-apps'), '--status'], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    apps = {a['id']: a for a in json.loads(out.stdout)['apps']}
    assert apps['krita'] == {'id': 'krita', 'name': 'Krita', 'kind': 'flatpak', 'done': True}, apps['krita']
    assert apps['inkscape']['kind'] == 'flatpak' and apps['inkscape']['done'] is False
    assert apps['ollama']['kind'] == 'store' and apps['ollama']['done'] is False
    assert apps['davinci-resolve'] == {'id': 'davinci-resolve', 'name': 'DaVinci Resolve', 'kind': 'store', 'done': False}, apps['davinci-resolve']
    assert apps['netflix']['kind'] == 'web' and apps['netflix']['done'] is True and apps['disney-plus']['done'] is False
    # --status changes nothing
    assert json.loads((t / 'state/windoesnot/pending-apps-done.json').read_text())['done'] == ['krita']
    # the switch: welcome-state stores it, setup-notice reads it
    state = lambda *a: subprocess.run([str(BIN / 'windoesnot-welcome-state'), *a], env=env, capture_output=True, text=True)
    assert state('showAtStart', 'true').returncode == 0
    assert json.loads(state().stdout)['state']['showAtStart'] is True
    loader = importlib.machinery.SourceFileLoader('notice', str(BIN / 'windoesnot-setup-notice'))
    spec = importlib.util.spec_from_loader('notice', loader); notice = importlib.util.module_from_spec(spec); loader.exec_module(notice)
    os.environ['XDG_CONFIG_HOME'] = str(t / 'cfg')
    assert notice.show_at_start() is True
    state('showAtStart', 'false'); assert notice.show_at_start() is False
    (t / 'cfg/windoesnot/welcome-checklist.json').write_text('not json'); assert notice.show_at_start() is False
    german = notice.welcome_payload({'cpu_level': 'v3', 'drivers': 'configured', 'driver_profiles': ['qemu']}, {'uiLanguage': 'de'})
    english = notice.welcome_payload({'cpu_level': 'v3', 'drivers': 'configured', 'driver_profiles': ['qemu']}, {'uiLanguage': 'en'})
    assert german['showAtStart'] == 'Beim Start anzeigen' and english['showAtStart'] == 'Show at startup'
print('PASS: welcome window helpers (apps left for later with state, show-at-startup switch stored and read)')
