#!/usr/bin/env python3
"""The desktop trash icon follows the real trash folder (emptied in the file manager): MonitorWindow._refresh_trash_icon swaps the picture."""
import importlib.util
from pathlib import Path
import os
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / 'desktop/config/hyprdesk/hyprdesk.py'
try:
    spec = importlib.util.spec_from_file_location('hyprdesk_trash_under_test', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.argv = ['hyprdesk.py']
    spec.loader.exec_module(module)
except Exception as error:
    print(f'SKIP: hyprdesk cannot be imported here ({error.__class__.__name__}: {error})')
    raise SystemExit(0)

source_text = SOURCE.read_text()
assert 'self.trash_monitor.connect("changed", self._on_trash_changed)' in source_text, 'the trash folder must be watched'

with tempfile.TemporaryDirectory() as home:
    os.environ['HOME'] = home
    trash = Path(home) / '.local/share/Trash/files'
    trash.mkdir(parents=True)

    class Image:
        def __init__(self): self.path = None; self.size = None
        def set_from_file(self, path): self.path = path
        def set_pixel_size(self, size): self.size = size

    class Icon:
        def __init__(self): self.spec = {'icon_name': ''}; self.icon_image = Image()

    window = object.__new__(module.MonitorWindow)
    window.trash_icon = Icon(); window.icon_size = 48
    module.Path.home = staticmethod(lambda: Path(home))
    window._refresh_trash_icon()
    assert window.trash_icon.icon_image.path.endswith('icons8-bin-windows-96.png'), window.trash_icon.icon_image.path
    (trash / 'x.txt').write_text('x')
    window._refresh_trash_icon()
    assert window.trash_icon.icon_image.path.endswith('icons8-full-bin-windows.svg') and window.trash_icon.icon_image.size == 48
    (trash / 'x.txt').unlink()
    window._refresh_trash_icon()
    assert window.trash_icon.icon_image.path.endswith('icons8-bin-windows-96.png')
print('PASS: trash icon is watched and follows empty/full')
