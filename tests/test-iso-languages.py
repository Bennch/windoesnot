#!/usr/bin/env python3
"""Focused checks for the two live ISO language paths."""
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('live_language', ROOT/'iso/live-language.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)

assert live.boot_choice('quiet windoesnot.lang=de windoesnot.keymap=de') == ('de', 'de')
assert live.boot_choice('windoesnot.lang=en windoesnot.keymap=us') == ('en', 'us')
assert live.boot_choice('windoesnot.lang=fr windoesnot.keymap=evil') == (None, None)
assert live.boot_choice('windoesnot.lang=de;rm windoesnot.keymap=de') == (None, 'de')

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

installation = load('installation', 'iso/installation.py')
boot_language = load('boot_language', 'desktop/lib/windoesnot/boot_language.py')
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root/'etc/sddm.conf.d').mkdir(parents=True)
    greeter = root/'etc/sddm.conf.d/windoesnot.conf'
    greeter.write_text('[General]\nGreeterEnvironment=LANG=en_US.UTF-8\n')
    for language in ('en', 'de'):
        locale = language + ('_US.UTF-8' if language == 'en' else '_DE.UTF-8')
        installation.apply_selected_locale(root, locale)
        assert boot_language.language(root) == language
        assert (root/'etc/locale.conf').read_text() == f'LANG={locale}\nLC_MESSAGES={locale}\nLC_TIME={locale}\n'
        assert 'GreeterEnvironment=LANG='+locale in greeter.read_text()

import sys
sys.path.insert(0, str(ROOT/'tools'))
from live_boot_menu import grub_modes, syslinux_modes

source = (ROOT/'upstream/cachyos-live-iso/archiso')
grub = (source/'grub/grub.cfg').read_text().replace('CachyOS', 'WinDoesNot')
bios = (source/'syslinux/archiso_sys-linux.cfg').read_text().replace('CachyOS', 'WinDoesNot')
for language, label in [('en', 'offline install'), ('de', 'Offline-Installation')]:
    assert grub_modes(grub, language).count(label) == 3
    assert syslinux_modes(bios, language).count(label) == 2

print('PASS: ISO language selection and boot labels')
