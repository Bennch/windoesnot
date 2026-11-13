#!/usr/bin/env python3
"""Apply reviewed German Calamares catalog overrides to a disposable source copy."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDERS = re.compile(r'%(?:\d+|n)')


def patch_catalog(catalog: Path, overrides_path=ROOT / 'iso/calamares/de-overrides.json'):
    catalog = Path(catalog)
    overrides = json.loads(Path(overrides_path).read_text())
    has_doctype = '<!DOCTYPE TS>' in catalog.read_text(encoding='utf-8')
    tree = ET.parse(catalog)
    found = set()
    for context in tree.getroot().findall('context'):
        name = context.findtext('name')
        for message in context.findall('message'):
            source = message.findtext('source') or ''
            key = (name, source)
            if name not in overrides or source not in overrides[name]:
                continue
            translation = message.find('translation')
            if translation is None or translation.get('type') == 'vanished':
                raise ValueError(f'Missing active German translation for {name}: {source!r}')
            replacement = overrides[name][source]
            if PLACEHOLDERS.findall(source) != PLACEHOLDERS.findall(replacement):
                raise ValueError(f'Placeholder mismatch in {name}: {source!r}')
            translation.text = replacement
            found.add(key)
    expected = {(context, source) for context, messages in overrides.items() for source in messages}
    missing = expected - found
    if missing:
        raise ValueError('Upstream German catalog no longer has override keys: ' + repr(sorted(missing)))
    output = BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    serialized = output.getvalue()
    if has_doctype:
        serialized = serialized.replace(b'?>', b'?>\n<!DOCTYPE TS>', 1)
    catalog.write_bytes(serialized)
    return len(found)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path, help='Disposable Calamares source copy')
    args = parser.parse_args()
    source = args.source.resolve()
    if (source / '.git').exists():
        raise SystemExit('Refusing to modify an upstream checkout; pass its generated build copy')
    catalog = source / 'lang/calamares_de.ts'
    print(f'Applied {patch_catalog(catalog)} German Calamares overrides')


if __name__ == '__main__':
    main()
