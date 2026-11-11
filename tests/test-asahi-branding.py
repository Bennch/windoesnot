#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('asahi_branding', ROOT / 'tools/brand-asahi.py')
brand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brand)


class BrandingTests(unittest.TestCase):
    def test_grub_keeps_root_encryption_and_other_settings(self):
        source = ('GRUB_CMDLINE_LINUX_DEFAULT="root=UUID=123 rootflags=subvol=@ '
                  'rd.luks.uuid=456 console=tty0 quiet loglevel=7"\n'
                  'GRUB_CMDLINE_LINUX="audit=1"\nGRUB_TIMEOUT=5\n')
        value = brand.set_grub(source)
        for part in ('root=UUID=123', 'rootflags=subvol=@', 'rd.luks.uuid=456',
                     'GRUB_CMDLINE_LINUX="audit=1"', 'GRUB_TIMEOUT=5'):
            self.assertIn(part, value)
        self.assertIn('splash', value)
        self.assertEqual(value, brand.set_grub(value))
        with self.assertRaises(ValueError):
            brand.set_grub('GRUB_CMDLINE_LINUX_DEFAULT="$(danger)"\n')

    def test_staging_preserves_asahi_and_custom_hostname(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            brand.stage(root, 'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n',
                        'MODULES=(btrfs)\nHOOKS=(base asahi udev kms keyboard block filesystems)\n',
                        'my-mac\n')
            self.assertFalse((root / 'etc/hostname').exists())
            self.assertIn('base asahi udev kms plymouth', (root / 'etc/mkinitcpio.conf').read_text())
            self.assertIn('MODULES=(btrfs)', (root / 'etc/mkinitcpio.conf').read_text())
            self.assertIn('ID_LIKE="archarm arch"', (root / 'etc/os-release').read_text())
            self.assertFalse((root / 'usr/lib/os-release').exists())
            self.assertFalse((root / 'boot/efi').exists())
            self.assertTrue((root / 'usr/share/plymouth/themes/windoesnot/watermark.png').exists())
            self.assertNotIn('@KEYMAP_SHORT@', (root / 'usr/share/grub/themes/windoesnot/theme.txt').read_text())

    def test_rollback_restores_symlink_and_removes_new_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backup = root / 'backup'
            backup.mkdir()
            old = root / 'os-release'
            old.symlink_to('../usr/lib/os-release')
            new = root / 'new'
            records = [brand.save(old, backup), brand.save(new, backup)]
            replacement = root / 'replacement'
            replacement.write_text('WinDoesNotMac')
            brand.atomic_copy(replacement, old)
            brand.atomic_copy(replacement, new)
            self.assertFalse(old.is_symlink())
            brand.restore(records, backup)
            self.assertEqual(old.readlink(), Path('../usr/lib/os-release'))
            self.assertFalse(new.exists())


if __name__ == '__main__':
    unittest.main()
