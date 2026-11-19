#!/usr/bin/env python3
"""Compare a fixture with a migrated filesystem without following symlinks."""
import argparse
from collections import defaultdict
import hashlib
import os
from pathlib import Path
import stat
import sys

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('target', type=Path)
p.add_argument('--uid-map', action='append', default=[], metavar='OLD:NEW')
p.add_argument('--gid-map', action='append', default=[], metavar='OLD:NEW')
a = p.parse_args()
def mapping(items):
    try: return dict(tuple(map(int, item.split(':'))) for item in items)
    except ValueError: p.error('maps must be OLD:NEW numeric pairs')
uids, gids = mapping(a.uid_map), mapping(a.gid_map)
roots = [x.resolve(strict=True) for x in (a.source, a.target)]
if not all(x.is_dir() for x in roots): p.error('both roots must be directories')
categories = ('Home', 'Docker', 'VMs', '/opt', 'Andere Benutzer', 'Sonstiges')
def category(path):
    s = path.as_posix()
    if s.startswith(('var/lib/docker/', 'srv/docker/', 'etc/docker/')): return 'Docker'
    if s.startswith('var/lib/libvirt/') or 'VirtualBox VMs/' in s: return 'VMs'
    if s == 'opt' or s.startswith('opt/'): return '/opt'
    if s == 'home/anna' or s.startswith('home/anna/'): return 'Andere Benutzer'
    if s == 'home/benni' or s.startswith('home/benni/'): return 'Home'
    return 'Sonstiges'
def excluded(path):
    parts = path.parts
    return len(parts) >= 3 and parts[0] == 'home' and (parts[2] == '.cache' or parts[2:5] == ('.local', 'share', 'Trash'))
def walk(root):
    result = {}
    def visit(path):
        for entry in sorted(os.scandir(root / path), key=lambda e: e.name):
            rel = path / entry.name
            if excluded(rel): continue
            st = entry.stat(follow_symlinks=False)
            result[rel] = st
            if stat.S_ISDIR(st.st_mode): visit(rel)
    visit(Path())
    return result

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.digest()
def attrs(path):
    return {key: os.getxattr(path, key, follow_symlinks=False) for key in os.listxattr(path, follow_symlinks=False)}
try:
    trees = [walk(root) for root in roots]
    counts = defaultdict(int); errors = defaultdict(list)
    def fail(path, message): errors[category(path)].append(f'{str(path)!r}: {message}')
    for path in sorted(trees[0].keys() | trees[1].keys()):
        cat = category(path); counts[cat] += 1
        if path not in trees[0] or path not in trees[1]:
            fail(path, 'unexpected in target' if path not in trees[0] else 'missing in target'); continue
        s, t = trees[0][path], trees[1][path]
        if stat.S_IFMT(s.st_mode) != stat.S_IFMT(t.st_mode): fail(path, 'type differs'); continue
        if stat.S_IMODE(s.st_mode) != stat.S_IMODE(t.st_mode): fail(path, 'mode differs')
        if uids.get(s.st_uid, s.st_uid) != t.st_uid or gids.get(s.st_gid, s.st_gid) != t.st_gid: fail(path, 'owner differs')
        if stat.S_ISREG(s.st_mode) and (s.st_size != t.st_size or digest(roots[0] / path) != digest(roots[1] / path)): fail(path, 'SHA-256/size differs')
        if stat.S_ISLNK(s.st_mode) and os.readlink(roots[0] / path) != os.readlink(roots[1] / path): fail(path, 'symlink target differs')
        if attrs(roots[0] / path) != attrs(roots[1] / path): fail(path, 'xattr/ACL differs')
    # Compare hardlink equivalence classes, including accidental extra links within the tree.
    groups = []
    for tree in trees:
        by_inode = defaultdict(set)
        for path, st in tree.items():
            if stat.S_ISREG(st.st_mode): by_inode[(st.st_dev, st.st_ino)].add(path)
        groups.append({frozenset(group) for group in by_inode.values() if len(group) > 1})
    for group in groups[0] ^ groups[1]:
        for path in sorted(group): fail(path, 'hardlink group differs')
    for cat in categories:
        print(f'{"FAIL" if errors[cat] else "PASS"} {cat}: {counts[cat]} paths, {len(errors[cat])} errors')
        for error in errors[cat][:5]: print('  ', error)
    sys.exit(any(errors.values()))
except (OSError, ValueError) as exc:
    print(f'FAIL: {exc}', file=sys.stderr); sys.exit(2)
