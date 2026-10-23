#!/usr/bin/env python3
"""Snapshot network transactions, bootloader validation and backup initialization."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'iso'))
sys.path.insert(0,str(ROOT/'iso/software'))
import installation
import repository

for loader in installation.BOOT_PACKAGES:
    installation.validate_choice(loader,'efi','offline')
for loader in ('grub','limine'):
    installation.validate_choice(loader,'bios','online')
for choice in [('refind','bios','offline'),('systemd-boot','bios','online'),('none','efi','offline'),('refind-ai','efi','online'),('grub','efi','typo')]:
    try: installation.validate_choice(*choice)
    except ValueError: pass
    else: raise AssertionError('Unsupported boot choice accepted')

with tempfile.TemporaryDirectory(prefix='wdn-install-modes-') as temporary:
    root=Path(temporary);base=root/'base';bundle=base/'offline-apps';(bundle/'repository').mkdir(parents=True)
    package=b'package fixture';name='optional-1-1-x86_64.pkg.tar.zst'
    (bundle/'repository'/name).write_bytes(package)
    (bundle/'repository/windoesnot-apps.db').write_bytes(b'db fixture')
    (bundle/'manifest.json').write_text(json.dumps({'schema_version':1,'archives':{name:{'package':'optional','version':'1-1','sha256':hashlib.sha256(package).hexdigest(),'url':'https://packages.example.invalid/'+name}}}))
    (bundle/'pacman.conf').write_text('[windoesnot-apps]\n')
    calls=[];downloads=[]
    def run(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1 if command[:2]==['pacman','-Q'] else 0,stdout='')
    def download(url,dest):
        downloads.append(url);dest.write_bytes(b'signature fixture' if url.endswith('.sig') else package)
    with patch.object(repository.subprocess,'run',side_effect=run),patch.object(repository.subprocess,'check_output',return_value='optional 1-1\n'),patch.object(repository,'download',side_effect=download):
        repository.install_packages(['optional'],'online',base)
    assert len(downloads)==2 and downloads[0].startswith('https://')
    install=next(c for c in calls if '-S' in c)
    assert 'windoesnot-online-' in install[install.index('--config')+1]
    assert not any('-Syu' in c for c in calls)
    downloads.clear();calls.clear()
    with patch.object(repository.subprocess,'run',side_effect=run),patch.object(repository.subprocess,'check_output',return_value='optional 1-1\n'),patch.object(repository,'download',side_effect=RuntimeError('network offline')):
        try: repository.install_packages(['optional'],'online',base)
        except RuntimeError: pass
        else: raise AssertionError('Online silently fell back to ISO cache')
    assert not any('-S' in c for c in calls)
    calls.clear()
    with patch.object(repository.subprocess,'run',side_effect=run),patch.object(repository.subprocess,'check_output',return_value='optional 1-1\n'),patch.object(repository,'download',side_effect=AssertionError('Offline accessed network')):
        repository.install_packages(['optional'],'offline',base)
    assert any('-S' in c for c in calls)
    def installed(name):return '0-1' if name=='base-library' else None
    calls.clear()
    with patch.object(repository,'package_version',side_effect=installed),patch.object(repository.subprocess,'run',side_effect=run),patch.object(repository.subprocess,'check_output',return_value='base-library 2-1\noptional 1-1\n'):
        try: repository.install_packages(['optional'],'online',base)
        except RuntimeError as error: assert 'tested ISO base' in str(error)
        else: raise AssertionError('Base replacement allowed')
    assert not any('-S' in c for c in calls)
    (bundle/'repository'/name).write_bytes(b'corrupt')
    calls.clear()
    with patch.object(repository.subprocess,'run',side_effect=run):
        try: repository.install_packages(['optional'],'offline',base)
        except RuntimeError: pass
        else: raise AssertionError('Corrupt offline archive accepted')
    assert not any('-Sy' in c for c in calls)
    # Snapper belongs only to Btrfs; initial snapshot must not contain live marker.
    marker=root/'etc/windoesnot-image-build';marker.parent.mkdir();marker.touch()
    calls.clear()
    def finish_run(command,**kwargs):
        if command[:5]==['snapper','--no-dbus','-c','root','create']:assert not marker.exists()
        calls.append(command);return SimpleNamespace(returncode=0)
    with patch.object(installation.subprocess,'check_output',return_value='btrfs\n'),patch.object(installation.subprocess,'run',side_effect=finish_run):
        installation.finish('grub','efi','offline',root)
    assert any('create-config' in c for c in calls)
    assert any('snapper-timeline.timer' in c for c in calls)
    calls.clear()
    with patch.object(installation.subprocess,'check_output',return_value='ext4\n'),patch.object(installation.subprocess,'run',side_effect=finish_run):
        installation.finish('grub','efi','offline',root)
    assert not calls
    (root/'boot').mkdir()
    (root/'etc/default').mkdir()
    (root/'boot/limine.conf').write_text('timeout: 5\ndefault_entry: 2\ncomment: machine-id=test-id\n/+CachyOS\n')
    (root/'etc/default/limine').write_text('ESP_PATH="/boot"\n')
    def limine_run(command,**kwargs):
        assert command==['limine-update']
        config=(root/'boot/limine.conf').read_text()
        assert config.count('/+WinDoesNot')==1 and '/+CachyOS' not in config
        assert '/+WinDoesNot\ncomment: machine-id=test-id' in config
        assert 'TARGET_OS_NAME="WinDoesNot"' in (root/'etc/default/limine').read_text()
        return SimpleNamespace(returncode=0)
    with patch.object(installation.subprocess,'check_output',return_value='ext4\n'),patch.object(installation.subprocess,'run',side_effect=limine_run):
        installation.finish('limine','efi','offline',root)

print('PASS: bootloader/firmware validation, HTTPS-only snapshot transactions, offline isolation, network failures, base drift rejection, Btrfs-only backups')
