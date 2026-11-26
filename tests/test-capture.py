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


HYPR_MONITORS = [
    {'name': 'DP-1', 'x': 0, 'y': 0, 'width': 3840, 'height': 2160, 'scale': 2.0, 'transform': 0, 'focused': True,
     'activeWorkspace': {'id': 1}, 'specialWorkspace': {'id': 0}},
    {'name': 'HDMI-A-1', 'x': -1080, 'y': -200, 'width': 1920, 'height': 1080, 'scale': 1.0, 'transform': 1, 'focused': False,
     'activeWorkspace': {'id': 2}, 'specialWorkspace': {'id': 0}},
]


def client(address, ws, at, size, **extra):
    base = {'address': address, 'title': 'T' + address, 'class': 'c', 'mapped': True, 'hidden': False, 'floating': False,
            'workspace': {'id': ws}, 'at': at, 'size': size, 'focusHistoryID': 5}
    base.update(extra)
    return base


HYPR_CLIENTS = [
    client('0xa', 1, [10, 10], [500, 400], focusHistoryID=1),
    client('0xb', 1, [100, 100], [300, 200], floating=True, focusHistoryID=3),
    client('0xc', 3, [0, 0], [100, 100]),                       # workspace not visible
    client('0xd', 2, [-1000, 0], [800, 600], focusHistoryID=0),
    client('0xe', 1, [0, 0], [100, 100], mapped=False),
    client('0xf', 1, [0, 0], [100, 100], hidden=True),
    client('0xg', -99, [0, 0], [100, 100]),                     # special workspace, not shown
    client('0xh', 1, [0, 0], [0, 100]),
]
PNG_HEADER = b'\x89PNG\r\n\x1a\n' + b'\0\0\0\rIHDR' + (6000).to_bytes(4, 'big') + (3840).to_bytes(4, 'big')


def fake_hypr(argv, **kwargs):
    assert isinstance(argv, list) and 'shell' not in kwargs and kwargs.get('timeout'), (argv, kwargs)
    if argv[:2] == ['hyprctl', '-j']:
        data = {'monitors': HYPR_MONITORS, 'clients': HYPR_CLIENTS}[argv[2]]
        return subprocess.CompletedProcess(argv, 0, json.dumps(data), '')
    if argv[0] == 'grim':
        Path(argv[-1]).write_bytes(PNG_HEADER)
    return subprocess.CompletedProcess(argv, 0, '', '')


class OverlayBackendTests(unittest.TestCase):
    def test_monitor_logical_geometry(self):
        monitors = c.monitors_from_hyprctl(HYPR_MONITORS)
        self.assertEqual([(m['name'], m['x'], m['y'], m['width'], m['height']) for m in monitors],
                         [('DP-1', 0, 0, 1920, 1080), ('HDMI-A-1', -1080, -200, 1080, 1920)])
        self.assertEqual(c.bounds_of(monitors), {'x': -1080, 'y': -200, 'width': 3000, 'height': 1920})
        self.assertEqual(c.monitors_from_hyprctl([{'name': 'bad name;', 'width': 1, 'height': 1}, 'x', None]), [])
        self.assertEqual(c.monitors_from_hyprctl('nope'), [])

    def test_window_list_visible_topmost_first(self):
        monitors = c.monitors_from_hyprctl(HYPR_MONITORS)
        windows = c.windows_from_hyprctl(HYPR_CLIENTS, monitors)
        self.assertEqual([w['address'] for w in windows], ['0xb', '0xd', '0xa'])
        self.assertEqual(windows[1], {'address': '0xd', 'title': 'T0xd', 'class': 'c', 'x': -1000, 'y': 0,
                                      'width': 800, 'height': 600, 'workspace': 2})
        self.assertEqual(c.windows_from_hyprctl('junk', monitors), [])

    def test_crop_rect_scale_and_negative_coordinates(self):
        bounds, scale = {'x': -1080, 'y': -200, 'width': 3000, 'height': 1920}, 2.0
        self.assertEqual(c.crop_rect('-1080,-200 100x50', bounds, scale), (0, 0, 200, 100))
        self.assertEqual(c.crop_rect('0,0 960x540', bounds, scale), (2160, 400, 1920, 1080))
        self.assertEqual(c.crop_rect('1500,1500 1000x1000', bounds, scale), (5160, 3400, 840, 440))   # clamped to the image
        self.assertEqual(c.crop_rect('-1100,-300 40x1000', bounds, scale), (0, 0, 40, 1400))        # clamped at the origin
        with self.assertRaises(c.CaptureError): c.crop_rect('5000,5000 10x10', bounds, scale)
        with self.assertRaises(c.CaptureError): c.crop_rect('1,2 3x4; rm', bounds, scale)

    def test_crop_command_argv(self):
        self.assertEqual(c.crop_command('/r/s.png', '/o/a.png', (2160, 400, 1920, 1080), 'magick'),
                         ['magick', '/r/s.png', '-crop', '1920x1080+2160+400', '+repage', '/o/a.png'])
        for bad in ((-1, 0, 5, 5), (0, 0, 0, 5)):
            with self.assertRaises(c.CaptureError): c.crop_command('a', 'b', bad)

    def test_fresh_command(self):
        self.assertEqual(c.fresh_command('/o.png', '-5,6 70x80', True), ['grim', '-c', '-g', '-5,6 70x80', '/o.png'])
        self.assertEqual(c.fresh_command('/o.png', '1,2 3x4'), ['grim', '-g', '1,2 3x4', '/o.png'])

    def test_snapshot_json_with_fake_hyprctl_and_grim(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'snap.png'
            data = c.take_snapshot(out, fake_hypr)
            self.assertEqual([m['name'] for m in data['monitors']], ['DP-1', 'HDMI-A-1'])
            self.assertEqual(set(data['monitors'][0]), {'name', 'x', 'y', 'width', 'height', 'scale', 'focused'})
            self.assertEqual(len(data['windows']), 3)
            self.assertEqual(data['scale'], 2.0)
            self.assertEqual(data['pixels'], {'width': 6000, 'height': 3840})
            self.assertEqual(json.loads(c.sidecar_path(out).read_text()), data)
            self.assertEqual(c.load_snapshot(out)['bounds'], {'x': -1080, 'y': -200, 'width': 3000, 'height': 1920})
            with self.assertRaises(c.CaptureError): c.load_snapshot(Path(tmp) / 'missing.png')

    def test_shoot_crops_frozen_snapshot_or_grabs_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'snap.png'
            c.take_snapshot(out, fake_hypr)
            calls, sleeps = [], []
            def runner(argv, **kwargs):
                calls.append(argv)
                if argv[0] in ('magick', 'grim'):
                    Path(argv[-1]).write_bytes(b'png')
                return subprocess.CompletedProcess(argv, 0, '', '')
            kw = dict(now=NOW, home=tmp, runner=runner, sleep=sleeps.append, tool='magick')
            path = c.shoot('0,0 960x540', snapshot=out, copy=True, **kw)
            self.assertEqual(calls[0], ['magick', str(out), '-crop', '1920x1080+2160+400', '+repage', str(path)])
            self.assertEqual([x[0] for x in calls], ['magick', 'wl-copy', 'notify-send'])
            self.assertEqual(sleeps, [])
            calls.clear()
            c.shoot('0,0 960x540', snapshot=out, delay=3, settle=0.5, **kw)
            self.assertEqual(calls[0][:3], ['grim', '-g', '0,0 960x540'])
            self.assertEqual(sleeps, [3.5])
            calls.clear()
            c.shoot('0,0 960x540', snapshot=out, pointer=True, **kw)
            self.assertEqual(calls[0][:2], ['grim', '-c'])
            with self.assertRaises(c.CaptureError): c.shoot('0,0 5x5', snapshot=out, delay=4, **kw)
            with self.assertRaises(c.CaptureError): c.shoot('x', snapshot=out, **kw)

    def test_record_options_and_status(self):
        self.assertEqual(c.record_command('/v/r.mp4', output='DP-1'), ['wf-recorder', '-o', 'DP-1', '-f', '/v/r.mp4'])
        with self.assertRaises(c.CaptureError): c.record_command('/v/r.mp4', output='a b')
        with self.assertRaises(c.CaptureError): c.record_command('/v/r.mp4', '1,2 3x4', output='DP-1')
        class Proc: pid = 77
        seen = []
        def popen(argv, **kwargs): seen.append(argv); return Proc()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(c.status_json(tmp, lambda pid: True), {'recording': False})
            c.start_recording(geometry='1,2 30x40', audio=True, now=NOW, home=tmp, runtime=tmp, runner=FakeRunner(),
                              popen=popen, alive=lambda pid: False, clock=lambda: 1000)
            self.assertEqual(seen[0][:4], ['wf-recorder', '-g', '1,2 30x40', '--audio'])
            status = c.status_json(tmp, lambda pid: True, clock=lambda: 1005)
            self.assertEqual((status['recording'], status['started'], status['now']), (True, 1000, 1005))

    def test_open_overlay_stops_recording_closes_or_opens(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'home'
            cfg = home / '.config/quickshell/capture'
            cfg.mkdir(parents=True)
            (cfg / 'shell.qml').write_text('x')
            popens, kills = [], []
            class Proc: pid = 31337
            def popen(argv, **kwargs):
                popens.append((argv, kwargs)); return Proc()
            kw = dict(runtime=tmp, home=home, runner=fake_hypr, popen=popen, sleep=lambda s: None,
                      kill=lambda pid, sig: kills.append((pid, sig)))
            with self.assertRaises(c.CaptureError): c.open_overlay('bogus', **kw)
            self.assertEqual(c.open_overlay('record', alive=lambda pid: True, rec_alive=lambda pid: False, **kw), 'opened')
            argv, kwargs = popens[0]
            self.assertEqual(argv, ['quickshell', '--path', str(cfg / 'shell.qml')])
            self.assertEqual(kwargs['env']['WINDOESNOT_CAPTURE_TAB'], 'record')
            self.assertTrue(Path(kwargs['env']['WINDOESNOT_CAPTURE_DATA']).is_file())
            self.assertNotIn('shell', kwargs)
            self.assertEqual(c.open_overlay('screenshot', alive=lambda pid: True, rec_alive=lambda pid: False, **kw), 'closed')
            self.assertEqual(kills, [(31337, signal.SIGTERM)])
            (Path(tmp) / c.PID_NAME).write_text(json.dumps({'pid': 9, 'file': 'x.mp4'}))
            self.assertEqual(c.open_overlay('screenshot', alive=lambda pid: True, rec_alive=lambda pid: True, **kw), 'stopped')
            self.assertEqual(kills[-1], (9, signal.SIGINT))
            self.assertEqual(len(popens), 1)

    def test_cli_new_commands_validate(self):
        for argv in (['shoot'], ['shoot', '--geometry', 'x'], ['shoot', '--geometry', '1,2 3x4', '--delay', '4'],
                     ['shoot', '--geometry', '1,2 3x4', '--settle', '99'], ['snapshot'], ['overlay', '--tab', 'x'],
                     ['record-start', '--output', 'a b'], ['record-start', '--bogus'], ['overlay', '--tab']):
            self.assertEqual(c.main(argv), 1, argv)


class SourceTests(unittest.TestCase):
    def test_no_shell_and_packaged(self):
        source = (ROOT / 'desktop/lib/windoesnot/capture.py').read_text()
        self.assertNotIn('shell=True', source); self.assertNotIn('os.system', source)
        self.assertIn('wf-recorder', (ROOT / 'iso/packages-extra.txt').read_text().split())
        pkg = (ROOT / 'packaging/PKGBUILD.in').read_text()
        self.assertIn('windoesnot-capture.desktop', pkg); self.assertIn('lib/windoesnot/capture.py', pkg)
        binds = (ROOT / 'desktop/config/hypr/lua/bindings.lua').read_text()
        self.assertIn('hl.bind("SUPER + SHIFT + S", hl.dsp.exec_cmd("windoesnot-capture overlay --tab screenshot")', binds)
        self.assertIn('hl.bind("PRINT", hl.dsp.exec_cmd("windoesnot-capture overlay --tab screenshot")', binds)
        self.assertIn('hl.bind("SUPER + SHIFT + R", hl.dsp.exec_cmd("windoesnot-capture overlay --tab record")', binds)
        self.assertIn('hl.bind("SUPER + PRINT", hl.dsp.exec_cmd("windoesnot-capture screen --copy")', binds)


if __name__ == '__main__':
    unittest.main()
