#!/usr/bin/env python3
"""Bring the host's Quickshell code to the shared desktop sources, keeping personal files.

Dry run by default: prints exactly which files would change. With --apply it backs
up every target, stops only the main shell, replaces files atomically, restarts the
shell inside the Hyprland session and rolls everything back if the native
authentication agent does not register or a personal file changes.

Not part of this sync: generated IconMap.js (rebuilt at shell start), replace.qml
(personal app overrides), Hyprland configuration, other desktop components, packages.
"""
import argparse
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
SOURCE = ROOT / 'desktop/config/quickshell/default'
HOST = Path.home() / '.config/quickshell/default'
TERMINAL = 'widgets/terminalmodule/LocalTerminal'
# Generated at shell start or personal: never replaced by shared sources.
SKIPPED = {'IconMap.js', 'icon-map.json', 'replace.qml'}
PERSONAL = ['settings.txt', 'pinned.txt', 'taskbar.txt', 'calendar_notes.json',
            'settings/copilot-state.json', 'icons.json', 'taskbar_order.txt']
# Both icon-map.json and IconMap.js are regenerated from desktop entries at
# startup. New application packages legitimately change them, unlike user pins
# and desktop icon positions, which must remain unchanged.
BIN = Path.home() / '.local/bin'
APPLICATIONS = Path.home() / '.local/share/applications'
# The start menu reads launchers from desktop files now; the personal Keys entry
# from the previous host shell stays available this way (not part of the release).
KEYS_LAUNCHER = f"""[Desktop Entry]
Type=Application
Name=Keys
Comment=Hyprland-Konfiguration neu laden
Exec=windoesnot-hyprctl reload
Icon={HOST / 'img/keys.svg'}
Terminal=false
"""


def host_layout_differs(target):
    """True below a symlinked host directory (e.g. a theme folder linked elsewhere),
    and for an icon cache next to such links: the host keeps its own layout."""
    parents = [p for p in target.parents if HOST in p.parents or p == HOST]
    if any(p.is_symlink() for p in parents):
        return True
    if target.name == 'icon-theme.cache':
        return any(child.is_symlink() for child in target.parent.rglob('*'))
    return False


def changes(terminal_build):
    """(target, source bytes, mode) for every file that differs on the host."""
    result = []
    for source in sorted(SOURCE.rglob('*')):
        relative = source.relative_to(SOURCE)
        if not source.is_file() or source.name in SKIPPED:
            continue
        if any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
            continue
        if str(relative).startswith(TERMINAL + '/'):
            continue  # replaced by the build against the host's Qt below
        result.append((HOST / relative, source.read_bytes(), source.stat().st_mode & 0o777))
    for library in sorted((terminal_build / TERMINAL).iterdir()):
        result.append((HOST / TERMINAL / library.name, library.read_bytes(), library.stat().st_mode & 0o777))
    for name in ('windoesnot-list-apps', 'windoesnot-open-bluetooth', 'windoesnot-open-network'):
        launcher = ROOT / 'desktop/bin' / name
        result.append((BIN / name, launcher.read_bytes(), 0o755))
    keys = APPLICATIONS / 'windoesnot-keys.desktop'
    if not keys.exists():
        result.append((keys, KEYS_LAUNCHER.encode(), 0o644))
    differing = [c for c in result if not c[0].exists() or c[0].read_bytes() != c[1]]
    for target, _, _ in differing:
        if host_layout_differs(target):
            print('belassen ' + str(target.relative_to(Path.home())) + ' (eigenes Host-Layout mit Symlinks)')
    return [c for c in differing if not host_layout_differs(c[0])]


def check_terminal_build(terminal_build):
    module = terminal_build / TERMINAL
    if not (module / 'qmldir').is_file():
        raise SystemExit(f'No terminal build in {module}')
    for library in module.glob('*.so'):
        dynamic = subprocess.run(['readelf', '-d', str(library)], capture_output=True, text=True, check=True).stdout
        runpaths = [line for line in dynamic.splitlines() if 'RUNPATH' in line or 'RPATH' in line]
        if any('[$ORIGIN]' not in line for line in runpaths):
            raise SystemExit(f'Unexpected RUNPATH in {library}: {runpaths}')
        linked = subprocess.run(['ldd', str(library)], capture_output=True, text=True, cwd=module).stdout
        if 'not found' in linked:
            raise SystemExit(f'Unresolved library for {library}')


def personal_hashes():
    return {name: hashlib.sha256((HOST / name).read_bytes()).hexdigest()
            for name in PERSONAL if (HOST / name).is_file()}


def running_shells():
    found = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            args = (entry / 'cmdline').read_bytes().split(b'\0')
            if entry.stat().st_uid == os.getuid() and Path(args[0].decode()).name in ('quickshell', 'qs') \
                    and str(HOST / 'shell.qml').encode() in args:
                found.append(int(entry.name))
        except (OSError, UnicodeError):
            pass
    return found


def stop_shell():
    for pid in running_shells():
        os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if not running_shells():
            return
        time.sleep(0.1)
    raise RuntimeError('Shell did not exit')


def start_shell():
    # Inside the real logind session via Hyprland, so the Polkit agent registers.
    command = str(Path.home() / '.config/hypr/scripts/start-quickshell.sh')
    result = subprocess.run(['hyprctl', 'eval', 'return hl.dispatch(hl.dsp.exec_cmd(' + json.dumps(command) + '))'],
                            capture_output=True, text=True, check=True)
    if 'ok' not in result.stdout:
        raise RuntimeError('Shell launch failed')


def wait_for_agent():
    for _ in range(30):
        time.sleep(1)
        check = subprocess.run(['quickshell', 'ipc', '-p', str(HOST / 'shell.qml'), 'call', 'authentication', 'status'],
                               capture_output=True, text=True)
        if check.returncode == 0 and json.loads(check.stdout).get('registered'):
            return
    raise RuntimeError('Native authentication agent did not register')


def write(target, data, mode):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.wdn-new')
    temporary.write_bytes(data)
    temporary.chmod(mode)
    os.replace(temporary, target)


def restore(backup, manifest):
    for entry in manifest:
        target = Path(entry['target'])
        if entry['existed']:
            shutil.copy2(backup / 'files' / target.relative_to(Path.home()), target)
        else:
            target.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--terminal-build', type=Path,
                        help='Build directory of the terminal module against this host\'s Qt')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--restore', type=Path, metavar='BACKUP',
                        help='Put back the files of an earlier sync from its backup directory')
    args = parser.parse_args()
    if args.restore:
        manifest = json.loads((args.restore / 'manifest.json').read_text())
        stop_shell()
        restore(args.restore, manifest)
        start_shell()
        wait_for_agent()
        print('Vorheriger Stand wiederhergestellt aus ' + str(args.restore))
        return
    if not args.terminal_build:
        parser.error('--terminal-build is required unless --restore is given')
    check_terminal_build(args.terminal_build)
    pending = changes(args.terminal_build)
    for target, _, _ in pending:
        print(('neu     ' if not target.exists() else 'ändern  ') + str(target.relative_to(Path.home())))
    print(f'{len(pending)} Dateien; persönliche Dateien und IconMap.js bleiben unberührt')
    if not args.apply or not pending:
        return
    for target, _, _ in pending:
        if target.is_symlink():
            raise SystemExit(f'Refusing to replace a symlink: {target}')
    if len(running_shells()) != 1:
        raise SystemExit('Expected one running main shell; no files changed')

    backup = Path.home() / '.local/state/windoesnot/desktop-sync' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    (backup / 'files').mkdir(parents=True, mode=0o700)
    manifest = []
    for target, data, _ in pending:
        existed = target.exists()
        if existed:
            saved = backup / 'files' / target.relative_to(Path.home())
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        manifest.append({'target': str(target), 'existed': existed, 'sha256': hashlib.sha256(data).hexdigest()})
    before = personal_hashes()
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (backup / 'personal-hashes.json').write_text(json.dumps(before, indent=2) + '\n')
    print('Sicherung: ' + str(backup), flush=True)

    stop_shell()
    try:
        # Libraries, assets and helpers first, shell.qml last.
        for target, data, mode in sorted(pending, key=lambda c: (c[0].suffix == '.qml', c[0].name == 'shell.qml')):
            write(target, data, mode)
        start_shell()
        wait_for_agent()
        if personal_hashes() != before:
            raise RuntimeError('Personal files changed unexpectedly')
    except Exception:
        stop_shell()
        restore(backup, manifest)
        start_shell()
        print('Fehler: vorheriger Stand wiederhergestellt aus ' + str(backup), flush=True)
        raise
    report = {'backup': str(backup), 'files': len(pending), 'agent_registered': True, 'personal_files_unchanged': True}
    (ROOT / 'checks/host-desktop-sync.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
