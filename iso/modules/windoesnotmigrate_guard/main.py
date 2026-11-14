# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop before partitioning while an in-installer import cannot be protected."""
import json
import libcalamares


def pretty_name():
    return ('Windows-Datenquelle prüfen' if str(libcalamares.globalstorage.value('locale')).startswith('de')
            else 'Check Windows migration source')


def has_selection(raw):
    """Reject malformed plans instead of accidentally allowing partitioning."""
    plan = json.loads(raw)
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
    try:
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
        return None
    if str(storage.value('locale')).startswith('de'):
        return ('Windows-Datenumzug nur bei „Parallel installieren“',
                'Der Datenumzug ist nur möglich, wenn Windows bestehen bleibt: Wähle „Parallel installieren“ '
                'oder schalte den Datenumzug aus. Die Installation wurde vor der Partitionierung angehalten, '
                'damit keine Daten verloren gehen.')
    return ('Windows data migration needs "Install alongside"',
            'Data migration only works while Windows stays on the disk: choose "Install alongside" or switch '
            'the migration off. Installation stopped before partitioning so that no data is lost.')
