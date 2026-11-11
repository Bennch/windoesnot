#!/usr/bin/python3 -I
"""Fixed Polkit entry point for kernel and maintenance settings. No shell commands."""
import base64
import configparser
import ctypes
import ctypes.util
import fcntl
import hmac
import io
import json
import os
import pwd
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import stat
import sys
import time
import tomllib
import uuid

LANGUAGE_SETUP_API = 1
LOCALE_GEN = Path("/etc/locale.gen")
LANGUAGE_LOCALES = ("de_DE.UTF-8", "en_US.UTF-8")

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
SHELLS = ('bash', 'fish', 'zsh')
DB_LOCK = Path('/var/lib/pacman/db.lck')
MIRRORS_MARKER = Path('/var/lib/windoesnot/mirrors-ranked')
REFIND_CONF = Path('/boot/EFI/refind/refind.conf')
SDDM_THEMES_DIR = Path('/usr/share/sddm/themes')
SDDM_CONF = Path('/etc/sddm.conf.d/windoesnot.conf')
SDDM_WALLPAPER_DIR = Path('/var/lib/windoesnot/sddm-wallpaper')
SDDM_PRESETS = {
    'windoesnot': ('cinder', 'cinder-still', 'fire', 'glut-dunkel'),
    'silentsddm': ('default',),
}


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
    # pacman returns the number of missing targets, not a fixed error code.
    # Query individually so an offline install or missing variant stays usable.
    raw = '\n'.join(query('/usr/bin/pacman', '-Si', '--', name, allowed=(0, 1))
                    for name in names)
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
    # The portable desktop is also supported on an existing CachyOS host.
    # Such a host has no installer record, but rEFInd is unambiguous when both
    # of its required configuration files live on the mounted EFI partition.
    if REFIND_CONF.is_file() and Path('/boot/refind_linux.conf').is_file():
        return 'refind'
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
            'catalogAvailable': bool(repo),
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
            'printers': printers_status(), 'firewall': firewall_status(),
            'tools': {name: available(name) for name in ('cachyos-rate-mirrors', 'paccache', 'pacman-key', 'chwd', 'curl')}}


PRINTER_NAME = re.compile(r'[A-Za-z0-9_-]{1,64}')
PRINTER_URI = re.compile(r'[a-z][a-z0-9+.-]{1,20}://[\x21-\x7e]{1,400}')
# LocalSend's port (53317) is opened only by the explicit nearby-ports-set action.
NEARBY_PORT = 53317


def parse_printers(queues, default, found):
    """Parse lpstat -v, lpstat -d and lpinfo -v output without trusting any of it."""
    printers = []
    for line in queues.splitlines():
        match = re.match(r'device for (\S+): (\S+)$', line.strip())
        if match and PRINTER_NAME.fullmatch(match.group(1)):
            printers.append({'name': match.group(1), 'uri': match.group(2)})
    match = re.search(r'system default destination: (\S+)', default)
    candidates = []
    for line in found.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        uri = parts[1].strip()
        if PRINTER_URI.fullmatch(uri) and not uri.startswith(('file:', 'http')) and uri not in candidates:
            candidates.append(uri)
    return {'printers': printers, 'default': match.group(1) if match else None, 'candidates': candidates}


def printers_status():
    if not available('lpstat'):
        return None
    try:
        active = query('/usr/bin/systemctl', 'is-active', 'cups.service', allowed=(0, 3)) == 'active'
    except (RuntimeError, subprocess.SubprocessError):
        return None
    if not active:
        return {'cupsActive': False, 'printers': [], 'default': None, 'candidates': []}
    try:
        queues = query('/usr/bin/lpstat', '-v', allowed=(0, 1))
        default = query('/usr/bin/lpstat', '-d', allowed=(0, 1))
        found = query('/usr/bin/lpinfo', '-v', allowed=(0, 1), timeout=30)
    except (RuntimeError, subprocess.SubprocessError):
        return None
    return {'cupsActive': True, **parse_printers(queues, default, found)}


def printer_candidates():
    return (printers_status() or {}).get('candidates', [])


def firewall_status():
    if not available('ufw'):
        return None
    try:
        active = query('/usr/bin/systemctl', 'is-active', 'ufw.service', allowed=(0, 3)) == 'active'
    except (RuntimeError, subprocess.SubprocessError):
        return None
    return {'enabled': active}


def parse_firmware(raw):
    """Return [{device, version}] from fwupdmgr get-updates --json, or None if unreadable."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get('Devices'), list):
        return None
    updates = []
    for device in data['Devices']:
        releases = device.get('Releases') if isinstance(device, dict) else None
        if not releases or not isinstance(releases[0], dict):
            continue
        name = str(device.get('Name', ''))[:120]
        version = str(releases[0].get('Version', ''))[:60]
        if name and version:
            updates.append({'device': name, 'version': version})
    return updates


def firmware_status():
    if not available('fwupdmgr'):
        return None
    try:
        raw = query('/usr/bin/fwupdmgr', 'get-updates', '--json', allowed=(0, 2), timeout=120)
    except (RuntimeError, subprocess.SubprocessError):
        return None
    return parse_firmware(raw)


def battery_info():
    try:
        devices = query('/usr/bin/upower', '-e').splitlines()
    except (RuntimeError, FileNotFoundError):
        return None
    path = next((d for d in devices if '/battery_' in d), None)
    if not path:
        return None
    fields = {}
    for line in query('/usr/bin/upower', '-i', path).splitlines():
        key, sep, value = line.strip().partition(':')
        if sep:
            fields[key.strip()] = value.strip()
    return {'percentage': fields.get('percentage', '').rstrip('%'),
            'state': fields.get('state', ''),
            'timeToEmpty': fields.get('time to empty', ''),
            'timeToFull': fields.get('time to full', ''),
            'capacity': fields.get('capacity', '')}


def power_profiles():
    try:
        raw = query('/usr/bin/powerprofilesctl', 'list')
    except (RuntimeError, FileNotFoundError):
        return [], ''
    profiles, current = [], ''
    for line in raw.splitlines():
        match = re.match(r'^(\* |  )([a-z][\w-]*):$', line)
        if match:
            name = match.group(2)
            profiles.append(name)
            if match.group(1) == '* ':
                current = name
    return profiles, current


def power_status():
    profiles, current = power_profiles()
    return {'battery': battery_info(), 'profiles': profiles, 'currentProfile': current,
            'profilesAvailable': available('powerprofilesctl')}


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


def _ini_parser():
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    return parser


GRUB_DEFAULTS = Path('/etc/default/grub')
GRUB_DROPIN_DIR = Path('/etc/default/grub.d')
GRUB_THEME_DROPIN = GRUB_DROPIN_DIR / '99-windoesnot-theme.cfg'
GRUB_THEME_PATH = '/boot/grub/themes/windoesnot/theme.txt'


def grub_theme_value():
    """Effective GRUB_THEME: the last assignment grub-mkconfig sees (defaults, then grub.d/*.cfg)."""
    value = ''
    files = [GRUB_DEFAULTS] + (sorted(GRUB_DROPIN_DIR.glob('*.cfg')) if GRUB_DROPIN_DIR.is_dir() else [])
    for path in files:
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            match = re.match(r'\s*(?:export\s+)?GRUB_THEME=(.*)$', line)
            if match:
                try:
                    parts = shlex.split(match.group(1), comments=True)
                except ValueError:
                    continue
                value = parts[0] if parts else ''
    return value


def bootloader_theme_status():
    """Current bootloader theme state (unprivileged)."""
    loader = bootloader()
    supported = loader in ('grub', 'refind', 'limine')
    enabled = False
    if loader == 'grub':
        enabled = 'windoesnot' in grub_theme_value()
    elif loader == 'refind':
        try:
            enabled = REFIND_CONF.exists() and 'include themes/windoesnot/theme.conf' in REFIND_CONF.read_text()
        except OSError:
            pass
    elif loader == 'limine':
        path = Path('/boot/limine.conf')
        try:
            enabled = path.exists() and 'wallpaper:' in path.read_text()
        except OSError:
            pass
    return {'bootloader': loader, 'enabled': enabled, 'supported': supported}


def bootloader_theme_set(payload):
    """Enable or disable the WinDoesNot bootloader theme (privileged)."""
    loader = bootloader()
    enable = payload['enabled']
    if loader == 'grub':
        # A late drop-in wins over /etc/default/grub and the live image's 90-windoesnot.cfg.
        GRUB_DROPIN_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write(GRUB_THEME_DROPIN, 'GRUB_THEME="' + (GRUB_THEME_PATH if enable else '') + '"\n')
        command('/usr/bin/grub-mkconfig', '-o', '/boot/grub/grub.cfg', timeout=180)
    elif loader == 'refind':
        include_line = 'include themes/windoesnot/theme.conf\n'
        text = REFIND_CONF.read_text()
        if enable:
            if include_line not in text:
                atomic_write(REFIND_CONF, text.rstrip() + '\n' + include_line, mode=None)
        else:
            new_text = text.replace(include_line, '')
            if new_text != text:
                atomic_write(REFIND_CONF, new_text, mode=None)
    elif loader == 'limine':
        config = Path('/boot/limine.conf')
        text = config.read_text()
        if enable:
            if 'wallpaper:' not in text:
                efi_dir = 'limine'
                for d in ('limine', 'LIMINE'):
                    if Path('/boot/EFI/' + d).is_dir():
                        efi_dir = d
                        break
                wallpaper_path = 'boot():/EFI/' + efi_dir + '/background.png'
                theme_lines = (
                    'wallpaper: ' + wallpaper_path + '\n'
                    'interface_branding_color: fe6f2d\n'
                    'interface_help_color: f4f1eb\n'
                    'term_background: 80141414\n'
                    'term_foreground: f4f1eb\n'
                    'term_foreground_bright: fe6f2d\n'
                )
                atomic_write(config, theme_lines + text)
        else:
            new_text = re.sub(r'(?m)^wallpaper:.*\n?', '', text)
            new_text = re.sub(r'(?m)^interface_branding_color:.*\n?', '', new_text)
            new_text = re.sub(r'(?m)^interface_help_color:.*\n?', '', new_text)
            new_text = re.sub(r'(?m)^term_background:.*\n?', '', new_text)
            new_text = re.sub(r'(?m)^term_foreground:.*\n?', '', new_text)
            new_text = re.sub(r'(?m)^term_foreground_bright:.*\n?', '', new_text)
            if new_text != text:
                atomic_write(config, new_text)
        command('/usr/bin/limine-update')
    else:
        raise ValueError('Bootloader theme is not supported for this bootloader')
    return {'reboot': False}


def sddm_theme_status():
    """Current SDDM login-screen theme and preset, as last written by sddm-set-theme."""
    current = 'windoesnot'
    parser = _ini_parser()
    if parser.read(SDDM_CONF) and parser.has_option('Theme', 'Current'):
        current = parser.get('Theme', 'Current')
    if current not in SDDM_PRESETS:
        current = 'windoesnot'
    preset = SDDM_PRESETS[current][0]
    try:
        first_line = (SDDM_THEMES_DIR / current / 'theme.conf.user').read_text().splitlines()[0]
        if first_line.startswith('; windoesnot-preset:'):
            marked = first_line.split(':', 1)[1].strip()
            if marked in SDDM_PRESETS[current]:
                preset = marked
    except (OSError, IndexError):
        pass
    return {'theme': current, 'preset': preset}


def sddm_wallpaper_source(account):
    """The real user's current wallpaper: their Hyprland primary monitor's, or any one if unset."""
    primary = None
    try:
        first_line = (Path(account.pw_dir) / '.config/hypr/lua/state.lua').read_text().splitlines()[0]
        if first_line.startswith('-- state-json:'):
            data = json.loads(base64.b64decode(first_line[len('-- state-json:'):]))
            primary = data.get('primary_monitor')
    except (OSError, IndexError, ValueError, TypeError):
        pass
    try:
        text = (Path(account.pw_dir) / '.config/hypr/hyprpaper.conf').read_text()
    except OSError:
        return None
    paths = {}
    for block in re.findall(r'wallpaper\s*\{([^}]*)\}', text):
        monitor = re.search(r'^\s*monitor\s*=\s*(\S+)\s*$', block, re.MULTILINE)
        path = re.search(r'^\s*path\s*=\s*(\S+)\s*$', block, re.MULTILINE)
        if monitor and path:
            paths[monitor.group(1)] = path.group(1)
    if primary and primary in paths:
        return Path(paths[primary])
    return Path(next(iter(paths.values()))) if paths else None


def sddm_sync_wallpaper(account, force=False):
    """Refresh the world-readable wallpaper cache the SilentSDDM theme mirrors as its background.

    The cache directory is owned by the real user (not root) so the unprivileged
    Settings UI can keep it in sync on every wallpaper change without re-prompting."""
    SDDM_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chown(SDDM_WALLPAPER_DIR, account.pw_uid, account.pw_gid)
    target = SDDM_WALLPAPER_DIR / 'current.jpg'
    if target.exists() and not force:
        return
    source = sddm_wallpaper_source(account)
    if source and source.is_file():
        shutil.copy2(source, target)
        os.chown(target, account.pw_uid, account.pw_gid)
        os.chmod(target, 0o644)


def sddm_write_conf(current, general_extra):
    parser = _ini_parser()
    parser.read(SDDM_CONF)
    for section in ('General', 'X11', 'Theme'):
        if not parser.has_section(section):
            parser.add_section(section)
    parser.set('General', 'DisplayServer', 'x11')
    for key in ('InputMethod', 'GreeterEnvironment'):
        parser.remove_option('General', key)
    for key, value in general_extra.items():
        parser.set('General', key, value)
    # Always routed through our own Xsetup, regardless of the selected theme:
    # it also matches SDDM's X11 primary output to Hyprland's main monitor.
    parser.set('X11', 'DisplayCommand', '/usr/share/sddm/themes/windoesnot/Xsetup')
    parser.set('Theme', 'Current', current)
    buffer = io.StringIO()
    parser.write(buffer)
    atomic_write(SDDM_CONF, buffer.getvalue())


def sddm_set_theme(payload):
    theme = payload['theme']
    account = shell_account()
    if theme == 'windoesnot':
        preset = payload['preset']
        base = (SDDM_THEMES_DIR / 'windoesnot/presets' / (preset + '.conf')).read_text()
        atomic_write(SDDM_THEMES_DIR / 'windoesnot/theme.conf.user', f'; windoesnot-preset: {preset}\n' + base)
        sddm_write_conf('windoesnot', {})
    elif theme == 'silentsddm':
        merged = _ini_parser()
        merged.read_string((SDDM_THEMES_DIR / 'silentsddm/configs/default.conf').read_text())
        for section in ('LoginScreen', 'LockScreen'):
            if not merged.has_section(section):
                merged.add_section(section)
            merged.set(section, 'background', '"current.jpg"')
        buffer = io.StringIO()
        merged.write(buffer)
        atomic_write(SDDM_THEMES_DIR / 'silentsddm/theme.conf.user', '; windoesnot-preset: default\n' + buffer.getvalue())
        sddm_sync_wallpaper(account, force=True)
        link = SDDM_THEMES_DIR / 'silentsddm/backgrounds/current.jpg'
        if not link.is_symlink():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(SDDM_WALLPAPER_DIR / 'current.jpg')
        sddm_write_conf('silentsddm', {
            'InputMethod': 'qtvirtualkeyboard',
            'GreeterEnvironment': ('QML2_IMPORT_PATH=/usr/share/sddm/themes/silentsddm/components/,'
                                    'QT_IM_MODULE=qtvirtualkeyboard'),
        })
    return {'reboot': False}


def shell_account():
    uid = int(os.environ.get('PKEXEC_UID', os.getuid()))
    if uid < 1000 or uid == 65534:
        raise ValueError('Select a regular user account')
    return pwd.getpwuid(uid)


def shell_status():
    account = shell_account()
    allowed = Path('/etc/shells').read_text().splitlines()
    return {'current': Path(account.pw_shell).name,
            'available': [name for name in SHELLS if Path('/usr/bin/' + name).is_file()
                          and any(path in allowed for path in ('/usr/bin/' + name, '/bin/' + name))]}


def set_shell(name):
    account = shell_account()
    if name not in shell_status()['available']:
        raise ValueError('Install the selected shell first')
    command('/usr/bin/usermod', '--shell', '/usr/bin/' + name, '--', account.pw_name)
    return {'reboot': False}


ACCOUNTS_DIR = Path('/var/lib/AccountsService')
PASSWORD_MIN, PASSWORD_MAX = 8, 256
AVATAR_MAX = 256 * 1024
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
# These actions read their data from stdin, so secrets and image bytes never reach argv or the log.
STDIN_ACTIONS = ('password-change', 'avatar-set')


def caller_account():
    """The account that started pkexec. Every account action works on this user only."""
    raw = os.environ.get('PKEXEC_UID', '')
    if not raw.isdigit() or not 1000 <= int(raw) < 65534:
        raise ValueError('Only regular user accounts can change their own account')
    try:
        return pwd.getpwuid(int(raw)).pw_name
    except KeyError:
        raise ValueError('Unknown user account') from None


def stored_password_hash(user):
    for line in Path('/etc/shadow').read_text().splitlines():
        fields = line.split(':')
        if len(fields) > 1 and fields[0] == user:
            return fields[1]
    return None


def crypt_hash(password, setting):
    """Hash with libcrypt, the same library PAM uses, so yescrypt and SHA-512 hashes both verify."""
    library = ctypes.CDLL(ctypes.util.find_library('crypt') or 'libcrypt.so.2')
    library.crypt.restype = ctypes.c_char_p
    library.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    result = library.crypt(password.encode(), setting.encode())
    if not result or result.startswith(b'*'):
        return None
    return result.decode()


def verify_current_password(user, password):
    stored = stored_password_hash(user)
    # Locked ('!', '*') or empty hashes cannot be verified, so the change is refused.
    if not stored or stored[0] in '!*':
        return False
    computed = crypt_hash(password, stored)
    return computed is not None and hmac.compare_digest(computed.encode(), stored.encode())


def validate_password_change(data):
    if set(data) != {'current', 'password'} or any(type(data[key]) is not str for key in data):
        raise ValueError('Invalid password data')
    for value in data.values():
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('Passwords must not contain control characters')
    if not data['current'] or len(data['current'].encode()) > 1024:
        raise ValueError('Enter the current password')
    if not PASSWORD_MIN <= len(data['password']) <= PASSWORD_MAX:
        raise ValueError(f'The new password must have {PASSWORD_MIN} to {PASSWORD_MAX} characters')


def change_own_password(data):
    validate_password_change(data)
    user = caller_account()
    if not verify_current_password(user, data['current']):
        raise ValueError('The current password is wrong')
    # chpasswd reads user:password from stdin, so the new password is never an argument or logged.
    result = subprocess.run(['/usr/bin/chpasswd'], input=f"{user}:{data['password']}\n", env=ENV,
                            text=True, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError('The password was not changed')
    if LOG:
        LOG.write(f'Password changed for {user}\n')
    return {'reboot': False}


def validate_png(data):
    if type(data) is not bytes or not data.startswith(PNG_SIGNATURE) or len(data) < 64:
        raise ValueError('The picture must be a PNG image')
    if len(data) > AVATAR_MAX:
        raise ValueError('The picture is too large')


def set_own_avatar(data):
    validate_png(data)
    user = caller_account()
    icon = ACCOUNTS_DIR / 'icons' / user
    icon.parent.mkdir(parents=True, exist_ok=True)
    temporary = icon.with_name(icon.name + '.windoesnot-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as out:
            os.chmod(temporary, 0o644)
            out.write(data); out.flush(); os.fsync(out.fileno())
        temporary.replace(icon)
    finally:
        temporary.unlink(missing_ok=True)
    # AccountsService reads Icon= from users/<name>; keep every other key the file already has.
    user_file = ACCOUNTS_DIR / 'users' / user
    parser = _ini_parser()
    if user_file.exists():
        parser.read_string(user_file.read_text())
    if not parser.has_section('User'):
        parser.add_section('User')
    parser.set('User', 'Icon', str(icon))
    text = io.StringIO()
    parser.write(text, space_around_delimiters=False)
    atomic_write(user_file, text.getvalue(), mode=0o644)
    if LOG:
        LOG.write(f'Profile picture set for {user}\n')
    return {'reboot': False}


def read_stdin_payload(action):
    if action == 'password-change':
        line = sys.stdin.buffer.readline(16385)
        if not line.endswith(b'\n') or len(line) > 16384:
            raise ValueError('Invalid password data')
        data = json.loads(line.decode('utf-8'))
        if type(data) is not dict:
            raise ValueError('Invalid password data')
        return data
    data = sys.stdin.buffer.read(AVATAR_MAX + 1)
    validate_png(data)
    return data


def validate(action, payload):
    if type(payload) is not dict:
        raise ValueError('Arguments must be an object')
    if action in ('kernel-status', 'maintenance-status', 'shell-status', 'power-status', 'sddm-theme-status',
                  'bootloader-theme-status',
                  'scx-install', 'scx-stop', 'mirrors-rank', 'cache-clean', 'keyring-repair', 'lock-remove',
                  'drivers-configure', 'printer-service-start', 'firmware-apply') + STDIN_ACTIONS:
        if payload:
            raise ValueError('This action takes no arguments')
    elif action == 'locale-set':
        if set(payload) != {'locale'} or payload.get('locale') not in LANGUAGE_LOCALES:
            raise ValueError('Unsupported language locale')
    elif action == 'bootloader-theme-set':
        if set(payload) != {'enabled'} or type(payload['enabled']) is not bool:
            raise ValueError('Invalid bootloader-theme-set payload')
    elif action == 'sddm-set-theme':
        theme = payload.get('theme')
        if (set(payload) != {'theme', 'preset'} or theme not in SDDM_PRESETS
                or payload.get('preset') not in SDDM_PRESETS[theme]):
            raise ValueError('Unsupported SDDM theme')
    elif action == 'shell-set':
        if set(payload) != {'shell'} or payload['shell'] not in SHELLS:
            raise ValueError('Unsupported shell')
    elif action in ('kernel-install', 'kernel-remove'):
        if set(payload) != {'kernel'} or payload['kernel'] not in KERNELS:
            raise ValueError('Unsupported kernel')
    elif action == 'orphans-remove':
        names = payload.get('packages')
        if (set(payload) != {'packages'} or type(names) is not list or not 1 <= len(names) <= 500
                or any(type(n) is not str or not re.fullmatch(r'[a-zA-Z0-9@._+][a-zA-Z0-9@._+-]{0,254}', n) for n in names)
                or len(set(names)) != len(names)):
            raise ValueError('Invalid orphan package list')
    elif action == 'printer-add':
        if (set(payload) != {'uri', 'name'} or type(payload['uri']) is not str
                or not PRINTER_URI.fullmatch(payload['uri']) or type(payload['name']) is not str
                or not PRINTER_NAME.fullmatch(payload['name'])):
            raise ValueError('Invalid printer settings')
    elif action == 'printer-default':
        if set(payload) != {'name'} or type(payload['name']) is not str or not PRINTER_NAME.fullmatch(payload['name']):
            raise ValueError('Invalid printer name')
    elif action == 'firewall-set':
        if set(payload) != {'enabled'} or type(payload['enabled']) is not bool:
            raise ValueError('Invalid firewall setting')
    elif action == 'nearby-ports-set':
        if set(payload) != {'open'} or type(payload['open']) is not bool:
            raise ValueError('Invalid LocalSend port setting')
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
        record = None
    # An installer record is useful context but must not be a prerequisite for
    # an explicitly detected rEFInd installation on the user's existing host.
    # In both cases, require the EFI partition to be mounted before changing
    # packages: otherwise new images could be written to the root filesystem.
    if (record is None and loader == 'refind') or (record and record.get('firmware') == 'efi'):
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


def locale_progress(stage, step):
    print(json.dumps({'event': 'progress', 'stage': stage, 'step': step, 'total': 3}), flush=True)


def set_language_locale(locale):
    if locale not in LANGUAGE_LOCALES:
        raise ValueError('Unsupported language locale')
    previous = LOCALE_GEN.read_text()
    mode = stat.S_IMODE(LOCALE_GEN.stat().st_mode)
    locale_progress('prepare', 1)
    pattern = r'^\s*#?\s*' + re.escape(locale) + r'\s+UTF-8\s*$'
    updated, count = re.subn(pattern, locale + ' UTF-8', previous, flags=re.M)
    if not count:
        updated = updated.rstrip() + '\n' + locale + ' UTF-8\n'
    atomic_write(LOCALE_GEN, updated, mode)
    try:
        locale_progress('generate', 2)
        command('/usr/bin/locale-gen', timeout=600)
        installed = {line.strip().replace('.utf8', '.UTF-8') for line in query('/usr/bin/locale', '-a').splitlines()}
        if locale not in installed:
            raise ValueError('Language data could not be generated')
        locale_progress('apply', 3)
        command('/usr/bin/localectl', 'set-locale', 'LANG=' + locale,
                'LC_MESSAGES=' + locale, 'LC_TIME=' + locale)
    except Exception:
        atomic_write(LOCALE_GEN, previous, mode)
        raise
    return {'locale': locale, 'reboot': False}


def apply(action, payload):
    if action == 'locale-set':
        return set_language_locale(payload['locale'])
    if action == 'shell-set':
        return set_shell(payload['shell'])
    if action == 'sddm-set-theme':
        return sddm_set_theme(payload)
    if action == 'bootloader-theme-set':
        return bootloader_theme_set(payload)
    if action in ('mirrors-rank', 'cache-clean', 'keyring-repair', 'lock-remove', 'orphans-remove', 'drivers-configure'):
        return maintenance_apply(action, payload)
    if action == 'printer-service-start':
        command('/usr/bin/systemctl', 'enable', '--now', 'cups.service', timeout=120)
        return {'reboot': False}
    if action == 'printer-add':
        command('/usr/bin/systemctl', 'enable', '--now', 'cups.service', timeout=120)
        # Only devices found by the discovery run are accepted, never a free-form URI.
        if payload['uri'] not in printer_candidates():
            raise ValueError('The printer was not found. Search again.')
        command('/usr/bin/lpadmin', '-p', payload['name'], '-E', '-v', payload['uri'],
                '-m', 'everywhere', timeout=300)
        return {'reboot': False}
    if action == 'printer-default':
        names = [p['name'] for p in (printers_status() or {}).get('printers', [])]
        if payload['name'] not in names:
            raise ValueError('Unknown printer')
        command('/usr/bin/lpadmin', '-d', payload['name'], timeout=60)
        return {'reboot': False}
    if action == 'nearby-ports-set':
        if not available('ufw'):
            raise ValueError('ufw is not installed')
        for proto in ('tcp', 'udp'):
            rule = f'{NEARBY_PORT}/{proto}'
            if payload['open']:
                command('/usr/bin/ufw', 'allow', rule, timeout=60)
            else:
                command('/usr/bin/ufw', '--force', 'delete', 'allow', rule, timeout=60, allowed=(0, 1))
        return {'reboot': False}
    if action == 'firewall-set':
        if not available('ufw'):
            raise ValueError('ufw is not installed')
        if payload['enabled']:
            # Default policies first, so the firewall comes up with deny-incoming.
            command('/usr/bin/ufw', 'default', 'deny', 'incoming', timeout=60)
            command('/usr/bin/ufw', 'default', 'allow', 'outgoing', timeout=60)
            command('/usr/bin/ufw', '--force', 'enable', timeout=60)
            command('/usr/bin/systemctl', 'enable', 'ufw.service', timeout=60)
        else:
            command('/usr/bin/systemctl', 'disable', 'ufw.service', timeout=60)
            command('/usr/bin/ufw', '--force', 'disable', timeout=60)
        return {'reboot': False}
    if action == 'password-change':
        return change_own_password(payload)
    if action == 'avatar-set':
        return set_own_avatar(payload)
    if action == 'firmware-apply':
        if not available('fwupdmgr'):
            raise ValueError('fwupd is not installed')
        command('/usr/bin/fwupdmgr', 'update', '-y', '--no-reboot-check', timeout=3600)
        return {'reboot': True}
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
    if action in ('kernel-status', 'maintenance-status', 'shell-status', 'power-status', 'sddm-theme-status',
                  'bootloader-theme-status'):
        print(json.dumps({'kernel-status': kernel_status, 'maintenance-status': maintenance_status,
                          'shell-status': shell_status, 'power-status': power_status,
                          'sddm-theme-status': sddm_theme_status,
                          'bootloader-theme-status': bootloader_theme_status}[action]())); return
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
            logged = '[stdin]' if action in STDIN_ACTIONS else payload
            log.write(json.dumps({'action': action, 'arguments': logged}) + '\n'); log.flush()
            try:
                if action in STDIN_ACTIONS:
                    payload = read_stdin_payload(action)
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
