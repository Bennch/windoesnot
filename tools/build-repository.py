#!/usr/bin/env python3
"""Assemble a versioned local Pacman repository; never uploads or edits pacman.conf."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--packages',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
choice=parser.add_mutually_exclusive_group(required=True)
choice.add_argument('--sign-key',help='Existing GPG fingerprint; uses the caller-selected GNUPGHOME')
choice.add_argument('--unsigned-test',action='store_true',help='Explicitly allow an unsigned PRIVATE VM test repository')
parser.add_argument('--test-only',action='store_true',help='Mark a signed snapshot as a private test, e.g. when using an ephemeral key')
args=parser.parse_args()
if args.sign_key:
    args.sign_key=args.sign_key.upper()
    if not re.fullmatch(r'(?:[A-F0-9]{40}|[A-F0-9]{64})',args.sign_key):
        parser.error('Use the complete primary-key fingerprint, not a short key ID')
    keys=subprocess.check_output(['gpg','--batch','--with-colons','--list-keys',args.sign_key],text=True)
    primary=next((line.split(':')[9] for line in keys.splitlines() if line.startswith('fpr:')),None)
    if primary!=args.sign_key: parser.error('Fingerprint must identify the primary key')
output=args.output.resolve()
if output.exists(): raise SystemExit('Use a new output directory; repositories are immutable snapshots')
packages=sorted(args.packages.glob('*.pkg.tar.zst'))
expected={'windoesnot-desktop','windoesnot-tools','windoesnot-plugins','windoesnot-components'}
optional={'windoesnot-store'}
metadata={}
for package in packages:
    name,version=subprocess.check_output(['pacman','-Qp',str(package)],text=True).strip().split()
    if name not in expected|optional or name in metadata: raise SystemExit('Unexpected/duplicate package: '+name)
    metadata[name]={'version':version,'filename':package.name,'sha256':hashlib.sha256(package.read_bytes()).hexdigest()}
if not expected.issubset(metadata) or len({metadata[name]['version'] for name in expected if name in metadata})!=1:
    raise SystemExit('Supply exactly one matching version of all four packages')
output.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='.repo-stage-',dir=output.parent) as temp:
    stage=Path(temp)/'repo';stage.mkdir()
    paths=[]
    for package in packages:
        dest=stage/package.name;shutil.copy2(package,dest);paths.append(str(dest))
        if args.sign_key:
            subprocess.run(['gpg','--batch','--yes','--local-user',args.sign_key,'--detach-sign','--output',str(dest)+'.sig',str(dest)],check=True)
    command=['repo-add']
    if args.sign_key: command += ['--sign','--key',args.sign_key,'--verify']
    subprocess.run([*command,str(stage/'windoesnot.db.tar.gz'),*paths],check=True)
    if args.sign_key:
        signed=[*(Path(p) for p in paths),stage/'windoesnot.db.tar.gz',stage/'windoesnot.files.tar.gz']
        for item in signed:
            subprocess.run(['gpg','--batch','--verify',str(item)+'.sig',str(item)],check=True)
    manifest=stage/'REPOSITORY.json'
    manifest.write_text(json.dumps({'signed':bool(args.sign_key),'key':args.sign_key,'private_test_only':args.unsigned_test or args.test_only,'packages':metadata},indent=2)+'\n')
    if args.sign_key:
        with (stage/'RELEASE-KEY.asc').open('wb') as stream:
            subprocess.run(['gpg','--batch','--armor','--export',args.sign_key],stdout=stream,check=True)
        (stage/'RELEASE-KEY.fingerprint').write_text(args.sign_key+'\n')
        subprocess.run(['gpg','--batch','--yes','--local-user',args.sign_key,'--detach-sign','--output',str(manifest)+'.sig',str(manifest)],check=True)
        subprocess.run(['gpg','--batch','--verify',str(manifest)+'.sig',str(manifest)],check=True)
    stage.rename(output)
print(output)
print('Local snapshot created. No publication or client configuration performed.')
