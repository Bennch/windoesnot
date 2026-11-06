#!/usr/bin/env python3
"""Installer start page: one QML welcome page (logo, short text, language), no extra page, no dashes, DE and EN."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
qml = (ROOT / 'iso/branding/welcomeq.qml').read_text()
texts = re.findall(r'"([^"\n]{12,})"', qml)
assert not [t for t in texts if '—' in t or '–' in t], 'no em/en dashes in UI text (project rule)'
for needle in ('Du bist auf der richtigen Seite.', "You're on the right side.", 'kurz vor der ersten Version', 'close to the first release',
               'config.languagesModel', 'config.localeIndex', 'qrc:/Requirements.qml'):
    assert needle in qml, needle
assert 'early preview' not in qml.lower() and 'frühe vorschau' not in qml.lower()
profile = (ROOT / 'tools/prepare-profile.py').read_text()
assert "pages[pages.index('welcome')] = 'welcomeq'" in profile
assert "cfg('welcomeq.conf', {**welcome, 'qmlSearch': 'both'})" in profile and "online / 'modules/welcomeq.conf'" in profile
assert 'windoesnotintro' not in profile and 'productBanner' not in profile and 'productWelcome' not in profile
assert not (ROOT / 'iso/modules/windoesnotintro').exists()
assert 'windoesnotintro' not in (ROOT / 'tools/build-installer-module.sh').read_text()
print('PASS installer-welcome')
