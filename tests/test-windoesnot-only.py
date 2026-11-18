#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fixture', ROOT / 'tests/test-upstream-resolvability.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

class OnlyTests(fixture.ResolverTests):
    def run_update(self, repos):
        config = self.p/'pacman.conf'
        config.write_text('[options]\nArchitecture = x86_64\nSigLevel = Never\nDisableSandbox\n' + ''.join(f'[{n}]\nServer = file://{p}\n' for n, p in repos))
        code = '''import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("update", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec); loader.exec_module(m)
sys.exit(m.windoesnot_only(True, sys.argv[2], sys.argv[3:]))'''
        return subprocess.run(['unshare', '-Ur', 'python3', '-c', code, str(ROOT/'desktop/bin/windoesnot-update'), str(config), '--root', str(self.p/'root'), '--dbpath', str(self.db), '--cachedir', str(self.p), '--logfile', str(self.p/'pacman.log')], text=True, capture_output=True, env={**os.environ, 'LC_ALL':'C'})

    def test_only_repo_and_installed_packages(self):
        fixture.installed(self.db, 'windoesnot-app', '1-1')
        ours = self.repo('windoesnot', [('windoesnot-app','2-1',[],[])])
        other = self.repo('other', [('gate-libffi','2-1',[],[])])
        (self.db/'sync').mkdir(exist_ok=True)
        marker = self.db/'sync/other.db'
        marker.write_bytes((other/'other.db.tar.gz').read_bytes())
        before = marker.read_bytes()
        result = self.run_update([('other', other), ('windoesnot', ours)])
        self.assertEqual(marker.read_bytes(), before)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.db/'local/windoesnot-app-2-1').exists())
        self.assertTrue((self.db/'local/gate-libffi-1-1').exists())

    def test_pinned_desktop_and_tools_upgrade_together(self):
        fixture.installed(self.db, 'windoesnot-desktop', '1-1', ['windoesnot-tools=1-1'])
        fixture.installed(self.db, 'windoesnot-tools', '1-1')
        ours = self.repo('windoesnot', [('windoesnot-desktop','2-1',['windoesnot-tools=2-1'],[]), ('windoesnot-tools','2-1',[],[])])
        result = self.run_update([('windoesnot', ours)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.db/'local/windoesnot-desktop-2-1').exists())
        self.assertTrue((self.db/'local/windoesnot-tools-2-1').exists())

    def test_foreign_dependency_in_own_repo_is_rejected(self):
        fixture.installed(self.db, 'windoesnot-app', '1-1')
        ours = self.repo('windoesnot', [('windoesnot-app','2-1',['foreign-lib'],[]), ('foreign-lib','1-1',[],[])])
        result = self.run_update([('windoesnot', ours)])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.db/'local/windoesnot-app-1-1').exists())
        self.assertFalse((self.db/'local/foreign-lib-1-1').exists())

    def test_conflict_does_not_remove_foreign_package(self):
        fixture.installed(self.db, 'windoesnot-app', '1-1')
        fixture.installed(self.db, 'foreign-app', '1-1')
        ours = self.repo('windoesnot', [('windoesnot-app','2-1',[],['conflict = foreign-app'])])
        result = self.run_update([('windoesnot', ours)])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.db/'local/foreign-app-1-1').exists())
        self.assertTrue((self.db/'local/windoesnot-app-1-1').exists())

    def test_missing_dependency_changes_no_packages(self):
        fixture.installed(self.db, 'windoesnot-app', '1-1')
        ours = self.repo('windoesnot', [('windoesnot-app','2-1',['missing-lib>=2'],[])])
        other = self.repo('other', [('missing-lib','2-1',[],[])])
        result = self.run_update([('other', other), ('windoesnot', ours)])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Abhängigkeiten', result.stderr)
        self.assertTrue((self.db/'local/windoesnot-app-1-1').exists())
        self.assertFalse((self.db/'sync/other.db').exists())

if __name__ == '__main__': unittest.main()
