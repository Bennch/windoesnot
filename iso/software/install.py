#!/usr/bin/env python3
"""Install a validated app selection from the ISO's signed offline repository."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
from catalog import load_catalog, packages_for
from repository import install_packages

BASE = Path('/usr/share/windoesnot')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection-json', required=True)
    parser.add_argument('--language', default='en')
    parser.add_argument('--mode', default='offline', choices=['online', 'offline'])
    args = parser.parse_args()
    if os.geteuid() != 0 or os.environ.get('WINDOESNOT_INSTALL_TARGET') != '1':
        raise SystemExit('Calamares installation target only')
    install_selection(json.loads(args.selection_json), args.language, mode=args.mode)
    Path('/var/lib/pacman/sync/windoesnot-apps.db').unlink(missing_ok=True)


def install_selection(selected, language, base=BASE, record=Path('/var/lib/windoesnot/software-profile.json'), mode='offline'):
    catalog = load_catalog(base / 'iso/software/catalog.json')
    packages, services = packages_for(catalog, selected, language)
    bundle = base / 'offline-apps'
    install_packages(packages, mode, base)
    for service in services:
        subprocess.run(['systemctl', 'enable', service], check=True)
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({'schema_version': 1, 'selected': sorted(selected)}, indent=2) + '\n')
    # Optional archives belong to the live medium, not the installed desktop.
    shutil.rmtree(bundle)
    print('Selected applications installed (' + mode + ', ISO snapshot)')


if __name__ == '__main__':
    main()
