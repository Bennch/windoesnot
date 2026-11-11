#!/usr/bin/env python3
"""Test lid decisions without closing a lid, suspending, or locking the host."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('lid', str(ROOT / 'desktop/bin/windoesnot-lid-controller'))
spec = importlib.util.spec_from_loader(loader.name, loader)
lid = importlib.util.module_from_spec(spec)
loader.exec_module(lid)


class LidPolicy(unittest.TestCase):
    def test_context_priority_and_default_inheritance(self):
        prefs = dict(battery='lock', ac='ignore', docked='system')
        self.assertEqual(lid.selected_action(prefs, {}), 'lock')
        self.assertEqual(lid.selected_action(prefs, {'OnExternalPower': True}), 'ignore')
        self.assertEqual(lid.selected_action(prefs, {'Docked': True, 'OnExternalPower': True}), 'ignore')
        prefs = dict.fromkeys(prefs, 'system')
        self.assertEqual(lid.selected_action(prefs, {'HandleLidSwitch': 'lock', 'OnExternalPower': True}), 'lock')

    def test_preferences_reject_unknown_actions_and_partial_writes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'settings.txt'
            p.write_text('lidBatteryAction=lock\nlidAcAction=delete-all\n')
            self.assertEqual(lid.preferences(p), dict(battery='lock', ac='system', docked='system'))
            p.write_text('')
            with self.assertRaises(ValueError): lid.preferences(p)

    def test_system_defaults_do_not_take_over_logind(self):
        obj = lid.Controller.__new__(lid.Controller)
        obj.fd = None; obj.bus = Mock(); obj.persist = Mock()
        with patch.object(lid, 'preferences', return_value=dict.fromkeys(lid.KEYS, 'system')):
            obj.configure()
        self.assertIsNone(obj.fd)
        obj.bus.call_with_unix_fd_list_sync.assert_not_called()

    def test_only_close_edge_triggers_an_explicit_override(self):
        obj = lid.Controller.__new__(lid.Controller)
        obj.fd = 42; obj.closed = False; obj.prefs = dict.fromkeys(lid.KEYS, 'lock')
        obj.bus = Mock(); obj.persist = Mock(); obj.execute = Mock()
        with patch.object(lid, 'manager_state', return_value={'LidClosed': True}):
            obj.changed(); obj.changed()
        obj.execute.assert_called_once_with('lock')
        obj.fd = None; obj.closed = False; obj.execute.reset_mock()
        with patch.object(lid, 'manager_state', return_value={'LidClosed': True}): obj.changed()
        obj.execute.assert_not_called()


if __name__ == '__main__': unittest.main()
