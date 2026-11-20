#!/usr/bin/python3 -I
"""Fixed, root-owned pkexec entry point: export system restore points to an external drive and bring them back.

  export  {"dest": "<folder on an external or network target>"}   new snapshot -> btrfs send | zstd -> dest
  restore {"dir": "<export folder>", "id": N, "into": "<folder on a btrfs filesystem>"}   chain -> btrfs receive
Files are `snap-<id>-<stamp>-full.btrfs.zst` or `...-inc<parent>.btrfs.zst`; `index.json` lists them. The destination
must be below /run/media/<user>/, /media/<user>/ or /mnt/ and not on the system disk. Nothing else is writable.
"""
import datetime
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

CONFIG = 'root'
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
KEEP_CHAINS = 3
FILE_RE = re.compile(r'snap-(\d+)-(\d{8}T\d{6})-(full|inc(\d+))\.btrfs\.zst')


def fail(message):
    print(json.dumps({'error': message}), file=sys.stderr)
    sys.exit(1)


def run(*args, **kwargs):
    return subprocess.run(args, env=ENV, text=True, capture_output=True, check=True, timeout=kwargs.pop('timeout', 120), **kwargs)


def allowed_destination(path, uid):
    user = pwd.getpwuid(uid).pw_name
    if '..' in Path(path).parts:
        fail('Invalid destination')
    real = Path(os.path.realpath(path))
    prefixes = [Path('/run/media') / user, Path('/media') / user, Path('/mnt')]
    if not any(real == p or p in real.parents for p in prefixes):
        fail('The destination must be on an external drive or a network share')
    if not real.is_dir():
        fail('The destination folder does not exist')
    if same_device(real, Path('/')):
        fail('The destination is on the system disk')
    return real


def source_device(path):
    """The block device under a path ('/dev/vda2[/@home]' -> '/dev/vda2'): subvolumes of one btrfs have different st_dev."""
    out = run('/usr/bin/findmnt', '-n', '-o', 'SOURCE', '-T', str(path)).stdout.strip()
    return out.split('[')[0]


def same_device(path, other):
    try:
        if os.stat(path).st_dev == os.stat(other).st_dev:
            return True
        return source_device(path) == source_device(other) != ''
    except (OSError, subprocess.SubprocessError):
        return True   # when in doubt, refuse


def read_index(folder):
    try:
        data = json.loads((folder / 'index.json').read_text())
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def write_index(folder, entries):
    tmp = folder / '.index.tmp'
    tmp.write_text(json.dumps(entries, indent=1))
    os.replace(tmp, folder / 'index.json')


def snapshot_dir(number):
    return Path('/.snapshots') / str(number) / 'snapshot'


def new_snapshot():
    number = run('/usr/bin/snapper', '--no-dbus', '-c', CONFIG, 'create', '--description', 'windoesnot-backup-export',
                 '--userdata', 'windoesnot.export=yes', '--print-number').stdout.strip()
    if not number.isdecimal():
        fail('Could not create a restore point')
    return int(number)


def export(dest, uid):
    folder = allowed_destination(dest, uid)
    entries = read_index(folder)
    parent = next((e['id'] for e in reversed(entries) if snapshot_dir(e['id']).is_dir()), None)
    number = new_snapshot()
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    name = 'snap-%d-%s-%s.btrfs.zst' % (number, stamp, 'inc%d' % parent if parent else 'full')
    part = folder / ('.' + name + '.part')
    send = ['/usr/bin/btrfs', 'send', '-q'] + (['-p', str(snapshot_dir(parent))] if parent else []) + [str(snapshot_dir(number))]
    try:
        with open(part, 'wb') as out:
            sender = subprocess.Popen(send, stdout=subprocess.PIPE, env=ENV)
            packer = subprocess.Popen(['/usr/bin/zstd', '-q', '-T0', '-3'], stdin=sender.stdout, stdout=out, env=ENV)
            sender.stdout.close()
            if packer.wait() or sender.wait():
                raise OSError('The transfer failed')
            out.flush(); os.fsync(out.fileno())
        os.replace(part, folder / name)
    except Exception as error:
        part.unlink(missing_ok=True)
        run('/usr/bin/snapper', '--no-dbus', '-c', CONFIG, 'delete', str(number))
        fail(str(error))
    entries.append({'id': number, 'parent': parent, 'file': name, 'time': datetime.datetime.now().isoformat(timespec='seconds'),
                    'bytes': (folder / name).stat().st_size})
    entries = prune(folder, entries)
    write_index(folder, entries)
    # the previous export point is not needed locally any more (the new one is the next parent)
    if parent and parent != number:
        subprocess.run(['/usr/bin/snapper', '--no-dbus', '-c', CONFIG, 'delete', str(parent)], env=ENV, capture_output=True)
    return {'ok': True, 'id': number, 'file': name, 'bytes': entries[-1]['bytes'], 'full': parent is None}


def chains(entries):
    result, current = [], []
    for entry in entries:
        if entry['parent'] is None and current:
            result.append(current); current = []
        current.append(entry)
    if current:
        result.append(current)
    return result


def prune(folder, entries):
    groups = chains(entries)
    for old in groups[:-KEEP_CHAINS]:
        for entry in old:
            (folder / entry['file']).unlink(missing_ok=True)
    return [entry for group in groups[-KEEP_CHAINS:] for entry in group]


def restore(directory, number, into, uid):
    folder = allowed_destination(directory, uid)
    target = Path(os.path.realpath(into))
    if not target.is_dir() or run('/usr/bin/findmnt', '-n', '-o', 'FSTYPE', '-T', str(target)).stdout.strip() != 'btrfs':
        fail('The restore folder must be on a btrfs file system')
    if same_device(target, Path('/')) and not Path('/etc/windoesnot-image-build').exists():
        fail('Restore from the live system, not into the running system')
    entries = {e['id']: e for e in read_index(folder)}
    chain, current = [], entries.get(number)
    while current:
        chain.insert(0, current)
        current = entries.get(current['parent']) if current['parent'] else None
    if not chain or chain[0]['parent'] is not None:
        fail('The chain of this restore point is incomplete')
    for entry in chain:
        path = folder / entry['file']
        if not FILE_RE.fullmatch(entry['file']) or not path.is_file():
            fail('A file of the chain is missing: %s' % entry['file'])
    done = []

    def scratch_of(entry_id):
        return target / ('.receive-%d' % entry_id)

    def drop(entry_id):
        # A received subvolume is read-only and cannot be renamed across folders; it is deleted where it was received.
        snap = scratch_of(entry_id) / 'snapshot'
        if snap.exists():
            subprocess.run(['/usr/bin/btrfs', 'subvolume', 'delete', str(snap)], env=ENV, capture_output=True)
        try:
            scratch_of(entry_id).rmdir()
        except OSError:
            pass

    try:
        for entry in chain:
            # Every stream carries a subvolume called 'snapshot': each one is received into its own scratch folder and stays there
            # (an incremental stream finds its parent by UUID on the same file system).
            scratch = scratch_of(entry['id'])
            scratch.mkdir()
            done.append(entry['id'])
            unpack = subprocess.Popen(['/usr/bin/zstd', '-dc', str(folder / entry['file'])], stdout=subprocess.PIPE, env=ENV)
            receive = subprocess.run(['/usr/bin/btrfs', 'receive', '-q', str(scratch)], stdin=unpack.stdout, env=ENV, capture_output=True, text=True)
            unpack.stdout.close()
            if unpack.wait() or receive.returncode:
                fail(receive.stderr.strip() or 'btrfs receive failed')
        last = scratch_of(chain[-1]['id']) / 'snapshot'
        final = target / ('restore-%d' % chain[-1]['id'])
        made_writable = subprocess.run(['/usr/bin/btrfs', 'property', 'set', '-ts', str(last), 'ro', 'false'], env=ENV, capture_output=True, text=True)
        if made_writable.returncode:
            fail(made_writable.stderr.strip() or 'The restored subvolume could not be made writable')
        os.rename(last, final)
    except BaseException:
        for entry_id in done:
            drop(entry_id)
        raise
    for entry_id in done:   # the final subvolume does not depend on its parents any more
        drop(entry_id)
    return {'ok': True, 'received': done, 'into': str(target), 'subvolume': str(final)}


def main():
    if os.geteuid() != 0 or 'PKEXEC_UID' not in os.environ:
        fail('Use the authorized pkexec entry point')
    if len(sys.argv) != 3 or len(sys.argv[2]) > 2048:
        fail('Invalid arguments')
    uid = int(os.environ['PKEXEC_UID'])
    if uid < 1000:
        fail('Only regular accounts')
    payload = json.loads(sys.argv[2])
    if type(payload) is not dict:
        fail('Arguments must be an object')
    if Path('/etc/windoesnot-image-build').exists() and sys.argv[1] != 'restore':
        fail('Restore points are unavailable in this environment')
    if sys.argv[1] == 'export' and type(payload.get('dest')) is str:
        result = export(payload['dest'], uid)
    elif sys.argv[1] == 'restore' and type(payload.get('dir')) is str and type(payload.get('into')) is str and type(payload.get('id')) is int:
        result = restore(payload['dir'], payload['id'], payload['into'], uid)
    else:
        fail('Unknown action')
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        fail(error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error))
