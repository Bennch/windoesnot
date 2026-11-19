#!/usr/bin/env python3
"""The real search window (SearchWindow.qml) in an offscreen shell: instant ranking, answers, filters, no QML warnings."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-search-') as temp:
    base = Path(temp)
    for name in ('i18n', 'widgets', 'settings', 'img'):
        shutil.copytree(SOURCE / name, base / name)
    for name in ('SearchWindow.qml', 'AppIcon.qml', 'SearchLogic.js', 'EmojiData.js', 'SpecialChars.js'):
        shutil.copy2(SOURCE / name, base / name)
    (base / 'shell.qml').write_text('''import QtQuick
import Quickshell
ShellRoot {
  ListModel { id: apps
    ListElement { name: "Firefox"; cmd: "firefox"; icon: "firefox"; customIcon: false }
    ListElement { name: "Visual Studio Code"; cmd: "code"; icon: "code"; customIcon: false }
    ListElement { name: "Files"; cmd: "nautilus"; icon: "folder"; customIcon: false } }
  SearchWindow { id: s; appsModel: apps; visible: true }
  Timer { running: true; interval: 600; onTriggered: {
    try {
      function names() { return s.appResults.map(a => a.name).join(",") }
      s.query = "vsc";   var initials = names()
      s.query = "2+2*3"; var calc = s.calcResult
      s.query = "5 km in mi"; var unit = s.calcResult
      s.query = "/pdf bill"; var filter = s.filterKind + "|" + s.searchText + "|" + s.appResults.length + "|" + (s.calcResult === "")
      s.query = "bill"; s.stepChip(1); var chip1 = s.filterKind
      s.stepChip(4); var chip2 = s.filterKind + ":" + s.activeChip
      s.stepChip(-9); var chip3 = s.filterKind + ":" + s.activeChip
      s.query = "/pdf x"; s.stepChip(1); var chip4 = s.filterKind + ":" + s.searchText + ":" + s.query
      s.chipIndex = 0
      s.query = ""; s.cycleChip(1); var up1 = s.filterKind
      s.cycleChip(1); s.cycleChip(1); var up3 = s.filterKind
      s.cycleChip(-1); var up4 = s.filterKind
      s.chipIndex = 0
      s.query = ":herz"; var heart = s.filteredEmoji.length > 3 && s.filteredEmoji[0].e.length > 0
      s.query = ";euro"; var euro = s.filterKind === "special" && s.filteredSpecial.length > 0 && s.filteredSpecial[0].e === "€"
      s.query = ";"; var allSpecial = s.filteredSpecial.length > 250
      s.query = ":"; var allEmoji = s.filteredEmoji.length > 1800
      s.query = "euro"; s.chipIndex = 8; var chipSpecial = s.filterKind + ":" + (s.filteredSpecial.length > 0) + ":" + s.appResults.length
      s.chipIndex = 0
      s.query = ":lol"; var hint = s.filteredEmoji.length > 0
      s.query = ""
      var empty = s.showHints
      s.usage = {"Files": {c: 4, t: Date.now()}}
      var recent = s.allApps().length
      console.log("SEARCH_RESULT " + [initials, calc, unit, filter, empty, recent, chip1, chip2, chip3, chip4, up1, up3, up4, heart, euro, allSpecial, allEmoji, hint, chipSpecial].join(" ; "))
    } catch (e) { console.log("SEARCH_ERROR " + e) }
    Qt.quit() } }
}''')
    runtime = base / 'runtime'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen',
           'QT_QUICK_BACKEND': 'software', 'QT_QPA_PLATFORMTHEME': 'basic', 'WAYLAND_DISPLAY': '', 'DISPLAY': '',
           'DBUS_SESSION_BUS_ADDRESS': ''}
    out = subprocess.run(['quickshell', '--no-color', '-p', str(base / 'shell.qml')], env=env, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30).stdout
    line = next((l for l in out.splitlines() if 'SEARCH_' in l), '')
    assert 'SEARCH_RESULT Visual Studio Code ; 8 ; 3.1068559612 mi ; pdf|bill|0|true ; true ; 3 ; apps ; pdf:5 ; :0 ; video:x:x ; apps ; docs ; folders ; true ; true ; true ; true ; true ; special:true:0' in line, line + out[-1500:]
    for bad in ('WARN scene', 'TypeError', 'ReferenceError', 'Failed to load configuration'):
        assert bad not in out, bad + '\n' + out[-1500:]
print('PASS: search window ranks, answers and filters without QML warnings')
