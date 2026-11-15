#!/usr/bin/python3
"""Brand only entries generated for this installation's kernels."""
import os
from pathlib import Path
import re
import subprocess
import sys


def title(kernel, fallback=False):
    name = kernel.lower()
    variants = [part.upper() if part in ('lts', 'rt') else part.capitalize()
                for part in re.split(r'[-_]+', name)
                if part and part not in ('linux', 'cachyos') and not part[0].isdigit()]
    return 'WinDoesNot' + (' (' + ' '.join(variants) + ')' if variants else '') + (' (Fallback)' if fallback else '')


def update(path, name):
    text = path.read_text()
    changed, count = re.subn(r'(?m)^title[ \t]+[^\n]*$', lambda m: 'title ' + name, text)
    if count == 1 and changed != text:
        path.write_text(changed)


def sdboot(esp):
    entries = esp / 'loader/entries'
    for kernel in esp.glob('vmlinuz-*'):
        if not kernel.is_file():
            continue
        suffix = kernel.name[len('vmlinuz-'):]
        for fallback in (False, True):
            entry = entries / (suffix + ('-fallback' if fallback else '') + '.conf')
            if entry.is_symlink() or not entry.is_file():
                continue
            text = entry.read_text()
            if re.search(r'(?m)^linux[ \t]+/' + re.escape(kernel.name) + r'[ \t]*$', text):
                update(entry, title(suffix, fallback))


def kernel_install(version, entry_dir):
    token = os.environ.get('KERNEL_INSTALL_ENTRY_TOKEN', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', token) or '/' in version:
        return
    entries = Path(entry_dir).parent.parent / 'loader/entries'
    prefix = token + '-' + version
    for entry in entries.glob(prefix + '*.conf'):
        if not entry.is_symlink() and re.fullmatch(re.escape(prefix) + r'(?:\+\d+(?:-\d+)?)?\.conf', entry.name):
            update(entry, title(version))


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'kernel':
        kernel_install(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == 'sdboot':
        esp = subprocess.check_output(['/usr/bin/bootctl', '-p'], text=True).strip()
        sdboot(Path(esp))
