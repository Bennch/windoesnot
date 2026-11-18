#!/usr/bin/env python3
"""Tests for the boot entry migration and guard (isolated temp roots; no real /boot, no pacman)."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migration', ROOT / 'desktop/lib/windoesnot/boot_entry_migration.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
MID = 'a' * 32
GOOD_MOUNT = {'mounted': True, 'fstype': 'vfat', 'rw': True, 'free': 500 * 1024 * 1024}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'etc').mkdir()
        (self.root / 'etc/machine-id').write_text(MID)
        self.boot = self.root / 'boot'
        self.entries = self.boot / 'loader/entries'
        self.entries.mkdir(parents=True)
        (self.boot / 'EFI/systemd').mkdir(parents=True)
        (self.boot / 'loader/loader.conf').write_text('default linux-main.conf\n')
        (self.boot / 'vmlinuz-linux-cachyos').write_text('kernel')
        (self.boot / 'initramfs-linux-cachyos.img').write_text('initrd')
        self.write_entry('linux-main.conf', '/vmlinuz-linux-cachyos', '/initramfs-linux-cachyos.img')
        (self.boot / MID / '6.1').mkdir(parents=True)
        (self.boot / MID / '6.1/linux').write_text('oldkernel')
        (self.boot / MID / '6.1/initrd').write_text('oldinitrd')
        self.write_entry(MID + '-6.1.conf', '/%s/6.1/linux' % MID, '/%s/6.1/initrd' % MID)

    def write_entry(self, name, linux, initrd, extra=''):
        (self.entries / name).write_text('title t\nlinux %s\ninitrd %s\noptions root=UUID=x rw\n%s' % (linux, initrd, extra))


class Migration(Base):
    def test_retires_only_own_kernel_install_entries_and_is_idempotent(self):
        self.write_entry('b' * 32 + '-6.1.conf', '/%s/6.1/linux' % ('b' * 32), '/x')
        result = m.apply(self.root)
        self.assertEqual(result['removed'], [MID + '-6.1.conf'])
        self.assertTrue((self.entries / ('b' * 32 + '-6.1.conf')).exists())
        self.assertTrue((self.boot / MID / '6.1/linux').exists(), 'kernel copies are never deleted')
        self.assertEqual(m.apply(self.root)['state'], 'nothing-to-do')
        saved = json.loads((self.root / m.STATE_DIR / 'result.json').read_text())
        self.assertEqual(saved['state'], 'nothing-to-do')
        self.assertTrue(list((self.root / m.STATE_DIR).glob('backup-*/*.conf')))

    def test_empty_initramfs_preserves_everything(self):
        (self.boot / 'initramfs-linux-cachyos.img').write_text('')
        with self.assertRaises(m.BootProblem):
            m.apply(self.root)
        self.assertTrue((self.entries / (MID + '-6.1.conf')).exists())
        self.assertEqual(json.loads((self.root / m.STATE_DIR / 'result.json').read_text())['state'], 'error')

    def test_missing_initrd_and_no_root_option_rejected(self):
        (self.boot / 'initramfs-linux-cachyos.img').unlink()
        with self.assertRaises(m.BootProblem):
            m.apply(self.root)
        (self.boot / 'initramfs-linux-cachyos.img').write_text('i')
        (self.entries / 'linux-main.conf').write_text('linux /vmlinuz-linux-cachyos\ninitrd /initramfs-linux-cachyos.img\n')
        with self.assertRaises(m.BootProblem):
            m.apply(self.root)

    def test_path_escape_and_symlink_rejected(self):
        (self.root / 'etc/secret').write_text('x')
        self.write_entry('linux-main.conf', '/../etc/secret', '/initramfs-linux-cachyos.img')
        with self.assertRaises(m.BootProblem):
            m.apply(self.root)
        (self.boot / 'link').symlink_to(self.root / 'etc/secret')
        self.write_entry('linux-main.conf', '/link', '/initramfs-linux-cachyos.img')
        with self.assertRaises(m.BootProblem):
            m.apply(self.root)

    def test_custom_entry_with_keep_marker_is_kept(self):
        self.write_entry(MID + '-custom.conf', '/%s/6.1/linux' % MID, '/%s/6.1/initrd' % MID, '# windoesnot-keep\n')
        result = m.apply(self.root)
        self.assertNotIn(MID + '-custom.conf', result['removed'])
        self.assertTrue((self.entries / (MID + '-custom.conf')).exists())

    def test_entry_with_foreign_kernel_path_is_kept(self):
        self.write_entry(MID + '-lts.conf', '/vmlinuz-linux-lts', '/initramfs-linux-lts.img')
        self.assertNotIn(MID + '-lts.conf', m.apply(self.root)['removed'])

    def test_default_pointing_at_retired_entry_is_repaired_before_removal(self):
        (self.boot / 'loader/loader.conf').write_text('default %s-6.1.conf\n' % MID)
        calls = []
        def set_default(entry):
            calls.append((entry, (self.entries / (MID + '-6.1.conf')).exists()))
        result = m.apply(self.root, set_default=set_default)
        self.assertEqual(calls, [('linux-main.conf', True)], 'repair happens while the old entry still exists')
        self.assertEqual(result['default_repaired'], 'linux-main.conf')
        self.assertFalse((self.entries / (MID + '-6.1.conf')).exists())

    def test_default_glob_matching_retired_entries_is_repaired(self):
        (self.boot / 'loader/loader.conf').write_text('default %s-*\n' % MID)
        calls = []
        m.apply(self.root, set_default=calls.append)
        self.assertEqual(calls, ['linux-main.conf'])

    def test_failed_default_repair_keeps_entries(self):
        (self.boot / 'loader/loader.conf').write_text('default %s-6.1.conf\n' % MID)
        def boom(entry): raise RuntimeError('efi write failed')
        with self.assertRaises(m.BootProblem):
            m.apply(self.root, set_default=boom)
        self.assertTrue((self.entries / (MID + '-6.1.conf')).exists())

    def test_default_on_valid_generic_entry_is_not_touched(self):
        calls = []
        m.apply(self.root, set_default=calls.append)
        self.assertEqual(calls, [])

    def test_lts_default_family_is_not_replaced(self):
        (self.boot / 'vmlinuz-linux-lts').write_text('k'); (self.boot / 'initramfs-linux-lts.img').write_text('i')
        self.write_entry('linux-lts.conf', '/vmlinuz-linux-lts', '/initramfs-linux-lts.img')
        (self.boot / 'loader/loader.conf').write_text('default linux-lts.conf\n')
        calls = []
        m.apply(self.root, set_default=calls.append)
        self.assertEqual(calls, [])


class Layout(Base):
    def test_grub_or_bios_is_not_applicable(self):
        import shutil
        shutil.rmtree(self.boot / 'loader')
        shutil.rmtree(self.boot / 'EFI')
        self.assertEqual(m.classify(self.root), 'not-applicable')
        self.assertEqual(m.main(['--root', str(self.root), '--post-transaction']), 0)

    def test_systemd_boot_is_detected(self):
        self.assertEqual(m.classify(self.root), 'systemd-boot')

    def test_mount_checks(self):
        m.check_mount(GOOD_MOUNT)
        for bad in ({**GOOD_MOUNT, 'mounted': False}, {**GOOD_MOUNT, 'fstype': 'ext4'}, {**GOOD_MOUNT, 'rw': False}, {**GOOD_MOUNT, 'free': 1}):
            with self.assertRaises(m.BootProblem):
                m.check_mount(bad)

    def test_preflight_fails_on_supported_layout_with_unmounted_boot(self):
        orig = m.mount_info
        m.mount_info = lambda root='/': {**GOOD_MOUNT, 'mounted': False}
        try:
            self.assertEqual(m.main(['--root', str(self.root), '--preflight']), 1)
            self.assertTrue((self.entries / (MID + '-6.1.conf')).exists(), 'post mode must not change anything either')
            self.assertEqual(m.main(['--root', str(self.root), '--post-transaction']), 1)
            self.assertTrue((self.entries / (MID + '-6.1.conf')).exists())
        finally:
            m.mount_info = orig

    def test_post_transaction_runs_end_to_end_with_good_mount(self):
        orig = m.mount_info
        m.mount_info = lambda root='/': GOOD_MOUNT
        try:
            self.assertEqual(m.main(['--root', str(self.root), '--post-transaction']), 0)
            self.assertFalse((self.entries / (MID + '-6.1.conf')).exists())
        finally:
            m.mount_info = orig


class Hooks(unittest.TestCase):
    def read(self, name):
        return (ROOT / 'desktop/share/libalpm/hooks' / name).read_text()

    def test_hook_file_contract(self):
        post = self.read('zzzz-windoesnot-boot-entries.hook')
        pre = self.read('00-windoesnot-boot-guard.hook')
        for text in ('PostTransaction', 'usr/lib/modules/*/vmlinuz', 'windoesnot-tools', 'Operation = Install', '--post-transaction'):
            self.assertIn(text, post)
        for text in ('PreTransaction', 'AbortOnFail', 'usr/lib/modules/*/vmlinuz', '--preflight'):
            self.assertIn(text, pre)
        self.assertLess('00-windoesnot-boot-guard.hook', '90-mkinitcpio-install.hook')
        self.assertGreater('zzzz-windoesnot-boot-entries.hook', 'sdboot-kernel-update.hook')


if __name__ == '__main__':
    unittest.main()
