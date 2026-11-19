#!/usr/bin/env python3
"""Exercise the actual fixture and verifier on disk, without privileged access."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools/vm-test/migrate-sim'
work = ROOT / 'out/migrate-sim'
work.mkdir(parents=True, exist_ok=True)
def run(*args, expected=0):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != expected:
        raise AssertionError(f'{args}: expected {expected}, got {p.returncode}\n{p.stdout}')
    return p.stdout
with tempfile.TemporaryDirectory(prefix='test-', dir=work) as tmp:
    base = Path(tmp); source = base / 'source'; second = base / 'second'; copy = base / 'copy'
    for root in (source, second): run(sys.executable, str(TOOLS / 'make-fixture.py'), str(root))
    output = run(sys.executable, str(TOOLS / 'verify.py'), str(source), str(second))
    assert 'PASS Home:' in output and 'PASS Docker:' in output
    run(sys.executable, str(TOOLS / 'verify.py'), str(source), str(source))
    run('cp', '-a', '--reflink=auto', '--sparse=always', str(source), str(copy))
    (copy / 'srv/docker/volumes/example/_data/data').write_text('modified\n')
    output = run(sys.executable, str(TOOLS / 'verify.py'), str(source), str(copy), expected=1)
    assert 'FAIL Docker:' in output and 'volumes/example' in output
    # The private mount must be visible only to the command launched in its namespace.
    run(sys.executable, str(TOOLS / 'make-fixture.py'), str(source), '--with-mount', '--',
        'test', '-f', str(source / 'home/benni/nested-mount/mounted-content'))
    assert not (source / 'home/benni/nested-mount/mounted-content').exists()
print('migration fixture tests passed')
