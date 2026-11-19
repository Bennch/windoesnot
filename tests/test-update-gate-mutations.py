#!/usr/bin/env python3
"""Real negative-control VMs; opt in because these run full system upgrades."""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from update_gate_common import package_set
from update_gate_runner import Runner

PACKAGES = Path(os.environ.get('WINDOESNOT_GATE_PACKAGES', ROOT / 'build/release-packages-32'))
CONFIGURATION = os.environ.get('WINDOESNOT_GATE_CONFIGURATION', 'A')

@unittest.skipUnless(os.environ.get('WINDOESNOT_RUN_GATE_MUTATIONS') == '1', 'requires real VM mutations and network')
class Mutations(unittest.TestCase):
    def test_real_mutations(self):
        expected = package_set(PACKAGES)
        positive = Path(os.environ['WINDOESNOT_GATE_POSITIVE'])
        evidence = json.loads(positive.read_text())
        self.assertTrue(evidence.get('passed'))
        self.assertEqual(evidence.get('package_set_sha256'), expected)
        self.assertIn(CONFIGURATION, ('A', 'B', 'C'))
        self.assertEqual(evidence.get('configuration', 'A'), CONFIGURATION)
        for mutation in ('A', 'B', 'C'):
            with self.subTest(mutation=mutation):
                print('Starting real mutation', mutation, flush=True)
                runner = Runner(PACKAGES, mutation=mutation, configuration=CONFIGURATION)
                result = runner.execute()
                self.assertTrue(result.get('mutation_active'), result)
                self.assertEqual(result.get('package_set_sha256'), expected)
                self.assertFalse(result.get('passed'), result)
                self.assertNotIn('cleanup_error', result)
                log = (runner.run / 'update.log').read_text(errors='replace')
                if mutation == 'A':
                    self.assertNotEqual(result['job']['steps']['update'], 0)
                    self.assertIn('/usr/bin/windoesnot-update', log)
                    self.assertIn('exists in filesystem', log)
                elif mutation == 'B':
                    self.assertNotEqual(result['job']['steps']['update'], 0)
                    self.assertIn('exit status 73', log)
                else:
                    self.assertEqual(result['job']['steps']['update'], 0)
                    self.assertEqual(len(result.get('reboots', [])), 2)
                    self.assertEqual(result.get('error'), 'one or more update assertions failed')
                    self.assertTrue(result['checks']['kernel_changed'])
                    self.assertTrue(result['checks']['desktop_plugins'])
                    self.assertFalse(result['checks']['hook_order'])
                    self.assertFalse(result['checks']['post_hook_status'])
                print('Detected mutation', mutation, 'evidence:', runner.run / 'result.json', flush=True)

if __name__ == '__main__':
    unittest.main(verbosity=2)
