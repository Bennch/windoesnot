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
    for choice in ('alongside', 'erase', 'manual', 'replace', None):
        values['partitionChoices'] = {'install': choice}
        values['windoesnotMigrateManifest'] = json.dumps({'profiles': [{'items': [{'selected': True}]}], 'handoff': None})
        assert 'vor der Partitionierung' in guard.run()[1]
        values['windoesnotMigrateManifest'] = json.dumps({'profiles': [], 'handoff': {'wlan_selected': True}})
        assert 'vor der Partitionierung' in guard.run()[1]
    for malformed in ('{', '{}', '[]', '{"profiles": null}', '{"profiles": [{"items": [{"selected": "false"}]}]}'):
        values['windoesnotMigrateManifest'] = malformed
        assert guard.run() is not None
    values['locale'] = 'en_US.UTF-8'
    assert 'before partitioning' in guard.run()[1]
print('PASS migrate guard')
