#!/usr/bin/env python3
"""Restore points are found on a Btrfs top level; foreign systems and odd values are rejected."""
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'desktop/lib/windoesnot/recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)

def snapshot(top, number, os_release, kernel=True, config='@/.snapshots'):
    entry = top / config / str(number)
    (entry / 'snapshot/etc').mkdir(parents=True)
    (entry / 'snapshot/etc/os-release').write_text(os_release)
    (entry / 'info.xml').write_text(f'<snapshot><type>single</type><num>{number}</num><date>2026-11-2{number} 10:00:00</date><description>test {number}</description></snapshot>')
    if kernel:
        (entry / 'snapshot/boot').mkdir()
        (entry / 'snapshot/boot/vmlinuz-linux-cachyos').touch()
        (entry / 'snapshot/boot/initramfs-linux-cachyos.img').touch()

with tempfile.TemporaryDirectory(prefix='wdn-recovery-test-') as temporary:
    top = Path(temporary)
    snapshot(top, 1, 'NAME="WinDoesNot"\nPRETTY_NAME="WinDoesNot"\n')
    snapshot(top, 2, 'NAME="WinDoesNot"\nPRETTY_NAME="WinDoesNot"\n', kernel=False)
    snapshot(top, 3, 'NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04"\n')
    found = recovery.find_snapshots(top, '/dev/sda2', 'ABCD-1234')
    assert [s['number'] for s in found] == [1, 2], found
    assert found[0]['subvolume'] == '@/.snapshots/1/snapshot' and found[0]['kernel'] == 'linux-cachyos'
    assert found[1]['kernel'] == '' and found[0]['description'] == 'test 1'
    assert recovery.command_line('ab12-CD', '@/.snapshots/1/snapshot') == 'root=UUID=ab12-CD rootflags=subvol=@/.snapshots/1/snapshot ro quiet splash'
    for uuid, subvolume in (('x y', '@/a'), ('ab12', '@/a b'), ('ab12', '@/a,rw'), ('ab12', '@/a;rm')):
        try: recovery.command_line(uuid, subvolume)
        except ValueError: pass
        else: raise AssertionError((uuid, subvolume))
    try: recovery.boot('/dev/sda2', '@/x', 'evil')
    except ValueError: pass
    else: raise AssertionError('unknown kernel accepted')
# ESP kernels (systemd-boot / Limine). A fake bzImage carries only the header fields kernel_release() reads.
def bzimage(path, release):
    data = bytearray(0x400)
    data[0x202:0x206] = b'HdrS'
    data[0x20e:0x210] = (0x100).to_bytes(2, 'little')
    text = f'{release} (builder@host) #1 SMP'.encode() + b'\0'
    data[0x300:0x300 + len(text)] = text
    path.write_bytes(bytes(data))

def modules(top, number, release, config='@/.snapshots'):
    (top / config / str(number) / 'snapshot/usr/lib/modules' / release).mkdir(parents=True)

with tempfile.TemporaryDirectory(prefix='wdn-recovery-test-') as temporary:
    temporary = Path(temporary)
    bzimage(temporary / 'k', '6.12.5-2-cachyos')
    assert recovery.kernel_release(temporary / 'k') == '6.12.5-2-cachyos'
    (temporary / 'junk').write_bytes(b'x' * 2000)
    assert recovery.kernel_release(temporary / 'junk') == '' and recovery.kernel_release(temporary / 'missing') == ''
    sd = importlib.util.spec_from_file_location('sdboot_snapshots', ROOT / 'desktop/lib/windoesnot/sdboot_snapshots.py')
    helper = importlib.util.module_from_spec(sd); sd.loader.exec_module(helper)
    assert helper.kernel_release(temporary / 'k') == '6.12.5-2-cachyos'

    top, esp = temporary / 'top', temporary / 'esp'
    top.mkdir()
    plain_os = 'NAME="WinDoesNot"\nPRETTY_NAME="WinDoesNot"\n'
    for number, release in ((1, '6.12.5-2-cachyos'), (2, '6.12.4-1-cachyos'), (3, '6.12.5-2-cachyos'), (4, '6.12.5-2-cachyos')):
        snapshot(top, number, plain_os, kernel=False)
        modules(top, number, release)
    snapshot(top, 5, plain_os, kernel=True)   # GRUB style: the kernel inside the snapshot wins over the ESP
    esp.mkdir()
    bzimage(esp / 'vmlinuz-linux-cachyos', '6.12.5-2-cachyos')
    (esp / 'initramfs-linux-cachyos.img').write_bytes(b'initrd')
    # 3 has a restore-point copy of its own (sdboot_snapshots.py layout), 4 has a limine.conf entry.
    (esp / 'windoesnot-restore/6.12.5-2-cachyos-aaaa').mkdir(parents=True)
    bzimage(esp / 'windoesnot-restore/6.12.5-2-cachyos-aaaa/vmlinuz', '6.12.5-2-cachyos')
    (esp / 'windoesnot-restore/6.12.5-2-cachyos-aaaa/initramfs.img').write_bytes(b'x')
    (esp / 'loader/entries').mkdir(parents=True)
    (esp / 'loader/entries/windoesnot-restore-3.conf').write_text(
        'title WinDoesNot restore point 2026-11-23 10:00\nlinux /windoesnot-restore/6.12.5-2-cachyos-aaaa/vmlinuz\n'
        'initrd /windoesnot-restore/6.12.5-2-cachyos-aaaa/initramfs.img\noptions root=UUID=ABCD rootflags=subvol=@/.snapshots/3/snapshot ro quiet\n')
    (esp / 'lim').mkdir()
    bzimage(esp / 'lim/k4', '6.12.5-2-cachyos')
    (esp / 'lim/initramfs-4.img').write_bytes(b'x')
    (esp / 'limine.conf').write_text(
        'timeout: 5\n\n/+WinDoesNot\n//Snapshots\n/Snapshot 4\n    protocol: linux\n    comment: snapshot 4\n'
        '    kernel_path: boot():/lim/k4\n    module_path: boot():/lim/initramfs-4.img\n'
        '    cmdline: quiet root=UUID=ABCD rootflags=subvol=/@/.snapshots/4/snapshot ro\n')
    found = {s['number']: s for s in recovery.find_snapshots(top, '/dev/sda2', 'ABCD', [('/dev/sda1', esp)])}
    assert found[5]['source'] == 'snapshot' and found[5]['kernel'] == 'linux-cachyos' and found[5]['esp'] == ''
    assert found[3]['source'] == 'esp-restore' and found[3]['kernel'] == 'linux-cachyos' and found[3]['note'] == ''
    assert found[3]['esp'] == '/dev/sda1' and found[3]['kernel_file'].endswith('aaaa/vmlinuz'), found[3]
    assert found[4]['source'] == 'esp-limine' and found[4]['kernel_file'] == 'lim/k4' and found[4]['initrd_file'] == 'lim/initramfs-4.img', found[4]
    assert found[1]['source'] == 'esp-current' and found[1]['note'] == 'current-kernel' and found[1]['kernel'] == 'linux-cachyos'
    assert found[2]['kernel'] == '' and found[2]['reason'] == 'kernel-version-mismatch' and found[2]['source'] == ''
    assert recovery.status_text(found[1]).strip() == '(uses the current kernel, modules may differ)'
    assert 'cannot start' in recovery.status_text(found[2]) and recovery.status_text(found[5]) == ''
    # A restore-point copy of another version than the snapshot's modules is never used.
    bzimage(esp / 'windoesnot-restore/6.12.5-2-cachyos-aaaa/vmlinuz', '6.11.0-1-cachyos')
    again = {s['number']: s for s in recovery.find_snapshots(top, '/dev/sda2', 'ABCD', [('/dev/sda1', esp)])}
    assert again[3]['source'] == 'esp-current' and again[3]['note'] == 'current-kernel'
    # No ESP on the disk: unchanged behaviour (kernel '' when the snapshot has none).
    bare = {s['number']: s for s in recovery.find_snapshots(top, '/dev/sda2', 'ABCD')}
    assert bare[1]['kernel'] == '' and bare[1]['reason'] == 'no-kernel' and bare[5]['kernel'] == 'linux-cachyos'
    # An entry whose kernel path escapes the ESP is ignored.
    assert recovery.below(esp, '../top') is None

    # lsblk: the ESP is taken from the same disk only, and must be vfat with the ESP partition type.
    lsblk = {'blockdevices': [
        {'path': '/dev/sda', 'type': 'disk', 'fstype': None, 'uuid': None, 'parttype': None, 'children': [
            {'path': '/dev/sda1', 'type': 'part', 'fstype': 'vfat', 'uuid': 'E1', 'parttype': 'C12A7328-F81F-11D2-BA4B-00A0C93EC93B'},
            {'path': '/dev/sda2', 'type': 'part', 'fstype': 'btrfs', 'uuid': 'B1', 'parttype': '0fc63daf-8483-4772-8e79-3d69d8477de4'}]},
        {'path': '/dev/sdb', 'type': 'disk', 'fstype': None, 'uuid': None, 'parttype': None, 'children': [
            {'path': '/dev/sdb1', 'type': 'part', 'fstype': 'vfat', 'uuid': 'E2', 'parttype': 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'},
            {'path': '/dev/sdb2', 'type': 'part', 'fstype': 'btrfs', 'uuid': 'B2', 'parttype': None}]}]}
    devices = {d['path']: d['esps'] for d in recovery.parse_block_devices(lsblk)}
    assert devices == {'/dev/sda2': ['/dev/sda1'], '/dev/sdb2': []}, devices
print('PASS: restore points found, foreign systems skipped, kernel command line validated, ESP kernels matched by version')
