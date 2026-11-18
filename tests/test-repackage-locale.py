#!/usr/bin/env python3
"""Packaged Unicode paths must not truncate extraction under the C locale."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class RepackageLocale(unittest.TestCase):
    def test_non_ascii_then_later_files_extract_under_c_locale(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); image = root / 'image'; output = root / 'packages'
            entry = image / 'var/lib/pacman/local/windoesnot-test-1-1'; entry.mkdir(parents=True)
            (entry / 'desc').write_text('%NAME%\nwindoesnot-test\n\n%VERSION%\n1-1\n\n%BUILDDATE%\n1\n\n%SIZE%\n2\n\n%ARCH%\nany\n')
            names = ['usr/share/test/' + 'a' * 110 + '/datei-é.txt', 'usr/share/test/zzz-after.txt']
            (entry / 'files').write_text('%FILES%\n' + '\n'.join(names) + '\n')
            for name in names:
                p = image / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('ok')
            subprocess.run([sys.executable, str(ROOT / 'tools/repackage-from-image.py'), '--image', str(image), '--output', str(output), 'windoesnot-test'], check=True, capture_output=True)
            target = root / 'unpacked'; target.mkdir()
            subprocess.run(['bsdtar', '-xf', str(next(output.glob('*.pkg.tar.zst'))), '-C', str(target)],
                           check=True, env={**os.environ, 'LC_ALL': 'C'}, capture_output=True)
            for name in names: self.assertEqual((target / name).read_text(), 'ok')

if __name__ == '__main__': unittest.main()
