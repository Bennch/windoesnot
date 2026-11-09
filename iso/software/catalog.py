#!/usr/bin/env python3
"""Strict, shared data contract for installer choices and portable profiles."""
import json
from pathlib import Path
import re

SOURCES = ('offline', 'flatpak', 'repo', 'aur', 'webapp', 'link')
# https only, plain host and path: no credentials, ports, queries or fragments, no shell metacharacters.
WEBAPP_URL = re.compile(r'https://([a-z0-9-]+\.)+[a-z]{2,}(/[A-Za-z0-9._~%/-]*)?')
# Extra Flatpak remotes: name and .flatpakrepo URL come only from the catalogue's fixed allowlist.
REMOTE_NAME = re.compile(r'[a-z][a-z0-9-]*')
REMOTE_URL = re.compile(r'https://([a-z0-9-]+\.)+[a-z]{2,}(/[A-Za-z0-9._~-]+)*/[A-Za-z0-9._-]+\.flatpakrepo')


def load_catalog(path):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported catalogue version')
    ids = [app['id'] for app in data['apps']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate application')
    remotes = data.get('flatpak_remotes', {})
    if not isinstance(remotes, dict):
        raise ValueError('Invalid Flatpak remotes')
    for name, remote in remotes.items():
        if name == 'flathub' or not REMOTE_NAME.fullmatch(name) or not isinstance(remote, dict) \
                or not REMOTE_URL.fullmatch(remote.get('url', '')):
            raise ValueError('Invalid Flatpak remote')
    categories = {c['id'] for c in data['categories']}
    for app in data['apps']:
        if not re.fullmatch(r'[a-z][a-z0-9-]*', app['id']) or app['category'] not in categories:
            raise ValueError('Invalid application ID or category')
        source = app.get('source', 'offline')
        if source not in SOURCES:
            raise ValueError('Unknown application source')
        for package in app['packages'] + sum(app.get('localizations', {}).values(), []) + app.get('repo_packages', []):
            if not re.fullmatch(r'[a-z0-9][a-z0-9@._+-]*', package):
                raise ValueError('Invalid package name')
        # Deferred sources carry exactly one fixed reference and never offline packages.
        if app.get('flatpak_remote') and (source != 'flatpak' or app['flatpak_remote'] not in remotes):
            raise ValueError('Flatpak remote not in the allowlist')
        if source == 'offline':
            if app.get('flatpak_id') or app.get('aur_package') or app.get('repo_packages') or app.get('url'):
                raise ValueError('Offline application with deferred reference')
        else:
            if app['packages'] or app.get('required') or app.get('services'):
                raise ValueError('Deferred application with offline content')
            if source == 'flatpak' and not re.fullmatch(r'[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}', app.get('flatpak_id', '')):
                raise ValueError('Invalid Flatpak ID')
            if source == 'aur' and not re.fullmatch(r'[a-z0-9][a-z0-9@._+-]*', app.get('aur_package', '')):
                raise ValueError('Invalid AUR package')
            if source in ('webapp', 'link') and not WEBAPP_URL.fullmatch(app.get('url', '')):
                raise ValueError('Invalid web app URL')
            if source == 'repo' and not app.get('repo_packages'):
                raise ValueError('Repository application without packages')
        if any(service != 'cups.service' for service in app.get('services', [])):
            raise ValueError('Unsupported service')
    for profile in data['profiles']:
        validate_selection(data, profile['selected'])
    return data


def validate_selection(catalog, selected):
    allowed = {app['id'] for app in catalog['apps']}
    if not isinstance(selected, list) or any(not isinstance(x, str) for x in selected):
        raise ValueError('Select application IDs')
    if len(selected) != len(set(selected)) or not set(selected) <= allowed:
        raise ValueError('Unknown or duplicate application')
    required = {app['id'] for app in catalog['apps'] if app.get('required')}
    if not required <= set(selected):
        raise ValueError('Required desktop applications cannot be removed')
    return selected


def read_profile(catalog, path):
    source = Path(path)
    if source.stat().st_size > 65536:
        raise ValueError('Profile too large')
    data = json.loads(source.read_text())
    if not isinstance(data, dict) or set(data) != {'schema_version', 'selected'} or data['schema_version'] != 1:
        raise ValueError('Invalid profile format')
    return validate_selection(catalog, data['selected'])


def packages_for(catalog, selected, language='en'):
    validate_selection(catalog, selected)
    packages = set()
    services = set()
    language = re.split('[-_.]', language)[0].lower()
    for app in catalog['apps']:
        if app['id'] not in selected or app.get('source', 'offline') != 'offline':
            continue
        # Required apps are already in the image, but still need their language packs.
        packages.update(app.get('localizations', {}).get(language, []))
        if not app.get('required'):
            packages.update(app['packages'])
            services.update(app.get('services', []))
    return sorted(packages), sorted(services)


def pending_for(catalog, selected):
    """Deferred applications (installed after the first boot, when online): IDs only, in catalogue order."""
    validate_selection(catalog, selected)
    return [app['id'] for app in catalog['apps']
            if app['id'] in selected and app.get('source', 'offline') != 'offline']


def pending_reference(app):
    """(source, fixed reference) of a deferred application, resolved from the catalogue, never from user data."""
    source = app.get('source', 'offline')
    if source == 'flatpak':
        return source, [app['flatpak_id']]
    if source == 'aur':
        return source, [app['aur_package']]
    if source == 'repo':
        return source, list(app['repo_packages'])
    if source in ('webapp', 'link'):
        return source, [app['url']]
    raise ValueError('Not a deferred application')


def flatpak_remote(catalog, app):
    """(name, flatpakrepo URL) of the app's Flatpak remote; Flathub unless the allowlist names another."""
    name = app.get('flatpak_remote')
    if not name:
        return 'flathub', 'https://dl.flathub.org/repo/flathub.flatpakrepo'
    return name, catalog['flatpak_remotes'][name]['url']
