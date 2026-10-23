#!/usr/bin/env python3
"""Load the real SDDM greeter in test mode, without a display-manager service."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--greeter', type=Path, default=Path('/usr/bin/sddm-greeter-qt6'))
parser.add_argument('--imports', type=Path, help='QML import directory when using an unpacked target package')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='windoesnot-greeter-test-') as tmp:
    directory = Path(tmp)
    runtime = directory / 'run'; runtime.mkdir(mode=0o700)
    theme = directory / 'theme'
    shutil.copytree(ROOT / 'desktop/share/sddm/themes/windoesnot', theme)
    main = theme / 'Main.qml'
    main.write_text(main.read_text().replace('file:///usr/share/windoesnot/branding/windoesnot-logo-hell.png', (ROOT / 'desktop/config/quickshell/default/img/brand/windoesnot-logo-hell.png').as_uri()))
    screenshot = directory / 'greeter.png'
    # A rendered image proves the selected theme initialized, even when SDDM's
    # own logging handler sends messages to the journal instead of stdout.
    timer = '    Timer { interval: 500; running: true; onTriggered: { container.grabToImage(function(result) { result.saveToFile(' + __import__('json').dumps(str(screenshot)) + ') }) } }\n'
    main.write_text(main.read_text().replace('    Component.onCompleted:', timer + '    Component.onCompleted:'))
    env = {**os.environ, 'HOME': tmp, 'XDG_CONFIG_HOME': str(directory / '.config'), 'XDG_CACHE_HOME': str(directory / '.cache'), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-bus')}
    env.pop('WAYLAND_DISPLAY', None); env.pop('DISPLAY', None)
    if args.imports:
        env['QML_IMPORT_PATH'] = str(args.imports.resolve())
    p = subprocess.Popen([str(args.greeter.resolve()), '--test-mode', '--theme', str(theme)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        output = p.communicate(timeout=3)[0]
        raise AssertionError('Greeter exited early: ' + output)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)
        output = p.communicate(timeout=5)[0]
    (ROOT / 'checks/branding-sddm.log').write_text(output)
    assert screenshot.is_file() and screenshot.stat().st_size > 1000, 'Selected theme did not render'
    shutil.copy2(screenshot, ROOT / 'checks/branding-sddm-preview.png')
    for marker in ['ReferenceError', 'TypeError', 'Cannot assign', 'is not a type', 'failed to load', 'cannot open', 'no such file']:
        assert marker.lower() not in output.lower(), output
    print('PASS: real SDDM test greeter loads branded theme; no authentication or system service changed')
