#!/usr/bin/env python3
"""Checks that missing or wrongly ordered update hooks cannot pass the runner."""
import sys
import importlib.util
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from update_gate_runner import BASELINES, Runner, hook_order

class HookOrder(unittest.TestCase):
    def test_matrix_rejects_retired_bios_limine(self):
        self.assertEqual(set(BASELINES), set("ABCDE"))
        with self.assertRaises(ValueError):
            Runner(Path("."), configuration="F")

    def test_requires_both_hooks_after_kernel_in_order(self):
        pre = 'Checking WinDoesNot boot filesystem before update'
        kernel = 'Updating linux initcpios'
        post = 'Validating WinDoesNot boot entries'
        self.assertTrue(hook_order('\n'.join((pre, kernel, post))))
        for text in ('', pre + '\n' + kernel, post + '\n' + pre + '\n' + kernel,
                     pre + '\n' + post + '\n' + kernel):
            self.assertFalse(hook_order(text))

    def test_grub_bootstrap_has_no_temporary_guard(self):
        bootstrap = 'Kein systemd-boot-Layout; keine Änderung erforderlich.'
        pre = 'Checking WinDoesNot boot filesystem before update'
        kernel = 'Updating linux initcpios'
        post = 'Validating WinDoesNot boot entries'
        for config in ('B', 'C', 'D', 'E'):
            self.assertTrue(hook_order('\n'.join((bootstrap, kernel, post)), config))
            self.assertTrue(hook_order('\n'.join((bootstrap, pre, kernel, post)), config))
            for text in (kernel + '\n' + post, bootstrap + '\n' + post + '\n' + kernel,
                         bootstrap + '\n' + kernel + '\n' + pre + '\n' + post):
                self.assertFalse(hook_order(text, config))

class LimineFiles(unittest.TestCase):
    def test_deployed_kernel_and_initramfs_must_match_configuration(self):
        spec = importlib.util.spec_from_file_location('guest_verify', Path(__file__).resolve().parents[1] / 'tools/vm-test/guest-update-verify.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            boot = Path(tmp); deployed = boot / 'machine/linux-cachyos'; deployed.mkdir(parents=True)
            (boot / 'limine.conf').write_text('path: boot():/machine/linux-cachyos/vmlinuz\nmodule_path: boot():/machine/linux-cachyos/initramfs\n')
            (deployed / 'vmlinuz').write_bytes(b'kernel')
            self.assertFalse(module.limine_boot_files(boot, 'machine'))
            (deployed / 'initramfs').write_bytes(b'initramfs')
            self.assertTrue(module.limine_boot_files(boot, 'machine'))
            (boot / 'limine.conf').write_text('path: other\n')
            self.assertFalse(module.limine_boot_files(boot, 'machine'))

if __name__ == '__main__':
    unittest.main()
