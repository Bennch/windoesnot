#!/usr/bin/env python3
"""The remote support command validates its input, asks first and never runs by itself."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-remote-support'


def run(*args, stdin=None, lang='de_DE.UTF-8'):
    return subprocess.run([str(SCRIPT), *args], input=stdin, capture_output=True, text=True,
                          env={**os.environ, 'LANG': lang, 'LC_ALL': lang})


ok = run('--dry-run', '192.168.8.138', 'wdn7')
assert ok.returncode == 0 and 'http://192.168.8.138:8000/wdn7/s' in ok.stdout and 'Fernhilfe' in ok.stdout
assert 'Remote support' in run('--dry-run', 'example.lan:9000', 'abcd', lang='en_US.UTF-8').stdout
for host, code in (('a b', 'wdn7'), ('1.2.3.4;rm', 'wdn7'), ('1.2.3.4', 'x'), ('1.2.3.4', 'a/b'), ('1.2.3.4', '$(id)')):
    assert run('--dry-run', host, code).returncode == 2, (host, code)
assert run().returncode == 2 and run('--bogus', 'h', 'c').returncode == 2
# Without --yes it needs a terminal, so it cannot be started from a script or a pipe by accident.
refused = run('192.168.8.138', 'wdn7', stdin='')
assert refused.returncode == 1 and 'terminal' in refused.stderr
text = SCRIPT.read_text()
assert '--yes' in text and 'Never starts by itself' in text
print('PASS: remote support command validates input, asks first and needs a terminal')
