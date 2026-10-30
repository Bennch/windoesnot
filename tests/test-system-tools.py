#!/usr/bin/env python3
"""Host-safe security and state tests; no real system commands are executed."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('system_tools', ROOT/'desktop/lib/windoesnot/system_tools.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class SystemTools(unittest.TestCase):
    def test_shell_allowlist_and_calling_account(self):
        m.validate('shell-set', {'shell': 'fish'})
        for value in ['/bin/sh', 'bash;id', '', 'root']:
            with self.assertRaises(ValueError): m.validate('shell-set', {'shell': value})
        with patch.dict(m.os.environ, {'PKEXEC_UID': '0'}):
            with self.assertRaises(ValueError): m.shell_account()
        with patch.object(m, 'shell_account') as account, patch.object(m, 'shell_status', return_value={'available': ['fish']}), patch.object(m, 'command') as command:
            account.return_value.pw_name = 'test-user'
            m.set_shell('fish')
            command.assert_called_once_with('/usr/bin/usermod', '--shell', '/usr/bin/fish', '--', 'test-user')
            with self.assertRaises(ValueError): m.set_shell('zsh')

    def test_offline_and_partially_available_kernel_catalogue(self):
        missing = m.subprocess.CompletedProcess([], 1, '', "error: package was not found")
        found = m.subprocess.CompletedProcess([], 0, 'Name : linux-cachyos\nVersion : 7.2.7\n', '')
        with patch.object(m.subprocess, 'run', return_value=missing) as run:
            self.assertEqual(m.repository_packages(m.KERNELS), {})
            self.assertEqual(run.call_count, len(m.KERNELS))
            self.assertTrue(all(call.args[0][1] == '-Si' for call in run.call_args_list))
        with patch.object(m.subprocess, 'run', side_effect=[found, missing]):
            self.assertEqual(m.repository_packages(m.KERNELS[:2]), {'linux-cachyos': '7.2.7'})

    def test_missing_catalogue_keeps_installed_kernel_status(self):
        with patch.object(m, 'packages', return_value={'linux-cachyos': '7.2.7'}), \
             patch.object(m, 'repository_packages', return_value={}), \
             patch.object(m, 'kernel_state', return_value=('7.2.7', 'linux-cachyos', {'linux-cachyos'})), \
             patch.object(m, 'driver_state', return_value=('qemu', False)), \
             patch.object(m, 'query', return_value='cachyos-v3'), \
             patch.object(m, 'cpu_level', return_value='v3'), \
             patch.object(m, 'read_setup', return_value=None), \
             patch.object(m, 'bootloader', return_value='grub'), \
             patch.object(m, 'scx_status', return_value={'supported': True}):
            status = m.kernel_status()
        self.assertFalse(status['catalogAvailable'])
        self.assertEqual(status['kernels'][0]['installed'], '7.2.7')
        self.assertTrue(status['kernels'][0]['running'])
        self.assertTrue(status['scx']['supported'])

    def test_strict_action_arguments(self):
        for action, payload in [('shell', {}), ('kernel-install', {'kernel': '--help'}),
                ('kernel-remove', {'kernel': 'linux-cachyos;id'}),
                ('kernel-status', {'anything': 1}), ('scx-install', {'packages': ['bash']}),
                ('scx-set', {'scheduler': 'scx_lavd', 'mode': 'Auto', 'onBoot': 1}),
                ('scx-set', {'scheduler': 'scx_lavd', 'mode': '--help', 'onBoot': True}),
                ('kernel-install', []), ('kernel-install', {'kernel': ['linux-cachyos']}),
                ('kernel-install', {'kernel': 'linux-cachyos', 'extra': '--overwrite'})]:
            with self.subTest(action=action, payload=payload), self.assertRaises(ValueError):
                m.validate(action, payload)
        m.validate('scx-set', {'scheduler':'scx_lavd', 'mode':'Auto', 'onBoot':True})
        m.validate('kernel-install', {'kernel':'linux-cachyos'})

    def test_installer_json(self):
        data = {'schema_version':1,'cpu_level':'v3','repositories':['cachyos-v3'],
                'drivers':'pending','driver_profiles':[], 'mirrors_ranked':False}
        self.assertEqual(m.parse_setup(json.dumps(data))['drivers'], 'pending')
        for raw in ['null', '[]', '{}', '{', json.dumps({**data,'driver_profiles':'nvidia'}),
                    json.dumps({**data,'cpu_level':'$(id)'}), json.dumps({**data,'mirrors_ranked':1})]:
            with self.subTest(raw=raw), self.assertRaises(ValueError): m.parse_setup(raw)
        with patch.object(m,'SETUP',Path('/nonexistent/windoesnot/setup.json')):
            self.assertIsNone(m.read_setup())

    def test_running_last_and_unknown_kernel_are_protected(self):
        with patch.object(m,'packages',return_value={'linux-cachyos':'1','linux-cachyos-lts':'2'}):
            for running, bases, target in [('linux-cachyos',{'linux-cachyos','linux-cachyos-lts'},'linux-cachyos'),
                    ('linux-cachyos',{'linux-cachyos'},'linux-cachyos'),
                    ('',{'linux-cachyos','linux-cachyos-lts'},'linux-cachyos-lts'),
                    ('linux',{'linux-cachyos','linux-cachyos-lts'},'linux-cachyos-lts')]:
                with self.subTest(running=running), patch.object(m,'kernel_state',return_value=('1',running,bases)), self.assertRaises(ValueError):
                    m.kernel_packages(target,False)

    def test_removal_keeps_unrelated_packages(self):
        with patch.object(m,'packages',return_value={'linux-cachyos':'1','linux-cachyos-lts':'2',
                'linux-cachyos-lts-headers':'2','nvidia-open-dkms':'1'}), patch.object(m,'kernel_state',return_value=('1','linux-cachyos',{'linux-cachyos','linux-cachyos-lts'})):
            self.assertEqual(m.kernel_packages('linux-cachyos-lts',False),['linux-cachyos-lts','linux-cachyos-lts-headers'])

    def test_headers_and_nvidia_required(self):
        wanted=['linux-cachyos-bore','linux-cachyos-bore-headers','linux-cachyos-bore-nvidia-open']
        with patch.object(m,'packages',return_value={}), patch.object(m,'kernel_state',return_value=('1','linux',{'linux'})), patch.object(m,'driver_state',return_value=('nvidia',True)), patch.object(m,'repository_packages',return_value=dict.fromkeys(wanted,'1')) as repo:
            self.assertEqual(m.kernel_packages('linux-cachyos-bore',True),wanted)
            repo.assert_called_once_with(wanted)
            repo.return_value={wanted[0]:'1',wanted[1]:'1'}
            with self.assertRaises(ValueError): m.kernel_packages('linux-cachyos-bore',True)

    def test_no_partial_update(self):
        with patch.object(m,'command') as command:
            m.update_system(['linux-cachyos'])
            self.assertEqual(command.call_args.args,('/usr/bin/pacman','-Syu','--needed','--noconfirm','--','linux-cachyos'))

    def test_config_preserves_custom_flags_and_validates(self):
        text='# custom\ndefault_sched = "scx_rusty"\ndefault_mode = "Auto"\n[scheds.scx_rusty]\nauto_mode = ["--custom"]\n'
        updated=m.replace_scx_defaults(text,'scx_lavd','Gaming')
        self.assertIn('# custom',updated); self.assertIn('auto_mode = ["--custom"]',updated)
        config=m.tomllib.loads(updated)
        self.assertEqual(config['default_sched'],'scx_lavd')
        self.assertEqual(config['default_mode'],'Gaming')
        with self.assertRaises(ValueError): m.replace_scx_defaults('[invalid','scx_lavd','Auto')

    def test_bootloader_generators(self):
        with patch.object(m,'command') as command:
            for loader, expected in [('grub',('/usr/bin/grub-mkconfig','-o','/boot/grub/grub.cfg')),
                    ('limine',('/usr/bin/limine-update',)), ('systemd-boot',('/usr/bin/sdboot-manage','gen'))]:
                m.refresh_bootloader(loader); self.assertEqual(command.call_args.args,expected)
            with self.assertRaises(ValueError): m.refresh_bootloader('unknown')

    def test_firmware_only_is_not_an_active_nvidia_profile(self):
        with patch.object(m,'available',return_value=False):
            self.assertFalse(m.driver_state({'linux-firmware-nvidia':'1'})[1])
            self.assertTrue(m.driver_state({'linux-cachyos-nvidia-open':'1'})[1])
            self.assertTrue(m.driver_state({'nvidia-open-dkms':'1'})[1])

    def test_kernel_transaction_uses_only_validated_packages(self):
        with patch.object(m,'check_bootloader'), patch.object(m,'bootloader',return_value='grub'), patch.object(m,'kernel_packages',return_value=['linux-cachyos-bore','linux-cachyos-bore-headers']), patch.object(m,'update_system') as update, patch.object(m,'refresh_bootloader') as refresh:
            self.assertTrue(m.apply('kernel-install',{'kernel':'linux-cachyos-bore'})['reboot'])
            update.assert_called_once_with(['linux-cachyos-bore','linux-cachyos-bore-headers'])
            refresh.assert_called_once_with('grub')

    def test_no_bootloader_means_no_transaction(self):
        with patch.object(m,'bootloader',return_value=''), patch.object(m,'command') as command, self.assertRaises(ValueError):
            m.apply('kernel-install',{'kernel':'linux-cachyos'})
        command.assert_not_called()

    def test_refind_retains_custom_versions_and_adds_all_variants(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'REFIND_CONF',Path(temp)/'refind.conf'):
            m.REFIND_CONF.write_text('timeout 5\nextra_kernel_version_strings "custom,linux" # own kernels\n')
            m.refresh_refind_versions()
            text=m.REFIND_CONF.read_text()
            self.assertIn('timeout 5',text)
            self.assertIn('custom',text)
            for kernel in m.KERNELS:self.assertIn(kernel,text)
            self.assertLess(text.index('linux-cachyos-rt-bore'),text.index(',linux"'))
            m.refresh_refind_versions();self.assertEqual(m.REFIND_CONF.read_text(),text)

    def test_current_profiles_override_staged_nvidia_modules(self):
        with patch.object(m,'available',return_value=True), patch.object(m,'query',return_value='│ qemu ┆ 5 │'):
            self.assertFalse(m.driver_state({'linux-cachyos-nvidia-open':'1'})[1])
        with patch.object(m,'available',return_value=True), patch.object(m,'query',return_value='│ nvidia-open-dkms.prime ┆ 5 │'):
            self.assertTrue(m.driver_state({})[1])

    def test_sddm_set_theme_rejects_unknown_theme_or_preset(self):
        for payload in [{'theme': 'windoesnot', 'preset': 'nope'}, {'theme': 'nope', 'preset': 'cinder'},
                        {'theme': 'silentsddm', 'preset': 'fire'}, {'theme': 'windoesnot'}, {}]:
            with self.assertRaises(ValueError): m.validate('sddm-set-theme', payload)
        m.validate('sddm-set-theme', {'theme': 'windoesnot', 'preset': 'fire'})
        m.validate('sddm-set-theme', {'theme': 'silentsddm', 'preset': 'default'})

    def test_sddm_write_conf_sets_theme_and_strips_stale_greeter_env(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m, 'SDDM_CONF', Path(temp)/'windoesnot.conf'):
            m.SDDM_CONF.write_text('[General]\nDisplayServer=x11\nInputMethod=qtvirtualkeyboard\n'
                                    'GreeterEnvironment=stale\n[Theme]\nCurrent=silentsddm\n')
            m.sddm_write_conf('windoesnot', {})
            parser = m._ini_parser(); parser.read(m.SDDM_CONF)
            self.assertEqual(parser.get('Theme', 'Current'), 'windoesnot')
            self.assertEqual(parser.get('X11', 'DisplayCommand'), '/usr/share/sddm/themes/windoesnot/Xsetup')
            self.assertFalse(parser.has_option('General', 'InputMethod'))
            self.assertFalse(parser.has_option('General', 'GreeterEnvironment'))
            m.sddm_write_conf('silentsddm', {'InputMethod': 'qtvirtualkeyboard', 'GreeterEnvironment': 'QML2_IMPORT_PATH=x'})
            parser = m._ini_parser(); parser.read(m.SDDM_CONF)
            self.assertEqual(parser.get('General', 'InputMethod'), 'qtvirtualkeyboard')
            self.assertEqual(parser.get('Theme', 'Current'), 'silentsddm')

    def test_sddm_theme_status_reads_preset_marker_and_falls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            themes = Path(temp)/'themes'; (themes/'windoesnot').mkdir(parents=True)
            conf = Path(temp)/'windoesnot.conf'
            with patch.object(m, 'SDDM_THEMES_DIR', themes), patch.object(m, 'SDDM_CONF', conf):
                self.assertEqual(m.sddm_theme_status(), {'theme': 'windoesnot', 'preset': 'cinder'})
                conf.write_text('[Theme]\nCurrent=windoesnot\n')
                (themes/'windoesnot/theme.conf.user').write_text('; windoesnot-preset: fire\n[General]\n')
                self.assertEqual(m.sddm_theme_status(), {'theme': 'windoesnot', 'preset': 'fire'})
                conf.write_text('[Theme]\nCurrent=not-a-real-theme\n')
                self.assertEqual(m.sddm_theme_status()['theme'], 'windoesnot')

    def test_sddm_wallpaper_source_prefers_primary_monitor(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); hypr = home/'.config/hypr'; hypr.mkdir(parents=True)
            (hypr/'lua').mkdir()
            encoded = m.base64.b64encode(m.json.dumps({'primary_monitor': 'DP-2'}).encode()).decode()
            (hypr/'lua/state.lua').write_text('-- state-json:' + encoded + '\nreturn {}\n')
            (hypr/'hyprpaper.conf').write_text(
                'wallpaper {\n    monitor = HDMI-A-1\n    path = /pics/a.jpg\n    fit_mode = cover\n}\n'
                'wallpaper {\n    monitor = DP-2\n    path = /pics/b.jpg\n    fit_mode = cover\n}\n')
            account = type('Account', (), {'pw_dir': str(home)})()
            self.assertEqual(m.sddm_wallpaper_source(account), Path('/pics/b.jpg'))

    def test_sddm_wallpaper_source_without_state_falls_back_to_any(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); hypr = home/'.config/hypr'; hypr.mkdir(parents=True)
            (hypr/'hyprpaper.conf').write_text('wallpaper {\n    monitor = HDMI-A-1\n    path = /pics/a.jpg\n}\n')
            account = type('Account', (), {'pw_dir': str(home)})()
            self.assertEqual(m.sddm_wallpaper_source(account), Path('/pics/a.jpg'))

    def test_sddm_wallpaper_source_missing_config_returns_none(self):
        with tempfile.TemporaryDirectory() as temp:
            account = type('Account', (), {'pw_dir': temp})()
            self.assertIsNone(m.sddm_wallpaper_source(account))

    def test_sddm_set_theme_windoesnot_writes_marked_preset(self):
        with tempfile.TemporaryDirectory() as temp:
            themes = Path(temp)/'themes'
            (themes/'windoesnot/presets').mkdir(parents=True)
            (themes/'windoesnot/presets/fire.conf').write_text('[General]\nBackground="fire.jpg"\n')
            conf = Path(temp)/'windoesnot.conf'
            with patch.object(m, 'SDDM_THEMES_DIR', themes), patch.object(m, 'SDDM_CONF', conf), \
                 patch.object(m, 'shell_account') as account:
                account.return_value.pw_uid = 1000; account.return_value.pw_gid = 1000
                m.sddm_set_theme({'theme': 'windoesnot', 'preset': 'fire'})
                written = (themes/'windoesnot/theme.conf.user').read_text()
                self.assertTrue(written.startswith('; windoesnot-preset: fire\n'))
                self.assertIn('fire.jpg', written)
                parser = m._ini_parser(); parser.read(conf)
                self.assertEqual(parser.get('Theme', 'Current'), 'windoesnot')

    def test_sddm_set_theme_silentsddm_forces_current_jpg_background_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            themes = Path(temp)/'themes'
            (themes/'silentsddm/configs').mkdir(parents=True)
            (themes/'silentsddm/configs/default.conf').write_text(
                '[LoginScreen]\nbackground = "smoky.jpg"\nblur = 0\n[LockScreen]\nbackground = "smoky.jpg"\n')
            cache = Path(temp)/'cache'; conf = Path(temp)/'windoesnot.conf'
            source = Path(temp)/'wallpaper.jpg'; source.write_bytes(b'fake-jpeg')
            with patch.object(m, 'SDDM_THEMES_DIR', themes), patch.object(m, 'SDDM_CONF', conf), \
                 patch.object(m, 'SDDM_WALLPAPER_DIR', cache), \
                 patch.object(m, 'shell_account') as account, \
                 patch.object(m, 'sddm_wallpaper_source', return_value=source):
                account.return_value.pw_uid = os.getuid(); account.return_value.pw_gid = os.getgid()
                m.sddm_set_theme({'theme': 'silentsddm', 'preset': 'default'})
                written = (themes/'silentsddm/theme.conf.user').read_text()
                self.assertIn('background = "current.jpg"', written)
                self.assertNotIn('smoky.jpg', written)
                self.assertIn('blur = 0', written)  # untouched keys survive the merge
                link = themes/'silentsddm/backgrounds/current.jpg'
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), (cache/'current.jpg').resolve())
                self.assertEqual((cache/'current.jpg').read_bytes(), b'fake-jpeg')
                parser = m._ini_parser(); parser.read(conf)
                self.assertEqual(parser.get('Theme', 'Current'), 'silentsddm')
                self.assertEqual(parser.get('General', 'InputMethod'), 'qtvirtualkeyboard')
                self.assertIn('QML2_IMPORT_PATH', parser.get('General', 'GreeterEnvironment'))
                # Re-running must not choke on the symlink already existing.
                m.sddm_set_theme({'theme': 'silentsddm', 'preset': 'default'})

    def test_policy_has_exact_entry_points(self):
        policy=ET.parse(ROOT/'desktop/share/polkit-1/actions/org.windoesnot.system.policy')
        for action in policy.findall('action'):
            self.assertEqual(action.findtext('defaults/allow_active'),'auth_admin_keep')
            annotations={a.attrib['key']:a.text for a in action.findall('annotate')}
            self.assertEqual(annotations['org.freedesktop.policykit.exec.path'],'/usr/lib/windoesnot/system_tools.py')
            self.assertEqual(action.attrib['id'],'org.windoesnot.system.'+annotations['org.freedesktop.policykit.exec.argv1'])

if __name__ == '__main__': unittest.main()
