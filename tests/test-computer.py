#!/usr/bin/env python3
"""This PC (windoesnot-computer): which drives are shown, categories, fill percentages, hidden system partitions, network drives, texts."""
import importlib.machinery, importlib.util
from pathlib import Path
loader = importlib.machinery.SourceFileLoader('computer', str(Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-computer'))
spec = importlib.util.spec_from_loader('computer', loader); pc = importlib.util.module_from_spec(spec); loader.exec_module(pc)
ESP, RECOVERY, BASIC = pc.ESP, 'de94bba4-06d1-4d40-a16a-bfd50179d6ac', 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
GB = 1 << 30
lsblk = {'blockdevices': [
    {'name': 'nvme0n1', 'path': '/dev/nvme0n1', 'type': 'disk', 'size': 2000 * GB, 'fstype': None, 'rm': False, 'hotplug': False, 'tran': 'nvme', 'model': 'WD Blue SN580 2TB', 'vendor': None, 'mountpoints': [None], 'children': [
        {'name': 'nvme0n1p1', 'path': '/dev/nvme0n1p1', 'type': 'part', 'size': 2 * GB, 'fstype': 'vfat', 'parttype': ESP, 'mountpoints': ['/boot'], 'fsused': 100 << 20, 'fsavail': GB},
        {'name': 'nvme0n1p2', 'path': '/dev/nvme0n1p2', 'type': 'part', 'size': 1900 * GB, 'fstype': 'btrfs', 'label': 'root', 'parttype': BASIC, 'mountpoints': ['/var/log', '/', '/home'], 'fsused': 1700 * GB, 'fsavail': 200 * GB}]},
    {'name': 'nvme1n1', 'path': '/dev/nvme1n1', 'type': 'disk', 'size': 1000 * GB, 'fstype': None, 'rm': False, 'hotplug': False, 'tran': 'nvme', 'model': 'Samsung SSD 980 PRO 1TB', 'vendor': None, 'mountpoints': [None], 'children': [
        {'name': 'nvme1n1p2', 'path': '/dev/nvme1n1p2', 'type': 'part', 'size': 930 * GB, 'fstype': 'ntfs', 'label': 'Platte', 'parttype': BASIC, 'mountpoints': [None], 'fsused': None, 'fsavail': None},
        {'name': 'nvme1n1p3', 'path': '/dev/nvme1n1p3', 'type': 'part', 'size': 1 * GB, 'fstype': 'ntfs', 'label': None, 'parttype': RECOVERY, 'mountpoints': [None]}]},
    {'name': 'sda', 'path': '/dev/sda', 'type': 'disk', 'size': 58 * GB, 'fstype': None, 'rm': True, 'hotplug': True, 'tran': 'usb', 'model': 'USB3.2', 'vendor': 'Generic ', 'mountpoints': [None], 'children': [
        {'name': 'sda1', 'path': '/dev/sda1', 'type': 'part', 'size': 58 * GB, 'fstype': 'exfat', 'label': 'STICK', 'mountpoints': ['/run/media/benni/STICK'], 'fsused': 55 * GB, 'fsavail': 3 * GB}]},
    {'name': 'sr0', 'path': '/dev/sr0', 'type': 'rom', 'size': 4 * GB, 'fstype': 'iso9660', 'label': 'DISC', 'rm': True, 'hotplug': True, 'tran': 'usb', 'model': 'SDRW-08D2S-U', 'mountpoints': ['/run/media/benni/DISC'], 'fsused': 4 * GB, 'fsavail': 0},
    {'name': 'loop0', 'path': '/dev/loop0', 'type': 'loop', 'size': GB, 'fstype': 'squashfs', 'mountpoints': ['/run/archiso/airootfs']},
    {'name': 'zram0', 'path': '/dev/zram0', 'type': 'disk', 'size': 30 * GB, 'fstype': 'swap', 'mountpoints': ['[SWAP]']},
    {'name': 'sdb', 'path': '/dev/sdb', 'type': 'disk', 'size': 8 * GB, 'fstype': 'iso9660', 'rm': True, 'hotplug': True, 'tran': 'usb', 'model': 'Live', 'mountpoints': ['/run/archiso/bootmnt']},
]}
drives = pc.drives_from_lsblk(lsblk)
by_path = {d['path']: d for d in drives}
assert set(by_path) == {'/dev/nvme0n1p2', '/dev/nvme1n1p2', '/dev/sda1', '/dev/sr0'}, sorted(by_path)   # no ESP, recovery, loop, swap, live medium
root = by_path['/dev/nvme0n1p2']
assert root['category'] == 'internal' and root['mount'] == '/' and root['percent'] == 89 and root['mounted'] and not root['ejectable']
assert by_path['/dev/nvme1n1p2']['mounted'] is False and by_path['/dev/nvme1n1p2']['percent'] is None
stick = by_path['/dev/sda1']
assert stick['category'] == 'removable' and stick['ejectable'] and stick['percent'] == 95 and stick['disk'] == '/dev/sda' and stick['model'] == 'Generic USB3.2'
assert by_path['/dev/sr0']['category'] == 'optical'
assert [d['category'] for d in drives] == ['internal', 'internal', 'removable', 'optical'], 'internal first, then removable, then optical'
pc.GERMAN = True
assert pc.title_of(root) == 'Linux-System' and pc.title_of(stick) == 'STICK' and pc.title_of(by_path['/dev/nvme1n1p2']) == 'Platte'
assert pc.space_text(root) == '200 GB frei von 1.8 TB'.replace('1.8 TB', pc.human(1900 * GB)), pc.space_text(root)
assert 'nicht eingehängt' in pc.space_text(by_path['/dev/nvme1n1p2'])
pc.GERMAN = False
assert pc.space_text(stick) == '3 GB free of 58 GB'
findmnt = {'filesystems': [
    {'target': '/mnt/nas', 'source': '//nas/media', 'fstype': 'cifs', 'size': str(4000 * GB), 'avail': str(1000 * GB), 'used': str(3000 * GB)},
    {'target': '/mnt/x', 'source': '/dev/x', 'fstype': 'ext4', 'size': '1', 'avail': '1', 'used': '0'}]}
network = pc.network_from_findmnt(findmnt)
assert len(network) == 1 and network[0]['category'] == 'network' and network[0]['percent'] == 75 and network[0]['label'] == 'nas' and network[0]['mount'] == '/mnt/nas'
assert pc.human(None) == '' and pc.human(512) == '512 B'
print('PASS: This PC lists internal, removable, optical and network drives with fill percentages and hides system partitions')
