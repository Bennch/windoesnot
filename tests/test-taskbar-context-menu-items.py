#!/usr/bin/env python3
"""Taskbar context menus (quickSettingsContextMenu.itemsFor): the tray menu has Cinema mode (DE/EN) that runs windoesnot-kino toggle;
the clock, weather and audio entries stay; every menu except the clock still ends with the tray settings."""
import json
import re
import subprocess
from pathlib import Path

shell = (Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default/shell.qml').read_text()
start = shell.index('    function itemsFor(kind) {')
end = shell.index('    function openFor(kind, iconItem)', start)
function = shell[start:end]
script = 'var settingsMenu = {uiLanguage: "de"};\n' + function + '''
var out = {}
;["tray", "clock", "weather", "audio", "network", "bluetooth", "graphics"].forEach(function(k) {
  settingsMenu.uiLanguage = "de"; var de = itemsFor(k)
  settingsMenu.uiLanguage = "en"; var en = itemsFor(k)
  out[k] = {de: de, en: en}
})
console.log(JSON.stringify(out))
'''
result = subprocess.run(['node', '-e', script.replace('    function itemsFor', 'function itemsFor')], capture_output=True, text=True, timeout=20)
assert result.returncode == 0, result.stderr
menus = json.loads(result.stdout)
tray = menus['tray']
assert [i['kind'] for i in tray['de']] == ['cinemaMode', 'traySettings'] and tray['de'][0]['label'] == 'Kinomodus' and tray['en'][0]['label'] == 'Cinema mode'
assert [i['kind'] for i in menus['clock']['de']] == ['calendarSettings'], 'the clock menu has no tray entry'
assert [i['kind'] for i in menus['weather']['de']] == ['weatherSettings', 'traySettings']
assert [i['kind'] for i in menus['audio']['de']] == ['openAudio', 'traySettings']
assert all(menus[k]['de'][-1]['kind'] == 'traySettings' for k in ('tray', 'weather', 'audio', 'network', 'bluetooth', 'graphics'))
assert re.search(r'kind === "cinemaMode"\) \{\s*visible = false\s*run\("windoesnot-kino toggle"\)', shell), 'the entry must run windoesnot-kino toggle'
print('PASS: taskbar context menus: tray has Cinema mode (DE/EN) and runs windoesnot-kino toggle, other menus unchanged')
