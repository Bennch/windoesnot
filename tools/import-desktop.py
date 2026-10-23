#!/usr/bin/env python3
"""Import selected desktop sources, keeping private state outside the release."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
CONFIG = ROOT / 'desktop/config'
SKIP = {'.git', 'build', 'CMakeFiles', '__pycache__', 'backup', 'backups', 'node_modules', 'accent-color-change'}
CODE = {'.qml', '.js', '.py', '.sh', '.cpp', '.hpp', '.h', '.desktop', '.hook', '.service', '.conf'}
PRIVATE = {'calendar_notes.json', 'copilot-state.json', 'icon-map.json', 'settings.txt', 'pinned.txt', 'taskbar.txt', 'taskbar_order.txt', 'icons.json', 'state.lua', 'state.json', 'state.lock'}
ALIASES = {
    str(HOME / '.config/hypr/lua/bin/hypr-bridge'): 'windoesnot-hyprctl',
    str(HOME / '.config/hypr/lua/bin/hypr-state'): 'windoesnot-settings',
}


def portable(text, relative):
    for old, new in ALIASES.items():
        text = text.replace(old, new)
    if relative.endswith('.qml'):
        text = text.replace('"file://' + str(HOME) + '/.config/quickshell/default/widgets/terminalmodule/LocalTerminal"', '"terminalmodule/LocalTerminal"')
        # Python fragments embedded in QML strings use Python home expansion,
        # while ordinary QML expressions use the process's real HOME.
        text = re.sub(r"'/home/benni([^']*)'", lambda m: "(__import__('os').path.expanduser('~" + m[1] + "'))", text)
        text = re.sub(r'"/home/benni([^"\n]*)"', lambda m: 'Quickshell.env("HOME") + "' + m[1] + '"', text)
        text = text.replace('cd /home/benni/docker/ollama && docker compose ', 'cd \\"$HOME/docker/ollama\\" && docker compose ')
        # Generated QML is kept free of user-specific paths by using $HOME in
        # its already-existing bash command string.
        text = text.replace('/home/benni/.config/hypr/hide_windows.sh', '$HOME/.config/hypr/hide_windows.sh')
        if 'Quickshell.env(' in text and not re.search(r'^import Quickshell\s*$', text, re.M):
            text = 'import Quickshell\n' + text
    elif relative.endswith('.py'):
        text = re.sub(r"'/home/benni([^']*)'", lambda m: "(__import__('os').path.expanduser('~" + m[1] + "'))", text)
        text = re.sub(r'"/home/benni([^"\n]*)"', lambda m: '(__import__("os").path.expanduser("~' + m[1] + '"))', text)
    return text


def copy_tree(source, destination, kind):
    records = []
    for base, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.')]
        for name in files:
            path = Path(base) / name
            rel = path.relative_to(source)
            if name in PRIVATE or name.endswith(('.backup', '.bak', '.old', '.pyc', '.so')):
                continue
            asset = kind == 'shell' and rel.parts[0] == 'img'
            include = asset or path.suffix in CODE or name in {'CMakeLists.txt', 'qmldir', 'LICENSE', 'LICENSE.txt'}
            if not include or path.is_symlink():
                continue
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not asset and path.suffix in CODE | {'.lua'}:
                target.write_text(portable(path.read_text(), str(rel)))
                shutil.copymode(path, target)
            else:
                shutil.copy2(path, target)
            records.append({'source': str(path), 'target': str(target.relative_to(ROOT)), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def main():
    if (ROOT / 'desktop/import-manifest.json').exists():
        raise SystemExit('Import already exists. Keep canonical edits; do not overwrite from the live system.')
    CONFIG.mkdir(parents=True, exist_ok=True)
    records = []
    for relative, kind in [('quickshell/default', 'shell'), ('quickshell/overview', 'overview'), ('hyprdesk', 'desktop')]:
        records += copy_tree(HOME / '.config' / relative, CONFIG / relative, kind)
    copilot = CONFIG / 'quickshell/copilot'
    copilot.mkdir(parents=True, exist_ok=True)
    for name in ['openclaw_pair.py', 'openclaw_models_multi.py', 'openclaw_chat.py', 'openclaw_agent_chat.py']:
        source = HOME / '.config/quickshell/copilot' / name
        if source.exists():
            (copilot / name).write_text(portable(source.read_text(), name))
    records += copy_tree(HOME / '.config/hypr/scripts', CONFIG / 'hypr/scripts', 'scripts')
    for name in ('hide_windows.sh', 'toggle-maximize.sh'):
        source = HOME / '.config/hypr' / name
        target = CONFIG / 'hypr' / name
        target.write_text(portable(source.read_text(), name))
        shutil.copymode(source, target)
    # Lua source is small; state files are imported separately as clean defaults.
    for source in (HOME / '.config/hypr/lua').glob('*.lua'):
        if source.name == 'state.lua':
            continue
        target = CONFIG / 'hypr/lua' / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(portable(source.read_text(), source.name))
    for source in (HOME / '.config/hypr/lua/bin').glob('*'):
        if not source.is_file() or source.suffix == '.pyc':
            continue
        target = CONFIG / 'hypr/lua/bin' / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(portable(source.read_text(), source.name))
        shutil.copymode(source, target)
    shutil.copy2(HOME / '.config/hypr/hyprland.lua', CONFIG / 'hypr/hyprland.lua')
    plugins = ROOT / 'desktop/plugins'
    for name in ('hyprbars', 'hyprdrag'):
        source = HOME / '.config/hypr/migration-work/lua/plugins' / name
        shutil.copytree(source, plugins / name, ignore=shutil.ignore_patterns('*.so', '*.o', '.git', 'build'))
    (ROOT / 'desktop/import-manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Imported {len(records)} source/asset files; host unchanged')


if __name__ == '__main__':
    main()
