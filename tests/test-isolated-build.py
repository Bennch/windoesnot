#!/usr/bin/env python3
"""Pure-logic tests of windoesnot-isolated-build (no root, no container)."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('wib', str(ROOT / 'desktop/bin/windoesnot-isolated-build'))
spec = importlib.util.spec_from_loader('wib', loader)
wib = importlib.util.module_from_spec(spec)
loader.exec_module(wib)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name)
        (self.src / 'PKGBUILD').write_text('pkgname=x\n')

    def test_digest_is_stable_and_content_sensitive(self):
        first = wib.digest(self.src)
        self.assertEqual(first, wib.digest(self.src))
        (self.src / 'PKGBUILD').write_text('pkgname=y\n')
        self.assertNotEqual(first, wib.digest(self.src))

    def test_added_file_changes_digest(self):
        first = wib.digest(self.src)
        (self.src / 'patch.diff').write_text('x')
        self.assertNotEqual(first, wib.digest(self.src))

    def test_symlink_is_refused(self):
        (self.src / 'leak').symlink_to('/etc/passwd')
        with self.assertRaises(wib.BuildError):
            wib.source_files(self.src)

    def test_missing_pkgbuild_is_refused(self):
        (self.src / 'PKGBUILD').unlink()
        with self.assertRaises(wib.BuildError):
            wib.source_files(self.src)

    def test_git_directory_is_ignored(self):
        (self.src / '.git').mkdir()
        (self.src / '.git/config').write_text('secret')
        _, files = wib.source_files(self.src)
        self.assertEqual([f.name for f in files], ['PKGBUILD'])

    def test_private_ranges_stay_in_the_high_block(self):
        for _ in range(50):
            base = wib.private_range()
            self.assertGreaterEqual(base, 0x40000000)
            self.assertLess(base + 65536, 2 ** 32)

    def test_system_accounts_are_refused(self):
        with self.assertRaises(wib.BuildError):
            wib.build(self.src, self.tmp.name, 0, 0)


if __name__ == '__main__':
    unittest.main()
