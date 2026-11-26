#!/usr/bin/env python3
"""Boot menu entries for the recovery image (UEFI), branded for WinDoesNot, in all four bootloaders.

CachyOS ships the recovery image as a unified kernel image, <ESP>/EFI/Linux/cachyos-recovery.efi, whose own
name is CachyOS-branded and which we cannot rebuild. Every function here is pure (inputs -> file contents);
`configure()` is the only one that touches files, and it never raises: an entry is an extra and must never abort an
installation. Nothing happens on BIOS or when the image is missing.

Assumptions about each loader (not verified on real hardware):
  systemd-boot  auto-discovers the UKI with the id 'cachyos-recovery.efi'. A type 1 entry file named
                cachyos-recovery.efi.conf has the same id (file name minus '.conf'), so it replaces the discovered one.
  GRUB          chainloads the UKI; the firmware then finds the root.addon.efi in cachyos-recovery.efi.extra.d itself.
  Limine        limine-entry-tool adds its own entry; we only rename it (or add one when none exists).
  rEFInd        a manual stanza; the stanza's volume defaults to the ESP that holds refind.conf.
"""
from pathlib import Path
import re
import subprocess
import sys

UKI = '/EFI/Linux/cachyos-recovery.efi'
IMAGE = 'usr/lib/cachyos-recovery/cachyos-recovery.efi'
TITLES = {'en': 'WinDoesNot Recovery', 'de': 'WinDoesNot Wiederherstellung'}
SDBOOT_ENTRY = 'cachyos-recovery.efi.conf'
GRUB_SCRIPT = 'etc/grub.d/45_windoesnot_recovery'
REFIND_FILE = 'windoesnot-recovery.conf'
REFIND_ICON = '/EFI/refind/themes/windoesnot/icons/os_linux.png'


def language(locale):
    """'de_DE.UTF-8' -> 'de'; anything else -> 'en'."""
    return 'de' if str(locale or '').lower().startswith('de') else 'en'


def title(lang):
    return TITLES.get(lang, TITLES['en'])


def sdboot_entry(name):
    return 'title ' + name + '\nsort-key windoesnot-z-recovery\nefi ' + UKI + '\n'


def grub_script(name, esp_uuid):
    """/etc/grub.d drop-in. Emits the entry only while the image exists on a mounted ESP (self-healing)."""
    if not re.fullmatch(r'[0-9A-Za-z-]+', esp_uuid or ''):
        raise ValueError('Invalid ESP UUID')
    quoted = "'" + name.replace("'", "'\\''") + "'"
    return ('#!/bin/sh\n# WinDoesNot: recovery image on the EFI system partition. Written by installation.py.\n'
            'for d in /boot /efi /boot/efi; do\n'
            '    if [ -f "$d' + UKI + '" ]; then found=1; break; fi\n'
            'done\n'
            '[ -n "$found" ] || exit 0\n'
            "cat <<'EOF'\n"
            'menuentry ' + quoted + ' --class windoesnot --class recovery --id windoesnot-recovery {\n'
            '    insmod part_gpt\n    insmod fat\n    insmod chain\n'
            '    search --no-floppy --fs-uuid --set=root ' + esp_uuid + '\n'
            '    chainloader ' + UKI + '\n'
            '}\nEOF\n')


def refind_stanza(name, partuuid=None):
    volume = '    volume ' + partuuid + '\n' if partuuid and re.fullmatch(r'[0-9A-Fa-f-]+', partuuid) else ''
    return ('# Written by WinDoesNot; rEFInd would otherwise list the CachyOS-named image a second time.\n'
            'dont_scan_files +,cachyos-recovery.efi\n'
            'menuentry "' + name + '" {\n'
            '    icon ' + REFIND_ICON + '\n' + volume +
            '    loader ' + UKI + '\n}\n')


def limine_entry(name):
    return '/' + name + '\n    protocol: efi\n    path: boot():' + UKI + '\n'


def limine_apply(text, name):
    """Rename the CachyOS-branded recovery entry; add ours when limine-entry-tool left none. Idempotent."""
    lines = text.split('\n')
    found = False
    for index, line in enumerate(lines):
        heading = re.match(r'^(/+)[ \t]*(.*)$', line)
        if heading and re.search(r'recovery', heading[2], re.I) and re.search(r'cachyos|windoesnot', heading[2], re.I):
            lines[index] = heading[1] + name
            found = True
        elif line.startswith('comment:') and re.search(r'cachyos recovery', line, re.I):
            lines[index] = re.sub(r'(?i)cachyos recovery', name, line)
    result = '\n'.join(lines)
    # An entry the tool wrote with an unexpected heading is left alone: a duplicate would be worse.
    if not found and 'cachyos-recovery.efi' not in result:
        result = result.rstrip('\n') + '\n\n' + limine_entry(name)
    return result if result.endswith('\n') else result + '\n'


def write_if_changed(path, text, mode=0o644):
    path = Path(path)
    if path.is_file() and path.read_text() == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return True


def esp_ids(target='/boot'):
    out = subprocess.run(['findmnt', '-n', '-o', 'UUID,PARTUUID', '--target', target], capture_output=True,
                         text=True, timeout=30, check=False).stdout.split()
    return (out[0] if out else None), (out[1] if len(out) > 1 else None)


def configure(bootloader, firmware, root=Path('/'), locale=None, ids=esp_ids):
    """Returns the changed paths (strings); [] when nothing applies or anything failed."""
    root = Path(root)
    if firmware != 'efi' or not (root / IMAGE).is_file():
        return []
    name = title(language(locale))
    changed = []
    try:
        if bootloader == 'systemd-boot':
            path = root / 'boot/loader/entries' / SDBOOT_ENTRY
            if write_if_changed(path, sdboot_entry(name)):
                changed.append(str(path))
        elif bootloader == 'grub':
            uuid = ids()[0]
            if not uuid:
                raise RuntimeError('ESP UUID unknown')
            path = root / GRUB_SCRIPT
            if write_if_changed(path, grub_script(name, uuid), 0o755):
                changed.append(str(path))
        elif bootloader == 'limine':
            path = root / 'boot/limine.conf'
            text = path.read_text()
            result = limine_apply(text, name)
            if result != text:
                path.write_text(result)
                changed.append(str(path))
        elif bootloader == 'refind':
            directory = root / 'boot/EFI/refind'
            path = directory / REFIND_FILE
            if write_if_changed(path, refind_stanza(name, ids()[1])):
                changed.append(str(path))
            main = directory / 'refind.conf'
            text = main.read_text()
            if not re.search(r'(?m)^\s*include\s+' + re.escape(REFIND_FILE) + r'\s*$', text):
                main.write_text(text.rstrip() + '\ninclude ' + REFIND_FILE + '\n')
                changed.append(str(main))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Recovery boot entry not configured:', error, file=sys.stderr)
        return []
    return changed
