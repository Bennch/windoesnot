#!/usr/bin/env python3
"""windoesnot-export-system: profile validity, no secrets, no base packages, offline with fakes."""
import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'iso/software'))
import catalog as catalog_module  # noqa: E402

loader = importlib.machinery.SourceFileLoader('exp', str(ROOT / 'desktop/bin/windoesnot-export-system'))
exp = importlib.util.module_from_spec(importlib.util.spec_from_loader('exp', loader))
loader.exec_module(exp)
CATALOG = json.loads((ROOT / 'iso/software/catalog.json').read_text())


def fake_run(*args):
    if args[:2] == ('pacman', '-Qqe'):
        return 'firefox\nvim\nlinux-cachyos\nmy-tool\nsome-aur\n'
    if args[:2] == ('pacman', '-Qqm'):
        return 'some-aur\n'
    if args[:2] == ('pacman', '-Qq'):
        return 'firefox\nvim\nlinux-cachyos\nmy-tool\nsome-aur\n'
    if args[0] == 'flatpak':
        return 'org.example.App\n'
    return ''


class Export(unittest.TestCase):
    def test_export(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Path(folder) / 'settings.txt'
            settings.write_text('uiLanguage=de\napiKey=SECRET\nchatHistory=x\naccentColor=#fe6f2d\n')
            with mock.patch.object(exp, 'run', fake_run), mock.patch.object(exp, 'SETTINGS', settings):
                result = exp.export(Path(folder) / 'out')
            out = Path(folder) / 'out'
            profile = catalog_module.read_profile(CATALOG, out / 'software-profile.json')
            self.assertIn('firefox', profile)
            self.assertTrue(result['ok'])
            other = (out / 'other-packages.txt').read_text().split()
            self.assertIn('vim', other); self.assertIn('my-tool', other)
            self.assertNotIn('linux-cachyos', other); self.assertNotIn('some-aur', other)
            self.assertEqual((out / 'aur-packages.txt').read_text().split(), ['some-aur'])
            kept = (out / 'desktop-settings.txt').read_text()
            self.assertIn('uiLanguage=de', kept)
            self.assertNotIn('SECRET', kept); self.assertNotIn('chatHistory', kept)


if __name__ == '__main__':
    unittest.main()
