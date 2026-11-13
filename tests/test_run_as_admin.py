import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / 'desktop/bin/windoesnot-run-as-admin'
spec = importlib.util.spec_from_loader('windoesnot_run_as_admin', SourceFileLoader('windoesnot_run_as_admin', str(CLI_PATH)))
admin_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin_cli)


def load_extension():
    nautilus = types.SimpleNamespace(MenuProvider=type('MenuProvider', (), {}), MenuItem=type('MenuItem', (), {
        '__init__': lambda self, **kw: self.__dict__.update(kw),
        'connect': lambda self, *_: None,
    }))
    gi = types.ModuleType('gi')
    repository = types.ModuleType('gi.repository')
    repository.Gio = types.SimpleNamespace()
    repository.GObject = types.SimpleNamespace(GObject=type('GObject', (), {}))
    repository.Nautilus = nautilus
    gi.repository = repository
    with patch.dict(sys.modules, {'gi': gi, 'gi.repository': repository}):
        ext_spec = importlib.util.spec_from_file_location(
            'windoesnot_admin_extension', ROOT / 'desktop/config/quickshell/default/extras/nautilus/windoesnot-admin.py')
        module = importlib.util.module_from_spec(ext_spec)
        ext_spec.loader.exec_module(module)
    return module


class AdminRunTests(unittest.TestCase):
    def test_classifies_executables_and_interpreted_scripts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'An app (ä).AppImage'
            binary.write_text('placeholder')
            binary.chmod(0o755)
            shell = root / 'my script; $(safe).SH'
            shell.write_text('echo safe')
            python = root / 'no-execute.py'
            python.write_text('print("safe")')
            text = root / 'notes.txt'
            text.write_text('not runnable')
            self.assertEqual(admin_cli.command_for(binary), [str(binary)])
            self.assertEqual(admin_cli.command_for(shell), ['/usr/bin/bash', str(shell)])
            self.assertEqual(admin_cli.command_for(python), ['/usr/bin/python3', str(python)])
            self.assertIsNone(admin_cli.command_for(text))
            self.assertIsNone(admin_cli.command_for(root))

    def test_nonautilus_menu_only_offers_supported_files(self):
        extension = load_extension()

        class Location:
            def __init__(self, path): self.path = path
            def get_path(self): return self.path

        class File:
            def __init__(self, path, directory=False): self.path, self.directory = path, directory
            def is_directory(self): return self.directory
            def get_location(self): return Location(self.path)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / 'script.py'; script.write_text('pass')
            ordinary = root / 'ordinary.txt'; ordinary.write_text('text')
            executable = root / 'launcher'; executable.write_text('binary'); executable.chmod(0o755)
            folder = root / 'folder'; folder.mkdir()
            provider = extension.WinDoesNotAdmin()
            with patch.object(extension, 'german', return_value=True):
                self.assertEqual(provider.get_file_items([File(str(ordinary))]), [])
                self.assertEqual(provider.get_file_items([File(str(folder), True)]), [])
                self.assertEqual(provider.get_file_items([File(str(script)), File(str(executable))]), [])
                self.assertEqual(provider.get_file_items([File(str(script))])[0].label, 'Als Administrator ausführen')
                self.assertEqual(provider.get_file_items([File(str(executable))])[0].label, 'Als Administrator ausführen')

    def test_filename_stays_one_argv_element_and_gui_environment_is_allowlisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'quote " ; $(not-shell) ü.py'
            path.write_text('pass')
            with patch.object(admin_cli.os, 'geteuid', return_value=1000), \
                    patch.object(admin_cli.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)) as run:
                self.assertEqual(admin_cli.run_root(path, {'WAYLAND_DISPLAY': 'wayland-1'}), 0)
            argv = run.call_args.args[0]
            self.assertEqual(argv[-2:], ['/usr/bin/python3', str(path)])
            self.assertNotIn('shell', argv)
            self.assertEqual(admin_cli.environment_for_root({
                'WAYLAND_DISPLAY': 'wayland-1', 'XDG_RUNTIME_DIR': '/run/user/1000',
                'DISPLAY': ':0', 'UNSAFE': 'ignored'}), {
                    'WAYLAND_DISPLAY': 'wayland-1', 'XDG_RUNTIME_DIR': '/run/user/1000', 'DISPLAY': ':0'})

    def test_terminal_argv_and_root_dispatch_keep_filename_unparsed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'script with spaces (ä).sh'
            path.write_text('true')
            with patch.object(admin_cli.shutil, 'which', side_effect=lambda name: '/usr/bin/ghostty' if name == 'ghostty' else None):
                terminal = admin_cli.terminal_command(Path('/usr/bin/windoesnot-run-as-admin'), path)
            self.assertEqual(terminal[-2:], ['--terminal-child', str(path)])
            with patch.object(admin_cli.os, 'geteuid', return_value=0), \
                    patch.object(admin_cli.subprocess, 'run', return_value=types.SimpleNamespace(returncode=7)) as run:
                result = admin_cli.main(['--root', '{"WAYLAND_DISPLAY":"wayland-1"}', '--', '/usr/bin/bash', str(path)])
            self.assertEqual(result, 7)
            self.assertEqual(run.call_args.args[0], ['/usr/bin/bash', str(path)])
            self.assertEqual(run.call_args.kwargs['env']['WAYLAND_DISPLAY'], 'wayland-1')


if __name__ == '__main__':
    unittest.main()
