#!/usr/bin/env python3
"""Patch a temporary copy of the pinned upstream German Calamares catalog."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('patch_calamares_language', ROOT / 'tools/patch-calamares-language.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source = Path(os.environ.get('WINDOESNOT_CALAMARES_SOURCE', ROOT.parent / 'WinDoesNot/upstream/cachyos-calamares'))
upstream = source / 'lang/calamares_de.ts'
if not upstream.is_file():
    raise SystemExit(f'German upstream catalog unavailable: {upstream}')

with tempfile.TemporaryDirectory(prefix='windoesnot-calamares-catalog-') as tmp:
    copy = Path(tmp) / 'calamares_de.ts'
    shutil.copy2(upstream, copy)
    count = module.patch_catalog(copy)
    assert '<!DOCTYPE TS>' in copy.read_text(encoding='utf-8')
    assert count == sum(len(v) for v in module.json.loads((ROOT / 'iso/calamares/de-overrides.json').read_text()).values())
    root = ET.parse(copy).getroot()
    values = {}
    for context in root.findall('context'):
        name = context.findtext('name')
        for message in context.findall('message'):
            translation = message.find('translation')
            if translation is not None:
                values[(name, message.findtext('source') or '')] = ''.join(translation.itertext())
    assert values[('Page_UserSetup', 'Your Full Name')] == 'Dein vollständiger Name'
    assert 'du ' in values[('Page_UserSetup', 'What name do you want to use to log in?')]
    assert 'Größe' in values[('ChoicePage', '<strong>Manual partitioning</strong><br/>You can create or resize partitions yourself.')]
    assert 'Grösse' not in values[('ChoicePage', '<strong>Manual partitioning</strong><br/>You can create or resize partitions yourself.')]
    assert 'Erstelle<strong>neue</strong>' not in values.values()

print(f'PASS: {count} upstream German keys overridden in temporary catalog; placeholders retained')
