#!/usr/bin/env python3
"""Maintenance contracts with fake commands/files only; safe on the host."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('system_tools',ROOT/'desktop/lib/windoesnot/system_tools.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Maintenance(unittest.TestCase):
    def test_strict_payloads(self):
        for action in ('maintenance-status','mirrors-rank','cache-clean','keyring-repair','lock-remove','drivers-configure'):
            m.validate(action,{})
            with self.assertRaises(ValueError): m.validate(action,{'command':'id'})
        m.validate('orphans-remove',{'packages':['example','example-bin','lib32-thing']})
        for value in ([],['--help'],['x;id'],['x/y'],['x','x'],[1],{},'example',None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.validate('orphans-remove',{'packages':value})

    def test_orphans_rechecked_without_cascading(self):
        with patch.object(m,'ensure_package_idle'), patch.object(m,'orphan_packages',return_value=['a','b']), patch.object(m,'command') as command:
            m.maintenance_apply('orphans-remove',{'packages':['a']})
            self.assertEqual(command.call_args.args,('/usr/bin/pacman','-R','--noconfirm','--','a'))
            command.reset_mock()
            with self.assertRaises(ValueError): m.maintenance_apply('orphans-remove',{'packages':['changed']})
            command.assert_not_called()

    def test_empty_orphans_are_not_database_errors(self):
        with patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','')):
            self.assertEqual(m.orphan_packages(),[])
        with patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','error: database')):
            with self.assertRaises(RuntimeError): m.orphan_packages()

    def test_active_manager_keeps_lock(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'DB_LOCK',Path(temp)/'db.lck'), patch.object(m,'package_processes',return_value=[{'pid':123,'name':'pacman'}]):
            m.DB_LOCK.touch()
            with self.assertRaises(ValueError): m.remove_stale_lock()
            self.assertTrue(m.DB_LOCK.exists())

    def test_stale_and_missing_lock(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'DB_LOCK',Path(temp)/'db.lck'), patch.object(m,'package_processes',return_value=[]):
            m.DB_LOCK.touch(); m.remove_stale_lock(); self.assertFalse(m.DB_LOCK.exists())
            m.remove_stale_lock()

    def test_symlink_is_not_a_stale_lock(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'DB_LOCK',Path(temp)/'db.lck'), patch.object(m,'package_processes',return_value=[]):
            other=Path(temp)/'important'; other.write_text('keep')
            m.DB_LOCK.symlink_to(other)
            with self.assertRaises(ValueError): m.remove_stale_lock()
            self.assertEqual(other.read_text(),'keep'); self.assertTrue(m.DB_LOCK.is_symlink())

    def test_replaced_lock_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'DB_LOCK',Path(temp)/'db.lck'):
            m.DB_LOCK.write_text('first')
            def scan():
                if scan.calls:
                    replacement=m.DB_LOCK.with_suffix('.new');replacement.write_text('new');replacement.replace(m.DB_LOCK)
                scan.calls+=1
                return []
            scan.calls=0
            with patch.object(m,'package_processes',side_effect=scan),self.assertRaises(ValueError): m.remove_stale_lock()
            self.assertEqual(m.DB_LOCK.read_text(),'new')

    def test_cache_keeps_two_and_reports_difference(self):
        with patch.object(m,'ensure_package_idle'),patch.object(m,'cache_bytes',side_effect=[5000,3000]),patch.object(m,'command') as command:
            result=m.maintenance_apply('cache-clean',{})
            self.assertEqual(command.call_args.args,('/usr/bin/paccache','-rk2'))
            self.assertEqual(result['freedBytes'],2000)

    def test_cache_size_observes_config_and_no_symlinks(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'query',return_value=temp):
            folder=Path(temp);(folder/'pkg').write_bytes(b'1234');(folder/'link').symlink_to(folder/'pkg')
            self.assertEqual(m.cache_bytes(),4)

    def test_mirror_marker_only_after_success(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'MIRRORS_MARKER',Path(temp)/'state/ranked'),patch.object(m,'ensure_package_idle'),patch.object(m,'require_online'),patch.object(m,'update_setup') as record,patch.object(m,'command',side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError): m.maintenance_apply('mirrors-rank',{})
            self.assertFalse(m.MIRRORS_MARKER.exists());record.assert_not_called()
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'MIRRORS_MARKER',Path(temp)/'state/ranked'),patch.object(m,'ensure_package_idle'),patch.object(m,'require_online'),patch.object(m,'update_setup'),patch.object(m,'command'):
            m.maintenance_apply('mirrors-rank',{}); self.assertTrue(m.MIRRORS_MARKER.exists())

    def test_driver_update_failure_prevents_chwd(self):
        with patch.object(m,'ensure_package_idle'),patch.object(m,'available',return_value=True),patch.object(m,'require_online'),patch.object(m,'update_system',side_effect=RuntimeError('ABI conflict')),patch.object(m,'command') as command:
            with self.assertRaises(RuntimeError): m.maintenance_apply('drivers-configure',{})
            command.assert_not_called()

    def test_driver_online_failure_prevents_update(self):
        with patch.object(m,'ensure_package_idle'),patch.object(m,'available',return_value=True),patch.object(m,'require_online',side_effect=RuntimeError('offline')),patch.object(m,'update_system') as update,patch.object(m,'command') as command:
            with self.assertRaises(RuntimeError): m.maintenance_apply('drivers-configure',{})
            update.assert_not_called();command.assert_not_called()

    def test_keyring_repair_keeps_existing_trust_and_reinstalls(self):
        with patch.object(m,'ensure_package_idle'),patch.object(m,'require_online'),patch.object(m,'command') as command:
            m.maintenance_apply('keyring-repair',{})
            self.assertEqual([c.args for c in command.call_args_list],[
                ('/usr/bin/pacman-key','--init'),('/usr/bin/pacman-key','--populate','archlinux','cachyos'),
                ('/usr/bin/pacman','-Syu','--noconfirm','--','archlinux-keyring','cachyos-keyring')])

    def test_partial_installer_record_and_preservation(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(m,'SETUP',Path(temp)/'setup.json'):
            data={'schema_version':1,'cpu_level':'v3','drivers':'pending','driver_reason':'offline','other':'keep'}
            m.SETUP.write_text(json.dumps(data))
            self.assertEqual(m.read_setup()['drivers'],'pending')
            m.update_setup(drivers='configured',driver_profiles=['intel'])
            actual=json.loads(m.SETUP.read_text())
            self.assertEqual(actual['other'],'keep');self.assertNotIn('driver_reason',actual)

if __name__=='__main__':unittest.main()
