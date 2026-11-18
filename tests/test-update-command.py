#!/usr/bin/env python3
"""Exercise unattended confirmation and planner failure without invoking pacman."""
import importlib.machinery
import importlib.util
import json
import sys
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-update'
loader = importlib.machinery.SourceFileLoader('update_command', str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

class UpdateCommandTests(unittest.TestCase):
    def test_unattended_forwards_targets_and_confirmation(self):
        plan = Mock(stdout=json.dumps({'status': 'fixed', 'targets': ['extra/firefox']}))
        with patch.object(sys, 'argv', ['windoesnot-update', '--noconfirm']), \
             patch.object(module.subprocess, 'call', side_effect=[0, 0]) as call, \
             patch.object(module.subprocess, 'run', return_value=plan), \
             patch('builtins.input', side_effect=AssertionError('unexpected prompt')):
            self.assertEqual(module.main(), 0)
        self.assertEqual(call.call_args_list[1].args[0], ['sudo', 'pacman', '-Su', '--noconfirm', 'extra/firefox'])

    def test_unresolvable_never_transacts(self):
        plan = Mock(stdout=json.dumps({'status': 'unresolvable', 'unresolved': ['broken']}))
        with patch.object(sys, 'argv', ['windoesnot-update', '--noconfirm']), \
             patch.object(module.subprocess, 'call', return_value=0) as call, \
             patch.object(module.subprocess, 'run', return_value=plan):
            self.assertEqual(module.main(), 1)
        self.assertEqual(call.call_count, 1)

if __name__ == '__main__':
    unittest.main()
