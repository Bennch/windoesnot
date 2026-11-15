# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop before partitioning while an in-installer import cannot be protected."""
import json
import importlib.util
import os
from pathlib import Path
import stat

spec = importlib.util.spec_from_file_location("windoesnot_block_identity", Path(__file__).with_name("block_identity.py"))
block_identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(block_identity)
import libcalamares


def pretty_name():
    return ('Windows-Datenquelle prüfen' if str(libcalamares.globalstorage.value('locale')).startswith('de')
            else 'Check Windows migration source')


def has_selection(raw):
    """Reject malformed plans instead of accidentally allowing partitioning."""
    plan = json.loads(raw)
    if isinstance(plan, dict) and plan.get('kind') == 'linux':
        if plan.get('schema') != 1 or not isinstance(plan.get('users'), list):
            raise ValueError('Invalid Linux migration plan')
        for user in plan['users']:
            if not isinstance(user, dict) or not isinstance(user.get('selected', True), bool):
                raise ValueError('Invalid Linux migration selection')
        # Package and system selections are not yet represented by this guard.
        # Treat every Linux plan as selected until the complete schema is handled.
        return True
    if not isinstance(plan, dict) or not isinstance(plan.get('profiles'), list):
        raise ValueError('Invalid migration plan')
    selected = False
    for profile in plan['profiles']:
        if not isinstance(profile, dict) or not isinstance(profile.get('items'), list):
            raise ValueError('Invalid migration plan')
        for item in profile['items']:
            if not isinstance(item, dict) or not isinstance(item.get('selected'), bool):
                raise ValueError('Invalid migration plan')
            selected |= item['selected']
    handoff = plan.get('handoff')
    if handoff is not None:
        if not isinstance(handoff, dict) or not isinstance(handoff.get('wlan_selected', False), bool):
            raise ValueError('Invalid migration plan')
        selected |= handoff.get('wlan_selected', False)
    return selected


def run():
    storage = libcalamares.globalstorage
    raw = storage.value('windoesnotMigrateManifest')
    if not raw:
        return None
    invalid = False
    linux = False
    try:
        candidate = json.loads(raw)
        linux = isinstance(candidate, dict) and candidate.get('kind') == 'linux'
        if not has_selection(raw):
            return None
    except (ValueError, TypeError):
        # A plan that cannot be read is never trusted, whatever the install choice is.
        libcalamares.utils.warning('windoesnotmigrate guard: invalid migration plan')
        invalid = True
    # The import reads the Windows partition after partitioning. "Alongside" only shrinks an existing
    # partition and never deletes or formats one, so the source survives. Erase, replace and manual
    # partitioning can destroy it before it is read: stop before anything is written.
    choices = storage.value('partitionChoices') or {}
    if not invalid and isinstance(choices, dict) and choices.get('install') == 'alongside':
        if not linux:
            return None
        try:
            device = candidate['device']
            info = os.stat(device)
            identity = f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}'
            targets = choices.get('writableTargets')
            if (not stat.S_ISBLK(info.st_mode) or identity != candidate.get('block_identity')
                    or not isinstance(targets, list) or not targets
                    or any(not isinstance(x, str) or not x.startswith('/dev/') for x in targets)
                    or not block_identity.disjoint_backing(device, targets)):
                raise ValueError('Unsafe source or target')
            # Calamares does not provide a verified complete writable-target
            # inventory here. A caller-provided list cannot establish that no
            # other partition or bootloader target will be written.
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if linux:
        if str(storage.value('locale')).startswith('de'):
            return ('Linux-Datenquelle schützen',
                    'Die Linux-Quelle oder die Installationsziele konnten nicht sicher geprüft werden. '
                    'Die Installation wurde vor der Partitionierung angehalten, um die Quelle zu schützen.')
        return ('Protect Linux migration source',
                'The Linux source or installation targets could not be verified safely. '
                'Installation stopped before partitioning to protect the source.')
    if str(storage.value('locale')).startswith('de'):
        return ('Windows-Datenumzug nur bei „Parallel installieren“',
                'Der Datenumzug ist nur möglich, wenn Windows bestehen bleibt: Wähle „Parallel installieren“ '
                'oder schalte den Datenumzug aus. Die Installation wurde vor der Partitionierung angehalten, '
                'damit keine Daten verloren gehen.')
    return ('Windows data migration needs "Install alongside"',
            'Data migration only works while Windows stays on the disk: choose "Install alongside" or switch '
            'the migration off. Installation stopped before partitioning so that no data is lost.')
