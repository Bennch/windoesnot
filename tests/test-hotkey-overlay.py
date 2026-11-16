#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LUA = ROOT / 'desktop/config/hypr/lua'
QML = ROOT / 'desktop/config/quickshell/default'


class ShortcutOverlayTests(unittest.TestCase):
    def test_live_source_and_entry_points(self):
        overlay = (QML / 'ShortcutOverlay.qml').read_text()
        self.assertIn('/hypr/lua/bindings.lua', overlay)
        self.assertIn('root.parseBindings(text())', overlay)
        self.assertIn('HyprlandFocusGrab', overlay)
        self.assertIn('sequence: "Escape"', overlay)
        self.assertIn('toggle-shortcuts', (QML / 'shell.qml').read_text())
        self.assertIn('toggle-shortcuts', (QML / 'settings/HelpCategory.qml').read_text())
        self.assertIn('toggle-shortcuts', (ROOT / 'desktop/share/applications/windoesnot-shortcuts.desktop').read_text())

    def test_binding_unique_and_parser_covers_every_binding(self):
        entries = []
        for path in LUA.glob('*.lua'):
            for line in path.read_text().splitlines():
                if re.search(r'\bhl\.bind\s*\(', line):
                    match = re.match(r'^\s*hl\.bind\("([^\"]+)",\s*hl\.dsp\.([^\(]+)\((.*)', line)
                    self.assertIsNotNone(match, f'{path.name}: {line}')
                    entries.append((path.name, match.group(1).upper()))
        self.assertEqual([p for p, key in entries if key == 'SUPER + F1'], ['bindings.lua'])
        self.assertTrue(all(p == 'bindings.lua' for p, key in entries))
        self.assertEqual(len(entries), len(set(entries)))

    def test_checklist_state_and_windows_probe(self):
        helper = ROOT / 'desktop/bin/windoesnot-welcome-state'
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bin_dir = base / 'bin'
            bin_dir.mkdir()
            lsblk = bin_dir / 'lsblk'
            lsblk.write_text("#!/bin/sh\necho '{\"blockdevices\":[{\"children\":[{\"fstype\":\"ntfs\"}]}]}'\n")
            lsblk.chmod(0o755)
            env = {**os.environ, 'XDG_CONFIG_HOME': str(base / 'config'), 'PATH': str(bin_dir)}
            def run(*args):
                return subprocess.check_output([sys.executable, str(helper), *args], env=env, text=True)
            self.assertTrue(json.loads(run())['windows'])
            run('wifi', 'true')
            run('backup', 'true')
            run('wifi', 'false')
            self.assertEqual(json.loads(run())['state'], {'wifi': False, 'backup': True})
            self.assertEqual([p.name for p in (base / 'config/windoesnot').iterdir()], ['welcome-checklist.json'])
            lsblk.write_text("#!/bin/sh\necho '{\"blockdevices\":[{\"fstype\":\"ext4\"}]}'\n")
            self.assertFalse(json.loads(run())['windows'])

    def test_translation_keys_match(self):
        def keys(lang):
            return set(re.findall(r'"(shortcuts\.[^"]+)"\s*:', (QML / f'i18n/{lang}.js').read_text()))
        self.assertEqual(keys('de'), keys('en'))
        self.assertTrue({'shortcuts.title', 'shortcuts.migrate', 'shortcuts.done'} <= keys('de'))


if __name__ == '__main__':
    unittest.main()
