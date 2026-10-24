#!/usr/bin/env python3
"""CachyOS-style system setup in an install target: optimized repositories,
ranked mirrors and hardware drivers.

Repository selection follows CachyOS' Calamares `detect-architecture`; the
desktop packages accept the CPU-level `.N` rebuilds of their ABI pins.
Drivers come from the ISO snapshot in both modes, never from a rolling
partial upgrade. Profiles that need packages outside the snapshot (legacy
NVIDIA branches, DKMS network drivers) are recorded as pending instead.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

BASE = Path('/usr/share/windoesnot')
RECORD = Path('var/lib/windoesnot/system-setup.json')
LEVEL_REPOS = {
    'znver4': ('cachyos-v4-mirrorlist', ['cachyos-znver4', 'cachyos-core-znver4', 'cachyos-extra-znver4']),
    'v4': ('cachyos-v4-mirrorlist', ['cachyos-v4', 'cachyos-core-v4', 'cachyos-extra-v4']),
    'v3': ('cachyos-v3-mirrorlist', ['cachyos-v3', 'cachyos-core-v3', 'cachyos-extra-v3']),
}
MIRRORLISTS = {'cachyos': 'cachyos-mirrorlist', 'core': 'mirrorlist', 'extra': 'mirrorlist', 'multilib': 'mirrorlist'}
LEVEL_SECTIONS = {name for _, names in LEVEL_REPOS.values() for name in names}
# chwd writes these before pacman runs; a failed profile must not leave
# initramfs MODULES+= lines for drivers that were never installed.
CHWD_INITRAMFS = ['etc/mkinitcpio.conf.d/10-chwd.conf', 'etc/mkinitcpio.conf.d/10-chwd-kms.conf']


def is_zen4_or_newer(cpuinfo):
    flags = re.search(r'^flags\s*:\s*(.*)$', cpuinfo, re.M)
    family = re.search(r'^cpu family\s*:\s*(\d+)', cpuinfo, re.M)
    model = re.search(r'^model\s*:\s*(\d+)', cpuinfo, re.M)
    vendor = re.search(r'^vendor_id\s*:\s*(\S+)', cpuinfo, re.M)
    if not (flags and family and model) or 'avx512f' not in flags[1].split():
        return False
    if vendor and vendor[1] != 'AuthenticAMD':
        return False
    family, model = int(family[1]), int(model[1])
    if family == 0x19:
        return 0x10 <= model <= 0x1f or 0x60 <= model <= 0xaf
    return family == 0x1a


def cpu_level(ld_help, cpuinfo):
    """Return 'znver4', 'v4', 'v3' or None, in CachyOS' order of preference."""
    supported = set(re.findall(r'^\s*x86-64-(v\d) \(supported', ld_help, re.M))
    if is_zen4_or_newer(cpuinfo):
        return 'znver4'
    if 'v4' in supported:
        return 'v4'
    if 'v3' in supported:
        return 'v3'
    return None


def detect_level():
    ld_help = subprocess.run(['/usr/lib/ld-linux-x86-64.so.2', '--help'], capture_output=True, text=True).stdout
    return cpu_level(ld_help, Path('/proc/cpuinfo').read_text())


def configure_pacman(text, level):
    """Use ranked mirrorlists like an installed CachyOS and add the CPU-level repositories."""
    sections = []
    current = None
    for line in text.splitlines():
        header = re.fullmatch(r'\[([^\]]+)\]\s*', line)
        if header:
            current = [header[1], [line]]
            sections.append(current)
        elif current is None:
            sections.append([None, [line]])
        else:
            current[1].append(line)
    output = []
    for name, lines in sections:
        if name in LEVEL_SECTIONS:
            continue
        if name == 'options':
            lines = [l for l in lines if not re.match(r'\s*#?\s*(DisableSandbox|DownloadUser)\b', l)]
            while lines and not lines[-1].strip():
                lines.pop()
            # pacman's default for an installed system; the live image disables it.
            lines += ['DownloadUser = alpm', '']
        if name in MIRRORLISTS:
            body = [l for l in lines[1:] if not re.match(r'\s*(Server|Include)\s*=', l)]
            lines = [lines[0], f'Include = /etc/pacman.d/{MIRRORLISTS[name]}', *body]
        if name == 'cachyos' and level:
            mirrorlist, repos = LEVEL_REPOS[level]
            for repo in repos:
                output += [f'[{repo}]', f'Include = /etc/pacman.d/{mirrorlist}', '']
        output += lines
    result = '\n'.join(output).rstrip() + '\n'
    if level and '[cachyos]' not in result:
        raise ValueError('pacman.conf has no [cachyos] section')
    return result


def update_record(root, **values):
    path = root / RECORD
    data = json.loads(path.read_text()) if path.is_file() else {'schema_version': 1}
    data.update(values)
    for key in [key for key, value in data.items() if value is None]:
        del data[key]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def pacman_stage(root, level):
    for mirrorlist in {LEVEL_REPOS[level][0]} if level else set():
        if not (root / 'etc/pacman.d' / mirrorlist).is_file():
            raise RuntimeError('Missing mirror list ' + mirrorlist)
    config = root / 'etc/pacman.conf'
    config.write_text(configure_pacman(config.read_text(), level))
    update_record(root, cpu_level=level or 'x86-64', repositories=LEVEL_REPOS[level][1] if level else [])


def mirrors_stage(root, timeout=180):
    """Online only: rank mirrors now. Offline systems rank on their first connection."""
    try:
        result = subprocess.run(['cachyos-rate-mirrors'], timeout=timeout, capture_output=True, text=True)
        ranked = result.returncode == 0
        if not ranked:
            print(result.stderr[-2000:], file=sys.stderr)
    except subprocess.TimeoutExpired:
        ranked = False
    if ranked:
        (root / 'var/lib/windoesnot').mkdir(parents=True, exist_ok=True)
        (root / 'var/lib/windoesnot/mirrors-ranked').touch()
    update_record(root, mirrors_ranked=ranked)


def verify_bundle(bundle):
    manifest = json.loads((bundle / 'manifest.json').read_text())
    for filename, data in manifest['archives'].items():
        if hashlib.sha256((bundle / 'repository' / filename).read_bytes()).hexdigest() != data['sha256']:
            raise RuntimeError('Offline package checksum mismatch: ' + filename)
    return manifest


def driver_config(bundle, work):
    """pacman setup for chwd: the snapshot repository named [multilib].

    chwd drops every lib32- package unless its pacman.conf has a [multilib]
    section. The real database path stays: pacman replaces a symlinked
    `local` directory, which lost every new package entry (r11 VM test).
    """
    server = work / 'server'; server.mkdir()
    (server / 'multilib.db').symlink_to(bundle / 'repository/windoesnot-apps.db')
    config = work / 'pacman.conf'
    config.write_text('[options]\nArchitecture = auto\n'
                      'SigLevel = Required DatabaseOptional\nLocalFileSigLevel = Required\n'
                      'GPGDir = /etc/pacman.d/gnupg\n[multilib]\nServer = file://' + str(server) + '\n')
    return config


@contextmanager
def snapshot_multilib(sync=Path('/var/lib/pacman/sync')):
    """Keep a real multilib sync database out of reach and remove the snapshot copy afterwards."""
    names = ['multilib.db', 'multilib.db.sig']
    saved = []
    for name in names:
        if (sync / name).exists():
            (sync / name).rename(sync / (name + '.windoesnot-saved'))
            saved.append(name)
    try:
        yield
    finally:
        for name in names:
            (sync / name).unlink(missing_ok=True)
        for name in saved:
            (sync / (name + '.windoesnot-saved')).rename(sync / name)


def incomplete_entries(local=Path('/var/lib/pacman/local')):
    """Package directories without their description: files on disk pacman does not know about."""
    return sorted(entry.name for entry in local.iterdir() if entry.is_dir() and not (entry / 'desc').is_file())


def installed_profiles(environment):
    listing = subprocess.run(['chwd', '--list-installed'], capture_output=True, text=True, env=environment).stdout
    return sorted(set(re.findall(r'│\s*([a-z0-9][a-z0-9.-]*)\s*┆', listing)))


def drivers_stage(root, base=BASE):
    """Run chwd --autoconfigure against the verified ISO snapshot."""
    bundle = base / 'offline-apps'
    manifest = verify_bundle(bundle)
    if not manifest.get('chwd_packages'):
        update_record(root, drivers='pending', driver_reason='snapshot has no driver packages')
        return
    environment = dict(os.environ, LANG='C', LC_ALL='C')
    with tempfile.TemporaryDirectory(prefix='windoesnot-chwd-', dir='/var/tmp') as temporary, snapshot_multilib():
        config = driver_config(bundle, Path(temporary))
        subprocess.run(['pacman', '--config', str(config), '-Sy'], check=True)
        result = subprocess.run(['chwd', '--autoconfigure', '--pmconfig', str(config),
                                 '--pmcachedir', str(bundle / 'repository')],
                                capture_output=True, text=True, env=environment)
    print(result.stdout[-4000:])
    print(result.stderr[-4000:], file=sys.stderr)
    profiles = installed_profiles(environment)
    broken = incomplete_entries()
    if broken:
        raise RuntimeError('Incomplete package database after chwd: ' + ', '.join(broken))
    if result.returncode == 0:
        update_record(root, drivers='configured', driver_profiles=profiles, driver_reason=None)
        return
    # chwd runs pre_remove after a failed pacman call; keep this as a safety net.
    if 'nvidia' not in ' '.join(profiles):
        for name in CHWD_INITRAMFS:
            (root / name).unlink(missing_ok=True)
    update_record(root, drivers='pending', driver_profiles=profiles, driver_reason='chwd profile outside the ISO snapshot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['detect', 'pacman', 'mirrors', 'drivers'])
    parser.add_argument('--mode', choices=['online', 'offline'])
    args = parser.parse_args()
    if args.stage == 'detect':
        print(detect_level() or 'x86-64')
        return
    if os.geteuid() != 0 or os.environ.get('WINDOESNOT_INSTALL_TARGET') != '1' or not Path('/etc/windoesnot-image-build').is_file():
        raise SystemExit('Calamares installation target only')
    root = Path('/')
    if args.stage == 'pacman':
        pacman_stage(root, detect_level())
    elif args.stage == 'mirrors':
        mirrors_stage(root)
    else:
        drivers_stage(root)


if __name__ == '__main__':
    main()
