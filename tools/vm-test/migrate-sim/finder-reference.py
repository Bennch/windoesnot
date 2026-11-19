#!/usr/bin/env python3
"""Build a comparison tree from the selected manifest paths, independently of finder copy."""
import json, os, pathlib, subprocess, sys
m = json.load(open(sys.argv[1]))
out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
root = pathlib.Path(m['source_root']); home = root / m['user']['home'].lstrip('/')
unselected = [p for f in m['findings'] if not f['selected'] and f.get('note') != 'absolute' for p in f['paths']]
for f in m['findings']:
    if not f['selected']: continue
    absolute = f.get('note') == 'absolute'
    for rel in f['paths']:
        base = root if absolute else home
        dst = out if absolute else out / 'home/benni'
        dst.mkdir(parents=True, exist_ok=True)
        cmd = ['rsync', '-aHAXS', '--numeric-ids', '--no-specials', '--no-devices', '--relative']
        if not absolute:
            cmd += ['--exclude=/' + p for p in unselected]
        cmd += ['--', './' + rel.lstrip('/'), str(dst) + '/']
        subprocess.run(cmd, cwd=base, check=True)
# rsync is invoked once per selected path; restore source hardlink relationships
# across those invocations so verify.py checks the source, not rsync's partitioning.
seen = {}
for parent, dirs, files in os.walk(out, followlinks=False):
    for name in files:
        dest = pathlib.Path(parent) / name
        rel = dest.relative_to(out)
        src = root / rel
        if not src.is_file() or src.is_symlink() or dest.is_symlink():
            continue
        st = src.stat()
        if st.st_nlink < 2:
            continue
        key = (st.st_dev, st.st_ino)
        if key in seen:
            dest.unlink()
            os.link(seen[key], dest)
        else:
            seen[key] = dest
