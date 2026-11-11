#!/usr/bin/env python3
"""Review new official sources and regenerate our overlays before applying pins."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parent.parent

def run(args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)

parser=argparse.ArgumentParser()
parser.add_argument('--iso-ref',default='master')
parser.add_argument('--calamares-ref',default='cachyos')
parser.add_argument('--apply',action='store_true',help='Update pinned worktrees only after profile checks pass')
args=parser.parse_args()
review=ROOT/'build'/('upstream-review-'+time.strftime('%Y%m%d-%H%M%S'))
review.mkdir(parents=True)
pins=json.loads((ROOT/'sources.json').read_text())
for name,ref in [('cachyos-live-iso',args.iso_ref),('cachyos-calamares',args.calamares_ref)]:
    source=ROOT/'upstream'/name
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():
        raise SystemExit(f'{name} has local edits; preserving them and stopping')
    run(['git','-C',str(source),'fetch','--depth','30','origin',ref])
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','FETCH_HEAD'],text=True).strip()
    run(['git','-C',str(source),'worktree','add','--detach',str(review/name),commit])
    with (review/f'{name}.diff').open('w') as stream:
        run(['git','-C',str(source),'diff',pins[name]['commit'],commit,'--','archiso','settings_offline.conf','src/modules','src/scripts'],stdout=stream)
    pins[name]['commit']=commit
proposal=review/'sources.json';proposal.write_text(json.dumps(pins,indent=2)+'\n')
run(['python3',str(ROOT/'tools/prepare-profile.py'),'--sources-root',str(review),'--source-manifest',str(proposal),'--output',str(review/'profile')])
run(['python3',str(ROOT/'tools/validate-desktop.py')])
print('Review profile and upstream differences:',review)
if args.apply:
    for name in ['cachyos-live-iso','cachyos-calamares']:
        run(['git','-C',str(ROOT/'upstream'/name),'checkout','--detach',pins[name]['commit']])
    (ROOT/'sources.json').write_text(proposal.read_text())
    print('Pins updated. Resolve packages, build and test the new ISO before deploying.')
else:
    print('Current pins and desktop remain unchanged. Repeat with --apply after review.')
