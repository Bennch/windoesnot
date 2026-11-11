#!/usr/bin/env python3
"""Verify the offline guide and its handoff without any Mac power operations."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'installer/asahi/src'
spec = importlib.util.spec_from_file_location('recovery_guide', SOURCE / 'recovery_guide.py')
guide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)


class RecoveryGuideTests(unittest.TestCase):
    def test_languages_cover_same_steps_and_controls(self):
        self.assertEqual(set(guide.COPY), {'de', 'en'})
        reference = guide.COPY['de']
        for language, copy in guide.COPY.items():
            self.assertEqual(set(copy), set(reference))
            self.assertEqual(len(copy['steps']), 7)
            self.assertEqual([s[4] for s in copy['steps']], [s[4] for s in reference['steps']])
            self.assertTrue(all(all(s) for s in copy['steps']))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                guide.terminal_steps('My New OS', language)
            self.assertIn('My New OS', output.getvalue())
            self.assertIn('25', output.getvalue())

    def test_volume_label_cannot_break_out_of_script(self):
        label = '</script><script>alert("volume")</script>&\u2028'
        html = guide.render(label, 'en')
        self.assertEqual(html.count('<script>'), 1)
        self.assertNotIn(label, html)
        payload = re.search(r'const data=(.*);\nlet language=', html).group(1)
        self.assertEqual(json.loads(payload)['volume'], label)
        self.assertIn("connect-src 'none'", html)
        self.assertNotIn('<script src=', html)
        self.assertNotIn('<link ', html)

    def test_script_syntax(self):
        script = re.search(r'<script>(.*?)</script>', guide.render('Mac'), re.S).group(1)
        subprocess.run(['node', '--check'], input=script, text=True, check=True)

    def test_no_automatic_power_or_credentials_in_companion(self):
        html = guide.render('Mac')
        self.assertNotIn('<input', html)
        self.assertNotIn('fetch(', html)
        self.assertIn('prefers-reduced-motion:reduce', html)
        self.assertIn('window.print()', html)
        main = (SOURCE / 'main.py').read_text()
        block = main[main.index('    def step2_indirect('):main.index('    def get_min_free_space(')]
        self.assertLess(block.index('recovery_guide.terminal_steps'), block.index('recovery_guide.show'))
        self.assertRegex(block, r'self.input\(\)\n        time.sleep\(1\)\n        os.system\("shutdown -h now"\)')

    def test_browser_failure_preserves_saved_offline_file(self):
        with patch.object(guide.sys, 'platform', 'darwin'), \
             patch.object(guide.os, 'geteuid', return_value=1001), \
             patch.object(guide.subprocess, 'run', side_effect=OSError('no browser')), \
             contextlib.redirect_stdout(io.StringIO()):
            path = guide.show('WinDoesNotMac', 'en')
        try:
            self.assertIn('Your Mac. One step at a time.', path.read_text())
        finally:
            path.unlink()
            path.parent.rmdir()


if __name__ == '__main__':
    unittest.main()
