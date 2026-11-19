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
    for name in ('SearchWindow.qml', 'SearchLogic.js'):
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
      s.query = ""; var empty = s.showHints
      s.usage = {"Files": {c: 4, t: Date.now()}}
      var recent = s.allApps().length
      console.log("SEARCH_RESULT " + [initials, calc, unit, filter, empty, recent].join(" ; "))
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
    assert 'SEARCH_RESULT Visual Studio Code ; 8 ; 3.1068559612 mi ; pdf|bill|0|true ; true ; 3' in line, line + out[-1500:]
    for bad in ('WARN scene', 'TypeError', 'ReferenceError', 'Failed to load configuration'):
        assert bad not in out, bad + '\n' + out[-1500:]
print('PASS: search window ranks, answers and filters without QML warnings')
