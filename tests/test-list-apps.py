#!/usr/bin/env python3
"""Different desktop IDs for one command should yield one Start menu app."""
from pathlib import Path
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

print('PASS: duplicate launcher commands collapse; different apps with the same name remain')
