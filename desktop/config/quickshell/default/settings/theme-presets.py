#!/usr/bin/env python3
"""Save one pre-look snapshot and update the existing hyprpaper configuration."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'windoesnot/theme-preset.json'
wallpaper_config = config / 'hypr/hyprpaper.conf'
looks_file = config / 'windoesnot/looks.json'
action = sys.argv[1]


def current_wallpaper():
    try:
        match = re.search(r'(?m)^\s*path\s*=\s*(\S.*?)\s*$', wallpaper_config.read_text())
        return match.group(1) if match else ''
    except OSError:
        return ''


def saved_looks():
    try:
        data = json.loads(looks_file.read_text())
        return [item for item in data if isinstance(item, dict) and item.get('name')] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


if action == 'list':
    print(json.dumps(saved_looks()))
    raise SystemExit(0)
if action == 'save':
    # save <name> <json with darkMode, accentColor, borderRadius>: the current wallpaper is stored with it
    name = sys.argv[2].strip()[:40]
    values = json.loads(sys.argv[3])
    if not name:
        raise SystemExit('Name missing')
    entry = {'name': name, 'darkMode': bool(values['darkMode']), 'accentColor': str(values['accentColor']),
             'borderRadius': int(values['borderRadius']), 'wallpaperPath': current_wallpaper()}
    looks = [item for item in saved_looks() if item['name'] != name] + [entry]
    looks_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = looks_file.with_suffix('.tmp')
    temporary.write_text(json.dumps(looks, indent=1))
    temporary.replace(looks_file)
    print(json.dumps(looks))
    raise SystemExit(0)
if action == 'delete':
    looks = [item for item in saved_looks() if item['name'] != sys.argv[2]]
    looks_file.parent.mkdir(parents=True, exist_ok=True)
    looks_file.write_text(json.dumps(looks, indent=1))
    print(json.dumps(looks))
    raise SystemExit(0)
if action == 'apply':
    values = json.loads(sys.argv[2])
    wallpaper = sys.argv[3]
    if wallpaper and not Path(wallpaper).is_file():
        raise SystemExit('Wallpaper missing')
    original = wallpaper_config.read_text() if wallpaper_config.exists() else None
    if not state.exists():
        state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(state, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'values': values, 'wallpaperConfig': original}, stream)
    if not wallpaper:
        raise SystemExit(0)
    content = original or 'splash = false\n\nwallpaper {\n    monitor =\n    path =\n    fit_mode = cover\n}\n'
    # Change only paths inside wallpaper blocks, retaining all monitor assignments.
    def replace_block(match):
        block = match.group(0)
        return re.sub(r'(?m)^(\s*path\s*=).*$', lambda m: m.group(1) + ' ' + wallpaper, block)
    content, count = re.subn(r'(?ms)^\s*wallpaper\s*\{[^}]*\}', replace_block, content)
    if not count:
        content += '\nwallpaper {\n    monitor =\n    path = ' + wallpaper + '\n    fit_mode = cover\n}\n'
    wallpaper_config.parent.mkdir(parents=True, exist_ok=True)
    wallpaper_config.write_text(content)
elif action == 'restore':
    snapshot = json.loads(state.read_text())
    if snapshot['wallpaperConfig'] is None:
        wallpaper_config.unlink(missing_ok=True)
    else:
        wallpaper_config.parent.mkdir(parents=True, exist_ok=True)
        wallpaper_config.write_text(snapshot['wallpaperConfig'])
    print(json.dumps(snapshot['values']))
    state.unlink()
else:
    raise SystemExit('Unknown action')
# The installed system has windoesnot-wallpaper (swaybg); a host session may only run hyprpaper, which re-reads its
# config on restart. A missing tool must never make the whole look fail after the files were already written.
import shutil
try:
    if shutil.which('windoesnot-wallpaper'):
        subprocess.Popen(['windoesnot-wallpaper', '--restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which('hyprpaper') and subprocess.run(['pgrep', '-x', 'hyprpaper'], stdout=subprocess.DEVNULL).returncode == 0:
        subprocess.run(['pkill', '-x', 'hyprpaper'], stdout=subprocess.DEVNULL)
        subprocess.Popen(['hyprpaper'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
except OSError as error:
    print('wallpaper restart skipped:', error, file=sys.stderr)
