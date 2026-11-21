#!/usr/bin/env python3
"""windoesnot-open-app: a running app is brought forward (also when minimized), a closed one is started; matching by desktop entry."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

script = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-open-app'
loader = importlib.machinery.SourceFileLoader('open_app', str(script))
spec = importlib.util.spec_from_loader('open_app', loader); mod = importlib.util.module_from_spec(spec); loader.exec_module(mod)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    apps = tmp / 'applications'; apps.mkdir()
    (apps / 'firefox.desktop').write_text('[Desktop Entry]\nName=Firefox\nExec=firefox %u\nStartupWMClass=firefox\n')
    (apps / 'org.gnome.Nautilus.desktop').write_text('[Desktop Entry]\nName=Files\nExec=nautilus --new-window %U\n')
    (apps / 'com.mitchellh.ghostty.desktop').write_text('[Desktop Entry]\nName=Ghostty\nExec=ghostty --gtk-single-instance=false\n')
    (apps / 'discord.desktop').write_text('[Desktop Entry]\nName=Discord\nExec=env FOO=1 /usr/bin/discord\nStartupWMClass=discord\n')
    (apps / 'flat.desktop').write_text('[Desktop Entry]\nName=Flat\nExec=flatpak run --branch=stable org.example.Flat\n')
    (apps / 'webapp.desktop').write_text('[Desktop Entry]\nName=Web\nExec=windoesnot-webapp https://example.org\n')

    # executable_of
    assert mod.executable_of('env FOO=1 /usr/bin/discord --x') == 'discord'
    assert mod.executable_of('flatpak run --branch=stable org.example.Flat') == 'org.example.Flat'
    assert mod.executable_of('setsid nohup ghostty') == 'ghostty'

    # keys per app
    assert 'firefox' in mod.app_keys(apps / 'firefox.desktop', 'firefox')
    assert {'org.gnome.nautilus', 'nautilus'} <= mod.app_keys(apps / 'org.gnome.Nautilus.desktop', 'nautilus')
    assert 'ghostty' in mod.app_keys(apps / 'com.mitchellh.ghostty.desktop', 'ghostty')
    assert mod.app_keys(apps / 'webapp.desktop', 'windoesnot-webapp https://example.org') == {'webapp'}, 'generic executables are no key'
    assert mod.app_keys(None, 'bash -c something') == set()

    clients = [
        {'address': '0x1', 'class': 'firefox', 'mapped': True, 'focusHistoryID': 3, 'workspace': {'id': 1, 'name': '1'}, 'floating': False},
        {'address': '0x2', 'class': 'firefox', 'mapped': True, 'focusHistoryID': 1, 'workspace': {'id': -98, 'name': 'special:minimized'}, 'floating': True},
        {'address': '0x3', 'class': 'org.gnome.Nautilus', 'mapped': True, 'focusHistoryID': 0, 'workspace': {'id': 2, 'name': '2'}, 'floating': False},
        {'address': '0x4', 'class': 'com.mitchellh.ghostty', 'mapped': True, 'focusHistoryID': 2, 'workspace': {'id': 1, 'name': '1'}, 'floating': True},
        {'address': '0x5', 'class': 'quickshell', 'mapped': True, 'focusHistoryID': 9, 'workspace': {'id': 1, 'name': '1'}},
        {'address': '0x6', 'class': 'steam', 'mapped': False, 'focusHistoryID': 0, 'workspace': {'id': 1, 'name': '1'}}]
    assert mod.pick_window(clients, mod.app_keys(apps / 'firefox.desktop', 'firefox'))['address'] == '0x2', 'the most recently used window wins'
    assert mod.pick_window(clients, mod.app_keys(apps / 'org.gnome.Nautilus.desktop', 'nautilus'))['address'] == '0x3'
    assert mod.pick_window(clients, mod.app_keys(apps / 'com.mitchellh.ghostty.desktop', 'ghostty'))['address'] == '0x4', 'suffix of a reverse-DNS class'
    assert mod.pick_window(clients, {'quickshell'}) is None, 'shell surfaces are never a target'
    assert mod.pick_window(clients, {'steam'}) is None, 'unmapped windows are ignored'
    assert mod.pick_window(clients, {'libreoffice'}) is None
    assert mod.focus_commands(clients[1], 4) == ['movetoworkspace 4,address:0x2', 'focuswindow address:0x2', 'bringactivetotop'], mod.focus_commands(clients[1], 4)
    assert mod.focus_commands(clients[2], 1) == ['focuswindow address:0x3']

    # end to end with fake hyprctl / windoesnot-hyprctl on PATH
    bin_dir = tmp / 'bin'; bin_dir.mkdir(); log = tmp / 'calls.log'
    def tool(name, body):
        path = bin_dir / name; path.write_text('#!/bin/sh\n' + body); path.chmod(path.stat().st_mode | stat.S_IEXEC)
    import json
    tool('hyprctl', f"case \"$2\" in clients) cat {tmp}/clients.json;; activeworkspace) echo '{{\"id\": 4}}';; esac\n")
    tool('windoesnot-hyprctl', f'echo "$@" >> {log}\n')
    tool('started-app', f'echo started >> {tmp}/started.log\n')
    (tmp / 'clients.json').write_text(json.dumps(clients))
    env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'XDG_DATA_HOME': str(tmp), 'XDG_DATA_DIRS': str(tmp / 'none')}
    def run(*args): return subprocess.run([sys.executable, str(script), *args], env=env, capture_output=True, text=True, timeout=15)
    result = run('--cmd', 'started-app', '--name', 'Firefox', '--desktop', str(apps / 'firefox.desktop'))
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == ['dispatch movetoworkspace 4,address:0x2', 'dispatch focuswindow address:0x2', 'dispatch bringactivetotop'], log.read_text()
    assert not (tmp / 'started.log').exists(), 'a running app is not started again'
    # name lookup without a desktop file path
    log.write_text('')
    run('--cmd', 'started-app', '--name', 'Files')
    assert 'dispatch focuswindow address:0x3' in log.read_text()
    # an app that is not running is started
    result = run('--cmd', 'started-app', '--name', 'Discord', '--desktop', str(apps / 'discord.desktop'))
    import time; time.sleep(1)
    assert (tmp / 'started.log').exists(), 'a closed app is started'
print('PASS: open-app helper focuses a running app (restores minimized, raises floating, newest window) and starts a closed one')

# the Start menu and the search call the helper (no direct launch of an app that may already run)
shell = (script.parents[2] / 'desktop/config/quickshell/default/shell.qml').read_text()
search = (script.parents[2] / 'desktop/config/quickshell/default/SearchWindow.qml').read_text()
assert shell.count('panelWindow.launchOrFocus(') == 5 and 'function launchOrFocus(' in shell
assert 'windoesnot-open-app' in shell and 'windoesnot-open-app' in search
print('PASS: Start menu and search use windoesnot-open-app')
