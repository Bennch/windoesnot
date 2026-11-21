#!/usr/bin/env python3
"""Exercise the taskbar search magnifier's actual QML in both themes offscreen."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'desktop/config/quickshell/default'
qml = (source / 'shell.qml').read_text()
start = qml.index('                Image {', qml.index('id: searchTaskbarButton'))
end = qml.index('\n\n                MouseArea {', start)
icon = qml[start:end].replace('Image {', 'Image {\n                    id: searchIcon', 1)
with tempfile.TemporaryDirectory(prefix='wdn-search-icon-') as tmp:
    base = Path(tmp)
    (base / 'img').mkdir()
    shutil.copy(source / 'img/search.svg', base / 'img/search.svg')
    (base / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import QtQuick.Effects
import Quickshell
ShellRoot {
 Window { id: testWindow; visible: true; width: 80; height: 80
  QtObject { id: settingsMenu; property bool darkMode: true }
  Rectangle { id: searchTaskbarButton; property bool hovered: false; width: 40; height: 40
''' + icon + '''
  }
  property int step: 0
  Timer { interval: 500; running: true; repeat: true; onTriggered: {
   let icon = searchIcon
   if (!icon || icon.layer.enabled !== (testWindow.step === 1)) { console.error("ICON_FAIL", testWindow.step); Qt.quit(); return }
   if (testWindow.step === 0) settingsMenu.darkMode = false
   else if (testWindow.step === 1) settingsMenu.darkMode = true
   else { console.log("ICON_PASS"); Qt.quit(); return }
   testWindow.step++
  } }
 }
}''')
    runtime = base / 'run'
    runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen',
           'QT_QUICK_BACKEND': 'software', 'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    try:
        result = subprocess.run(['quickshell', '--no-color', '-p', str(base / 'shell.qml')], env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=4)
    except subprocess.TimeoutExpired as exc:
        print(exc.stdout)
        raise
    print(result.stdout)
    assert result.returncode == 0 and 'ICON_PASS' in result.stdout and 'ICON_FAIL' not in result.stdout
