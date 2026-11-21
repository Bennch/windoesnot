#!/usr/bin/env python3
"""The desktop context menu: the New flyout takes no pointer grab (the menu stayed stuck on the New row) and the menu has the
hide/show icons entry wired to the hotkey toggle."""
from pathlib import Path
import re

source = (Path(__file__).resolve().parents[1] / 'desktop/config/hyprdesk/hyprdesk.py').read_text()
assert re.search(r'sub = Gtk\.Popover\(\)(?:.|\n)*?sub\.set_autohide\(False\)', source), 'flyout popover must not autohide (pointer grab)'
assert '"desktopbg.toggle_icons"' in source and 'ti_action.connect("activate", lambda a, p: self.app._toggle_icons())' in source
for key in ('hide_icons', 'show_icons'):
    assert len(re.findall(rf'"{key}":', source)) == 2, f'{key} needs a German and an English text'
print('PASS: desktop menu flyout without grab, hide/show icons entry in both languages')
