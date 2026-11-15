#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

values = {'locale': 'de_DE', 'partitionChoices': {'install': 'erase'}}
fake = SimpleNamespace(globalstorage=SimpleNamespace(value=values.get),
                       utils=SimpleNamespace(warning=lambda message: None))
path = Path(__file__).resolve().parent.parent / 'iso/modules/windoesnotmigrate_guard/main.py'
with patch.dict(sys.modules, {'libcalamares': fake}):
    spec = importlib.util.spec_from_file_location('guard', path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    values['windoesnotMigrateManifest'] = json.dumps({'schema': 1, 'kind': 'linux', 'users': [{'name': 'alice'}]})
    assert 'Linux' in guard.run()[0]
    values['partitionChoices'] = {'install': 'alongside'}
    assert guard.run() is not None
    values['windoesnotMigrateManifest'] = json.dumps({'schema': 1, 'kind': 'linux', 'users': [{'selected': 'false'}]})
    assert guard.run() is not None
print('PASS mirror guard')
