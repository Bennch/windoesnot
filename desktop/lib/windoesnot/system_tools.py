#!/usr/bin/python3 -I
"""Fixed Polkit entry point for kernel and maintenance settings. No shell commands."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import stat
import sys
import time
import tomllib
import uuid

ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'HOME': '/root'}
KERNELS = ('linux-cachyos', 'linux-cachyos-lts', 'linux-cachyos-bore',
           'linux-cachyos-rt-bore', 'linux-cachyos-eevdf', 'linux-cachyos-bmq', 'linux-cachyos-server')
SCHEDULERS = ('scx_lavd', 'scx_bpfland', 'scx_rusty')
MODES = ('Auto', 'Gaming', 'PowerSave', 'LowLatency', 'Server')
SETUP = Path('/var/lib/windoesnot/system-setup.json')
INSTALLATION = Path('/var/lib/windoesnot/installation.json')
SCX_CONFIG = Path('/etc/scx_loader/config.toml')
SCX_PATHS = (SCX_CONFIG, Path('/etc/scx_loader.toml'),
             Path('/usr/share/scx_loader/config.toml'), Path('/usr/share/scx_loader.toml'))
LOG_DIR = Path('/var/log/windoesnot/system-tools')
LOG = None
DB_LOCK = Path('/var/lib/pacman/db.lck')
MIRRORS_MARKER = Path('/var/lib/windoesnot/mirrors-ranked')
REFIND_CONF = Path('/boot/EFI/refind/refind.conf')


def command(*args, allowed=(0,), timeout=60):
    """Run only root-owned binaries with an isolated environment and closed stdin."""
    if LOG:
        LOG.write('\n$ ' + ' '.join(args) + '\n'); LOG.flush()
        result = subprocess.run(args, env=ENV, stdin=subprocess.DEVNULL, text=True,
                                stdout=LOG, stderr=subprocess.STDOUT, timeout=timeout)
    else:
        result = subprocess.run(args, env=ENV, stdin=subprocess.DEVNULL, text=True,
                                capture_output=True, timeout=timeout)
    if result.returncode not in allowed:
        detail = '' if LOG else (result.stderr or result.stdout or '').strip()[-1500:]
        raise RuntimeError(f'{Path(args[0]).name}: exit {result.returncode}. {detail}')
    # Read-only queries always use query(), including during logged mutations.
    return result


def query(*args, allowed=(0,), timeout=60):
    result = subprocess.run(args, env=ENV, stdin=subprocess.DEVNULL, text=True,
                            capture_output=True, timeout=timeout)
    if result.returncode not in allowed:
        raise RuntimeError(f'{Path(args[0]).name}: {(result.stderr or result.stdout).strip()[-1500:]}')
    return result.stdout.strip()


def available(binary):
    return Path('/usr/bin', binary).is_file()


def parse_setup(raw):
    data = json.loads(raw)
    if type(data) is not dict or data.get('schema_version') != 1:
        raise ValueError('Unsupported installer record')
    if data.get('cpu_level') not in ('znver4', 'v4', 'v3', 'x86-64'):
        raise ValueError('Invalid CPU level')
    if data.get('drivers') not in ('configured', 'pending'):
        raise ValueError('Invalid driver state')
    for field in ('repositories', 'driver_profiles'):
        if field not in data:
            data[field] = []
        if type(data[field]) is not list or any(type(x) is not str for x in data[field]):
            raise ValueError('Invalid installer list')
    data.setdefault('mirrors_ranked', False)
    if type(data['mirrors_ranked']) is not bool:
        raise ValueError('Invalid mirror state')
    return {k: data[k] for k in ('cpu_level', 'repositories', 'drivers', 'driver_profiles', 'mirrors_ranked')}


def read_setup():
    try:
        return parse_setup(SETUP.read_text())
    except (OSError, ValueError):
        return None


def packages():
    result = {}
    for line in query('/usr/bin/pacman', '-Q').splitlines():
        name, version = line.split(maxsplit=1)
        result[name] = version
    return result


def repository_packages(names):
    # Local sync database only. Missing variants must not trigger a database refresh.
    raw = query('/usr/bin/pacman', '-Si', '--', *names, allowed=(0, 1))
    result = {}; current = None
    for line in raw.splitlines():
        key, separator, value = line.partition(':')
        if not separator:
            continue
        if key.strip() == 'Name':
            current = value.strip(); result[current] = ''
        elif key.strip() == 'Version' and current:
            result[current] = value.strip()
    return result


def kernel_state(installed):
    release = os.uname().release
    running_path = Path('/usr/lib/modules') / release / 'pkgbase'
    running = running_path.read_text().strip() if running_path.is_file() else ''
    # Every installed kernel with modules counts, including kernels outside our picker.
    bases = {p.read_text().strip() for p in Path('/usr/lib/modules').glob('*/pkgbase')}
    bases.update(k for k in KERNELS if k in installed)
    bases.intersection_update(installed)
    return release, running, bases


def driver_state(installed):
    raw = query('/usr/bin/chwd', '--list-installed', allowed=(0, 1)) if available('chwd') else ''
    raw = re.sub(r'\x1b\[[0-9;]*m', '', raw)
    if 'No installed profiles' in raw:
        raw = ''
    # Current packages/profiles are authoritative; installer records may be stale.
    profiles = re.findall(r'│\s*([a-z0-9][a-z0-9.-]*)\s*┆', raw)
    nvidia = any(re.fullmatch(r'(?:linux[\w+-]*-nvidia(?:-open)?|nvidia(?:-open)?(?:-dkms)?)', name)
                 for name in installed if not name.startswith('linux-firmware'))
    if profiles:
        nvidia = any('nvidia' in profile for profile in profiles)
    return ', '.join(profiles) if profiles else raw, nvidia


def bootloader():
    try:
        record = json.loads(INSTALLATION.read_text())
        loader = record['bootloader']
        if loader in ('grub', 'limine', 'systemd-boot', 'refind'):
            return loader
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return ''


def cpu_level():
    # glibc checks CPUID and OS register support, unlike guessing from the CPU name.
    loader = '/usr/lib/ld-linux-x86-64.so.2'
    if Path(loader).exists():
        text = query(loader, '--help')
        for level in ('v4', 'v3', 'v2'):
            if re.search(r'x86-64-' + level + r' \(supported, searched\)', text):
                return level
    return 'x86-64'


def scx_status():
    supported = Path('/sys/kernel/sched_ext').is_dir()
    installed = available('scx_loader') and available('busctl')
    scheds = [s for s in SCHEDULERS if available(s)]
    config = {}
    config_error = ''
    try:
        for path in SCX_PATHS:
            if path.exists():
                config = tomllib.loads(path.read_text()); break
    except (OSError, ValueError) as error:
        config_error = str(error)
    active = query('/usr/bin/systemctl', 'is-active', 'scx_loader.service', allowed=(0, 3, 4)) == 'active'
    enabled = query('/usr/bin/systemctl', 'is-enabled', 'scx_loader.service', allowed=(0, 1, 3, 4)) == 'enabled'
    state_path = Path('/sys/kernel/sched_ext/state')
    state = state_path.read_text().strip() if state_path.exists() else ''
    current = ''
    if active:
        try:
            reply = query('/usr/bin/busctl', '--system', 'get-property',
                          'org.scx.Loader', '/org/scx/Loader', 'org.scx.Loader', 'CurrentScheduler')
            current = json.loads(reply[2:]) if reply.startswith('s ') else ''
            if current == 'unknown':
                current = ''
        except (RuntimeError, ValueError):
            pass
    return {'supported': supported, 'installed': installed, 'schedulers': scheds,
            'active': active, 'enabled': enabled, 'state': state, 'current': current,
            'defaultScheduler': config.get('default_sched', ''),
            'defaultMode': config.get('default_mode', 'Auto'), 'configError': config_error}


def kernel_status():
    installed = packages()
    repo = repository_packages(KERNELS)
    release, running, bases = kernel_state(installed)
    drivers, nvidia = driver_state(installed)
    repos = query('/usr/bin/pacman-conf', '--repo-list').splitlines()
    optimized = [r for r in repos if re.fullmatch(r'cachyos(?:-(?:core|extra))?-(?:v3|v4|znver4)', r)]
    rows = []
    for name in sorted(set(repo) | {n for n in installed if n in KERNELS or n in bases and n.startswith('linux-cachyos')}):
        rows.append({'name': name, 'installed': installed.get(name, ''), 'available': repo.get(name, ''),
                     'running': name == running,
                     'removable': bool(running and name in installed and name != running and len(bases) > 1 and name in KERNELS),
                     'selectable': name in KERNELS})
    return {'live': Path('/etc/windoesnot-image-build').exists(), 'setup': read_setup(),
            'cpuLevel': cpu_level(), 'repositories': optimized, 'drivers': drivers,
            'nvidia': nvidia, 'release': release, 'running': running,
            'kernels': rows, 'bootloader': bootloader(), 'scx': scx_status()}


def package_processes():
    # Include common libalpm frontends and chwd between its package transactions.
    names = {'pacman', 'pacman-static', 'paru', 'yay', 'pamac-daemon', 'packagekitd',
             'octopi', 'chwd', 'paccache', 'windoesnot-stor', 'aurora-helper'}
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            name = (proc / 'comm').read_text().strip()
            if name in names:
                found.append({'pid': int(proc.name), 'name': name})
        except FileNotFoundError:
            pass  # Process exited while scanning.
        except PermissionError:
            # Never infer a stale lock when process visibility is restricted.
            raise ValueError('Cannot check all package manager processes') from None
    return found


def cache_bytes():
    total = 0
    directories = query('/usr/bin/pacman-conf', 'CacheDir').splitlines()
    for directory in directories:
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
        except FileNotFoundError:
            continue
    return total


def orphan_packages():
    result = subprocess.run(['/usr/bin/pacman', '-Qdtq'], env=ENV, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=60)
    if result.returncode not in (0, 1) or (result.returncode == 1 and result.stderr.strip()):
        raise RuntimeError('Cannot read orphan packages: ' + result.stderr.strip())
    names = result.stdout.splitlines()
    if any(not re.fullmatch(r'[a-zA-Z0-9@._+][a-zA-Z0-9@._+-]{0,254}', n) for n in names):
        raise ValueError('Invalid package name in database')
    return sorted(set(names))


def maintenance_status():
    try:
        cache = cache_bytes()
    except (PermissionError, RuntimeError):
        cache = None
    try:
        processes = package_processes()
        visibility = True
    except ValueError:
        processes = []; visibility = False
    failed = query('/usr/bin/systemctl', '--failed', '--no-legend', '--plain', '--no-pager')
    return {'live': Path('/etc/windoesnot-image-build').exists(), 'setup': read_setup(),
            'mirrorsRanked': MIRRORS_MARKER.exists(), 'cacheBytes': cache,
            'lockExists': DB_LOCK.exists(), 'packageProcesses': processes,
            'processesVisible': visibility, 'orphans': orphan_packages(),
            'failedServices': failed.splitlines(),
            'tools': {name: available(name) for name in ('cachyos-rate-mirrors', 'paccache', 'pacman-key', 'chwd', 'curl')}}


def require_online():
    # A real HTTPS request rejects disconnected/captive portal environments.
    command('/usr/bin/curl', '--fail', '--silent', '--show-error', '--max-time', '20',
            '--output', '/dev/null', 'https://archlinux.org/', timeout=25)


def ensure_package_idle():
    if package_processes():
        raise ValueError('A package manager is running. Wait for it to finish.')


def remove_stale_lock():
    ensure_package_idle()
    try:
        before = DB_LOCK.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Unexpected package lock type')
    ensure_package_idle()
    try:
        after = DB_LOCK.lstat()
    except FileNotFoundError:
        return
    if (before.st_ino, before.st_dev, before.st_mtime_ns) != (after.st_ino, after.st_dev, after.st_mtime_ns):
        raise ValueError('The package lock changed. Try again later.')
    DB_LOCK.unlink()


def update_setup(**updates):
    # Preserve installer-owned fields; do not invent an installer record on older systems.
    if read_setup() is None:
        return
    data = json.loads(SETUP.read_text())
    data.update(updates)
    if updates.get('drivers') == 'configured':
        data.pop('driver_reason', None)
    atomic_write(SETUP, json.dumps(data, indent=2) + '\n')


def maintenance_apply(action, payload):
    ensure_package_idle()
    if action == 'mirrors-rank':
        require_online()
        command('/usr/bin/cachyos-rate-mirrors', timeout=1800)
        MIRRORS_MARKER.parent.mkdir(parents=True, exist_ok=True)
        MIRRORS_MARKER.touch()
        update_setup(mirrors_ranked=True)
    elif action == 'cache-clean':
        before = cache_bytes()
        command('/usr/bin/paccache', '-rk2', timeout=600)
        return {'reboot': False, 'freedBytes': max(0, before - cache_bytes())}
    elif action == 'keyring-repair':
        require_online()
        # Preserve all existing/custom trusted keys, including the WinDoesNot repo.
        command('/usr/bin/pacman-key', '--init', timeout=180)
        command('/usr/bin/pacman-key', '--populate', 'archlinux', 'cachyos', timeout=300)
        # Reinstall even if already current, with a complete system update.
        command('/usr/bin/pacman', '-Syu', '--noconfirm', '--', 'archlinux-keyring', 'cachyos-keyring', timeout=7200)
    elif action == 'lock-remove':
        remove_stale_lock()
    elif action == 'orphans-remove':
        current = set(orphan_packages())
        selected = payload['packages']
        if not set(selected) <= current:
            raise ValueError('The orphan list changed. Refresh and review it again.')
        # -R removes precisely the reviewed packages; dependencies are not added implicitly.
        command('/usr/bin/pacman', '-R', '--noconfirm', '--', *selected, timeout=7200)
    elif action == 'drivers-configure':
        if not available('chwd'):
            raise ValueError('chwd is not installed')
        require_online()
        update_system([])  # Any failure aborts before chwd can change drivers.
        command('/usr/bin/chwd', '--autoconfigure', timeout=1800)
        raw = query('/usr/bin/chwd', '--list-installed', allowed=(0, 1))
        profiles = sorted(set(re.findall(r'│\s*([a-z0-9][a-z0-9.-]*)\s*┆', raw)))
        update_setup(drivers='configured', driver_profiles=profiles)
        return {'reboot': True}
    else:
        raise ValueError('Unknown maintenance action')
    return {'reboot': False}


def validate(action, payload):
    if type(payload) is not dict:
        raise ValueError('Arguments must be an object')
    if action in ('kernel-status', 'maintenance-status', 'scx-install', 'scx-stop',
                  'mirrors-rank', 'cache-clean', 'keyring-repair', 'lock-remove', 'drivers-configure'):
        if payload:
            raise ValueError('This action takes no arguments')
    elif action in ('kernel-install', 'kernel-remove'):
        if set(payload) != {'kernel'} or payload['kernel'] not in KERNELS:
            raise ValueError('Unsupported kernel')
    elif action == 'orphans-remove':
        names = payload.get('packages')
        if (set(payload) != {'packages'} or type(names) is not list or not 1 <= len(names) <= 500
                or any(type(n) is not str or not re.fullmatch(r'[a-zA-Z0-9@._+][a-zA-Z0-9@._+-]{0,254}', n) for n in names)
                or len(set(names)) != len(names)):
            raise ValueError('Invalid orphan package list')
    elif action == 'scx-set':
        if (set(payload) != {'scheduler', 'mode', 'onBoot'} or payload['scheduler'] not in SCHEDULERS
                or payload['mode'] not in MODES or type(payload['onBoot']) is not bool):
            raise ValueError('Unsupported scheduler settings')
    else:
        raise ValueError('Unknown action')


def kernel_packages(name, installing):
    installed = packages()
    release, running, bases = kernel_state(installed)
    if not installing:
        if not running or running not in bases:
            raise ValueError('Cannot identify the running kernel. Restart before removing a kernel.')
        if name == running or len(bases - {name}) < 1:
            raise ValueError('The running and last remaining kernel cannot be removed')
        if name not in installed:
            raise ValueError('Kernel is not installed')
        return [p for p in (name, name + '-headers', name + '-nvidia-open') if p in installed]
    result = [name, name + '-headers']
    if driver_state(installed)[1]:
        result.append(name + '-nvidia-open')
    found = repository_packages(result)
    if any(p not in found for p in result):
        raise ValueError('Kernel, headers or matching NVIDIA package missing from package sources')
    return result


def check_bootloader(loader):
    tools = {'grub': 'grub-mkconfig', 'limine': 'limine-update', 'systemd-boot': 'sdboot-manage', 'refind': 'refind-install'}
    if loader not in tools or not available(tools[loader]):
        raise ValueError('No supported installer bootloader record or loader tool is missing')
    # An unmounted ESP would put new images in the root filesystem, hiding them at boot.
    query('/usr/bin/findmnt', '--verify', '--tab-file', '/etc/fstab')
    try:
        record = json.loads(INSTALLATION.read_text())
    except (OSError, ValueError):
        raise ValueError('Cannot read installation record') from None
    if record.get('firmware') == 'efi':
        if query('/usr/bin/findmnt', '-n', '-o', 'FSTYPE', '--mountpoint', '/boot') != 'vfat':
            raise ValueError('The EFI boot partition must be mounted at /boot')
    if loader == 'refind' and (not Path('/boot/refind_linux.conf').is_file() or not REFIND_CONF.is_file()):
        raise ValueError('Missing rEFInd Linux command line configuration')


def refresh_bootloader(loader):
    if loader == 'grub':
        command('/usr/bin/grub-mkconfig', '-o', '/boot/grub/grub.cfg', timeout=180)
    elif loader == 'limine':
        command('/usr/bin/limine-update', timeout=180)
    elif loader == 'systemd-boot':
        command('/usr/bin/sdboot-manage', 'remove', timeout=180)
        command('/usr/bin/sdboot-manage', 'gen', timeout=180)
    elif loader == 'refind':
        # rEFInd discovers /boot/vmlinuz-* directly; mkinitcpio generates images.
        if not Path('/boot/refind_linux.conf').is_file():
            raise ValueError('Missing rEFInd Linux command line configuration')
        refresh_refind_versions()
    else:
        raise ValueError('Unsupported bootloader')


def refresh_refind_versions():
    text = REFIND_CONF.read_text()
    versions = set(KERNELS)
    pattern = r'(?m)^\s*extra_kernel_version_strings\s+([^\n]*)$'
    for match in re.finditer(pattern, text):
        for token in shlex.split(match.group(1), comments=True):
            versions.update(v for v in token.split(',') if v)
    # More specific names must precede linux/linux-cachyos for initramfs matching.
    value = ','.join(sorted(versions, key=lambda name: (-len(name), name)))
    line = 'extra_kernel_version_strings "' + value.replace('"', '\\"') + '"'
    updated = re.sub(pattern, lambda match: line, text)
    if not re.search(pattern, text):
        updated = text.rstrip() + '\n' + line + '\n'
    if updated != text:
        if LOG:
            (LOG_DIR / (Path(LOG.name).stem + '-refind.conf')).write_text(text)
        atomic_write(REFIND_CONF, updated, mode=None)


def update_system(names):
    command('/usr/bin/pacman', '-Syu', '--needed', '--noconfirm', '--', *names, timeout=7200)


def scx_call(method, *args):
    command('/usr/bin/busctl', '--system', 'call', 'org.scx.Loader', '/org/scx/Loader',
            'org.scx.Loader', method, *args)


def replace_scx_defaults(text, scheduler, mode):
    # Keep custom scheduler flags/comments; replace only root-level defaults.
    tomllib.loads(text)
    match = re.search(r'(?m)^\s*\[', text)
    offset = match.start() if match else len(text)
    root, tables = text[:offset], text[offset:]
    root = re.sub(r'(?m)^\s*default_(?:sched|mode)\s*=.*\n?', '', root)
    result = f'default_sched = "{scheduler}"\ndefault_mode = "{mode}"\n' + root + '\n' + tables
    tomllib.loads(result)
    return result


def atomic_write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.windoesnot-' + uuid.uuid4().hex)
    try:
        with temporary.open('x') as out:
            if mode is not None:
                os.chmod(temporary, mode)
            out.write(text); out.flush(); os.fsync(out.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def wait_scx(scheduler):
    # The D-Bus method queues a request before the BPF scheduler has attached.
    for _ in range(40):
        time.sleep(0.25)
        state = scx_status()
        if state['current'] == scheduler and state['state'] == 'enabled':
            return
    detail = query('/usr/bin/journalctl', '-u', 'scx_loader.service', '-n', '20', '--no-pager')
    if LOG:
        LOG.write(detail + '\n'); LOG.flush()
    raise ValueError('Scheduler did not start. See the service log; the kernel scheduler remains available.')


def set_scx(payload):
    state = scx_status()
    if not state['supported'] or not state['installed'] or payload['scheduler'] not in state['schedulers']:
        raise ValueError('Scheduler support or selected scheduler is missing')
    # Do not silently take over a separately configured legacy scheduler.
    if query('/usr/bin/systemctl', 'is-active', 'scx.service', allowed=(0, 3, 4)) == 'active':
        raise ValueError('scx.service is active; disable it before using scx_loader')
    if query('/usr/bin/systemctl', 'is-enabled', 'scx.service', allowed=(0, 1, 3, 4)) == 'enabled':
        raise ValueError('scx.service is enabled; disable it before using scx_loader')
    if state['state'] == 'enabled' and not state['active']:
        raise ValueError('A scheduler is running outside scx_loader. Stop it before switching.')
    old = SCX_CONFIG.read_text() if SCX_CONFIG.exists() else None
    template = next((p.read_text() for p in SCX_PATHS if p.is_file()), '')
    updated = replace_scx_defaults(template, payload['scheduler'], payload['mode'])
    if payload['onBoot']:
        # Save a recoverable copy before the first change in this invocation.
        if old is not None and LOG:
            (LOG_DIR / (Path(LOG.name).stem + '-scx.toml')).write_text(old)
        atomic_write(SCX_CONFIG, updated)
    try:
        command('/usr/bin/systemctl', 'start', 'scx_loader.service')
        scx_call('SwitchScheduler', 'su', payload['scheduler'], str(MODES.index(payload['mode'])))
        wait_scx(payload['scheduler'])
        command('/usr/bin/systemctl', 'enable' if payload['onBoot'] else 'disable', 'scx_loader.service')
    except Exception:
        if payload['onBoot']:
            if old is None:
                SCX_CONFIG.unlink(missing_ok=True)
            else:
                atomic_write(SCX_CONFIG, old)
        raise


def apply(action, payload):
    if action in ('mirrors-rank', 'cache-clean', 'keyring-repair', 'lock-remove', 'orphans-remove', 'drivers-configure'):
        return maintenance_apply(action, payload)
    if action in ('kernel-install', 'kernel-remove'):
        check_bootloader(bootloader())
        names = kernel_packages(payload['kernel'], action == 'kernel-install')
        if action == 'kernel-install':
            update_system(names)
        else:
            command('/usr/bin/pacman', '-R', '--noconfirm', '--', *names, timeout=7200)
        # The stock GRUB package has no kernel-triggered menu hook. Refresh via
        # the installed loader tool as well; the other generators are idempotent.
        refresh_bootloader(bootloader())
        return {'reboot': True}
    if action == 'scx-install':
        if not Path('/sys/kernel/sched_ext').is_dir():
            raise ValueError('The running kernel does not support sched-ext')
        # CachyOS scx-tools contains scx_loader (check actual image metadata).
        update_system(['scx-scheds', 'scx-tools'])
    elif action == 'scx-set':
        set_scx(payload)
    elif action == 'scx-stop':
        command('/usr/bin/systemctl', 'disable', '--now', 'scx_loader.service')
    return {'reboot': False}


def main():
    global LOG
    if len(sys.argv) not in (2, 3) or len(sys.argv[-1]) > 16384:
        raise ValueError('Invalid arguments')
    action = sys.argv[1]
    payload = json.loads(sys.argv[2]) if len(sys.argv) == 3 else {}
    validate(action, payload)
    if action in ('kernel-status', 'maintenance-status'):
        print(json.dumps(kernel_status() if action == 'kernel-status' else maintenance_status())); return
    if os.geteuid() != 0:
        raise PermissionError('Use the authorized pkexec entry point')
    if Path('/etc/windoesnot-image-build').exists():
        raise ValueError('System changes are unavailable in a live session')
    lock_dir = Path('/run/windoesnot-system-tools')
    lock_dir.mkdir(mode=0o755, exist_ok=True)
    with (lock_dir / 'operation.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another system tool is running') from None
        LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o755)
        log_path = LOG_DIR / (time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8] + '.log')
        with log_path.open('x') as log:
            os.chmod(log_path, 0o644); LOG = log
            log.write(json.dumps({'action': action, 'arguments': payload}) + '\n'); log.flush()
            try:
                result = apply(action, payload)
                print(json.dumps({'ok': True, 'log': str(log_path), **result}))
            except Exception as error:
                log.write('\nERROR: ' + str(error) + '\n'); log.flush()
                detail = log_path.read_text()[-6000:]
                print(json.dumps({'error': str(error), 'log': str(log_path), 'detail': detail}))
                return 1
            finally:
                LOG = None
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, PermissionError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)})); sys.exit(1)
