#!/usr/bin/env python3
"""Compile the real Accessibility settings page offscreen: no QML warnings, it reads the helper's state and changes colour filter, cursor, text size, motion and zoom through it."""
import json, os, shutil, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-a11y-ui-') as temp:
    base = Path(temp); profile = base / 'profile'; (profile / 'settings').mkdir(parents=True)
    shutil.copytree(SOURCE / 'i18n', profile / 'i18n')
    for path in (SOURCE / 'settings').iterdir():
        if path.suffix in ('.qml', '.js') or path.name == 'qmldir':
            shutil.copy2(path, profile / 'settings')
    bin_dir = base / 'bin'; bin_dir.mkdir(); calls = base / 'calls.log'; zoom = base / 'zoom'; zoom.write_text('1.0')
    shutil.copy2(ROOT / 'desktop/bin/windoesnot-accessibility', bin_dir)
    def stub(name, body):
        p = bin_dir / name; p.write_text('#!/bin/sh\n' + body); p.chmod(0o755)
    stub('windoesnot-hyprctl', f'echo "hypr $*" >> {calls}\n[ "$1 $2" = "keyword cursor:zoom_factor" ] && echo "$3" > {zoom}\nexit 0\n')
    stub('hyprctl', f'echo "{{\\"float\\":$(cat {zoom})}}"\n')
    stub('gsettings', f'echo "gsettings $*" >> {calls}\n[ "$1" = get ] && echo "\'Adwaita\'"\nexit 0\n')
    stub('squeekboard', 'sleep 5\n')
    (profile / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import "settings"
ShellRoot {
 Window {
  id: testWindow; visible: true; width: 700; height: 900
  Loader { id: loader; anchors.fill: parent; source: "settings/AccessibilityCategory.qml"; onLoaded: item.settingsMenu = menu }
  QtObject { id: menu; property string uiLanguage: "de"; property bool darkMode: true; property color accentColor: "#fe6f2d" }
  property int step: 0
  function check(ok, message) { if (!ok) throw new Error(message) }
  function find(o, predicate) { if (predicate(o)) return o; for (let c of (o.children || [])) { let r = find(c, predicate); if (r) return r } return null }
  Timer { interval: 700; running: true; repeat: true; onTriggered: {
   try {
    const page = loader.item
    if (testWindow.step === 0) {
     testWindow.check(page.loaded, "state read from the helper")
     testWindow.check(page.keyboardInstalled && page.colorFilter === "none" && page.zoom === 1.0, "defaults shown")
     testWindow.check(testWindow.find(page, o => o.text === "Lupe") && testWindow.find(page, o => o.text === "Bildschirmtastatur") && testWindow.find(page, o => o.text === "Farben"), "German section titles")
     page.run(["set", "colorFilter", "protanopia"])
    } else if (testWindow.step === 1) {
     testWindow.check(page.colorFilter === "protanopia", "colour filter read back")
     page.run(["set", "cursorSize", "48"])
    } else if (testWindow.step === 2) {
     testWindow.check(page.cursorSize === 48, "cursor size read back")
     page.run(["set", "textScale", "1.5"])
    } else if (testWindow.step === 3) {
     testWindow.check(page.textScale === 1.5, "text size read back")
     page.run(["set", "reduceMotion", "true"])
    } else if (testWindow.step === 4) {
     testWindow.check(page.reduceMotion === true, "reduced motion read back")
     page.run(["zoom", "in"])
    } else if (testWindow.step === 5) {
     testWindow.check(page.zoom === 1.25, "zoom read back, got " + page.zoom)
     menu.uiLanguage = "en"; page._lang = "en"
     testWindow.check(testWindow.find(page, o => o.text === "Magnifier") && testWindow.find(page, o => o.text === "Color filter"), "English labels")
     console.log("A11Y_UI_PASS"); Qt.quit()
    }
    testWindow.step++
   } catch (e) { console.error("A11Y_UI_FAIL", e); Qt.quit() }
  } }
 }
}''')
    runtime = base / 'run'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_CONFIG_HOME': str(base / 'config'), 'XDG_CACHE_HOME': str(base / 'cache'),
           'XDG_RUNTIME_DIR': str(runtime), 'PATH': f'{bin_dir}:' + os.environ['PATH'], 'QT_QPA_PLATFORM': 'offscreen',
           'QT_QUICK_BACKEND': 'software', 'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(profile / 'shell.qml')], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)
    print(result.stdout[-2500:])
    assert 'A11Y_UI_PASS' in result.stdout
    for error in ('ReferenceError', 'TypeError', 'Failed to load configuration', 'Cannot assign', 'Binding loop', 'Non-existent attached object', 'A11Y_UI_FAIL'):
        assert error not in result.stdout, error
    saved = json.loads((base / 'config/windoesnot/accessibility.json').read_text())
    assert saved == {'colorFilter': 'protanopia', 'cursorSize': 48, 'textScale': 1.5, 'reduceMotion': True}, saved
print('PASS: accessibility settings page loads without warnings and drives the helper (filter, cursor, text, motion, zoom, DE/EN)')
