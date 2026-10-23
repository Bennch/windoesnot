import gi
gi.require_version('Nautilus', '4.1')
gi.require_version('GObject', '2.0')
from gi.repository import Nautilus, GObject
import subprocess
import os
import re
from urllib.parse import unquote, urlparse

ARCHIVE_EXTS = ('.rar', '.zip', '.7z', '.tar.gz', '.tar.xz', '.tar.bz2', '.tar.zst', '.tgz')

def filepath(fileinfo):
    return unquote(urlparse(fileinfo.get_uri()).path)

def is_archive(path):
    lower = path.lower()
    return any(lower.endswith(ext) for ext in ARCHIVE_EXTS)

def extract(path):
    lower = path.lower()
    dir_ = os.path.dirname(path)

    # Bei mehrteiligen RARs immer part1 verwenden
    if re.search(r'\.part\d+\.rar$', lower):
        path = re.sub(r'\.part\d+\.rar$', '.part1.rar', path)
        if not os.path.exists(path):
            notify(f"part1.rar nicht gefunden")
            return

    base = os.path.basename(path)
    dest = re.sub(r'(\.part1)?\.rar$|\.zip$|\.7z$|\.tgz$|\.tar\.(gz|xz|bz2|zst)$', '', path, flags=re.IGNORECASE)
    os.makedirs(dest, exist_ok=True)

    if re.search(r'\.rar$', lower) or re.search(r'\.part1\.rar$', lower):
        cmd = ['unrar', 'x', '-o+', path, dest + '/']
    elif lower.endswith('.zip'):
        cmd = ['unzip', '-o', path, '-d', dest]
    elif lower.endswith('.7z'):
        cmd = ['7z', 'x', path, f'-o{dest}', '-y']
    elif re.search(r'\.tar\.gz$|\.tgz$', lower):
        cmd = ['tar', '-xzf', path, '-C', dest]
    elif lower.endswith('.tar.xz'):
        cmd = ['tar', '-xJf', path, '-C', dest]
    elif lower.endswith('.tar.bz2'):
        cmd = ['tar', '-xjf', path, '-C', dest]
    elif lower.endswith('.tar.zst'):
        cmd = ['tar', '-I', 'zstd', '-xf', path, '-C', dest]
    else:
        return

    def run():
        ret = subprocess.call(cmd)
        msg = f"Fertig: {base}" if ret == 0 else f"Fehler bei: {base}"
        subprocess.Popen(['notify-send', 'Entpacken', msg, '--icon=package-x-generic'])

    import threading
    threading.Thread(target=run, daemon=True).start()


class ExtractMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, files):
        archives = [f for f in files if is_archive(filepath(f))]
        if not archives:
            return []

        item = Nautilus.MenuItem(
            name='ExtractProvider::extract_all',
            label='Part Dateien entpacken',
            tip='Archiv(e) entpacken',
            icon='package-x-generic',
        )
        item.connect('activate', lambda *_: [extract(filepath(f)) for f in archives])
        return [item]
