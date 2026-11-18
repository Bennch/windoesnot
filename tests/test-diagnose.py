#!/usr/bin/env python3
"""windoesnot-diagnose: redaction, known-harmless tagging, pacman.log parsing, check results (all offline)."""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('diag', str(ROOT / 'desktop/bin/windoesnot-diagnose'))
diag = importlib.util.module_from_spec(importlib.util.spec_from_loader('diag', loader))
loader.exec_module(diag)


class Diagnose(unittest.TestCase):
    def test_redaction(self):
        with mock.patch.dict(os.environ, {'USER': 'alice'}), mock.patch('socket.gethostname', return_value='workstation'), \
                mock.patch('os.path.expanduser', return_value='/home/alice'):
            clean = diag.redactor()
            text = clean('alice at workstation: /home/alice/x 192.168.1.20 aa:bb:cc:dd:ee:ff fe80:1:2:3:4:5:6:7')
        for secret in ('alice', 'workstation', '192.168', 'aa:bb', 'fe80'):
            self.assertNotIn(secret, text)

    def test_pacman_log(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'pacman.log'
            log.write_text('[2026-11-18T10:00:00+0100] [ALPM] upgraded foo (1.0-1 -> 1.1-1)\n'
                           '[2026-11-18T10:00:01+0100] [PACMAN] Running x\n'
                           '[2026-11-17T09:00:00+0100] [ALPM] removed bar (2.0-1)\n')
            with mock.patch.object(diag, 'PACMAN_LOG', str(log)):
                result = diag.package_changes()
        names = [(c['action'], c['package']) for c in result['entries']]
        self.assertEqual(names, [('upgraded', 'foo'), ('removed', 'bar')])

    def test_known_and_grouping(self):
        records = [{'MESSAGE': 'kvm [1]: ignored rdmsr: 0x64d', 'SYSLOG_IDENTIFIER': 'kernel', '__REALTIME_TIMESTAMP': '2000000'},
                   {'MESSAGE': 'kvm [2]: ignored rdmsr: 0x64d', 'SYSLOG_IDENTIFIER': 'kernel', '__REALTIME_TIMESTAMP': '3000000'},
                   {'MESSAGE': 'real failure', 'SYSLOG_IDENTIFIER': 'x', '__REALTIME_TIMESTAMP': '1000000'}]
        with mock.patch.object(diag, 'run', return_value=(0, '\n'.join(json.dumps(r) for r in records))):
            result = diag.boot_errors()
        by_message = {e['message']: e for e in result['entries']}
        self.assertEqual(len(result['entries']), 2)
        self.assertEqual(sum(e['count'] for e in result['entries'] if e['known']), 2)
        self.assertEqual(by_message['real failure']['known'], '')

    def test_checks_never_raise(self):
        with mock.patch.object(diag, 'run', side_effect=OSError('boom')):
            results = diag.checks()
        self.assertEqual(len(results), len(diag.CHECKS))
        self.assertTrue(all(r['status'] in ('ok', 'warn', 'unknown') for r in results))

    def test_bluetooth_blocked(self):
        with mock.patch.object(diag, 'run', return_value=(0, '0: hci0: Bluetooth\n\tSoft blocked: yes\n\tHard blocked: no\n')):
            self.assertEqual(diag.check_bluetooth(), ('warn', 'soft-blocked'))

    def test_new_checks(self):
        with mock.patch.object(diag, 'run', return_value=(0, '00:02.0 VGA compatible controller: Intel Corporation GPU\n')):
            self.assertEqual(diag.check_gpu(), ('ok', 'none'))
        with mock.patch.object(diag, 'run', side_effect=[(0, '01:00.0 VGA compatible controller: NVIDIA GPU\n'), (0, 'Module Size Used by\n')]), mock.patch('os.path.isdir', return_value=False):
            self.assertEqual(diag.check_gpu(), ('warn', 'no-driver'))
        with mock.patch.object(diag, 'run', return_value=(0, '01:00.0 VGA compatible controller: NVIDIA GPU\n\tKernel driver in use: nouveau\n')):
            self.assertEqual(diag.check_gpu(), ('unknown', ''))
        with mock.patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': 'test'}), mock.patch.object(diag, 'run', return_value=(0, '[{"disabled": true}]')):
            self.assertEqual(diag.check_display(), ('warn', 'disabled'))
        with mock.patch.object(diag, 'run', return_value=(1, '')):
            self.assertEqual(diag.check_suspend(), ('unknown', ''))
        with mock.patch.object(diag, 'run', return_value=(0, 'Failed to suspend')):
            self.assertEqual(diag.check_suspend(), ('warn', 'failed'))
        with mock.patch('os.path.isfile', return_value=True), mock.patch.object(diag, 'run', return_value=(0, 'number,type\n' + ''.join('%d,single\n' % i for i in range(1, 51)))):
            self.assertEqual(diag.check_snapshots(), ('warn', 'many'))
        boot = 'BootOrder: 0001,0002\nBoot0001* Windows Boot Manager\tHD(...)\nBoot0002* Linux\tHD(...)\n'
        with mock.patch('os.path.isdir', return_value=True), mock.patch.object(diag, 'run', return_value=(0, boot)):
            self.assertEqual(diag.check_boot(), ('warn', 'windows-first'))
        with mock.patch('builtins.open', mock.mock_open(read_data='{"enabled": false}')):
            self.assertEqual(diag.check_firewall(), ('warn', 'off'))
        with mock.patch('builtins.open', mock.mock_open(read_data='{"enabled": true}')), mock.patch.object(diag, 'run', return_value=(3, 'inactive\n')):
            self.assertEqual(diag.check_firewall(), ('warn', 'inactive'))
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'pacman.log'
            log.write_text('[2020-01-01T00:00:00+0000] [ALPM] upgraded foo (1 -> 2)\n')
            with mock.patch.object(diag, 'PACMAN_LOG', str(log)):
                self.assertEqual(diag.check_updates(), ('warn', 'old'))
                log.write_text('')
                self.assertEqual(diag.check_updates(), ('unknown', ''))

    def test_new_checks_are_in_report_and_redacted(self):
        data = {'time': 1, 'boot': 0, 'kernel': 'test', 'failed': [], 'errors': {'available': False, 'entries': []},
                'packages': {'entries': []}, 'hyprland': {'available': False, 'errors': [], 'plugins': []},
                'disk': [], 'checks': [{'id': 'boot', 'status': 'warn', 'detail': 'windows-first'}]}
        self.assertIn('boot: warn windows-first', diag.report(data))


if __name__ == '__main__':
    unittest.main()
