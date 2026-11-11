#!/usr/bin/env python3
"""Package existing PNG resolutions as ICNS without changing the artwork."""
from pathlib import Path
import struct
import sys

brand = Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default/img/brand'
chunks = []
for kind, size in [('icp4',16),('icp5',32),('icp6',64),('ic07',128),('ic08',256),('ic09',512),('ic10',1024)]:
    png = (brand / f'windoesnot-icon-{size}.png').read_bytes()
    chunks.append(kind.encode() + struct.pack('>I', len(png)+8) + png)
data = b''.join(chunks)
Path(sys.argv[1]).write_bytes(b'icns' + struct.pack('>I', len(data)+8) + data)
