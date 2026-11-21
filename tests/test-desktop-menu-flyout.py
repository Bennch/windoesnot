#!/usr/bin/env python3
"""The desktop context menu has the hide/show icons entry wired to the hotkey toggle, and the New flyout keeps its default grab
(set_autohide(False) broke clicks on the flyout items)."""
from pathlib import Path
import re

source = (Path(__file__).resolve().parents[1] / 'desktop/config/hyprdesk/hyprdesk.py').read_text()
assert 'sub.set_autohide(False)' not in source, 'flyout without grab broke the menu'
assert '"desktopbg.toggle_icons"' in source and 'ti_action.connect("activate", lambda a, p: self.app._toggle_icons())' in source
for key in ('hide_icons', 'show_icons'):
    assert len(re.findall(rf'"{key}":', source)) == 2, f'{key} needs a German and an English text'
print('PASS: desktop menu flyout keeps its grab, hide/show icons entry in both languages')
