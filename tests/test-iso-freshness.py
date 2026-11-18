#!/usr/bin/env python3
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('freshness', Path(__file__).resolve().parents[1] / 'tools/check-iso-freshness.py')
freshness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freshness)


class FreshnessTests(unittest.TestCase):
    def test_classification(self):
        matches = {'foo': ['core'], 'bar': ['cachyos']}
        self.assertEqual(freshness.classify('foo', '1-1', '1-2', 'core', matches), 'a')
        self.assertEqual(freshness.classify('bar', '1-1', '1-1.1', 'cachyos-v3', matches), 'b')
        self.assertEqual(freshness.classify('bar', '1-1', '1-2', 'cachyos-v3', matches), 'c')
        self.assertEqual(freshness.classify('foo', '1-1', '1-1.1', 'extra', matches), 'c')

    def test_snapshot_and_threshold_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sync = root / 'sync'; sync.mkdir()
            local = root / 'local' / 'foo-1-1'; local.mkdir(parents=True)
            desc = b'%NAME%\nfoo\n\n%VERSION%\n1-1\n\n'
            (local / 'desc').write_bytes(desc)
            with tarfile.open(sync / 'core.db', 'w:gz') as archive:
                entry = tarfile.TarInfo('foo-1-1/desc'); entry.size = len(desc)
                archive.addfile(entry, io.BytesIO(desc))
            target = root / 'metadata.json'
            freshness.snapshot(sync, local.parent, target)
            metadata = json.loads(target.read_text())
            self.assertEqual(metadata['matches'], {'foo': ['core']})
            self.assertEqual(metadata['oldest_sync'], (sync / 'core.db').stat().st_ctime)
            self.assertFalse(freshness.gate_failed(25, 25, 24))
            self.assertTrue(freshness.gate_failed(26, 25, 1))
            self.assertTrue(freshness.gate_failed(0, 25, 24.01))

    def test_missing_sync_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                freshness.snapshot(root, root, root / 'output')


if __name__ == '__main__':
    unittest.main()
