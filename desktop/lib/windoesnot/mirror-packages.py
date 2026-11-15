#!/usr/bin/env python3
"""Install explicitly inventoried repository and Flatpak applications once."""
import json
import os
from pathlib import Path
import re
import subprocess

NAME = re.compile(r'^[a-z0-9@._+-]+$')
FLATPAK = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$')
DENY = re.compile(r'^(linux|grub|systemd-boot|nvidia|mesa|.*(?:driver|drivers|firmware|microcode|bootloader|kernel|headers|xf86-video|vulkan))')


def allowed(name):
    return isinstance(name, str) and bool(NAME.fullmatch(name)) and not name.startswith('-') and not DENY.search(name)


def process(folder, run=subprocess.run):
    folder = Path(folder)
    done = folder / 'done'
    if done.exists():
        return
    data = json.loads((folder / 'packages.json').read_text(encoding='utf-8'))
    home = Path(data['home'])
    source = data['source']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', source) or source in ('.', '..'):
        raise ValueError('Invalid source')
    if not home.is_absolute() or home.is_symlink() or not home.is_dir() or home.resolve() != home:
        raise ValueError('Unsafe home')
    archive = home / ('Umzug-' + source)
    if archive.is_symlink():
        raise ValueError('Unsafe report directory')
    archive.mkdir(exist_ok=True)
    report = ['Paketumzug / Package migration']
    failed = False
    foreign = data.get('arch_foreign')
    for name in data.get('arch_explicit', []):
        if not allowed(name) or foreign is None or name in foreign:
            report.append('Ausgelassen / Skipped: ' + str(name))
            continue
        result = run(['pacman', '-S', '--needed', '--noconfirm', '--', name], check=False)
        report.append(('OK: ' if result.returncode == 0 else 'Fehler / Failed: ') + name)
        failed |= result.returncode != 0
    for app in data.get('flatpak', []):
        if not isinstance(app, str) or not FLATPAK.fullmatch(app) or '.' not in app:
            report.append('Ausgelassen / Skipped: ' + str(app)); continue
        result = run(['flatpak', 'install', '--noninteractive', '--', app], check=False)
        report.append(('OK: ' if result.returncode == 0 else 'Fehler / Failed: ') + app)
        failed |= result.returncode != 0
    report.append('Fremdpakete / Foreign packages: ' + (', '.join(foreign) if foreign is not None else 'unbekannt / unknown'))
    report.append('Debian (manuell) / Debian (manual): ' + ', '.join(data.get('deb_manual', [])))
    target = archive / 'BERICHT.txt'
    if target.is_symlink():
        raise ValueError('Unsafe report')
    target.write_text('\n'.join(report) + '\n', encoding='utf-8')
    if not failed:
        done.touch()
    # Session notification is best effort; root services normally lack a user bus.
    run(['notify-send', 'WinDoesNot', 'Paketumzug abgeschlossen / Package migration finished'], check=False)
    if failed:
        raise RuntimeError('Some packages failed')


def main():
    root = Path('/var/lib/windoesnot/mirror')
    if root.is_dir():
        for folder in sorted(root.iterdir()):
            if folder.is_dir() and not folder.is_symlink() and (folder / 'packages.json').is_file():
                process(folder)


if __name__ == '__main__':
    main()
