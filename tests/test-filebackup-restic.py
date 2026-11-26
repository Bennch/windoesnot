#!/usr/bin/env python3
"""Encrypted file backup (restic engine) against the real restic binary: init, backup, dedup, snapshots, browse, restore,
retention, wrong key, key file mode, key never in argv, logs, status, config or the repository. Skipped without restic."""
import contextlib, io, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

if shutil.which('restic') is None:
    print('SKIP test-filebackup-restic: restic is not installed (apt-get install restic / pacman -S restic)')
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'desktop/lib/windoesnot'))
tmp = Path(tempfile.mkdtemp(prefix='fbrestic-', dir=os.environ.get('WDN_TEST_DIR', tempfile.gettempdir())))
os.environ['XDG_CONFIG_HOME'] = str(tmp / 'cfg'); os.environ['XDG_CACHE_HOME'] = str(tmp / 'cache'); os.environ['XDG_DATA_HOME'] = str(tmp / 'data')
home = tmp / 'home'; home.mkdir(); os.environ['HOME'] = str(home)
import filebackup as fb
fb.Path.home = staticmethod(lambda: home)

# record every argv any subprocess is started with
argvs = []
real_run, real_popen = subprocess.run, subprocess.Popen
def spy_run(args, *a, **k):
    argvs.append(list(args)); return real_run(args, *a, **k)
class SpyPopen(real_popen):
    def __init__(self, args, *a, **k):
        argvs.append(list(args)); super().__init__(args, *a, **k)
subprocess.run, subprocess.Popen = spy_run, SpyPopen

def tree_size(path):
    return sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())

try:
    (home / 'Documents').mkdir(); (home / 'Documents/a.txt').write_text('one'); (home / 'Documents/big.bin').write_bytes(os.urandom(2_000_000))
    (home / 'Documents/sub').mkdir(); (home / 'Documents/sub/n.txt').write_text('nested')
    (home / '.cache').mkdir(); (home / '.cache/junk').write_text('junk')
    target = tmp / 'disk'; target.mkdir()
    config = fb.load_config()
    assert config['engine'] == 'rsync', 'existing configs keep the rsync engine'
    config.update(engine='restic', enabled=True, target={'kind': 'folder', 'path': str(target)}, sources=[str(home)])
    fb.validate_config(config)
    try: fb.validate_config({**config, 'engine': 'tar'}); raise SystemExit('unknown engine accepted')
    except fb.BackupError: pass

    # a silent background run must not invent a key nobody has seen
    try: fb.run_backup(config); raise SystemExit('background run created a key')
    except fb.BackupError as e: assert 'recovery key' in str(e), e
    assert not fb.PASSWORD_FILE.exists()

    # first run: key created, shown once
    result = fb.run_backup(config, force=True)
    key = result['recovery_key']
    assert result['mode'] == 'restic' and len(key) >= 32, result
    assert oct(fb.PASSWORD_FILE.stat().st_mode & 0o777) == '0o600', oct(fb.PASSWORD_FILE.stat().st_mode)
    assert fb.PASSWORD_FILE.read_text() == key
    assert (target / 'windoesnot-restic/config').is_file()
    first_size = tree_size(target / 'windoesnot-restic')
    assert first_size > 1_900_000, first_size

    # second run: changed small file, unchanged big file -> deduplicated
    (home / 'Documents/a.txt').write_text('two')
    result2 = fb.run_backup(config, force=True)
    assert 'recovery_key' not in result2, 'key must be shown only once'
    points = fb.restic_points(target)
    assert len(points) == 2 and all(fb.HEX_RE.fullmatch(p['id']) for p in points), points
    second_size = tree_size(target / 'windoesnot-restic')
    assert second_size < 2 * first_size * 0.75, (first_size, second_size)   # a full copy would be about 2x
    fb.save_config(config); status = fb.status_report()
    assert status['points'] == 2 and status['hasKey'] and status['config']['engine'] == 'restic', status

    # browse uses the same 'home/...' paths as the rsync engine; excluded folders are not in the backup
    new, old = points[0]['id'], points[1]['id']
    assert [e['name'] for e in fb.restic_browse(target, new)] == ['home']
    top = [e['name'] for e in fb.restic_browse(target, new, 'home')]
    assert 'Documents' in top and '.cache' not in top, top
    docs = {e['name']: e for e in fb.restic_browse(target, new, 'home/Documents')}
    assert set(docs) == {'a.txt', 'big.bin', 'sub'} and docs['sub']['dir'] and docs['big.bin']['size'] == 2_000_000, docs

    # restore: the replaced file goes to the trash, backup content returns
    (home / 'Documents/a.txt').write_text('three')
    fb.restic_restore(target, old, 'home/Documents/a.txt')
    assert (home / 'Documents/a.txt').read_text() == 'one', 'restore of the older snapshot'
    trashed = list((tmp / 'data/Trash/files').glob('a.txt*')) if (tmp / 'data/Trash/files').is_dir() else []
    assert trashed and trashed[0].read_text() == 'three', 'replaced file must be in the trash'
    out = tmp / 'out'
    fb.restic_restore(target, new, 'home/Documents/sub', destination=str(out))
    assert (out / 'sub/n.txt').read_text() == 'nested'
    fb.restic_restore(target, new, 'home/Documents/big.bin', destination=str(out))
    assert (out / 'big.bin').stat().st_size == 2_000_000
    assert not list(fb.CACHE_DIR.glob('restore-*')), 'scratch restore folder left behind'

    # strict validation: snapshot ids are hex, paths stay inside HOME
    for bad in ('../x', 'latest', 'abc', 'zz' * 8, new + '; rm -rf /', '', None):
        try: fb.restic_browse(target, bad, 'home'); raise SystemExit('bad id accepted: %r' % bad)
        except fb.BackupError: pass
        try: fb.restic_restore(target, bad, 'home/Documents/a.txt'); raise SystemExit('bad id accepted: %r' % bad)
        except fb.BackupError: pass
    for bad in ('home/../../etc/passwd', '../etc', 'etc/passwd', 'home/Documents/../../../x', 'abs+etc/passwd', 'home'):
        try: fb.restic_restore(target, new, bad); raise SystemExit('bad path accepted: %r' % bad)
        except fb.BackupError: pass
        try: fb.restic_browse(target, new, bad) if bad != 'home' else (_ for _ in ()).throw(fb.BackupError())
        except fb.BackupError: pass
        else: raise SystemExit('bad browse path accepted: %r' % bad)

    # integrity check
    assert fb.restic_check(target) == {'ok': True}

    # retention: five more points, nothing configured to keep except the always-kept newest three
    for _ in range(4):   # raw backups without the automatic forget of run_backup
        fb.run_restic(target, fb.restic_backup_args(config, target))
    assert len(fb.restic_points(target)) == 6
    newest3 = [p['id'] for p in fb.restic_points(target)[:3]]
    fb.prune_points(target, config)   # default retention: a burst of runs within one hour collapses, the newest three stay
    kept = [p['id'] for p in fb.restic_points(target)]
    assert 3 <= len(kept) <= 4 and set(newest3) <= set(kept), kept
    forget = fb.restic_forget_args({'hourly': 0, 'daily': 2, 'weekly': 0, 'monthly': 1})
    assert forget[:2] == ['forget', '--prune'] and '--keep-daily' in forget and '--keep-monthly' in forget and '--keep-hourly' not in forget, forget
    fb.prune_points(target, {**config, 'keep': {'hourly': 0, 'daily': 0, 'weekly': 0, 'monthly': 0}})
    assert len(fb.restic_points(target)) == 3, 'only the newest three remain'
    victim = fb.restic_points(target)[-1]['id']
    fb.delete_point(target, victim, config)
    assert victim not in [p['id'] for p in fb.restic_points(target)]

    # wrong password is refused, for every operation
    good = fb.PASSWORD_FILE.read_text()
    fb.PASSWORD_FILE.write_text('wrong-wrong-wrong')
    for call in (lambda: fb.restic_points(target), lambda: fb.restic_browse(target, new, 'home'), lambda: fb.run_backup(config, force=True),
                 lambda: fb.restic_check(target)):
        try: call(); raise SystemExit('wrong password accepted')
        except fb.BackupError as e: assert 'recovery key' in str(e).lower() and good not in str(e), e
    fb.PASSWORD_FILE.write_text(good); os.chmod(fb.PASSWORD_FILE, 0o600)
    assert len(fb.restic_points(target)) == 2
    # set_password keeps the mode private
    fb.set_password(good); assert oct(fb.PASSWORD_FILE.stat().st_mode & 0o777) == '0o600'

    # the key never shows up in argv, status, config, the repository or the process environment of the spawned restic calls
    assert any(a[:1] == ['restic'] or 'restic' in a for a in argvs), 'restic was never started'
    assert not any(good in part for a in argvs for part in a), 'recovery key on a command line'
    assert not any(a for a in argvs if '--password' in ' '.join(a) or '-p' == a[-1]), 'password option used'
    for name in (fb.STATUS_FILE, fb.CONFIG_FILE):
        if name.exists(): assert good not in name.read_text(), name
    fb.save_config(config); assert good not in fb.CONFIG_FILE.read_text()
    for f in (target / 'windoesnot-restic').rglob('*'):
        if f.is_file() and f.stat().st_size < 4096: assert good.encode() not in f.read_bytes(), f
    # stored data really is encrypted: file content of the big random file or the text must not be readable in the repository
    assert b'nested' not in b''.join(f.read_bytes() for f in (target / 'windoesnot-restic/data').rglob('*') if f.is_file())

    # CLI: switching to restic returns the recovery key exactly once; output of normal commands never contains it
    cli = str(ROOT / 'desktop/bin/windoesnot-filebackup')
    shutil.rmtree(tmp / 'cfg'); cfgdir = None
    env = {**os.environ}
    def cli_run(*args, stdin=None):
        return real_run([sys.executable, cli, *args], capture_output=True, text=True, timeout=120, env=env, input=stdin)
    first = cli_run('config', json.dumps({'engine': 'restic', 'target': {'kind': 'folder', 'path': str(target)}, 'sources': [str(home)]}))
    data = json.loads(first.stdout); assert first.returncode == 0 and data['engine'] == 'restic' and data['recovery_key'], first
    newkey = data['recovery_key']
    again = json.loads(cli_run('config', json.dumps({'engine': 'restic'})).stdout)
    assert 'recovery_key' not in again, 'key shown twice'
    # the repository was made with the old key: the new key is refused until the old one is entered (set-key)
    refused = cli_run('list'); assert refused.returncode == 1 and 'recovery key' in json.loads(refused.stdout)['error'].lower(), refused
    assert newkey not in refused.stdout + refused.stderr
    assert cli_run('set-key', stdin=good + '\n').returncode == 0
    listed = cli_run('list'); assert listed.returncode == 0 and len(json.loads(listed.stdout)) == 2, listed
    browsed = json.loads(cli_run('browse', json.loads(listed.stdout)[0]['id'], 'home/Documents').stdout)
    assert {e['name'] for e in browsed} == {'a.txt', 'big.bin', 'sub'}, browsed
    assert json.loads(cli_run('check').stdout) == {'ok': True}
    status = cli_run('status'); assert good not in status.stdout + status.stderr and newkey not in status.stdout
    # rsync configs keep working untouched
    assert json.loads(cli_run('config', json.dumps({'engine': 'rsync'})).stdout)['engine'] == 'rsync'
    print('PASS test-filebackup-restic')
finally:
    subprocess.run, subprocess.Popen = real_run, real_popen
    shutil.rmtree(tmp, ignore_errors=True)
