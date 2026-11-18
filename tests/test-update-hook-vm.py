import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('gate', Path(__file__).resolve().parents[1] / 'tools/update-gate-vm.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Evidence(unittest.TestCase):
    def good(self):
        return dict(pacman_log='Checking WinDoesNot boot filesystem before update\nUpdating linux initcpios\nValidating WinDoesNot boot entries', transaction_exit=0, old_entries_after=[], default_valid=True, baseline_boot_id='a', old_kernel='old', new_kernel='new', reboots=[dict(boot_id='b', kernel='new'), dict(boot_id='c', kernel='new')], negative_control_invariant_failed=True, unmounted_pre_guard_exit=1, unmounted_package_unchanged=True)
    def test_missing_evidence_fails(self):
        self.assertFalse(m.evaluate({})['passed'])
    def test_complete_evidence(self):
        self.assertTrue(m.evaluate(self.good())['passed'])
    def test_reboot_and_counterexample_required(self):
        e = self.good(); e['reboots'][1]['boot_id'] = 'b'
        self.assertFalse(m.evaluate(e)['passed'])
        e = self.good(); e['negative_control_invariant_failed'] = False
        self.assertFalse(m.evaluate(e)['passed'])
    def test_order_required(self):
        e = self.good(); e['pacman_log'] = 'Validating WinDoesNot boot entries\nChecking WinDoesNot boot filesystem before update'
        self.assertFalse(m.evaluate(e)['passed'])

if __name__ == '__main__': unittest.main()
