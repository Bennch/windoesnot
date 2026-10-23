#!/usr/bin/env python3
"""Fetch only the exact official source commits recorded by this project."""
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent.parent
pins=json.loads((ROOT/'sources.json').read_text())
for name in ['cachyos-live-iso','cachyos-calamares']:
    source=ROOT/'upstream'/name;pin=pins[name]
    if not (source/'.git').exists():
        source.mkdir(parents=True,exist_ok=True)
        subprocess.run(['git','init',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'remote','add','origin',pin['url']],check=True)
    head=subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],capture_output=True,text=True)
    if head.returncode==0 and head.stdout.strip()==pin['commit']:continue
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():raise SystemExit(f'Preserving local edits in {source}; fetch stopped')
    subprocess.run(['git','-C',str(source),'fetch','--depth','1','origin',pin['commit']],check=True)
    subprocess.run(['git','-C',str(source),'checkout','--detach',pin['commit']],check=True)
print('Pinned official sources available')
