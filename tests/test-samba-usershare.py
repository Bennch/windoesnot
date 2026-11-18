#!/usr/bin/env python3
"""Validation and command tests; never touches the host Samba configuration."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('usershare', ROOT / 'tools/samba/usershare.py')
share = importlib.util.module_from_spec(spec)
spec.loader.exec_module(share)


class UsershareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.folder = self.home / 'Documents'
        self.folder.mkdir()
        (self.home / 'escape').symlink_to(self.root, target_is_directory=True)

    def test_names(self):
        for value in ('', '../x', '-option', 'a/b', 'x\nfoo', 'a' * 81):
            with self.subTest(value=value), self.assertRaises(ValueError):
                share.validate_name(value)
        self.assertEqual(share.validate_name('My_share-1'), 'My_share-1')

    def test_paths(self):
        for value in (self.home, self.root, self.home / 'escape', 'relative', self.home / 'missing'):
            with self.subTest(value=value), self.assertRaises((ValueError, OSError)):
                share.validate_path(value, self.home)
        self.assertEqual(share.validate_path(self.folder, self.home), str(self.folder))

    def test_commands(self):
        make = lambda **kw: share.add_command('Docs', self.folder, self.home, 'benni', **kw)
        self.assertEqual(make()[-2:], ['benni:R', 'guest_ok=n'])
        self.assertEqual(make(writable=True)[-2:], ['benni:F', 'guest_ok=n'])
        self.assertEqual(make(guest=True)[-2:], ['Everyone:R', 'guest_ok=y'])
        with self.assertRaises(ValueError):
            make(writable=True, guest=True)
        self.assertEqual(share.remove_command('Docs')[-1], 'Docs')
        with self.assertRaises(ValueError):
            share.remove_command('../Docs')

if __name__ == '__main__':
    unittest.main()
