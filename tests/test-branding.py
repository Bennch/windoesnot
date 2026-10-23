#!/usr/bin/env python3
"""Exercise local-image import and render branding without desktop/session IPC."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='windoesnot-branding-test-') as temporary:
    directory = Path(temporary)
    runtime = directory / 'run'
    runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(directory), 'XDG_CONFIG_HOME': str(directory / '.config'), 'XDG_CACHE_HOME': str(directory / '.cache'), 'XDG_DATA_HOME': str(directory / '.local/share'), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-bus'), 'HYPRLAND_INSTANCE_SIGNATURE': 'branding-isolated'}
    env.pop('WAYLAND_DISPLAY', None)
    env.pop('DISPLAY', None)
    # Filename characters stay encoded in the stored URL; settings.txt uses '='.
    original = directory / "my orb = ü ' image.png"
    original.write_bytes((BASE / 'img/brand/windoesnot-icon-128.png').read_bytes())
    command = [str(ROOT / 'desktop/bin/windoesnot-import-orb')]
    imported = subprocess.check_output([*command, original.as_uri()], env=env, text=True).strip()
    from urllib.parse import unquote, urlsplit
    copied = Path(unquote(urlsplit(imported).path))
    assert copied.read_bytes() == original.read_bytes()
    original.unlink()
    assert copied.exists() and '=' not in imported
    rejected = subprocess.run([*command, 'https://example.invalid/icon.png'], env=env, capture_output=True)
    assert rejected.returncode != 0
    bad = directory / 'invalid.png'; bad.write_text('not an image')
    assert subprocess.run([*command, bad.as_uri()], env=env, capture_output=True).returncode != 0
    assert not list(copied.parent.glob('.orb-*'))
    fixture = directory / 'shell.qml'
    fixture.write_text('''import Quickshell
import QtQuick
import QtQuick.Window
import "''' + (BASE / 'widgets').as_uri() + '''" as Widgets
import "''' + (BASE / 'settings').as_uri() + '''" as Settings
ShellRoot {
    Window {
        id: preview
        visible: true
        width: 900; height: 720
        color: prefs.darkMode ? "#202024" : "#f4f1eb"
        QtObject {
            id: prefs
            property bool darkMode: true
            property string uiLanguage: "de"
            property color accentColor: "#fe6f2d"
            property int borderRadius: 6
            property string startOrbStyle: "classic"
            property string startOrbCustomSource: ""
            property bool fileDialogOpen: false
        }
        Widgets.StartOrb { id: orb; x: 20; y: 20; width: 64; height: 64 }
        Settings.StartOrbSettings { x: 120; y: 20; width: 550; settingsMenu: prefs }
        Settings.AboutCategory { id: about; x: 120; y: 220; width: 550; settingsMenu: prefs }
        Timer {
            interval: 300; running: true; repeat: true
            property int phase: 0
            onTriggered: {
                function checkLogo(item) {
                    if (item.source && item.source.toString().indexOf("windoesnot-logo-") >= 0 && item.status !== Image.Ready) throw new Error("About logo missing")
                    if (item.children) for (var i = 0; i < item.children.length; i++) checkLogo(item.children[i])
                }
                checkLogo(about)
                var image = orb.children[0]
                var fallback = orb.children[1]
                if (phase === 0) {
                    if (orb.style !== "classic" || image.status !== Image.Ready) throw new Error("Original orb missing")
                    orb.style = "dot"
                } else if (phase === 1) {
                    if (image.status !== Image.Ready || image.source.toString().indexOf("windoesnot-icon-128.png") < 0) throw new Error("Dot missing")
                    orb.customSource = ''' + json.dumps(imported) + '''; orb.style = "custom"
                } else if (phase === 2) {
                    if (image.status !== Image.Ready) throw new Error("Custom orb missing")
                    orb.customSource = "file:///does-not-exist/orb.png"
                } else if (phase === 3) {
                    if (!fallback.visible || fallback.status !== Image.Ready) throw new Error("Original fallback missing")
                    prefs.darkMode = false
                } else {
                    console.log("BRANDING_READY")
                    preview.contentItem.grabToImage(function(result) {
                        result.saveToFile(''' + json.dumps(str(ROOT / 'checks/branding-preview.png')) + ''')
                        Qt.quit()
                    })
                    stop()
                }
                phase += 1
            }
        }
    }
}
''')
    p = subprocess.Popen(['quickshell', '--no-color', '--path', str(fixture)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        output = p.communicate(timeout=12)[0]
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)
        output = p.communicate()[0]
        raise AssertionError(output)
    (ROOT / 'checks/branding-qml.log').write_text(output)
    assert p.returncode == 0 and 'BRANDING_READY' in output, output
    for marker in ['ReferenceError', 'TypeError', 'Failed to load configuration', 'Cannot assign', 'Error:']:
        assert marker not in output, output
    print('PASS: classic/dot/custom orbs, missing-file fallback, native chooser component, About logo in light/dark, local import with special characters')
