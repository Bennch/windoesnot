#!/usr/bin/env python3
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('image', ROOT / 'tools/prepare-asahi-image.py')
image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image)


class ImageInputsTests(unittest.TestCase):
    def test_package_architecture_is_read_from_payload(self):
        with tempfile.TemporaryDirectory() as d:
            for arch in ('aarch64', 'any', 'x86_64'):
                path = Path(d) / f'example-{arch}.pkg.tar.gz'
                data = f'pkgname = example\npkgver = 1.0-1\narch = {arch}\n'.encode()
                with tarfile.open(path, 'w:gz') as stream:
                    item = tarfile.TarInfo('.PKGINFO')
                    item.size = len(data)
                    stream.addfile(item, io.BytesIO(data))
                if arch == 'x86_64':
                    with self.assertRaises(ValueError):
                        image.package_info(path)
                else:
                    info = image.package_info(path)
                    self.assertEqual(info['arch'], arch)
                    self.assertEqual(info['sha256'], image.digest(path))

    def test_seed_mismatch_stops_before_creating_workspace(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as d:
            output, seed = Path(d) / 'output', Path(d) / 'seed.tar.gz'
            seed.write_bytes(b'not the verified seed')
            with patch.object(image.subprocess, 'check_output', side_effect=[image.BUILDER + '\n', '']):
                with self.assertRaisesRegex(ValueError, 'matching SHA-256'):
                    image.prepare(output, Path(d), base=seed, base_sha='0' * 64)
            self.assertFalse(output.exists())

    def test_host_paths_cannot_be_image_workspaces(self):
        for path in (Path('/'), Path('/boot'), ROOT, ROOT / 'build'):
            with self.assertRaises(ValueError):
                image.prepare(path, Path('/tmp'))


if __name__ == '__main__':
    unittest.main()
