#!/usr/bin/env python3
"""Check the installed GRUB defaults without building an image."""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tree = ast.parse((root / 'tools/prepare-profile.py').read_text())
configs = [node.args[1].value for node in ast.walk(tree)
           if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
           and node.func.id == 'write' and len(node.args) >= 2
           and isinstance(node.args[0], ast.BinOp)
           and isinstance(node.args[0].right, ast.Constant)
           and node.args[0].right.value == 'etc/default/grub.d/90-windoesnot.cfg'
           and isinstance(node.args[1], ast.Constant)]
assert len(configs) == 1
lines = configs[0].splitlines()
assert 'GRUB_DISTRIBUTOR="WinDoesNot"' in lines
assert 'GRUB_DISABLE_OS_PROBER=false' in lines
assert not any(line.startswith('GRUB_DISABLE_RECOVERY=') for line in lines)
print('PASS: installed GRUB distributor is branded and other OS detection remains enabled')

# Exercise the entry filters in temporary directories; no host boot files are touched.
import importlib.util
import os
import tempfile
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('bootnames', root / 'iso/bootnames/bootnames.py')
bootnames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootnames)
with tempfile.TemporaryDirectory() as tmp:
    esp = Path(tmp)
    entries = esp / 'loader/entries'
    entries.mkdir(parents=True)
    (esp / 'vmlinuz-linux-cachyos-lts').touch()
    normal = entries / 'linux-cachyos-lts.conf'
    fallback = entries / 'linux-cachyos-lts-fallback.conf'
    foreign = entries / 'foreign.conf'
    normal.write_text('title Linux CachyOS Lts\nlinux /vmlinuz-linux-cachyos-lts\n')
    fallback.write_text('title old\nlinux /vmlinuz-linux-cachyos-lts\n')
    foreign.write_text('title Other OS\nlinux /vmlinuz-linux-cachyos-lts\n')
    bootnames.sdboot(esp)
    assert normal.read_text().startswith('title WinDoesNot (LTS)\n')
    assert fallback.read_text().startswith('title WinDoesNot (LTS) (Fallback)\n')
    assert foreign.read_text().startswith('title Other OS\n')
    counted = entries / 'abc-6.12.1-1-cachyos-lts+3-1.conf'
    counted.write_text('title CachyOS\nlinux /abc/kernel\n')
    other = entries / 'abc-6.12.1-1-cachyos-lts-extra.conf'
    other.write_text('title Other\n')
    with patch.dict(os.environ, {'KERNEL_INSTALL_ENTRY_TOKEN': 'abc'}):
        bootnames.kernel_install('6.12.1-1-cachyos-lts', str(esp / 'abc/6.12.1-1-cachyos-lts'))
    assert counted.read_text().startswith('title WinDoesNot (LTS)\n')
    assert other.read_text() == 'title Other\n'
assert 'REMOVE_EXISTING="no"' in (root / 'iso/installation.py').read_text()
print('PASS: systemd-boot entry filters and boot counting')
