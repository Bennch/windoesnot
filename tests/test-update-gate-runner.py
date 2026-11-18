#!/usr/bin/env python3
"""Checks that missing or wrongly ordered update hooks cannot pass the runner."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from update_gate_runner import hook_order

class HookOrder(unittest.TestCase):
    def test_requires_both_hooks_after_kernel_in_order(self):
        pre = 'Checking WinDoesNot boot filesystem before update'
        kernel = 'Updating linux initcpios'
        post = 'Validating WinDoesNot boot entries'
        self.assertTrue(hook_order('\n'.join((pre, kernel, post))))
        for text in ('', pre + '\n' + kernel, post + '\n' + pre + '\n' + kernel,
                     pre + '\n' + post + '\n' + kernel):
            self.assertFalse(hook_order(text))

if __name__ == '__main__':
    unittest.main()
