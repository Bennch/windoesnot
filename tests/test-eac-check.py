#!/usr/bin/env python3
"""Fixture-directory tests for eac_check.py."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('eac_check', ROOT/'desktop/lib/windoesnot/eac_check.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
PREFIX = b'\x07\x00\x00\x00'


class EacCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(); self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def put(self, rel, data=b''):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def efivars(self, **values):
        for name, data in values.items():
            self.put(f'sys/firmware/efi/efivars/{name}-8be4df61-93ca-11d2-aa0d-00e098032b8c', PREFIX + data)

    def test_uefi(self):
        self.assertFalse(m.check_uefi(self.root)['ok'])
        (self.root/'sys/firmware/efi').mkdir(parents=True)
        self.assertTrue(m.check_uefi(self.root)['ok'])

    def test_tpm2(self):
        self.assertFalse(m.check_tpm2(self.root)['ok'])
        self.put('sys/class/tpm/tpm0/tpm_version_major', b'1\n')
        self.assertFalse(m.check_tpm2(self.root)['ok'])
        self.put('sys/class/tpm/tpm0/tpm_version_major', b'2\n')
        self.assertTrue(m.check_tpm2(self.root)['ok'])

    def test_iommu_table(self):
        self.assertIsNone(m.check_iommu_table(self.root)['ok'])
        (self.root/'sys/firmware/acpi/tables').mkdir(parents=True)
        self.assertFalse(m.check_iommu_table(self.root)['ok'])
        self.put('sys/firmware/acpi/tables/IVRS')
        self.assertEqual(m.check_iommu_table(self.root)['detail'], 'IVRS')
        self.assertTrue(m.check_iommu_table(self.root)['ok'])

    def test_secure_boot(self):
        self.assertIsNone(m.check_secure_boot(self.root)['ok'])
        self.efivars(SecureBoot=b'\x01', SetupMode=b'\x00')
        self.assertEqual(m.check_secure_boot(self.root), {'id': 'secure_boot', 'ok': False, 'detail': 'enabled'})
        self.efivars(SecureBoot=b'\x00', SetupMode=b'\x00')
        self.assertEqual(m.check_secure_boot(self.root)['detail'], 'disabled')
        self.efivars(SecureBoot=b'\x00', SetupMode=b'\x01')
        self.assertEqual(m.check_secure_boot(self.root), {'id': 'secure_boot', 'ok': True, 'detail': 'setup-mode'})

    def test_secure_boot_unknown_without_vars(self):
        (self.root/'sys/firmware/efi/efivars').mkdir(parents=True)
        self.assertIsNone(m.check_secure_boot(self.root)['ok'])

    def test_boot_manager(self):
        self.assertIsNone(m.check_boot_manager(self.root)['ok'])
        self.put('boot/grub/grub.cfg')
        self.assertEqual(m.check_boot_manager(self.root)['detail'], 'grub')
        self.put('boot/limine.conf')
        self.assertIsNone(m.check_boot_manager(self.root)['ok'])  # ambiguous
        self.efivars(LoaderInfo='systemd-boot 256\x00'.encode('utf-16-le'))
        self.assertEqual(m.check_boot_manager(self.root), {'id': 'boot_manager', 'ok': True, 'detail': 'systemd-boot'})

    def test_snapshot_boot(self):
        self.assertIsNone(m.check_not_snapshot_boot(self.root)['ok'])
        self.put('proc/cmdline', b'root=x rootflags=subvol=/@/.snapshots/3/snapshot\n')
        self.assertFalse(m.check_not_snapshot_boot(self.root)['ok'])
        self.put('proc/cmdline', b'root=x rootflags=subvol=@\n')
        self.assertTrue(m.check_not_snapshot_boot(self.root)['ok'])

    def test_tools(self):
        bindir = self.root/'bin'; bindir.mkdir()
        self.assertFalse(m.check_tools(str(bindir))['ok'])
        tool = bindir/'eac-setup'; tool.write_text('#!/bin/sh\n'); tool.chmod(0o755)
        self.assertTrue(m.check_tools(str(bindir))['ok'])

    def test_run_checks_shape(self):
        result = m.run_checks(self.root, str(self.root))
        self.assertEqual([c['id'] for c in result], ['uefi', 'tpm2', 'iommu_table', 'secure_boot',
                         'boot_manager', 'not_snapshot_boot', 'eac_tools_installed'])
        for c in result:
            self.assertIn(c['ok'], (True, False, None)); self.assertIsInstance(c['detail'], str)


if __name__ == '__main__':
    unittest.main()
