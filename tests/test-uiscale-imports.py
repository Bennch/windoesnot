#!/usr/bin/env python3
"""Every QML file that scales text through UiScale imports it with a relative path that really points at default/i18n
(a bare "i18n" is read as a module name and took the whole shell down: 'module "i18n" is not installed')."""
import re
from pathlib import Path
SOURCE = Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default'
checked = 0
for path in SOURCE.rglob('*.qml'):
    text = path.read_text()
    if 'UiI.UiScale' not in text:
        continue
    matches = re.findall(r'^import "([^"]+)" as UiI$', text, re.M)
    assert len(matches) == 1, (path, matches)
    assert matches[0].startswith(('./', '../')), (path, matches[0])
    assert (path.parent / matches[0] / 'UiScale.qml').is_file(), (path, matches[0])
    checked += 1
assert checked > 50, checked
assert 'singleton UiScale' in (SOURCE / 'i18n/qmldir').read_text()
print('PASS: %d QML files import UiScale with a valid relative path' % checked)
