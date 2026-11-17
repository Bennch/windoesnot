#!/usr/bin/env python3
"""Calamares' versioned kernel-install boot entries must not survive next to sdboot-manage's entries."""
import importlib.util
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('installation', root / 'iso/installation.py')
installation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installation)

MID = '7d80e40fe41b41f9aa240501304ad110'


def make(base, generic=True, files=True):
    (base / 'etc').mkdir()
    (base / 'etc/machine-id').write_text(MID + '\n')
    entries = base / 'boot/loader/entries'
    entries.mkdir(parents=True)
    for version in ('7.3.3-1-cachyos', '6.18.60-2-cachyos-lts'):
        (entries / f'{MID}-{version}.conf').write_text(f'title x\nlinux /{MID}/{version}/linux\ninitrd /{MID}/{version}/initrd\n')
        (base / 'boot' / MID / version).mkdir(parents=True)
        (base / 'boot' / MID / version / 'linux').write_text('k')
    (entries / 'other-os.conf').write_text('title other\nlinux /other/linux\n')
    if generic:
        (entries / 'linux-cachyos.conf').write_text('title WinDoesNot\nlinux /vmlinuz-linux-cachyos\ninitrd /initramfs-linux-cachyos.img\n')
        if files:
            (base / 'boot/vmlinuz-linux-cachyos').write_text('k')
            (base / 'boot/initramfs-linux-cachyos.img').write_text('i')


with tempfile.TemporaryDirectory() as d:
    base = Path(d)
    make(base)
    removed = installation.remove_versioned_boot_entries(base)
    names = sorted(p.name for p in (base / 'boot/loader/entries').iterdir())
    assert names == ['linux-cachyos.conf', 'other-os.conf'], names
    assert not (base / 'boot' / MID).exists()
    assert len(removed) == 3, removed
    assert installation.remove_versioned_boot_entries(base) == []  # idempotent

for kwargs in ({'generic': False}, {'files': False}):
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        make(base, **kwargs)
        assert installation.remove_versioned_boot_entries(base) == [], kwargs
        assert (base / 'boot' / MID).is_dir() and len(list((base / 'boot/loader/entries').glob(MID + '-*.conf'))) == 2, kwargs

with tempfile.TemporaryDirectory() as d:  # no valid machine id: nothing is touched
    base = Path(d)
    make(base)
    (base / 'etc/machine-id').write_text('../../..\n')
    assert installation.remove_versioned_boot_entries(base) == []
    assert (base / 'boot' / MID).is_dir()
print('PASS boot entry cleanup')
