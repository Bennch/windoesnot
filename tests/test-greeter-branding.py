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
PRESETS = ['cinder-still', 'fire', 'glut-dunkel', 'cinder']
THEME = ROOT / 'desktop/share/sddm/themes/windoesnot'
for preset in PRESETS:
  with tempfile.TemporaryDirectory(prefix='windoesnot-greeter-test-') as tmp:
    directory = Path(tmp)
    runtime = directory / 'run'; runtime.mkdir(mode=0o700)
    theme = directory / 'theme'
    shutil.copytree(THEME, theme)
    # A variant is a theme.conf.user next to theme.conf, exactly as the settings write it.
    shutil.copy2(theme / 'presets' / (preset + '.conf'), theme / 'theme.conf.user')
    main = theme / 'src/Main.qml'
    screenshot = directory / 'greeter.png'
    # A rendered image proves the theme initialized, even when SDDM logs to the journal.
    timer = '    Timer { interval: 1500; running: true; onTriggered: root.grabToImage(function(result) { result.saveToFile(' + __import__('json').dumps(str(screenshot)) + ') }) }\n'
    main.write_text(main.read_text().replace('    focus: true\n', '    focus: true\n' + timer, 1))
    env = {**os.environ, 'HOME': tmp, 'XDG_CONFIG_HOME': str(directory / '.config'), 'XDG_CACHE_HOME': str(directory / '.cache'), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-bus')}
    env.pop('WAYLAND_DISPLAY', None); env.pop('DISPLAY', None)
    if args.imports:
        env['QML_IMPORT_PATH'] = str(args.imports.resolve())
    p = subprocess.Popen([str(args.greeter.resolve()), '--test-mode', '--theme', str(theme)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        output = p.communicate(timeout=4)[0]
        raise AssertionError('Greeter exited early: ' + output)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)
        output = p.communicate(timeout=5)[0]
    (ROOT / f'checks/branding-sddm-{preset}.log').write_text(output)
    assert screenshot.is_file() and screenshot.stat().st_size > 1000, preset + ': theme did not render'
    shutil.copy2(screenshot, ROOT / f'checks/branding-sddm-{preset}.png')
    for marker in ['ReferenceError', 'TypeError', 'Cannot assign', 'is not a type', 'failed to load', 'cannot open', 'no such file']:
        assert marker.lower() not in output.lower(), (preset, output)
print('PASS: real SDDM test greeter renders all WinDoesNot presets; no authentication or system service changed')
