#!/usr/bin/env python3
"""Exercise the post-transaction rebuild without root or a compiler."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-rebuild-plugins'


class RebuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'usr/share/windoesnot/plugins-src'
        self.target = self.root / 'usr/lib/windoesnot/plugins'
        self.bin = self.root / 'fake-bin'
        self.bin.mkdir()
        self.target.mkdir(parents=True)
        for name in ('hyprbars', 'hyprdrag'):
            folder = self.source / name
            folder.mkdir(parents=True)
            (folder / 'Makefile').write_text('all:\n')
            (self.target / f'{name}.so').write_text('old')
        (self.source / 'check-plugin-symbols.py').write_text(
            'import os, sys\n'
            'sys.exit(1 if os.environ.get("FAKE_CHECK_FAIL") else 0)\n')
        self.fake('pacman', '#!/bin/sh\nprintf "hyprland 0.57.1-1\\nlibstdc++ 16.2.1-1\\n"\n')
        self.fake('pkg-config', '#!/bin/sh\nexit 0\n')
        self.fake('make', '#!/bin/sh\n'
                  'while [ "$1" != "-C" ]; do shift; done\n'
                  'name=${2##*/}\n'
                  'if [ "$FAKE_MAKE_FAIL" = "$name" ]; then exit 1; fi\n'
                  'printf "new-%s" "$name" > "$2/$name.so"\n')
        self.env = os.environ.copy()
        self.env.update(WDN_REBUILD_TEST_ROOT=str(self.root),
                        PATH=str(self.bin) + os.pathsep + self.env['PATH'])

    def fake(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def invoke(self, **extra):
        return subprocess.run([sys.executable, str(SCRIPT)], env=self.env | extra,
                              capture_output=True, text=True)

    def test_build_and_current_marker(self):
        self.assertEqual(self.invoke().returncode, 0)
        marker = self.root / 'var/lib/windoesnot/plugins-built-for'
        self.assertIn('hyprland 0.57.1-1', marker.read_text())
        self.assertIn('libstdc++ 16.2.1-1', marker.read_text())
        for name in ('hyprbars', 'hyprdrag'):
            self.assertEqual((self.target / f'{name}.so').read_text(), f'new-{name}')
        self.fake('make', '#!/bin/sh\nexit 1\n')
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual((self.target / 'hyprbars.so').read_text(), 'new-hyprbars')

    def test_compiler_failure_keeps_both_originals(self):
        self.assertEqual(self.invoke(FAKE_MAKE_FAIL='hyprdrag').returncode, 0)
        for name in ('hyprbars', 'hyprdrag'):
            self.assertEqual((self.target / f'{name}.so').read_text(), 'old')
        self.assertFalse((self.root / 'var/lib/windoesnot/plugins-built-for').exists())
        self.assertIn('Plugin rebuild failed', (self.root / 'var/log/windoesnot-plugins-rebuild.log').read_text())

    def test_replace_failure_restores_both_originals(self):
        self.assertEqual(self.invoke(WDN_REBUILD_TEST_FAIL_AFTER_FIRST_REPLACE='1').returncode, 0)
        for name in ('hyprbars', 'hyprdrag'):
            self.assertEqual((self.target / f'{name}.so').read_text(), 'old')
        self.assertFalse((self.root / 'var/lib/windoesnot/plugins-built-for').exists())

    def test_symbol_failure_keeps_both_originals(self):
        self.assertEqual(self.invoke(FAKE_CHECK_FAIL='1').returncode, 0)
        for name in ('hyprbars', 'hyprdrag'):
            self.assertEqual((self.target / f'{name}.so').read_text(), 'old')


class TerminalRebuildTests(unittest.TestCase):
    fake = RebuildTests.fake
    invoke = RebuildTests.invoke

    def setUp(self):
        RebuildTests.setUp(self)
        # The terminal path is independent of the Hyprland plugin path.
        import shutil
        shutil.rmtree(self.source)
        self.terminal_source = self.root / 'usr/share/windoesnot/components-src/terminalmodule'
        self.terminal_source.mkdir(parents=True)
        (self.terminal_source / 'CMakeLists.txt').write_text('terminal source')
        self.terminal_target = self.root / 'usr/lib/windoesnot/LocalTerminal'
        self.terminal_target.mkdir()
        for name in ('qmldir', 'liblocalterminalplugin.so', 'liblocalterminalpluginplugin.so'):
            (self.terminal_target / name).write_text('old')
        self.fake('pacman', '#!/bin/sh\nprintf "qt6-base 6.12.0-4\\nqtermwidget 2.2.0-1\\nqt6-declarative 6.12.0-4\\n"\n')
        self.fake('cmake', '#!/bin/sh\n'
                  'if [ "$FAKE_CMAKE_FAIL" = 1 ]; then exit 1; fi\n'
                  'if [ "$1" = "-S" ]; then exit 0; fi\n'
                  'build=$2\n'
                  'out="${build%/*}/widgets/terminalmodule/LocalTerminal"\n'
                  'mkdir -p "$out"\n'
                  'printf "new-qml" > "$out/qmldir"\n'
                  'printf "new-main" > "$out/liblocalterminalplugin.so"\n'
                  'printf "new-plugin" > "$out/liblocalterminalpluginplugin.so"\n')
        self.fake('readelf', '#!/bin/sh\nprintf "0x0 (RUNPATH) Library runpath: [\\$ORIGIN]\\n"\n')

    def test_terminal_build_and_idempotence(self):
        self.assertEqual(self.invoke().returncode, 0)
        marker = self.root / 'var/lib/windoesnot/components-built-for'
        self.assertIn('qt6-base 6.12.0-4', marker.read_text())
        self.assertEqual((self.terminal_target / 'liblocalterminalplugin.so').read_text(), 'new-main')
        self.assertEqual(self.invoke(FAKE_CMAKE_FAIL='1').returncode, 0)
        self.assertEqual((self.terminal_target / 'liblocalterminalplugin.so').read_text(), 'new-main')
        import stat
        self.assertEqual(stat.S_IMODE(self.terminal_target.stat().st_mode), 0o755, 'normal users must be able to read the terminal module')

    def test_terminal_build_failure_keeps_original(self):
        self.assertEqual(self.invoke(FAKE_CMAKE_FAIL='1').returncode, 0)
        self.assertEqual((self.terminal_target / 'liblocalterminalplugin.so').read_text(), 'old')
        self.assertFalse((self.root / 'var/lib/windoesnot/components-built-for').exists())

    def test_terminal_exchange_failure_restores_original(self):
        self.assertEqual(self.invoke(WDN_REBUILD_TEST_FAIL_AFTER_COMPONENT_REPLACE='1').returncode, 0)
        self.assertEqual((self.terminal_target / 'liblocalterminalplugin.so').read_text(), 'old')
        self.assertFalse((self.root / 'var/lib/windoesnot/components-built-for').exists())

    def test_terminal_bad_runpath_keeps_original(self):
        self.fake('readelf', '#!/bin/sh\nprintf "0x0 (RUNPATH) Library runpath: [/tmp/build]\\n"\n')
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual((self.terminal_target / 'liblocalterminalplugin.so').read_text(), 'old')

    def test_terminal_failure_does_not_stop_plugins(self):
        for name in ('hyprbars', 'hyprdrag'):
            (self.source / name).mkdir(parents=True)
            (self.source / name / 'Makefile').write_text('all:\n')
        (self.source / 'check-plugin-symbols.py').write_text('pass\n')
        self.fake('pacman', '#!/bin/sh\n'
                  'if [ "$2" = hyprland ]; then printf "hyprland 0.57.1-1\\nlibstdc++ 16.2.1-1\\n"; '
                  'else printf "qt6-base 6.12.0-4\\nqtermwidget 2.2.0-1\\nqt6-declarative 6.12.0-4\\n"; fi\n')
        self.assertEqual(self.invoke(FAKE_CMAKE_FAIL='1').returncode, 0)
        self.assertEqual((self.target / 'hyprbars.so').read_text(), 'new-hyprbars')
        self.assertEqual((self.terminal_target / 'liblocalterminalplugin.so').read_text(), 'old')


if __name__ == '__main__':
    unittest.main()
