#!/usr/bin/env python3
"""Compile the real Bluetooth panel offscreen: it loads without QML warnings, lists devices, the split button's second part sets and
clears the default device (real windoesnot-bluetooth-default with a temporary config), the status line stays inside its column."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-bluetooth-ui-') as temp:
    base = Path(temp)
    profile = base / 'profile'
    (profile / 'widgets').mkdir(parents=True)
    shutil.copytree(SOURCE / 'i18n', profile / 'i18n')
    shutil.copy2(SOURCE / 'widgets/qmldir', profile / 'widgets/qmldir')
    for path in (SOURCE / 'widgets').iterdir():
        if path.suffix == '.qml' or path.suffix == '.py':
            shutil.copy2(path, profile / 'widgets')
    if (SOURCE / 'bt_scan.py').exists():
        shutil.copy2(SOURCE / 'bt_scan.py', profile / 'bt_scan.py')
    if (SOURCE / 'img').exists():
        shutil.copytree(SOURCE / 'img', profile / 'img')
    bin_dir = base / 'bin'; bin_dir.mkdir()
    shutil.copy2(ROOT / 'desktop/bin/windoesnot-bluetooth-default', bin_dir)
    stub = bin_dir / 'windoesnot-bounded'; stub.write_text('#!/bin/sh\nshift\nexec "$@"\n'); stub.chmod(0o755)
    ctl = bin_dir / 'bluetoothctl'; ctl.write_text('#!/bin/sh\nexit 0\n'); ctl.chmod(0o755)
    (profile / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import "widgets"
ShellRoot {
 Window {
  id: testWindow; visible: true; width: 320; height: 450
  Loader { id: loader; anchors.fill: parent; source: "widgets/BluetoothPanel.qml" }
  readonly property var panel: loader.item
  function check(ok, message) { if (!ok) throw new Error(message) }
  function find(o, predicate) { if (predicate(o)) return o; for (let c of (o.children || [])) { let r = find(c, predicate); if (r) return r } return null }
  function findAll(o, predicate, out) { if (predicate(o)) out.push(o); for (let c of (o.children || [])) findAll(c, predicate, out); return out }
  property int step: 0
  property var panelRef: loader.item
  Timer { interval: 400; running: true; repeat: true; onTriggered: {
   try {
    if (testWindow.step === 0) {
     testWindow.panel.bluetoothEnabled = true; testWindow.panel.bluetoothControllerAvailable = true
     testWindow.panel.allDevices = [
      {mac: "08:EB:ED:11:97:7A", name: "SoundCore 2", paired: true, connected: true, battery: 100, icon: "img/Win11-dark/devices/symbolic/audio-headphones-symbolic.svg", cls: ""},
      {mac: "98:B6:E9:C2:19:E6", name: "Pro Controller", paired: true, connected: false, battery: -1, icon: "img/Win11-dark/devices/symbolic/audio-headphones-symbolic.svg", cls: ""},
      {mac: "AA:BB:CC:DD:EE:FF", name: "Unpaired Speaker", paired: false, connected: false, battery: -1, icon: "img/Win11-dark/devices/symbolic/audio-headphones-symbolic.svg", cls: ""}]
    } else if (testWindow.step === 1) {
     testWindow.check(testWindow.find(testWindow.panel, o => o.text === "SoundCore 2") && testWindow.find(testWindow.panel, o => o.text === "Pro Controller"), "devices listed")
     const segments = testWindow.findAll(testWindow.panel, o => o.visible && o.width === 24 && o.height === 24 && o.radius === 4, [])
     testWindow.check(segments.length === 2, "second button part only for paired devices, found " + segments.length)
     testWindow.check(testWindow.panel.defaultMac === "", "no default yet")
     testWindow.panel.toggleDefault("08:EB:ED:11:97:7A")
    } else if (testWindow.step === 3) {
     testWindow.check(testWindow.panel.defaultMac === "08:EB:ED:11:97:7A", "default set through the helper, got " + testWindow.panel.defaultMac)
     const status = testWindow.find(testWindow.panel, o => o.text === "Verbunden • 100%")
     testWindow.check(status && status.elide === Text.ElideRight && status.width > 0, "status line elides inside its column")
     testWindow.panel.toggleDefault("08:EB:ED:11:97:7A")
    } else if (testWindow.step === 5) {
     testWindow.check(testWindow.panel.defaultMac === "", "default cleared again")
     testWindow.panel.uiLanguage = "en"
     testWindow.check(testWindow.find(testWindow.panel, o => o.text === "Connected • 100%"), "English status line")
     console.log("BLUETOOTH_UI_PASS"); Qt.quit()
    }
    testWindow.step++
   } catch (e) { console.error("BLUETOOTH_UI_FAIL", e); Qt.quit() }
  } }
 }
}''')
    runtime = base / 'run'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_CONFIG_HOME': str(base / 'config'), 'XDG_CACHE_HOME': str(base / 'cache'),
           'XDG_RUNTIME_DIR': str(runtime), 'PATH': f'{bin_dir}:' + os.environ['PATH'],
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'QT_QPA_PLATFORMTHEME': 'basic',
           'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(profile / 'shell.qml')], env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    print(result.stdout[-3000:])
    assert 'BLUETOOTH_UI_PASS' in result.stdout
    for error in ('ReferenceError', 'TypeError', 'Failed to load configuration', 'Cannot assign', 'Binding loop', 'Non-existent attached object', 'BLUETOOTH_UI_FAIL'):
        assert error not in result.stdout, error
print('PASS: Bluetooth panel loads without warnings, split button sets and clears the default device, status line elides, DE/EN')
