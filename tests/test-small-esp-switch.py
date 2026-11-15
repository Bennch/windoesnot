#!/usr/bin/env python3
"""The reserved small-ESP switch must fail before producing a profile."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root) as tmp:
    output = Path(tmp) / 'profile'
    def run(value):
        env = os.environ.copy()
        env.pop('WINDOESNOT_SMALL_ESP', None)
        if value is not None:
            env['WINDOESNOT_SMALL_ESP'] = value
        return subprocess.run([sys.executable, str(root / 'tools/prepare-profile.py'),
                               '--output', str(output), '--source-manifest', str(Path(tmp) / 'missing')],
                              env=env, capture_output=True)
    default, disabled = run(None), run('0')
    assert default.returncode == disabled.returncode
    assert default.stdout == disabled.stdout and default.stderr == disabled.stderr
    enabled = run('1')
    assert enabled.returncode and b'not implemented' in enabled.stderr
    assert not output.exists()
    invalid = run('yes')
    assert invalid.returncode and b'must be 0 or 1' in invalid.stderr
    assert not output.exists()
print('PASS: small ESP switch fails closed; unset and 0 follow the same path')
