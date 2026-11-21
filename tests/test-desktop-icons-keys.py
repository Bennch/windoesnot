#!/usr/bin/env python3
"""Desktop icon keys: Ctrl+A selects every shown icon (not the trash), Esc clears the selection, F2 renames a single selection."""
import importlib.util
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / 'desktop/config/hyprdesk/hyprdesk.py'
try:
    spec = importlib.util.spec_from_file_location('hyprdesk_keys_under_test', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.argv = ['hyprdesk.py']
    spec.loader.exec_module(module)
except Exception as error:
    print(f'SKIP: hyprdesk cannot be imported here ({error.__class__.__name__}: {error})')
    raise SystemExit(0)
Gdk = module.Gdk


class Icon:
    def __init__(self, name, trash=False, visible=True):
        self.spec = {'name': name, **({'is_trash': True} if trash else {})}
        self.visible = visible; self.selected = False; self.renamed = False
    def get_visible(self): return self.visible
    def set_selected(self, value): self.selected = value
    def start_rename(self): self.renamed = True


window = object.__new__(module.MonitorWindow)
a, b, hidden, trash = Icon('a'), Icon('b'), Icon('h', visible=False), Icon('trash', trash=True)
window.icons = [a, b, hidden, trash]; window._icon_being_renamed = None
window.selection_area = type('Area', (), {'queue_draw': lambda self: None})()
press = lambda key, state=0: window.on_key_pressed(None, key, 0, state)

assert press(Gdk.KEY_a, Gdk.ModifierType.CONTROL_MASK) is True
assert a.selected and b.selected and not hidden.selected and not trash.selected, 'Ctrl+A: shown icons only, no trash'
assert press(Gdk.KEY_F2) is False and not a.renamed, 'F2 needs exactly one selected icon'
assert press(Gdk.KEY_Escape) is True and not a.selected and not b.selected, 'Esc clears the selection'
assert press(Gdk.KEY_Escape) is False, 'Esc without a selection is not handled'
a.selected = True
assert press(Gdk.KEY_F2) is True and a.renamed
print('PASS: Ctrl+A, Esc and F2 on the desktop icons')
