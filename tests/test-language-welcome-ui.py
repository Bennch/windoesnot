#!/usr/bin/env python3
"""Exercise language selection and the welcome window without system changes."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from unittest.mock import patch
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
settings = (SOURCE / 'Settings.qml').read_text()
loader = importlib.machinery.SourceFileLoader('notice', str(ROOT / 'desktop/bin/windoesnot-setup-notice'))
spec = importlib.util.spec_from_loader('notice', loader)
notice = importlib.util.module_from_spec(spec)
loader.exec_module(notice)

with tempfile.TemporaryDirectory(prefix='wdn-language-welcome-') as temp:
    base = Path(temp)
    profile = base / 'profile'
    (profile / 'settings').mkdir(parents=True)
    shutil.copytree(SOURCE / 'i18n', profile / 'i18n')
    shutil.copytree(SOURCE / 'img/brand', profile / 'img/brand')
    for name in ('InputCategory', 'SystemToolsButton'):
        shutil.copy2(SOURCE / f'settings/{name}.qml', profile / 'settings')
    references = set(re.findall(r'settingsMenu\.(\w+)', (SOURCE / 'settings/InputCategory.qml').read_text()))
    references |= {'pendingSystemLocale', 'previousUiLanguage', 'fileDialogOpen'}
    properties = []
    for name in sorted(references - {'selectLanguage'}):
        match = re.search(r'^    property (\w+) ' + name + r': (.+)$', settings, re.M)
        assert match, name
        kind, value = match.groups()
        if kind == 'alias':
            properties.append(f'property var {name}: ListModel {{}}')
        else:
            properties.append(f'property {kind} {name}: ' + ('"de"' if name == 'uiLanguage' else value))
    methods = '\n'.join(re.search(r'    function ' + name + r'\([^\n]*\) \{.*?\n    \}', settings, re.S).group()
                        for name in ('selectLanguage', 'updateSystemLocale', 'finishLanguageChange'))
    (profile / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import "i18n/Lang.js" as Lang
ShellRoot {
 Window {
  id: testWindow; visible: true; width: 900; height: 720
  QtObject { id: localeProc; property var command: []; property bool running: false }
  QtObject { id: settingsMenu; PROPERTIES
METHODS
  }
  Loader { id: input; width: 650; Component.onCompleted: setSource("settings/InputCategory.qml", {settingsMenu:settingsMenu}) }
  function check(ok, message) { if (!ok) throw new Error(message) }
  function find(o,predicate) { if(predicate(o)) return o; for(let c of (o.children || [])) { let r=find(c,predicate); if(r) return r } return null }
  Timer { interval: 100; running: true; onTriggered: {
   try {
    settingsMenu.systemLocalesModel.append({value:"de_DE.UTF-8",text:"Deutsch"})
    settingsMenu.systemLocalesModel.append({value:"en_US.UTF-8",text:"English"})
    settingsMenu.systemLocalesModel.append({value:"fr_FR.UTF-8",text:"français"})
    testWindow.check(input.item !== null, "language page loaded")
    settingsMenu.selectLanguage("en_US.UTF-8")
    testWindow.check(settingsMenu.uiLanguage === "en" && settingsMenu.localeChangeBusy, "English immediately")
    testWindow.check(localeProc.command.join("|") === "localectl|set-locale|LANG=en_US.UTF-8|LC_MESSAGES=en_US.UTF-8|LC_TIME=en_US.UTF-8", "locale, interface and time argv")
    settingsMenu.selectLanguage("fr_FR.UTF-8")
    testWindow.check(settingsMenu.pendingSystemLocale === "en_US.UTF-8", "busy guard")
    settingsMenu.finishLanguageChange(0)
    testWindow.check(settingsMenu.systemLocale === "en_US.UTF-8", "system locale committed")
    const fallback = testWindow.find(input.item,o => o.text === Lang.get("input.languageFallback", "en"))
    testWindow.check(fallback && !fallback.visible, "no warning for English")
    settingsMenu.selectLanguage("de_DE.UTF-8"); settingsMenu.finishLanguageChange(0)
    testWindow.check(settingsMenu.uiLanguage === "de", "German immediately")
    testWindow.check(!fallback.visible, "no warning for German")
    settingsMenu.selectLanguage("fr_FR.UTF-8"); settingsMenu.finishLanguageChange(0)
    testWindow.check(settingsMenu.uiLanguage === "en" && settingsMenu.systemLocale === "fr_FR.UTF-8", "English fallback retains French system locale")
    testWindow.check(fallback.visible, "warning only for unsupported interface language")
    settingsMenu.selectLanguage("de_DE.UTF-8"); settingsMenu.finishLanguageChange(1)
    testWindow.check(settingsMenu.systemLocale === "fr_FR.UTF-8" && settingsMenu.uiLanguage === "en", "failed system change restores previous choice")
    testWindow.check(settingsMenu.localeChangeFailed && !settingsMenu.fileDialogOpen, "failed change visible and focus released")
    settingsMenu.selectLanguage("de_DE.UTF-8"); settingsMenu.finishLanguageChange(0)
    testWindow.check(settingsMenu.uiLanguage === "de" && !fallback.visible && !settingsMenu.localeChangeFailed, "German recovers without fallback warning")
    console.log("LANGUAGE_UI_PASS")
   } catch(e) { console.error("LANGUAGE_UI_FAIL",e) }
   Qt.quit()
  } }
 }
}'''.replace('PROPERTIES', '\n'.join(properties)).replace('METHODS', methods))
    runtime = base / 'runtime'
    runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_CONFIG_HOME': str(base / 'config'),
           'XDG_CACHE_HOME': str(base / 'cache'), 'XDG_RUNTIME_DIR': str(runtime),
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '',
           'DBUS_SESSION_BUS_ADDRESS': ''}

    def run(path, extra, marker):
        result = subprocess.run(['quickshell', '--no-color', '-p', str(path)], env={**env, **extra},
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        assert marker in result.stdout, result.stdout
        for error in ('ReferenceError', 'TypeError', 'Failed to load configuration', 'Cannot assign', 'Binding loop', '_FAIL'):
            assert error not in result.stdout, result.stdout

    if '--welcome-only' not in sys.argv:
        run(profile / 'shell.qml', {}, 'LANGUAGE_UI_PASS')
    welcome = (SOURCE / 'SetupWelcome.qml').read_text()
    # Only add a timer: exercise the actual standalone window, sizing and shared button.
    welcome = welcome.replace('        onClosing: Qt.quit()', '''        onClosing: Qt.quit()
        Component.onCompleted: { width = 920; height = 800 }
        Timer { interval: 100; running: true; onTriggered: {
            if (welcome.width < 600 || welcome.height < 450 || start.text !== welcome.payload.close)
                console.error("WELCOME_UI_FAIL")
            else {
                console.log("WELCOME_UI_PASS")
                const path = Quickshell.env("WINDOESNOT_WELCOME_SCREENSHOT")
                if (path) {
                    welcome.contentItem.grabToImage(function(image) { image.saveToFile(path); Qt.quit() })
                    return
                }
            }
            Qt.quit()
        } }''')
    (profile / 'SetupWelcome.qml').write_text(welcome)
    for language, dark in [('de', 'true'), ('en', 'false')]:
        # A freshly installed image supplies these six launchers.
        with patch.object(notice.shutil, 'which', return_value='/usr/bin/fixture'):
            payload = notice.welcome_payload({'cpu_level': 'v3', 'drivers': 'configured', 'driver_profiles': ['qemu']},
                                             {'uiLanguage': language, 'darkMode': dark})
        for app in payload['apps']:
            icon = profile / app['icon']
            icon.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / app['icon'], icon)
        assert len(payload['lines']) == 3 and payload['dark'] == (dark == 'true')
        assert len(payload['apps']) == 6
        assert all(isinstance(app['command'], list) and isinstance(app['available'], bool) for app in payload['apps'])
        extra = {'WINDOESNOT_WELCOME': json.dumps(payload)}
        screenshots = os.environ.get('WINDOESNOT_TEST_SCREENSHOTS')
        if screenshots:
            Path(screenshots).mkdir(parents=True, exist_ok=True)
            extra['WINDOESNOT_WELCOME_SCREENSHOT'] = str(Path(screenshots).resolve() / f'welcome-{language}.png')
        run(profile / 'SetupWelcome.qml', extra, 'WELCOME_UI_PASS')

print('PASS: welcome window with six apps, DE/EN and dark/light' if '--welcome-only' in sys.argv else 'PASS: one language choice, DE/EN, French fallback, failure recovery; welcome window DE/EN and dark/light')
