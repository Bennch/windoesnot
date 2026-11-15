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
    # The application job precedes the migration job. Include Thunderbird when
    # a profile was selected, even if the later copy is ultimately unsuccessful.
    raw = libcalamares.globalstorage.value('windoesnotMigrateManifest')
    try:
        plan = json.loads(raw) if isinstance(raw, str) and raw else {}
        profiles = plan.get('profiles', []) if isinstance(plan, dict) else []
        if any(item.get('kind') in ('Thunderbird', 'Windows Live Mail', 'Windows Mail', 'Outlook PST') and item.get('selected') is True
               for profile in profiles if isinstance(profile, dict)
               for item in profile.get('items', []) if isinstance(item, dict)):
            selected = list(dict.fromkeys([*selected, 'thunderbird']))
    except (ValueError, TypeError):
        pass  # The migration job validates the manifest separately.
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
