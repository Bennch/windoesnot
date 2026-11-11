#!/usr/bin/env python3
"""Back up and activate ONLY the agreed backup/auth code, with automatic rollback."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / 'build/backup-integration/host'
HOST = Path.home() / '.config/quickshell/default'
FILES = ['widgets/AuthenticationCard.qml', 'widgets/SystemAuthentication.qml',
         'widgets/qmldir', 'i18n/de.js', 'i18n/en.js', 'settings/BackupsCategory.qml',
         'Settings.qml', 'shell.qml']
BACKUP = Path.home() / '.local/state/windoesnot/backup-integration' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')


def running_shells():
    result = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            args = (entry / 'cmdline').read_bytes().split(b'\0')
            if entry.stat().st_uid == os.getuid() and Path(args[0].decode()).name in ('quickshell', 'qs') and str(HOST / 'shell.qml').encode() in args:
                result.append(int(entry.name))
        except (OSError, UnicodeError):
            pass
    return result


def stop_shell():
    for pid in running_shells():
        os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if not running_shells():
            return
        time.sleep(0.1)
    raise RuntimeError('Shell did not exit; refusing to install')


def start_shell():
    # Let Hyprland launch it inside the real logind session (native Polkit agent).
    command = str(Path.home() / '.config/hypr/scripts/start-quickshell.sh')
    result = subprocess.run(['hyprctl', 'eval', 'return hl.dispatch(hl.dsp.exec_cmd(' + json.dumps(command) + '))'], capture_output=True, text=True, check=True)
    if 'ok' not in result.stdout:
        raise RuntimeError('Shell launch failed')


def atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.wdn-new')
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


def personal_hashes():
    paths = [HOST / name for name in ('settings/settings.txt', 'settings.txt', 'pinned.txt', 'taskbar.txt')]
    return {str(p.relative_to(HOST)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def main():
    if not Path('/usr/lib/windoesnot/snapshots.py').is_file():
        raise SystemExit('Install the reviewed system helper first')
    if len(running_shells()) != 1:
        raise SystemExit('Expected one running main shell; no files changed')
    BACKUP.mkdir(parents=True, mode=0o700)
    manifest = {}
    for name in FILES:
        target = HOST / name
        if target.is_symlink():
            raise SystemExit('Refusing to replace a symlink: ' + name)
        manifest[name] = target.exists()
        if target.exists():
            saved = BACKUP / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    before = personal_hashes()
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    (BACKUP / 'personal-hashes.json').write_text(json.dumps(before, indent=2))
    print('Host recovery copy: ' + str(BACKUP), flush=True)
    stop_shell()
    try:
        for name in FILES:
            atomic_copy(STAGE / name, HOST / name)
        start_shell()
        for _ in range(30):
            time.sleep(1)
            check = subprocess.run(['quickshell', 'ipc', '-p', str(HOST / 'shell.qml'), 'call',
                                    'authentication', 'status'], capture_output=True, text=True)
            if check.returncode == 0:
                state = json.loads(check.stdout)
                if state.get('registered'):
                    if personal_hashes() != before:
                        raise RuntimeError('Personal settings changed unexpectedly')
                    report = {'registered': True, 'personal_files_unchanged': True, 'backup': str(BACKUP)}
                    (ROOT / 'checks/backup-host-activation.json').write_text(json.dumps(report, indent=2))
                    print(json.dumps(report), flush=True)
                    return
        raise RuntimeError('Native authentication agent did not become ready')
    except Exception:
        stop_shell()
        for name, existed in manifest.items():
            if existed:
                atomic_copy(BACKUP / name, HOST / name)
            else:
                (HOST / name).unlink(missing_ok=True)
        start_shell()
        print('Previous shell code restored; system helpers remain installed.', flush=True)
        raise


if __name__ == '__main__':
    main()
