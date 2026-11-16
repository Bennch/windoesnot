#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('media_check', ROOT / 'desktop/lib/windoesnot/media_check.py')
media = importlib.util.module_from_spec(spec); spec.loader.exec_module(media)

class Tests(unittest.TestCase):
    def test_fixed_output(self):
        result = media.parse(' D  matroska,webm Matroska\n  E mp4 MP4\n', ' DEV.LS h264 H.264\n .EV.L. hevc HEVC\n D.AIL. mp3 MP3\n', 'libav:  avdec_h264: decoder\nmatroska:  matroskademux: Demuxer\n')
        self.assertEqual(result['H.264'], {'ffmpeg': True, 'gstreamer': True})
        self.assertEqual(result['H.265'], {'ffmpeg': False, 'gstreamer': False})
        self.assertTrue(result['MP3']['ffmpeg']); self.assertTrue(result['WebM']['ffmpeg']); self.assertTrue(result['WebM']['gstreamer'])
        self.assertFalse(media.parse('', '', '')['WebM']['ffmpeg'])
    def test_desktop_and_catalog(self):
        p = ROOT / 'desktop/share/applications/windoesnot-windows-program.desktop'
        text = p.read_text()
        for mime in ('application/x-ms-dos-executable', 'application/x-msi', 'application/vnd.microsoft.portable-executable'): self.assertIn(mime + ';', text)
        if shutil.which('desktop-file-validate'): subprocess.run(['desktop-file-validate', str(p)], check=True)
        catalog = json.loads((ROOT / 'iso/software/catalog.json').read_text())
        app = next(x for x in catalog['apps'] if x['id'] == 'bottles')
        self.assertEqual(app['flatpak_id'], 'com.usebottles.bottles')
        self.assertFalse(any('bottles' in p['selected'] for p in catalog['profiles']))
        for lang in ('de', 'en'):
            text = (ROOT / f'desktop/config/quickshell/default/i18n/{lang}.js').read_text()
            for key in ('title', 'hint', 'check', 'present', 'missing', 'failed'): self.assertIn('"media.' + key + '"', text)

if __name__ == '__main__': unittest.main()
