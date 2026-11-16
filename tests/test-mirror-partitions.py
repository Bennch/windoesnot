#!/usr/bin/env python3
"""Linux discovery only returns supported partitions from lsblk output."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mirror_partitions', root / 'desktop/lib/windoesnot/mirror.py')
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)
fixture = {'blockdevices': [{'type': 'disk', 'children': [
    {'path': '/dev/a1', 'type': 'part', 'fstype': 'ext4', 'label': 'root', 'size': 10},
    {'path': '/dev/a2', 'type': 'part', 'fstype': 'crypto_LUKS', 'size': 20},
    {'path': '/dev/a3', 'type': 'part', 'fstype': 'ntfs'},
    {'path': '/dev/a4', 'type': 'part', 'fstype': 'btrfs'},
    {'path': '/dev/a5', 'type': 'part', 'fstype': 'xfs'},
]}]}
with patch.object(mirror.subprocess, 'check_output', return_value=json.dumps(fixture)):
    result = mirror.partitions()
assert [p['filesystem'] for p in result] == ['ext4', 'crypto_luks', 'btrfs', 'xfs']
assert result[0]['device'] == '/dev/a1' and result[0]['label'] == 'root'
print('PASS mirror partition discovery')
