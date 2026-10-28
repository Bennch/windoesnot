#!/usr/bin/env python3
"""Prepare an offline device-manager build from the exact sources.json commit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def stage(pin, target, root=ROOT):
    repo = root / pin.get('path', 'device-manager')
    commit = pin['commit']
    subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', f'{commit}^{{commit}}'], check=True)
    pkgbuild = subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:pkgbuild/PKGBUILD'], text=True)
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=False)
    archive = target / 'windoesnot-device-manager-source.tar.gz'
    subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar.gz',
                    '--prefix=windoesnot-device-manager/', '-o', str(archive), commit], check=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    pkgbuild, count = re.subn(r'^sha256sums=.*$', f"sha256sums=('{digest}')", pkgbuild, count=1, flags=re.M)
    if count != 1:
        raise ValueError('Missing device-manager source checksum')
    (target / 'PKGBUILD').write_text(pkgbuild)
    report = {'commit': commit, 'archive_sha256': digest}
    (target / 'source.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(json.loads((ROOT / 'sources.json').read_text())['windoesnot-device-manager'], args.output)))
