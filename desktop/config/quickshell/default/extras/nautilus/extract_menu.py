import gi
gi.require_version('Nautilus', '4.1')
gi.require_version('GObject', '2.0')
from gi.repository import Nautilus, GObject
import subprocess
import os
import re
from urllib.parse import unquote, urlparse

ARCHIVE_EXTS = ('.rar', '.zip', '.7z', '.tar.gz', '.tar.xz', '.tar.bz2', '.tar.zst', '.tgz')


def german():
    from pathlib import Path
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'quickshell/default/settings.txt'
    try:
        for line in config.read_text().splitlines():
            if line.startswith('uiLanguage='):
                return line.partition('=')[2].strip() == 'de'
    except OSError:
        pass
    return os.environ.get('LANG', '').startswith('de')


def filepath(fileinfo):
    return unquote(urlparse(fileinfo.get_uri()).path)

def is_archive(path):
    lower = path.lower()
    return any(lower.endswith(ext) for ext in ARCHIVE_EXTS)

def extract(path):
    lower = path.lower()
    dir_ = os.path.dirname(path)

    # Multi-part RARs: always extract via part1
    if re.search(r'\.part\d+\.rar$', lower):
        path = re.sub(r'\.part\d+\.rar$', '.part1.rar', path)
        if not os.path.exists(path):
            msg = "part1.rar nicht gefunden" if german() else "part1.rar not found"
            subprocess.Popen(['notify-send', 'Entpacken' if german() else 'Extract', msg, '--icon=package-x-generic'])
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
        de = german()
        if ret == 0:
            msg = f"Fertig: {base}" if de else f"Done: {base}"
        else:
            msg = f"Fehler bei: {base}" if de else f"Failed: {base}"
        subprocess.Popen(['notify-send', 'Entpacken' if de else 'Extract', msg, '--icon=package-x-generic'])

    import threading
    threading.Thread(target=run, daemon=True).start()


class ExtractMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, files):
        archives = [f for f in files if is_archive(filepath(f))]
        if not archives:
            return []

        de = german()
        item = Nautilus.MenuItem(
            name='ExtractProvider::extract_all',
            label='Dateien entpacken' if de else 'Extract files',
            tip='Archiv(e) entpacken' if de else 'Extract archive(s)',
            icon='package-x-generic',
        )
        item.connect('activate', lambda *_: [extract(filepath(f)) for f in archives])
        return [item]
