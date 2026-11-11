#!/usr/bin/env python3
"""Host-safe snapshot integration tests: only temp files and mocked system commands."""
import configparser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'iso'),str(ROOT/'iso/software')]
import installation
spec=importlib.util.spec_from_file_location('snapshots',ROOT/'desktop/lib/windoesnot/snapshots.py')
backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)

class Snapshots(unittest.TestCase):
    def test_restore_id_validation(self):
        backend.validate('restore', {'id': '9'})
        for value in ['0', '-1', '../9', '9;reboot', 9]:
            with self.assertRaises(ValueError): backend.validate('restore', {'id': value})

    def test_full_offline_union_and_filesystem_matrix(self):
        union=set()
        for loader in installation.BOOT_PACKAGES:
            for fs in ('btrfs','ext4','xfs'):
                selected=installation.selected_packages(loader,fs)
                union.update(selected)
                self.assertEqual({'snapper','snap-pac'} <= set(selected),fs=='btrfs')
                if fs!='btrfs':self.assertEqual(selected,installation.BOOT_PACKAGES[loader])
        self.assertEqual(union,set(installation.BOOT_EXTRA_PACKAGES))
        self.assertNotIn('grub-btrfs-support',installation.BOOT_EXTRA_PACKAGES)
        self.assertIn('grub-btrfs',installation.BOOT_EXTRA_PACKAGES)
        self.assertIn('inotify-tools',installation.selected_packages('grub','btrfs'))
        # The existing offline resolver must consume this same exported union.
        source=(ROOT/'iso/software/prepare.py').read_text()
        self.assertIn('from installation import BOOT_EXTRA_PACKAGES',source)
        self.assertIn('packages = set(BOOT_EXTRA_PACKAGES)',source)

    def test_cleanup_keeps_timeline_and_bounds_transaction_points(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'etc/snapper/configs').mkdir(parents=True)
            (root/'etc/snapper/configs/root').touch()
            (root/'etc/snap-pac.ini').write_text('[root]\nuserdata = ["custom=keep"]\n[home]\nsnapshot = False\n')
            with patch.object(installation.subprocess,'run') as run:
                installation.configure_snapshots('systemd-boot',root)
            arguments=next(c.args[0] for c in run.call_args_list if 'set-config' in c.args[0])
            for value in ['NUMBER_CLEANUP=yes','NUMBER_LIMIT=20','NUMBER_LIMIT_IMPORTANT=5',
                          'EMPTY_PRE_POST_CLEANUP=yes','TIMELINE_LIMIT_DAILY=5','TIMELINE_LIMIT_HOURLY=0']:
                self.assertIn(value,arguments)
            self.assertIn(['systemctl','enable','snapper-timeline.timer','snapper-cleanup.timer'],[c.args[0] for c in run.call_args_list])
            config=configparser.ConfigParser();config.read(root/'etc/snap-pac.ini')
            self.assertFalse(config.getboolean('home','snapshot'))
            self.assertTrue(config.getboolean('root','snapshot'))
            self.assertIn('custom=keep',config['root']['userdata'])
            self.assertIn('windoesnot.package-change=yes',config['root']['userdata'])
            self.assertIn('linux-cachyos',config['root']['important_packages'])
            self.assertFalse(any('mkinitcpio' in c.args[0] for c in run.call_args_list))

    def test_systemd_hook_preserves_existing_hooks_even_when_sourced_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'etc').mkdir()
            config=root/'etc/mkinitcpio.conf';config.write_text('HOOKS=(base systemd plymouth filesystems windoesnot-boot-errors grub-btrfs-overlayfs)\n')
            installation.configure_grub_overlay(root);first=config.read_text()
            installation.configure_grub_overlay(root);self.assertEqual(config.read_text(),first)
            self.assertEqual(first.count('source /etc/mkinitcpio.conf.d/20-windoesnot-snapshots.conf'),1)
            dropin=root/'etc/mkinitcpio.conf.d/20-windoesnot-snapshots.conf'
            output=subprocess.check_output(['bash','-c','HOOKS=(base systemd plymouth filesystems windoesnot-boot-errors grub-btrfs-overlayfs); source "$1"; source "$1"; printf "%s\\n" "${HOOKS[@]}"','test',str(dropin)],text=True).splitlines()
            self.assertEqual(output,['base','systemd','plymouth','filesystems','windoesnot-boot-errors','windoesnot-snapshot-overlay'])
            for file in ['usr/lib/initcpio/install/windoesnot-snapshot-overlay','usr/lib/windoesnot/snapshot-overlay']:
                subprocess.run(['bash','-n',str(root/file)],check=True)
            script=(root/'usr/lib/windoesnot/snapshot-overlay').read_text()
            start=script.index('if [[ -f /sysroot/etc/fstab ]]')
            end=script.index("printf 'overlay",start)
            fstab=root/'etc/fstab';original='UUID=root / btrfs defaults,subvol=/@ 0 0\nUUID=home /home btrfs subvol=/@home 0 0\n'
            fstab.write_text(original)
            scratch=root/'scratch';scratch.mkdir()
            fragment=script[start:end].replace('/sysroot/etc/fstab',str(fstab)).replace('/run/windoesnot-snapshot/fstab',str(scratch/'fstab'))
            subprocess.run(['bash','-eu','-c',fragment],check=True)
            self.assertIn('# WinDoesNot snapshot preview: UUID=root',fstab.read_text())
            self.assertIn('UUID=home /home btrfs subvol=/@home 0 0',fstab.read_text())
            unit=(root/'usr/lib/systemd/system/windoesnot-snapshot-overlay.service').read_text()
            self.assertIn('After=initrd-fs.target',unit);self.assertIn('Before=initrd.target',unit)
            self.assertIn('/.snapshots/',(root/'usr/lib/windoesnot/snapshot-overlay').read_text())

    def test_limine_target_name_service_and_systemd_hook(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'etc/snapper/configs').mkdir(parents=True)
            (root/'etc/snapper/configs/root').touch()
            (root/'etc/mkinitcpio.conf').write_text('HOOKS=(base systemd filesystems)\n')
            (root/'etc/limine-snapper-sync.conf').write_text('TARGET_OS_NAME="CachyOS"\nMAX_SNAPSHOT_ENTRIES=5\n')
            with patch.object(installation.subprocess,'run') as run:
                installation.configure_snapshots('limine',root)
            text=(root/'etc/limine-snapper-sync.conf').read_text()
            self.assertIn('TARGET_OS_NAME=WinDoesNot',text);self.assertIn('MAX_SNAPSHOT_ENTRIES=3',text)
            self.assertIn('sd-btrfs-overlayfs',(root/'etc/mkinitcpio.conf.d/20-windoesnot-snapshots.conf').read_text())
            commands=[c.args[0] for c in run.call_args_list]
            self.assertIn(['systemctl','enable','limine-snapper-sync.service'],commands)
            self.assertIn(['mkinitcpio','-P'],commands)

    def test_refind_manual_stanzas_and_immutable_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'boot/EFI/refind').mkdir(parents=True);(root/'etc').mkdir()
            (root/'boot/EFI/refind/refind.conf').write_text('timeout 5\n')
            (root/'boot/refind_linux.conf').write_text('"Standard" "root=UUID=test rw rootflags=subvol=/@ initrd=old.img quiet"\n')
            (root/'etc/refind-btrfs.conf').write_text('[snapshot-manipulation]\nselection_count = 5\nmodify_read_only_flag = true\n')
            for name in ['linux-cachyos','linux-cachyos-lts']:
                (root/('boot/vmlinuz-'+name)).touch();(root/('boot/initramfs-'+name+'.img')).touch()
            installation.configure_refind_snapshots(root);installation.configure_refind_snapshots(root)
            self.assertEqual((root/'boot/EFI/refind/refind.conf').read_text().count('include windoesnot-linux.conf'),1)
            sources=(root/'boot/EFI/refind/windoesnot-linux.conf').read_text()
            self.assertIn('loader /vmlinuz-linux-cachyos-lts',sources)
            self.assertIn('rootflags=subvol=/@',sources);self.assertNotIn('old.img',sources)
            config=(root/'etc/refind-btrfs.conf').read_text()
            self.assertIn('selection_count = 3',config);self.assertIn('modify_read_only_flag = false',config)

    def test_post_label_uses_linked_pre_and_userdata(self):
        rows=[{'number':7,'type':'pre','description':'pacman -S tree','cleanup':'number'},
              {'number':8,'type':'post','pre-number':7,'description':'tree','cleanup':'number'},
              {'number':9,'type':'post','pre-number':99,'description':'tree','userdata':{'windoesnot.package-change':'yes'}},
              {'number':10,'type':'single','description':'unrelated','cleanup':'number'}]
        result={r['id']:r for r in backend.parse_snapshots(json.dumps({'root':rows}))}
        self.assertTrue(result['7']['packageChange']);self.assertTrue(result['8']['packageChange'])
        self.assertTrue(result['9']['packageChange']);self.assertFalse(result['10']['packageChange'])
        self.assertEqual(result['8']['preId'],'7')

    def test_invalid_or_older_installer_records_are_not_boot_claims(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(backend,'INSTALLATION',Path(temp)/'installation.json'):
            self.assertFalse(backend.boot_status()['configured'])
            for data in [None,[],{}, {'schema_version':1,'filesystem':'ext4','bootloader':'grub'}]:
                backend.INSTALLATION.write_text(json.dumps(data));self.assertFalse(backend.boot_status()['configured'])
            backend.INSTALLATION.write_text(json.dumps({'schema_version':1,'filesystem':'btrfs','bootloader':'systemd-boot'}))
            self.assertEqual(backend.boot_status(),{'loader':'systemd-boot','configured':False})

    def test_configured_hook_can_be_explicitly_disabled(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(backend,'SNAP_PAC',Path(temp)/'snap-pac.ini'),patch.object(backend,'PRE_HOOK',Path(temp)/'pre.hook'):
            self.assertFalse(backend.package_snapshots_enabled())
            backend.PRE_HOOK.touch();self.assertTrue(backend.package_snapshots_enabled())
            backend.SNAP_PAC.write_text('[root]\nsnapshot = False\n');self.assertFalse(backend.package_snapshots_enabled())
            backend.SNAP_PAC.write_text('[root]\nsnapshot = True\n');self.assertTrue(backend.package_snapshots_enabled())
            backend.SNAP_PAC.write_text('malformed');self.assertFalse(backend.package_snapshots_enabled())

    def test_preview_detection_and_status_guard(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(backend,'SNAPSHOT_BOOT',Path(temp)/'preview'):
            for raw,expected in [('btrfs /dev/vda2[/@]',''),('overlay overlay','overlay'),
                    ('btrfs /dev/vda2[/@/.snapshots/9/snapshot]','snapshot'),
                    ('btrfs /dev/vda2[/@root/.refind-btrfs/rwsnap_test]','snapshot')]:
                with patch.object(backend.subprocess,'run',return_value=SimpleNamespace(stdout=raw)):
                    self.assertEqual(backend.snapshot_boot_mode(),expected)
            backend.SNAPSHOT_BOOT.touch()
            self.assertEqual(backend.snapshot_boot_mode(),'overlay')
            state=backend.status();self.assertFalse(state['ready']);self.assertTrue(state['snapshotBoot'])

if __name__=='__main__':unittest.main()
