#!/usr/bin/env python3
"""Install the fixed, root-owned language helper/policy on a source installation."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ('desktop/lib/windoesnot/system_tools.py', '/usr/lib/windoesnot/system_tools.py', 0o755),
    ('desktop/share/polkit-1/actions/org.windoesnot.system.policy', '/usr/share/polkit-1/actions/org.windoesnot.system.policy', 0o644),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--locale', choices=['de_DE.UTF-8', 'en_US.UTF-8'])
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'targets': [v[1] for v in FILES]}))
        return
    if os.geteuid() != 0:
        raise SystemExit('Administrator authorization is required')
    if Path('/usr/bin/pacman').exists() and subprocess.run(
            ['/usr/bin/pacman', '-Qo', '/usr/lib/windoesnot/system_tools.py'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        raise SystemExit('Update the installed WinDoesNot tools package to enable language setup')
    backup = Path('/var/backups/windoesnot-language') / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, mode=0o700)
    print(json.dumps({'event': 'progress', 'stage': 'install', 'step': 0, 'total': 3}), flush=True)
    for source, destination, mode in FILES:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError('Refusing a symlinked helper/policy target')
        if target.exists():
            saved = backup / target.relative_to('/');saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as out:
            temp = Path(out.name)
            os.fchmod(out.fileno(), mode)
            out.write((ROOT / source).read_bytes());out.flush();os.fsync(out.fileno())
        temp.replace(target)
    if args.locale:
        os.execv('/usr/lib/windoesnot/system_tools.py',
                 ['/usr/lib/windoesnot/system_tools.py', 'locale-set', json.dumps({'locale': args.locale})])


if __name__ == '__main__':
    main()
