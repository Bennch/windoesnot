#!/usr/bin/env python3
"""Exercise locale generation on temporary files without sudo or locale-gen."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('locale_setup', str(ROOT / 'desktop/bin/windoesnot-language-setup'))
spec = importlib.util.spec_from_loader(loader.name, loader)
setup = importlib.util.module_from_spec(spec)
loader.exec_module(setup)


class LocaleSetup(unittest.TestCase):
    def test_enable_one_locale_and_preserve_other_entries(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'locale.gen'
            p.write_text('# Keep this comment\n#de_DE.UTF-8 UTF-8  \n#en_US.UTF-8 UTF-8\nfr_FR.UTF-8 UTF-8\n')
            p.chmod(0o640)
            code = setup.GENERATOR.replace("Path('/etc/locale.gen')", 'Path('+repr(str(p))+')')
            subprocess.run(['python', '-I', '-c', code, 'de_DE.UTF-8'], check=True)
            text = p.read_text()
            self.assertIn('\nde_DE.UTF-8 UTF-8\n', text)
            self.assertIn('#en_US.UTF-8 UTF-8', text)
            self.assertIn('fr_FR.UTF-8 UTF-8', text)
            self.assertEqual(p.stat().st_mode & 0o777, 0o640)
            subprocess.run(['python', '-I', '-c', code, 'de_DE.UTF-8'], check=True)
            self.assertEqual(p.read_text(), text)
            rejected = subprocess.run(['python', '-I', '-c', code, 'invalid'], capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(p.read_text(), text)

    def test_quoted_system_locale_is_read_without_environment_override(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'locale.conf';p.write_text('LANG="de_DE.UTF-8"\n')
            self.assertEqual(setup.configured_locale(p), 'de_DE.UTF-8')


if __name__ == '__main__': unittest.main()
