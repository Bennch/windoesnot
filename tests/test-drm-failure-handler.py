#!/usr/bin/env python3
"""The GPU failure screen speaks the system language and keeps the bug report log."""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'desktop/lib/windoesnot/drm-failure-handler'
unit = (ROOT / 'desktop/share/systemd/system/drm-failure-handler.service.d/10-windoesnot.conf').read_text()
assert 'ExecStart=\nExecStart=/usr/lib/windoesnot/drm-failure-handler' in unit, 'the drop-in must reset and replace ExecStart'
pkgbuild = (ROOT / 'packaging/PKGBUILD.in').read_text()
assert 'drm-failure-handler.service.d/10-windoesnot.conf' in pkgbuild and 'usr/lib/windoesnot/drm-failure-handler' in pkgbuild

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    bindir = temp / 'bin'
    bindir.mkdir()
    (bindir / 'logger').write_text('#!/bin/sh\nshift 2\nprintf "%s\\n" "$*" > "$OUT"\n')
    (bindir / 'cachyos-bugreport.sh').write_text('#!/bin/sh\necho report > "$LOG_FILENAME"\n')
    for tool in bindir.iterdir():
        tool.chmod(0o755)

    def message(locale):
        conf = temp / 'locale.conf'
        conf.write_text(f'LANG={locale}\n')
        out = temp / 'out'
        env = {**os.environ, 'PATH': f'{bindir}:{os.environ["PATH"]}', 'OUT': str(out),
               'WINDOESNOT_DRM_LOGS': str(temp / 'logs'), 'WINDOESNOT_LOCALE_CONF': str(conf)}
        subprocess.run([str(SCRIPT)], env=env, check=True)
        return out.read_text()

    german = message('de_DE.UTF-8')
    assert 'Grafiktreiber' in german and 'nomodeset' in german and 'lite-mode' in german and 'wiki.cachyos' not in german
    english = message('en_US.UTF-8')
    assert 'graphics driver' in english and 'nomodeset' in english and 'wiki.cachyos' not in english
    assert any((temp / 'logs').glob('cachyos-bugreport-*.log')), 'the bug report log is still written'
print('PASS: GPU failure handler is branded, bilingual and keeps the bug report')
