#!/usr/bin/env python3
"""Check actual installed installer files, not only their staged source tree."""
import argparse
import json
import hashlib
from pathlib import Path
import yaml

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path('/'))
args=parser.parse_args()
root=args.root
base=root/'usr/share/windoesnot'
assert (root/'etc/windoesnot-image-build').is_file(),'Not a prepared live image'
for path in ['usr/bin/windoesnot-bluetooth','usr/bin/windoesnot-network','usr/bin/windoesnot-device-manager','usr/bin/windoesnot-drivers',
             'usr/share/applications/me.windoesnot.DeviceManager.desktop',
             'usr/share/polkit-1/actions/me.windoesnot.DeviceManager.policy']:
    assert (root/path).is_file(),f'Missing Device Manager package file: {path}'
assert (root/'usr/lib/windoesnot/boot_language.py').is_file(),'Missing boot language runtime'
boot_language=root/'usr/lib/windoesnot/boot-language'
boot_manifest=json.loads((boot_language/'manifest.json').read_text())
assert boot_manifest['runtime_sha256']==hashlib.sha256((root/'usr/lib/windoesnot/boot_language.py').read_bytes()).hexdigest(),'Stale boot language runtime'
assert boot_manifest['patcher_sha256']==hashlib.sha256((base/'tools/patch-boot-language.py').read_bytes()).hexdigest(),'Stale boot language source patch'
for name,checksum in boot_manifest['catalogs'].items():
    assert checksum==hashlib.sha256((base/f'iso/boot-language/{name}-de.json').read_bytes()).hexdigest(),'Stale boot language catalog'
for name,data in boot_manifest['loaders'].items():
    for filename,checksum in data['sha256'].items():
        assert hashlib.sha256((boot_language/name/filename).read_bytes()).hexdigest()==checksum,'Boot language artifact mismatch'
assert (root/'usr/lib/os-probes/55windoesnot-btrfs').read_bytes()==(base/'iso/os-prober-btrfs').read_bytes(),'Missing Btrfs os-prober extension'
assert (root/'usr/lib/os-probes/55windoesnot-btrfs').stat().st_mode & 0o111
for name in ['windoesnotprepare','windoesnotsystem','windoesnotapps_install','windoesnotfinish','windoesnotbootreuse']:
    for filename in ['main.py','module.desc']:
        source=base/'iso/modules'/name/filename
        installed=root/'usr/lib/calamares/modules'/name/filename
        assert source.read_bytes()==installed.read_bytes(),f'Stale installed installer job: {name}/{filename}'
for name in ['windoesnotapps','windoesnotboot']:
    assert (root/'usr/lib/calamares/modules'/name/f'libcalamares_viewmodule_{name}.so').is_file(),name
for mode,directory in [('offline',root/'etc/windoesnot-calamares'),('online',root/'etc/windoesnot-calamares/online')]:
    settings=yaml.safe_load((directory/'settings.conf').read_text())
    assert 'windoesnotboot' in settings['sequence'][0]['show']
    execution=next(step['exec'] for step in settings['sequence'] if 'exec' in step)
    assert execution.index('windoesnotbootreuse@preflight') < execution.index('partition')
    assert execution.index('windoesnotbootreuse@guard') < execution.index('unpackfs')
    assert execution.index('windoesnotbootreuse@finish') < execution.index('umount')
    assert yaml.safe_load((directory/'modules/bootloader.conf').read_text())['efiBootLoaderVar']=='windoesnotBootInstall'
    for name in ['windoesnotprepare','windoesnotsystem','windoesnotapps_install','windoesnotfinish','windoesnotapps']:
        assert yaml.safe_load((directory/'modules'/(name+'.conf')).read_text())['mode']==mode
for name in ['windoesnot-installer','calamares-online.sh']:
    assert (root/'usr/local/bin'/name).read_bytes()==(base/'iso/windoesnot-installer').read_bytes(),name
manifest=json.loads((base/'offline-apps/manifest.json').read_text())
available={line.split()[0] for line in manifest['base_packages']}|{data['package'] for data in manifest['archives'].values()}
assert {'grub','refind','limine','limine-mkinitcpio-hook','systemd-boot-manager','snapper'}<=available
assert all(data.get('url','').startswith('https://') for data in manifest['archives'].values())
# chwd resolves every graphics profile target in the snapshot repository.
assert manifest.get('chwd_packages') and set(manifest['chwd_packages'])<=available|set(manifest.get('database_only',[])),'Driver packages missing from snapshot'
assert {'mesa','vulkan-intel','vulkan-radeon','lib32-mesa','nvidia-utils'}<=set(manifest['chwd_packages'])
print('PASS: installed Python jobs equal canonical sources, both native views/configurations/launchers present, bootloader and backup packages available')
