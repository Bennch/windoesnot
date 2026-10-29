#!/usr/bin/env python3
"""Compile the Power settings page and the combined Maintenance/Kernel page."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
POWER_FIXTURE = {'battery': {'percentage': '72', 'state': 'discharging', 'timeToEmpty': '3.2 hours',
                              'timeToFull': '', 'capacity': '98%'},
                  'profiles': ['performance', 'balanced', 'power-saver'], 'currentProfile': 'balanced',
                  'profilesAvailable': True}
NO_BATTERY_FIXTURE = {'battery': None, 'profiles': ['performance', 'balanced', 'power-saver'],
                       'currentProfile': 'performance', 'profilesAvailable': True}
with tempfile.TemporaryDirectory(prefix='wdn-power-ui-') as temp:
    base = Path(temp); profile = base / 'profile'; (profile / 'settings').mkdir(parents=True)
    shutil.copytree(SOURCE / 'i18n', profile / 'i18n')
    shutil.copy2(SOURCE / 'settings/PowerCategory.qml', profile / 'settings')
    shutil.copy2(SOURCE / 'settings/SystemCategory.qml', profile / 'settings')
    shutil.copy2(SOURCE / 'settings/KernelCategory.qml', profile / 'settings')
    shutil.copy2(SOURCE / 'settings/MaintenanceCategory.qml', profile / 'settings')
    for name in ('SystemToolsButton', 'SystemToolsChoice', 'SystemToolsToggle', 'SystemToolsConfirm'):
        shutil.copy2(SOURCE / ('settings/' + name + '.qml'), profile / 'settings')
    (profile / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 Window {
  id: testWindow
  visible: true; width: 900; height: 1100
  QtObject { id: preferences; property bool darkMode: true; property string uiLanguage: "de"; property string accentColor: "#fe6f2d"; property bool fileDialogOpen: false; property int borderRadius: 10 }
  Loader { id: powerLoader; width: 650; Component.onCompleted: setSource("settings/PowerCategory.qml", {settingsMenu:preferences,autoLoad:false}) }
  Loader { id: systemLoader; width: 650; Component.onCompleted: setSource("settings/SystemCategory.qml", {settingsMenu:preferences}) }
  function check(ok,message) { if(!ok) throw new Error(message) }
  function find(o,predicate) { if(predicate(o)) return o; for(let c of (o.children || [])) { let r=find(c,predicate); if(r) return r } return null }
  Timer { running: true; interval: 250; onTriggered: {
   try {
    const page = powerLoader.item
    page.acceptStatus(__POWER_FIXTURE__)
    testWindow.check(page.ready, "power status applied")
    testWindow.check(page.height > 100, "power page has content")
    testWindow.check(!!testWindow.find(page, o => o.text === "72%"), "battery percentage shown")
    testWindow.check(!!testWindow.find(page, o => o.text === page.tr("power.stateDischarging")), "battery state translated")
    const activeChip = testWindow.find(page, o => o.modelData === "balanced" && o.active === true)
    testWindow.check(!!activeChip, "active profile highlighted")
    page.acceptStatus(__NO_BATTERY_FIXTURE__)
    testWindow.check(!!testWindow.find(page, o => o.text === page.tr("power.noBattery") && o.visible), "no-battery note shown")

    const system = systemLoader.item
    testWindow.check(system.height > 800, "combined maintenance+kernel content is tall")
    testWindow.check(!!testWindow.find(system, o => !!o.text && o.text.indexOf("Werkzeuge helfen bei Problemen") >= 0), "maintenance section content present")
    testWindow.check(!!testWindow.find(system, o => !!o.text && o.text.indexOf("technische Grundlage") >= 0), "kernel section content present")

    preferences.uiLanguage = "en"
    testWindow.check(page.tr("power.battery") === "Battery", "power EN")
    console.log("POWER_SETTINGS_UI_PASS")
   } catch(e) { console.error("POWER_SETTINGS_UI_FAIL", e) }
   Qt.quit()
  } }
 }
}'''.replace('__POWER_FIXTURE__', json.dumps(POWER_FIXTURE)).replace('__NO_BATTERY_FIXTURE__', json.dumps(NO_BATTERY_FIXTURE)))
    runtime = base / 'runtime'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_CONFIG_HOME': str(base / 'config'), 'XDG_CACHE_HOME': str(base / 'cache'),
           'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(profile / 'shell.qml')], env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
    print(result.stdout)
    assert 'POWER_SETTINGS_UI_PASS' in result.stdout
    for error in ['ReferenceError', 'TypeError', 'Failed to load configuration', 'Cannot assign', 'Binding loop', 'POWER_SETTINGS_UI_FAIL']:
        assert error not in result.stdout, error
print('PASS: power settings page (battery/no-battery, profile highlight, i18n) and combined maintenance+kernel page')
