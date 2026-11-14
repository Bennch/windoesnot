#!/usr/bin/env python3
"""Keep shipped swaync styles in sync with the settings-generated palettes."""
import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
swaync = root / 'desktop/config/swaync'
config = json.loads((swaync / 'config.json').read_text())
assert config['positionX'] == 'right' and config['positionY'] == 'top'
assert config['control-center-positionX'] == 'center'
assert config['layer'] == 'overlay'
assert config['widget-config']['title']['text'] == 'Meldungen'
source = root / 'desktop/config/hyprdesk/hyprdesk.py'
tree = ast.parse(source.read_text())
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_build_swaync_css')
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
for name, dark in [('style.css', True), ('style-dark.css', True), ('style-light.css', False)]:
    css = namespace['_build_swaync_css']('#FE6F2D', 10, dark)
    assert (swaync / name).read_text() == css
    assert 'box-shadow' not in css and 'blur' not in css
    assert 'border-radius: 10px' in css and '#FE6F2D' in css
assert namespace['_build_swaync_css']('#123456', 14, True) != namespace['_build_swaync_css']('#123456', 14, False)
print('PASS: notification position and generated dark/light styles')
