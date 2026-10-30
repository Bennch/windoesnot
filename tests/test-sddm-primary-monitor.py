#!/usr/bin/env python3
"""Parser checks for the Xsetup helper that points X11's primary RandR
output at Hyprland's main monitor, matched by EDID (not by connector name,
since the two display stacks do not have to agree on those)."""
import base64
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / 'desktop/share/sddm/themes/windoesnot/set-primary-monitor.py'
spec = importlib.util.spec_from_file_location('set_primary_monitor', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def state_lua(data):
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    return '-- state-json:' + encoded + '\nreturn {}\n'


class LastUser(unittest.TestCase):
    def test_reads_user_from_last_section(self):
        with _tmp_file('[Last]\nSession=hyprland.desktop\nUser=benni\n') as path:
            self.assertEqual(mod.last_user(path), 'benni')

    def test_missing_file_returns_none(self):
        self.assertIsNone(mod.last_user(Path('/nonexistent/state.conf')))

    def test_missing_user_key_returns_none(self):
        with _tmp_file('[Last]\nSession=hyprland.desktop\n') as path:
            self.assertIsNone(mod.last_user(path))


class PrimaryMonitorName(unittest.TestCase):
    def test_extracts_primary_monitor(self):
        with _tmp_home() as home:
            state = home / '.config/hypr/lua/state.lua'
            state.parent.mkdir(parents=True)
            state.write_text(state_lua({'primary_monitor': 'DP-2', 'monitors': []}))
            self.assertEqual(mod.primary_monitor_name(home), 'DP-2')

    def test_missing_state_file_returns_none(self):
        with _tmp_home() as home:
            self.assertIsNone(mod.primary_monitor_name(home))

    def test_non_marker_first_line_returns_none(self):
        with _tmp_home() as home:
            state = home / '.config/hypr/lua/state.lua'
            state.parent.mkdir(parents=True)
            state.write_text('return {}\n')
            self.assertIsNone(mod.primary_monitor_name(home))

    def test_corrupt_base64_returns_none(self):
        with _tmp_home() as home:
            state = home / '.config/hypr/lua/state.lua'
            state.parent.mkdir(parents=True)
            state.write_text('-- state-json:not-valid-base64!!\nreturn {}\n')
            self.assertIsNone(mod.primary_monitor_name(home))


class ConnectorEdidHex(unittest.TestCase):
    def test_reads_matching_connector_edid(self):
        with _tmp_home() as root:
            drm = root / 'drm'
            (drm / 'card1-DP-2').mkdir(parents=True)
            (drm / 'card1-DP-2/edid').write_bytes(b'\x00\xff\x01\x02')
            self.assertEqual(mod.connector_edid_hex('DP-2', drm_root=str(drm)), '00ff0102')

    def test_no_match_returns_none(self):
        with _tmp_home() as root:
            drm = root / 'drm'
            drm.mkdir()
            self.assertIsNone(mod.connector_edid_hex('DP-2', drm_root=str(drm)))

    def test_empty_edid_file_is_skipped(self):
        with _tmp_home() as root:
            drm = root / 'drm'
            (drm / 'card0-DP-2').mkdir(parents=True)
            (drm / 'card0-DP-2/edid').write_bytes(b'')
            self.assertIsNone(mod.connector_edid_hex('DP-2', drm_root=str(drm)))


XRANDR_VERBOSE = '''Screen 0: minimum 16 x 16, current 5080 x 2560, maximum 32767 x 32767
HDMI-A-1 connected 1920x1080+0+0 (0x47) normal (normal left inverted right x axis y axis) 600mm x 340mm
\tIdentifier: 0x21
\tEDID:
\t\t00ffffffffffff0005e3
\t\t022000000000
\tscaling mode: Full aspect
DFP-3 connected primary 2560x1440+1804+614 (0x48) normal (normal left inverted right x axis y axis) 597mm x 336mm
\tIdentifier: 0x22
\tEDID:
\t\taabbccddeeff00112233
\t\t44556677
\tscaling mode: Full aspect
DFP-1 connected 2560x1440+4364+54 (0x49) left (normal left inverted right x axis y axis) 597mm x 336mm
\tIdentifier: 0x23
\tEDID:
\t\t998877665544332211
DFP-5 disconnected (0x4a)
\tIdentifier: 0x24
'''


class XrandrOutputEdids(unittest.TestCase):
    def test_parses_connected_outputs_with_edid(self):
        outputs = mod.xrandr_output_edids(XRANDR_VERBOSE)
        self.assertEqual(outputs['HDMI-A-1'], '00ffffffffffff0005e3022000000000')
        self.assertEqual(outputs['DFP-3'], 'aabbccddeeff0011223344556677')
        self.assertEqual(outputs['DFP-1'], '998877665544332211')

    def test_disconnected_outputs_are_excluded(self):
        outputs = mod.xrandr_output_edids(XRANDR_VERBOSE)
        self.assertNotIn('DFP-5', outputs)

    def test_no_connected_outputs_returns_empty(self):
        self.assertEqual(mod.xrandr_output_edids('DFP-5 disconnected (0x4a)\n'), {})


import contextlib
import shutil
import tempfile


@contextlib.contextmanager
def _tmp_file(content):
    directory = tempfile.mkdtemp(prefix='windoesnot-sddm-primary-')
    try:
        path = Path(directory) / 'state.conf'
        path.write_text(content)
        yield path
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@contextlib.contextmanager
def _tmp_home():
    directory = tempfile.mkdtemp(prefix='windoesnot-sddm-primary-')
    try:
        yield Path(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
