#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fixtures', ROOT / 'tests/test-upstream-resolvability.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

class PlanTests(fixture.ResolverTests):
    def plan(self, repos):
        # Synchronize the fixture in its private user namespace, then preview it.
        self.preview(repos)
        args = ['unshare', '-Ur', 'python3', str(ROOT/'desktop/bin/windoesnot-update-plan'),
                '--config', str(self.p/'pacman.conf'), '--root', str(self.p/'root'),
                '--dbpath', str(self.db), '--cachedir', str(self.p), '--logfile', str(self.p/'pacman.log')]
        result = subprocess.run(args, text=True, capture_output=True, env={**os.environ, 'LC_ALL': 'C'})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_plan_ok(self):
        repo = self.repo('first', [('gate-libffi', '1-1', [], [])])
        self.assertEqual(self.plan([('first', repo)])['status'], 'ok')

    def test_plan_fixed_and_multiple_with_epoch(self):
        for name in ('firefox', 'epoch'):
            fixture.installed(self.db, 'gate-'+name, '1:1-1' if name == 'epoch' else '1-1')
            fixture.installed(self.db, 'gate-'+name+'-i18n', '1-1')
        first = self.repo('first', [('gate-firefox','1-1.1',[],[]), ('gate-epoch','1:1-1.1',[],[])])
        later = self.repo('later', [('gate-firefox','2-1',[],[]), ('gate-epoch','1:2-1',[],[]),
                                  ('gate-firefox-i18n','2-1',['gate-firefox>=2'],[]),
                                  ('gate-epoch-i18n','2-1',['gate-epoch>=1:2'],[])])
        plan = self.plan([('first', first), ('later', later)])
        self.assertEqual(plan['status'], 'fixed', plan)
        self.assertEqual(set(plan['targets']), {'later/gate-firefox', 'later/gate-epoch'})

    def test_duplicate_firefox_dependency(self):
        fixture.installed(self.db, 'gate-firefox', '1-1')
        for language in ('de', 'en'):
            fixture.installed(self.db, 'gate-firefox-i18n-'+language, '1-1')
        first = self.repo('first', [('gate-firefox', '1-1.1', [], [])])
        later = self.repo('later', [('gate-firefox', '2-1', [], [])] + [
            ('gate-firefox-i18n-'+language, '2-1', ['gate-firefox>=2'], []) for language in ('de', 'en')])
        plan = self.plan([('first', first), ('later', later)])
        self.assertEqual(plan['status'], 'fixed', plan)
        self.assertEqual(plan['targets'], ['later/gate-firefox'])

    def test_plan_unresolvable(self):
        repo = self.repo('broken', [('gate-lib32-libffi', '2-1', ['gate-libffi>=3'], [])])
        plan = self.plan([('broken', repo)])
        self.assertEqual(plan['status'], 'unresolvable', plan)
        self.assertIn('gate-libffi>=3', plan['unresolved'])

if __name__ == '__main__': unittest.main()
