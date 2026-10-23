#!/usr/bin/env python3
"""Import approved PNG exports into standalone desktop release sources."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=ROOT / 'website/brand/png')
parser.add_argument('--check', action='store_true', help='Check imported files without changing them')
args = parser.parse_args()
target = ROOT / 'desktop/config/quickshell/default/img/brand'
expected = {f'windoesnot-logo-{name}.png': (2446, 459) for name in ('hell', 'dunkel')}
expected.update({f'windoesnot-icon-{size}.png': (size, size) for size in (16, 32, 48, 64, 128, 256, 512, 1024)})
manifest = {}
for name, dimensions in expected.items():
    source = args.source / name
    data = source.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', data[16:24]) == dimensions, name
    assert data[25] in (4, 6), f'Expected alpha channel: {name}'
    manifest[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'width': dimensions[0], 'height': dimensions[1]}
    if args.check:
        assert (target / name).read_bytes() == data, f'Brand export differs: {name}'
    else:
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target / name)
if not args.check:
    (target / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
# GRUB treats an image's native dimensions as its minimum layout size.
# Keep a separate correctly proportioned boot derivative; original exports stay intact.
boot = ROOT / 'desktop/share/grub/themes/windoesnot/windoesnot-logo-hell.png'
png = base64.b64encode((target / 'windoesnot-logo-hell.png').read_bytes()).decode()
svg = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="480" height="90"><image width="480" height="90" preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,' + png + '"/></svg>'
data = subprocess.check_output(['rsvg-convert'], input=svg.encode())
if args.check:
    assert boot.read_bytes() == data, 'Boot derivative needs regeneration'
else:
    boot.parent.mkdir(parents=True, exist_ok=True)
    boot.write_bytes(data)
print('PASS: all 10 transparent PNG exports match; proportionate 480x90 GRUB derivative matches')
