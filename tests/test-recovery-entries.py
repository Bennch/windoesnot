#!/usr/bin/env python3
"""Branded recovery entries for all four bootloaders: golden outputs, languages, idempotency, skips. No root needed."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'iso'))
import recovery_entries as r

EN, DE = 'WinDoesNot Recovery', 'WinDoesNot Wiederherstellung'
assert r.title(r.language('de_DE.UTF-8')) == DE and r.title(r.language('en_US.UTF-8')) == EN
assert r.title(r.language(None)) == EN and r.title(r.language('')) == EN

assert r.sdboot_entry(DE) == ('title WinDoesNot Wiederherstellung\nsort-key windoesnot-z-recovery\n'
                              'efi /EFI/Linux/cachyos-recovery.efi\n')
grub = r.grub_script(EN, 'ABCD-1234')
assert "menuentry 'WinDoesNot Recovery' --class windoesnot --class recovery --id windoesnot-recovery {" in grub
assert 'search --no-floppy --fs-uuid --set=root ABCD-1234\n    chainloader /EFI/Linux/cachyos-recovery.efi\n' in grub
assert grub.startswith('#!/bin/sh\n') and 'CachyOS' not in grub.replace('cachyos-recovery', '')
for bad in ('', None, 'a b', 'x;rm'):
    try:
        r.grub_script(EN, bad)
        raise AssertionError('accepted ' + repr(bad))
    except ValueError:
        pass
assert r.refind_stanza(DE, '1234-ab') == (
    '# Written by WinDoesNot; rEFInd would otherwise list the CachyOS-named image a second time.\n'
    'dont_scan_files +,cachyos-recovery.efi\n'
    'menuentry "WinDoesNot Wiederherstellung" {\n'
    '    icon /EFI/refind/themes/windoesnot/icons/os_linux.png\n    volume 1234-ab\n'
    '    loader /EFI/Linux/cachyos-recovery.efi\n}\n')
assert 'volume' not in r.refind_stanza(EN, None) and 'volume' not in r.refind_stanza(EN, 'x;y')

# Limine: rename the tool's entry, add ours when absent, never duplicate.
tool = 'timeout: 5\n/+WinDoesNot\n    comment: x\n\n/CachyOS Recovery\n    protocol: efi\n    path: boot():/EFI/Linux/cachyos-recovery.efi\n'
renamed = r.limine_apply(tool, DE)
assert '/WinDoesNot Wiederherstellung\n' in renamed and 'CachyOS Recovery' not in renamed
assert renamed.count('cachyos-recovery.efi') == 1 and r.limine_apply(renamed, DE) == renamed
added = r.limine_apply('timeout: 5\n/+WinDoesNot\n', EN)
assert added.endswith('/WinDoesNot Recovery\n    protocol: efi\n    path: boot():/EFI/Linux/cachyos-recovery.efi\n')
assert r.limine_apply(added, EN) == added
assert r.limine_apply(added, DE).count('cachyos-recovery.efi') == 1  # language change renames, no duplicate

def ids():
    return 'ABCD-1234', 'ab12-34'

def tree(directory, image=True):
    root = Path(directory)
    if image:
        (root / r.IMAGE).parent.mkdir(parents=True)
        (root / r.IMAGE).touch()
    (root / 'boot/EFI/refind').mkdir(parents=True)
    (root / 'boot/EFI/refind/refind.conf').write_text('timeout 20\n')
    (root / 'boot/limine.conf').write_text('timeout: 5\n/+WinDoesNot\n')
    return root

with tempfile.TemporaryDirectory(prefix='wdn-recovery-entries-') as tmp:
    root = tree(tmp)
    sd = r.configure('systemd-boot', 'efi', root, 'de_DE.UTF-8', ids)
    assert sd == [str(root / 'boot/loader/entries/cachyos-recovery.efi.conf')]
    assert (root / 'boot/loader/entries/cachyos-recovery.efi.conf').read_text() == r.sdboot_entry(DE)
    assert r.configure('systemd-boot', 'efi', root, 'de_DE.UTF-8', ids) == []  # idempotent
    assert len(r.configure('systemd-boot', 'efi', root, 'en_US.UTF-8', ids)) == 1  # language change rewrites
    assert r.configure('grub', 'efi', root, 'de_DE.UTF-8', ids) == [str(root / r.GRUB_SCRIPT)]
    assert (root / r.GRUB_SCRIPT).stat().st_mode & 0o111 and r.configure('grub', 'efi', root, 'de_DE.UTF-8', ids) == []
    assert len(r.configure('limine', 'efi', root, 'en_US.UTF-8', ids)) == 1
    assert r.configure('limine', 'efi', root, 'en_US.UTF-8', ids) == []
    assert len(r.configure('refind', 'efi', root, 'de_DE.UTF-8', ids)) == 2
    assert r.configure('refind', 'efi', root, 'de_DE.UTF-8', ids) == []
    main = (root / 'boot/EFI/refind/refind.conf').read_text()
    assert main.count('include windoesnot-recovery.conf') == 1
    assert 'volume ab12-34' in (root / 'boot/EFI/refind' / r.REFIND_FILE).read_text()
    # Failures never raise: unknown ESP UUID, unreadable config.
    (root / r.GRUB_SCRIPT).unlink()
    assert r.configure('grub', 'efi', root, None, lambda: (None, None)) == []
    (root / 'boot/limine.conf').unlink()
    assert r.configure('limine', 'efi', root, None, ids) == []

with tempfile.TemporaryDirectory(prefix='wdn-recovery-entries-') as tmp:
    root = tree(tmp, image=False)
    for loader in ('systemd-boot', 'grub', 'limine', 'refind'):
        assert r.configure(loader, 'efi', root, 'de', ids) == []  # image missing
    assert not (root / 'boot/loader').exists() and not (root / r.GRUB_SCRIPT).exists()
with tempfile.TemporaryDirectory(prefix='wdn-recovery-entries-') as tmp:
    root = tree(tmp)
    for loader in ('systemd-boot', 'grub', 'limine', 'refind'):
        assert r.configure(loader, 'bios', root, 'de', ids) == []  # BIOS skipped
    assert not (root / 'boot/loader').exists() and 'WinDoesNot Recovery' not in (root / 'boot/limine.conf').read_text()

# esp_ids: bounded subprocess, tolerant of empty output.
with patch.object(r.subprocess, 'run') as run:
    run.return_value.stdout = 'ABCD-1234 ab12-34\n'
    assert r.esp_ids() == ('ABCD-1234', 'ab12-34') and run.call_args.kwargs['timeout'] == 30
    run.return_value.stdout = ''
    assert r.esp_ids() == (None, None)
print('PASS: recovery entries are branded, idempotent and UEFI-only in systemd-boot, GRUB, Limine and rEFInd')
