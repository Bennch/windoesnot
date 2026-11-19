#!/usr/bin/env python3
"""Create disposable migration data, or run a command with its bind mount active."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
p.add_argument('--with-mount', action='store_true', help='run COMMAND in a private user/mount namespace')
a, command = p.parse_known_args()
a.command = command
if command and not a.with_mount:
    p.error('unexpected arguments: ' + ' '.join(command))
root = a.root.resolve()
if a.with_mount:
    if not a.command:
        p.error('--with-mount requires a command after --')
    cmd = a.command[1:] if a.command[0] == '--' else a.command
    script = 'mount --bind "$1/mnt/fixture-layer" "$1/home/benni/nested-mount"; shift; exec "$@"'
    sys.exit(subprocess.call(['unshare', '-Urm', 'sh', '-ec', script, 'fixture', str(root), *cmd]))
if root.exists() and any(root.iterdir()):
    p.error('root must be absent or empty')
root.mkdir(parents=True, exist_ok=True)
def write(name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path

def db(name):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE fixture (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
        conn.execute('INSERT INTO fixture VALUES (1, ?)', ('migration test',))

for user in ('benni', 'anna'):
    home = 'home/' + user + '/'
    for app, profile in (('.mozilla/firefox', 'fixture.default'), ('.thunderbird', 'fixture.default')):
        base = home + app + '/' + profile + '/'
        for name in ('places.sqlite', 'key4.db'):
            db(base + name)
        write(base + 'logins.json', '{"logins":[]}\n')
        write(base + 'prefs.js', 'user_pref("fixture", true);\n')
    for name in ('.config/app/settings.ini', '.local/share/app/data', '.var/app/org.example.App/data', '.cache/discard', '.local/share/Trash/files/discard'):
        write(home + name, 'fixture ' + user + '\n')
write('home/benni/Dateien mit Umlaut ä und\nZeile.txt', 'special name\n')
file = write('home/benni/hardlink-original', 'hardlink content\n')
os.link(file, root / 'home/benni/hardlink-second')
os.symlink('hardlink-original', root / 'home/benni/relative-link')
os.symlink('/opt/example/app', root / 'home/benni/absolute-link')
os.symlink('missing-target', root / 'home/benni/broken-link')
large = root / 'home/benni/large-sparse.bin'
with large.open('wb') as f:
    f.write(b'start fixture\n')
    f.seek(2 * 1024**3 - 16)
    f.write(b'end fixture data')
os.setxattr(file, b'user.fixture', b'migration-xattr')
subprocess.run(['setfacl', '-m', 'u:1234:r--', str(file)], check=True)
(root / 'home/benni/nested-mount').mkdir()
write('home/benni/nested-mount/hidden-under-mount', 'underlay\n')
write('mnt/fixture-layer/mounted-content', 'mounted filesystem\n')
for name, content in {
    'var/lib/docker/overlay2/layer/diff/file': 'default docker layer\n',
    'var/lib/docker/volumes/default/_data/data': 'default volume data\n',
    'var/lib/docker/containers/abcdef012345/config.v2.json': '{"Name":"default"}\n',
    'var/lib/docker/image/overlay2/repositories.json': '{"Repositories":{}}\n',
    'srv/docker/overlay2/custom/diff/file': 'custom docker layer\n',
    'srv/docker/volumes/example/_data/data': 'volume data\n',
    'srv/docker/containers/0123456789ab/config.v2.json': '{"Name":"fixture"}\n',
    'srv/docker/image/overlay2/repositories.json': '{"Repositories":{}}\n',
    'etc/docker/daemon.json': '{"data-root":"/srv/docker"}\n',
    'home/benni/VirtualBox VMs/test/test.vdi': 'fixture vdi placeholder\n',
    'opt/example/app': 'application\n', 'usr/local/bin/example-tool': '#!/bin/sh\nexit 0\n',
    'srv/data/data.txt': 'service data\n', 'etc/os-release': 'ID=cachyos\nNAME=CachyOS\n',
    'etc/passwd': 'root:x:0:0:root:/root:/bin/bash\nbenni:x:1000:1000:Benni:/home/benni:/bin/bash\nanna:x:1001:1001:Anna:/home/anna:/bin/bash\n',
}.items(): write(name, content)
(root / 'usr/local/bin/example-tool').chmod(0o755)
for package in ('bash-5.2-1', 'firefox-130-1', 'example-aur-1.0-1'):
    name, version, release = package.rsplit('-', 2)
    write('var/lib/pacman/local/' + package + '/desc', f'%NAME%\n{name}\n\n%VERSION%\n{version}-{release}\n\n')
qcow = root / 'var/lib/libvirt/images/test.qcow2'
qcow.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(['qemu-img', 'create', '-q', '-f', 'qcow2', str(qcow), '8M'], check=True)
print('Fixture created:', root)
print('Actual ownership is the invoking user; logical fixture UIDs 1000/1001 are recorded in etc/passwd.')
