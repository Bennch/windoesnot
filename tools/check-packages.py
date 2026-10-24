#!/usr/bin/env python3
"""Validate package contents, public readability and ABI version requirements."""
import argparse
from pathlib import Path
import re
import subprocess
import tarfile

def abi_range(metadata,name):
    """Require name>=V-R and name<V-(R+1): CPU-level .N rebuilds pass, real rebuilds do not."""
    depends=[line[len('depend = '):] for line in metadata.splitlines() if line.startswith('depend = ')]
    lower=[d for d in depends if d.startswith(name+'>=')]
    upper=[d for d in depends if d.startswith(name+'<') and not d.startswith(name+'<=')]
    assert len(lower)==1 and len(upper)==1 and not any(d==name or d.startswith(name+'=') for d in depends),(name,depends)
    match=re.fullmatch(re.escape(name)+r'>=(.+)-(\d+)',lower[0])
    assert match,lower[0]
    assert upper[0]==f'{name}<{match[1]}-{int(match[2])+1}',(lower[0],upper[0])

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory',type=Path)
parser.add_argument('--store',action='store_true',help='Validate a directory holding only the separately versioned store package')
args=parser.parse_args()
core={'windoesnot-desktop','windoesnot-tools','windoesnot-plugins','windoesnot-components'}
expected={'windoesnot-store'} if args.store else core
found={}
for package in sorted(args.directory.glob('*.pkg.tar.zst')):
    name,version=subprocess.check_output(['pacman','-Qp',str(package)],text=True).strip().split()
    assert name in expected and name not in found, name
    found[name]=version
    metadata=''
    flags=''
    process=subprocess.Popen(['zstd','-dc',str(package)],stdout=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
        for info in archive:
            path=Path(info.name)
            assert not path.is_absolute() and '..' not in path.parts,info.name
            assert info.uid==0 and info.gid==0,(info.name,info.uid,info.gid)
            if info.isfile():
                assert info.mode & 0o444==0o444,(info.name,oct(info.mode))
                assert not info.mode & 0o022,(info.name,oct(info.mode))
            assert not info.mode & 0o6000,(info.name,oct(info.mode))
            assert not any(p in ('home','root','.ssh','.aws','.codex','import-manifest.json') for p in path.parts),info.name
            if path.as_posix().startswith('usr/share/windoesnot/desktop/config/'):
                assert path.name not in {'settings.txt','state.lua','host.lua','geometry.lua','calendar_notes.json','icons.json'},info.name
            if info.name=='.PKGINFO': metadata=archive.extractfile(info).read().decode()
            if info.name.endswith(('/plugins-flags.txt','/components-flags.txt')): flags=archive.extractfile(info).read().decode()
    process.stdout.close()
    assert process.wait()==0
    assert metadata
    if name=='windoesnot-plugins':
        abi_range(metadata,'hyprland'); abi_range(metadata,'libstdc++')
    if name=='windoesnot-components':
        abi_range(metadata,'qt6-base'); abi_range(metadata,'qtermwidget')
    if name in ('windoesnot-plugins','windoesnot-components'):
        assert '-march=x86-64' in flags and '-mtune=generic' in flags and '-march=native' not in flags
    if name=='windoesnot-store':
        for dependency in ('gtk4','libadwaita','polkit','pacman'):
            assert f'depend = {dependency}\n' in metadata,dependency
assert set(found)==expected and len(set(found.values()))==1
if args.store:
    print('PASS: store package, root ownership, readable code, no setuid, no private state, desktop runtime dependencies')
else:
    print('PASS: four matching packages, root ownership, readable code, no private state, native ABI version ranges, generic CPU flags')
