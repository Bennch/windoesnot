#!/usr/bin/env python3
"""One-time conversion of the old unowned development layout to Pacman packages.

Dry run by default. Run from a TTY while the selected user's desktop is stopped.
Ordinary subsequent upgrades use pacman and need none of this cleanup.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--packages',required=True,type=Path)
parser.add_argument('--user',required=True)
parser.add_argument('--apply',action='store_true')
parser.add_argument('--sync-tool',type=Path,default=ROOT/'desktop/bin/windoesnot-desktop-sync')
args=parser.parse_args()
account=pwd.getpwnam(args.user)
if account.pw_uid<1000: raise SystemExit('Select a regular desktop account')
home=Path(account.pw_dir)
expected={'windoesnot-desktop','windoesnot-tools','windoesnot-plugins','windoesnot-components'}
def output(*argv): return subprocess.check_output(argv,text=True).strip()
packages=sorted(args.packages.resolve().glob('*.pkg.tar.zst'))
versions={}
files=set()
for package in packages:
    name,version=output('pacman','-Qp',str(package)).split()
    if name not in expected or name in versions: raise SystemExit('Unexpected/duplicate package')
    versions[name]=version
    files.update(output('pacman','-Qqlp',str(package)).splitlines())
if set(versions)!=expected or len(set(versions.values()))!=1: raise SystemExit('Need all four matching packages')
if Path('/var/lib/pacman/db.lck').exists(): raise SystemExit('Another package transaction is active')
if subprocess.run(['pgrep','-u',str(account.pw_uid),'-x','Hyprland'],stdout=subprocess.DEVNULL).returncode==0:
    raise SystemExit('Log out of the selected desktop before the one-time migration')
source=Path('/usr/share/windoesnot')
if not (source/'desktop/config/hypr/hyprland.lua').is_file(): raise SystemExit('Legacy WinDoesNot source is missing')
if (source/'VERSION').exists(): raise SystemExit('Already package-managed; use normal pacman updates')
owned=set(output('pacman','-Qlq').splitlines())
collisions=[]
for value in sorted(files):
    path=Path(value)
    if not path.is_absolute() or '..' in path.parts or not (value.startswith('/usr/') and not value.endswith('/')):
        if value.endswith('/'): continue
        raise SystemExit('Unexpected package file path: '+value)
    if (path.is_file() or path.is_symlink()) and value not in owned: collisions.append(path)
shadows=[]
for command in (source/'desktop/bin').iterdir():
    for directory in [Path('/usr/local/bin'),home/'.local/bin']:
        target=directory/command.name
        if target.exists() or target.is_symlink():
            if target.is_symlink() or target.read_bytes()!=command.read_bytes():
                raise SystemExit('Locally modified launcher needs manual review: '+str(target))
            shadows.append(target)
for directory in [Path('/usr/local/bin'),home/'.local/bin']:
    target=directory/'snappy-switcher'; original=Path('/usr/lib/windoesnot/bin/snappy-switcher')
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not original.is_file() or target.read_bytes()!=original.read_bytes():
            raise SystemExit('Locally modified switcher needs manual review: '+str(target))
        shadows.append(target)
plan={'user':args.user,'versions':versions,'unowned_files_to_back_up':len(collisions),'legacy_launchers_to_back_up':[str(p) for p in shadows]}
print(json.dumps(plan,indent=2),flush=True)
if not args.apply: raise SystemExit(0)
if os.geteuid()!=0: raise SystemExit('--apply requires root; no changes made')
# Resolve the complete target transaction before touching unowned legacy files.
subprocess.run(['pacman','-Up','--noconfirm',*[str(p) for p in packages]],check=True)
backup=Path('/var/lib/windoesnot/legacy-layout')/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
backup.mkdir(parents=True,mode=0o700)
# The source baseline is read before replacing files. The user's ledger is
# created as that user, not root, and adoption does not modify their config.
subprocess.run(['runuser','-u',args.user,'--','env','HOME='+str(home),'XDG_CONFIG_HOME='+str(home/'.config'),'XDG_STATE_HOME='+str(home/'.local/state'),'python3',str(args.sync_tool.resolve()),'--adopt','--source',str(source)],check=True)
paths=list(dict.fromkeys([*collisions,*shadows]))
for path in paths:
    target=backup/path.relative_to('/')
    target.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink(): target.symlink_to(os.readlink(path))
    else: shutil.copy2(path,target)
    stat=path.lstat()
    os.chown(target,stat.st_uid,stat.st_gid,follow_symlinks=False)
(backup/'MANIFEST.json').write_text(json.dumps({'plan':plan,'files':[str(p) for p in paths]},indent=2)+'\n')
for path in paths: path.unlink()
try:
    subprocess.run(['pacman','-U','--noconfirm',*[str(p) for p in packages]],check=True)
except BaseException:
    # Restore pre-transaction files only where no newly installed file exists.
    for path in paths:
        saved=backup/path.relative_to('/')
        if not path.exists() and not path.is_symlink():
            if saved.is_symlink(): path.symlink_to(os.readlink(saved))
            else: shutil.copy2(saved,path)
            stat=saved.lstat()
            os.chown(path,stat.st_uid,stat.st_gid,follow_symlinks=False)
    print('Package transaction failed. Recovery files: '+str(backup),flush=True)
    raise
print('Installed. Recovery backup: '+str(backup))
print('Log in normally to refresh managed user code. Personal settings remain in your home.')
