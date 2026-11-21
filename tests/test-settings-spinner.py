#!/usr/bin/env python3
"""The settings spinner (explicit colour instead of the palette-dependent BusyIndicator) spins only while it runs (offscreen)."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'desktop/config/quickshell/default/settings'
settings = '\n'.join(p.read_text() for p in source.glob('*Category.qml'))
assert 'BusyIndicator' not in settings, 'stock BusyIndicator (palette colour) is back in a settings page'
assert 'SettingsSpinner 1.0 SettingsSpinner.qml' in (source / 'qmldir').read_text()

with tempfile.TemporaryDirectory(prefix='wdn-spinner-') as tmp:
    base = Path(tmp)
    shutil.copy(source / 'SettingsSpinner.qml', base / 'SettingsSpinner.qml')
    (base / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 Window { id: win; visible: true; width: 120; height: 60; color: "#f5f5f5"
  SettingsSpinner { id: spin; x: 10; y: 10; width: 32; height: 32; color: "#fe6f2d"; running: true }
  SettingsSpinner { id: idle; x: 60; y: 10; width: 32; height: 32; color: "#fe6f2d"; running: false }
  Timer { interval: 900; running: true; onTriggered: {
    var dots = spin.children[0].children.length
    console.log("SPIN", spin.children[0].rotation > 0, idle.children[0].rotation === 0, dots)
    Qt.quit()
  } }
 }
}''')
    runtime = base / 'run'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(base / 'shell.qml')], env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=15)
    print(result.stdout[-600:])
    assert 'SPIN true true' in result.stdout and 'Failed' not in result.stdout and 'ERROR' not in result.stdout, result.stdout
print('PASS: settings pages use the colour-explicit spinner; it spins while running and stays still when not')
