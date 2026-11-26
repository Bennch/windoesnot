#!/usr/bin/env python3
"""Capture backend: command building, validation, naming and pidfile logic with fakes."""
import datetime
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('capture', ROOT / 'desktop/lib/windoesnot/capture.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
NOW = datetime.datetime(2026, 3, 4, 5, 6, 7)


class FakeRunner:
    def __init__(self, create=None, returncode=0, stdout=''):
        self.calls, self.create, self.returncode, self.stdout = [], create, returncode, stdout
    def __call__(self, argv, **kwargs):
        assert isinstance(argv, list) and 'shell' not in kwargs and kwargs.get('timeout'), (argv, kwargs)
        self.calls.append(argv)
        if self.create and argv[0] in ('grim', 'hyprshot'):
            self.create.write_bytes(b'png')
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, '')


class CaptureTests(unittest.TestCase):
    def test_filenames_with_injected_clock(self):
        home = Path('/home/u')
        self.assertEqual(c.screenshot_path(NOW, home), home / 'Pictures/Screenshots/Screenshot_2026-03-04_05-06-07.png')
        self.assertEqual(c.recording_path(NOW, home), home / 'Videos/Recordings/Recording_2026-03-04_05-06-07.mp4')

    def test_screenshot_commands(self):
        p = Path('/h/Pictures/Screenshots/a.png')
        self.assertEqual(c.screenshot_command('region', p), ['hyprshot', '-m', 'region', '-z', '--silent', '-o', '/h/Pictures/Screenshots', '-f', 'a.png'])
        self.assertEqual(c.screenshot_command('window', p)[:3], ['hyprshot', '-m', 'window'])
        self.assertEqual(c.screenshot_command('screen', p), ['grim', str(p)])
        self.assertEqual(c.screenshot_command('monitor', p, 'DP-1'), ['grim', '-o', 'DP-1', str(p)])

    def test_validation_refusals(self):
        p = Path('/x/a.png')
        for bad in ('', 'full', 'region; rm', None):
            with self.assertRaises(c.CaptureError): c.screenshot_command(bad, p)
        for bad in ('', '-o x', 'a b', 'DP-1;ls', '$(x)', 'a' * 70, None):
            with self.assertRaises(c.CaptureError): c.screenshot_command('monitor', p, bad)
        for bad in (1, 7, -3, '3', True, None, 3.0):
            with self.assertRaises(c.CaptureError): c.validate_delay(bad)
        for good in c.DELAYS: self.assertEqual(c.validate_delay(good), good)
        for bad in ('0,0 0x5', '1,2 3', 'x', '1,2 3x4; ls', '0,0 10x10\n'):
            with self.assertRaises(c.CaptureError): c.record_command('/x.mp4', bad)

    def test_take_screenshot_all_modes_and_delays(self):
        for mode in ('region', 'window', 'screen', 'monitor'):
            for delay in c.DELAYS:
                with tempfile.TemporaryDirectory() as home:
                    path = c.screenshot_path(NOW, home)
                    path.parent.mkdir(parents=True)
                    runner, sleeps = FakeRunner(create=path), []
                    got = c.take_screenshot(mode, delay, True, 'DP-1', NOW, home, runner, sleeps.append)
                    self.assertEqual(got, path)
                    self.assertEqual(sleeps, [delay] if delay else [])
                    names = [call[0] for call in runner.calls]
                    self.assertEqual(names, [('hyprshot' if mode in ('region', 'window') else 'grim'), 'wl-copy', 'notify-send'])
                    self.assertIn(str(path), runner.calls[-1])

    def test_cancelled_selection_and_failure(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertIsNone(c.take_screenshot('region', 0, False, None, NOW, home, FakeRunner(), lambda s: None))
            with self.assertRaises(c.CaptureError):
                c.take_screenshot('region', 0, False, None, NOW, home, FakeRunner(returncode=1), lambda s: None)
            with self.assertRaises(c.CaptureError): c.take_screenshot('screen', 4, home=home)

    def test_record_command(self):
        self.assertEqual(c.record_command('/v/r.mp4'), ['wf-recorder', '-f', '/v/r.mp4'])
        self.assertEqual(c.record_command('/v/r.mp4', '10,20 300x400', True), ['wf-recorder', '-g', '10,20 300x400', '--audio', '-f', '/v/r.mp4'])

    def test_pidfile_start_toggle_stop(self):
        alive_pids = set()
        killed = []
        class Proc: pid = 4242
        def popen(argv, **kwargs):
            self.assertEqual(argv[0], 'wf-recorder'); self.assertNotIn('shell', kwargs)
            alive_pids.add(Proc.pid); return Proc()
        def kill(pid, sig): killed.append((pid, sig)); alive_pids.discard(pid)
        alive = lambda pid: pid in alive_pids
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRunner(stdout='5,6 70x80\n')
            kw = dict(now=NOW, home=tmp, runtime=tmp, runner=run, alive=alive)
            self.assertFalse(c.is_recording(tmp, alive))
            action, path = c.toggle_recording(region=True, popen=popen, **kw)
            self.assertEqual(action, 'started')
            self.assertEqual(run.calls[0][0], 'slurp')
            self.assertTrue(c.is_recording(tmp, alive))
            self.assertEqual(json.loads((Path(tmp) / c.PID_NAME).read_text())['pid'], 4242)
            with self.assertRaises(c.CaptureError): c.start_recording(popen=popen, **kw)
            action, stopped = c.toggle_recording(kill=kill, sleep=lambda s: None, **kw)
            self.assertEqual((action, stopped), ('stopped', path))
            self.assertEqual(killed, [(4242, signal.SIGINT)])
            self.assertFalse((Path(tmp) / c.PID_NAME).exists())
            self.assertEqual(run.calls[-1][0], 'notify-send')

    def test_stale_and_corrupt_pidfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / c.PID_NAME
            pidfile.write_text(json.dumps({'pid': 99, 'file': 'x'}))
            self.assertIsNone(c.read_state(tmp, lambda pid: False)); self.assertFalse(pidfile.exists())
            for junk in ('garbage', '{"pid": 1}', '{"pid": "x"}', '[]'):
                pidfile.write_text(junk)
                self.assertIsNone(c.read_state(tmp, lambda pid: True)); self.assertFalse(pidfile.exists())
            self.assertIsNone(c.stop_recording(tmp, lambda pid: True))

    def test_region_cancel_starts_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            def popen(*a, **k): raise AssertionError('must not start')
            self.assertIsNone(c.start_recording(region=True, home=tmp, runtime=tmp, runner=FakeRunner(returncode=1), popen=popen))

    def test_cli_rejects_bad_arguments(self):
        self.assertEqual(c.main([]), 2)
        self.assertEqual(c.main(['bogus']), 2)
        self.assertEqual(c.main(['screen', '--delay', '4']), 1)


class SourceTests(unittest.TestCase):
    def test_no_shell_and_packaged(self):
        source = (ROOT / 'desktop/lib/windoesnot/capture.py').read_text()
        self.assertNotIn('shell=True', source); self.assertNotIn('os.system', source)
        self.assertIn('wf-recorder', (ROOT / 'iso/packages-extra.txt').read_text().split())
        pkg = (ROOT / 'packaging/PKGBUILD.in').read_text()
        self.assertIn('windoesnot-capture.desktop', pkg); self.assertIn('lib/windoesnot/capture.py', pkg)
        binds = (ROOT / 'desktop/config/hypr/lua/bindings.lua').read_text()
        self.assertIn('hl.bind("SUPER + SHIFT + S", hl.dsp.exec_cmd("windoesnot-capture region")', binds)
        self.assertIn('"PRINT", hl.dsp.exec_cmd("windoesnot-screenshot region")', binds)


if __name__ == '__main__':
    unittest.main()
