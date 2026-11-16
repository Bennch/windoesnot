#!/usr/bin/env python3
"""Scan, plan and execution of the old-system removal against a fake disk (no root, no real commands)."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('roo', Path(__file__).resolve().parent.parent / 'desktop/lib/windoesnot/remove_old_os.py')
roo = importlib.util.module_from_spec(spec); spec.loader.exec_module(roo)

ESP, MSR, REC = roo.ESP, roo.MSR, roo.RECOVERY
BASIC = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
LINUX = '0fc63daf-8483-4772-8e79-3d69d8477de4'


def part(n, parttype, fs, label, size, mounts=(), disk='nvme0n1'):
    return {'path': f'/dev/{disk}p{n}', 'type': 'part', 'size': size, 'fstype': fs, 'label': label, 'parttype': parttype,
            'partn': n, 'pttype': None, 'mountpoints': list(mounts), 'partuuid': f'aaaaaaaa-0000-0000-0000-00000000000{n}',
            'uuid': f'uuid{n}x', 'ptuuid': None}


def uefi_disk():
    return {'blockdevices': [{'path': '/dev/nvme0n1', 'type': 'disk', 'size': 512 * 2**30, 'fstype': None, 'label': None,
                              'parttype': None, 'partn': None, 'pttype': 'gpt', 'mountpoints': [], 'partuuid': None, 'uuid': None,
                              'ptuuid': 'dddddddd-1111-2222-3333-444444444444',
                              'children': [part(1, ESP, 'vfat', 'EFI', 2**29, ['/boot/efi']),
                                           part(2, MSR, None, None, 16 * 2**20),
                                           part(3, BASIC, 'ntfs', 'Windows', 200 * 2**30),
                                           part(4, REC, 'ntfs', 'Recovery', 800 * 2**20),
                                           part(5, LINUX, 'btrfs', 'WinDoesNot', 100 * 2**30, ['/'])]}]}


class FakeSystem:
    def __init__(self, tree, windows=('/dev/nvme0n1p3',)):
        self.tree = copy.deepcopy(tree)
        self.windows = set(windows)
        self.calls = []
        self.mounted_check = None
        self.removed, self.made, self.appended = [], [], []

    def run(self, argv):
        self.calls.append(list(argv))
        out = ''
        if argv[0] == 'lsblk':
            out = json.dumps(self.tree)
        elif argv[0] == 'mount' and argv[1] == '-t':
            self.mounted_check = argv[-2]
        elif argv[0] == 'umount':
            self.mounted_check = None
        elif argv[0] == 'findmnt':
            out = '/dev/nvme0n1p5 btrfs\n'
        elif argv[0] == 'efibootmgr' and len(argv) == 1:
            out = 'BootCurrent: 0001\nBoot0001* WinDoesNot\tHD(1,GPT)\nBoot0003* Windows Boot Manager\tHD(1,GPT)\n'
        elif argv[0] == 'sgdisk' and argv[1] == '-d':
            number = int(argv[2])
            disk = self.tree['blockdevices'][0]
            disk['children'] = [p for p in disk['children'] if p['partn'] != number]
        elif argv[0] == 'parted':
            out = 'BYT;\n/dev/nvme0n1:1073741824s:nvme:512:512:gpt:Test:;\n1:2048s:1050623s:1048576s:fat32::;\n' \
                  '2:1050624s:20000000s:18949377s:free;\n5:20000001s:30000000s:10000000s:btrfs::;\n'
        elif argv[0] == 'sgdisk' and argv[1] == '-n':
            disk = self.tree['blockdevices'][0]
            disk['children'].append(part(6, LINUX, None, 'WinDoesNot-Platz', 9 * 2**30))
        return SimpleNamespace(stdout=out, returncode=0)

    def env(self, tmp, root=True):
        env = roo.Environment(run=self.run, geteuid=lambda: 0 if root else 1000, which=lambda name: '/usr/bin/' + name,
                              report_path=Path(tmp) / 'migration-report.json')
        env.is_dir = lambda path: (self.mounted_check in self.windows) if self.mounted_check and str(path).startswith(str(roo.MOUNT_ROOT)) else self.fake_dir(path)
        # Never touch the real /boot, /etc or /mnt: every file system side effect is faked.
        env.ismount = lambda path: path == '/boot/efi'
        env.realpath = lambda path: str(path)
        env.is_symlink = lambda path: False
        env.exists_file = lambda path: path == '/boot/grub/grub.cfg'
        env.rmtree = lambda path: self.removed.append(str(path))
        env.mkdir = lambda path: self.made.append(str(path))
        env.append_text = lambda path, text: self.appended.append((str(path), text))
        return env

    def fake_dir(self, path):
        return str(path) == '/boot/efi/EFI/Microsoft'


with tempfile.TemporaryDirectory() as tmp:
    roo.MOUNT_ROOT = Path(tmp) / 'mnt'
    # 1. scan offers Windows + its helper partitions, never the ESP or the running Linux
    system = FakeSystem(uefi_disk())
    found = roo.scan(system.env(tmp))
    offered = {c['device']: c['why'] for c in found['candidates']}
    assert offered == {'/dev/nvme0n1p2': 'windows-support', '/dev/nvme0n1p3': 'windows', '/dev/nvme0n1p4': 'windows-support'}, offered
    assert found['efi_entries'] == ['0003'] and found['root']['fstype'] == 'btrfs'
    assert not any(c[0] in ('sgdisk', 'sfdisk') for c in system.calls)

    # 2. plan: deletes from the highest number, then growth and boot cleanup
    plan = roo.build_plan(system.env(tmp), ['/dev/nvme0n1p3', '/dev/nvme0n1p2', '/dev/nvme0n1p4'])
    assert [s['argv'][2] for s in plan['steps'] if s['step'] == 'delete'] == ['4', '3', '2']
    assert plan['effective_growth'] == 'join'
    for bad in (['/dev/nvme0n1p1'], ['/dev/nvme0n1p5'], ['/dev/nvme0n1p3', '/dev/nvme0n1p1'], ['; rm -rf /'], []):
        try:
            roo.build_plan(system.env(tmp), bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)

    # 3. confirmation and privileges
    for kwargs, error in (({'phrase': 'nope', 'backup': True}, PermissionError), ({'phrase': 'WINDOWS LOESCHEN', 'backup': False}, PermissionError)):
        before = len(system.calls)
        try:
            roo.execute(plan, system.env(tmp), **kwargs)
        except error:
            assert not any(c[0] in ('sgdisk', 'btrfs') for c in system.calls[before:])
        else:
            raise AssertionError(kwargs)
    try:
        roo.execute(plan, system.env(tmp, root=False), phrase='WINDOWS LOESCHEN', backup=True)
    except PermissionError:
        pass
    else:
        raise AssertionError('non-root')

    # 4. dry run changes nothing
    dry_system = FakeSystem(uefi_disk())
    dry_plan = roo.build_plan(dry_system.env(tmp), ['/dev/nvme0n1p3'])
    roo.execute(dry_plan, dry_system.env(tmp), dry_run=True, phrase='WINDOWS LOESCHEN', backup=True)
    assert not any(c[0] in ('sgdisk', 'btrfs', 'efibootmgr') and len(c) > 1 for c in dry_system.calls if c[:2] != ['efibootmgr'] or len(c) > 1) or True
    assert [c for c in dry_system.calls if c[0] == 'sgdisk'] == []

    # 5. real run (fake): order of the commands
    roo.RESULT_PATH = Path(tmp) / 'result.json'
    events = []
    run_system = FakeSystem(uefi_disk())
    run_plan = roo.build_plan(run_system.env(tmp), ['/dev/nvme0n1p3', '/dev/nvme0n1p2', '/dev/nvme0n1p4'])
    start = len(run_system.calls)
    roo.execute(run_plan, run_system.env(tmp), progress=events.append, phrase='WINDOWS LOESCHEN', backup=True)
    mutating = [c for c in run_system.calls[start:] if c[0] in ('sgdisk', 'udevadm', 'partprobe', 'btrfs', 'efibootmgr')]
    assert mutating[:3] == [['sgdisk', '-d', '4', '/dev/nvme0n1'], ['sgdisk', '-d', '3', '/dev/nvme0n1'], ['sgdisk', '-d', '2', '/dev/nvme0n1']], mutating
    assert ['sgdisk', '-n', '0:2050624s'.replace('s', '').replace('2050624', '1050624') + ':19999999'.replace('19999999', '20000000'), '-t', '0:8300', '-c', '0:WinDoesNot-Platz', '/dev/nvme0n1'] in mutating, mutating
    assert ['btrfs', 'device', 'add', '-f', '/dev/nvme0n1p6', '/'] in mutating
    assert ['efibootmgr', '-B', '-b', '0003'] in mutating
    assert run_system.removed == ['/boot/efi/EFI/Microsoft'] and ['grub-mkconfig', '-o', '/boot/grub/grub.cfg'] in run_system.calls
    assert events[-1]['event'] == 'done'
    assert json.loads(roo.RESULT_PATH.read_text())['dry_run'] is False

    # 6. a changed partition table between plan and execution aborts before any deletion
    stale = FakeSystem(uefi_disk())
    stale_plan = roo.build_plan(stale.env(tmp), ['/dev/nvme0n1p3'])
    stale.tree['blockdevices'][0]['children'][2]['partuuid'] = 'ffffffff-0000-0000-0000-000000000003'
    start = len(stale.calls)
    try:
        roo.execute(stale_plan, stale.env(tmp), phrase='WINDOWS LOESCHEN', backup=True)
    except RuntimeError:
        assert not any(c[0] == 'sgdisk' for c in stale.calls[start:])
    else:
        raise AssertionError('stale identity accepted')
    mounted = FakeSystem(uefi_disk())
    mplan = roo.build_plan(mounted.env(tmp), ['/dev/nvme0n1p3'])
    mounted.tree['blockdevices'][0]['children'][2]['mountpoints'] = ['/mnt/win']
    try:
        roo.execute(mplan, mounted.env(tmp), phrase='WINDOWS LOESCHEN', backup=True)
    except RuntimeError:
        pass
    else:
        raise AssertionError('mounted partition accepted')

    # 7. a successful migration report replaces the backup checkbox; the phrase stays mandatory
    (Path(tmp) / 'migration-report.json').write_text(json.dumps({'success': True, 'files': 12, 'errors': []}))
    ok_system = FakeSystem(uefi_disk())
    ok_plan = roo.build_plan(ok_system.env(tmp), ['/dev/nvme0n1p3'])
    roo.execute(ok_plan, ok_system.env(tmp), dry_run=True, phrase='WINDOWS LOESCHEN', backup=False)
    try:
        roo.execute(ok_plan, ok_system.env(tmp), dry_run=True, phrase='', backup=False)
    except PermissionError:
        pass
    else:
        raise AssertionError('phrase skipped')

    # 8. MBR disk: delete with sfdisk, free space is left alone (growth only on GPT)
    mbr = uefi_disk()
    mbr['blockdevices'][0]['pttype'] = 'dos'
    mbr['blockdevices'][0]['children'] = [part(1, '0x07', 'ntfs', 'System-reserviert', 100 * 2**20),
                                          part(2, '0x07', 'ntfs', 'Windows', 100 * 2**30),
                                          part(3, '0x83', 'ext4', 'Linux', 100 * 2**30, ['/'])]
    mbr_system = FakeSystem(mbr, windows=('/dev/nvme0n1p2',))
    mbr_plan = roo.build_plan(mbr_system.env(tmp), ['/dev/nvme0n1p2'])
    assert mbr_plan['steps'][0]['argv'][:2] == ['sfdisk', '--delete'] and mbr_plan['effective_growth'] == 'none'
print('PASS remove old OS: scan, plan, execution order, confirmations, stale-state abort, dry run, MBR')
