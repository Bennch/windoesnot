#!/usr/bin/env python3
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent

@unittest.skipUnless(all(shutil.which(x) for x in ('ffmpeg', 'ffprobe', 'magick')), 'ffmpeg, ffprobe and magick required')
class VideoTest(unittest.TestCase):
    def test_missing_scene_reports_error(self):
        with tempfile.TemporaryDirectory(prefix='umzug-missing-') as temp:
            root = Path(temp)
            (root/'01-windows').mkdir()
            (root/'01-windows/windows-7.png').touch()
            result = subprocess.run([sys.executable, str(ROOT/'tools/make-umzug-video.py'), '--footage', str(root), '--out', str(root.parent/'umzug-unused-output')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('02-boot', result.stderr)

    def test_outputs(self):
        with tempfile.TemporaryDirectory(prefix='umzug-test-') as temp:
            root = Path(temp)
            footage, out = root/'footage', root/'out'
            for folder in ('01-windows', '02-boot', '03-installer', '04-desktop'):
                (footage/folder).mkdir(parents=True)
            image = root/'placeholder.png'
            subprocess.run(['magick', '-size', '320x200', 'xc:#455266', '-font', 'DejaVu-Sans', '-fill', 'white', '-gravity', 'center', '-pointsize', '26', '-annotate', '0', 'PLATZHALTER', str(image)], check=True)
            shutil.copy(image, footage/'01-windows/windows-10.png')
            for folder in ('02-boot', '03-installer', '04-desktop'):
                shutil.copy(image, footage/folder/'frame-0001.png')
                (footage/folder/'fps.txt').write_text('4\n')
            config = root/'config.json'
            config.write_text(json.dumps(dict.fromkeys(('windows','boot','installer','desktop','end'), 0.1)))
            subprocess.run([sys.executable, str(ROOT/'tools/make-umzug-video.py'), '--footage', str(footage), '--out', str(out), '--config', str(config)], check=True, timeout=55)
            for lang in ('de', 'en'):
                for stem, codec, width, height in [('reel-9x16','h264',1080,1920), ('web-16x9','h264',1920,1080), ('web-16x9','vp9',1920,1080)]:
                    ext = 'webm' if codec == 'vp9' else 'mp4'
                    path = out/f'umzug-{stem}-{lang}.{ext}'
                    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,r_frame_rate:format=duration','-of','json',str(path)]))
                    stream = info['streams'][0]
                    self.assertEqual((stream['codec_name'],stream['width'],stream['height'],stream['r_frame_rate']), (codec,width,height,'30/1'))
                    self.assertAlmostEqual(float(info['format']['duration']), 0.5, delta=0.1)
                gif = out/f'umzug-{lang}.gif'
                self.assertLess(gif.stat().st_size, 8_000_000)
                info = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,r_frame_rate','-of','json',str(gif)]))
                self.assertEqual(info['streams'][0]['width'], 720)
                num, den = map(int, info['streams'][0]['r_frame_rate'].split('/'))
                self.assertAlmostEqual(num / den, 12, delta=0.15)
                self.assertTrue((out/f'poster-{lang}.png').is_file())

if __name__ == '__main__': unittest.main()
