#!/usr/bin/env python3
"""Permanent rollback from the live session: planning is pure and tested on fixtures, commands are mocked."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'desktop/lib/windoesnot/recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)

STAMP = '20261126-101500'


def refused(function, *args):
    try:
        function(*args)
    except ValueError:
        return True
    raise AssertionError(('accepted', function.__name__, args))


# subvolume argument
assert recovery.parse_subvolume('@/.snapshots/12/snapshot') == ('@', 12)
assert recovery.parse_subvolume('@root-1/.snapshots/3/snapshot') == ('@root-1', 3)
for bad in ('', '@/.snapshots/0/snapshot', '@/.snapshots/01/snapshot', '../.snapshots/1/snapshot', '@/x/.snapshots/1/snapshot',
            '.snapshots/1/snapshot', '@/.snapshots/1/snapshot/x', '@ /.snapshots/1/snapshot', '@/.snapshots/1;rm/snapshot', None):
    refused(recovery.parse_subvolume, bad)

# plan from a listing
entries = {'@', '@/.snapshots', '@home'}
steps = recovery.plan_rollback(entries, '@', 7, STAMP)
assert steps == [('rename', '@', f'@-before-restore-{STAMP}'),
                 ('snapshot', f'@-before-restore-{STAMP}/.snapshots/7/snapshot', '@'),
                 ('rmdir', '@/.snapshots', ''),
                 ('rename', f'@-before-restore-{STAMP}/.snapshots', '@/.snapshots')], steps
assert not any(kind == 'delete' for kind, *_ in steps)
refused(recovery.plan_rollback, {'@'}, '@', 7, STAMP)                       # no .snapshots
refused(recovery.plan_rollback, entries | {f'@-before-restore-{STAMP}'}, '@', 7, STAMP)
refused(recovery.plan_rollback, entries, '@', 7, 'now')
refused(recovery.plan_rollback, entries, '../x', 7, STAMP)

# undo plan: newest backup wins, points go back with it
after = {'@', '@/.snapshots', '@-before-restore-20261101-000000', f'@-before-restore-{STAMP}'}
undo = recovery.plan_undo(after, '@', '20261127-000000')
assert undo == [('rename', '@', '@-undone-20261127-000000'), ('rmdir', f'@-before-restore-{STAMP}/.snapshots', ''),
                ('rename', '@-undone-20261127-000000/.snapshots', f'@-before-restore-{STAMP}/.snapshots'),
                ('rename', f'@-before-restore-{STAMP}', '@')], undo
refused(recovery.plan_undo, {'@', '@/.snapshots'}, '@', STAMP)

# default subvolume, fstab, nested subvolumes
assert recovery.parse_default('ID 5 (FS_TREE)\n') == (5, None)
assert recovery.parse_default('ID 256 gen 9 top level 5 path @\n') == (256, '@')
assert recovery.default_action((5, None), '@') is None and recovery.default_action((256, '@'), '@') == 'set'
refused(recovery.default_action, (300, '@other'), '@')
refused(recovery.parse_default, 'garbage')
assert recovery.parse_subvolume_id('Name: @\n\tSubvolume ID: \t\t258\n\tGeneration: 3\n'.replace('\t\t', ' ')) == 258

good = 'UUID=a / btrfs rw,noatime,subvol=/@ 0 0\nUUID=a /home btrfs rw,subvol=/@home 0 0\nUUID=b /boot/efi vfat umask=0077 0 2\n'
assert recovery.fstab_problems(good, '@', lambda n: n in ('@home',)) == []
assert recovery.fstab_problems(good, '@', lambda n: False)                     # @home missing
assert recovery.fstab_problems(good.replace('subvol=/@ ', 'subvolid=256 '), '@', lambda n: True)
assert recovery.fstab_problems(good.replace('subvol=/@ ', 'subvol=/@old '), '@', lambda n: True)
assert recovery.fstab_problems('UUID=b /boot/efi vfat defaults 0 2\n', '@', lambda n: True)
assert recovery.fstab_problems(good.replace('/@home', '/@home # note'), '@', lambda n: True) == []

listing_ok = 'ID 258 gen 5 top level 256 path @/.snapshots\nID 300 gen 5 top level 258 path @/.snapshots/1/snapshot\n'
assert recovery.nested_problems(listing_ok, '@') == []
assert recovery.nested_problems(listing_ok + 'ID 301 gen 5 top level 256 path @/var/lib/machines\n', '@') == ['@/var/lib/machines']

# apply_steps on a real directory tree: rename + stubbed btrfs snapshot, and revert on failure
def tree(base):
    for path in ('@/.snapshots/7/snapshot/etc', '@/etc', '@home'):
        (base / path).mkdir(parents=True)
    (base / '@/.snapshots/7/snapshot/etc/marker').write_text('snap')
    (base / '@/etc/marker').write_text('old')

calls = []
def fake_snapshot(args, timeout=120):
    calls.append([str(a) for a in args])
    if args[1:3] == ['subvolume', 'snapshot']:
        src, dst = Path(args[3]), Path(args[4])
        dst.mkdir()
        (dst / '.snapshots').mkdir()           # the empty stub
        (dst / 'etc').mkdir()
        (dst / 'etc/marker').write_text((src / 'etc/marker').read_text())
    return ''

with tempfile.TemporaryDirectory(prefix='wdn-rollback-test-') as temporary:
    top = Path(temporary)
    tree(top)
    recovery.apply_steps(top, steps, fake_snapshot)
    backup = top / f'@-before-restore-{STAMP}'
    assert (top / '@/etc/marker').read_text() == 'snap'
    assert (backup / 'etc/marker').read_text() == 'old', 'old root must survive intact'
    assert (top / '@/.snapshots/7/snapshot/etc/marker').is_file(), 'snapshots moved to the new root'
    assert not (backup / '.snapshots').exists()
    assert calls == [['btrfs', 'subvolume', 'snapshot', str(backup / '.snapshots/7/snapshot'), str(top / '@')]], calls
    # undo restores the original layout
    recovery.apply_steps(top, recovery.plan_undo(recovery.listing(top), '@', '20261127-000000'), fake_snapshot)
    assert (top / '@/etc/marker').read_text() == 'old' and (top / '@/.snapshots/7/snapshot/etc/marker').is_file()
    assert (top / '@-undone-20261127-000000/etc/marker').read_text() == 'snap'

with tempfile.TemporaryDirectory(prefix='wdn-rollback-test-') as temporary:
    top = Path(temporary)
    tree(top)
    def failing(args, timeout=120):
        if args[1:3] == ['subvolume', 'snapshot']:
            raise subprocess.CalledProcessError(1, args)
        return ''
    try: recovery.apply_steps(top, steps, failing)
    except subprocess.CalledProcessError: pass
    else: raise AssertionError('failure swallowed')
    assert (top / '@/etc/marker').read_text() == 'old' and not list(top.glob('@-before*')), 'rename not reverted'

# full flow with mocked commands: refusals happen before anything changes
with tempfile.TemporaryDirectory(prefix='wdn-rollback-test-') as temporary:
    top = Path(temporary)
    tree(top)
    (top / '@/.snapshots/7/info.xml').write_text('<snapshot><type>single</type><num>7</num><date>2026-11-20 10:00:00</date></snapshot>')
    (top / '@/.snapshots/7/snapshot/etc/os-release').write_text('PRETTY_NAME="WinDoesNot"\n')
    (top / '@/.snapshots/7/snapshot/etc/fstab').write_text(good)
    (top / '@/.snapshots/7/snapshot/boot').mkdir()
    (top / '@/.snapshots/7/snapshot/boot/vmlinuz-linux-cachyos').touch()
    (top / '@/.snapshots/7/snapshot/boot/initramfs-linux-cachyos.img').touch()
    state = {'list': listing_ok, 'default': 'ID 5 (FS_TREE)\n'}
    seen = []
    def fake_run(args, timeout=120):
        args = [str(a) for a in args]
        seen.append(args)
        assert isinstance(timeout, int) and timeout > 0
        if args[:3] == ['btrfs', 'subvolume', 'list']: return state['list']
        if args[:3] == ['btrfs', 'subvolume', 'get-default']: return state['default']
        if args[:3] == ['btrfs', 'subvolume', 'show']: return 'Subvolume ID: 400\n'
        return fake_snapshot(args, timeout)
    recovery.run = fake_run
    original_rename = recovery.os.rename
    renames = []
    # nested subvolume: refused, nothing renamed
    state['list'] = listing_ok + 'ID 9 gen 1 top level 256 path @/srv\n'
    (top / '@home').rmdir(); (top / '@home').mkdir()
    refused(recovery._rollback_mounted, top, '/dev/x', '@', 7, STAMP)
    assert not list(top.glob('@-before*'))
    state['list'] = listing_ok
    # fstab uses subvolid: refused
    (top / '@/.snapshots/7/snapshot/etc/fstab').write_text(good.replace('subvol=/@ ', 'subvolid=256 '))
    refused(recovery._rollback_mounted, top, '/dev/x', '@', 7, STAMP)
    (top / '@/.snapshots/7/snapshot/etc/fstab').write_text(good)
    # unexpected default subvolume: refused
    state['default'] = 'ID 300 gen 1 top level 5 path @other\n'
    refused(recovery._rollback_mounted, top, '/dev/x', '@', 7, STAMP)
    # default pointing at the root: switched to the new one
    state['default'] = 'ID 256 gen 1 top level 5 path @\n'
    report = recovery._rollback_mounted(top, '/dev/x', '@', 7, STAMP)
    assert any(a[:3] == ['btrfs', 'subvolume', 'set-default'] and a[3] == '400' for a in seen), seen
    assert (top / '@/etc/marker').read_text() == 'snap' and (top / f'@-before-restore-{STAMP}/etc/marker').read_text() == 'old'
    assert '"restored_point": 7' in (top / '@/var/lib/windoesnot/last-restore.json').read_text()
    assert len(report) == 3 and STAMP in report[1]
    assert all(a[0] in ('btrfs', 'sync') for a in seen)

# a kernel that is not in the point (ESP kernels) is refused
with tempfile.TemporaryDirectory(prefix='wdn-rollback-test-') as temporary:
    top = Path(temporary)
    tree(top)
    (top / '@/.snapshots/7/info.xml').write_text('<snapshot><type>single</type><num>7</num></snapshot>')
    (top / '@/.snapshots/7/snapshot/etc/os-release').write_text('PRETTY_NAME="WinDoesNot"\n')
    refused(recovery._rollback_mounted, top, '/dev/x', '@', 7, STAMP)

# bad devices never reach a mount
for bad in ('sda', '/dev/../etc/passwd', '/dev/sda; rm', ''):
    refused(recovery.check_device, bad)

print('PASS: rollback plan, refusals, undo and revert on failure')
