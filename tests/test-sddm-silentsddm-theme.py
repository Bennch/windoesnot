#!/usr/bin/env python3
"""Structural checks for the vendored SilentSDDM theme.

A full offscreen render (like test-greeter-branding.py does for our own
windoesnot theme) does not work for this theme in CI: it uses QtQuick.Effects
MultiEffect for its background blur, which needs a real GPU-backed Qt Quick
scenegraph and hangs under the software/offscreen combination used there.
Manually verified instead against the real X11/XWayland display with a
working GPU (see PAUSE-NOTES.md); these checks catch packaging regressions
(missing files, broken configs, invalid QML) without needing a display.
"""
import configparser
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / 'desktop/share/sddm/themes/silentsddm'


class SilentSddmTheme(unittest.TestCase):
    def test_required_files_present(self):
        for relative in ['Main.qml', 'qmldir', 'metadata.desktop', 'LICENSE',
                          'backgrounds/default.jpg', 'configs/default.conf']:
            self.assertTrue((THEME / relative).is_file(), relative)

    def test_metadata_config_file_exists(self):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.read(THEME / 'metadata.desktop')
        config_file = parser.get('SddmGreeterTheme', 'ConfigFile')
        self.assertTrue((THEME / config_file).is_file(), config_file)
        self.assertEqual(parser.get('SddmGreeterTheme', 'QtVersion'), '6')
        # metadata.desktop referencing a path we deliberately did not vendor
        # (we trimmed docs/previews and translations/ to keep the repo small).
        self.assertNotIn('Screenshot', parser['SddmGreeterTheme'])
        self.assertNotIn('TranslationsDirectory', parser['SddmGreeterTheme'])

    def test_all_shipped_configs_are_valid_ini(self):
        configs = list((THEME / 'configs').glob('*.conf'))
        self.assertGreaterEqual(len(configs), 1)
        for path in configs:
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            with self.subTest(config=path.name):
                parser.read(path)
                self.assertTrue(parser.has_section('LoginScreen'))

    def test_default_config_background_keys_exist(self):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.read(THEME / 'configs/default.conf')
        self.assertTrue(parser.has_option('LoginScreen', 'background'))
        self.assertTrue(parser.has_option('LockScreen', 'background'))

    @unittest.skipUnless(shutil.which('qmllint'), 'qmllint not installed')
    def test_qml_files_pass_qmllint(self):
        qml_files = [THEME / 'Main.qml', *sorted((THEME / 'components').glob('*.qml'))]
        self.assertGreater(len(qml_files), 5)
        for path in qml_files:
            with self.subTest(file=path.name):
                result = subprocess.run(['qmllint', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
