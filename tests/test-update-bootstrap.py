#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap', ROOT / 'tools/update-bootstrap.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
MID = 'a' * 32

class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for p in ('etc', 'boot/loader/entries', 'boot/EFI/systemd', 'boot/' + MID + '/old'):
            (self.root / p).mkdir(parents=True, exist_ok=True)
        (self.root / 'etc/machine-id').write_text(MID)
        (self.root / 'boot/loader/loader.conf').write_text('default linux-main.conf\n')
        for p in ('vmlinuz', 'initrd'):
            (self.root / 'boot' / p).write_text('data')
        entries = self.root / 'boot/loader/entries'
        (entries / 'linux-main.conf').write_text('linux /vmlinuz\ninitrd /initrd\noptions root=UUID=x\n')
        (entries / (MID + '-old.conf')).write_text('linux /' + MID + '/old/linux\ninitrd /x\n')
        self.entries = entries
        # The fixture is not an actual mount; exercise the real migration otherwise.
        self.mount = patch('subprocess.run', side_effect=lambda *a, **k: type('R', (), {'returncode': 0, 'stdout': 'vfat rw'})())
        self.mount.start()
        self.addCleanup(self.mount.stop)

    def test_embedded_sources_match_package_sources(self):
        self.assertEqual(b.MIGRATION, (ROOT / "desktop/lib/windoesnot/boot_entry_migration.py").read_bytes())
        self.assertEqual(b.PACKAGED_HOOK, (ROOT / "desktop/share/libalpm/hooks/00-windoesnot-boot-guard.hook").read_bytes())

    def test_install_repeat_and_handoff(self):
        b.run(self.root)
        self.assertFalse((self.entries / (MID + '-old.conf')).exists())
        self.assertTrue(list((self.root / 'var/lib/windoesnot/boot-migration').glob('backup-*/*.conf')))
        b.run(self.root)
        self.assertEqual((self.root / b.HOOK).read_bytes(), b.TEMP_HOOK)
        for path, data in (('usr/share/libalpm/hooks/00-windoesnot-boot-guard.hook', b.PACKAGED_HOOK), ('usr/lib/windoesnot/boot_entry_migration.py', b.MIGRATION)):
            p = self.root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        b.run(self.root)
        self.assertFalse((self.root / b.HOOK).exists())
        self.assertFalse((self.root / b.SCRIPT).exists())

    def test_foreign_override_blocks_before_migration(self):
        p = self.root / b.HOOK
        p.parent.mkdir(parents=True)
        p.write_text('foreign')
        with self.assertRaises(RuntimeError): b.run(self.root)
        self.assertEqual(p.read_text(), 'foreign')
        self.assertTrue((self.entries / (MID + '-old.conf')).exists())

    def test_unmounted_esp_blocks(self):
        import shutil
        shutil.rmtree(self.root / 'boot')
        (self.root / 'boot').mkdir()
        (self.root / 'etc/fstab').write_text('UUID=1 /boot vfat defaults 0 2\n')
        self.assertEqual(b.main(['--root', str(self.root)]), 1)
        self.assertFalse((self.root / b.HOOK).exists())

    def test_mismatched_packaged_script_keeps_guard(self):
        b.run(self.root)
        p = self.root / 'usr/share/libalpm/hooks/00-windoesnot-boot-guard.hook'
        p.parent.mkdir(parents=True)
        p.write_bytes(b.PACKAGED_HOOK)
        b.run(self.root)
        self.assertTrue((self.root / b.HOOK).exists())

if __name__ == '__main__': unittest.main()
