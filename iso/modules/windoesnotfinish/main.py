# SPDX-License-Identifier: GPL-3.0-or-later
"""Finish bootloader maintenance and snapshots after the selected apps."""
import libcalamares


def pretty_name():
    return 'Startsystem und Backups einrichten' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Configure boot maintenance and backups'


def run():
    bootloader = libcalamares.globalstorage.value('packagechooser_bootloader')
    firmware = libcalamares.globalstorage.value('firmwareType')
    mode = libcalamares.job.configuration.get('mode')
    if bootloader not in ('grub', 'refind', 'systemd-boot', 'limine') or firmware not in ('efi', 'bios') or mode not in ('online', 'offline'):
        return ('Invalid installation choices', 'The selected bootloader or installation mode is missing.')
    command = ['/usr/bin/env', 'WINDOESNOT_INSTALL_TARGET=1', '/usr/bin/python3', '/usr/share/windoesnot/iso/installation.py', 'finish', '--bootloader', bootloader, '--firmware', firmware, '--mode', mode]
    try:
        if libcalamares.utils.target_env_call(command):
            return ('Boot maintenance or backups failed', 'See the installation log for details.')
        if libcalamares.utils.target_env_call(['/usr/bin/rm', '-f', '/etc/windoesnot-image-build']):
            return ('Live marker cleanup failed', 'See the installation log for details.')
    except Exception as error:
        return ('Installation finalization failed', str(error))
    return None
