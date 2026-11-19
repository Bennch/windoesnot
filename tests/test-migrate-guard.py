#!/usr/bin/env python3
"""Calamares migration guard must stop before any source can be erased."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parent.parent
warnings = []
values = {'locale': 'de_DE.UTF-8'}
storage = SimpleNamespace(value=lambda key: values.get(key))
fake = SimpleNamespace(globalstorage=storage, utils=SimpleNamespace(warning=warnings.append))
with patch.dict(sys.modules, {'libcalamares': fake}):
    spec = importlib.util.spec_from_file_location('guard', root / 'iso/modules/windoesnotmigrate_guard/main.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert guard.run() is None
    values['windoesnotMigrateManifest'] = json.dumps({'profiles': [{'items': [{'selected': False}]}], 'handoff': None})
    assert guard.run() is None
    for choice in ('erase', 'manual', 'replace', None):
        values['partitionChoices'] = {'install': choice}
        values['windoesnotMigrateManifest'] = json.dumps({'profiles': [{'items': [{'selected': True}]}], 'handoff': None})
        assert 'vor der Partitionierung' in guard.run()[1]
        values['windoesnotMigrateManifest'] = json.dumps({'profiles': [], 'handoff': {'wlan_selected': True}})
        assert 'vor der Partitionierung' in guard.run()[1]
    values['partitionChoices'] = {'install': 'erase'}
    values['windoesnotMigrateManifest'] = json.dumps({'profiles': [], 'handoff': {'chromium_envelope': True}})
    assert guard.run() is not None
    # Installing alongside keeps Windows on the disk: the import may run.
    values['partitionChoices'] = {'install': 'alongside'}
    values['windoesnotMigrateManifest'] = json.dumps({'profiles': [{'items': [{'selected': True}]}], 'handoff': None})
    assert guard.run() is None
    values['windoesnotMigrateManifest'] = json.dumps({'profiles': [], 'handoff': {'wlan_selected': True}})
    assert guard.run() is None
    values['partitionChoices'] = {}
    values['partitionChoices'] = {'install': 'alongside'}
    for malformed in ('{', '{}', '[]', '{"profiles": null}', '{"profiles": [{"items": [{"selected": "false"}]}]}'):
        values['windoesnotMigrateManifest'] = malformed
        assert guard.run() is not None
    # A transfer package (copy on another disk or share) works with every install choice; a live Linux source does not.
    linux_plan = {'kind': 'linux', 'schema': 1, 'users': [{'selected': True}]}
    for choice in ('erase', 'manual', 'replace', None):
        values['partitionChoices'] = {'install': choice}
        values['windoesnotMigrateManifest'] = json.dumps(dict(linux_plan, package='/run/windoesnot/packages/x/umzug'))
        assert guard.run() is None, choice
        values['windoesnotMigrateManifest'] = json.dumps(linux_plan)
        assert 'Linux-Datenquelle' in guard.run()[0], choice
    values['windoesnotMigrateManifest'] = json.dumps({'kind': 'linux', 'schema': 2, 'users': [], 'package': '/x'})
    assert guard.run() is not None
    values['partitionChoices'] = {'install': 'alongside'}
    values['windoesnotMigrateManifest'] = '{'
    values['locale'] = 'en_US.UTF-8'
    assert 'before partitioning' in guard.run()[1]
print('PASS migrate guard')
