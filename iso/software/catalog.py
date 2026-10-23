#!/usr/bin/env python3
"""Strict, shared data contract for installer choices and portable profiles."""
import json
from pathlib import Path
import re


def load_catalog(path):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported catalogue version')
    ids = [app['id'] for app in data['apps']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate application')
    categories = {c['id'] for c in data['categories']}
    for app in data['apps']:
        if not re.fullmatch(r'[a-z][a-z0-9-]*', app['id']) or app['category'] not in categories:
            raise ValueError('Invalid application ID or category')
        for package in app['packages'] + sum(app.get('localizations', {}).values(), []):
            if not re.fullmatch(r'[a-z0-9][a-z0-9@._+-]*', package):
                raise ValueError('Invalid package name')
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
        if app['id'] not in selected:
            continue
        # Required apps are already in the image, but still need their language packs.
        packages.update(app.get('localizations', {}).get(language, []))
        if not app.get('required'):
            packages.update(app['packages'])
            services.update(app.get('services', []))
    return sorted(packages), sorted(services)
