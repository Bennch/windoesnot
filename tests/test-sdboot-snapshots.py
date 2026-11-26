#!/usr/bin/env python3
"""systemd-boot restore points: at most 3 entries, kernel copied per snapshot, stale ones removed, no root needed."""
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('sdboot_snapshots', ROOT / 'desktop/lib/windoesnot/sdboot_snapshots.py')
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)
rspec = importlib.util.spec_from_file_location('recovery', ROOT / 'desktop/lib/windoesnot/recovery.py')
recovery = importlib.util.module_from_spec(rspec)
rspec.loader.exec_module(recovery)


def bzimage(path, release, pad=0):
    data = bytearray(0x400 + pad)
    data[0x202:0x206] = b'HdrS'
    data[0x20e:0x210] = (0x100).to_bytes(2, 'little')
    text = f'{release} (builder@host) #1 SMP'.encode() + b'\0'
    data[0x300:0x300 + len(text)] = text
    path.write_bytes(bytes(data))


def snapshot(snapshots, number, release, date='2026-11-2%d 10:00:00'):
    entry = snapshots / str(number)
    (entry / 'snapshot/usr/lib/modules' / release).mkdir(parents=True)
    (entry / 'info.xml').write_text(f'<snapshot><type>single</type><num>{number}</num><date>{date % (number % 10)}</date></snapshot>')


def esp_kernel(esp, release, initrd=b'initrd'):
    esp.mkdir(parents=True, exist_ok=True)
    bzimage(esp / 'vmlinuz-linux-cachyos', release)
    (esp / 'initramfs-linux-cachyos.img').write_bytes(initrd)


with tempfile.TemporaryDirectory(prefix='wdn-sdboot-test-') as temporary:
    temporary = Path(temporary)
    esp, snapshots = temporary / 'esp', temporary / 'snapshots'
    snapshots.mkdir()
    (esp / 'loader/entries').mkdir(parents=True)
    (esp / 'loader/entries/linux-cachyos.conf').write_text('title x\nlinux /vmlinuz-linux-cachyos\ninitrd /initramfs-linux-cachyos.img\noptions root=UUID=OLD rw rootflags=subvol=@ quiet splash\n')
    (esp / 'loader/entries/linux-cachyos-fallback.conf').write_text('options root=UUID=OLD debug\n')
    base = sd.base_options(esp)
    assert base == 'root=UUID=OLD rw rootflags=subvol=@ quiet splash', base
    assert sd.entry_options(base, 'ab12-CD', '@/.snapshots/7/snapshot') == 'root=UUID=ab12-CD rootflags=subvol=@/.snapshots/7/snapshot ro quiet splash'
    for uuid, sub in (('x y', '@/a'), ('ab', '@/a b'), ('ab', '@/a,rw'), ('ab', '@/a;rm')):
        try: sd.entry_options(base, uuid, sub)
        except ValueError: pass
        else: raise AssertionError((uuid, sub))

    # Transaction 1: snapshots 1 (pre) and 2 (post) share the kernel; copies are shared.
    esp_kernel(esp, '6.12.4-1-cachyos')
    snapshot(snapshots, 1, '6.12.4-1-cachyos')
    result = sd.sync(esp, snapshots, 'ABCD-1', '/@', base)
    assert result['added'] == [1] and not result['removed'], result
    snapshot(snapshots, 2, '6.12.4-1-cachyos')
    result = sd.sync(esp, snapshots, 'ABCD-1', '/@', base)
    assert result['added'] == [2], result
    stores = sorted(p.name for p in (esp / 'windoesnot-restore').iterdir())
    assert len(stores) == 1 and stores[0].startswith('6.12.4-1-cachyos-'), stores
    entry = (esp / 'loader/entries/windoesnot-restore-2.conf').read_text()
    assert entry.startswith('title WinDoesNot restore point 2026-12 10:00'.replace('2026-12', '2026-11-22')), entry
    assert f'linux /windoesnot-restore/{stores[0]}/vmlinuz\n' in entry and f'initrd /windoesnot-restore/{stores[0]}/initramfs.img\n' in entry
    assert 'options root=UUID=ABCD-1 rootflags=subvol=@/.snapshots/2/snapshot ro quiet splash\n' in entry, entry
    assert sd.sync(esp, snapshots, 'ABCD-1', '/@', base) == {'added': [], 'removed': [], 'skipped': []}

    # Kernel update: the ESP now holds 6.12.5, snapshot 3 (post) is made for it; the new initramfs gives a new copy.
    esp_kernel(esp, '6.12.5-2-cachyos', b'new initrd')
    snapshot(snapshots, 3, '6.12.5-2-cachyos')
    assert sd.sync(esp, snapshots, 'ABCD-1', '/@', base)['added'] == [3]
    # A snapshot whose kernel is already gone from the ESP (old release, no copy made) gets no entry.
    snapshot(snapshots, 4, '6.12.4-1-cachyos')
    result = sd.sync(esp, snapshots, 'ABCD-1', '/@', base)
    assert result['added'] == [] and not (esp / 'loader/entries/windoesnot-restore-4.conf').exists(), result
    # Snapshot 5 is fine; 3 entries is the limit, the oldest (1) goes together with nothing else it shares.
    snapshot(snapshots, 5, '6.12.5-2-cachyos')
    result = sd.sync(esp, snapshots, 'ABCD-1', '/@', base)
    entries = sorted(p.name for p in (esp / 'loader/entries').glob('windoesnot-restore-*.conf'))
    assert entries == ['windoesnot-restore-2.conf', 'windoesnot-restore-3.conf', 'windoesnot-restore-5.conf'], entries
    assert result['added'] == [5] and 'windoesnot-restore-1.conf' in result['removed'], result
    # Regular entries and kernels are never touched.
    assert (esp / 'loader/entries/linux-cachyos.conf').is_file() and (esp / 'vmlinuz-linux-cachyos').is_file()
    # Snapshot 2 is deleted by Snapper: its entry and the (now unused) 6.12.4 copy disappear; 3 and 5 share one copy.
    import shutil
    shutil.rmtree(snapshots / '2')
    result = sd.sync(esp, snapshots, 'ABCD-1', '/@', base)
    assert 'windoesnot-restore-2.conf' in result['removed'], result
    assert [p.name for p in (esp / 'windoesnot-restore').iterdir() if p.name.startswith('6.12.4')] == []
    assert len(list((esp / 'windoesnot-restore').iterdir())) == 1
    # recovery.py reads exactly these entries (restore point layout contract).
    found = recovery.bls_restore_entries(esp)
    assert sorted(found) == ['@/.snapshots/3/snapshot', '@/.snapshots/5/snapshot'], found
    top = temporary / 'top'
    for number in (3, 5):
        (top / '@/.snapshots' / str(number) / 'snapshot/etc').mkdir(parents=True)
        (top / '@/.snapshots' / str(number) / 'snapshot/usr/lib/modules/6.12.5-2-cachyos').mkdir(parents=True)
        (top / '@/.snapshots' / str(number) / 'snapshot/etc/os-release').write_text('PRETTY_NAME="WinDoesNot"\n')
        (top / '@/.snapshots' / str(number) / 'info.xml').write_text('<snapshot><date>2026-11-25 10:00:00</date></snapshot>')
    seen = recovery.find_snapshots(top, '/dev/sda2', 'ABCD-1', [('/dev/sda1', esp)])
    assert [(s['number'], s['source'], s['note']) for s in seen] == [(3, 'esp-restore', ''), (5, 'esp-restore', '')], seen

    # Too little room on the ESP: no copy, no entry, no exception.
    full = temporary / 'esp2'
    (full / 'loader/entries').mkdir(parents=True)
    esp_kernel(full, '6.12.5-2-cachyos')
    real = sd.shutil.disk_usage
    sd.shutil.disk_usage = lambda path: type('U', (), {'free': 1024})()
    try:
        result = sd.sync(full, snapshots, 'ABCD-1', '/@', base)
    finally:
        sd.shutil.disk_usage = real
    assert result['added'] == [] and result['skipped'] == [5, 3], result
    assert not list((full / 'loader/entries').glob('windoesnot-restore-*'))

# Wiring: installation enables it for systemd-boot only; hooks and units exist and call the helper.
source = (ROOT / 'iso/installation.py').read_text()
assert "elif bootloader == 'systemd-boot':" in source and 'sdboot-snapshots.conf' in source
for name in ('06-windoesnot-sdboot-snapshots.hook', 'zz-windoesnot-sdboot-snapshots.hook'):
    text = (ROOT / 'desktop/share/libalpm/hooks' / name).read_text()
    assert 'sdboot_snapshots.py sync' in text and 'AbortOnFail' not in text
assert 'PreTransaction' in (ROOT / 'desktop/share/libalpm/hooks/06-windoesnot-sdboot-snapshots.hook').read_text()
assert 'PathModified=/.snapshots' in (ROOT / 'desktop/share/systemd/system/windoesnot-sdboot-snapshots.path').read_text()
pkgbuild = (ROOT / 'packaging/PKGBUILD.in').read_text()
for name in ('sdboot_snapshots.py', '06-windoesnot-sdboot-snapshots.hook', 'zz-windoesnot-sdboot-snapshots.hook', 'windoesnot-sdboot-snapshots.path', 'windoesnot-sdboot-snapshots.service'):
    assert name in pkgbuild, name
print('PASS: systemd-boot restore points: max 3, per-snapshot kernel copies shared, stale cleaned, ESP-full safe')
