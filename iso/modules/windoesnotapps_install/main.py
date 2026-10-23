# SPDX-License-Identifier: GPL-3.0-or-later
"""Install only approved selections in the mounted installation target."""
import json
import libcalamares


def pretty_name():
    return 'Ausgewählte Programme installieren' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Install selected applications'


def run():
    selected = libcalamares.globalstorage.value('windoesnotSoftwareSelection')
    if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
        return ('Application selection is missing', 'Return to the Programs page and choose a profile.')
    language = str(libcalamares.globalstorage.value('locale') or 'en')
    mode = libcalamares.job.configuration.get('mode', 'offline')
    if mode not in ('online', 'offline'):
        return ('Invalid installation mode', 'Restart the installer using an online or offline live entry.')
    command = ['/usr/bin/env', 'WINDOESNOT_INSTALL_TARGET=1', '/usr/bin/python', '/usr/share/windoesnot/iso/software/install.py', '--selection-json', json.dumps(selected), '--language', language, '--mode', mode]
    libcalamares.job.setprogress(0)
    try:
        result = libcalamares.utils.target_env_call(command)
        if result:
            return ('Selected applications could not be installed', mode + ' package installation failed. See the installer log for details.')
    except Exception as error:
        return ('Selected applications could not be installed', str(error))
    libcalamares.job.setprogress(1)
    return None
