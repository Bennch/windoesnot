#!/usr/bin/env python3
"""The switcher searches apps/scalable, while the original icon is in apps/22."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
apps = root / 'desktop/config/quickshell/default/img/Win11-dark/apps'
target = (apps / '22/system-file-manager.svg').resolve(strict=True)
for name in ('system-file-manager', 'org.gnome.Nautilus', 'org.gnome.nautilus',
             'nautilus', 'org.gnome.Files', 'org.gnome.files', 'thunar', 'dolphin'):
    alias = apps / 'scalable' / f'{name}.svg'
    assert alias.is_file(), f'Missing or broken icon: {alias}'
    assert alias.resolve() == target, f'Wrong icon: {alias}'
print('Switcher file manager aliases resolve to the Win11 folder icon')
