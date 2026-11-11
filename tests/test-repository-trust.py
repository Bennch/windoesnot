#!/usr/bin/env python3
"""Trust bootstrap regression checks against an existing signed PRIVATE fixture."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
REPO=Path(sys.argv.pop(1)).resolve() if len(sys.argv)>1 else ROOT/'out/repos/signed-r8-update-16'

class TrustBootstrap(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wdn-client-check-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.fingerprint=json.loads((REPO/'REPOSITORY.json').read_text())['key']
    def prepare(self,repo=REPO,extra=('--allow-test-repository',),fingerprint=None,server='http://10.0.2.2:18763'):
        self.output=self.root/'client'
        return subprocess.run(['python3',str(ROOT/'tools/prepare-repository-client.py'),
            '--repository',str(repo),'--fingerprint',fingerprint or self.fingerprint,
            '--server',server,'--output',str(self.output),*extra],text=True,capture_output=True)
    def modified(self,name):
        dest=self.root/'modified';shutil.copytree(REPO,dest,symlinks=False)
        p=dest/name;p.write_bytes(p.read_bytes()+b'CORRUPTED\n')
        return dest
    def test_valid_signed_test_bundle(self):
        p=self.prepare();self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('Required DatabaseRequired TrustedOnly',(self.output/'windoesnot.conf').read_text())
        self.assertIn('systemd-detect-virt',(self.output/'bootstrap.sh').read_text())
        subprocess.run(['bash','-n',str(self.output/'bootstrap.sh')],check=True)
    def test_wrong_full_fingerprint_rejected(self):
        self.assertNotEqual(self.prepare(fingerprint='0'*40).returncode,0)
        self.assertFalse(self.output.exists())
    def test_test_key_cannot_become_production(self):
        self.assertNotEqual(self.prepare(extra=(),server='https://updates.example.invalid/x86_64').returncode,0)
        self.assertFalse(self.output.exists())
    def test_unsigned_modified_manifest_rejected(self):
        self.assertNotEqual(self.prepare(repo=self.modified('REPOSITORY.json')).returncode,0)
        self.assertFalse(self.output.exists())
    def test_modified_database_rejected(self):
        self.assertNotEqual(self.prepare(repo=self.modified('windoesnot.db.tar.gz')).returncode,0)
        self.assertFalse(self.output.exists())
    def test_modified_package_rejected(self):
        name=next(REPO.glob('windoesnot-tools-*.pkg.tar.zst')).name
        self.assertNotEqual(self.prepare(repo=self.modified(name)).returncode,0)
        self.assertFalse(self.output.exists())

if __name__=='__main__': unittest.main()
