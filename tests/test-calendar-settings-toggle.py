#!/usr/bin/env python3
"""Calendar toggles on the Input page must read and write the real settings object.

Regression: `settingsMenu: settingsMenu` inside a control that has its own `settingsMenu` property binds the control
to itself (null), so the switch showed the wrong state and never changed the setting."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-cal-ui-') as temp:
    base = Path(temp)
    shutil.copytree(SOURCE / 'settings', base / 'settings'); shutil.copytree(SOURCE / 'i18n', base / 'i18n')
    shutil.copy2(SOURCE / 'LocaleNames.js', base)
    (base / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 Window {
  id: w; visible: true; width: 900; height: 1100
  QtObject { id: prefs; property bool darkMode: true; property string uiLanguage: "de"; property color accentColor: "#fe6f2d"; property int borderRadius: 10
    property bool calendarHolidays: true; property bool calendarWeekNumbers: false; property string calendarRegion: "auto"; property string calendarState: "ALL"
    property bool calendarRegional: true; property bool calendarObservances: true; property string calendarFirstDay: "auto" }
  Loader { id: l; width: 700; Component.onCompleted: setSource("settings/InputCategory.qml", {settingsMenu: prefs}) }
  function find(o,p){ if(p(o)) return o; for(let c of (o.children||[])){ let r=find(c,p); if(r) return r } return null }
  Timer { running: true; interval: 500; onTriggered: {
    try {
      const sw = w.find(l.item, o => o.text === "Feiertage im Kalender markieren" && o.toggle)
      if (!sw.checked) throw new Error("holiday switch must start on")
      sw.toggle(); sw.toggled()
      if (prefs.calendarHolidays) throw new Error("holiday switch did not change the setting")
      const kw = w.find(l.item, o => o.text === "Kalenderwochen anzeigen (KW)" && o.toggle)
      kw.toggle(); kw.toggled()
      if (!prefs.calendarWeekNumbers) throw new Error("week number switch did not change the setting")
      console.log("CAL_TOGGLE_PASS")
    } catch(e) { console.log("CAL_TOGGLE_FAIL " + e) }
    Qt.quit() } }
 }
}''')
    runtime = base / 'runtime'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen',
           'QT_QUICK_BACKEND': 'software', 'WAYLAND_DISPLAY': '', 'DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    out = subprocess.run(['quickshell', '--no-color', '-p', str(base / 'shell.qml')], env=env, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20).stdout
    assert 'CAL_TOGGLE_PASS' in out, out[-1500:]
    assert 'Value is null' not in out, out[-1500:]
print('PASS: calendar settings switches change the real settings')
