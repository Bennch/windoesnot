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
    # Like Windows: "install alongside" only shrinks a partition, the source stays readable.
    values['partitionChoices'] = {'install': 'alongside'}
    assert guard.run() is None
    for blocked in ('erase', 'replace', 'manual'):
        values['partitionChoices'] = {'install': blocked}
        assert guard.run() is not None, blocked
    values['partitionChoices'] = {}
    assert guard.run() is not None  # missing information: fail closed
    values['partitionChoices'] = {'install': 'alongside'}
    values['windoesnotMigrateManifest'] = json.dumps({'schema': 1, 'kind': 'linux', 'users': [{'selected': 'false'}]})
    assert guard.run() is not None  # malformed plan is never trusted, even alongside
print('PASS mirror guard')
