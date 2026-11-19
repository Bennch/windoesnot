#!/usr/bin/env python3
"""The finder lists profiles, keys, projects and rebuildable things from a synthetic old system and copies only what is confirmed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('finder', root / 'desktop/lib/windoesnot/finder.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def write(path, data='x'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)

with tempfile.TemporaryDirectory() as tmp:
    old = Path(tmp) / 'old'
    home = old / 'home/anna'
    write(old / 'etc/passwd', 'anna:x:1000:1000::/home/anna:/bin/bash\n')
    write(home / '.mozilla/firefox/abc.default/logins.json', 'L' * 100)
    write(home / '.mozilla/firefox/abc.default/key4.db', 'K' * 50)
    write(home / '.thunderbird/x.default/ImapMail/mail', 'M' * 200)
    write(home / '.ssh/id_ed25519', 'S' * 10)
    write(home / '.gnupg/pubring.kbx', 'G')
    write(home / '.gitconfig', '[user]\nname=a\n')
    write(home / '.config/Code/User/settings.json', '{}')
    write(home / '.config/Code/Cache/blob', 'C' * 1000)
    write(home / '.config/unknownapp/cfg', 'u' * 5)
    write(home / '.config/chromium/Default/Login Data', 'chromium')
    write(home / '.local/share/Steam/steamapps/common/game/big.bin', 'g' * 5000)
    write(home / '.local/share/Steam/userdata/1/save', 'save')
    write(home / '.cache/thing', 'c' * 300)
    write(home / 'Documents/letter.txt', 'dear')
    write(home / 'Pictures/p.png', 'png')
    (home / 'Projects/app').mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(home / 'Projects/app')], check=True)
    write(home / 'Projects/app/src/main.rs', 'fn main(){}')
    write(home / 'Projects/app/node_modules/dep/index.js', 'N' * 4000)
    write(home / 'Projects/app/target/debug/out', 'T' * 2000)
    write(home / 'Projects/app/.gitignore', 'out/\ndocs/\n')
    write(home / 'Projects/app/out/image.bin', 'I' * 3000)
    write(home / 'Projects/app/docs/notes.md', 'private notes')
    write(home / 'Stuff/loose.txt', 'x')
    write(home / 'notes.txt', 'n')
    write(home / '.bashrc', 'alias')
    write(old / 'opt/tool/bin', 'tool')
    f.IGNORED_BIG = 2000
    manifest = f.scan(old)
    items = {i['id']: i for i in manifest['findings']}
    assert manifest['schema'] == 2 and manifest['user']['name'] == 'anna'
    for needed in ('firefox', 'thunderbird', 'ssh', 'gnupg', 'git', 'vscode', 'chromium', 'steam-saves', 'steam-games', 'cache',
                   'dir:Documents', 'dir:Pictures', 'dir:Projects', 'dir:Stuff', 'build-folders', 'loose-files', 'sweep:.config', 'shell', 'sys:opt'):
        assert needed in items, (needed, sorted(items))
    assert items['firefox']['secrets'] and items['firefox']['selected'] and items['firefox']['bytes'] == 150
    assert items['chromium']['secrets'] and 'Schlüsselbund' in items['chromium']['detail']['de']
    # Rebuildable things are visible with their size but not ticked, and are carved out of what contains them.
    assert not items['cache']['selected'] and not items['steam-games']['selected'] and not items['build-folders']['selected']
    assert items['build-folders']['bytes'] == 6000
    # A big folder ignored by Git is listed but not ticked; a small ignored folder (private notes) stays with the project.
    assert items['ignored-big']['paths'] == ['Projects/app/out'] and not items['ignored-big']['selected']
    assert items['dir:Projects']['bytes'] < 100000 and items['dir:Projects']['group'] == 'dev'
    # The editor's cache is never counted, the unknown app's settings land in the sweep.
    assert items['vscode']['bytes'] == 2
    assert items['sweep:.config']['paths'] == ['.config/unknownapp'], items['sweep:.config']['paths']
    # Sorted: personal first, within a group by importance.
    groups = [i['group'] for i in manifest['findings']]
    assert groups == sorted(groups, key=lambda g: [x[0] for x in f.GROUPS].index(g))
    personal = [i['id'] for i in manifest['findings'] if i['group'] == 'personal']
    assert personal.index('dir:Documents') < personal.index('dir:Stuff')
    # Copy: only the confirmed ones, no rebuildable folders inside confirmed projects.
    items['firefox']['selected'] = False
    new_home, new_root = Path(tmp) / 'new/home/anna', Path(tmp) / 'new'
    new_home.mkdir(parents=True)
    result = f.copy(manifest, new_home, new_root)
    assert not result['problems'], result
    assert (new_home / 'Documents/letter.txt').read_text() == 'dear'
    assert (new_home / 'Projects/app/src/main.rs').exists() and not (new_home / 'Projects/app/node_modules').exists()
    assert (new_home / 'Projects/app/docs/notes.md').exists() and not (new_home / 'Projects/app/out').exists()
    assert (new_home / '.ssh/id_ed25519').exists() and not (new_home / '.mozilla').exists() and not (new_home / '.cache').exists()
    assert (new_home / '.local/share/Steam/userdata/1/save').exists() and not (new_home / '.local/share/Steam/steamapps').exists()
    assert (new_root / 'opt/tool/bin').read_text() == 'tool'
    assert (new_home / 'notes.txt').exists() and (new_home / '.bashrc').exists()
    # A forged manifest cannot escape.
    items['ssh']['paths'] = ['../../etc']
    try:
        f.copy(manifest, new_home, new_root)
        raise AssertionError('traversal accepted')
    except ValueError:
        pass
print('PASS finder')
