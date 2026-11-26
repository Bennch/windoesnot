#!/usr/bin/env python3
"""fetch-sources clones every sources.json entry with path+commit; offline via file:// repos."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ID = ['-c', 'user.name=t', '-c', 'user.email=t@t']


def git(*args):
    return subprocess.run(['git', *ID, *args], check=True, text=True, capture_output=True).stdout.strip()


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    pins, heads = {}, {}
    for name, path in (('windoesnot-store', 'store'), ('windoesnot-audio', 'audio'), ('windoesnot-network', 'network')):
        up = tmp / 'remote' / path
        up.mkdir(parents=True)
        git('init', '-q', str(up))
        (up / 'a').write_text('1')
        git('-C', str(up), 'add', 'a')
        git('-C', str(up), 'commit', '-qm', 'one')
        first = git('-C', str(up), 'rev-parse', 'HEAD')
        (up / 'a').write_text('2')
        git('-C', str(up), 'commit', '-qam', 'two')
        pins[name] = {'url': 'file://' + str(up), 'path': path, 'commit': first}
        heads[path] = first
    pins['hyprland'] = {'version': '1'}  # entries without path/commit are ignored
    work = tmp / 'work'
    (work / 'tools').mkdir(parents=True)
    shutil.copy(ROOT / 'tools/fetch-sources.py', work / 'tools')
    (work / 'sources.json').write_text(json.dumps(pins))
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(tmp), 'GIT_CONFIG_COUNT': '1',
           'GIT_CONFIG_KEY_0': 'protocol.file.allow', 'GIT_CONFIG_VALUE_0': 'always'}

    def run():
        subprocess.run([sys.executable, str(work / 'tools/fetch-sources.py')], check=True, text=True,
                       capture_output=True, env=env)

    run()
    for path, commit in heads.items():
        assert (work / path / '.git').exists(), path
        git('-C', str(work / path), 'cat-file', '-e', commit + '^{commit}')
    # Local edits in an existing checkout are never touched; a second run is a no-op.
    (work / 'audio' / 'a').write_text('local edit')
    run()
    assert (work / 'audio' / 'a').read_text() == 'local edit'
    # A newly pinned commit is fetched into the existing repo.
    newer = git('-C', str(tmp / 'remote' / 'store'), 'rev-parse', 'HEAD')
    pins['windoesnot-store']['commit'] = newer
    (work / 'sources.json').write_text(json.dumps(pins))
    run()
    git('-C', str(work / 'store'), 'cat-file', '-e', newer + '^{commit}')
print('fetch-sources test passed')
