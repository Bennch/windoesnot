#!/usr/bin/env python3
"""Overlay selected repository files in a disposable live VM and run checks."""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
# Prefix, guest destinations. Add narrow prefixes before broad ones.
MAPPINGS = (
    ('desktop/bin/windoesnot-migrate', ('/usr/bin/windoesnot-migrate', '/usr/local/bin/windoesnot-migrate')),
    ('desktop/share/applications/', ('/usr/share/applications/',)),
    ('desktop/bin/', ('/usr/bin/',)),
    ('desktop/config/quickshell/default/', ('/etc/skel/.config/quickshell/default/', '/home/liveuser/.config/quickshell/default/')),
    ('desktop/share/libalpm/hooks/', ('/usr/share/libalpm/hooks/',)),
    ('desktop/config/hyprdesk/', ('/etc/skel/.config/hyprdesk/', '/home/liveuser/.config/hyprdesk/')),
    ('tools/check-image-installer.py', ('/usr/share/windoesnot/tools/check-image-installer.py',)),
    ('tools/build-installer-module.sh', ('/usr/share/windoesnot/tools/build-installer-module.sh',)),
    ('desktop/lib/windoesnot/', ('/usr/lib/windoesnot/', '/usr/share/windoesnot/desktop/lib/windoesnot/')),
    ('iso/modules/', ('/usr/share/windoesnot/iso/modules/',)),
)

CHECKS = {
    'session': "test -e /etc/windoesnot-image-build && test -n \"$(find /run/user/1000/hypr -name .socket.sock -print -quit 2>/dev/null)\" && pgrep -u liveuser -x Hyprland && pgrep -u liveuser -x quickshell",
    'terminal': "test -d /usr/lib/windoesnot/LocalTerminal && runuser -u liveuser -- test -r /usr/lib/windoesnot/LocalTerminal/qmldir && runuser -u liveuser -- test -x /usr/lib/windoesnot/LocalTerminal",
    'channel': "pacman-key --list-keys && pacman -Sy",
    'hook': "test -f /usr/share/libalpm/hooks/90-windoesnot-plugins.hook && /usr/bin/python3 -m py_compile /usr/bin/windoesnot-rebuild-plugins && test -x /usr/bin/windoesnot-rebuild-plugins",
}
READY = "test -f /etc/windoesnot-image-build && systemctl is-active --quiet getty@tty1.service && " + CHECKS['session']
LOGS = "for f in /var/log/windoesnot-plugins-rebuild.log /run/user/1000/start-quickshell.log; do if test -f \"$f\"; then echo \"LOG $f\"; tail -n 80 \"$f\"; fi; done; journalctl -b -n 80 --no-pager"


def destinations(relative):
    for prefix, targets in MAPPINGS:
        if relative == prefix or relative.startswith(prefix):
            suffix = relative[len(prefix):]
            return tuple(target + suffix for target in targets)
    raise ValueError(f'No guest mapping for {relative}')


def plan(files):
    result = []
    for name in files:
        source = Path(name)
        if not source.is_absolute():
            source = ROOT / source
        source = source.resolve(strict=True)
        relative = source.relative_to(ROOT).as_posix()
        if not source.is_file() or source.is_symlink():
            raise ValueError(f'Expected regular repo file: {name}')
        result.extend((source, target) for target in destinations(relative))
    return result


def shell_command(script):
    return ['/usr/bin/bash', '-lc', script]


def vmctl(name, action, *arguments, check=True):
    return subprocess.run([sys.executable, str(ROOT / 'tools/vmctl.py'), '--vm-name', name, action, *map(str, arguments)],
                          text=True, capture_output=True, check=check, timeout=45)


def guest(name, script, check=True):
    return vmctl(name, 'exec', *shell_command(script), check=check)


def self_test():
    assert destinations('desktop/bin/windoesnot-session') == ('/usr/bin/windoesnot-session',)
    assert len(destinations('desktop/config/quickshell/default/shell.qml')) == 2
    assert destinations('desktop/config/hyprdesk/hyprdesk.py')[1] == '/home/liveuser/.config/hyprdesk/hyprdesk.py'
    assert shell_command('true') == ['/usr/bin/bash', '-lc', 'true']
    assert set(CHECKS) == {'session', 'terminal', 'channel', 'hook'}
    assert 'getty@tty1.service' in READY and 'quickshell' in READY
    assert plan(['desktop/bin/windoesnot-session'])[0][1] == '/usr/bin/windoesnot-session'
    print('PASS mapping and commands')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='*', help='Repository files to overlay')
    parser.add_argument('--iso', type=Path)
    parser.add_argument('--run', action='append', default=[], help='Guest shell command, repeatable')
    parser.add_argument('--only', choices=CHECKS, action='append', help='Run only named built-in checks')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.iso or not args.iso.is_file():
        parser.error('--iso must name an existing ISO')
    try:
        transfers = plan(args.files)
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))
    prefix = 'overlaytest-' + uuid.uuid4().hex[:10]
    process = None
    vm = None
    failed = False
    try:
        process = subprocess.Popen([str(ROOT / 'build-and-run.sh'), '--run-only', str(args.iso.resolve()),
                                    '--fresh-vm', '--headless', '--vm-name', prefix], cwd=ROOT,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            matches = list((ROOT / 'vm').glob(prefix + '-*'))
            if matches:
                vm = matches[0].name
                break
            if process.poll() is not None:
                raise RuntimeError(f'VM launcher exited {process.returncode}')
            time.sleep(2)
        if vm is None:
            raise TimeoutError('VM directory did not appear')
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'VM exited {process.returncode} before readiness')
            try:
                if guest(vm, READY, check=False).returncode == 0:
                    break
            except (OSError, subprocess.TimeoutExpired):
                pass
            time.sleep(5)
        else:
            raise TimeoutError('Login prompt and live desktop not ready after 300 seconds')
        print('PASS login and liveuser session', flush=True)
        for source, target in transfers:
            guest(vm, 'install -d -m 755 ' + shlex.quote(str(Path(target).parent)))
            vmctl(vm, 'push', source, target)
            guest(vm, 'chmod ' + format(source.stat().st_mode & 0o777, 'o') + ' ' + shlex.quote(target) +
                  (' && chown liveuser:liveuser ' + shlex.quote(target) if target.startswith('/home/liveuser/') else ''))
            print('PUSH', source.relative_to(ROOT), '=>', target, flush=True)
        commands = [(name, CHECKS[name]) for name in (args.only or list(CHECKS))]
        commands += [('custom', script) for script in args.run]
        for label, script in commands:
            result = guest(vm, script, check=False)
            print(('PASS' if result.returncode == 0 else 'FAIL'), label, flush=True)
            if result.stdout: print(result.stdout, end='')
            if result.stderr: print(result.stderr, end='', file=sys.stderr)
            failed |= result.returncode != 0
        if args.screenshot:
            screen = Path(vmctl(vm, 'screenshot').stdout.strip())
            shutil.copy2(screen, args.screenshot)
            print('Screenshot:', args.screenshot)
    except Exception as error:
        failed = True
        print('FAIL', error, file=sys.stderr)
    finally:
        if vm:
            try:
                logs = guest(vm, LOGS, check=False)
                print(logs.stdout, end='')
                if logs.stderr: print(logs.stderr, end='', file=sys.stderr)
            except Exception as error:
                print('Guest logs unavailable:', error, file=sys.stderr)
            for filename in ('serial.log', 'qemu.log'):
                path = ROOT / 'vm' / vm / filename
                if path.is_file():
                    print('LOG', path, '\n', path.read_text(errors='replace')[-8000:])
            if not args.keep:
                try: vmctl(vm, 'stop')
                except Exception as error: print('VM stop failed:', error, file=sys.stderr); failed = True
        if process:
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                if not args.keep: process.terminate()
        if vm and not args.keep and process and process.poll() is not None:
            shutil.rmtree(ROOT / 'vm' / vm)
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
