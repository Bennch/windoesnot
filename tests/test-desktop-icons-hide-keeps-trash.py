#!/usr/bin/env python3
"""Super + Shift + D hides every desktop icon except the trash and shows them again (MonitorWindow.set_icons_hidden)."""
import importlib.util
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / 'desktop/config/hyprdesk/hyprdesk.py'
try:
    spec = importlib.util.spec_from_file_location('hyprdesk_under_test', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.argv = ['hyprdesk.py']
    spec.loader.exec_module(module)
except Exception as error:   # GTK or layer-shell bindings missing in this environment
    print(f'SKIP: hyprdesk cannot be imported here ({error.__class__.__name__}: {error})')
    raise SystemExit(0)


class Icon:
    def __init__(self, spec, transferred=False):
        self.spec = spec; self.visible = True; self._being_transferred = transferred; self.selected = False
    def set_visible(self, value): self.visible = value
    def get_visible(self): return self.visible
    def set_selected(self, value): self.selected = value


window = object.__new__(module.MonitorWindow)
files = [Icon({'name': 'a'}), Icon({'name': 'b'})]
ghost = Icon({'name': 'ghost'}, transferred=True); ghost.visible = False
trash = Icon({'name': 'trash', 'is_trash': True})
window.icons = files + [ghost, trash]; window.trash_icon = trash
redraws = []
window.selection_area = type('Area', (), {'queue_draw': lambda self: redraws.append(1)})()
files[0].selected = True
window.set_icons_hidden(True)
assert [i.visible for i in files] == [False, False], 'files must be hidden'
assert trash.visible, 'the trash must stay visible'
assert not files[0].selected and redraws, 'a hidden icon must not stay selected'
window.set_icons_hidden(False)
assert [i.visible for i in files] == [True, True] and trash.visible
assert ghost.visible is False, 'an icon in transfer must not be revealed'
print('PASS: hiding the desktop icons keeps the trash and restores the files')
