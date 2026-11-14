#!/usr/bin/env python3
"""Image package builds must not use -march=native (SIGILL on older CPUs)."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / "tools").glob("build-image-*.sh"))


class GenericPackageFlagsTests(unittest.TestCase):
    def test_every_makepkg_call_uses_the_generic_config(self):
        checked = 0
        for script in SCRIPTS:
            text = script.read_text()
            calls = re.findall(r"makepkg\b[^\n]*", text)
            calls = [c for c in calls if "--cleanbuild" in c]
            if not calls:
                continue
            checked += 1
            self.assertIn("-march=native/-march=x86-64", text, script.name)
            self.assertIn("makepkg-generic.conf", text, script.name)
            for call in calls:
                self.assertIn('--config "$WDN_MAKEPKG_CONF"', call, f"{script.name}: {call}")
        self.assertGreaterEqual(checked, 4)

    def test_generic_conf_is_created_before_first_use(self):
        for script in SCRIPTS:
            text = script.read_text()
            if "makepkg --config" not in text:
                continue
            self.assertLess(text.index("makepkg-generic.conf"), text.index("makepkg --config"), script.name)


if __name__ == "__main__":
    unittest.main()
