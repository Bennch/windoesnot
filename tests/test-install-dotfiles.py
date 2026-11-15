#!/usr/bin/env python3
"""Exercise the installer without a package manager or access to the real home."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'tools/install-dotfiles.sh'
source = SCRIPT.read_text()
subprocess.run(['bash', '-n', str(SCRIPT)], check=True)
assert not re.search(r'\brm\s+-rf\b', source)
assert 'if ask ' in source and source.count('then sudo pacman') == 3
assert "'tools/install-dotfiles.sh'" in (ROOT / 'tools/export-dotfiles.py').read_text()
assert "'packaging/windoesnot-desktop.install'" in (ROOT / 'tools/export-dotfiles.py').read_text()

with tempfile.TemporaryDirectory() as temp:
    tmp = Path(temp)
    (tmp / 'home').mkdir()
    bindir = tmp / 'bin'
    bindir.mkdir()
    release = tmp / 'os-release'
    release.write_text('ID=cachyos\nID_LIKE=arch\n')
    log = tmp / 'calls'
    for name, body in {
        'pacman': 'case "$1" in -Q) exit 1;; -Si|-Sp) exit 0;; *) exit 99;; esac',
        'sudo': 'exit 99', 'makepkg': 'exit 99',
    }.items():
        path = bindir / name
        path.write_text(f'#!/bin/bash\nprintf "%s\\n" "{name} $*" >> "$CALLS"\n{body}\n')
        path.chmod(0o755)
    env = dict(os.environ, HOME=str(tmp / 'home'), XDG_CACHE_HOME=str(tmp / 'cache'),
               PATH=f'{bindir}:/usr/bin:/bin', WDN_OS_RELEASE=str(release), CALLS=str(log))
    def run(*args):
        return subprocess.run(['bash', str(SCRIPT), *args], env=env, text=True, capture_output=True)
    assert run('--help').returncode == 0
    for lang, expected in [('de', 'Fehlende Repository-Pakete'), ('en', 'Missing repository packages')]:
        result = run('--lang', lang, '--check')
        assert result.returncode == 1 and expected in result.stdout, result
        result = run('--lang', lang, '--dry-run', '--yes')
        assert result.returncode == 0 and expected in result.stdout, result
    assert not (tmp / 'cache').exists()
    assert not re.search(r'^(sudo|makepkg) ', log.read_text(), re.M)
    release.write_text('ID=debian\n')
    result = run('--check')
    assert result.returncode and 'https://windoesnot.me/download/' in result.stderr
print('PASS installer fake-system and static checks')
