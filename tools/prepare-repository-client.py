#!/usr/bin/env python3
"""Verify a local signed snapshot and prepare, but do not install, client trust."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlparse

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--repository', type=Path, required=True)
p.add_argument('--fingerprint', required=True, help='Full primary fingerprint obtained independently')
p.add_argument('--server', required=True, help='HTTPS URL of the directory containing windoesnot.db')
p.add_argument('--output', type=Path, required=True)
p.add_argument('--allow-test-repository', action='store_true')
a = p.parse_args()
fingerprint = a.fingerprint.upper()
if not re.fullmatch(r'(?:[A-F0-9]{40}|[A-F0-9]{64})', fingerprint):
    p.error('A complete primary-key fingerprint is required')
url = urlparse(a.server)
if any(c in a.server for c in '\n\r\t ') or url.username or url.password:
    p.error('Invalid repository URL')
if not (url.scheme == 'https' and url.hostname) and not (
    a.allow_test_repository and url.scheme in ('http', 'file')
):
    p.error('Production clients require HTTPS')
repo = a.repository.resolve()
if a.output.exists():
    p.error('Use a new output directory')
with tempfile.TemporaryDirectory(prefix='windoesnot-trust-') as temporary:
    private = Path(temporary)
    key = repo / 'RELEASE-KEY.asc'
    listing = subprocess.check_output([
        'gpg', '--no-options', '--homedir', str(private), '--batch', '--with-colons', '--show-keys', str(key)
    ], text=True)
    primary = []
    want_primary = False
    for line in listing.splitlines():
        fields = line.split(':')
        if fields[0] in ('pub', 'sub'):
            want_primary = fields[0] == 'pub'
            if fields[0]=='pub' and (fields[1] in ('r','e','d') or (fields[6] and int(fields[6]) <= time.time())):
                p.error('Expired, revoked or disabled key material is not accepted')
        elif fields[0] == 'fpr' and want_primary:
            primary.append(fields[9])
            want_primary = False
    if primary != [fingerprint]:
        p.error('Public key does not match the independently supplied fingerprint')
    keyring = private / 'release.gpg'
    subprocess.run(['gpg', '--no-options', '--batch', '--dearmor', '--output', str(keyring), str(key)], check=True)
    def verify(path):
        result=subprocess.run(['gpgv', '--status-fd','1','--homedir', str(private), '--keyring', str(keyring), str(path) + '.sig', str(path)],check=True,text=True,capture_output=True)
        if any('[GNUPG:] '+status in result.stdout for status in ('EXPKEYSIG','EXPSIG','REVKEYSIG','KEYEXPIRED','SIGEXPIRED')):
            p.error('Expired or revoked signature: '+str(path))
        valid=[line.split() for line in result.stdout.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
        if not valid or any(row[2]!=fingerprint and row[-1]!=fingerprint for row in valid):
            p.error('Unexpected signature fingerprint: '+str(path))
    manifest = repo / 'REPOSITORY.json'
    verify(manifest)
    metadata = json.loads(manifest.read_text())
    if not metadata['signed'] or metadata['key'] != fingerprint:
        p.error('Inconsistent signed manifest')
    if metadata['private_test_only'] and not a.allow_test_repository:
        p.error('A test repository must never become a production client')
    for name in ('windoesnot.db.tar.gz', 'windoesnot.files.tar.gz'):
        verify(repo / name)
    for package in metadata['packages'].values():
        filename = package['filename']
        if Path(filename).name != filename:
            p.error('Unsafe package path')
        path = repo / filename
        if hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != package['sha256']:
            p.error('Package checksum mismatch: ' + filename)
        verify(path)
    a.output.mkdir(parents=True)
    shutil.copyfile(key, a.output / 'RELEASE-KEY.asc')
    (a.output / 'RELEASE-KEY.fingerprint').write_text(fingerprint + '\n')
    (a.output / 'windoesnot.conf').write_text(
        '[windoesnot]\nSigLevel = Required DatabaseRequired TrustedOnly\nServer = ' + a.server.rstrip('/') + '\n'
    )
    (a.output / 'CLIENT.json').write_text(json.dumps({
        'fingerprint': fingerprint, 'server': a.server, 'private_test_only': metadata['private_test_only'],
        'repository_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }, indent=2) + '\n')
    bootstrap = a.output / 'bootstrap.sh'
    bootstrap.write_text('''#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo on the target system.' >&2; exit 1; }
client_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
''' + ('systemd-detect-virt --vm --quiet || { echo "Test trust is allowed only in a VM." >&2; exit 1; }\n' if metadata['private_test_only'] else '') + '''
python3 - "$client_dir" <<'PY'
import pathlib,re,subprocess,sys,time,shutil
source=pathlib.Path(sys.argv[1])
config=pathlib.Path('/etc/pacman.conf')
text=config.read_text()
include='Include = /etc/pacman.d/windoesnot.conf'
if include in text or re.search(r'^\\[windoesnot\\]',text,re.M):
    sys.exit('Repository already configured; review the existing configuration first')
fingerprint=(source/'RELEASE-KEY.fingerprint').read_text().strip()
keys=subprocess.check_output(['gpg','--batch','--with-colons','--show-keys',str(source/'RELEASE-KEY.asc')],text=True)
actual=next(line.split(':')[9] for line in keys.splitlines() if line.startswith('fpr:'))
if actual!=fingerprint: sys.exit('Public key fingerprint mismatch')
subprocess.run(['pacman-key','--add',str(source/'RELEASE-KEY.asc')],check=True)
subprocess.run(['pacman-key','--lsign-key',fingerprint],check=True)
backup=config.with_name('pacman.conf.before-windoesnot-'+str(time.time_ns()))
shutil.copy2(config,backup)
shutil.copyfile(source/'windoesnot.conf','/etc/pacman.d/windoesnot.conf')
lines=text.splitlines(keepends=True)
position=next((i for i,line in enumerate(lines) if re.match(r'^\\[(?!options\\])',line)),len(lines))
lines.insert(position,include+'\\n\\n')
config.write_text(''.join(lines))
print('Configured repository. Backup:',backup)
print('Next: sudo pacman -Syu; then log out and back in.')
PY
''')
    bootstrap.chmod(0o755)
print('Verified client bundle:', a.output)
print('Nothing installed. Review the bundle; run its bootstrap.sh only on the intended target.')
