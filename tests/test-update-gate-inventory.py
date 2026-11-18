#!/usr/bin/env python3
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]; WORK=ROOT/'out/update-gate/work'; WORK.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('inventory',ROOT/'tools/update-gate-inventory.py'); inventory=importlib.util.module_from_spec(spec); spec.loader.exec_module(inventory)

def package(path,name='gate-one',version='1-1',arch='any'):
    data=f'pkgname = {name}\npkgver = {version}\narch = {arch}\n'.encode()
    with tarfile.open(path,'w:gz') as t:
        info=tarfile.TarInfo('.PKGINFO'); info.size=len(data); t.addfile(info,io.BytesIO(data))

class InventoryTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(dir=WORK); self.p=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_pkginfo_version_and_arch(self):
        package(self.p/'one.pkg.tar.gz',version='3:4-2'); a=inventory.packages(self.p); self.assertEqual((a[0]['name'],a[0]['version'],a[0]['arch']),('gate-one','3:4-2','any'))
    def test_duplicate(self):
        package(self.p/'one.pkg.tar.gz'); package(self.p/'two.pkg.tar.gz',version='2-1')
        with self.assertRaisesRegex(ValueError,'duplicate'): inventory.packages(self.p)
    def test_broken_and_stray(self):
        (self.p/'broken.pkg.tar.gz').write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError,'broken archive'): inventory.packages(self.p)
        (self.p/'broken.pkg.tar.gz').unlink(); (self.p/'stray').write_text('x')
        with self.assertRaisesRegex(ValueError,'unexpected'): inventory.packages(self.p)
if __name__=='__main__': unittest.main(verbosity=2)
