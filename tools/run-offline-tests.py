#!/usr/bin/env python3
"""Run repository tests that are safe without a VM, display server, or network."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
TEST_DIRS = (ROOT / 'tests', ROOT / 'tools')

# These checks need a VM or an already running live desktop by design.
SKIP = {
    'tests/test-package-abi-guard.py': 'requires a disposable VM with the target image package database',
    'tests/test-package-personal-state.py': 'requires the prepared VM user and before-update state',
    'tests/test-signed-package-upgrade.py': 'requires a disposable VM and prepared signed package repository',
    'tools/test-live-guest.py': 'must run inside the disposable live/installed VM',
    'tools/test-live-preferences.py': 'requires a running live desktop session in the disposable VM',
}


def requirement(path: str) -> str | None:
    """Return an explicit skip reason for fixtures/binaries unavailable locally."""
    if path in SKIP:
        return SKIP[path]
    if path.endswith('.cpp'):
        if not shutil.which('g++') or not shutil.which('pkg-config'):
            return 'requires g++ and pkg-config to compile the standalone widget test'
        qt = subprocess.run(['pkg-config', '--exists', 'Qt6Widgets'], check=False)
        if qt.returncode:
            return 'requires Qt6Widgets development files to compile the standalone widget test'
    if path == 'tests/test-aur-updater.py' and not (ROOT / 'store/target/release/windoesnot-store').is_file():
        return 'requires the built Store CLI at store/target/release/windoesnot-store (package builds are out of scope)'
    if path == 'tests/test-calamares-language.py':
        configured = os.environ.get('WINDOESNOT_CALAMARES_SOURCE')
        source = Path(configured).resolve() if configured else ROOT / 'upstream/cachyos-calamares'
        # Do not inspect an upstream checkout outside this worktree.
        try:
            source.relative_to(ROOT)
        except ValueError:
            return 'requires pinned Calamares sources inside this worktree; external/main-repo checkouts are out of scope'
        if not (source / 'lang/calamares_de.ts').is_file():
            return 'requires upstream/cachyos-calamares/lang/calamares_de.ts, absent from this worktree'
    if path == 'tests/test-iso-languages.py' and not (
            ROOT / 'upstream/cachyos-live-iso/archiso/grub/grub.cfg').is_file():
        return 'requires upstream/cachyos-live-iso/archiso boot-menu fixtures, absent from this worktree'
    if path == 'tests/test-repository-trust.py':
        fixture = ROOT / 'out/repos/signed-r8-update-16'
        if not (fixture / 'REPOSITORY.json').is_file():
            return 'requires the prepared signed repository fixture at out/repos/signed-r8-update-16'
    if path == 'tests/test-greeter-branding.py' and not Path('/usr/bin/sddm-greeter-qt6').is_file():
        return 'requires /usr/bin/sddm-greeter-qt6 for the offscreen render'
    return None


def tests() -> list[Path]:
    found = []
    for directory in TEST_DIRS:
        found.extend(directory.glob('test-*.py'))
        if directory == ROOT / 'tests':
            found.extend(directory.glob('test_*.py'))
            found.extend(directory.glob('*.cpp'))
    return sorted(set(found), key=lambda path: path.relative_to(ROOT).as_posix())


def run_cpp(path: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    cases = {
        'apps-widget.cpp': ('iso/modules/windoesnotapps/AppSelectionWidget.cpp',
                            'iso/modules/windoesnotapps', [str(ROOT / 'iso/software/catalog.json')]),
        'boot-widget.cpp': ('iso/modules/windoesnotboot/BootSelectionWidget.cpp',
                            'iso/modules/windoesnotboot', []),
    }
    source, include, arguments = cases[path.name]
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Widgets'], text=True))
    with tempfile.TemporaryDirectory(prefix='windoesnot-widget-test-') as tmp:
        binary = Path(tmp) / path.stem
        command = ['g++', '-std=c++17', '-fPIC', '-I', str(ROOT / include), str(path),
                   str(ROOT / source), '-o', str(binary), *flags]
        build = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout)
        if build.returncode:
            return build
        return subprocess.run([str(binary), *arguments], cwd=ROOT, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def main() -> int:
    env = os.environ.copy()
    env.update({
        'QT_QPA_PLATFORM': 'offscreen',
        'QT_QUICK_BACKEND': 'software',
        'QT_QPA_PLATFORMTHEME': 'basic',
        'DISPLAY': '',
        'WAYLAND_DISPLAY': '',
        'DBUS_SESSION_BUS_ADDRESS': '',
    })
    timeout = int(os.environ.get('WINDOESNOT_OFFLINE_TEST_TIMEOUT', '180'))
    passed: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    started = time.monotonic()

    suite = tests()
    validator = ROOT / 'tools/validate-desktop.py'
    commands = [(validator, None), *((path, requirement(path.relative_to(ROOT).as_posix())) for path in suite)]
    for path, reason in commands:
        name = path.relative_to(ROOT).as_posix()
        if reason:
            skipped.append((name, reason))
            print(f'SKIP {name}: {reason}')
            continue
        print(f'RUN  {name}', flush=True)
        try:
            if path.suffix == '.cpp':
                result = run_cpp(path, env, timeout)
            else:
                result = subprocess.run([sys.executable, str(path)], cwd=ROOT, env=env,
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        timeout=timeout)
            if result.returncode == 0:
                passed.append(name)
                print(f'PASS {name}')
            else:
                detail = result.stdout.strip() or f'exit status {result.returncode}'
                failed.append((name, detail[-5000:]))
                print(f'FAIL {name} (exit {result.returncode})')
                print(detail[-5000:])
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ''
            if isinstance(output, bytes):
                output = output.decode(errors='replace')
            failed.append((name, f'timed out after {timeout}s\n{output[-3000:]}'))
            print(f'FAIL {name} (timeout after {timeout}s)')
        except OSError as exc:
            failed.append((name, str(exc)))
            print(f'FAIL {name}: {exc}')

    elapsed = time.monotonic() - started
    print('\nOffline test summary')
    print(f'PASS: {len(passed)}  FAIL: {len(failed)}  SKIP: {len(skipped)}  TIME: {elapsed:.1f}s')
    if skipped:
        print('\nSkipped tests')
        for name, reason in skipped:
            print(f'- {name}: {reason}')
    if failed:
        print('\nFailed tests')
        for name, detail in failed:
            print(f'- {name}: {detail.splitlines()[-1] if detail else "failed"}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
