#!/usr/bin/env python3
"""Load the full Appearance page through Quickshell's actual virtual filesystem."""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'desktop/config/quickshell/default'
settings_source = (BASE / 'Settings.qml').read_text()
page_source = (BASE / 'settings/AppearanceCategory.qml').read_text()
references = set(re.findall(r'settingsMenu\.([A-Za-z_]\w*)', page_source + (BASE / 'settings/StartOrbSettings.qml').read_text()))
references.add('uiLanguage')
properties = []
for name in sorted(references):
    match = re.search(r'^    property (\w+) ' + name + r': (.+)$', settings_source, re.M)
    assert match, name
    kind, value = match.groups()
    if kind == 'alias':
        properties.append('property var ' + name + ': ListModel {}')
    else:
        properties.append('property ' + kind + ' ' + name + ': ' + value)

with tempfile.TemporaryDirectory(prefix='wdn-appearance-loader-') as temporary:
    directory = Path(temporary)
    config = directory / 'profile'
    shutil.copytree(BASE, config)
    runtime = directory / 'run'; runtime.mkdir(mode=0o700)
    fixture = '''import Quickshell
import QtQuick
import QtQuick.Window
ShellRoot {
    Window {
        visible: true; width: 900; height: 720
        QtObject {
            id: prefs
            ''' + '\n            '.join(properties) + '''
        }
        Loader {
            id: page
            width: 600
            Component.onCompleted: setSource("settings/AppearanceCategory.qml", {"settingsMenu": prefs})
            onStatusChanged: if (status === Loader.Error) Qt.exit(2)
        }
        Timer { interval: 400; running: true; onTriggered: {
            if (!page.item || page.item.height < 500) { Qt.exit(3); return }
            var found = false
            for (var i = 0; i < page.item.children.length; i++) {
                var child = page.item.children[i]
                if (child.hasOwnProperty("importFailed")) {
                    if (child.settingsMenu !== prefs || child.width < 100 || child.height < 100) { Qt.exit(4); return }
                    found = true
                }
            }
            if (!found) { Qt.exit(5); return }
            console.log("APPEARANCE_LOADER_READY"); Qt.quit()
        } }
    }
}
'''
    (config / 'shell.qml').write_text(fixture)
    env = {**os.environ, 'HOME': str(directory), 'XDG_CONFIG_HOME': str(directory / '.config'), 'XDG_CACHE_HOME': str(directory / '.cache'), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-bus'), 'HYPRLAND_INSTANCE_SIGNATURE': 'appearance-isolated'}
    env.pop('WAYLAND_DISPLAY', None); env.pop('DISPLAY', None)
    def run():
        p = subprocess.Popen(['quickshell', '--no-color', '--path', str(config / 'shell.qml')], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            output = p.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            output = p.communicate()[0]
            raise AssertionError(output)
        return p.returncode, output
    code, output = run()
    (ROOT / 'checks/appearance-loader.log').write_text(output)
    assert code == 0 and 'APPEARANCE_LOADER_READY' in output, output
    for marker in ['ReferenceError', 'TypeError', 'is not a type', 'Failed to load configuration', 'Cannot assign']:
        assert marker not in output, output
    # Prove the fixture exercises the actual old failure, not a direct directory import.
    (config / 'settings/AppearanceCategory.qml').write_text(page_source.replace('import "."\n', '', 1))
    (config / 'settings/qmldir').unlink()
    code, old_output = run()
    assert code != 0 and 'StartOrbSettings is not a type' in old_output, old_output
    print('PASS: full Appearance page and orb controls load through dynamic Loader; original missing-import regression detected')
