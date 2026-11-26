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
print('PASS: restore points found, foreign systems skipped, kernel command line validated')
