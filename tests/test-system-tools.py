#!/usr/bin/env python3
"""Host-safe security and state tests; no real system commands are executed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('system_tools', ROOT/'desktop/lib/windoesnot/system_tools.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class SystemTools(unittest.TestCase):
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

    def test_policy_has_exact_entry_points(self):
        policy=ET.parse(ROOT/'desktop/share/polkit-1/actions/org.windoesnot.system.policy')
        for action in policy.findall('action'):
            self.assertEqual(action.findtext('defaults/allow_active'),'auth_admin_keep')
            annotations={a.attrib['key']:a.text for a in action.findall('annotate')}
            self.assertEqual(annotations['org.freedesktop.policykit.exec.path'],'/usr/lib/windoesnot/system_tools.py')
            self.assertEqual(action.attrib['id'],'org.windoesnot.system.'+annotations['org.freedesktop.policykit.exec.argv1'])

if __name__ == '__main__': unittest.main()
