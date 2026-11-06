#!/usr/bin/env python3
"""Installer wishlist -> post-boot installation of deferred apps (Flatpak per user, repo/AUR via Store)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'iso/software'))
import install as installer  # noqa: E402

with tempfile.TemporaryDirectory() as temp:
    d = Path(temp)
    # 1. The installer records only IDs of deferred apps.
    base = d / 'base'; (base / 'iso/software').mkdir(parents=True)
    (base / 'iso/software/catalog.json').write_text((ROOT / 'iso/software/catalog.json').read_text())
    (base / 'offline-apps').mkdir()
    pending = d / 'var/pending-apps.json'
    installer.install_packages = lambda *a, **k: None
    installer.install_selection(['firefox', 'google-chrome', 'ollama'], 'en', base=base, record=d / 'var/profile.json', mode='offline', pending=pending)
    data = json.loads(pending.read_text())
    assert data == {'schema_version': 1, 'pending': ['google-chrome', 'ollama']}, data
    (base / 'offline-apps').mkdir()
    installer.install_selection(['firefox'], 'en', base=base, record=d / 'var/profile.json', mode='offline', pending=pending)
    assert not pending.exists(), 'no deferred apps: no wishlist'

    # 2. The runner: Flatpak per user, nothing arbitrary, repo/AUR only announced (once).
    pending.write_text(json.dumps({'schema_version': 1, 'pending': ['google-chrome', 'ollama', 'codex-cli', 'bogus', 'firefox']}))
    bin_dir = d / 'bin'; bin_dir.mkdir(); calls = d / 'calls'; notes = d / 'notes'
    (bin_dir / 'flatpak').write_text(f'#!/bin/sh\necho "flatpak $@" >> {calls}\n')
    (bin_dir / 'nm-online').write_text('#!/bin/sh\nexit 0\n')
    (bin_dir / 'notify-send').write_text(f'#!/bin/sh\necho "$@" >> {notes}\n')
    for f in bin_dir.iterdir(): f.chmod(0o755)
    env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'WINDOESNOT_PENDING': str(pending), 'XDG_STATE_HOME': str(d / 'state'),
           'WINDOESNOT_BASE': str(base), 'LANG': 'en_US.UTF-8'}
    tool = str(ROOT / 'desktop/bin/windoesnot-pending-apps')
    subprocess.run([tool, '--no-wait'], env=env, check=True)
    lines = calls.read_text().splitlines()
    assert lines == ['flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo',
                     'flatpak install --user --noninteractive -y flathub com.google.Chrome'], lines
    text = notes.read_text()
    assert 'Google Chrome' in text and 'Ollama, Codex CLI' in text and 'bogus' not in text and 'Firefox' not in text, text
    # Second run: Chrome is done, Ollama/Codex were already announced: nothing happens.
    calls.unlink(); notes.unlink()
    subprocess.run([tool, '--no-wait'], env=env, check=True)
    assert not calls.exists() and not notes.exists()
print('PASS pending-apps')
