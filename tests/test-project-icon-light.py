#!/usr/bin/env python3
"""ProjectIcon picks a dark default colour in light mode and keeps the light grey in dark mode (offscreen)."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-project-icon-') as tmp:
    base = Path(tmp)
    (base / 'widgets').mkdir(); (base / 'img/project').mkdir(parents=True)
    shutil.copy(source / 'widgets/ProjectIcon.qml', base / 'widgets/ProjectIcon.qml')
    shutil.copytree(source / 'i18n', base / 'i18n')
    shutil.copy(source / 'img/project/headphones.svg', base / 'img/project/headphones.svg')
    (base / 'widgets/qmldir').write_text('ProjectIcon 1.0 ProjectIcon.qml\n')
    (base / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import "widgets"
ShellRoot {
 Window { id: win; visible: true; width: 100; height: 100
  Item { id: panel; property bool darkMode: false
    ProjectIcon { id: plain; name: "headphones" }
    ProjectIcon { id: explicit; name: "headphones"; color: "#fe6f2d" }
  }
  Item { id: viaSettings; property var settingsMenu: ({ darkMode: true })
    ProjectIcon { id: nested; name: "headphones" }
  }
  Timer { interval: 400; running: true; onTriggered: {
    var light = String(plain.color)
    panel.darkMode = true
    var dark = String(plain.color)
    console.log("ICON", light, dark, String(explicit.color), String(nested.color))
    Qt.quit()
  } }
 }
}''')
    runtime = base / 'run'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(base / 'shell.qml')], env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=15)
    line = next((l for l in result.stdout.splitlines() if ' qml: ICON ' in l), '')
    print(line)
    assert line.split()[-4:] == ['#333333', '#cccccc', '#fe6f2d', '#cccccc'], (line, result.stdout[-400:])
print('PASS: ProjectIcon default is dark in light mode, light in dark mode, explicit colours win')
