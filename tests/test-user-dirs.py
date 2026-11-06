#!/usr/bin/env python3
"""windoesnot-user-dirs renames default folders to the target language, safely."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / 'desktop/bin/windoesnot-user-dirs'


def run(home, locale):
    env = {**os.environ, 'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config')}
    env.pop('XDG_DOCUMENTS_DIR', None)
    subprocess.run([str(TOOL), '--locale', locale], env=env, check=True)


with tempfile.TemporaryDirectory() as temp:
    home = Path(temp)
    (home / '.config').mkdir()
    env = {**os.environ, 'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'), 'LANG': 'en_US.UTF-8', 'LC_ALL': 'en_US.UTF-8'}
    subprocess.run(['xdg-user-dirs-update', '--force'], env=env, check=True)
    assert (home / 'Documents').is_dir() and (home / 'Pictures').is_dir()
    (home / 'Documents/keep.txt').write_text('mine')
    (home / 'Music').rmdir()
    (home / 'Music').mkdir(); (home / 'Music/a.mp3').write_text('x')
    (home / 'Custom').mkdir()
    # a customised Videos path must stay untouched
    subprocess.run(['xdg-user-dirs-update', '--set', 'VIDEOS', str(home / 'Custom')], env=env, check=True)
    (home / 'Videos').rmdir()
    # a German folder already holding data next to a default one: keep both
    (home / 'Bilder').mkdir(); (home / 'Bilder/b.png').write_text('y'); (home / 'Pictures/p.png').write_text('z')

    from urllib.parse import quote
    bm = home / '.config/gtk-3.0/bookmarks'; bm.parent.mkdir(parents=True)
    bm.write_text(''.join(f'file://{quote(str(home / d))} {d}\n' for d in ('Documents', 'Music')) + f'file://{quote(str(home / "Custom"))} Meins\n')
    run(home, 'de_DE.UTF-8')
    marks = bm.read_text()
    assert f'file://{quote(str(home / "Dokumente"))} Dokumente' in marks and f'{quote(str(home / "Musik"))} Musik' in marks, marks
    assert 'Meins' in marks, 'user bookmarks stay'
    assert (home / 'Dokumente/keep.txt').read_text() == 'mine', 'data must move with the folder'
    assert not (home / 'Documents').exists()
    assert (home / 'Musik/a.mp3').is_file()
    assert (home / 'Custom').is_dir()
    assert (home / 'Bilder/b.png').is_file() and (home / 'Pictures/p.png').is_file(), 'both non-empty: nothing merged'
    dirs = (home / '.config/user-dirs.dirs').read_text()
    assert 'XDG_DOCUMENTS_DIR="$HOME/Dokumente"' in dirs, dirs
    assert 'XDG_VIDEOS_DIR="$HOME/Custom"' in dirs, 'customised path kept'
    assert (home / '.config/user-dirs.locale').read_text().strip() == 'de_DE.UTF-8'

    run(home, 'en_US.UTF-8')           # and back, live
    assert (home / 'Documents/keep.txt').read_text() == 'mine'
    assert not (home / 'Dokumente').exists()
    run(home, 'en_US.UTF-8')           # idempotent
print('PASS user-dirs')

# Initialization: no skeleton bookmarks; a stale /etc/skel bookmark file is repaired for a real user (own entries kept).
import shutil
with tempfile.TemporaryDirectory() as temp:
    d = Path(temp); home = d / 'home'; (home / '.config/gtk-3.0').mkdir(parents=True)
    (home / '.config/gtk-3.0/bookmarks').write_text('file:///etc/skel/Desktop Desktop\nfile:///etc/skel/Documents Documents\nfile:///srv/data Daten\n')
    env = {**os.environ, 'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_DATA_HOME': str(home / '.local/share'),
           'WINDOESNOT_SOURCE': str(ROOT), 'LANG': 'de_DE.UTF-8'}
    subprocess.run([str(ROOT / 'desktop/bin/windoesnot-initialize')], env=env, check=True, stdout=subprocess.DEVNULL)
    marks = (home / '.config/gtk-3.0/bookmarks').read_text()
    assert '/etc/skel/' not in marks and 'Daten' in marks, marks
    assert f'{home}/Dokumente'.replace(' ', '%20') in marks.replace('%2F', '/') or 'Dokumente' in marks, marks
    assert (home / 'Dokumente').is_dir() and not (home / 'Documents').exists()
print('PASS bookmarks')
