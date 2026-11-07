# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy selected Windows data after Calamares creates the target user."""
import json
from pathlib import Path
import re
import sys
import libcalamares

sys.path.insert(0, '/usr/lib/windoesnot')
import migrate


def pretty_name():
    return 'Windows-Daten kopieren' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Copy Windows data'


def run():
    raw = libcalamares.globalstorage.value('windoesnotMigrateManifest')
    if not raw:
        return None
    def warn(message):
        libcalamares.globalstorage.insert('windoesnotMigrateWarning', message)
        libcalamares.utils.warning('windoesnotmigrate: ' + message)
    try:
        username = libcalamares.globalstorage.value('username')
        if not isinstance(username, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}\$?', username):
            raise ValueError('Target username is invalid')
        plan = json.loads(raw)
        if not any(item.get('selected') for profile in plan.get('profiles', []) for item in profile.get('items', [])) and not (plan.get('handoff') or {}).get('wlan_selected'):
            return None
        secret = libcalamares.globalstorage.value('windoesnotMigrateSecret') or None
        target_root = libcalamares.globalstorage.value('rootMountPoint')
        if not isinstance(target_root, str) or not target_root.startswith('/'):
            raise ValueError('Calamares target mount point is missing')
        target_root = Path(target_root).resolve()
        if target_root == Path('/') or not (target_root / 'etc/windoesnot-image-build').is_file():
            raise ValueError('Refusing to copy outside the installation target')
        def progress(event):
            job = getattr(libcalamares, 'job', None)
            if event.get('event') == 'file' and event.get('total_bytes') and hasattr(job, 'setprogress'):
                job.setprogress(min(1.0, event['copied_bytes'] / event['total_bytes']))
        result = migrate.copy_manifest(plan, target_root / 'home' / username, secret=secret, progress=progress,
                                       nm_dir=target_root / 'etc/NetworkManager/system-connections')
        if result['errors']:
            warn(f"Windows data migration incomplete: {len(result['errors'])} item(s) could not be copied. First: {result['errors'][0]['path']}: {result['errors'][0]['error']}")
    except Exception as error:
        warn('Windows data migration could not finish: ' + str(error))
    finally:
        libcalamares.globalstorage.insert('windoesnotMigrateSecret', '')
    return None
