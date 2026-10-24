#!/usr/bin/env python3
"""Check actual installed installer files, not only their staged source tree."""
import argparse
import json
from pathlib import Path
import yaml

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path('/'))
args=parser.parse_args()
root=args.root
base=root/'usr/share/windoesnot'
assert (root/'etc/windoesnot-image-build').is_file(),'Not a prepared live image'
for name in ['windoesnotprepare','windoesnotsystem','windoesnotapps_install','windoesnotfinish']:
    for filename in ['main.py','module.desc']:
        source=base/'iso/modules'/name/filename
        installed=root/'usr/lib/calamares/modules'/name/filename
        assert source.read_bytes()==installed.read_bytes(),f'Stale installed installer job: {name}/{filename}'
for name in ['windoesnotapps','windoesnotboot']:
    assert (root/'usr/lib/calamares/modules'/name/f'libcalamares_viewmodule_{name}.so').is_file(),name
for mode,directory in [('offline',root/'etc/windoesnot-calamares'),('online',root/'etc/windoesnot-calamares/online')]:
    settings=yaml.safe_load((directory/'settings.conf').read_text())
    assert 'windoesnotboot' in settings['sequence'][0]['show']
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
