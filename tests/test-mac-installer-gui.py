#!/usr/bin/env python3
"""UI protocol tests; no partitioning, macOS commands, authorization or reboot."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'installer/asahi/src'
sys.path.insert(0, str(SOURCE))
import gui_protocol as gui
import ui_backend as bridge


class GuiTests(unittest.TestCase):
    def test_secret_response_is_never_emitted(self):
        output = io.StringIO()
        secret = ' unique secret äöü '
        with patch.object(gui, 'enabled', True), patch('sys.stdin', io.StringIO(secret+'\n')), contextlib.redirect_stdout(output):
            self.assertEqual(gui.request('Password', kind='password'), secret)
        value = json.loads(output.getvalue().strip()[7:])
        self.assertEqual(value['kind'], 'password')
        self.assertNotIn(secret, output.getvalue())

    def test_response_protocol_does_not_accept_commands_or_control_chars(self):
        self.assertEqual(bridge.response('{"text":"pässword"}'), 'pässword\n'.encode())
        for value in ({'command':'reboot'}, {'text':'yes\nreboot'}, {'text':'x'*2049}, {'text':False}):
            with self.assertRaises(ValueError):
                bridge.response(json.dumps(value))

    def test_backend_choice_preserves_array_and_dictionary_types(self):
        # Importing defines classes only; never instantiate the hardware inspector.
        import main
        installer = object.__new__(main.InstallerMain)
        with patch.object(gui, 'enabled', True), patch.object(gui, 'request', return_value='2'):
            self.assertEqual(installer.choice('OS', ['one','two']), 1)
            self.assertEqual(installer.choice('Disk', {2:'disk two'}), 2)

    def test_yesno_never_auto_accepts_default(self):
        import main
        installer = object.__new__(main.InstallerMain)
        with patch.object(gui, 'enabled', True), patch.object(gui, 'request', side_effect=['','n']) as request:
            self.assertFalse(installer.yesno('Change the partition?', default=True))
            self.assertEqual(request.call_count, 2)

    def test_cli_path_and_recovery_fallback_remain(self):
        script = SOURCE / 'step2/step2.sh'
        subprocess.run(['sh','-n',str(script)],check=True)
        text = script.read_text()
        for command in ('bputil -nc', 'kmutil configure-boot', 'bless --setBoot'):
            self.assertIn(command, text)
        self.assertIn('wdn_phase complete', text)
        launcher = (SOURCE / 'step2/Finish Installation.app/Contents/MacOS/step2_launcher.sh').read_text()
        self.assertIn('--probe', launcher)
        self.assertIn('Terminal.app', launcher)


if __name__ == '__main__':
    unittest.main()
