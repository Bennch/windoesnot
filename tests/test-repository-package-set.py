#!/usr/bin/env python3
"""Exercise the real repo builder with disposable metadata-only test packages.

No installation, signing key or system Pacman database is used.
"""
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = ['windoesnot-desktop', 'windoesnot-tools', 'windoesnot-plugins', 'windoesnot-components']


class RepositoryPackageSet(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='windoesnot-repo-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packages = self.root / 'packages'
        self.packages.mkdir()
        self.output = self.root / 'repository'

    def package(self, name, version):
        metadata = '\n'.join([
            'pkgname = ' + name, 'pkgbase = ' + name, 'pkgver = ' + version,
            'pkgdesc = Synthetic test metadata only - never install',
            'url = https://windoesnot.me', 'builddate = 1',
            'packager = Test', 'size = 0', 'arch = any', 'license = MIT', '',
        ]).encode()
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w') as archive:
            entry = tarfile.TarInfo('.PKGINFO')
            entry.size = len(metadata)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(metadata))
        dest = self.packages / f'{name}-{version}-any.pkg.tar.zst'
        subprocess.run(['zstd', '-q', '-o', str(dest)], input=raw.getvalue(), check=True)

    def core(self):
        for name in CORE:
            self.package(name, '0.0.0-1')

    def build(self, success):
        result = subprocess.run([
            'python3', str(ROOT / 'tools/build-repository.py'),
            '--packages', str(self.packages), '--output', str(self.output), '--unsigned-test',
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        if not success:
            self.assertFalse(self.output.exists())
        return result

    def test_existing_four_package_contract_still_works(self):
        self.core()
        self.build(True)
        result = json.loads((self.output / 'REPOSITORY.json').read_text())
        self.assertEqual(set(result['packages']), set(CORE))
        self.assertTrue(result['private_test_only'])
        self.assertFalse(result['signed'])

    def test_store_has_independent_version_and_is_in_actual_database(self):
        self.core()
        self.package('windoesnot-store', '0.0.1-1')
        self.build(True)
        result = json.loads((self.output / 'REPOSITORY.json').read_text())
        self.assertEqual(result['packages']['windoesnot-store']['version'], '0.0.1-1')
        with tarfile.open(self.output / 'windoesnot.db.tar.gz') as db:
            self.assertTrue(any(p.name == 'windoesnot-store-0.0.1-1/desc' for p in db))

    def test_store_cannot_replace_missing_core_package(self):
        self.core()
        next(self.packages.glob('windoesnot-tools-*')).unlink()
        self.package('windoesnot-store', '0.0.1-1')
        self.build(False)

    def test_mixed_desktop_versions_rejected(self):
        self.core()
        next(self.packages.glob('windoesnot-tools-*')).unlink()
        self.package('windoesnot-tools', '0.0.0-2')
        self.package('windoesnot-store', '0.0.1-1')
        self.build(False)

    def test_duplicate_store_rejected(self):
        self.core()
        self.package('windoesnot-store', '0.0.1-1')
        self.package('windoesnot-store', '0.0.1-2')
        self.build(False)

    def test_unexpected_package_rejected(self):
        self.core()
        self.package('unrelated', '0.0.1-1')
        self.build(False)


if __name__ == '__main__':
    unittest.main()
