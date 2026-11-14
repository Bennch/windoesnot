#!/usr/bin/env python3
"""windoesnot-screenshot saves via hyprshot, copies to the clipboard and offers a clickable notification."""
import os
import subprocess
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-screenshot'

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    bindir = temp / 'bin'
    bindir.mkdir()
    log = temp / 'calls.log'

    def tool(name, body):
        path = bindir / name
        path.write_text('#!/bin/bash\n' + body)
        path.chmod(0o755)

    tool('xdg-user-dir', f'echo {temp}/Pictures')
    # hyprshot writes the requested file unless CANCEL is set (Esc during the selection).
    tool('hyprshot', f'echo "hyprshot $*" >> {log}\n[ -n "${{CANCEL:-}}" ] && exit 1\n'
                     f'while [ $# -gt 0 ]; do case "$1" in -o) d=$2;; -f) f=$2;; esac; shift; done\nprintf PNG > "$d/$f"')
    tool('wl-copy', f'echo "wl-copy $*" >> {log}\ncat > /dev/null')
    tool('notify-send', f'echo "notify-send $*" >> {log}\necho default')
    tool('xdg-open', f'echo "xdg-open $*" >> {log}')
    env = {**os.environ, 'PATH': f'{bindir}:{os.environ["PATH"]}', 'LANG': 'de_DE.UTF-8', 'HOME': str(temp)}
    result = subprocess.run([str(SCRIPT), 'region'], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for _ in range(50):
        if log.exists() and 'xdg-open' in log.read_text():
            break
        time.sleep(0.1)
    calls = log.read_text()
    shots = list((temp / 'Pictures/Screenshots').glob('*.png'))
    assert len(shots) == 1, shots
    assert '-m region' in calls and '--silent' in calls and f'-o {temp}/Pictures/Screenshots' in calls
    assert 'wl-copy --type image/png' in calls
    assert 'default=Öffnen' in calls and 'open=Öffnen' in calls and 'folder=Ordner' in calls and '--wait' in calls
    assert f'xdg-open {shots[0]}' in calls, 'a click on the notification opens the picture'
    # A cancelled selection saves and announces nothing.
    log.unlink()
    for picture in shots:
        picture.unlink()
    cancelled = subprocess.run([str(SCRIPT)], env={**env, 'CANCEL': '1'}, capture_output=True, text=True)
    assert cancelled.returncode == 0 and 'notify-send' not in log.read_text()
    assert subprocess.run([str(SCRIPT), 'bogus'], env=env, capture_output=True).returncode == 2
print('PASS: screenshot wrapper saves, copies, announces with click actions and respects cancel')
