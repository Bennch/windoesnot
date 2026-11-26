#!/usr/bin/env python3
"""The live boot menus get one extra entry that opens the restore point list."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from live_boot_menu import RECOVERY_PARAMETER, efi_recovery, grub_recovery, syslinux_recovery

grub = ("menuentry \"WinDoesNot (live, offline install)\" --class arch --id 'windoesnot-offline' {\n"
        "    linux /arch/boot/x86_64/vmlinuz-linux-cachyos archisobasedir=arch quiet windoesnot.install=offline\n    initrd /arch/boot/initramfs\n}\n\n"
        "menuentry \"WinDoesNot (live, online install)\" --class arch --id 'windoesnot-online' {\n    linux /x windoesnot.install=online\n}\n")
result = grub_recovery(grub, 'de')
assert result.count(RECOVERY_PARAMETER) == 1 and 'windoesnot.install=offline' in result
entry = result[result.index("--id 'windoesnot-recovery'"):]
assert 'windoesnot.install' not in entry.split('}')[0] and result.count('menuentry') == 3
bios = ("LABEL wdn-offline\nMENU LABEL WinDoesNot (offline install)\nMENU DEFAULT\nLINUX /boot/vmlinuz\nAPPEND archisobasedir=arch windoesnot.install=offline\n"
        "LABEL wdn-online\nMENU LABEL WinDoesNot (online install)\nAPPEND x windoesnot.install=online\n")
result = syslinux_recovery(bios, 'en')
block = result[result.index('LABEL wdn-recovery'):result.index('LABEL wdn-online')]
assert RECOVERY_PARAMETER in block and 'MENU DEFAULT' not in block and 'windoesnot.install' not in block and 'Start restore points from disk' in block
assert result.count('MENU DEFAULT') == 1
with tempfile.TemporaryDirectory() as directory:
    (Path(directory) / '01-live.conf').write_text('title WinDoesNot\nsort-key 01\nlinux /vmlinuz\noptions archisobasedir=arch\n')
    target = efi_recovery(directory, 'en')
    text = target.read_text()
    assert RECOVERY_PARAMETER in text and 'sort-key' not in text and 'title Start restore points from disk' in text
    assert efi_recovery(Path(directory) / 'none', 'en') is None
for broken in (grub_recovery, syslinux_recovery):
    try: broken('nothing', 'en')
    except ValueError: pass
    else: raise AssertionError('layout change not detected')
print('PASS: GRUB, BIOS and UEFI boot menus get a restore point entry')
