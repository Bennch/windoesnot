#!/usr/bin/env python3
"""Isolated pacman update-resolution preview; success is not an installation test."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tarfile
import glob

BASE = Path(__file__).resolve().parents[1]
WORK = BASE / 'out/update-gate/work'

def classify(code, log):
    if not code:
        return 'PASS'
    s = log.lower()
    if any(x in s for x in ('unable to satisfy dependency', 'could not satisfy dependencies', 'cannot resolve')):
        return 'UNSATISFIABLE_DEPENDENCY'
    if 'exists in filesystem' in s or 'conflicting files' in s:
        return 'FILE_CONFLICT'
    if 'conflicting dependencies' in s or 'are in conflict' in s:
        return 'PACKAGE_CONFLICT'
    return 'INFRA_ERROR'

def repository_order(config):
    """Read pacman sections in include expansion order, rejecting ambiguous input."""
    order = []
    active = set()
    def read(path):
        path = path.resolve()
        if path in active:
            raise ValueError(f'include cycle: {path}')
        active.add(path)
        for line in path.read_text().splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            if line.startswith('[') and line.endswith(']'):
                name = line[1:-1].strip()
                if name.lower() != 'options':
                    if not name or name in order or '/' in name or name in ('.', '..'):
                        raise ValueError(f'invalid or duplicate repository: {name}')
                    order.append(name)
            elif re.match(r'(?i)^include\s*=', line):
                pattern = line.split('=', 1)[1].strip()
                if not os.path.isabs(pattern):
                    pattern = str(path.parent / pattern)
                matches = sorted(glob.glob(pattern))
                if not matches:
                    raise ValueError(f'include matches no files: {pattern}')
                for match in matches:
                    read(Path(match))
        active.remove(path)
    read(config)
    return order

def sync_packages(path):
    packages = {}
    with tarfile.open(path, 'r:*') as archive:
        for member in archive:
            if not member.isfile() or not member.name.rstrip('/').endswith('/desc'):
                continue
            stream = archive.extractfile(member)
            lines = stream.read().decode('utf-8').splitlines()
            def field(key):
                indexes = [i for i, line in enumerate(lines) if line == f'%{key}%']
                if len(indexes) != 1 or indexes[0] + 1 >= len(lines) or not lines[indexes[0] + 1]:
                    raise ValueError(f'invalid {key} in {path}: {member.name}')
                return lines[indexes[0] + 1]
            name, version = field('NAME'), field('VERSION')
            if name in packages:
                raise ValueError(f'duplicate package {name} in {path}')
            packages[name] = version
    return packages

def detect_shadowing(config, sync_dir):
    order = repository_order(config)
    if not order:
        raise ValueError('no repositories in config')
    seen = {}
    findings = []
    for repo in order:
        db = sync_dir / (repo + '.db')
        for name, version in sorted(sync_packages(db).items()):
            for early_repo, early_version in seen.get(name, []):
                compared = subprocess.run(['vercmp', early_version, version], text=True, capture_output=True, check=True)
                if int(compared.stdout.strip()) < 0:
                    findings.append({'name': name, 'earlier_repo': early_repo, 'earlier_version': early_version,
                                     'later_repo': repo, 'later_version': version})
            seen.setdefault(name, []).append((repo, version))
    return findings

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--detect-shadowing', type=Path, metavar='SYNC_DB_DIR', help='report older versions in earlier repositories as JSON')
    p.add_argument('--local-db', type=Path)
    p.add_argument('--pacman-d', type=Path)
    p.add_argument('--image', help='locally available OCI image by sha256 digest')
    p.add_argument('--work-dir', type=Path, default=WORK)
    p.add_argument('--snapshot', type=Path)
    p.add_argument('--packages', type=Path)
    p.add_argument('--json', type=Path)
    a = p.parse_args()
    if a.detect_shadowing is not None:
        try:
            payload = json.dumps(detect_shadowing(a.config, a.detect_shadowing), indent=2)
            if a.json:
                a.json.parent.mkdir(parents=True, exist_ok=True)
                a.json.write_text(payload + '\n')
            print(payload)
            return 0
        except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError, UnicodeError) as exc:
            print(json.dumps({'category': 'INFRA_ERROR', 'error': str(exc)}))
            return 2
    result = {'category':'INFRA_ERROR', 'exit_code':2, 'scope':'resolution preview only', 'mode':'live diagnostic', 'phases':[]}
    try:
        if not a.image or not re.search(r'@sha256:[0-9a-f]{64}$', a.image):
            raise ValueError('image must be pinned by sha256 digest')
        if a.snapshot or a.packages:
            raise ValueError('snapshot and candidate package injection are not implemented; refusing to ignore inputs')
        if not a.config.is_file() or not a.local_db or not a.local_db.is_dir() or not a.pacman_d or not a.pacman_d.is_dir():
            raise ValueError('config, local-db or pacman-d missing')
        if not (a.local_db / 'ALPM_DB_VERSION').is_file() or not any(a.local_db.glob('*/desc')):
            raise ValueError('local DB missing ALPM_DB_VERSION or installed package metadata')
        if (a.local_db.parent / 'db.lck').exists():
            raise ValueError('source DB is locked; export a consistent snapshot first')
        # Reject links and external Include paths; never follow a host link when copying.
        for root in (a.local_db, a.pacman_d):
            if root.is_symlink() or any(x.is_symlink() for x in root.rglob('*')):
                raise ValueError(f'symlink in input tree: {root}')
        for f in [a.config, *[x for x in a.pacman_d.rglob('*') if x.is_file() and 'gnupg' not in x.parts]]:
            if f.stat().st_size > 4_000_000: continue
            try: content = f.read_text()
            except UnicodeDecodeError: continue
            for line in content.splitlines():
                line = line.split('#', 1)[0].strip()
                if re.match(r'(?i)^(DBPath|RootDir|CacheDir|LogFile|HookDir|GPGDir)\s*=', line):
                    raise ValueError(f'path override requires isolated mapping: {f}: {line}')
                if re.match(r'(?i)^Include\s*=', line):
                    path = line.split('=',1)[1].strip()
                    if not path.startswith('/etc/pacman.d/') or '..' in Path(path).parts:
                        raise ValueError(f'unsafe include: {path}')
                if re.search(r'(?i)\bfile://', line):
                    raise ValueError('file:// repository requires explicit isolated mapping')
        if any(x.name in ('private-keys-v1.d', 'secring.gpg') for x in a.pacman_d.rglob('*')):
            raise ValueError('private key material in pacman-d; supply public trust data only')
        tool = shutil.which('podman') or shutil.which('docker')
        if not tool: raise ValueError('podman/docker unavailable')
        if not a.work_dir.resolve().is_relative_to(WORK.resolve()):
            raise ValueError(f'work-dir must be under {WORK}')
        a.work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='resolver-', dir=a.work_dir) as t:
            t = Path(t).resolve(); db = t / 'db'; db.mkdir()
            shutil.copytree(a.local_db, db / 'local')
            shutil.copytree(a.pacman_d, t / 'pacman.d')
            shutil.copy2(a.config, t / 'pacman.conf')
            common = [tool, 'run', '--rm', '--pull=never', '--security-opt', 'no-new-privileges', '-e', 'LC_ALL=C', '-v', f'{db}:/var/lib/pacman:rw', '-v', f'{t / "pacman.conf"}:/etc/pacman.conf:ro', '-v', f'{t / "pacman.d"}:/etc/pacman.d:rw', a.image]
            for phase, args in [('version',['pacman','--version']), ('sync',['pacman','-Sy','--noconfirm']), ('preview',['pacman','-Su','--print','--noconfirm'])]:
                run = subprocess.run(common + args, text=True, capture_output=True, timeout=600)
                result['phases'].append({'phase':phase,'exit_code':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
                if run.returncode:
                    result['category'] = classify(run.returncode, run.stdout + run.stderr) if phase == 'preview' else 'INFRA_ERROR'
                    result['exit_code'] = 1 if result['category'] != 'INFRA_ERROR' else 2
                    break
            else:
                result['category'] = 'PASS'; result['exit_code'] = 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result['error'] = str(exc)
    payload = json.dumps(result, indent=2)
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True); a.json.write_text(payload + '\n')
    print(payload)
    return result['exit_code']

if __name__ == '__main__':
    raise SystemExit(main())
