#!/usr/bin/env python3
"""The Files card in Settings > Apps loads without QML warnings, shows the open mode and the sidebar places (the start page is fixed to This PC, no setting), and writes changes through windoesnot-file-manager."""
import os, shutil, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-files-ui-') as temp:
    base = Path(temp); profile = base / 'profile'; (profile / 'settings').mkdir(parents=True)
    shutil.copytree(SOURCE / 'i18n', profile / 'i18n')
    for path in (SOURCE / 'settings').iterdir():
        if path.suffix in ('.qml', '.js') or path.name == 'qmldir':
            shutil.copy2(path, profile / 'settings')
    bin_dir = base / 'bin'; bin_dir.mkdir(); log = base / 'calls.log'
    stub = bin_dir / 'windoesnot-file-manager'
    stub.write_text(f'''#!/bin/sh
echo "$*" >> {log}
case "$1 $2" in
  "--open-mode get") echo tab;;
  "--sidebar available") exit 0;;
  "--sidebar get") echo "recent network";;
esac
exit 0
'''); stub.chmod(0o755)
    (profile / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import "settings"
ShellRoot {
 Window {
  id: w; visible: true; width: 700; height: 800
  Loader { id: loader; anchors.fill: parent; source: "settings/FileManagerSettings.qml"; onLoaded: item.settingsMenu = menu }
  QtObject { id: menu; property string uiLanguage: "de"; property bool darkMode: true; property color accentColor: "#fe6f2d" }
  property int step: 0
  function check(ok, message) { if (!ok) throw new Error(message) }
  function find(o, predicate) { if (predicate(o)) return o; for (let c of (o.children || [])) { let r = find(c, predicate); if (r) return r } return null }
  Timer { interval: 700; running: true; repeat: true; onTriggered: {
   try {
    const page = loader.item
    if (w.step === 1) {
     w.check(page.mode === "tab", "open mode read: " + page.mode)
     w.check(page.sidebarAvailable && page.hiddenPlaces.length === 2, "sidebar places read: " + page.hiddenPlaces)
     w.check(w.find(page, o => o.text === "Papierkorb") && w.find(page, o => o.text === "Zuletzt verwendet") && w.find(page, o => o.text === "In der Seitenleiste anzeigen"), "German labels")
     page.setPlace("trash", false)
    } else if (w.step === 3) {
     console.log("FILES_UI_PASS"); Qt.quit()
    }
    w.step++
   } catch (e) { console.error("FILES_UI_FAIL", e); Qt.quit() }
  } }
 }
}''')
    runtime = base / 'run'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_CONFIG_HOME': str(base / 'config'), 'XDG_RUNTIME_DIR': str(runtime), 'PATH': f'{bin_dir}:' + os.environ['PATH'],
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(profile / 'shell.qml')], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    print(result.stdout[-1500:])
    assert 'FILES_UI_PASS' in result.stdout
    for error in ('ReferenceError', 'TypeError', 'Failed to load configuration', 'Cannot assign', 'Binding loop', 'Non-existent attached object', 'FILES_UI_FAIL'):
        assert error not in result.stdout, error
    assert '--sidebar hide trash' in log.read_text(), log.read_text()
print('PASS: Files card (open mode, sidebar places) loads without warnings and writes through windoesnot-file-manager')
