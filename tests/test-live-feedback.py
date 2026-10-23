#!/usr/bin/env python3
"""Exercise real settings pages, live backup guard and translation initialization."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
shell = (ROOT / 'desktop/config/quickshell/default/shell.qml').read_text()
assert 'icon: "img/keys.svg"' not in shell, 'Personal Custom Keys launcher leaked into release'
BASE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-live-feedback-') as temporary:
    directory = Path(temporary)
    config = directory / 'profile'; shutil.copytree(BASE, config)
    runtime = directory / 'run'; runtime.mkdir(mode=0o700)
    binpath = directory / 'bin'; binpath.mkdir()
    # An isolated live probe: unexpected privileged/snapper calls leave evidence.
    for command, body in [('sh', 'exit 10'), ('pkexec', 'echo unexpected >> "' + str(directory / 'unexpected') + '"; exit 1'), ('snapper', 'echo unexpected >> "' + str(directory / 'unexpected') + '"; exit 1')]:
        p = binpath / command; p.write_text('#!/bin/bash\n' + body + '\n'); p.chmod(0o755)
    source = (BASE / 'Settings.qml').read_text()
    references = set(re.findall(r'settingsMenu\.([A-Za-z_]\w*)', (BASE / 'settings/AppsCategory.qml').read_text() + (BASE / 'settings/BackupsCategory.qml').read_text()))
    references |= {'showDockerTray', 'showOllamaTray', 'keyboardLayout'}
    properties = []
    for name in sorted(references):
        if name in ('saveAppOverride', 'deleteAppOverride'):
            properties.append('function ' + name + '() {}'); continue
        if name == 'visible':
            properties.append('property bool visible: false'); continue
        match = re.search(r'^    property (\w+) ' + name + r': (.+)$', source, re.M)
        assert match, name
        kind, value = match.groups()
        if kind == 'alias': properties.append('property var ' + name + ': ListModel {}')
        else: properties.append('property ' + kind + ' ' + name + ': ' + ('"de"' if name == 'uiLanguage' else value))
    ipc = source[source.index('    IpcHandler {'):source.index('    function finishLoadingSettings()')]
    ipc = ipc.replace('    IpcHandler {', '    IpcHandler { id: settingsIpc', 1)
    pinning = re.search(r'    function pinIndex\(appName, aliases\) \{.*?\n    \}', shell, re.S).group()
    properties += ['property var pinnedAppNames: ["Firefox", "Files", "Ghostty"]', pinning]
    finish = re.search(r'    function finishLoadingSettings\(\) \{.*?\n    \}', source, re.S).group()
    assert "'settingsMenu.finishLoadingSettings(); ' +" in source
    properties += ['property bool isLoadingSettings: true', 'property var panelWindow: null', finish]
    (config / 'shell.qml').write_text('''import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Window
import "i18n/Lang.js" as Lang
ShellRoot {
    Window {
        visible: true; width: 900; height: 720
        QtObject { id: settingsMenu; ''' + '\n'.join(properties) + ''' }
''' + ipc + '''
        Image { id: trayArrow; source: "img/project/chevron-up.svg"; width: 16; height: 16 }
        Loader { id: apps; width: 600; Component.onCompleted: setSource("settings/AppsCategory.qml", {"settingsMenu": settingsMenu}) }
        Loader { id: backups; width: 600; visible: false; Component.onCompleted: setSource("settings/BackupsCategory.qml", {"settingsMenu": settingsMenu}) }
        Timer { interval: 800; running: true; onTriggered: {
            if (trayArrow.status !== Image.Ready) { Qt.exit(8); return }
            if (!apps.item || !backups.item || apps.item.height < 100) { Qt.exit(2); return }
            if (!backups.item.liveSession || backups.item.backupsReady || backups.item.busy) { Qt.exit(3); return }
            backups.item.runAction("create", {}, false)
            if (backups.item.busy) { Qt.exit(4); return }
            if (settingsMenu.showDockerTray || settingsMenu.showOllamaTray) { Qt.exit(5); return }
            Qt.createQmlObject('import QtQml; QtObject { Component.onCompleted: settingsMenu.finishLoadingSettings() }', settingsMenu)
            if (settingsMenu.isLoadingSettings) { Qt.exit(9); return }
            if (settingsMenu.pinIndex("Dateien", ["Files", "Dateien"]) !== 1) { Qt.exit(10); return }
            if (settingsMenu.pinIndex("Firefox", ["Firefox"]) !== 0) { Qt.exit(11); return }
            if (settingsMenu.pinIndex("Unpinned", ["Unpinned"]) !== -1) { Qt.exit(12); return }
            if (settingsIpc.setKeyboardLayout("de") !== "de" || settingsMenu.keyboardLayout !== "de") { Qt.exit(13); return }
            if (settingsIpc.setKeyboardLayout("ru,us") !== "ru,us") { Qt.exit(14); return }
            if (settingsIpc.setKeyboardLayout("de;reboot") !== "unsupported" || settingsMenu.keyboardLayout !== "ru,us") { Qt.exit(15); return }
            Lang.setCurrent("en")
            if (Lang.get("nav.settings", "de") !== "Einstellungen") { Qt.exit(6); return }
            Lang.setCurrent("de")
            if (Lang.get("nav.settings", "en") !== "Settings") { Qt.exit(7); return }
            console.log("LIVE_FEEDBACK_READY"); Qt.quit()
        } }
    }
}
''')
    env = {**os.environ, 'PATH': str(binpath) + ':' + os.environ['PATH'], 'HOME': str(directory), 'XDG_CONFIG_HOME': str(directory / '.config'), 'XDG_CACHE_HOME': str(directory / '.cache'), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-bus'), 'HYPRLAND_INSTANCE_SIGNATURE': 'feedback-isolated'}
    env.pop('WAYLAND_DISPLAY', None); env.pop('DISPLAY', None)
    p = subprocess.Popen(['quickshell', '--no-color', '--path', str(config / 'shell.qml')], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try: output = p.communicate(timeout=12)[0]
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM); output = p.communicate()[0]; raise AssertionError(output)
    (ROOT / 'checks/live-feedback.log').write_text(output)
    assert p.returncode == 0 and 'LIVE_FEEDBACK_READY' in output, output
    assert not (directory / 'unexpected').exists(), 'Live backups invoked a privileged command'
    for marker in ['ReferenceError', 'TypeError', 'is not a type', 'Failed to load configuration', 'Cannot assign']:
        assert marker not in output, output
    sys.path.insert(0, str(ROOT / 'iso/software'))
    spec = importlib.util.spec_from_file_location('prepare_apps', ROOT / 'iso/software/prepare.py'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    staged = directory / 'build-dns'; resolver = directory / 'resolv.conf'
    resolver.write_text('# clean image resolver\n'); staged.write_text('nameserver 127.0.0.53\n')
    try:
        with module.build_resolver(staged, resolver):
            assert resolver.read_text() == 'nameserver 127.0.0.53\n'
            assert not staged.exists()
            raise RuntimeError('simulated failed download')
    except RuntimeError: pass
    assert resolver.read_text() == '# clean image resolver\n'
    import runpy
    launchers = runpy.run_path(str(ROOT / 'desktop/bin/windoesnot-list-apps'))['launchers']
    applications = directory / 'applications'; applications.mkdir()
    (applications / 'sample.desktop').write_text('[Desktop Entry]\nType=Application\nName=Files\nName[de]=Dateien\nExec=files %U\nIcon=files\n[Desktop Action other]\nName=Do not use this name\n')
    assert launchers([applications], 'de_DE.UTF-8') == ['Dateien|files|files']
    assert launchers([applications], 'en') == ['Files|files|files']
    structured = launchers([applications], 'de', True)
    assert structured[0]['name'] == 'Dateien' and structured[0]['names'] == ['Dateien', 'Files']
    assert structured[0]['id'] == 'sample.desktop'
    user = directory / 'user-apps'; user.mkdir()
    (user / 'sample.desktop').write_text('[Desktop Entry]\nHidden=true\n')
    assert launchers([user, applications], 'de') == []
    import ast
    tree = ast.parse((ROOT / 'desktop/config/hyprdesk/hyprdesk.py').read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'parse_desktop_file')
    namespace = {'debug': lambda *a, **k: None, 'sys': sys}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<desktop-parser>', 'exec'), namespace)
    parse_desktop = namespace['parse_desktop_file']
    assert parse_desktop(applications / 'sample.desktop', 'de')['name'] == 'Dateien'
    assert parse_desktop(applications / 'sample.desktop', 'en')['name'] == 'Files'
    branding = __import__('runpy').run_path(str(ROOT / 'iso/brand-installer.py'))['apply']
    image = directory / 'image'; entry = image / 'usr/share/applications/calamares.desktop'
    entry.parent.mkdir(parents=True); entry.write_text('[Desktop Entry]\nName=Install System\nExec=calamares\nIcon=calamares\n')
    branding(image)
    alias = entry.with_name('io.calamares.calamares.desktop')
    assert alias.read_bytes() == entry.read_bytes()
    assert 'NoDisplay=true' in alias.read_text() and 'Icon=windoesnot' in alias.read_text()
    assert launchers([entry.parent], 'de') == []

print('PASS: Apps/Backups dynamic loaders, optional tools off by default, live backup guard, independent DE/EN bindings, build DNS cleanup on failure')
