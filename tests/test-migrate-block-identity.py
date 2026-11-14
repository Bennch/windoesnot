#!/usr/bin/env python3
"""Synthetic sysfs graphs; no real block devices are opened or modified."""
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('block_identity', ROOT / 'iso/modules/windoesnotmigrate_guard/block_identity.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / 'sys'
    (root / 'dev/block').mkdir(parents=True)
    devices = {}

    def node(name, identity, parent=None, *, virtual=False, partition=False):
        if parent is None:
            base = root / ('devices/virtual/block' if virtual else 'devices/pci/block')
            path = base / name
        else:
            path = parent / name
        path.mkdir(parents=True)
        (path / 'dev').write_text(identity)
        if partition:
            (path / 'partition').write_text('1')
        else:
            (path / 'slaves').mkdir()
            (path / 'queue').mkdir()
        (root / 'dev/block' / identity).symlink_to(path)
        major, minor = (int(n) for n in identity.split(':'))
        devices['/dev/' + name] = SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=os.makedev(major, minor))
        return path

    def fake_stat(name):
        if name not in devices:
            raise FileNotFoundError(name)
        return devices[name]

    def backs(name):
        return m.backing_disks(name, sysfs_root=root, stat_device=fake_stat)

    def separate(source, *targets):
        return m.disjoint_backing(source, targets, sysfs_root=root, stat_device=fake_stat)

    def unknown(action):
        try:
            action()
        except m.UnknownBlockIdentity:
            return
        raise AssertionError('Unknown ancestry was accepted')

    a = node('sda', '8:0')
    a1 = node('sda1', '8:1', a, partition=True)
    b = node('sdb', '8:16')
    b1 = node('sdb1', '8:17', b, partition=True)
    assert backs('/dev/sda1') == {'8:0'}
    assert separate('/dev/sda1', '/dev/sdb1')
    assert not separate('/dev/sda1', '/dev/sda')
    assert not separate('/dev/sda1', '/dev/sdb', '/dev/sda1')

    mapper = node('dm-0', '253:0', virtual=True)
    (mapper / 'slaves' / 'sda1').symlink_to(a1)
    assert backs('/dev/dm-0') == {'8:0'}
    assert not separate('/dev/dm-0', '/dev/sda')
    raid = node('md0', '9:0', virtual=True)
    (raid / 'slaves' / 'dm-0').symlink_to(mapper)
    (raid / 'slaves' / 'sdb1').symlink_to(b1)
    assert backs('/dev/md0') == {'8:0', '8:16'}
    assert not separate('/dev/md0', '/dev/sdb')

    loop = node('loop0', '7:0', virtual=True)
    unknown(lambda: backs('/dev/loop0'))
    unknown(lambda: separate('/dev/sda1'))
    unknown(lambda: separate('/dev/sda1', '/dev/not-present'))
    devices['/dev/file'] = SimpleNamespace(st_mode=stat.S_IFREG, st_rdev=0)
    unknown(lambda: backs('/dev/file'))
    (mapper / 'slaves' / 'sda1').unlink()
    (mapper / 'slaves' / 'cycle').symlink_to(raid)
    unknown(lambda: backs('/dev/md0'))
    (mapper / 'slaves' / 'cycle').unlink()
    (mapper / 'slaves' / 'outside').symlink_to(Path(tmp))
    unknown(lambda: backs('/dev/dm-0'))
    (a / 'dev').write_text('8:99')
    unknown(lambda: backs('/dev/sda1'))

print('PASS synthetic block ancestry')
