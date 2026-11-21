#!/usr/bin/env python3
"""The 'Belegung' column of This PC in Files: texts for fill, free space, unmounted disks and empty drives (no Nautilus needed)."""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('column', str(Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default/extras/nautilus/windoesnot-computer.py'))
col = importlib.util.module_from_spec(spec); spec.loader.exec_module(col)
GB = 1 << 30
ESP, RECOVERY, BASIC = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b', 'de94bba4-06d1-4d40-a16a-bfd50179d6ac', 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
lsblk = {'blockdevices': [
    {'type': 'disk', 'path': '/dev/nvme0n1', 'vendor': None, 'model': 'WD Blue SN580 2TB', 'rm': False, 'hotplug': False, 'tran': 'nvme', 'mountpoints': [None], 'children': [
        {'path': '/dev/nvme0n1p1', 'size': 2 * GB, 'fstype': 'vfat', 'parttype': ESP, 'mountpoints': ['/boot'], 'fsused': 100 << 20, 'fsavail': GB},
        {'path': '/dev/nvme0n1p2', 'size': 1900 * GB, 'fstype': 'btrfs', 'parttype': BASIC, 'mountpoints': ['/var/log', '/', '/home'], 'fsused': 1700 * GB, 'fsavail': 200 * GB}]},
    {'type': 'disk', 'path': '/dev/nvme1n1', 'vendor': None, 'model': 'Samsung SSD 980 PRO 1TB', 'mountpoints': [None], 'children': [
        {'path': '/dev/nvme1n1p2', 'size': 930 * GB, 'fstype': 'ntfs', 'parttype': BASIC, 'mountpoints': [None]},
        {'path': '/dev/nvme1n1p3', 'size': 1 * GB, 'fstype': 'ntfs', 'parttype': RECOVERY, 'mountpoints': [None]}]},
    {'type': 'disk', 'path': '/dev/sda', 'vendor': 'Generic ', 'model': 'USB3.2', 'rm': True, 'hotplug': True, 'tran': 'usb', 'mountpoints': [None], 'children': [
        {'path': '/dev/sda1', 'size': 58 * GB, 'fstype': 'exfat', 'mountpoints': ['/run/media/benni/STICK'], 'fsused': 55 * GB, 'fsavail': 3 * GB}]},
    {'type': 'rom', 'path': '/dev/sr0', 'vendor': 'ASUS    ', 'model': 'SDRW-08D2S-U', 'size': 1 << 30, 'fstype': None, 'mountpoints': []},
    {'type': 'disk', 'path': '/dev/zram0', 'vendor': None, 'model': None, 'fstype': 'swap', 'mountpoints': ['[SWAP]']},
]}
full = col.disks_from_lsblk(lsblk)
disks = {name: info['entry'] for name, info in full.items()}
assert set(disks) == {'WD Blue SN580 2TB', 'Samsung SSD 980 PRO 1TB', 'Generic USB3.2', 'ASUS SDRW-08D2S-U'}, sorted(disks)
assert disks['WD Blue SN580 2TB'] == ('usage', 1900 * GB, 200 * GB), 'the ESP is ignored, three mounts of one btrfs count once'
assert disks['Samsung SSD 980 PRO 1TB'] == ('unmounted', 930 * GB), 'the recovery partition is ignored'
assert disks['Generic USB3.2'] == ('usage', 58 * GB, 3 * GB) and disks['ASUS SDRW-08D2S-U'] == ('empty',)
assert col.text_for_disk(disks['WD Blue SN580 2TB'], True) == '█████████░  89 %  ·  200 GB frei von 1,9 TB'.replace('1,9 TB', col.human(1900 * GB).replace('.', ',')), col.text_for_disk(disks['WD Blue SN580 2TB'], True)
assert col.text_for_disk(disks['Generic USB3.2'], False) == '██████████  95 %  ·  3 GB free of 58 GB'
assert col.text_for_disk(disks['Samsung SSD 980 PRO 1TB'], True) == 'nicht eingehängt  ·  930 GB'
assert col.text_for_disk(disks['ASUS SDRW-08D2S-U'], True) == 'kein Medium' and col.text_for_disk(None, False) == 'no media'
assert col.usage_text(0, 0) == '' and col.usage_text(100, None) == ''
assert col.text_for('Whatever.drive', True, disks={}) == 'kein Medium' and col.text_for('x.link', True) == ''
# categories and the Windows order: system disk, local disks, removable disks, optical drives, network
assert {n: i['category'] for n, i in full.items()} == {'WD Blue SN580 2TB': 'internal', 'Samsung SSD 980 PRO 1TB': 'internal', 'Generic USB3.2': 'removable', 'ASUS SDRW-08D2S-U': 'optical'}
items = {n: col.item_info(n, True, full) for n in ('ASUS SDRW-08D2S-U.drive', 'Generic USB3.2.drive', 'Samsung SSD 980 PRO 1TB.drive', 'WD Blue SN580 2TB.drive', 'nas.mount')}
items['root.link'] = ('', *col.item_info('root.link', True, full)[1:])
ordered = sorted(items, key=lambda n: items[n][2])
assert ordered == ['root.link', 'Samsung SSD 980 PRO 1TB.drive', 'WD Blue SN580 2TB.drive', 'Generic USB3.2.drive', 'ASUS SDRW-08D2S-U.drive', 'nas.mount'], ordered
assert [items[n][1] for n in ordered] == ['Lokaler Datenträger', 'Lokaler Datenträger', 'Lokaler Datenträger', 'Wechseldatenträger', 'CD-/DVD-Laufwerk', 'Netzwerkadresse']
assert col.item_info('x.txt', True, full) == ('', '', '')
print('PASS: This PC usage column (fill bar, percent, free space, unmounted and empty drives, system partitions ignored)')
