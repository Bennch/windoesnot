#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import subprocess
import tarfile
import io
import json
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'out/update-gate/work'; WORK.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('resolver',ROOT/'tools/check-upstream-resolvability.py'); resolver=importlib.util.module_from_spec(spec); spec.loader.exec_module(resolver)

def run(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, **kwargs)

def pkg(path,name,version,depends=(),extra=()):
    text='pkgname = '+name+'\npkgbase = '+name+'\npkgver = '+version+'\npkgdesc = gate fixture\nurl = https://example.invalid\nbuilddate = 1\npackager = Test\nsize = 0\narch = any\nlicense = custom\n'
    text+=''.join('depend = '+x+'\n' for x in depends)+''.join(x+'\n' for x in extra)
    with tarfile.open(path,'w:gz') as tf:
        data=text.encode(); info=tarfile.TarInfo('.PKGINFO'); info.size=len(data); tf.addfile(info,io.BytesIO(data))

def installed(db,name,version,depends=()):
    d=db/'local'/f'{name}-{version}'; d.mkdir(parents=True)
    s=f'%NAME%\n{name}\n\n%VERSION%\n{version}\n\n%DESC%\ngate fixture\n\n%ARCH%\nany\n\n%REASON%\n0\n\n'
    if depends: s+='%DEPENDS%\n'+'\n'.join(depends)+'\n\n'
    (d/'desc').write_text(s); (d/'files').write_text('%FILES%\n\n')

class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=WORK); self.p=Path(self.temp.name); self.db=self.p/'db'; (self.db/'local').mkdir(parents=True); (self.db/'local/ALPM_DB_VERSION').write_text('9\n'); (self.p/'root').mkdir()
        installed(self.db,'gate-libffi','1-1'); installed(self.db,'gate-lib32-libffi','1-1',['gate-libffi=1'])
    def tearDown(self): self.temp.cleanup()
    def repo(self,name,entries):
        d=self.p/name; d.mkdir(); paths=[]
        for n,v,deps,extra in entries:
            f=d/f'{n}-{v}-any.pkg.tar.gz'; pkg(f,n,v,deps,extra); paths.append(str(f))
        r=run(['repo-add',str(d/(name+'.db.tar.gz')),*paths],env={**os.environ,'TMPDIR':str(self.p)})
        self.assertEqual(r.returncode,0,r.stderr)
        return d
    def preview(self,repos):
        config=self.p/'pacman.conf'; config.write_text('[options]\nArchitecture = x86_64\nSigLevel = Never\nDisableSandbox\n' + ''.join(f'[{name}]\nServer = file://{path}\n' for name,path in repos))
        args=['unshare','-Ur','pacman','--config',str(config),'--root',str(self.p/'root'),'--dbpath',str(self.db),'--cachedir',str(self.p),'--logfile',str(self.p/'pacman.log')]
        r=run(args+['-Sy','--noconfirm'],env={**os.environ,'LC_ALL':'C'}); self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        return run(args+['-Su','--print','--noconfirm'],env={**os.environ,'LC_ALL':'C'})
    def test_priority_and_bridge(self):
        first=self.repo('first',[('gate-libffi','1-1.1',[],[])])
        later=self.repo('later',[('gate-libffi','2-1',[],[]),('gate-lib32-libffi','2-1',['gate-libffi=2-1'],[])])
        before=(self.db/'local/gate-libffi-1-1/desc').read_bytes()
        # NOTE: the libffi analogue (exact '=' dependency) does NOT fail on pacman 7.1: pacman falls back to the later
        # repo. The reproducible failure class is the '>=' dependency (see test_firefox_greater_equal, observed live on
        # 0.1.0-31 on 2026-11-18). The historic libffi trace is therefore not replayed here.
        self.assertEqual(before,(self.db/'local/gate-libffi-1-1/desc').read_bytes())
        bridge=self.repo('bridge',[('gate-libffi','2-1',[],[])])
        pos=self.preview([('bridge',bridge),('first',first),('later',later)])
        self.assertEqual(pos.returncode,0,pos.stdout+pos.stderr)
        equal=self.repo('equal',[('gate-libffi','1-1',[],[])])
        control=self.preview([('equal',equal),('later',later)])
        self.assertEqual(control.returncode,0,control.stdout+control.stderr)
        self.assertIn('later/gate-libffi-2-1',control.stdout)

    def test_firefox_greater_equal(self):
        installed(self.db,'gate-firefox','160.0-1')
        installed(self.db,'gate-firefox-i18n-de','160.0-1',['gate-firefox>=160.0'])
        first=self.repo('first',[('gate-firefox','160.0-1.1',[],[])])
        later=self.repo('later',[('gate-firefox','160.0.1-1',[],[]),('gate-firefox-i18n-de','160.0.1-1',['gate-firefox>=160.0.1'],[])])
        r=self.preview([('first',first),('later',later)])
        self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(resolver.classify(r.returncode,r.stdout+r.stderr),'UNSATISFIABLE_DEPENDENCY')
        bridge=self.repo('bridge',[('gate-firefox','160.0.1-1',[],[])])
        pos=self.preview([('bridge',bridge),('first',first),('later',later)])
        self.assertEqual(pos.returncode,0,pos.stdout+pos.stderr)

    def test_explicit_repo_target_resolves_shadowing(self):
        installed(self.db,'gate-firefox','160.0-1')
        installed(self.db,'gate-firefox-i18n-de','160.0-1',['gate-firefox>=160.0'])
        first=self.repo('first',[('gate-firefox','160.0-1.1',[],[])])
        later=self.repo('later',[('gate-firefox','160.0.1-1',[],[]),('gate-firefox-i18n-de','160.0.1-1',['gate-firefox>=160.0.1'],[])])
        config=self.p/'pacman.conf'; config.write_text('[options]\nArchitecture = x86_64\nSigLevel = Never\nDisableSandbox\n[first]\nServer = file://%s\n[later]\nServer = file://%s\n'%(first,later))
        args=['unshare','-Ur','pacman','--config',str(config),'--root',str(self.p/'root'),'--dbpath',str(self.db),'--cachedir',str(self.p),'--logfile',str(self.p/'pacman.log')]
        run(args+['-Sy','--noconfirm'],env={**os.environ,'LC_ALL':'C'})
        r=run(args+['-Su','--print','--noconfirm','later/gate-firefox'],env={**os.environ,'LC_ALL':'C'})
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('later/gate-firefox-160.0.1-1',r.stdout)

    def test_shadowing_real_databases(self):
        first=self.repo('first',[('gate-libffi','1-1.1',[],[]),('gate-epoch','1:1-1',[],[])])
        later=self.repo('later',[('gate-libffi','2-1',[],[]),('gate-epoch','2-1',[],[]),('gate-only','1-1',[],[])])
        sync=self.p/'sync'; sync.mkdir()
        for name, repo in [('first',first),('later',later)]:
            (sync/(name+'.db')).write_bytes((repo/(name+'.db.tar.gz')).read_bytes())
        config=self.p/'shadow.conf'; included=self.p/'repos.conf'; included.write_text('[first]\n[later]\n'); config.write_text('[options]\nInclude = '+str(included)+'\n')
        r=run(['python3',str(ROOT/'tools/check-upstream-resolvability.py'),'--config',str(config),'--detect-shadowing',str(sync)])
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(json.loads(r.stdout),[{'name':'gate-libffi','earlier_repo':'first','earlier_version':'1-1.1','later_repo':'later','later_version':'2-1'}])
        (sync/'later.db').write_text('corrupt')
        r=run(['python3',str(ROOT/'tools/check-upstream-resolvability.py'),'--config',str(config),'--detect-shadowing',str(sync)])
        self.assertEqual(r.returncode,2,r.stdout+r.stderr)

    def test_unsatisfiable_control(self):
        repo=self.repo('broken',[('gate-lib32-libffi','2-1',['gate-libffi=3'],[])])
        r=self.preview([('broken',repo)])
        self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(resolver.classify(r.returncode,r.stdout+r.stderr),'UNSATISFIABLE_DEPENDENCY',r.stdout+r.stderr)
    def test_epoch_and_newer_installed(self):
        installed(self.db,'gate-epoch','1:2-1'); installed(self.db,'gate-newer','3-1')
        repo=self.repo('versions',[('gate-epoch','1:3-1',[],[]),('gate-newer','2-1',[],[])])
        r=self.preview([('versions',repo)]); self.assertEqual(r.returncode,0,r.stderr); self.assertIn('gate-epoch',r.stdout); self.assertNotIn('gate-newer',r.stdout)
    def test_provides_and_conflicts(self):
        installed(self.db,'gate-client','1-1')
        repo=self.repo('provider',[
            ('gate-client','2-1',['gate-virtual=2'],[]),
            ('gate-provider','2-1',[],['provides = gate-virtual=2']),
        ])
        r=self.preview([('provider',repo)]); self.assertEqual(r.returncode,0,r.stdout+r.stderr); self.assertIn('gate-provider',r.stdout)
    def test_replacement(self):
        installed(self.db,'gate-old','1-1')
        repo=self.repo('replacement',[('gate-new','2-1',[],['replaces = gate-old','conflict = gate-old'])])
        r=self.preview([('replacement',repo)]); self.assertEqual(r.returncode,0,r.stdout+r.stderr); self.assertIn('gate-new',r.stdout)
    def test_missing_image_never_passes(self):
        r=run(['python3',str(ROOT/'tools/check-upstream-resolvability.py'),'--config','/missing','--local-db','/missing','--pacman-d','/missing','--image','archlinux:latest'])
        self.assertNotEqual(r.returncode,0); self.assertIn('INFRA_ERROR',r.stdout)

if __name__=='__main__': unittest.main(verbosity=2)
