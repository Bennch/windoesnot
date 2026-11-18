#!/usr/bin/env python3
"""Unprivileged CLI contract checks, using only a temporary fake state."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-share'

class ShareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.home())
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'folder'
        self.folder.mkdir()
        self.state = self.root / 'state.json'
        self.env = {**os.environ, 'WINDOESNOT_SHARE_STATE': str(self.state)}

    def cli(self, *args, input=None):
        p = subprocess.run([str(TOOL), *args], env=self.env, text=True, input=input, capture_output=True)
        self.assertEqual(len(p.stdout.splitlines()), 1, p.stdout)
        return json.loads(p.stdout)

    def test_share_lifecycle(self):
        self.assertTrue(self.cli('status')['configured'])
        opts = ('add', '--name', 'Fotos', '--path', str(self.folder), '--access', 'write')
        self.assertEqual(self.cli(*opts)['error'], 'needs-password')
        self.assertTrue(self.cli('set-password', input='secret\n')['ok'])
        self.assertTrue(self.cli(*opts)['ok'])
        item = self.cli('status')['shares'][0]
        self.assertEqual((item['name'], item['path'], item['access'], item['guest']), ('Fotos', str(self.folder), 'write', False))
        self.assertEqual(self.cli(*opts)['error'], 'exists')
        self.assertTrue(self.cli('remove', 'Fotos')['ok'])
        self.assertEqual(self.cli('status')['shares'], [])

    def test_validation(self):
        def add(name, path, access='read', *extra):
            return self.cli('add', '--name', name, '--path', str(path), '--access', access, *extra)
        self.assertEqual(add('../bad', self.folder)['error'], 'invalid-name')
        self.assertEqual(add('Good', '/etc')['error'], 'invalid-path')
        (self.root / 'escape').symlink_to('/etc')
        self.assertEqual(add('Good', self.root / 'escape')['error'], 'invalid-path')
        self.assertEqual(add('Good', self.folder, 'write', '--guest')['error'], 'failed')
        self.assertTrue(add('Good', self.folder, 'read', '--guest')['ok'])
        self.assertTrue(self.cli('status')['shares'][0]['guest'])
        self.assertEqual(self.cli('add')['error'], 'failed')

if __name__ == '__main__': unittest.main()
