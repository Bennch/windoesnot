#!/usr/bin/env python3
"""Validate and plan an R2 repository upload; uploads require --publish."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--repository', type=Path, required=True)
p.add_argument('--fingerprint', required=True)
p.add_argument('--client-bundle', type=Path)
p.add_argument('--plan', type=Path, required=True)
p.add_argument('--profile', default='windoesnot-r2')
p.add_argument('--bucket', default='windoesnot')
p.add_argument('--endpoint', default='https://7a6c4099b8258fbf6e1938332649c529.r2.cloudflarestorage.com')
p.add_argument('--server', default='https://download.windoesnot.me/repo/x86_64')
p.add_argument('--publish', action='store_true')
a = p.parse_args()
if a.profile == 'default':
    p.error('Use a dedicated R2 profile, never the unrelated default AWS profile')
repo = a.repository.resolve()
metadata = json.loads((repo / 'REPOSITORY.json').read_text())
if not metadata['signed'] or metadata['private_test_only']:
    p.error('Only a signed production repository may be published')
if metadata['key'] != a.fingerprint.upper():
    p.error('Repository key differs from the independently supplied fingerprint')

# Reuse the existing verifier: checks the key, manifest, DBs and every package.
with tempfile.TemporaryDirectory(prefix='windoesnot-publish-check-') as temporary:
    work = Path(temporary)
    subprocess.run([
        sys.executable, str(ROOT / 'tools/prepare-repository-client.py'),
        '--repository', str(repo), '--fingerprint', a.fingerprint,
        '--server', a.server, '--output', str(work / 'client'),
    ], check=True)
    if a.client_bundle:
        keyring = work / 'release.gpg'
        subprocess.run(['gpg', '--no-options', '--homedir', str(work), '--batch', '--dearmor', '--output', str(keyring),
                        str(repo / 'RELEASE-KEY.asc')], check=True)
        subprocess.run(['gpgv', '--homedir', str(work), '--keyring', str(keyring),
                        str(a.client_bundle) + '.sig', str(a.client_bundle)], check=True)

files = []
def add(source, key, immutable, content_type):
    source = source.resolve(strict=True)
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    files.append({
        'source': str(source), 'key': key, 'bytes': source.stat().st_size,
        'sha256': digest,
        'immutable': immutable, 'content_type': content_type,
        'cache_control': 'public, max-age=31536000, immutable' if immutable else 'no-cache, max-age=0, must-revalidate',
    })

# Explicit allowlist, never a recursive sync of a directory containing backups.
for package in metadata['packages'].values():
    name = package['filename']
    add(repo / name, 'repo/x86_64/' + name, True, 'application/octet-stream')
    add(repo / (name + '.sig'), 'repo/x86_64/' + name + '.sig', True, 'application/octet-stream')
for name in ('RELEASE-KEY.asc', 'RELEASE-KEY.fingerprint', 'REPOSITORY.json', 'REPOSITORY.json.sig'):
    add(repo / name, 'repo/x86_64/' + name, False, 'application/json' if name.endswith('.json') else 'application/octet-stream')
if a.client_bundle:
    for source in (a.client_bundle, Path(str(a.client_bundle) + '.sig')):
        add(source, 'repo/bootstrap/' + source.name, True, 'application/octet-stream')
# Resolve repo-add aliases into actual object contents; DBs/signatures go last.
for name in ('windoesnot.files.tar.gz', 'windoesnot.files.tar.gz.sig', 'windoesnot.files', 'windoesnot.files.sig',
             'windoesnot.db.tar.gz', 'windoesnot.db.tar.gz.sig', 'windoesnot.db', 'windoesnot.db.sig'):
    source = repo / name
    if source.resolve().parent != repo:
        p.error('Repository alias points outside the signed snapshot: ' + name)
    aliases = {'windoesnot.db': 'windoesnot.db.tar.gz', 'windoesnot.db.sig': 'windoesnot.db.tar.gz.sig',
               'windoesnot.files': 'windoesnot.files.tar.gz', 'windoesnot.files.sig': 'windoesnot.files.tar.gz.sig'}
    if name in aliases and source.read_bytes() != (repo / aliases[name]).read_bytes():
        p.error('Repository alias differs from the signed database: ' + name)
    add(source, 'repo/x86_64/' + name, False, 'application/octet-stream')
aws = ['aws', '--profile', a.profile, '--region', 'auto', '--endpoint-url', a.endpoint]
plan = {'bucket': a.bucket, 'server': a.server, 'fingerprint': a.fingerprint.upper(),
        'bytes': sum(f['bytes'] for f in files), 'files': files}
a.plan.parent.mkdir(parents=True, exist_ok=True)
a.plan.write_text(json.dumps(plan, indent=2) + '\n')

if a.publish:
    # Complete all immutability checks before changing any object.
    for item in files:
        if not item['immutable']:
            continue
        result = subprocess.run([*aws, 's3api', 'head-object', '--bucket', a.bucket,
                                 '--key', item['key'], '--output', 'json'], text=True, capture_output=True)
        if result.returncode:
            if not any(code in result.stderr for code in ('(404)', 'NoSuchKey', 'NotFound')):
                raise SystemExit(result.stderr)
        else:
            old = json.loads(result.stdout)
            if old.get('Metadata', {}).get('sha256') != item['sha256'] or old['ContentLength'] != item['bytes']:
                raise SystemExit('Refusing to overwrite a different immutable artifact: ' + item['key'])
for item in files:
    command = [*aws, 's3', 'cp', item['source'], f"s3://{a.bucket}/{item['key']}",
               '--storage-class', 'STANDARD', '--cache-control', item['cache_control'],
               '--content-type', item['content_type'], '--metadata', 'sha256=' + item['sha256'],
               '--only-show-errors']
    if a.publish:
        subprocess.run(command, check=True)
    else:
        print(shlex.join([*command, '--dryrun']))
print(f"{'Uploaded' if a.publish else 'Planned'} {len(files)} objects, {plan['bytes']} bytes. Plan: {a.plan}")
print('Database/signature changes span separate R2 requests; clients must fail closed and retry during publication.')
