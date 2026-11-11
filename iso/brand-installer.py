#!/usr/bin/env python3
"""Brand Calamares desktop entries while keeping one configured visible launcher."""
from pathlib import Path


def apply(root):
    p = root / 'usr/share/applications/calamares.desktop'
    lines = []
    for line in p.read_text().splitlines():
        if line.startswith(('Icon=', 'Icon[')):
            line = line.split('=', 1)[0] + '=windoesnot'
        elif line.startswith('Exec='):
            line = 'Exec=windoesnot-installer'
        elif line.startswith('NoDisplay='):
            continue
        lines.append(line)
    text = '\n'.join(lines) + '\nNoDisplay=true\n'
    p.write_text(text)
    # Wayland app_id must match the desktop filename used by icon discovery.
    p.with_name('io.calamares.calamares.desktop').write_text(text)


if __name__ == '__main__':
    root = Path('/')
    if not (root / 'etc/windoesnot-image-build').is_file():
        raise SystemExit('Image build only')
    apply(root)
