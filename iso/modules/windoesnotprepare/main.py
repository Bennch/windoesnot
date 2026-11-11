# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate bootloader choices and install their exact target dependencies."""
import libcalamares
from pathlib import Path


def pretty_name():
    return 'Bootloader vorbereiten' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Prepare bootloader'


def run():
    bootloader = libcalamares.globalstorage.value('packagechooser_bootloader')
    firmware = libcalamares.globalstorage.value('firmwareType')
    mode = libcalamares.job.configuration.get('mode')
    if bootloader not in ('grub', 'refind', 'systemd-boot', 'limine') or firmware not in ('efi', 'bios') or mode not in ('offline', 'online'):
        return ('Invalid installation choices', 'Return to the bootloader page and select a supported option.')
    if firmware != 'efi' and bootloader in ('refind', 'systemd-boot'):
        return ('UEFI required', 'Choose GRUB or Limine for a BIOS installation.')
    if mode == 'online':
        # unpackfs contains a clean, empty resolver. networkcfg runs later; use
        # the live connection's resolver for this first target download too.
        value = libcalamares.globalstorage.value('rootMountPoint')
        if not isinstance(value, str) or not value:
            return ('Installation target is missing', 'No root mount point was provided.')
        target = Path(value).resolve()
        if target == Path('/') or not (target / 'etc/windoesnot-image-build').is_file():
            return ('Invalid installation target', 'Refusing to modify the live root.')
        resolver = target / 'etc/resolv.conf'
        contents = Path('/etc/resolv.conf').read_bytes()
        resolver.unlink(missing_ok=True)
        resolver.write_bytes(contents)
    command = ['/usr/bin/env', 'WINDOESNOT_INSTALL_TARGET=1', '/usr/bin/python3', '/usr/share/windoesnot/iso/installation.py', 'prepare', '--bootloader', bootloader, '--firmware', firmware, '--mode', mode]
    try:
        result = libcalamares.utils.target_env_call(command)
        if result:
            return ('Bootloader preparation failed', 'Required packages could not be installed. See the log; online mode requires access to the ISO snapshot packages.')
    except Exception as error:
        return ('Bootloader preparation failed', str(error))
    return None
