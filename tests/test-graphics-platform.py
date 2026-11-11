#!/usr/bin/env python3
"""Distinguish unsupported Apple telemetry from a missing LACT installation."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gpu_status', ROOT / 'desktop/config/quickshell/default/widgets/gpu_status.py')
gpu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gpu)


class GraphicsPlatform(unittest.TestCase):
    def status(self, model, render=False):
        with patch.object(gpu, 'read', return_value=model), patch.object(gpu.shutil, 'which', return_value=None), patch.object(gpu, 'service', return_value=False), patch.object(gpu.glob, 'glob', return_value=['render'] if render else []), patch.object(gpu, 'list_gpus') as lact, contextlib.redirect_stdout(io.StringIO()) as output:
            gpu.main()
            lact.assert_not_called()
        return json.loads(output.getvalue())

    def test_apple_framebuffer_is_not_a_missing_lact_error(self):
        state = self.status('Apple MacBook Pro\x00')
        self.assertTrue(state['apple'])
        self.assertFalse(state['renderAvailable'])
        self.assertEqual(state['model'], 'Apple MacBook Pro')
        self.assertFalse(state['running'])

    def test_apple_with_render_node_is_distinguished(self):
        self.assertTrue(self.status('Apple MacBook Air', True)['renderAvailable'])

    def test_pc_keeps_lact_installation_path(self):
        state = self.status('')
        self.assertFalse(state['apple'])
        self.assertFalse(state['lact'])


if __name__ == '__main__':
    unittest.main()
