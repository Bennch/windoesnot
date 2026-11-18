#!/usr/bin/env python3
"""Inventory concrete release inputs; ambiguous or missing inputs block the gate."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def packages(directory):
    result = []; seen = set(); files = sorted(directory.iterdir())
    for f in files:
        if f.name.endswith('.sig') and (directory / f.name[:-4]).is_file(): continue
        if not f.is_file() or '.pkg.tar.' not in f.name or f.name.endswith('.sig'):
            raise ValueError(f'unexpected package directory entry: {f}')
        check = subprocess.run(['bsdtar', '-tf', str(f)], capture_output=True)
        if check.returncode: raise ValueError(f'broken archive {f}: {check.stderr.decode(errors="replace")}')
        proc = subprocess.run(['bsdtar', '-xOf', str(f), '.PKGINFO'], capture_output=True)
        if proc.returncode: raise ValueError(f'broken archive {f}: {proc.stderr.decode(errors="replace")}')
        data = {}
        for line in proc.stdout.decode('utf-8').splitlines():
            if ' = ' in line:
                k, v = line.split(' = ', 1); data.setdefault(k, []).append(v)
        for key in ('pkgname', 'pkgver', 'arch'):
            if len(data.get(key, [])) != 1: raise ValueError(f'invalid {key}: {f}')
        name, version, arch = (data[x][0] for x in ('pkgname','pkgver','arch'))
        if (name, arch) in seen: raise ValueError(f'duplicate package {name}/{arch}')
        seen.add((name,arch)); result.append({'name':name,'version':version,'arch':arch,'file':str(f),'sha256':sha(f)})
    if not result: raise ValueError(f'no packages in {directory}')
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true'); p.add_argument('--json',type=Path)
    p.add_argument('--packages',type=Path)
    a=p.parse_args(); errors=[]; iso={}
    for release in (29,30):
        for lang in ('de','en'):
            key=f'{release}-{lang}'; paths=list((ROOT / f'out/release-0.1.0-{release}').glob(f'*-{lang}-x86_64.iso'))
            if len(paths) != 1: errors.append(f'{key}: expected one proven release ISO, found {len(paths)} in out/release-0.1.0-{release}'); continue
            iso[key]={'path':str(paths[0]),'sha256':sha(paths[0])}
    spec=importlib.util.spec_from_file_location('system_setup',ROOT/'iso/system_setup.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    profiles={'generic':{'extra_repositories':[]}}
    profiles.update({k:{'include':'/etc/pacman.d/'+v[0], 'extra_repositories':v[1]} for k,v in mod.LEVEL_REPOS.items()})
    package_dir=a.packages
    if package_dir is None:
        dirs=sorted((ROOT/'build').glob('release-packages-*'))
        errors.append('candidate package directory is ambiguous; supply --packages: '+', '.join(map(str,dirs)))
    package_list=[]
    if package_dir:
        try: package_list=packages(package_dir)
        except (OSError,ValueError,UnicodeError) as exc: errors.append(str(exc))
    errors.append('historical 29/30 installed repo configurations, mirror URLs and upstream fingerprints are not exported')
    data={'status':'BLOCKED' if errors else 'PASS','errors':errors,'predecessors':iso,'profiles_current_installer':profiles,'base_includes':mod.MIRRORLISTS,'release_key_fingerprint':(ROOT/'packaging/release-key/RELEASE-KEY.fingerprint').read_text().strip(),'candidate_packages':package_list,'cli_contract_sources':['tools/vmctl.py','tools/vm-test/README.md','tools/vm-test/*.sh','tools/build-repository.py']}
    payload=json.dumps(data,indent=2,ensure_ascii=False)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(payload+'\n')
    print(payload); return 2 if errors else 0
if __name__=='__main__': raise SystemExit(main())
