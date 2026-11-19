#!/usr/bin/env python3
"""The snap manager must know the same apps as the hyprbars rules that remove our title bar (own-bar apps)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
qml = (ROOT / 'desktop/config/quickshell/default/SnapManager.qml').read_text()
lua = (ROOT / 'desktop/config/hypr/lua/reference.lua').read_text()

qml_list = set(re.search(r'ownBarClasses:\s*\[([^\]]*)\]', qml).group(1).replace('"', '').replace(' ', '').split(','))
lua_classes = set()
for match in re.finditer(r'\["class"\]="\^\(([^)]*)\)\$"\},\["name"\]="[^"]*",\["hyprbars:no_bar"\]=true', lua):
    lua_classes.update(match.group(1).split('|'))
assert lua_classes, 'no hyprbars:no_bar rules found'
assert qml_list == lua_classes, (sorted(qml_list), sorted(lua_classes))
print('PASS: snap manager own-bar list matches the hyprbars:no_bar rules (%s)' % ', '.join(sorted(lua_classes)))
