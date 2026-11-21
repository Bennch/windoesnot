#!/usr/bin/env python3
"""Image Firefox defaults must follow the system without locking user choices."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FirefoxDefaultsTest(unittest.TestCase):
    def test_defaults_and_image_install(self):
        defaults = (ROOT / 'iso/firefox-defaults.js').read_text()
        self.assertEqual(dict(re.findall(r'^pref\("([^"]+)", ([^;]+)\);$', defaults, re.M)), {
            'browser.theme.toolbar-theme': '2',
            'browser.theme.content-theme': '2',
            'layout.css.prefers-color-scheme.content-override': '2',
            'extensions.activeThemeID': '"default-theme@mozilla.org"',
        })
        self.assertNotIn('lockPref', defaults)
        self.assertIn('iso/firefox-defaults.js" /usr/lib/firefox/defaults/pref/windoesnot.js',
                      (ROOT / 'iso/customize-image.sh').read_text())


if __name__ == '__main__':
    unittest.main()
