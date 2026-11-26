#!/usr/bin/env python3
"""security_status.py: every item in every state against fixture trees (no root, no real system)."""
import importlib.util
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('security_status', ROOT / 'desktop/lib/windoesnot/security_status.py')
sec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sec)
NOW = time.mktime((2026, 6, 15, 12, 0, 0, 0, 0, -1))


def put(base, rel, data):
    path = Path(base) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


class SecurityStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / 'root'
        self.home = Path(self._tmp.name) / 'home'
        self.root.mkdir()
        self.home.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def test_firewall(self):
        self.assertEqual(sec.check_firewall(self.root)['state'], 'unknown')
        put(self.root, 'etc/ufw/ufw.conf', '# x\nENABLED=yes\n')
        self.assertEqual(sec.check_firewall(self.root), {'id': 'firewall', 'state': 'ok', 'detail': 'on'})
        put(self.root, 'etc/ufw/ufw.conf', 'ENABLED=no\n')
        self.assertEqual(sec.check_firewall(self.root)['state'], 'bad')
        put(self.root, 'var/lib/windoesnot/firewall/state.json', json.dumps({'enabled': True, 'profile': 'home!'}))
        self.assertEqual(sec.check_firewall(self.root)['detail'], 'profile:home')
        put(self.root, 'var/lib/windoesnot/firewall/state.json', json.dumps({'enabled': False}))
        self.assertEqual(sec.check_firewall(self.root), {'id': 'firewall', 'state': 'bad', 'detail': 'off'})

    def test_updates(self):
        self.assertEqual(sec.check_updates(self.root, NOW)['state'], 'unknown')
        put(self.root, 'var/log/pacman.log', '[2026-06-10T08:00:00+0200] [ALPM] upgraded foo (1 -> 2)\n[2026-06-11T08:00:00+0200] [PACMAN] Running x\n')
        result = sec.check_updates(self.root, NOW)
        self.assertEqual((result['state'], result['detail']), ('ok', 'age:5'))
        put(self.root, 'var/log/pacman.log', '[2026-03-01 08:00:00] [ALPM] upgraded foo (1 -> 2)\n')
        self.assertEqual(sec.check_updates(self.root, NOW)['state'], 'warn')
        put(self.root, 'var/log/pacman.log', '[2027-01-01T08:00:00+0000] [ALPM] upgraded foo (1 -> 2)\n')
        self.assertEqual(sec.check_updates(self.root, NOW)['state'], 'unknown')

    def test_backups(self):
        cache = self.home / '.cache'
        self.assertEqual(sec.check_backups(self.home, cache, NOW)['detail'], 'off')
        config = {'enabled': True, 'target': 'x', 'schedule': 'daily'}
        put(self.home, '.config/windoesnot/filebackup.json', json.dumps(config))
        self.assertEqual(sec.check_backups(self.home, cache, NOW)['detail'], 'never')
        status = put(cache, 'windoesnot/filebackup-status.json', json.dumps({'state': 'idle', 'last_success': NOW - 3600}))
        self.assertEqual(sec.check_backups(self.home, cache, NOW), {'id': 'backups', 'state': 'ok', 'detail': 'ok:0'})
        status.write_text(json.dumps({'state': 'idle', 'last_success': NOW - 10 * 86400}))
        self.assertEqual(sec.check_backups(self.home, cache, NOW), {'id': 'backups', 'state': 'warn', 'detail': 'stale:10'})
        status.write_text(json.dumps({'state': 'error'}))
        self.assertEqual(sec.check_backups(self.home, cache, NOW)['detail'], 'error')

    def test_restore_points(self):
        self.assertEqual(sec.check_restore_points(self.root)['detail'], 'none')
        (self.root / '.snapshots/notes').mkdir(parents=True)
        self.assertEqual(sec.check_restore_points(self.root)['state'], 'warn')
        (self.root / '.snapshots/3').mkdir()
        (self.root / '.snapshots/4').mkdir()
        self.assertEqual(sec.check_restore_points(self.root), {'id': 'restore_points', 'state': 'ok', 'detail': 'count:2'})
        if os.geteuid() != 0:
            (self.root / '.snapshots').chmod(0)
            self.addCleanup((self.root / '.snapshots').chmod, 0o755)
            self.assertEqual(sec.check_restore_points(self.root)['state'], 'unknown')

    def _mounts(self, source):
        put(self.root, 'proc/self/mountinfo',
            '22 1 0:21 / /proc rw - proc proc rw\n'
            '30 1 0:27 /@ / rw,relatime shared:1 - btrfs %s rw,subvol=/@\n' % source)

    def test_encryption(self):
        self.assertEqual(sec.check_encryption(self.root)['state'], 'unknown')
        # root on /dev/mapper/root -> dm-0 (dm-crypt)
        self._mounts('/dev/mapper/root')
        (self.root / 'dev/mapper').mkdir(parents=True)
        (self.root / 'dev/dm-0').write_text('')
        os.symlink('../dm-0', self.root / 'dev/mapper/root')
        put(self.root, 'sys/class/block/dm-0/dm/uuid', 'CRYPT-LUKS2-abc-root\n')
        self.assertEqual(sec.check_encryption(self.root), {'id': 'encryption', 'state': 'ok', 'detail': 'luks'})
        # LVM on LUKS: dm-1 (LVM) sits on dm-0
        os.symlink('../dm-1', self.root / 'dev/mapper/vg-root')
        (self.root / 'dev/dm-1').write_text('')
        put(self.root, 'sys/class/block/dm-1/dm/uuid', 'LVM-xyz\n')
        (self.root / 'sys/class/block/dm-1/slaves').mkdir()
        os.symlink('../../dm-0', self.root / 'sys/class/block/dm-1/slaves/dm-0')
        self._mounts('/dev/mapper/vg-root')
        self.assertEqual(sec.check_encryption(self.root)['state'], 'ok')
        # plain partition
        (self.root / 'dev/nvme0n1p2').write_text('')
        (self.root / 'sys/class/block/nvme0n1p2').mkdir(parents=True)
        self._mounts('/dev/nvme0n1p2')
        self.assertEqual(sec.check_encryption(self.root), {'id': 'encryption', 'state': 'bad', 'detail': 'none'})
        # overlay / tmpfs root (live session): not a block device, so unknown
        self._mounts('airootfs')
        self.assertEqual(sec.check_encryption(self.root)['state'], 'unknown')

    def test_secure_boot(self):
        self.assertEqual(sec.check_secure_boot(self.root)['detail'], 'no-uefi')
        efi = self.root / 'sys/firmware/efi/efivars'
        efi.mkdir(parents=True)
        self.assertEqual(sec.check_secure_boot(self.root)['detail'], 'unknown')
        guid = '-8be4df61-93ca-11d2-aa0d-00e098032b8c'
        attrs = b'\x06\x00\x00\x00'
        put(efi, 'SecureBoot' + guid, attrs + b'\x01')
        put(efi, 'SetupMode' + guid, attrs + b'\x00')
        self.assertEqual(sec.check_secure_boot(self.root), {'id': 'secure_boot', 'state': 'ok', 'detail': 'on'})
        put(efi, 'SecureBoot' + guid, attrs + b'\x00')
        self.assertEqual(sec.check_secure_boot(self.root), {'id': 'secure_boot', 'state': 'warn', 'detail': 'off'})
        put(efi, 'SetupMode' + guid, attrs + b'\x01')
        self.assertEqual(sec.check_secure_boot(self.root)['detail'], 'setup')

    def test_screen_lock(self):
        self.assertEqual(sec.check_screen_lock(self.root, self.home)['state'], 'warn')
        conf = put(self.home, '.config/hypr/hypridle.conf', 'listener {\n    timeout = 300\n    on-timeout = brightnessctl -s set 10\n}\n')
        self.assertEqual(sec.check_screen_lock(self.root, self.home)['state'], 'warn')
        conf.write_text('listener {\n    timeout = 300\n    # on-timeout = hyprlock\n}\n')
        self.assertEqual(sec.check_screen_lock(self.root, self.home)['state'], 'warn')
        conf.write_text('listener {\n    timeout = 300\n    on-timeout = loginctl lock-session\n}\n')
        self.assertEqual(sec.check_screen_lock(self.root, self.home), {'id': 'screen_lock', 'state': 'ok', 'detail': 'on'})
        conf.unlink()
        put(self.root, 'etc/hypr/hypridle.conf', 'general {\n    lock_cmd = pidof hyprlock || hyprlock\n}\n')
        self.assertEqual(sec.check_screen_lock(self.root, self.home)['state'], 'ok')

    def test_password(self):
        self.assertEqual(sec.check_password('al', lambda u: 'al P 2026-01-01 0 99999 7 -1\n'), {'id': 'password', 'state': 'ok', 'detail': 'set'})
        self.assertEqual(sec.check_password('al', lambda u: 'al NP 2026-01-01\n')['state'], 'bad')
        self.assertEqual(sec.check_password('al', lambda u: 'al L 2026-01-01\n')['state'], 'unknown')
        self.assertEqual(sec.check_password('al', lambda u: None)['state'], 'unknown')
        self.assertEqual(sec.check_password('al', lambda u: 'bob P x')['state'], 'unknown')

        def boom(user):
            raise subprocess.TimeoutExpired('passwd', 5)
        self.assertEqual(sec.check_password('al', boom)['state'], 'unknown')

    def test_overall_and_run(self):
        self.assertEqual(sec.overall([]), 'unknown')
        self.assertEqual(sec.overall([{'state': 'unknown'}, {'state': 'ok'}]), 'ok')
        self.assertEqual(sec.overall([{'state': 'ok'}, {'state': 'warn'}]), 'warn')
        self.assertEqual(sec.overall([{'state': 'warn'}, {'state': 'bad'}, {'state': 'ok'}]), 'bad')
        result = sec.run_checks(self.root, self.home, self.home / '.cache', NOW, 'al', lambda u: 'al P x')
        self.assertEqual([entry['id'] for entry in result['items']],
                         ['firewall', 'updates', 'backups', 'restore_points', 'encryption', 'secure_boot', 'screen_lock', 'password'])
        self.assertEqual(result['level'], 'warn')
        json.dumps(result)

    def test_script_prints_json(self):
        out = subprocess.run(['python3', '-I', str(ROOT / 'desktop/lib/windoesnot/security_status.py')], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0)
        self.assertIn(json.loads(out.stdout)['level'], ('ok', 'warn', 'bad', 'unknown'))


if __name__ == '__main__':
    unittest.main()
