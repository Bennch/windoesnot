#!/usr/bin/env python3
"""Synthetic-only checks for the unfinished, read-only removal groundwork."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parent.parent / 'desktop/lib/windoesnot/remove_old_os.py'
spec = importlib.util.spec_from_file_location('remove_old_os', path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def part(n, fs='', label='', ptype='', mounts=None):
    return {'path': '/dev/sda' + str(n), 'type': 'part', 'fstype': fs, 'label': label,
            'parttype': ptype, 'size': 1024, 'mountpoints': mounts or []}
tree = {'blockdevices': [{'path': '/dev/sda', 'type': 'disk', 'mountpoints': [], 'children': [
    part(1, 'vfat', ptype=m.ESP, mounts=['/boot']), part(2, ptype=m.MSR),
    part(3, 'ntfs', 'Windows'), part(4, ptype=m.RECOVERY), part(5, 'btrfs', mounts=['/']),
    part(6, 'ntfs', 'Data')]}]}
items = m.inventory(tree, ['/dev/sda3'])
assert items[0]['protected'] and items[4]['protected']
assert items[2]['role'] == 'windows' and items[5]['role'] == 'other'
assert not any(x['automatic'] for x in items)
for ptype in (m.ESP, '0xef', 'ef'):
    efi = {'blockdevices': [{'path': '/dev/sda', 'type': 'disk', 'mountpoints': [],
                              'children': [part(1, 'vfat', ptype=ptype)]}]}
    assert m.inventory(efi)[0]['protected']
nested = part(1, 'ntfs')
nested['children'] = [dict(part(2, 'ntfs', mounts=['/mnt/data']))]
assert m.inventory({'blockdevices': [{'path': '/dev/sda', 'type': 'disk',
                                      'mountpoints': [], 'children': [nested]}]})[0]['protected']
bios = {'blockdevices': [{'path': '/dev/sdb', 'type': 'disk', 'mountpoints': [], 'children': [
    dict(part(1, 'ntfs', 'System Reserved'), path='/dev/sdb1'),
    dict(part(2, 'ntfs', 'Windows'), path='/dev/sdb2'),
    dict(part(3, 'ext4', mounts=['/']), path='/dev/sdb3')]}]}
bios_items = m.inventory(bios, ['/dev/sdb2'])
assert bios_items[0]['role'] == 'possible-windows-support' and bios_items[2]['protected']
assert m.confirmed(True, 'WINDOWS LOESCHEN') and m.confirmed(True, 'DELETE WINDOWS', 'en')
assert not m.confirmed(False, 'WINDOWS LOESCHEN') and not m.confirmed(True, 'wrong')
for name in ['/dev/sda;reboot', '/dev/mapper/root', '/dev/sda1\n', '/dev/../sda']:
    assert not m.valid_device(name)
print('PASS conservative removal inventory')

# Preview derives targets solely from verified, unmounted Windows partitions.
disk = tree['blockdevices'][0]
disk['pttype'] = 'gpt'
for number, node in enumerate(disk['children'], 1):
    node['partn'] = number
assert m.deletion_preview(tree, ['/dev/sda3']) == [
    ['sgdisk', '-d', '3', '/dev/sda'], ['udevadm', 'settle']]
disk['pttype'] = 'dos'
assert m.deletion_preview(tree, ['/dev/sda3']) == [
    ['sfdisk', '--delete', '/dev/sda', '3'], ['udevadm', 'settle']]
assert m.deletion_preview(tree, ['/dev/sda5']) == []
disk['children'][2]['partn'] = None
try:
    m.deletion_preview(tree, ['/dev/sda3'])
    raise AssertionError('missing partition number accepted')
except ValueError:
    pass

# Exercise the runner with a fake subprocess; never execute a disk command.
calls = []
def fake_run(argv, **kwargs):
    calls.append((argv, kwargs))
    return 'ok'
m.subprocess.run = fake_run
assert m.command_runner(['sgdisk', '-d', '3', '/dev/sda']) == 'ok'
assert calls == [(['sgdisk', '-d', '3', '/dev/sda'],
                  {'check': True, 'text': True, 'capture_output': True, 'timeout': 900})]
print('PASS deletion preview and fake runner')

assert m.windows_boot_entries('Boot0001* Windows Boot Manager\tHD(1,GPT,...)\n'
                              'Boot0002* Windows Boot Manager Backup\tHD(...)\n'
                              'Boot000a Windows Boot Manager\tHD(...)\n') == ['0001', '000A']
try:
    m.windows_boot_entries('Boot0001* Windows Boot Manager\tHD(...)\n'
                           'Boot0001* Windows Boot Manager\tHD(...)\n')
    raise AssertionError('duplicate EFI entry accepted')
except ValueError:
    pass
print('PASS exact EFI label parsing')

disk['ptuuid'] = '12345678-ABCD'
disk['children'][2].update(partuuid='ABCD-1234', uuid='CDEF-5678')
stable = m.persistent_identity(disk, disk['children'][2])
assert m.match_persistent_identity(tree, stable) == '/dev/sda3'
disk['children'][2]['path'] = '/dev/sda7'
assert m.match_persistent_identity(tree, stable) == '/dev/sda7'
disk['children'][2]['uuid'] = 'different-uuid'
try:
    m.match_persistent_identity(tree, stable)
    raise AssertionError('changed filesystem identity accepted')
except ValueError:
    pass
disk['children'][2]['uuid'] = 'CDEF-5678'
disk['children'].append(dict(disk['children'][2], path='/dev/sda8'))
try:
    m.match_persistent_identity(tree, stable)
    raise AssertionError('duplicate identity accepted')
except ValueError:
    pass
print('PASS persistent identity matching')
