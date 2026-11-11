#!/usr/bin/env python3
"""Restore only files recorded by an install-user deployment backup."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

parser=argparse.ArgumentParser();parser.add_argument('backup',type=Path);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
home=Path.home();backup=args.backup.resolve()
if home not in backup.parents:raise SystemExit('Backup must be inside your home directory')
manifest=json.loads((backup/'manifest.json').read_text())
for record in manifest:
    target=Path(record['target'])
    if home not in target.parents:raise SystemExit('Refusing target outside HOME')
    print(('Restore' if record['existed'] else 'Remove new file'),target)
    if not args.apply:continue
    if record['existed']:
        saved=backup/target.relative_to(home)
        if record.get('symlink'):
            target.unlink(missing_ok=True);target.symlink_to(record['symlink'])
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as stream:
                stream.write(saved.read_bytes());temp=Path(stream.name)
            shutil.copymode(saved,temp);os.replace(temp,target)
    else:
        target.unlink(missing_ok=True)
print('Run hyprctl reload and restart the default Quickshell if restoring a running session.')
