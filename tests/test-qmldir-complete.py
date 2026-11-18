#!/usr/bin/env python3
"""Every QML component in a directory that has a qmldir must be listed there.

With a qmldir, Qt only finds the listed types: a new component that is used but not listed ("X is not a type")
stops its parent page from loading. The isolated UI tests copy single files without the qmldir and do not notice.
"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default'


def main():
    missing = []
    sources = {path: path.read_text() for path in BASE.rglob('*.qml')}
    for qmldir in sorted(BASE.rglob('qmldir')):
        listed = {line.split()[0] for line in qmldir.read_text().splitlines() if line.strip() and not line.startswith('#') and len(line.split()) >= 3
                  and re.match(r'^[A-Z]', line.split()[0])}
        for qml in sorted(qmldir.parent.glob('*.qml')):
            name = qml.stem
            # Components that are only loaded by file path (Loader source) never need the entry; types that are used do.
            used = any(re.search(r'(?<![\w.\"/])' + name + r'\s*\{', text) for path, text in sources.items() if path != qml)
            if name[0].isupper() and name not in listed and used:
                missing.append(f'{qmldir.parent.relative_to(BASE)}/{name}')
    if missing:
        print('NOT LISTED in qmldir: ' + ', '.join(missing))
        return 1
    print('PASS: every component is listed in its qmldir')
    return 0


if __name__ == '__main__':
    sys.exit(main())
