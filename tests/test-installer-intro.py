#!/usr/bin/env python3
"""Installer 'About WinDoesNot' page: wired into the sequence and build, no dashes in visible text, DE and EN."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
module = ROOT / 'iso/modules/windoesnotintro'
qml = (module / 'windoesnotintro.qml').read_text()
texts = re.findall(r'"([^"\n]{12,})"', qml)
assert not [t for t in texts if '—' in t or '–' in t], 'no em/en dashes in UI text (project rule)'
for needle in ('Du bist auf der richtigen Seite.', "You're on the right side.", 'kurz vor der ersten Version', 'close to the first release'):
    assert needle in qml, needle
assert 'early preview' not in qml.lower() and 'frühe vorschau' not in qml.lower()
profile = (ROOT / 'tools/prepare-profile.py').read_text()
assert "pages.insert(pages.index('welcome') + 1, 'windoesnotintro')" in profile
assert "cfg('windoesnotintro.conf', {'qmlSearch': 'qrc'})" in profile
assert "'productBanner':'windoesnot-banner.png'" in profile and 'productWelcome' not in profile
assert (ROOT / 'iso/branding/windoesnot-banner.png').is_file()
build = (ROOT / 'tools/build-installer-module.sh').read_text()
assert 'calamares_add_module_subdirectory(windoesnotintro)' in build and 'libcalamares_viewmodule_windoesnotintro.so' in build
assert 'windoesnotintro.qml' in (module / 'windoesnotintro.qrc').read_text()
assert 'calamares_add_plugin(windoesnotintro' in (module / 'CMakeLists.txt').read_text()
print('PASS installer-intro')
