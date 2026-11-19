#!/usr/bin/env python3
"""The installer side of a transfer package: found on a mounted disk, offered by the existing move page, restored into the new home."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, root / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
finder = load('finder', 'desktop/lib/windoesnot/finder.py')
mirror = load('mirror', 'desktop/lib/windoesnot/mirror.py')

def write(path, data='x', mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)
    if mode is not None:
        os.chmod(path, mode)

with tempfile.TemporaryDirectory() as tmp:
    old = Path(tmp) / 'old'
    home = old / 'home/anna'
    write(old / 'etc/passwd', 'anna:x:%d:%d::/home/anna:/bin/bash\n' % (os.getuid(), os.getgid()))
    write(home / '.ssh/id_ed25519', 'PRIVATE', 0o600)
    write(home / 'Documents/letter.txt', 'dear')
    write(home / '.cache/blob', 'c' * 100)
    manifest = finder.scan(old)
    stick = Path(tmp) / 'stick'
    stick.mkdir()
    package = Path(finder.export_package(manifest, stick)['package'])
    # Discovery: a partition that is already mounted is searched in place (no mount call needed).
    fake = [{'path': '/dev/sdb1', 'type': 'part', 'fstype': 'exfat', 'label': 'STICK', 'mountpoints': [str(stick)]},
            {'path': '/dev/sda2', 'type': 'part', 'fstype': 'ext4', 'label': 'system', 'mountpoints': ['/']}]
    found = finder.discover_packages(fake, mounter=lambda *a: None)
    assert len(found) == 1 and found[0]['device'] == '/dev/sdb1' and found[0]['complete'] and found[0]['user'] == 'anna', found
    # An unmounted partition is mounted read-only by the given mounter; without a package it is released again.
    calls = []
    empty = Path(tmp) / 'empty'
    empty.mkdir()
    def mounter(device, fs, name):
        calls.append((device, fs)); return empty
    assert finder.discover_packages([{'path': '/dev/sdc1', 'type': 'part', 'fstype': 'ntfs', 'mountpoints': [None]}], mounter=mounter) == [] and calls == [('/dev/sdc1', 'ntfs')]
    # The page sees the package as a Linux plan with the findings as ticked locations (rebuildable ones unticked).
    plan = mirror.scan_device('package:' + str(package))
    assert plan['kind'] == 'linux' and plan['package'] == str(package) and plan['users'][0]['name'] == 'anna'
    ids = {l['id']: l for l in plan['locations']}
    assert ids['ssh']['selected'] and ids['dir:Documents']['selected'] and 'cache' not in ids
    ids['ssh']['selected'] = False                       # the user unticks one finding
    # The install job's call: copy_manifest into the new home.
    target = Path(tmp) / 'new'
    new_home = target / 'home/neu'
    new_home.mkdir(parents=True)
    events = []
    result = mirror.copy_manifest(plan, str(new_home), str(target), None, events.append)
    assert not result['errors'] and result['files'] >= 1, result
    assert (new_home / 'Documents/letter.txt').read_text() == 'dear'
    assert not (new_home / '.ssh').exists(), 'unticked finding stays out'
    assert events and events[-1]['event'] == 'file' and events[-1]['copied_bytes'] <= events[-1]['total_bytes']
    # An incomplete package is not offered and cannot be restored.
    (package / finder.PACKAGE_MARKER).unlink()
    assert finder.find_packages([stick]) == []
print('PASS package installer')
