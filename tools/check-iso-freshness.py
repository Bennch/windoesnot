#!/usr/bin/env python3
"""Compare an ISO build's package database with freshly synchronized repositories."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = 'usr/share/windoesnot/build-sync.json'


def fields(data):
    return {m.group(1): m.group(2).strip().splitlines() for m in re.finditer(r'^%([^%]+)%\n(.*?)(?=\n%|\Z)', data, re.M | re.S)}


def database(path):
    result = {}
    with tarfile.open(path, 'r:*') as archive:
        for entry in archive:
            if entry.name.endswith('/desc'):
                f = fields(archive.extractfile(entry).read().decode())
                if 'NAME' in f and 'VERSION' in f:
                    result[f['NAME'][0]] = f['VERSION'][0]
    return result


def snapshot(sync, local, destination):
    files = sorted(sync.glob('*.db'))
    if not files:
        raise ValueError('No build sync databases; cannot establish their age or package origins')
    installed = {}
    for desc in local.glob('*/desc'):
        f = fields(desc.read_text())
        if 'NAME' in f and 'VERSION' in f:
            installed[f['NAME'][0]] = f['VERSION'][0]
    repositories = {p.stem: database(p) for p in files}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'oldest_sync': min(p.stat().st_ctime for p in files),
        'matches': {n: [r for r, pkgs in repositories.items() if pkgs.get(n) == v]
                    for n, v in installed.items()}}, sort_keys=True) + '\n')


def classify(name, old, new, selected, matches):
    # A .N CPU rebuild must come from a CPU-specific CachyOS repository.
    if re.fullmatch(r'cachyos(?:-core|-extra)?-(?:v3|v4|znver4)', selected or '') and re.fullmatch(re.escape(old) + r'\.\d+', new):
        return 'b'
    if selected in matches.get(name, []):
        return 'a'
    return 'c'


def gate_failed(count, threshold, age):
    return count > threshold or age > 24


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iso', nargs='?', help='ISO under out/<build-id>')
    parser.add_argument('--build-id', help='explicit build ID when the ISO was copied or renamed')
    parser.add_argument('--threshold', type=int, default=25)
    parser.add_argument('--snapshot', nargs=3, metavar=('SYNC', 'LOCAL', 'OUTPUT'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.snapshot:
        snapshot(*(Path(x) for x in args.snapshot)); return 0
    if args.threshold < 0: parser.error('threshold must be non-negative')
    if not args.iso: parser.error('provide an ISO')
    iso = Path(args.iso).resolve(strict=True)
    if not iso.is_file() or iso.suffix != '.iso': parser.error('ISO file required')
    build_id = args.build_id or iso.parent.name
    if not re.fullmatch(r'[A-Za-z0-9_-]+', build_id): parser.error('invalid build ID')
    originals = list((ROOT / 'out' / build_id).glob('*.iso'))
    if not originals or not any(p.resolve() == iso or digest(p) == digest(iso) for p in originals):
        raise ValueError('ISO does not match an output of this build ID')
    build = ROOT / 'build' / build_id
    image = build / 'work/x86_64/airootfs'
    meta = json.loads((image / SNAPSHOT).read_text())
    local = image / 'var/lib/pacman/local'
    config = build / 'profile/pacman.conf'
    if not local.is_dir() or not config.is_file():
        raise ValueError('Build local database or profile config missing; use --build-id for the original build')
    with tempfile.TemporaryDirectory(prefix='wdn-fresh-', dir='/var/tmp') as temp:
        db = Path(temp) / 'db'; db.mkdir(); (db / 'local').symlink_to(local.resolve())
        env = dict(os.environ, LC_ALL='C')
        cmd = ['unshare', '--user', '--map-root-user', '--', 'pacman', '--config', str(config), '--dbpath', str(db)]
        subprocess.run(cmd + ['-Sy'], check=True, env=env, stdout=sys.stderr)
        sync = db / 'sync'
        # pacman-conf emits configured repositories in priority order.
        repos = subprocess.check_output(['pacman-conf', '--config', str(config), '--repo-list'], text=True, env=env).splitlines()
        dbs = [(r, database(sync / (r + '.db'))) for r in repos if (sync / (r + '.db')).is_file()]
        p = subprocess.run(cmd + ['-Qu'], capture_output=True, text=True, env=env)
        if p.returncode not in (0, 1) or 'error:' in p.stderr.lower(): raise RuntimeError(p.stderr)
        counts = dict(a=0, b=0, c=0)
        for line in p.stdout.splitlines():
            parts = line.split()
            if len(parts) != 4 or parts[2] != '->': raise ValueError('Unexpected pacman output: ' + line)
            name, old, _, new = parts
            selected = next((r for r, packages in dbs if name in packages), None)
            kind = classify(name, old, new, selected, meta['matches'])
            counts[kind] += 1
            print(f'{kind} {selected or "?"} {line}')
    age = (time.time() - meta['oldest_sync']) / 3600
    print(f"a={counts['a']} b={counts['b']} c={counts['c']}; oldest build sync DB: {age:.1f} h; threshold: {args.threshold}")
    if age < -0.1: raise ValueError('Build sync timestamp is in the future')
    return int(gate_failed(counts['a'], args.threshold, age))


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        print('Freshness check failed:', exc, file=sys.stderr); sys.exit(2)
