#!/usr/bin/env python3
"""Backup engine: snapshots with hard links, retention, restore with trash, mirror mode, due logic (no real drives needed)."""
import datetime, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'desktop/lib/windoesnot'))
tmp = Path(tempfile.mkdtemp(prefix='fbtest-', dir=os.environ.get('WDN_TEST_DIR', str(Path.home() / '.cache'))))
os.environ['XDG_CONFIG_HOME'] = str(tmp / 'cfg'); os.environ['XDG_CACHE_HOME'] = str(tmp / 'cache')
home = tmp / 'home'; home.mkdir(); os.environ['HOME'] = str(home)
import filebackup as fb
fb.Path.home = staticmethod(lambda: home)
target = tmp / 'disk'; target.mkdir()
(home / 'Documents').mkdir(); (home / 'Documents/a.txt').write_text('one'); (home / 'Documents/big.bin').write_bytes(b'x' * 100000)
(home / '.cache').mkdir(); (home / '.cache/junk').write_text('junk')
config = fb.load_config(); config.update(enabled=True, target={'kind': 'folder', 'path': str(target)}, sources=[str(home)])
fb.validate_config(config)
r1 = fb.run_backup(config); assert r1['mode'] == 'snapshots', r1
snaps = target / 'WinDoesNot-Backup' / fb.host_name() / 'snapshots'
first = next(snaps.iterdir()); first.rename(snaps / (datetime.datetime.now() - datetime.timedelta(hours=2)).strftime(fb.STAMP))  # points of one hour collapse into the newest
time.sleep(1.1); (home / 'Documents/a.txt').write_text('two')
r2 = fb.run_backup(config)
points = fb.list_snapshots(target); assert len(points) == 2, points
new, old = [Path(p['path']) for p in points]
assert (new / 'home/Documents/a.txt').read_text() == 'two' and (old / 'home/Documents/a.txt').read_text() == 'one'
assert os.stat(new / 'home/Documents/big.bin').st_ino == os.stat(old / 'home/Documents/big.bin').st_ino, 'unchanged file must be a hard link'
assert not (new / 'home/.cache').exists(), 'excluded folder copied'
assert [e['name'] for e in fb.browse(target, points[0]['id'], 'home')][0] == 'Documents'
assert all(not str(e).startswith('.') for e in os.listdir(target / 'WinDoesNot-Backup' / fb.host_name() / 'snapshots'))
try: fb.browse(target, points[0]['id'], '../..'); raise SystemExit('path traversal')
except fb.BackupError: pass
# restore: current file goes to the trash, backup content returns
os.environ['XDG_DATA_HOME'] = str(tmp / 'data')
fb.restore(target, points[1]['id'], 'home/Documents/a.txt'); assert (home / 'Documents/a.txt').read_text() == 'one'
fb.restore(target, points[0]['id'], 'home/Documents', destination=str(tmp / 'out')); assert (tmp / 'out/Documents/a.txt').read_text() == 'two'
# retention
stamps = [(datetime.datetime(2026, 11, 20, 12) - datetime.timedelta(hours=h)).strftime(fb.STAMP) for h in range(0, 24 * 40, 6)]
kept = fb.keep_set(stamps, {'hourly': 2, 'daily': 3, 'weekly': 2, 'monthly': 2})
assert stamps[0] in kept and 4 <= len(kept) <= 9, len(kept)
assert fb.keep_set([], {'hourly': 1}) == set()
# due logic
assert not fb.due({'enabled': False, 'schedule': 'daily', 'target': {}}) and fb.due({'enabled': True, 'schedule': 'daily', 'target': {'x': 1}}, {'last_success': 0})
assert not fb.due({'enabled': True, 'schedule': 'daily', 'target': {'x': 1}}, {'last_success': time.time()})
# unreachable target is not an error state
try: fb.run_backup({**config, 'target': {'kind': 'folder', 'path': str(tmp / 'gone')}}); raise SystemExit('should fail')
except fb.BackupError as e: assert str(e) == 'unavailable'
# mirror mode keeps old versions of replaced and deleted files
mirror = tmp / 'exfat'; mirror.mkdir()
orig = fb.supports_hardlinks; fb.supports_hardlinks = lambda *a: False
mc = {**config, 'target': {'kind': 'folder', 'path': str(mirror)}}
fb.run_backup(mc); time.sleep(1.1); fb.prune = lambda *a: []; (home / 'Documents/a.txt').write_text('three'); (home / 'Documents/big.bin').unlink()
assert fb.run_backup(mc)['mode'] == 'mirror'
ids = [p['id'] for p in fb.list_snapshots(mirror)]; assert 'current' in ids and any(i.startswith('v-') for i in ids), ids
assert (mirror / 'WinDoesNot-Backup' / fb.host_name() / 'current/home/Documents/a.txt').read_text() == 'three'
# system export: chain bookkeeping of the root helper (the btrfs transfer itself is tested in a VM)
import importlib.util
spec = importlib.util.spec_from_file_location('snapshot_export', str(Path(__file__).resolve().parent.parent / 'desktop/lib/windoesnot/snapshot_export.py'))
se = importlib.util.module_from_spec(spec); spec.loader.exec_module(se)
entries = []
for i in range(1, 15):
    name = 'snap-%d-20261101T000000-%s.btrfs.zst' % (i, 'full' if i % 4 == 1 else 'inc%d' % (i - 1))
    (tmp / name).write_text('x'); entries.append({'id': i, 'parent': None if i % 4 == 1 else i - 1, 'file': name})
kept = se.prune(tmp, entries)
assert [e['id'] for e in kept] == [5, 6, 7, 8, 9, 10, 11, 12, 13, 14], [e['id'] for e in kept]
assert not (tmp / entries[0]['file']).exists() and (tmp / entries[4]['file']).exists()
assert se.FILE_RE.fullmatch(entries[1]['file']) and not se.FILE_RE.fullmatch('../x.btrfs.zst')
import shutil; shutil.rmtree(tmp)
print('PASS: filebackup engine')
