#!/usr/bin/env python3
"""Validate package contents, public readability and ABI version requirements."""
import argparse
from pathlib import Path
import subprocess
import tarfile

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
        assert 'depend = hyprland=' in metadata and 'depend = libstdc++=' in metadata
    if name=='windoesnot-components':
        assert 'depend = qt6-base=' in metadata and 'depend = qtermwidget=' in metadata
    if name in ('windoesnot-plugins','windoesnot-components'):
        assert '-march=x86-64' in flags and '-mtune=generic' in flags and '-march=native' not in flags
    if name=='windoesnot-store':
        for dependency in ('gtk4','libadwaita','polkit','pacman'):
            assert f'depend = {dependency}\n' in metadata,dependency
assert set(found)==expected and len(set(found.values()))==1
if args.store:
    print('PASS: store package, root ownership, readable code, no setuid, no private state, desktop runtime dependencies')
else:
    print('PASS: four matching packages, root ownership, readable code, no private state, exact native ABI dependencies, generic CPU flags')
