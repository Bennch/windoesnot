#!/usr/bin/env python3
"""Different desktop IDs for one command should yield one Start menu app."""
from pathlib import Path
import os
import runpy
import tempfile


launchers = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-list-apps'))['launchers']
with tempfile.TemporaryDirectory(prefix='wdn-list-apps-') as temporary:
    directory = Path(temporary)
    (directory / 'first.desktop').write_text('[Desktop Entry]\nName=Calculator\nName[de]=Taschenrechner\nExec=gnome-calculator\nIcon=one\n')
    (directory / 'second.desktop').write_text('[Desktop Entry]\nName=Calculator (alias)\nExec=gnome-calculator\nIcon=two\n')
    (directory / 'other.desktop').write_text('[Desktop Entry]\nName=Calculator\nName[de]=Taschenrechner\nExec=other-calculator\nIcon=other\n')
    results = launchers([directory], 'de', True)
    assert {item['cmd'] for item in results} == {'gnome-calculator', 'other-calculator'}
    assert next(item for item in results if item['cmd'] == 'gnome-calculator')['id'] == 'first.desktop'
    hidden = launchers([directory], 'de', True, {'first.desktop'})
    assert next(item for item in hidden if item['id'] == 'first.desktop')['technical'] is True
    assert next(item for item in hidden if item['id'] == 'other.desktop')['technical'] is False
    # The model keeps technical launchers, so Start menu search can still find them.
    assert next(item for item in hidden if item['id'] == 'first.desktop')['name'] == 'Taschenrechner'
    qml = (Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default/shell.qml').read_text()
    assert 'startMenu.searchText.length > 0 || startMenu.showTechnicalApps || !app.technical' in qml
    home = directory / 'home'
    user_apps = home / '.local/share/applications'
    user_apps.mkdir(parents=True)
    (user_apps / 'cmake-gui.desktop').write_text('[Desktop Entry]\nName=CMake\nExec=cmake-gui\n')
    old_home = os.environ.get('HOME')
    os.environ['HOME'] = str(home)
    try:
        installed_by_user = launchers([user_apps], 'en', True, {'cmake-gui.desktop'})
    finally:
        if old_home is None:
            os.environ.pop('HOME', None)
        else:
            os.environ['HOME'] = old_home
    assert installed_by_user[0]['technical'] is False

print('PASS: duplicate launcher commands collapse; different apps with the same name remain')
