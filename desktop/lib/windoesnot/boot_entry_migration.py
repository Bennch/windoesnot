#!/usr/bin/env python3
"""WinDoesNot boot entry migration and guard for systemd-boot systems (PLAN A4).

Old installations (<= 0.1.0-30) carry kernel-install entries ``<machine-id>-<kernel>.conf`` next to the generic
``linux-*.conf`` entries. After the first kernel update the old default boots a kernel without modules. The migration
retires exactly those entries, after it has validated the generic replacement and, if the default points at a
retired entry, repaired the default. Kernel copies are never deleted (only entries are retired; a backup is kept).

Modes
  --preflight          read only, PreTransaction: abort the update when a systemd-boot system has no usable /boot
  --post-transaction   PostTransaction (default): validate, repair default, retire obsolete entries, write result.json

Exit codes: 0 ok / not applicable, 1 problem on a supported layout (the hook message tells the user to fix it
before rebooting).
"""
import argparse
import datetime
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MIN_FREE_BYTES = 64 * 1024 * 1024
STATE_DIR = 'var/lib/windoesnot/boot-migration'
KEEP_MARKER = '# windoesnot-keep'


class BootProblem(Exception):
    """The layout is supported but unsafe or inconsistent: nothing may be changed."""


def machine_id(root):
    value = (Path(root) / 'etc/machine-id').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{32}', value):
        raise BootProblem('invalid machine ID')
    return value


def classify(root):
    """-> 'systemd-boot' or 'not-applicable'. GRUB/BIOS systems are never touched."""
    boot = Path(root) / 'boot'
    has_entries = (boot / 'loader/entries').is_dir()
    has_loader = any((boot / p).exists() for p in ('EFI/systemd', 'EFI/BOOT/BOOTX64.EFI', 'loader/loader.conf'))
    if has_entries and has_loader:
        return 'systemd-boot'
    if has_grub(boot) or has_refind(boot) or has_limine(boot):
        return 'not-applicable'   # GRUB, rEFInd or Limine on a vfat ESP mounted at /boot (UEFI installs): nothing of ours to guard
    if boot_expected_but_missing(root):
        return 'systemd-boot-unavailable'
    return 'not-applicable'


def has_grub(boot):
    """True when /boot holds a GRUB setup (configuration or an EFI GRUB image)."""
    try:
        return (boot / 'grub/grub.cfg').is_file() or any((boot / 'EFI').glob('*/grub*.efi'))
    except OSError:
        return False


def has_refind(boot):
    """True when /boot holds a rEFInd setup (EFI image or the kernel options file the installer writes)."""
    try:
        return (boot / 'refind_linux.conf').is_file() or any((boot / 'EFI/refind').glob('*.efi'))
    except OSError:
        return False


def has_limine(boot):
    """True when /boot holds a Limine setup (configuration file or an EFI image in a limine directory)."""
    try:
        return any((boot / name).is_file() for name in ('limine.conf', 'limine.cfg')) or any(
            efi.is_file() for directory in (boot / 'EFI').glob('[Ll][Ii][Mm][Ii][Nn][Ee]*') for efi in directory.glob('*.[Ee][Ff][Ii]'))
    except OSError:
        return False


def boot_expected_but_missing(root):
    """True when the system declares a vfat /boot (fstab) or runs in UEFI mode with a systemd-boot ESP
    configured, yet /boot holds no loader: an unmounted ESP must never look like a GRUB/BIOS system."""
    root = Path(root)
    fstab = root / 'etc/fstab'
    try:
        for line in fstab.read_text().splitlines():
            fields = line.split()
            if len(fields) >= 3 and not line.lstrip().startswith('#') and fields[1] in ('/boot', '/efi') and fields[2] == 'vfat':
                return True
    except OSError:
        pass
    return False


def mount_info(root='/'):
    """Facts about the boot filesystem: {'mounted', 'fstype', 'rw', 'free'} (real system only)."""
    boot = Path(root) / 'boot'
    out = subprocess.run(['findmnt', '-n', '-o', 'FSTYPE,OPTIONS', '--target', str(boot)], capture_output=True, text=True)
    mounted = subprocess.run(['mountpoint', '-q', str(boot)]).returncode == 0
    fstype, options = '', ''
    if out.returncode == 0 and out.stdout.strip():
        parts = out.stdout.split(None, 1)
        fstype = parts[0]
        options = parts[1] if len(parts) > 1 else ''
    rw = 'rw' in options.split(',')
    return {'mounted': mounted, 'fstype': fstype, 'rw': rw, 'free': shutil.disk_usage(boot).free if boot.exists() else 0}


def check_mount(info):
    if not info.get('mounted'):
        raise BootProblem('/boot is not mounted')
    if info.get('fstype') != 'vfat':
        raise BootProblem('/boot is %s, expected vfat' % (info.get('fstype') or 'unknown'))
    if not info.get('rw'):
        raise BootProblem('/boot is read-only')
    if info.get('free', 0) < MIN_FREE_BYTES:
        raise BootProblem('/boot has less than 64 MiB free')


def _inside(boot, name):
    path = (boot / name.lstrip('/')).resolve()
    if not path.is_relative_to(boot.resolve()):
        raise BootProblem('boot file outside /boot: %s' % name)
    return path


def parse_entry(text):
    fields = {}
    for line in text.splitlines():
        match = re.match(r'\s*(\w[\w-]*)\s+(.*\S)\s*$', line)
        if match and not line.lstrip().startswith('#'):
            fields.setdefault(match.group(1), []).append(match.group(2))
    return fields


def validate_entry(boot, entry):
    """A generic entry must name a kernel and at least one initrd that exist, are plain files and are not empty."""
    fields = parse_entry(entry.read_text())
    if not fields.get('linux') or not fields.get('initrd'):
        raise BootProblem('incomplete boot entry: %s' % entry.name)
    for name in fields['linux'] + fields['initrd']:
        path = _inside(boot, name.split()[0])
        if not path.is_file() or path.stat().st_size == 0:
            raise BootProblem('missing or empty boot file %s (entry %s)' % (name, entry.name))
    if not any(re.search(r'\broot=', o) for o in fields.get('options', [])):
        raise BootProblem('boot entry without root= option: %s' % entry.name)
    return fields


def loader_default(boot):
    """Default pattern from loader.conf (e.g. 'linux-main.conf', '*-6.1*', '@saved') or None."""
    conf = boot / 'loader/loader.conf'
    if not conf.is_file():
        return None
    for line in conf.read_text().splitlines():
        match = re.match(r'\s*default\s+(\S+)', line)
        if match:
            return match.group(1)
    return None


def plan(root, mid=None):
    root = Path(root)
    boot = root / 'boot'
    mid = mid or machine_id(root)
    entries = boot / 'loader/entries'
    generic = sorted(entries.glob('linux-*.conf'))
    if not generic:
        raise BootProblem('no generic linux boot entries')
    for entry in generic:
        validate_entry(boot, entry)
    retire, keep = [], []
    for entry in sorted(entries.glob(mid + '-*.conf')):
        if entry.is_symlink():
            keep.append((entry.name, 'symlink'))
            continue
        text = entry.read_text()
        fields = parse_entry(text)
        kernel = (fields.get('linux') or [''])[0]
        if KEEP_MARKER in text:
            keep.append((entry.name, 'marked as keep'))
        elif not kernel.startswith('/%s/' % mid):
            keep.append((entry.name, 'not a kernel-install entry'))
        else:
            retire.append(entry)
    return {'machine_id': mid, 'generic': [e.name for e in generic], 'retire': [e.name for e in retire], 'keep': keep}


def default_target(boot, retire_names):
    """Entry that the default should be repaired to, or None when the default stays valid."""
    pattern = loader_default(boot)
    if pattern is None or pattern == '@saved':
        return None  # @saved is resolved from the EFI variable by the caller (see saved_default_id)
    from fnmatch import fnmatch
    retired = [n for n in retire_names if fnmatch(n, pattern) or fnmatch(n[:-5], pattern)]
    others = [p.name for p in (boot / 'loader/entries').glob('*.conf') if p.name not in retire_names and (fnmatch(p.name, pattern) or fnmatch(p.name[:-5], pattern))]
    return 'repair' if retired and not others else None


def saved_default_id(run=subprocess.run):
    """Entry id that systemd-boot would pick via the saved EFI variable, or None when unknown."""
    try:
        out = run(['bootctl', 'list', '--no-pager'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    for block in re.split(r'(?m)^\s*type:', out.stdout)[1:]:
        if '(default)' in block:
            match = re.search(r'(?m)^\s*id:\s*(\S+)', block)
            return match.group(1) if match else None
    return None


def preferred_replacement(generic, retire_names, boot, selected=None):
    """Preserve the selected kernel family when replacing an old entry."""
    from fnmatch import fnmatch
    matches = [name for name in retire_names if selected and
               (fnmatch(name, selected) or fnmatch(name[:-5], selected))]
    if len(matches) == 1:
        # Prefer the longest suffix: cachyos-lts must not match cachyos.
        for candidate in sorted(generic, key=len, reverse=True):
            family = candidate.removeprefix('linux-').removesuffix('.conf')
            if matches[0].endswith('-' + family + '.conf'):
                return candidate
    # Ambiguous globs use the standard non-LTS entry where available.
    for candidate in ('linux-main.conf', 'linux-cachyos.conf'):
        if candidate in generic:
            return candidate
    return sorted(generic)[0]


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.tmp-')
    with os.fdopen(fd, 'w') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def apply(root, set_default=None, mid=None, now=None):
    """Retire obsolete entries. set_default(entry_id) repairs the default; it must raise on failure.
    Returns the result dict (also written to result.json)."""
    root = Path(root)
    boot = root / 'boot'
    state = Path(root) / STATE_DIR
    result = {'state': 'ok', 'started': (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(), 'removed': [], 'kept': [], 'default_repaired': None, 'error': None}
    state.mkdir(parents=True, exist_ok=True)
    lock = open(state / 'lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        try:
            p = plan(root, mid)
        except BootProblem as exc:
            result.update(state='error', error=str(exc))
            raise
        result['kept'] = p['keep']
        if not p['retire']:
            result['state'] = 'nothing-to-do'
            return result
        configured_default = loader_default(boot)
        selected = saved_default_id() if configured_default == '@saved' else configured_default
        replacement = preferred_replacement(p['generic'], p['retire'], boot, selected)
        if default_target(boot, p['retire']) == 'repair' or (configured_default == '@saved' and selected in [n[:-5] for n in p['retire']] + p['retire']):
            if set_default is None:
                raise BootProblem('default points to an obsolete entry and cannot be repaired')
            try:
                set_default(replacement)
            except Exception as exc:  # the default must be valid before anything is retired
                raise BootProblem('could not repair the default boot entry: %s' % exc)
            result['default_repaired'] = replacement
        backup = state / ('backup-' + re.sub(r'[^0-9A-Za-z]', '', result['started']))
        backup.mkdir(parents=True, exist_ok=True)
        for name in p['retire']:
            shutil.copy2(boot / 'loader/entries' / name, backup / name)
        for name in p['retire']:
            (boot / 'loader/entries' / name).unlink()
            result['removed'].append(name)
        result['backup'] = str(backup)
        return result
    except BootProblem as exc:
        result.update(state='error', error=str(exc))
        raise
    finally:
        result['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            write_atomic(state / 'result.json', json.dumps(result, indent=2))
        finally:
            lock.close()


def bootctl_set_default(entry_id):
    out = subprocess.run(['bootctl', '--esp-path=/boot', 'set-default', entry_id], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or 'bootctl set-default failed')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--post-transaction', action='store_true')
    parser.add_argument('--root', default='/')
    args = parser.parse_args(argv)
    kind = classify(args.root)
    if kind == 'systemd-boot-unavailable':
        print('windoesnot boot %s FAILED: fstab lists a vfat /boot but it holds no systemd-boot loader (ESP not mounted?)' % ('guard' if args.preflight else 'migration'), file=sys.stderr)
        print('Mount the EFI system partition on /boot BEFORE updating the kernel or rebooting.', file=sys.stderr)
        return 1
    if kind == 'not-applicable':
        print('windoesnot boot migration: not a systemd-boot layout (GRUB/BIOS); nothing to do')
        return 0
    try:
        check_mount(mount_info(args.root))
        if args.preflight:
            plan(args.root)
            print('windoesnot boot guard: /boot and boot entries are usable')
            return 0
        result = apply(args.root, set_default=bootctl_set_default)
        print('windoesnot boot migration: %s%s' % (result['state'], (': removed ' + ', '.join(result['removed'])) if result['removed'] else ''))
        return 0
    except BootProblem as exc:
        print('windoesnot boot %s FAILED: %s' % ('guard' if args.preflight else 'migration', exc), file=sys.stderr)
        print('Fix the boot partition BEFORE rebooting; do not continue the update.' if args.preflight else
              'Boot entries were not changed. Do not reboot before this is fixed (see https://windoesnot.me/hilfe/bekannte-einschraenkungen/).', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
