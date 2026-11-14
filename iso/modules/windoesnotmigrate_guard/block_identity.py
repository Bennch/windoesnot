# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative block-device ancestry comparison; does not authorize installs.

The caller must supply *all* writable targets, including bootloader and mount
targets, and must separately address device replacement and validation races.
This helper deliberately does not make a safety decision from an incomplete
Calamares partition-device plan.
"""
import os
from pathlib import Path
import re
import stat

_DEVICE_ID = re.compile(r'\A\d+:\d+\Z')


class UnknownBlockIdentity(ValueError):
    """Block-device ancestry could not be proved completely."""


def backing_disks(device, *, sysfs_root=Path('/sys'), stat_device=os.stat):
    """Return physical disk major:minor IDs backing a block device.

    Resolve partition parents and all device-mapper/RAID slave edges. If any
    node, disk, link or relationship cannot be identified, fail closed. A
    non-physical virtual block device without known slaves is not a disk.
    """
    try:
        info = stat_device(device)
        if not stat.S_ISBLK(info.st_mode):
            raise UnknownBlockIdentity('Not a block device')
        initial = f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}'
        root = Path(sysfs_root).resolve(strict=True)
        active, cache = set(), {}

        def contained(path):
            result = path.resolve(strict=True)
            if not result.is_relative_to(root):
                raise UnknownBlockIdentity('Block relationship escapes sysfs')
            return result

        def device_id(path):
            value = (path / 'dev').read_text().strip()
            if not _DEVICE_ID.fullmatch(value):
                raise UnknownBlockIdentity('Invalid sysfs block identity')
            return value

        def visit(identity):
            if identity in active:
                raise UnknownBlockIdentity('Block device cycle')
            if identity in cache:
                return cache[identity]
            active.add(identity)
            node = contained(root / 'dev/block' / identity)
            if device_id(node) != identity:
                raise UnknownBlockIdentity('Inconsistent sysfs block identity')
            if (node / 'partition').exists():
                parent = contained(node.parent)
                result = visit(device_id(parent))
            else:
                slaves = node / 'slaves'
                if not slaves.is_dir():
                    raise UnknownBlockIdentity('Missing block-device slave information')
                children = list(slaves.iterdir())
                if children:
                    result = set()
                    for child in children:
                        result.update(visit(device_id(contained(child))))
                else:
                    # An empty virtual device such as loop, zram or an
                    # inactive dm target is not proof of a physical disk.
                    if node.is_relative_to(root / 'devices/virtual'):
                        raise UnknownBlockIdentity('Virtual device has no physical backing')
                    if not (node / 'queue').is_dir():
                        raise UnknownBlockIdentity('Not an identifiable physical disk')
                    result = {identity}
            active.remove(identity)
            cache[identity] = frozenset(result)
            return cache[identity]

        return visit(initial)
    except UnknownBlockIdentity:
        raise
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        raise UnknownBlockIdentity('Unable to resolve physical block identity') from error


def disjoint_backing(source, writable_targets, *, sysfs_root=Path('/sys'), stat_device=os.stat):
    """Compare a source and a caller-provided complete list of writable targets.

    True says only that the resolved sets are disjoint at this instant. It is
    not permission to install, a guarantee against later hotplug, or a backup.
    """
    targets = list(writable_targets)
    if not targets:
        raise UnknownBlockIdentity('No writable targets were supplied')
    source_disks = backing_disks(source, sysfs_root=sysfs_root, stat_device=stat_device)
    target_disks = set()
    for device in targets:
        target_disks.update(backing_disks(device, sysfs_root=sysfs_root, stat_device=stat_device))
    return source_disks.isdisjoint(target_disks)
