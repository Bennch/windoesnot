#!/usr/bin/env python3
"""TrayIconImage measures a tray icon and lifts a near-black one on the dark bar / lowers a white one on the light bar (offscreen)."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
source = root / 'desktop/config/quickshell/default'

def make(path, background, glyph):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 6, 58, 58), fill=background)
    draw.rectangle((22, 20, 42, 26), fill=glyph); draw.rectangle((22, 30, 42, 36), fill=glyph); draw.rectangle((22, 40, 42, 46), fill=glyph)
    image.save(path)

with tempfile.TemporaryDirectory(prefix='wdn-tray-icon-') as tmp:
    base = Path(tmp)
    shutil.copy(source / 'TrayIconImage.qml', base / 'TrayIconImage.qml')
    make(base / 'dark.png', (24, 24, 24, 255), (12, 12, 12, 255))        # Spotify-like: dark disc, darker bars
    make(base / 'normal.png', (235, 120, 40, 255), (255, 255, 255, 255))  # colourful, bright
    make(base / 'white.png', (250, 250, 250, 255), (235, 235, 235, 255))  # white glyph
    (base / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 Window { id: win; visible: true; width: 200; height: 60
  property bool dark: true
  Row { spacing: 4
   TrayIconImage { id: dark; source: "file://''' + str(base) + '''/dark.png"; darkBar: win.dark }
   TrayIconImage { id: normal; source: "file://''' + str(base) + '''/normal.png"; darkBar: win.dark }
   TrayIconImage { id: white; source: "file://''' + str(base) + '''/white.png"; darkBar: win.dark }
   TrayIconImage { id: off; source: "file://''' + str(base) + '''/dark.png"; darkBar: win.dark; autoContrast: false }
  }
  property int step: 0
  Timer { interval: 700; running: true; repeat: true; onTriggered: {
    if (!dark.measured || !normal.measured || !white.measured) { console.log("WAIT"); return }
    if (win.step === 0) {
      console.log("DARKBAR", dark.luminance.toFixed(2), dark.adjusted, normal.adjusted, white.adjusted, off.adjusted)
      win.dark = false
    } else if (win.step === 1) {
      console.log("LIGHTBAR", dark.adjusted, normal.adjusted, white.adjusted, white.adjustment < 0)
      console.log("TRAY_DONE"); Qt.quit(); return
    }
    win.step++
  } }
 }
}''')
    runtime = base / 'run'; runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(base / 'shell.qml')], env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=15)
    print(result.stdout)
    lines = {line.split()[2]: line.split()[3:] for line in result.stdout.splitlines() if ' qml: DARKBAR' in line or ' qml: LIGHTBAR' in line}
    assert 'TRAY_DONE' in result.stdout, 'test did not finish'
    d = lines['DARKBAR']; assert float(d[0]) < 0.30 and d[1:] == ['true', 'false', 'false', 'false'], d
    l = lines['LIGHTBAR']; assert l == ['false', 'false', 'true', 'true'], l
print('PASS: tray icons: dark icons lifted on the dark bar, white ones lowered on the light bar, normal ones untouched')
