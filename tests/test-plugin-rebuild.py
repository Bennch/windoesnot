#!/usr/bin/env python3
"""Exercise the post-transaction rebuild without root or a compiler."""
from pathlib import Path
import os
import fcntl
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-rebuild-plugins'
HOOK = Path(__file__).resolve().parents[1] / 'desktop/share/libalpm/hooks/90-windoesnot-plugins.hook'
ELF = b'\x7fELF\x02\x01' + bytes(10) + b'\x03\x00\x3e\x00' + bytes(44)

def binary(path):
    return path.read_bytes()[64:].decode()



class RebuildTests(unittest.TestCase):
    def test_hook_targets(self):
        hook = HOOK.read_text()
        for operation in ('Install', 'Upgrade', 'Remove'):
            self.assertIn(f'Operation = {operation}', hook)
        for package in ('hyprland', 'gcc-libs', 'qt6-base', 'qtermwidget',
                        'qt6-declarative', 'windoesnot-plugins', 'windoesnot-components', 'windoesnot-tools'):
            self.assertIn(f'Target = {package}', hook)

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
                  'python3 -c \'import sys; open(sys.argv[1], "wb").write(bytes.fromhex("7f454c460201") + bytes(10) + bytes.fromhex("03003e00") + bytes(44) + ("new-" + sys.argv[2]).encode())\' "$2/$name.so" "$name"\n')
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
            self.assertEqual(binary(self.target / f'{name}.so'), f'new-{name}')
        self.fake('make', '#!/bin/sh\nexit 1\n')
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(binary(self.target / 'hyprbars.so'), 'new-hyprbars')

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

    def test_lock_prevents_parallel_build(self):
        lock = self.root / 'var/lib/windoesnot/rebuild.lock'
        lock.parent.mkdir(parents=True)
        with lock.open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self.assertEqual(self.invoke().returncode, 0)
            self.assertEqual((self.target / 'hyprbars.so').read_text(), 'old')
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(binary(self.target / 'hyprbars.so'), 'new-hyprbars')

    def test_crash_after_exchange_repairs_next_run(self):
        self.assertEqual(self.invoke(WDN_REBUILD_TEST_KILL_AFTER_REPLACE='1').returncode, 0)
        self.assertFalse((self.root / 'var/lib/windoesnot/plugins-built-for').exists())
        self.assertEqual(binary(self.target / 'hyprbars.so'), 'new-hyprbars')
        self.assertEqual(binary(self.target / 'hyprdrag.so'), 'new-hyprdrag')
        self.assertEqual(self.invoke().returncode, 0)
        self.assertTrue((self.root / 'var/lib/windoesnot/plugins-built-for').exists())

    def test_hostile_build_environment_is_ignored(self):
        self.assertEqual(self.invoke(CXX='/bin/false', CC='/bin/false', MAKEFLAGS='-f /bin/false',
                                     CMAKE_PREFIX_PATH='/invalid', LD_PRELOAD='/invalid').returncode, 0)
        self.assertEqual(binary(self.target / 'hyprbars.so'), 'new-hyprbars')

    def test_unsafe_target_permissions_and_symlink_abort(self):
        self.target.chmod(0o777)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual((self.target / 'hyprbars.so').read_text(), 'old')
        self.target.chmod(0o755)
        shutil.rmtree(self.target)
        elsewhere = self.root / 'elsewhere'
        elsewhere.mkdir()
        self.target.symlink_to(elsewhere, target_is_directory=True)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertFalse((self.root / 'var/lib/windoesnot/plugins-built-for').exists())

    def test_empty_result_with_valid_marker_rebuilds(self):
        self.assertEqual(self.invoke().returncode, 0)
        (self.target / 'hyprbars.so').write_bytes(b'')
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(binary(self.target / 'hyprbars.so'), 'new-hyprbars')

    def test_package_overwrite_then_failed_rebuild_restores_last_good(self):
        self.assertEqual(self.invoke().returncode, 0)
        marker = self.root / 'var/lib/windoesnot/plugins-built-for'
        saved = marker.read_text()
        for name in ('hyprbars', 'hyprdrag'):
            (self.target / f'{name}.so').write_text('packaged')
        (self.source / 'hyprbars/Makefile').write_text('changed source\n')
        self.assertEqual(self.invoke(FAKE_MAKE_FAIL='hyprdrag').returncode, 0)
        for name in ('hyprbars', 'hyprdrag'):
            self.assertEqual(binary(self.target / f'{name}.so'), f'new-{name}')
        self.assertEqual(marker.read_text(), saved)
        self.assertIn('Plugin rebuild failed', (self.root / 'var/log/windoesnot-plugins-rebuild.log').read_text())

    def test_package_remove_cleans_marker_and_backup(self):
        self.assertEqual(self.invoke().returncode, 0)
        shutil.rmtree(self.source)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertFalse((self.root / 'var/lib/windoesnot/plugins-built-for').exists())
        self.assertFalse((self.root / 'var/lib/windoesnot/plugins-last-good').exists())


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
                  'python3 -c \'import sys; open(sys.argv[1], "wb").write(bytes.fromhex("7f454c460201") + bytes(10) + bytes.fromhex("03003e00") + bytes(44) + b"new-main")\' "$out/liblocalterminalplugin.so"\n'
                  'python3 -c \'import sys; open(sys.argv[1], "wb").write(bytes.fromhex("7f454c460201") + bytes(10) + bytes.fromhex("03003e00") + bytes(44) + b"new-plugin")\' "$out/liblocalterminalpluginplugin.so"\n')
        self.fake('readelf', '#!/bin/sh\nprintf "0x0 (RUNPATH) Library runpath: [\\$ORIGIN]\\n"\n')

    def test_terminal_build_and_idempotence(self):
        self.assertEqual(self.invoke().returncode, 0)
        marker = self.root / 'var/lib/windoesnot/components-built-for'
        self.assertIn('qt6-base 6.12.0-4', marker.read_text())
        self.assertEqual(binary(self.terminal_target / 'liblocalterminalplugin.so'), 'new-main')
        self.assertEqual(self.invoke(FAKE_CMAKE_FAIL='1').returncode, 0)
        self.assertEqual(binary(self.terminal_target / 'liblocalterminalplugin.so'), 'new-main')
        import stat
        self.assertEqual(stat.S_IMODE(self.terminal_target.stat().st_mode), 0o755, 'normal users must be able to read the terminal module')
        for path in self.terminal_target.rglob('*'):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755 if path.is_dir() else
                             (0o755 if os.access(path, os.X_OK) else 0o644))

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
        self.assertEqual(binary(self.target / 'hyprbars.so'), 'new-hyprbars')
        self.assertEqual((self.terminal_target / 'liblocalterminalplugin.so').read_text(), 'old')


if __name__ == '__main__':
    unittest.main()
