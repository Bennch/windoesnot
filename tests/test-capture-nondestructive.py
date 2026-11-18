#!/usr/bin/env python3
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture', ROOT / 'tools/capture-screenshots.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

class CaptureSafety(unittest.TestCase):
    def test_cleanup_only_owned_pid(self):
        commands = []
        clients = [{'pid': 77, 'address': '0xabc'}, {'pid': 88, 'address': '0xdef'}]
        with patch.object(capture, 'read_json', return_value=clients), \
             patch.object(capture, 'guest', side_effect=lambda vm, cmd, dry: commands.append(cmd)):
            capture.cleanup_scene('vm', {'kind': 'launch', 'capture_pid': 77}, False)
        self.assertEqual(len(commands), 1)
        self.assertIn('address:0xabc', commands[0])
        self.assertNotIn('0xdef', commands[0])

    def test_foreign_panel_aborts_before_mutation(self):
        calls = []
        with patch.object(sys, 'argv', ['capture', '--vm-name', 'vm', '--scene', 'calendar']), \
             patch.object(capture, 'set_display'), \
             patch.object(capture, 'read_state', return_value={'language': 'de', 'dark': True}), \
             patch.object(capture, 'read_panels', return_value={'calendar': True}), \
             patch.object(capture, 'guest', side_effect=lambda *a: calls.append(a)):
            with self.assertRaisesRegex(RuntimeError, 'Open panels'):
                capture.main()
        self.assertEqual(calls, [])

    def test_preferences_restored_after_failure(self):
        calls = []
        with patch.object(sys, 'argv', ['capture', '--vm-name', 'vm', '--scene', 'desktop', '--language', 'en', '--theme', 'light']), \
             patch.object(capture, 'set_display'), patch.object(capture, 'read_panels', return_value={}), \
             patch.object(capture, 'read_json', return_value=[]), \
             patch.object(capture, 'read_state', side_effect=[{'language': 'de', 'dark': True}, {'language': 'en', 'dark': False}]), \
             patch.object(capture, 'guest', side_effect=lambda vm, cmd, dry: calls.append(cmd)), \
             patch.object(capture, 'prepare_scene', side_effect=RuntimeError('failed')), \
             patch.object(capture.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                capture.main()
        self.assertIn('setLanguage de', calls[-1])
        self.assertIn('setDarkMode true', calls[-1])
        self.assertNotIn('closeAll', '\n'.join(calls))

if __name__ == '__main__':
    unittest.main()
