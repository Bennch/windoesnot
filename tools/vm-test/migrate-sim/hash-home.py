#!/usr/bin/env python3
"""Record SHA-256 for a single fixture home, without crossing mounts or reading specials."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

if len(sys.argv) != 3:
    raise SystemExit('usage: hash-home.py HOME OUTPUT.json')
root = Path(sys.argv[1]).resolve(strict=True)
device = root.stat().st_dev
entries, skipped = {}, []
def visit(directory):
    for entry in sorted(os.scandir(directory), key=lambda e: e.name):
        path = Path(entry.path)
        rel = path.relative_to(root)
        if rel.parts[0] == '.cache' or rel.parts[:3] == ('.local', 'share', 'Trash'):
            skipped.append({'path': str(rel), 'reason': 'excluded'})
            continue
        st = entry.stat(follow_symlinks=False)
        if stat.S_ISDIR(st.st_mode):
            if st.st_dev != device or os.path.ismount(path):
                skipped.append({'path': str(rel), 'reason': 'mount'})
            else:
                visit(path)
        elif stat.S_ISREG(st.st_mode):
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
            entries[str(rel)] = {'size': st.st_size, 'sha256': h.hexdigest()}
        elif not stat.S_ISLNK(st.st_mode):
            skipped.append({'path': str(rel), 'reason': 'special'})
        else:
            entries[str(rel)] = {'symlink': os.readlink(path)}
visit(root)
Path(sys.argv[2]).write_text(json.dumps({'schema': 1, 'home': str(root), 'files': entries, 'skipped': skipped}, ensure_ascii=False, indent=2) + '\n')
