#!/usr/bin/env python3
"""A new logical partition needs a gap behind the shrunk one (MBR + extended, seen on a 2010 laptop)."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if not shutil.which('sfdisk'):
    print('SKIP: sfdisk missing')
    sys.exit(0)

LAYOUT = """label: dos
unit: sectors
$S1 : start=2048, size=1048576, type=b, bootable
$S2 : start=1052670, size=487344130, type=5
$S5 : start=1052672, size=243672065, type=83
""".replace('$S', 'p')
LAST_SECTOR_OF_SHRUNK_LOGICAL = 244724736


def append(image, start):
    script = f'start={start}, size=240000000, type=83\n'
    return subprocess.run(['sfdisk', '--no-act', '--force', '--append', str(image)], input=script,
                          capture_output=True, text=True).returncode == 0


with tempfile.TemporaryDirectory() as directory:
    image = Path(directory) / 'disk.img'
    with image.open('wb') as stream:
        stream.truncate(250059350016)
    subprocess.run(['sfdisk', '-q', str(image)], input=LAYOUT, text=True, check=True)
    upstream_start = 244726784  # what upstream Calamares asks for (end + 2, aligned to 1 MiB)
    assert not append(image, upstream_start), 'sfdisk now accepts the upstream start: re-check the patch'
    gap = max(4, (2 * 1024 * 1024) // 512)  # the patch: 2 MiB in 512 byte sectors
    assert append(image, LAST_SECTOR_OF_SHRUNK_LOGICAL + gap), 'the patched start sector must be accepted'
print('PASS: logical partitions need the EBR gap; the patched start sector is accepted')
