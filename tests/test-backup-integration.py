#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('snapshots', ROOT / 'desktop/lib/windoesnot/snapshots.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class Boundaries(unittest.TestCase):
    def test_read_accepts_no_mutation_payload(self):
        backend.validate('status', {})
        for args in ({'id': '1'}, {'command': 'sh'}, {'daily': 1}):
            with self.assertRaises(ValueError):
                backend.validate('status', args)

    def test_snapshot_ids(self):
        backend.validate('delete', {'id': '500'})
        for value in ('0', '-1', '--all', '1 2', '1;id', '1-500', '', 1, True):
            with self.assertRaises(ValueError):
                backend.validate('delete', {'id': value})

    def test_only_supported_operations(self):
        for action in ('shell', 'rollback', 'set-config', 'create-config', ''):
            with self.assertRaises(ValueError):
                backend.validate(action, {})

    def test_schedule_bounds(self):
        valid = dict(monthly=2, weekly=3, daily=5, hourly=0)
        backend.validate('schedule', valid)
        for value in (-1, 366, True, '5', '5;id', 1.5):
            with self.assertRaises(ValueError):
                backend.validate('schedule', {**valid, 'daily': value})
        with self.assertRaises(ValueError):
            backend.validate('schedule', {**valid, 'ALLOW_USERS': 'anyone'})

    def test_structured_list(self):
        rows = [{'number': 0, 'date': ''}, {'number': 9, 'date': '2026-10-23 10:00:00'},
                {'number': 10, 'date': '2026-10-23 11:00:00'}]
        self.assertEqual([x['id'] for x in backend.parse_snapshots(json.dumps({'root': rows}))], ['10', '9'])

    def test_list_preserves_classification_metadata(self):
        rows = [
            {'number': 1, 'description': 'WinDoesNot installation', 'type': 'single', 'cleanup': ''},
            {'number': 2, 'description': 'pacman -Syu', 'type': 'pre', 'cleanup': 'number'},
            {'number': 3, 'description': 'timeline', 'type': 'single', 'cleanup': 'timeline'},
        ]
        result = backend.parse_snapshots(json.dumps({'root': rows}))
        self.assertEqual(result[0]['cleanup'], 'timeline')
        self.assertEqual(result[1]['type'], 'pre')
        self.assertEqual(result[2]['description'], 'WinDoesNot installation')
        # Old listings without the additional columns remain readable.
        old = backend.parse_snapshots('[{"number": 9}]')[0]
        self.assertEqual((old['type'], old['cleanup']), ('', ''))

    def test_guard_restores_fallback_when_its_shell_exits(self):
        with tempfile.TemporaryDirectory(prefix='wdn-auth-guard-test-') as temporary:
            directory = Path(temporary)
            marker = directory / 'restored'
            fallback = directory / 'fallback'
            fallback.write_text('#!/usr/bin/python3\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("restored")\n')
            fallback.chmod(0o755)
            script = (ROOT / 'desktop/bin/windoesnot-auth-guard').read_text()
            script = script.replace("GNOME = '/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1'", 'GNOME = ' + repr(str(fallback)))
            script = script.replace("Path('/run/user')", 'Path(' + repr(str(directory)) + ')')
            (directory / str(__import__('os').getuid())).mkdir()
            guard = directory / 'guard.py'
            guard.write_text(script)
            owner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
            try:
                subprocess.run([sys.executable, str(guard), 'acquire', str(owner.pid)], check=True)
                subprocess.run([sys.executable, str(guard), 'heartbeat', str(owner.pid)], check=True)
                self.assertFalse(marker.exists())
                owner.terminate()
                owner.wait(timeout=5)
                for _ in range(40):
                    if marker.exists():
                        break
                    time.sleep(0.1)
                self.assertTrue(marker.exists(), 'Fallback must start after shell exit')
            finally:
                if owner.poll() is None:
                    owner.terminate()
                    owner.wait(timeout=5)

    def test_read_policy_is_scoped_to_exact_executable_and_argument(self):
        root = ET.parse(ROOT / 'desktop/share/polkit-1/actions/org.windoesnot.snapshots.policy')
        actions = root.findall('action')
        self.assertEqual(len(actions), 4)
        for action in actions:
            self.assertEqual(action.findtext('defaults/allow_any'), 'no')
            self.assertEqual(action.findtext('defaults/allow_inactive'), 'no')
            annotations = {x.attrib['key']: x.text for x in action.findall('annotate')}
            self.assertEqual(annotations['org.freedesktop.policykit.exec.path'], '/usr/lib/windoesnot/snapshots.py')
            self.assertEqual(annotations['org.freedesktop.policykit.exec.argv1'], action.attrib['id'].rsplit('.', 1)[1])
            self.assertEqual(action.findtext('defaults/allow_active'), 'yes' if action.attrib['id'].endswith('.status') else 'auth_admin')


if __name__ == '__main__':
    unittest.main()
