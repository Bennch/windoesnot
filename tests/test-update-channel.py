#!/usr/bin/env python3
"""Release channels: layout, unreleased gate, client drop-in, privileged action validation. Offline."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import channel_common as cc


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


uc = load('update_channel', 'desktop/lib/windoesnot/update_channel.py')
tools = load('system_tools', 'desktop/lib/windoesnot/system_tools.py')
STABLE_DROPIN = '[windoesnot]\nSigLevel = Required DatabaseRequired TrustedOnly\nServer = https://download.windoesnot.me/repo/x86_64\n'


class Layout(unittest.TestCase):
    def test_stable_is_unchanged(self):
        self.assertEqual(cc.repo_name('stable'), 'windoesnot')
        self.assertEqual(cc.remote_dir('stable'), 'repo/x86_64')
        self.assertEqual(cc.db_names('stable'), [
            'windoesnot.files.tar.gz', 'windoesnot.files.tar.gz.sig', 'windoesnot.files', 'windoesnot.files.sig',
            'windoesnot.db.tar.gz', 'windoesnot.db.tar.gz.sig', 'windoesnot.db', 'windoesnot.db.sig'])
        self.assertEqual(cc.default_server('stable'), 'https://download.windoesnot.me/repo/x86_64')

    def test_testing_paths(self):
        self.assertEqual(cc.repo_name('testing'), 'windoesnot-testing')
        self.assertEqual(cc.remote_dir('testing'), 'repo/testing/x86_64')
        self.assertIn('windoesnot-testing.db.tar.gz.sig', cc.db_names('testing'))
        self.assertFalse(any(n.startswith('windoesnot.') for n in cc.db_names('testing')))
        with self.assertRaises(ValueError):
            cc.remote_dir('nightly')

    def test_scripts_take_channel(self):
        for name in ('build-repository', 'prepare-release', 'preflight-release', 'publish-repository-r2', 'prepare-repository-client'):
            text = (ROOT / 'tools' / (name + '.py')).read_text()
            self.assertIn('--channel', text, name)
            self.assertRegex(text, r'default=[\'"]stable[\'"]', name)

    def test_stable_drop_in_matches_installer_check(self):
        self.assertIn(STABLE_DROPIN.replace('\n', '\\n'), (ROOT / 'tools/check-image-installer.py').read_text())
        self.assertEqual(uc.dropin_content('stable'), STABLE_DROPIN)


class Gate(unittest.TestCase):
    ENTRY = {'version': '0.1.0-34', 'unreleased': True}

    def test_unreleased_only_to_testing(self):
        self.assertIn('unreleased', cc.changelog_blocker(self.ENTRY, '0.1.0-34', 'stable'))
        self.assertIsNone(cc.changelog_blocker(self.ENTRY, '0.1.0-34', 'testing'))
        self.assertIsNone(cc.changelog_blocker({'version': '0.1.0-34'}, '0.1.0-34', 'stable'))
        self.assertIn('does not match', cc.changelog_blocker({'version': '0.1.0-35'}, '0.1.0-34', 'testing'))

    def test_preflight_versions_uses_channel(self):
        preflight = load('preflight_release', 'tools/preflight-release.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'packaging').mkdir()
            (root / 'packaging/version.json').write_text(json.dumps({'version': '0.1.0', 'release': '34'}))
            (root / 'packaging/changelog.json').write_text(json.dumps({'releases': [self.ENTRY]}))
            with patch.object(preflight, 'ROOT', root):
                for channel, status in (('stable', 'FAIL'), ('testing', 'PASS')):
                    with patch.object(preflight, 'CHANNEL', channel):
                        self.assertEqual(preflight.versions({}, True)[0][0], status, channel)

    def test_prepare_release_refuses_unreleased_on_stable(self):
        text = (ROOT / 'tools/prepare-release.py').read_text()
        self.assertIn('entry.get("unreleased") and args.channel != "testing"', text)


class Client(unittest.TestCase):
    def test_testing_drop_in(self):
        text = uc.dropin_content('testing')
        self.assertEqual(text, '[windoesnot-testing]\nSigLevel = Required DatabaseRequired TrustedOnly\n'
                               'Server = https://download.windoesnot.me/repo/testing/x86_64\n')
        self.assertNotIn('[windoesnot]', text)  # stable repository disabled
        self.assertEqual(text.count('['), 1)

    def test_custom_server_is_kept(self):
        mirror = 'http://10.0.2.2:8000/x86_64'
        self.assertEqual(uc.dropin_content('testing', mirror).splitlines()[2], 'Server = http://10.0.2.2:8000/testing/x86_64')
        self.assertEqual(uc.dropin_content('stable', 'http://10.0.2.2:8000/testing/x86_64').splitlines()[2], 'Server = ' + mirror)

    def test_parse_and_read(self):
        self.assertEqual(uc.parse_channel('testing\n'), 'testing')
        for junk in ('', 'nightly', 'testing; rm', None, 5):
            self.assertEqual(uc.parse_channel(junk), 'stable')
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(uc.read_channel(Path(temp) / 'missing'), 'stable')

    def test_apply_is_idempotent_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as temp:
            channel, dropin = Path(temp) / 'etc/channel', Path(temp) / 'windoesnot.conf'
            dropin.write_text(STABLE_DROPIN)
            first = uc.apply_channel('testing', channel, dropin)
            self.assertTrue(first['changed'] and first['repository'])
            self.assertEqual(dropin.read_text(), uc.dropin_content('testing'))
            self.assertEqual(uc.read_channel(channel), 'testing')
            self.assertFalse(uc.apply_channel('testing', channel, dropin)['changed'])
            uc.apply_channel('stable', channel, dropin)
            self.assertEqual(dropin.read_text(), STABLE_DROPIN)  # byte-identical to the original
            self.assertEqual(uc.read_channel(channel), 'stable')

    def test_unconfigured_system_gets_no_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            dropin = Path(temp) / 'windoesnot.conf'
            result = uc.apply_channel('testing', Path(temp) / 'channel', dropin)
            self.assertFalse(result['repository'])
            self.assertFalse(dropin.exists())


class Privileged(unittest.TestCase):
    def test_validation_accepts_only_two_values(self):
        for value in ('stable', 'testing'):
            tools.validate('update-channel-set', {'channel': value})
        for payload in ({'channel': 'nightly'}, {'channel': ''}, {'channel': 'Testing'}, {'channel': 1}, {'channel': None},
                        {'channel': '../x'}, {}, {'channel': 'stable', 'x': 1}, {'enabled': True}):
            with self.assertRaises(ValueError, msg=payload):
                tools.validate('update-channel-set', payload)

    def test_apply_writes_fixed_paths_only(self):
        with tempfile.TemporaryDirectory() as temp:
            channel, dropin = Path(temp) / 'channel', Path(temp) / 'windoesnot.conf'
            dropin.write_text(STABLE_DROPIN)
            with patch.object(tools, 'CHANNEL_FILE', channel), patch.object(tools, 'PACMAN_DROPIN', dropin):
                tools.validate('update-channel-set', {'channel': 'testing'})
                self.assertFalse(tools.apply('update-channel-set', {'channel': 'testing'})['reboot'])
            self.assertEqual(channel.read_text(), 'testing\n')
        self.assertEqual(tools.CHANNEL_FILE, Path('/etc/windoesnot/channel'))
        self.assertEqual(tools.PACMAN_DROPIN, Path('/etc/pacman.d/windoesnot.conf'))

    def test_polkit_policy_and_ui_keys(self):
        policy = (ROOT / 'desktop/share/polkit-1/actions/org.windoesnot.system.policy').read_text()
        self.assertIn('org.windoesnot.system.update-channel-set', policy)
        self.assertIn('<annotate key="org.freedesktop.policykit.exec.argv1">update-channel-set</annotate>', policy)
        found = {}
        for lang in ('en', 'de'):
            text = (ROOT / f'desktop/config/quickshell/default/i18n/{lang}.js').read_text()
            found[lang] = {k for k in ('updates.channelTitle', 'updates.channelHint', 'updates.channelSaveFailed') if f'"{k}"' in text}
        self.assertEqual(found['en'], found['de'])
        self.assertEqual(len(found['en']), 3)
        self.assertIn('update_channel.py', (ROOT / 'packaging/PKGBUILD.in').read_text())


if __name__ == '__main__':
    unittest.main()
