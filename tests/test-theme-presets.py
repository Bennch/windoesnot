#!/usr/bin/env python3
"""Check look definitions, translations and the private wallpaper snapshot."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
settings = root / 'desktop/config/quickshell/default/settings'
source = (settings / 'LookData.js').read_text()
rows = re.findall(r'\{\s*nameDe: "([^"]+)", nameEn: "([^"]+)", darkMode: (true|false), accentColor: "(#[0-9A-Fa-f]{6})", borderRadius: (\d+), wallpaper: "([^"]+)"\s*\}', source)
assert 6 <= len(rows) <= 8
assert len(rows) == source.count('nameDe:')
for de, en, dark, color, radius, wallpaper in rows:
    assert de and en and dark in ('true', 'false') and re.fullmatch(r'#[0-9a-fA-F]{6}', color)
    assert 0 <= int(radius) <= 30
    assert (root / 'desktop/share/backgrounds/windoesnot' / wallpaper).is_file()
translations = []
for lang in ('de', 'en'):
    text = (settings.parent / 'i18n' / (lang + '.js')).read_text()
    translations.append(set(re.findall(r'"(looks\.[^"]+)"\s*:', text)))
assert translations[0] == translations[1] == {'looks.title', 'looks.restore', 'looks.error'}

with tempfile.TemporaryDirectory() as tmp:
    temp = Path(tmp)
    config = temp / 'config'
    state = temp / 'state'
    bin_dir = temp / 'bin'
    bin_dir.mkdir()
    restart = bin_dir / 'windoesnot-wallpaper'
    restart.write_text('#!/bin/sh\nexit 0\n')
    restart.chmod(0o755)
    env = dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state), PATH=str(bin_dir))
    conf = config / 'hypr/hyprpaper.conf'
    conf.parent.mkdir(parents=True)
    original = 'splash = false\nwallpaper {\n monitor = A\n path = /old one.jpg\n}\nwallpaper {\n monitor = B\n path = /old-two.jpg\n}\n'
    conf.write_text(original)
    image = temp / 'look.jpg'
    image.touch()
    values = {'darkMode': True, 'accentColor': '#123456', 'borderRadius': 7}
    def run(*args):
        return subprocess.run(['/usr/bin/python3', str(settings / 'theme-presets.py'), *args], env=env, check=True, capture_output=True, text=True)
    run('apply', json.dumps(values), str(image))
    assert conf.read_text().count('path = ' + str(image)) == 2
    run('apply', json.dumps({'darkMode': False}), str(image))
    assert json.loads(run('restore').stdout) == values
    assert conf.read_text() == original
    assert not (state / 'windoesnot/theme-preset.json').exists()
print('theme presets: OK')
