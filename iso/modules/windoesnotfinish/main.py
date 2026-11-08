# SPDX-License-Identifier: GPL-3.0-or-later
"""Finish bootloader maintenance and snapshots after the selected apps."""
import libcalamares
import re


def pretty_name():
    return 'Startsystem und Backups einrichten' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Configure boot maintenance and backups'


def run():
    bootloader = libcalamares.globalstorage.value('packagechooser_bootloader')
    firmware = libcalamares.globalstorage.value('firmwareType')
    mode = libcalamares.job.configuration.get('mode')
    if bootloader not in ('grub', 'refind', 'systemd-boot', 'limine') or firmware not in ('efi', 'bios') or mode not in ('online', 'offline'):
        return ('Invalid installation choices', 'The selected bootloader or installation mode is missing.')
    command = ['/usr/bin/env', 'WINDOESNOT_INSTALL_TARGET=1', '/usr/bin/python3', '/usr/share/windoesnot/iso/installation.py', 'finish', '--bootloader', bootloader, '--firmware', firmware, '--mode', mode]
    selected_locale = str(libcalamares.globalstorage.value('locale') or '')
    if re.fullmatch(r'[A-Za-z]{2,3}_[A-Za-z]{2}(?:\.UTF-8)?', selected_locale):
        command += ['--locale', selected_locale if selected_locale.endswith('.UTF-8') else selected_locale + '.UTF-8']
    try:
        # The native users job has already created the account. Keep its default
        # unless the user explicitly selected another installed shell.
        shell = libcalamares.globalstorage.value('windoesnotUserShell')
        if shell:
            username = libcalamares.globalstorage.value('username')
            if shell not in ('/usr/bin/bash', '/usr/bin/fish', '/usr/bin/zsh') or not isinstance(username, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}\$?', username):
                return ('Invalid shell selection', 'Return to the Programs page and select a supported shell.')
            if libcalamares.utils.target_env_call(['/usr/bin/test', '-x', shell]) or libcalamares.utils.target_env_call(['/usr/bin/usermod', '--shell', shell, '--', username]):
                return ('Shell configuration failed', 'The selected shell must be installed before completing installation.')
        if libcalamares.utils.target_env_call(command):
            return ('Boot maintenance or backups failed', 'See the installation log for details.')
        # Remove installer launcher from the new user's Desktop and from skel.
        # finalize-install.sh passes ${USER}=root in its chroot context; this
        # module has the actual username from GlobalStorage.
        username = libcalamares.globalstorage.value('username')
        if isinstance(username, str) and re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}\$?', username):
            libcalamares.utils.target_env_call(['/usr/bin/rm', '-f', f'/home/{username}/Desktop/windoesnot-installer.desktop'])
        libcalamares.utils.target_env_call(['/usr/bin/rm', '-f', '/etc/skel/Desktop/windoesnot-installer.desktop'])
        if libcalamares.utils.target_env_call(['/usr/bin/rm', '-f', '/etc/windoesnot-image-build']):
            return ('Live marker cleanup failed', 'See the installation log for details.')
    except Exception as error:
        return ('Installation finalization failed', str(error))
    return None
