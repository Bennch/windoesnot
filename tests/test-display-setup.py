#!/usr/bin/env python3
"""First-start display helper: mode list, request building and input checks, no desktop needed."""
import importlib.machinery
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader('display_setup', str(ROOT / 'desktop/bin/windoesnot-display-setup'))
spec = importlib.util.spec_from_loader('display_setup', loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)

MONITORS = [
    {'name': 'DP-1', 'focused': False, 'width': 1920, 'height': 1080, 'refreshRate': 60.0, 'scale': 1.0, 'x': 0, 'y': 0,
     'transform': 0, 'availableModes': ['1920x1080@60.00Hz']},
    {'name': 'DP-2', 'focused': True, 'width': 2560, 'height': 1440, 'refreshRate': 144.0, 'scale': 1.0, 'x': 1920, 'y': 0,
     'transform': 0, 'availableModes': ['2560x1440@144.00Hz', '2560x1440@60.00Hz', '1920x1080@120.00Hz', '1920x1080@60.00Hz', 'junk']},
]


class DisplaySetup(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(m, 'preferred_primary', return_value='')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_modes_keep_best_refresh_per_resolution(self):
        modes = m.mode_list(MONITORS[1])
        self.assertEqual([(x['width'], x['height'], x['refreshRate']) for x in modes], [(2560, 1440, 144.0), (1920, 1080, 120.0)])

    def test_primary_from_settings_wins_over_focus(self):
        with patch.object(m, 'preferred_primary', return_value='DP-1'):
            self.assertEqual(m.pick_primary(MONITORS)['name'], 'DP-1')

    def test_request_changes_only_the_primary(self):
        request = m.build_request(MONITORS, 1920, 1080, 1.5)['monitors']
        self.assertEqual(request['primary'], 'DP-2')
        by_name = {s['name']: s for s in request['monitors']}
        self.assertEqual((by_name['DP-2']['width'], by_name['DP-2']['refreshRate'], by_name['DP-2']['scale']), (1920, 120.0, 1.5))
        self.assertEqual((by_name['DP-1']['width'], by_name['DP-1']['scale']), (1920, 1.0))

    def test_rejects_unknown_resolution_and_zoom(self):
        with self.assertRaises(ValueError):
            m.build_request(MONITORS, 800, 600, 1.0)
        with self.assertRaises(ValueError):
            m.build_request(MONITORS, 1920, 1080, 3.0)


if __name__ == '__main__':
    unittest.main()
