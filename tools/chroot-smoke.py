#!/usr/bin/env python3
"""Replay late image checks on a disposable copy of an existing airootfs."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('vm_overlay_test', ROOT / 'tools/vm-overlay-test.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

# Paths below refer only to the copied image. The original image stays untouched.
PERMISSIONS = r'''import pathlib, sys
bad=[]
base=pathlib.Path(sys.argv[1])
for root in ('/usr/lib/windoesnot', '/var/lib/windoesnot'):
 p=base/root.lstrip('/')
 if not p.is_dir(): bad.append(root + ': missing'); continue
 items=(p, *p.rglob('*')) if root.startswith('/usr/lib/') else (p,)
 for item in items:
  if item.is_symlink(): continue
  mode=item.stat().st_mode
  required=5 if item.is_dir() else 4
  if mode & required != required: bad.append(str(item) + ': not world readable/traversable')
print('\n'.join(bad) if bad else 'Readable image trees')
sys.exit(bool(bad))'''
PACMAN = r'''from pathlib import Path
import sys
root=Path(sys.argv[1])
conf=(root/'etc/pacman.conf').read_text()
include='Include = /etc/pacman.d/windoesnot.conf'
repo=(root/'etc/pacman.d/windoesnot.conf').read_text()
keys=root/'usr/share/pacman/keyrings'
checks=[conf.count(include)==1, '[windoesnot]' in repo, 'SigLevel = Required DatabaseRequired TrustedOnly' in repo,
        (keys/'windoesnot.gpg').is_file() and (keys/'windoesnot.gpg').stat().st_size>0,
        (keys/'windoesnot-trusted').read_text().strip()=='ED9530A990C6D39EB7D4BA8F9BDCA578FBF1DDB0:4:']
print('Pacman channel and keyring:', checks)
sys.exit(not all(checks))'''


def chroot_command(tree, *command):
    # Like arch-chroot in the real image build: /proc and /dev must exist inside, or cmake/ninja cannot even
    # start a test compile. A private mount and PID namespace inside the user namespace keeps this rootless.
    script = f'mount --rbind /dev {tree}/dev && mount --rbind /sys {tree}/sys 2>/dev/null; exec chroot {tree} "$@"'
    return ['podman', 'unshare', 'unshare', '--mount', '--pid', '--fork', f'--mount-proc={tree}/proc',
            'sh', '-c', script, 'sh', *command]


def check(name, command):
    result = subprocess.run(command, text=True, capture_output=True)
    print(('PASS' if result.returncode == 0 else 'FAIL'), name)
    if result.stdout: print(result.stdout, end='')
    if result.stderr: print(result.stderr, end='', file=sys.stderr)
    return result.returncode == 0


def self_test():
    command = chroot_command(Path('/tmp/image'), '/usr/bin/true')
    assert command[:4] == ['podman', 'unshare', 'unshare', '--mount'] and command[-1] == '/usr/bin/true' and '--mount-proc=/tmp/image/proc' in command
    assert '/usr/lib/windoesnot' in PERMISSIONS and '/var/lib/windoesnot' in PERMISSIONS
    assert 'windoesnot.gpg' in PACMAN and 'windoesnot.conf' in PACMAN
    assert overlay.destinations('desktop/bin/windoesnot-rebuild-plugins') == ('/usr/bin/windoesnot-rebuild-plugins',)
    compile(PERMISSIONS, '<permissions>', 'exec')
    compile(PACMAN, '<pacman>', 'exec')
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        library = base / 'usr/lib/windoesnot'
        library.mkdir(parents=True)
        (base / 'var/lib/windoesnot').mkdir(parents=True)
        module = library / 'module.so'
        module.write_bytes(b'ELF')
        assert subprocess.run([sys.executable, '-c', PERMISSIONS, directory], capture_output=True).returncode == 0
        module.chmod(0o600)
        assert subprocess.run([sys.executable, '-c', PERMISSIONS, directory], capture_output=True).returncode != 0
        (base / 'etc/pacman.d').mkdir(parents=True)
        (base / 'etc/pacman.conf').write_text('Include = /etc/pacman.d/windoesnot.conf\n')
        (base / 'etc/pacman.d/windoesnot.conf').write_text('[windoesnot]\nSigLevel = Required DatabaseRequired TrustedOnly\n')
        keys = base / 'usr/share/pacman/keyrings'
        keys.mkdir(parents=True)
        (keys / 'windoesnot.gpg').write_bytes(b'key')
        (keys / 'windoesnot-trusted').write_text('ED9530A990C6D39EB7D4BA8F9BDCA578FBF1DDB0:4:\n')
        assert subprocess.run([sys.executable, '-c', PACMAN, directory], capture_output=True).returncode == 0
        (keys / 'windoesnot-trusted').write_text('wrong\n')
        assert subprocess.run([sys.executable, '-c', PACMAN, directory], capture_output=True).returncode != 0
    print('PASS chroot checks and command formation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', nargs='?', type=Path, help='Existing build/<id>/work/x86_64/airootfs')
    parser.add_argument('files', nargs='*', help='Changed repository files to overlay')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.image is None:
        parser.error('image path required')
    image = args.image.resolve()
    if (image.name != 'airootfs' or image.parent.name != 'x86_64' or
            image.parent.parent.name != 'work' or image.parent.parent.parent.parent != ROOT / 'build' or
            not (image / 'etc/windoesnot-image-build').is_file()):
        parser.error('image must be a completed build/<id>/work/x86_64/airootfs')
    try:
        transfers = overlay.plan(args.files + ['tools/check-image-installer.py'])
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))
    scratch = Path(tempfile.mkdtemp(prefix='chroot-smoke-', dir=ROOT / 'build'))
    tree = scratch / 'airootfs'
    failed = False
    try:
        subprocess.run(['podman', 'unshare', 'cp', '-a', '--reflink=auto', str(image), str(tree)], check=True)
        for source, destination in transfers:
            target = tree / destination.lstrip('/')
            subprocess.run(['podman', 'unshare', 'install', '-d', '-m', '755', str(target.parent)], check=True)
            subprocess.run(['podman', 'unshare', 'cp', '-a', str(source), str(target)], check=True)
            print('OVERLAY', source.relative_to(ROOT), '=>', destination)
        checks = []
        if any(str(src.relative_to(ROOT)) == 'tools/build-installer-module.sh' for src, _ in transfers):
            checks.append(('installer module build', ['/usr/bin/bash', '/usr/share/windoesnot/tools/build-installer-module.sh']))
        checks += [
            ('installer', ['/usr/bin/python3', '/usr/share/windoesnot/tools/check-image-installer.py']),
            ('rebuild hook', ['/usr/bin/windoesnot-rebuild-plugins']),
            ('permissions', ['/usr/bin/python3', '-c', PERMISSIONS, '/']),
            ('pacman and keys', ['/usr/bin/python3', '-c', PACMAN, '/']),
        ]
        failed |= not check('remove rebuild markers', chroot_command(tree, '/usr/bin/rm', '-f',
                            '/var/lib/windoesnot/plugins-built-for', '/var/lib/windoesnot/components-built-for'))
        for name, command in checks:
            failed |= not check(name, chroot_command(tree, *command))
        log = tree / 'var/log/windoesnot-plugins-rebuild.log'
        if log.is_file():
            print('GUEST LOG', log, '\n', log.read_text(errors='replace')[-8000:])
    except (OSError, subprocess.CalledProcessError) as error:
        print('FAIL setup:', error, file=sys.stderr)
        failed = True
    finally:
        cleanup = subprocess.run(['podman', 'unshare', 'rm', '-rf', '--', str(scratch)], text=True, capture_output=True)
        if cleanup.returncode:
            print('FAIL cleanup:', cleanup.stderr, file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
