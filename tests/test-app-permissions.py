#!/usr/bin/env python3
"""Exercise the same parser and argv builder used by the settings page."""
from pathlib import Path
import subprocess
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'desktop/config/quickshell/default/settings/FlatpakPermissionParser.js'

class PermissionsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "requires Node.js to run the shared JavaScript parser")
    def test_parser_and_commands(self):
        program = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const ctx = {}; vm.createContext(ctx); vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const base = '[Context]\nshared=network;ipc;\nfilesystems=home;xdg-download:ro;\ndevices=dri;\n[Session Bus Policy]\norg.example=talk\n';
const override = '[Context]\nshared=!network;\nfilesystems=!home;\ndevices=all;\n';
const state = ctx.parse(override, ctx.parse(base));
assert(!ctx.has(state, 'shared', 'network')); assert(ctx.has(state, 'shared', 'ipc'));
assert(!ctx.has(state, 'filesystems', 'home')); assert(ctx.has(state, 'filesystems', 'xdg-download'));
assert.strictEqual(state['Session Bus Policy']['org.example'], 'org.example=talk');
assert(ctx.has(state, 'devices', 'all')); assert(ctx.has(state, 'devices', 'dri'));
assert(!ctx.validId('../bad')); assert(!ctx.validId('bad;id')); assert(ctx.validId('org.example.App-1'));
assert.throws(() => ctx.command('reset', 'bad;id')); assert.throws(() => ctx.command('invalid', 'org.example.App'));
assert.deepStrictEqual(Array.from(ctx.command('network', 'org.example.App', false)), ['windoesnot-bounded','15','flatpak','override','--user','--noshare=network','org.example.App']);
assert.deepStrictEqual(Array.from(ctx.command('home', 'org.example.App', true)).slice(-2), ['--filesystem=home','org.example.App']);
assert.deepStrictEqual(Array.from(ctx.command('devices', 'org.example.App', false)).slice(-2), ['--nodevice=all','org.example.App']);
assert.deepStrictEqual(Array.from(ctx.command('reset', 'org.example.App')).slice(-2), ['--reset','org.example.App']);
assert.deepStrictEqual(Array.from(ctx.command('portalReset', 'org.example.App')).slice(-2), ['permission-reset','org.example.App']);
assert.strictEqual(ctx.apps('org.example.App\tExample\ninvalid id\tBad\n').length, 1);
assert.strictEqual(ctx.portals('camera\tcamera\torg.example.App\tyes\t\ncamera\tcamera\tother.App\tno\t', 'org.example.App'), 'camera\tcamera\torg.example.App\tyes\t');
'''
        subprocess.run(['node', '-e', program, str(JS)], check=True, timeout=10)

if __name__ == '__main__':
    unittest.main()
