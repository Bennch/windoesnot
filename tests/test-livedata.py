#!/usr/bin/env python3
"""Files made in the live session are carried over safely."""
import importlib.util
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('livedata', ROOT / 'desktop/lib/windoesnot/livedata.py')
livedata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(livedata)

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    live, target = temp / 'live', temp / 'target'
    (live / '.config').mkdir(parents=True)
    (live / '.config/user-dirs.dirs').write_text(
        'XDG_DESKTOP_DIR="$HOME/Schreibtisch"\nXDG_DOWNLOAD_DIR="$HOME/Downloads"\nXDG_DOCUMENTS_DIR="$HOME/Dokumente"\n'
        'XDG_PICTURES_DIR="$HOME/../etc"\nXDG_MUSIC_DIR="/etc"\n')
    for name in ('Schreibtisch', 'Downloads', 'Dokumente/Projekt', 'Bilder', 'Musik'):
        (live / name).mkdir(parents=True)
    (live / 'Downloads/wdn-ssh.sh').write_text('#!/bin/sh\necho hi\n')
    (live / 'Downloads/wdn-ssh.sh').chmod(0o755)
    (live / 'Dokumente/Projekt/notizen.txt').write_text('wichtig')
    (live / 'Dokumente/Projekt/.versteckt').write_text('hidden')
    (live / 'Schreibtisch/link').symlink_to('/etc/passwd')
    (live / 'Schreibtisch/gross.bin').write_bytes(b'x' * 2000)
    (live / '.config/secret').write_text('config files are never copied')
    (live / 'Bilder/default.png').write_text('picture')
    (target / 'Downloads').mkdir(parents=True)
    (target / 'Downloads/wdn-ssh.sh').write_text('existing file stays')

    # Unsafe or odd folder entries in user-dirs.dirs fall back to the defaults, never escape the home.
    assert livedata.user_dirs(live)['PICTURES'] == 'Pictures' and livedata.user_dirs(live)['MUSIC'] == 'Music'
    assert livedata.user_dirs(live)['DESKTOP'] == 'Schreibtisch'

    result = livedata.copy_live_data(live, target, max_file=1000)
    assert (target / 'Dokumente/Projekt/notizen.txt').read_text() == 'wichtig'
    assert (target / 'Downloads/wdn-ssh.sh').read_text() == 'existing file stays', 'nothing is overwritten'
    assert not (target / 'Dokumente/Projekt/.versteckt').exists(), 'hidden files stay behind'
    assert not (target / 'Schreibtisch/link').exists(), 'links are not followed'
    assert not (target / 'Schreibtisch/gross.bin').exists(), 'oversized files are skipped'
    assert not (target / '.config').exists()
    assert result['files'] == 1 and any('gross.bin' in item for item in result['skipped'])

    # The executable bit survives (the remote support script keeps working).
    (target / 'Downloads/wdn-ssh.sh').unlink()
    livedata.copy_live_data(live, target, max_file=1000)
    assert os.access(target / 'Downloads/wdn-ssh.sh', os.X_OK)

    # The total size limit stops the copy.
    other = temp / 'other'
    limited = livedata.copy_live_data(live, other, max_total=3)
    assert limited['bytes'] <= 3
print('PASS: live data copy skips hidden files, links, oversized files and existing files; keeps modes')
