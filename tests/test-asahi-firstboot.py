#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
FIRSTBOOT = ROOT / 'installer/asahi/firstboot'


class FirstBootTests(unittest.TestCase):
    def test_installed_system_only_and_desktop_after_setup(self):
        config = yaml.safe_load((FIRSTBOOT / 'calamares/settings.conf').read_text())
        self.assertTrue(config['dont-chroot'])
        self.assertTrue(config['oem-setup'])
        self.assertEqual(config['sequence'][1]['exec'][-1], 'windoesnotmacfinish')
        sequence = str(config['sequence'])
        for forbidden in ('partition', 'unpackfs', 'bootloader', 'mount', 'packages'):
            self.assertNotIn(forbidden, sequence)
        service = (FIRSTBOOT / 'windoesnot-firstboot.service').read_text()
        self.assertIn('Before=display-manager.service sddm.service', service)
        self.assertIn('ConditionPathExists=/var/lib/windoesnot/firstboot-pending', service)
        subprocess.run(['bash', '-n', str(FIRSTBOOT / 'firstboot')], check=True)

    def exercise(self, fail=False, username='alice', language='en_US.UTF-8'):
        storage = {'username': username, 'locale': language}
        fake = SimpleNamespace(globalstorage=SimpleNamespace(value=lambda key: storage.get(key)))
        spec = importlib.util.spec_from_file_location('finish', FIRSTBOOT / 'calamares/modules/windoesnotmacfinish/main.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'libcalamares': fake}):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pending = root / 'var/lib/windoesnot/firstboot-pending'
            pending.parent.mkdir(parents=True)
            pending.write_text('pending')
            (root / 'home/alice').mkdir(parents=True)
            def account(name):
                return SimpleNamespace(pw_uid=1001 if name == 'alice' else 974,
                                       pw_gid=1001 if name == 'alice' else 974, pw_dir='/home/alice')
            with patch.object(module, 'Path', side_effect=lambda p: root / str(p).lstrip('/')), \
                 patch.object(module.pwd, 'getpwnam', side_effect=account), \
                 patch('os.chown'), patch.object(module.subprocess, 'run') as run:
                if fail:
                    run.side_effect = subprocess.CalledProcessError(1, 'initialize')
                result = module.run()
                if fail or username != 'alice':
                    self.assertIsNotNone(result)
                    self.assertTrue(pending.exists())
                    self.assertFalse(pending.with_name('firstboot-complete').exists())
                    if username != 'alice':
                        run.assert_not_called()
                else:
                    self.assertIsNone(result)
                    self.assertFalse(pending.exists())
                    self.assertTrue(pending.with_name('firstboot-complete').is_file())
                    self.assertIn('--adopt-system', run.call_args_list[0].args[0])
                    self.assertIn('Session=windoesnot.desktop', (root / 'var/lib/sddm/state.conf').read_text())
                return result

    def test_success_initializes_real_user_before_completing(self):
        self.exercise()

    def test_failure_keeps_setup_pending(self):
        result = self.exercise(fail=True, language='de_DE.UTF-8')
        self.assertIn('Einrichtung', result[0])

    def test_invalid_account_never_runs_commands(self):
        self.exercise(username='root; bad-command')


if __name__ == '__main__':
    unittest.main()
