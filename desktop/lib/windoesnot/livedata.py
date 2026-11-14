"""Carry files created in the live session over to the installed user's home.

Only what the user made in the normal folders (Desktop, Documents, Downloads, Pictures, Music, Videos) is
copied: no hidden files, no links, nothing that exists already, and with size limits because the live home
lives in memory. WLAN passwords are carried over by Calamares' networkcfg module, not here.
"""
import os
from pathlib import Path
import re
import shutil

USER_DIR_KEYS = ('DESKTOP', 'DOCUMENTS', 'DOWNLOAD', 'PICTURES', 'MUSIC', 'VIDEOS')
DEFAULTS = {'DESKTOP': 'Desktop', 'DOCUMENTS': 'Documents', 'DOWNLOAD': 'Downloads',
            'PICTURES': 'Pictures', 'MUSIC': 'Music', 'VIDEOS': 'Videos'}
MAX_TOTAL_BYTES = 2 * 1024 ** 3
MAX_FILE_BYTES = 512 * 1024 ** 2


def user_dirs(home):
    """Folder names (relative to the home) from ~/.config/user-dirs.dirs, falling back to the English names."""
    result = dict(DEFAULTS)
    try:
        text = (Path(home) / '.config/user-dirs.dirs').read_text(encoding='utf-8')
    except OSError:
        return result
    for key, value in re.findall(r'^XDG_([A-Z]+)_DIR="\$HOME/([^"]+)"', text, re.M):
        if key in result and value and '..' not in Path(value).parts and not Path(value).is_absolute():
            result[key] = value
    return result


def copy_live_data(live_home, target_home, uid=None, gid=None, max_total=MAX_TOTAL_BYTES, max_file=MAX_FILE_BYTES):
    """Copy the user's files; returns {'files': n, 'bytes': n, 'skipped': [...]}. Never overwrites."""
    live_home, target_home = Path(live_home), Path(target_home)
    summary = {'files': 0, 'bytes': 0, 'skipped': []}

    def own(path):
        if uid is not None and gid is not None:
            os.chown(path, uid, gid, follow_symlinks=False)

    def ensure_dir(path):
        missing = []
        while not path.exists() and path != target_home.parent:
            missing.append(path)
            path = path.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o755)
            own(directory)

    for relative in dict.fromkeys(user_dirs(live_home).values()):
        source_root = live_home / relative
        if not source_root.is_dir() or source_root.is_symlink():
            continue
        for base, dirs, files in os.walk(source_root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if not name.startswith('.') and not (Path(base) / name).is_symlink())
            for name in sorted(files):
                if name.startswith('.'):
                    continue
                source = Path(base) / name
                try:
                    info = source.lstat()
                except OSError:
                    summary['skipped'].append(str(source))
                    continue
                if not source.is_file() or source.is_symlink() or info.st_size > max_file or summary['bytes'] + info.st_size > max_total:
                    summary['skipped'].append(str(source))
                    continue
                target = target_home / source.relative_to(live_home)
                if target.exists() or target.is_symlink():
                    summary['skipped'].append(str(source))
                    continue
                ensure_dir(target.parent)
                shutil.copyfile(source, target)
                shutil.copymode(source, target)
                own(target)
                summary['files'] += 1
                summary['bytes'] += info.st_size
    return summary
