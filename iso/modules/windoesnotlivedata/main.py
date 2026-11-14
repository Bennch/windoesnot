# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy files the user made in the live session to the new user's home (after the user exists)."""
from pathlib import Path
import re
import sys
import libcalamares

sys.path.insert(0, '/usr/lib/windoesnot')
import livedata

LIVE_USER = 'liveuser'


def pretty_name():
    return 'Dateien aus dem Live-System übernehmen' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Carry over files from the live system'


def target_ids(target_root, username):
    for line in (target_root / 'etc/passwd').read_text().splitlines():
        fields = line.split(':')
        if fields[0] == username and len(fields) > 3:
            return int(fields[2]), int(fields[3])
    raise ValueError('Target user not found')


def run():
    try:
        if 'windoesnot.live-data=off' in Path('/proc/cmdline').read_text().split():
            return None
        username = libcalamares.globalstorage.value('username')
        if not isinstance(username, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}\$?', username):
            raise ValueError('Target username is invalid')
        target_root = libcalamares.globalstorage.value('rootMountPoint')
        if not isinstance(target_root, str) or not target_root.startswith('/'):
            raise ValueError('Calamares target mount point is missing')
        target_root = Path(target_root).resolve()
        if target_root == Path('/') or not (target_root / 'etc/windoesnot-image-build').is_file():
            raise ValueError('Refusing to copy outside the installation target')
        live_home = Path('/home') / LIVE_USER
        if not live_home.is_dir():
            return None
        uid, gid = target_ids(target_root, username)
        result = livedata.copy_live_data(live_home, target_root / 'home' / username, uid, gid)
        libcalamares.utils.debug(f"windoesnotlivedata: {result['files']} file(s), {result['bytes']} bytes, {len(result['skipped'])} skipped")
    except Exception as error:  # a failed convenience copy must never abort the installation
        libcalamares.utils.warning(f'windoesnotlivedata: {error}')
    return None
