#!/usr/bin/env python3
"""Synthetic cross-language credential envelopes; no real browser data."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'desktop/lib/windoesnot/migrate.py'
spec = importlib.util.spec_from_file_location('migrate', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp); root = base / 'windows'; home = base / 'home'
    home.mkdir(); handoff = root / 'WinDoesNotHandoff'; handoff.mkdir(parents=True)
    (handoff / 'manifest.json').write_text(json.dumps({'schema': 1, 'locale': 'de_DE', 'windows_version': '11.0', 'profiles': {}, 'wlan': False}))
    password = 'päss word'
    payload = json.dumps({'browser': 'Chrome', 'logins': [{'url': 'https://example.invalid', 'username': 'test', 'password': 'synthetic,secret'}], 'cookies': []}).encode()
    salt, nonce = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000, 32)
    envelope = b'IGCRD001' + salt + nonce + AESGCM(key).encrypt(nonce, payload, None)
    source = handoff / 'chromium-chrome.igcred'; source.write_bytes(envelope)
    plan = m.scan_tree(root)
    assert plan['handoff']['chromium_envelope']
    assert not m.copy_manifest(plan, home, source_root=root)['errors']
    assert not (home / 'Umzug-Windows').exists()
    for bad in ('wrong',):
        result = m.copy_manifest(plan, home, source_root=root, envelope_password=bad)
        assert result['errors'] and 'synthetic' not in str(result)
        assert not (home / 'Umzug-Windows').exists()
    damaged = bytearray(envelope); damaged[-1] ^= 1; source.write_bytes(damaged)
    assert m.copy_manifest(plan, home, source_root=root, envelope_password=password)['errors']
    assert not (home / 'Umzug-Windows').exists()
    source.write_bytes(envelope)
    for n in (1, 2):
        result = m.copy_manifest(plan, home, source_root=root, envelope_password=password)
        assert not result['errors'] and 'löschen' in result['password_notice']
        output = Path(result['password_csv'][0])
        assert output.name == ('Passwoerter.csv' if n == 1 else 'Passwoerter-2.csv')
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
        assert output.stat().st_uid == home.stat().st_uid
        with output.open(newline='') as stream:
            assert list(csv.reader(stream)) == [['name', 'url', 'username', 'password'], ['https://example.invalid', 'https://example.invalid', 'test', 'synthetic,secret']]
    manifest = base / 'plan.json'; manifest.write_text(json.dumps(plan))
    # CLI stdin handling can be checked with dry-run without mounting a device.
    result = subprocess.run([sys.executable, str(SCRIPT), 'copy', str(manifest), str(home), '--envelope-password-stdin'], input='', text=True, capture_output=True)
    assert result.returncode and 'fehlt' in result.stderr
print('PASS migrate envelope')
