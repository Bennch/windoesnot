#!/usr/bin/python3 -I
"""Remove an old operating system (Windows) after the data move and give the space to Linux.

Safety by design: the targets always come from a fresh scan (Windows is verified by mounting the NTFS partition
read-only and looking for Windows/System32), never from the caller. Mounted partitions, EFI system partitions and
the running system are excluded. Before every deletion the partition is matched again by PARTUUID and disk GUID.
Commands go through an injectable runner without a shell; --dry-run only prints them. The first layer below
(inventory, identity helpers) is conservative classification; the second layer (scan, plan, execute, CLI) adds the
execution with all checks.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DEVICE = re.compile(r'^/dev/(sd[a-z]+[0-9]*|nvme[0-9]+n[0-9]+(p[0-9]+)?|vd[a-z]+[0-9]*|mmcblk[0-9]+(p[0-9]+)?)$')
ESP = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
MSR = 'e3c9e316-0b5c-4db8-817d-f92df00215ae'
RECOVERY = 'de94bba4-06d1-4d40-a16a-bfd50179d6ac'
ESP_TYPES = {ESP, '0xef', 'ef'}


def valid_device(value):
    return isinstance(value, str) and bool(DEVICE.fullmatch(value))


def inventory(lsblk, windows_verified=()):
    """Classify a supplied lsblk tree; a caller must verify Windows read-only.

    Ancillary partitions are suggestions only: matching a type or label does
    not establish their ownership. Mounted partitions and their ancestors are
    never deletion candidates. This function does not authorize operations.
    """
    if not isinstance(lsblk, dict) or not isinstance(lsblk.get('blockdevices'), list):
        raise ValueError('Invalid lsblk inventory')
    verified = set(windows_verified)
    result = []
    seen = set()
    def has_mount(node):
        mounts = node.get('mountpoints')
        children = node.get('children') or []
        if not isinstance(mounts, list) or not isinstance(children, list):
            raise ValueError('Missing mount or child information')
        return any(mounts) or any(has_mount(child) for child in children)

    def visit(node, disk=None, ancestor_mounted=False):
        if not isinstance(node, dict):
            raise ValueError('Invalid block device')
        path = node.get('path')
        if not valid_device(path) or path in seen:
            raise ValueError('Invalid or duplicate device name')
        seen.add(path)
        children = node.get('children') or []
        if not isinstance(children, list):
            raise ValueError('Invalid block children')
        mounts = node.get('mountpoints')
        if not isinstance(mounts, list):
            raise ValueError('Missing mount information')
        mounted = ancestor_mounted or any(mounts)
        kind = node.get('type')
        if kind == 'disk':
            disk = path
        elif kind == 'part':
            if not disk:
                raise ValueError('Partition parent unknown')
            parttype = (node.get('parttype') or '').lower()
            fs = (node.get('fstype') or '').lower()
            label = node.get('label') or ''
            protected = mounted or has_mount(node) or parttype in ESP_TYPES or bool(children)
            role = 'other'
            if path in verified and fs == 'ntfs':
                role = 'windows'
            elif parttype in (MSR, RECOVERY) or label.lower() in ('system reserved', 'system-reserviert'):
                role = 'possible-windows-support'
            result.append({'device': path, 'disk': disk, 'size': node.get('size'), 'label': label,
                           'type': parttype, 'filesystem': fs, 'role': role,
                           'protected': protected, 'automatic': False})
        else:
            raise ValueError('Unsupported device topology')
        for child in children:
            visit(child, disk, mounted)
    for node in lsblk['blockdevices']:
        visit(node)
    if not verified.issubset(seen):
        raise ValueError('Verified source absent from inventory')
    return result


def confirmed(backup, phrase, language='de', system='windows'):
    expected = 'DELETE WINDOWS' if language != 'de' else ('WINDOWS LOESCHEN' if system == 'windows' else 'ALTES SYSTEM LOESCHEN')
    return backup is True and phrase == expected


def command_runner(argv, input=None):
    """Run one fixed argument vector without a shell, stopping on failure."""
    return subprocess.run(argv, check=True, text=True, capture_output=True, timeout=900, input=input)


def deletion_preview(lsblk, windows_verified):
    """Build a non-executable preview from the classification, never a target list.

    A preview is not authorization: the scan, device identities and mounts must
    be checked again immediately before any future implementation executes it.
    """
    rows = inventory(lsblk, windows_verified)
    by_path = {node['path']: node for node in lsblk['blockdevices']}
    commands = []
    targets = [row for row in rows if row['role'] == 'windows' and not row['protected']]
    for row in targets:
        disk = by_path[row['disk']]
        table = (disk.get('pttype') or '').lower()
        # Partition numbers must come from lsblk, not from a path supplied by
        # a caller or inferred from a device name.
        matches = [node for node in disk.get('children', []) if node.get('path') == row['device']]
        if len(matches) != 1:
            raise ValueError('Partition is not a direct child of its disk')
        number = matches[0].get('partn')
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError('Missing partition number')
        if table == 'gpt':
            commands.append(['sgdisk', '-d', str(number), row['disk']])
        elif table == 'dos':
            commands.append(['sfdisk', '--delete', row['disk'], str(number)])
        else:
            raise ValueError('Unsupported partition table')
    if commands:
        commands.append(['udevadm', 'settle'])
    return commands


def windows_boot_entries(efibootmgr_output):
    """Find exact Windows Boot Manager labels in efibootmgr output."""
    if not isinstance(efibootmgr_output, str):
        raise ValueError('Invalid EFI boot inventory')
    entries = []
    seen = set()
    for line in efibootmgr_output.splitlines():
        match = re.match(r'^Boot([0-9A-Fa-f]{4})\*?\s+([^\t]+)(?:\t.*)?$', line)
        if match and match.group(2).strip() == 'Windows Boot Manager':
            number = match.group(1).upper()
            if number in seen:
                raise ValueError('Duplicate EFI boot entry')
            seen.add(number)
            entries.append(number)
    return entries


def persistent_identity(disk, partition):
    """Extract stable identifiers; incomplete identities cannot authorize removal."""
    if disk.get('type') != 'disk' or partition.get('type') != 'part':
        raise ValueError('Invalid identity topology')
    if partition not in (disk.get('children') or []):
        raise ValueError('Partition is not a direct child of disk')
    result = {}
    for output_key, node, key in (('partuuid', partition, 'partuuid'),
                                  ('fs_uuid', partition, 'uuid'),
                                  ('disk_id', disk, 'ptuuid')):
        value = node.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9-]{4,128}', value):
            raise ValueError('Missing or invalid persistent identity')
        result[output_key] = value.lower()
    return result


def match_persistent_identity(lsblk, identity):
    """Resolve exactly one direct partition with all three identifiers."""
    if not isinstance(lsblk, dict) or not isinstance(lsblk.get('blockdevices'), list):
        raise ValueError('Invalid lsblk inventory')
    if not isinstance(identity, dict) or set(identity) != {'partuuid', 'fs_uuid', 'disk_id'}:
        raise ValueError('Invalid persistent identity')
    matches = []
    for disk in lsblk['blockdevices']:
        if not isinstance(disk, dict) or disk.get('type') != 'disk':
            raise ValueError('Invalid disk inventory')
        for partition in disk.get('children') or []:
            try:
                candidate = persistent_identity(disk, partition)
            except ValueError:
                continue
            if candidate == identity:
                if not valid_device(disk.get('path')) or not valid_device(partition.get('path')):
                    raise ValueError('Invalid device path')
                matches.append(partition['path'])
    if len(matches) != 1:
        raise ValueError('Persistent identity missing or ambiguous')
    return matches[0]


# --------------------------------------------------------------------------------------------------------------
# Second layer: scan, plan, execute
# --------------------------------------------------------------------------------------------------------------
LSBLK_COLUMNS = 'NAME,PATH,TYPE,SIZE,FSTYPE,LABEL,PARTTYPE,PARTN,PTTYPE,MOUNTPOINTS,PARTUUID,UUID,PTUUID'
REPORT_PATH = Path('/var/lib/windoesnot/migration-report.json')
RESULT_PATH = Path('/var/lib/windoesnot/remove-old-os-report.json')
MOUNT_ROOT = Path('/run/windoesnot-remove-old-os')
SECTOR = re.compile(r'^[0-9]+s$')


class Environment:
    """Everything with side effects, replaceable in tests."""

    def __init__(self, run=None, geteuid=None, which=None, report_path=REPORT_PATH):
        self.run = run or command_runner
        self.geteuid = geteuid or os.geteuid
        self.which = which or shutil.which
        self.report_path = Path(report_path)

    def lsblk(self):
        return only_real_disks(normalise_lsblk(json.loads(self.run(['lsblk', '-J', '-b', '-o', LSBLK_COLUMNS]).stdout)))

    def is_dir(self, path):
        return Path(path).is_dir()

    # File system side effects of the boot cleanup and the data partition option live here so that tests can
    # replace every one of them (a test must never touch the real /boot or /etc).
    def ismount(self, path):
        return os.path.ismount(path)

    def realpath(self, path):
        return os.path.realpath(path)

    def is_symlink(self, path):
        return Path(path).is_symlink()

    def exists_file(self, path):
        return Path(path).is_file()

    def rmtree(self, path):
        shutil.rmtree(path)

    def mkdir(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)

    def append_text(self, path, text):
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(text)


def normalise_lsblk(tree):
    """lsblk prints numbers as strings in some versions; the checks expect integers and lowercase GUIDs."""
    def visit(node):
        for key in ('size', 'partn'):
            value = node.get(key)
            if isinstance(value, str) and value.isdigit():
                node[key] = int(value)
        for key in ('parttype', 'partuuid', 'uuid', 'ptuuid'):
            if isinstance(node.get(key), str):
                node[key] = node[key].lower()
        if node.get('mountpoints') is None:
            node['mountpoints'] = []
        for child in node.get('children') or []:
            visit(child)
    for node in tree.get('blockdevices', []):
        visit(node)
    return tree


def only_real_disks(tree):
    """Keep physical-looking disks only (no loop, optical or zram devices). A partition that holds something
    (LUKS, LVM, RAID) is marked as in use so that it can never become a deletion target."""
    disks = []
    for disk in tree.get('blockdevices', []):
        if disk.get('type') != 'disk' or not valid_device(disk.get('path')):
            continue
        parts = disk.get('children') or []
        if any(p.get('type') != 'part' or not valid_device(p.get('path')) for p in parts):
            continue  # unusual topology: this disk is not considered at all
        for part in parts:
            if part.get('children'):
                part['children'] = []
                part['mountpoints'] = list(part.get('mountpoints') or []) + ['<in use by another device>']
        disks.append(disk)
    tree['blockdevices'] = disks
    return tree


def _flat(tree):
    for disk in tree['blockdevices']:
        for part in disk.get('children') or []:
            yield disk, part


def verify_windows(env, device, filesystem):
    """True if the NTFS partition holds a Windows installation. Mounted read-only in a private directory."""
    if filesystem != 'ntfs' or not valid_device(device):
        return False
    MOUNT_ROOT.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix='check-', dir=MOUNT_ROOT))
    mounted = False
    try:
        for argv in (['mount', '-t', 'ntfs3', '-o', 'ro,nodev,nosuid,noexec', device, str(target)],
                     ['mount', '-t', 'ntfs-3g', '-o', 'ro,nodev,nosuid,noexec', device, str(target)]):
            try:
                env.run(argv)
                mounted = True
                break
            except (subprocess.CalledProcessError, OSError):
                continue
        return mounted and env.is_dir(target / 'Windows' / 'System32')
    finally:
        if mounted:
            try:
                env.run(['umount', str(target)])
            except (subprocess.CalledProcessError, OSError):
                pass
        try:
            target.rmdir()
        except OSError:
            pass


def migration_status(report_path=REPORT_PATH):
    try:
        data = json.loads(Path(report_path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'present': False}
    return {'present': True, 'success': bool(data.get('success')) and int(data.get('files') or 0) > 0,
            'files': int(data.get('files') or 0), 'timestamp': str(data.get('timestamp', ''))[:32],
            'errors': len(data.get('errors') or [])}


def _root_filesystem(env):
    try:
        out = env.run(['findmnt', '-n', '-o', 'SOURCE,FSTYPE', '/']).stdout.split()
    except (subprocess.CalledProcessError, OSError):
        return {'device': None, 'fstype': None}
    source = out[0].split('[')[0] if out else None
    return {'device': source if source and valid_device(source) else None, 'fstype': out[1] if len(out) > 1 else None}


def scan(env=None):
    """Find what can be removed. Nothing here changes the system."""
    env = env or Environment()
    tree = env.lsblk()
    windows = [part['path'] for disk, part in _flat(tree)
               if (part.get('fstype') or '').lower() == 'ntfs' and not any(part.get('mountpoints') or [])
               and verify_windows(env, part['path'], 'ntfs')]
    rows = inventory(tree, windows)
    disks_with_windows = {row['disk'] for row in rows if row['role'] == 'windows'}
    candidates = []
    for row in rows:
        if row['role'] == 'windows' and not row['protected']:
            candidates.append({**row, 'selected': True, 'why': 'windows'})
        elif row['role'] == 'possible-windows-support' and row['disk'] in disks_with_windows and not row['protected']:
            candidates.append({**row, 'selected': True, 'why': 'windows-support'})
    efi = []
    if env.which('efibootmgr'):
        try:
            efi = windows_boot_entries(env.run(['efibootmgr']).stdout)
        except (subprocess.CalledProcessError, OSError, ValueError):
            efi = []
    return {'candidates': candidates, 'root': _root_filesystem(env), 'efi_entries': efi,
            'migration': migration_status(env.report_path),
            'other_partitions_on_same_disk': [r['device'] for r in rows if r['role'] == 'other' and not r['protected']
                                              and r['disk'] in disks_with_windows]}


def build_plan(env, selection, grow='join', boot_cleanup=True):
    """Turn a user selection into an ordered list of steps. The targets must be offered by a fresh scan."""
    if grow not in ('join', 'data', 'none'):
        raise ValueError('Unknown growth mode')
    found = scan(env)
    offered = {c['device']: c for c in found['candidates']}
    selection = list(dict.fromkeys(selection))
    if not selection or any(d not in offered for d in selection):
        raise ValueError('Selection contains a partition that is not offered')
    tree = env.lsblk()
    by_disk = {}
    for device in selection:
        match = [(d, p) for d, p in _flat(tree) if p['path'] == device]
        if len(match) != 1:
            raise ValueError('Partition not found: ' + device)
        disk, part = match[0]
        identity = {'partuuid': part.get('partuuid'), 'disk_guid': disk.get('ptuuid'), 'partn': part.get('partn')}
        if not identity['partuuid'] or not identity['disk_guid'] or not isinstance(identity['partn'], int):
            raise ValueError('Missing persistent identity for ' + device)
        by_disk.setdefault(disk['path'], []).append((identity['partn'], device, identity, (disk.get('pttype') or '').lower()))
    steps = []
    for disk, items in by_disk.items():
        # MBR logical partitions renumber when one is removed: delete from the highest number down.
        for number, device, identity, table in sorted(items, reverse=True):
            if table == 'gpt':
                argv = ['sgdisk', '-d', str(number), disk]
            elif table == 'dos':
                argv = ['sfdisk', '--delete', disk, str(number)]
            else:
                raise ValueError('Unsupported partition table')
            steps.append({'step': 'delete', 'device': device, 'disk': disk, 'identity': identity, 'argv': argv})
    tables = {t for items in by_disk.values() for _n, _d, _i, t in items}
    effective = grow
    if grow != 'none' and tables not in ({'gpt'}, {'dos'}):
        effective = 'none'  # free space handling covers GPT and MBR disks, not mixed selections
    if effective == 'join' and found['root'].get('fstype') != 'btrfs':
        effective = 'data'
    steps.append({'step': 'grow', 'mode': effective, 'disks': sorted(by_disk), 'root': found['root'], 'table': 'dos' if tables == {'dos'} else 'gpt'})
    if boot_cleanup:
        steps.append({'step': 'boot-cleanup', 'efi_entries': found['efi_entries']})
    return {'steps': steps, 'requested_growth': grow, 'effective_growth': effective}


def _emit(progress, **event):
    if progress:
        progress(event)


def _largest_free(env, disk):
    """Largest free region of a GPT disk in sectors, from parted's machine-readable output."""
    out = env.run(['parted', '-m', '-s', disk, 'unit', 's', 'print', 'free']).stdout
    best = None
    for line in out.splitlines():
        fields = line.rstrip(';').split(':')
        if len(fields) >= 5 and fields[4] == 'free' and all(SECTOR.match(fields[i]) for i in (1, 2, 3)):
            start, end, size = (int(fields[i][:-1]) for i in (1, 2, 3))
            if best is None or size > best[2]:
                best = (start, end, size)
    return best


def execute(plan, env=None, dry_run=False, progress=None, phrase='', backup=False, language='de'):
    env = env or Environment()
    mig = migration_status(env.report_path)
    if not confirmed(bool(backup) or bool(mig.get('success')), phrase, language):
        raise PermissionError('Confirmation phrase or backup confirmation is missing')
    if not dry_run and env.geteuid() != 0:
        raise PermissionError('Root privileges are required')
    log = []

    def do(argv, input=None):
        _emit(progress, event='command', argv=argv)
        log.append(argv)
        if not dry_run:
            return env.run(argv, input) if input is not None else env.run(argv)
        return None

    before = env.lsblk()
    if not dry_run:
        # Re-check every target immediately before touching the disk.
        for step in plan['steps']:
            if step['step'] != 'delete':
                continue
            match = [(d, p) for d, p in _flat(before) if p['path'] == step['device']]
            if len(match) != 1:
                raise RuntimeError('Partition disappeared: ' + step['device'])
            disk, part = match[0]
            ident = step['identity']
            if (part.get('partuuid') != ident['partuuid'] or disk.get('ptuuid') != ident['disk_guid']
                    or part.get('partn') != ident['partn'] or any(part.get('mountpoints') or [])):
                raise RuntimeError('Partition changed or is mounted: ' + step['device'])
    total = len(plan['steps'])
    for index, step in enumerate(plan['steps'], 1):
        _emit(progress, event='step', index=index, total=total, step=step['step'], device=step.get('device'))
        if step['step'] == 'delete':
            do(step['argv'])
        elif step['step'] == 'grow':
            do(['udevadm', 'settle'])
            for disk in step['disks']:
                do(['partprobe', disk])
            if step['mode'] in ('join', 'data'):
                _grow(step, env, do, dry_run, progress)
            else:
                _emit(progress, event='note', text='free-space-left')
        elif step['step'] == 'boot-cleanup':
            _boot_cleanup(step, env, do, dry_run, progress)
    result = {'schema': 1, 'timestamp': datetime.now(timezone.utc).isoformat(), 'dry_run': dry_run,
              'commands': log, 'growth': plan['effective_growth']}
    if not dry_run:
        try:
            RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
            RESULT_PATH.write_text(json.dumps(result), encoding='utf-8')
        except OSError:
            pass
    _emit(progress, event='done', dry_run=dry_run, growth=plan['effective_growth'])
    return result


def _grow(step, env, do, dry_run, progress):
    disk = step['disks'][0]
    mbr = step.get('table') == 'dos'
    if dry_run:
        do(['sfdisk', '--append', '--no-reread', disk] if mbr else ['sgdisk', '-n', '0:<start>:<end>', '-t', '0:8300', '-c', '0:WinDoesNot-Platz', disk])
        do(['btrfs', 'device', 'add', '-f', '<new partition>', '/'] if step['mode'] == 'join'
           else ['mkfs.ext4', '-L', 'Daten', '<new partition>'])
        return
    region = _largest_free(env, disk)
    if not region or region[2] < 2097152:  # under 1 GiB: not worth a partition
        _emit(progress, event='note', text='free-space-too-small')
        return
    old = {p['path'] for _d, p in _flat(env.lsblk())}
    if mbr:
        # MBR: one more primary partition in the freed region (sfdisk reads the layout from stdin).
        # sfdisk wants an aligned start (the free region often begins at sector 2) and a size inside the region.
        start = ((max(region[0], 2048) + 2047) // 2048) * 2048
        size = region[1] - start + 1
        size -= size % 2048
        if size < 2097152:
            _emit(progress, event='note', text='free-space-too-small')
            return
        do(['sfdisk', '--append', '--no-reread', disk], f'start={start}, size={size}, type=83\n')
    else:
        do(['sgdisk', '-n', f'0:{region[0]}:{region[1]}', '-t', '0:8300', '-c', '0:WinDoesNot-Platz', disk])
    do(['udevadm', 'settle'])
    do(['partprobe', disk])
    new = [p for d, p in _flat(env.lsblk()) if p['path'] not in old and d['path'] == disk]
    if len(new) != 1 or not valid_device(new[0]['path']):
        raise RuntimeError('Could not identify the new partition')
    device = new[0]['path']
    if step['mode'] == 'join':
        do(['btrfs', 'device', 'add', '-f', device, '/'])
    else:
        do(['mkfs.ext4', '-F', '-L', 'Daten', device])
        uuid = env.run(['blkid', '-s', 'UUID', '-o', 'value', device]).stdout.strip()
        if not re.fullmatch(r'[0-9a-fA-F-]{8,40}', uuid):
            raise RuntimeError('Missing filesystem UUID')
        env.mkdir('/mnt/daten')
        env.append_text('/etc/fstab', f'UUID={uuid} /mnt/daten ext4 defaults,nofail 0 2\n')
        do(['mount', '/mnt/daten'])


def _boot_cleanup(step, env, do, dry_run, progress):
    for number in step.get('efi_entries', []):
        if re.fullmatch(r'[0-9A-F]{4}', number):
            do(['efibootmgr', '-B', '-b', number])
    esp = next((Path(c) for c in ('/boot/efi', '/efi', '/boot') if env.ismount(c)), None)
    if esp is not None:
        target = esp / 'EFI' / 'Microsoft'
        real = Path(env.realpath(target))
        if (real.name == 'Microsoft' and real.parent.parent == Path(env.realpath(esp)) and env.is_dir(target)
                and not env.is_symlink(target)):
            _emit(progress, event='command', argv=['rmtree', str(real)])
            if not dry_run:
                env.rmtree(real)
    if env.which('grub-mkconfig') and env.exists_file('/boot/grub/grub.cfg'):
        do(['grub-mkconfig', '-o', '/boot/grub/grub.cfg'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('scan')
    run = sub.add_parser('run')
    run.add_argument('--select', required=True, help='comma separated partition devices offered by scan')
    run.add_argument('--grow', choices=('join', 'data', 'none'), default='join')
    run.add_argument('--no-boot-cleanup', action='store_true')
    run.add_argument('--backup', action='store_true')
    run.add_argument('--phrase', default='')
    run.add_argument('--lang', choices=('de', 'en'), default='de')
    run.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    env = Environment()
    if args.action == 'scan':
        if env.geteuid() != 0:
            sys.exit('Root privileges are required to verify Windows read-only')
        print(json.dumps(scan(env)))
        return
    devices = [d for d in args.select.split(',') if d]
    if any(not valid_device(d) for d in devices):
        sys.exit('Invalid device name')
    plan = build_plan(env, devices, args.grow, not args.no_boot_cleanup)
    execute(plan, env, args.dry_run, lambda event: print(json.dumps(event), flush=True), args.phrase, args.backup, args.lang)


if __name__ == '__main__':
    try:
        main()
    except (PermissionError, ValueError, RuntimeError) as error:
        sys.exit(str(error))
    except subprocess.CalledProcessError as error:
        sys.exit(f'{error} {(error.stderr or "").strip()}')
