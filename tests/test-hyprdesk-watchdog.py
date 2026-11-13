#!/usr/bin/env python3
"""Exercise hyprdesk startup retries with a fake compositor and child."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'desktop/config/hypr/scripts/start-hyprdesk.sh'
assert 'start-hyprdesk.sh' in (ROOT / 'desktop/config/hypr/lua/reference.lua').read_text()
source = (ROOT / 'desktop/config/hyprdesk/hyprdesk.py').read_text()
assert '_retry_monitor_startup' in source and 'GLib.timeout_add(750, self._retry_monitor_startup)' in source

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    count = root / 'starts'
    desk = root / 'fake-desk'
    desk.write_text(f'''#!/bin/sh\necho $$ >> "{count}"\ntrap 'exit 0' TERM\nwhile :; do sleep 0.05; done\n''')
    desk.chmod(0o755)
    hyprctl = root / 'hyprctl'
    hyprctl.write_text(f'''#!/bin/sh\nn=$(wc -l < "{count}" 2>/dev/null || echo 0)\n[ "$n" -ge 2 ] && echo '{{"namespace":"hyprdesk-desktop"}}'\n''')
    hyprctl.chmod(0o755)
    env = dict(os.environ, HOME=tmp, XDG_RUNTIME_DIR=tmp,
               WINDOESNOT_HYPRCTL=str(hyprctl), WINDOESNOT_HYPRDESK=str(desk),
               WINDOESNOT_HYPRDESK_CHECK_DELAY='0.1')
    process = subprocess.Popen([str(SCRIPT)], env=env)
    try:
        import time
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and (not count.exists() or len(count.read_text().splitlines()) < 2):
            time.sleep(0.05)
        assert count.exists() and len(count.read_text().splitlines()) == 2
    finally:
        process.terminate()
        process.wait(timeout=2)
        if count.exists():
            for pid in count.read_text().splitlines():
                subprocess.run(['kill', pid], check=False, stderr=subprocess.DEVNULL)

print('PASS: hyprdesk watchdog restarts until its layer appears')
