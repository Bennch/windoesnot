#!/usr/bin/env python3
"""In lite mode the Ghostty wrapper must start Foot with arguments Foot understands."""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'desktop/bin/ghostty'
assert SCRIPT.read_text() == (ROOT / 'iso/ghostty-wrapper.sh').read_text(), 'both wrapper copies must match'

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    flag = temp / 'lite-mode'
    foot = temp / 'foot'
    foot.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$OUT"\n')
    foot.chmod(0o755)
    # Run the wrapper body against fixture paths.
    body = SCRIPT.read_text().replace('/etc/windoesnot/lite-mode', str(flag)).replace('/usr/bin/foot', str(foot))
    wrapper = temp / 'ghostty'
    wrapper.write_text(body)
    wrapper.chmod(0o755)
    out = temp / 'out'
    flag.touch()

    def run(*args):
        subprocess.run([str(wrapper), *args], check=True, env={**os.environ, 'OUT': str(out)})
        return out.read_text().split('\n')[:-1]

    # The desktop entry's launch (taskbar pin, start menu): Foot must not see the Ghostty option.
    assert run('--gtk-single-instance=false') == ['--app-id=com.mitchellh.ghostty']
    assert run('--gtk-single-instance=false', '-e', 'htop') == ['--app-id=com.mitchellh.ghostty', '-e', 'htop']
    assert run('--class=my.terminal', '--working-directory=/tmp') == ['--app-id=my.terminal', '--working-directory=/tmp']
    assert run() == ['--app-id=com.mitchellh.ghostty']
print('PASS: lite-mode ghostty wrapper translates options for Foot and keeps the Ghostty app id')
