#!/usr/bin/env python3
"""Test authorized language setup without root actions or a terminal."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('system_tools', ROOT / 'desktop/lib/windoesnot/system_tools.py')
backend = importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
loader = importlib.machinery.SourceFileLoader('locale_setup', str(ROOT / 'desktop/bin/windoesnot-language-setup'))
spec = importlib.util.spec_from_loader(loader.name, loader)
setup = importlib.util.module_from_spec(spec);loader.exec_module(setup)


class LocaleSetup(unittest.TestCase):
    def test_enable_one_locale_with_progress_and_preserve_other_entries(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'locale.gen'
            p.write_text('# Keep this comment\n#de_DE.UTF-8 UTF-8  \n#en_US.UTF-8 UTF-8\nfr_FR.UTF-8 UTF-8\n');p.chmod(0o640)
            with patch.object(backend, 'LOCALE_GEN', p), patch.object(backend, 'command') as command, patch.object(backend, 'query', return_value='C\nde_DE.utf8\n'), contextlib.redirect_stdout(io.StringIO()) as output:
                backend.validate('locale-set', {'locale':'de_DE.UTF-8'})
                backend.apply('locale-set', {'locale':'de_DE.UTF-8'})
            text = p.read_text()
            self.assertIn('\nde_DE.UTF-8 UTF-8\n', text)
            self.assertIn('#en_US.UTF-8 UTF-8', text)
            self.assertIn('fr_FR.UTF-8 UTF-8', text)
            self.assertEqual(p.stat().st_mode & 0o777, 0o640)
            self.assertEqual([json.loads(v)['stage'] for v in output.getvalue().splitlines()], ['prepare','generate','apply'])
            self.assertEqual(command.call_args_list[-1].args, ('/usr/bin/localectl','set-locale','LANG=de_DE.UTF-8','LC_MESSAGES=de_DE.UTF-8','LC_TIME=de_DE.UTF-8'))

    def test_generation_failure_restores_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'locale.gen';original='#de_DE.UTF-8 UTF-8\n';p.write_text(original)
            with patch.object(backend, 'LOCALE_GEN', p), patch.object(backend, 'command', side_effect=RuntimeError('fixture failure')), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):backend.set_language_locale('de_DE.UTF-8')
            self.assertEqual(p.read_text(), original)

    def test_payload_is_an_exact_allowlist(self):
        for payload in [{'locale':'C'}, {'locale':'de_DE.UTF-8;id'}, {'locale':'de_DE.UTF-8','path':'/tmp/locale.gen'}, {}]:
            with self.assertRaises(ValueError):backend.validate('locale-set', payload)

    def test_ready_helper_uses_polkit_without_terminal_or_sudo(self):
        with patch.object(setup, 'support_ready', return_value=True), patch.object(setup.os, 'execv', side_effect=RuntimeError('captured')) as execute, patch('sys.argv', ['windoesnot-language-setup','de']):
            with self.assertRaisesRegex(RuntimeError,'captured'):setup.main()
            command=execute.call_args.args[1]
            self.assertEqual(command[:3], ['/usr/bin/pkexec','--disable-internal-agent',str(setup.HELPER)])
            self.assertEqual(json.loads(command[-1]), {'locale':'de_DE.UTF-8'})
            self.assertFalse(any('terminal' in v or v == 'sudo' for v in command))


if __name__ == '__main__':unittest.main()
