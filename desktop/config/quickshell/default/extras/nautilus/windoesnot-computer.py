"""This PC in Files: the "Belegung" column (fill bar, percent, free space) for the drives listed at computer:///.

Files lists the drives of the computer at computer:/// (disks, optical drives, the file system). The desktop opens that page
as the start page when chosen in Settings > Apps; this extension adds how full each drive is, like "My Computer" on Windows."""
import os
from pathlib import Path

try:
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GObject, Nautilus
except (ImportError, ValueError):           # imported by the tests without Nautilus
    Gio = GObject = Nautilus = None

ATTRIBUTE = 'wdn_usage'
COLUMN = 'WinDoesNot::usage'
KIND_COLUMN = 'WinDoesNot::kind'


def german():
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'quickshell/default/settings.txt'
    try:
        for line in config.read_text().splitlines():
            if line.startswith('uiLanguage='):
                return line.partition('=')[2] == 'de'
    except OSError:
        pass
    return os.environ.get('LANG', '').startswith('de')


def human(value):
    for unit, shift in (('TB', 40), ('GB', 30), ('MB', 20)):
        if value >= 1 << shift:
            text = f'{value / (1 << shift):.1f}'
            return (text[:-2] if text.endswith('.0') else text) + ' ' + unit
    return f'{max(value >> 10, 0)} KB'


def usage_parts(size, free, de=True):
    """('87', '248 GB frei von 1,8 TB'): the percentage and the free-space text for the categorised This PC view."""
    if not size or size <= 0 or free is None:
        return '', ''
    percent = round(100 * max(size - free, 0) / size)
    total, free_text = human(size), human(free)
    if de:
        total, free_text = total.replace('.', ','), free_text.replace('.', ',')
        return str(percent), f'{free_text} frei von {total}'
    return str(percent), f'{free_text} free of {total}'


def usage_text(size, free, de=True):
    """'████████░░  87 %  ·  248 GB frei von 1,8 TB'; empty when the size is unknown."""
    if not size or size <= 0 or free is None:
        return ''
    used = max(size - free, 0)
    percent = round(100 * used / size)
    filled = min(10, max(0, round(percent / 10)))
    bar = '█' * filled + '░' * (10 - filled)
    total = human(size)
    free_text = human(free)
    if de:
        total, free_text = total.replace('.', ','), free_text.replace('.', ',')
        return f'{bar}  {percent} %  ·  {free_text} frei von {total}'
    return f'{bar}  {percent} %  ·  {free_text} free of {total}'


def filesystem(location):
    """(size, free) of the file system under a Gio.File, or None."""
    try:
        info = location.query_filesystem_info('filesystem::size,filesystem::free', None)
        return info.get_attribute_uint64('filesystem::size'), info.get_attribute_uint64('filesystem::free')
    except Exception:
        return None


def sum_filesystems(locations):
    size = free = 0
    seen = set()
    for location in locations:
        if location is None or not location.is_native():
            continue
        values = filesystem(location)
        if values and values not in seen:
            seen.add(values)
            size += values[0]
            free += values[1]
    return (size, free) if size else None


HIDDEN_FS = {None, '', 'swap', 'linux_raid_member', 'LVM2_member', 'crypto_LUKS', 'squashfs', 'bcache', 'zfs_member'}
SYSTEM_PARTITION_TYPES = {'c12a7328-f81f-11d2-ba4b-00a0c93ec93b', 'de94bba4-06d1-4d40-a16a-bfd50179d6ac', 'e3c9e316-0b5c-4db8-817d-f92df00215ae'}
SYSTEM_MOUNTS = ('/boot', '/efi', '/run/archiso')


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get('children') or [])


def disks_from_lsblk(data):
    """name (vendor + model, as Files shows the drive) -> {'entry': ('usage', size, free) | ('unmounted', size) | ('empty',), 'category': ...}."""
    result = {}
    for disk in data.get('blockdevices', []):
        if disk.get('type') not in ('disk', 'rom'):
            continue
        name = ' '.join(filter(None, [(disk.get('vendor') or '').strip(), (disk.get('model') or '').strip()]))
        size = free = unmounted = 0
        seen = set()
        for node in walk([disk]):
            mounts = [m for m in (node.get('mountpoints') or []) if m and m != '[SWAP]']
            if node.get('fstype') in HIDDEN_FS or (node.get('parttype') or '').lower() in SYSTEM_PARTITION_TYPES:
                continue
            if mounts and all(m.startswith(SYSTEM_MOUNTS) for m in mounts):
                continue
            if mounts and node.get('fsused') is not None and node.get('fsavail') is not None and node.get('path') not in seen:
                seen.add(node.get('path'))
                size += node['fsused'] + node['fsavail']
                free += node['fsavail']
            elif not mounts:
                unmounted += node.get('size') or 0
        removable = bool(disk.get('rm') or disk.get('hotplug')) or disk.get('tran') in ('usb', 'mmc')
        category = 'optical' if disk.get('type') == 'rom' else ('removable' if removable else 'internal')
        if name:
            result[name] = {'entry': ('usage', size, free) if size else (('unmounted', unmounted) if unmounted else ('empty',)), 'category': category}
    return result


def lsblk():
    import json
    import subprocess
    try:
        out = subprocess.run(['lsblk', '-J', '-b', '-o', 'NAME,PATH,TYPE,SIZE,FSTYPE,PARTTYPE,MOUNTPOINTS,RM,HOTPLUG,TRAN,VENDOR,MODEL,FSAVAIL,FSUSED'],
                             capture_output=True, text=True, timeout=5)
        return json.loads(out.stdout) if out.returncode == 0 else {}
    except (OSError, ValueError, Exception):
        return {}


_cache = {'at': 0.0, 'disks': {}}


def text_for_disk(entry, de):
    if entry is None or entry[0] == 'empty':
        return 'kein Medium' if de else 'no media'
    if entry[0] == 'unmounted':
        return (f'nicht eingehängt  ·  {human(entry[1])}' if de else f'not mounted  ·  {human(entry[1])}').replace('.', ',' if de else '.')
    return usage_text(entry[1], entry[2], de)


KINDS = {'system': ('Lokaler Datenträger', 'Local disk'), 'internal': ('Lokaler Datenträger', 'Local disk'),
         'removable': ('Wechseldatenträger', 'Removable disk'), 'optical': ('CD-/DVD-Laufwerk', 'CD/DVD drive'),
         'network': ('Netzwerkadresse', 'Network location')}
ORDER = {'system': 0, 'internal': 1, 'removable': 2, 'optical': 3, 'network': 4}


def item_info(name, de, disks=None):
    """(usage text, kind text, sort key) for an item at computer:/// (name is the item's file name, e.g. 'Samsung SSD 980 PRO 1TB.drive').
    The sort key puts the items in the order of Windows Explorer: the system disk, local disks, removable disks, optical drives, network."""
    category, usage = None, ''
    if name == 'root.link':
        category = 'system'
        values = sum_filesystems([Gio.File.new_for_path('/')])
        usage = usage_text(*values, de=de) if values else ''
    elif name.endswith('.drive'):
        if disks is None:
            import time
            if time.monotonic() - _cache['at'] > 3:
                _cache.update(at=time.monotonic(), disks=disks_from_lsblk(lsblk()))
            disks = _cache['disks']
        info = disks.get(name[:-len('.drive')])
        category = info['category'] if info else 'internal'
        usage = text_for_disk(info['entry'] if info else None, de)
    elif name.endswith('.mount'):
        category = 'network'   # mounted network shares (GVfs); local partitions are part of their drive
    if category is None:
        return '', '', ''
    return usage, KINDS[category][0 if de else 1], f'{ORDER[category]}{name.lower()}'


def view_info(name, de, disks=None):
    """(percent, space text) of an item for the This PC view; both empty when the fill is unknown (unmounted drive: the size only)."""
    if name == 'root.link':
        values = sum_filesystems([Gio.File.new_for_path('/')])
        return usage_parts(*values, de=de) if values else ('', '')
    if name.endswith('.drive'):
        if disks is None:
            item_info(name, de)   # refreshes the lsblk cache
            disks = _cache['disks']
        info = disks.get(name[:-len('.drive')])
        if not info:
            return '', ''
        entry = info['entry']
        if entry[0] == 'usage':
            return usage_parts(entry[1], entry[2], de)
        return '', text_for_disk(entry, de)
    return '', ''


def text_for(name, de, disks=None):
    return item_info(name, de, disks)[0]


if Nautilus is not None:
    class WinDoesNotComputer(GObject.GObject, Nautilus.ColumnProvider, Nautilus.InfoProvider):
        def get_columns(self):
            return (Nautilus.Column(name=KIND_COLUMN, attribute='wdn_kind', label='Art' if german() else 'Kind',
                                    description='Art des Laufwerks' if german() else 'Kind of drive'),
                    Nautilus.Column(name=COLUMN, attribute=ATTRIBUTE, label='Belegung' if german() else 'Usage',
                                    description='Wie voll das Laufwerk ist' if german() else 'How full the drive is'))

        def update_file_info(self, file):
            try:
                if file.get_uri_scheme() != 'computer':
                    return
                usage, kind, order = item_info(file.get_name(), german())
                file.add_string_attribute(ATTRIBUTE, usage)
                file.add_string_attribute('wdn_kind', kind)
                file.add_string_attribute('wdn_order', order)   # the patched Files sorts computer:/// by this
                percent, space = view_info(file.get_name(), german())
                file.add_string_attribute('wdn_percent', percent)   # fill bar and free space of the categorised view
                file.add_string_attribute('wdn_space', space)
            except Exception:
                pass
