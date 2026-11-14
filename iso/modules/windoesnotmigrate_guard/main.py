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
    try:
        if not has_selection(raw):
            return None
    except (ValueError, TypeError):
        libcalamares.utils.warning('windoesnotmigrate guard: invalid migration plan')
    # The source is currently read only after the partition job. Calamares
    # does not expose its final partition operations before that job executes;
    # even an "alongside" choice is not sufficient proof of source identity.
    if str(storage.value('locale')).startswith('de'):
        return ('Windows-Datenumzug noch nicht verfügbar',
                'Die gewählte Windows-Datenquelle kann während der Installation noch nicht sicher erhalten werden. '
                'Die Installation wurde vor der Partitionierung angehalten. Erstelle eine externe Datensicherung; '
                'ohne ausgewählten Datenumzug kann der Installer verwendet werden.')
    return ('Windows migration is not yet available',
            'The selected Windows data source cannot yet be guaranteed to survive installation. '
            'Installation stopped before partitioning. Make an external backup; '
            'the installer can be used without selecting Windows data migration.')
