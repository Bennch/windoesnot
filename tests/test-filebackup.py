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
assert stamps[0] in kept and 4 <= len(kept) <= 10, len(kept)
recent = [(datetime.datetime(2026, 11, 20, 12, m)).strftime(fb.STAMP) for m in (0, 5, 10)]
assert fb.keep_set(recent, {'hourly': 1, 'daily': 1, 'weekly': 1, 'monthly': 1}) == set(recent), 'newest three always kept'
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

# restore of a chain: every stream is received into its own scratch folder, only the last subvolume is made writable and moved
# (a read-only subvolume cannot be renamed across folders: EROFS on the real kernel, found by the Codex retest)
import os, subprocess as sp, tempfile as tf
class FakeRun:
    def __init__(self, fs): self.fs = fs
    def __call__(self, *args, **kw):
        cmd = [str(c) for c in (args[0] if len(args) == 1 and isinstance(args[0], (list, tuple)) else args)]; out = sp.CompletedProcess(cmd, 0, '', '')
        if cmd[1:3] == ['receive', '-q']:
            snap = Path(cmd[3]) / 'snapshot'; snap.mkdir(); self.fs['ro'][str(snap)] = True
        elif cmd[1:3] == ['property', 'set']:
            assert cmd[3] == '-f', 'a received subvolume needs -f to flip ro->rw (real btrfs refuses otherwise)'
            self.fs['ro'][cmd[5]] = False
        elif cmd[1:3] == ['subvolume', 'delete']:
            import shutil as sh; sh.rmtree(cmd[3])
        elif cmd[0].endswith('findmnt'):
            out = sp.CompletedProcess(cmd, 0, 'btrfs\n', '')
        return out
class FakePopen:
    def __init__(self, cmd, **kw): self.stdout = open(os.devnull, 'rb')
    def wait(self): return 0
work = Path(tf.mkdtemp()); folder = work / 'backup'; into = work / 'into'; folder.mkdir(); into.mkdir()
entries = [dict(id=2, parent=None, file='snap-2-20261120T000001-full.btrfs.zst'), dict(id=3, parent=2, file='snap-3-20261120T000002-inc2.btrfs.zst'), dict(id=4, parent=3, file='snap-4-20261120T000003-inc3.btrfs.zst')]
for e in entries: (folder / e['file']).write_bytes(b'x')
fs = {'ro': {}}; real_rename = os.rename
def checked_rename(a, b):
    assert fs['ro'].get(str(a)) is False, 'a read-only subvolume must not be renamed (EROFS)'; real_rename(a, b)
saved = (se.run, se.subprocess.run, se.subprocess.Popen, se.allowed_destination, se.read_index, se.same_device, os.rename, se.os.path.realpath)
se.run = FakeRun(fs); se.subprocess.run = FakeRun(fs); se.subprocess.Popen = FakePopen
se.allowed_destination = lambda d, u: folder; se.read_index = lambda f: entries; se.same_device = lambda a, b: False; os.rename = checked_rename
try:
    result = se.restore(str(folder), 4, str(into), 1000)
finally:
    se.run, se.subprocess.run, se.subprocess.Popen, se.allowed_destination, se.read_index, se.same_device, os.rename = saved[:7]
assert result['ok'] and result['received'] == [2, 3, 4], result
assert sorted(p.name for p in into.iterdir()) == ['restore-4'], sorted(p.name for p in into.iterdir())
import shutil; shutil.rmtree(work)

# run_rsync drains stderr while the process runs: 300 KB of warnings before any progress used to block rsync on a full pipe
import signal
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(AssertionError('run_rsync hangs when stderr fills its pipe')))
signal.alarm(20)
fb.run_rsync(['sh', '-c', 'i=0; while [ $i -lt 6000 ]; do echo "file has vanished: \"/some/long/path/that/disappears/during/the/backup/$i\"" >&2; i=$((i+1)); done; echo "  1,024 100%  0.00kB/s"; exit 24'])
signal.alarm(0)
try:
    fb.run_rsync(['sh', '-c', 'i=0; while [ $i -lt 6000 ]; do echo "boom $i" >&2; i=$((i+1)); done; exit 11'])
    raise SystemExit('a real rsync error must raise')
except fb.BackupError as error:
    assert str(error) == 'boom 5999', str(error)
import shutil; shutil.rmtree(tmp)
print('PASS: filebackup engine')
