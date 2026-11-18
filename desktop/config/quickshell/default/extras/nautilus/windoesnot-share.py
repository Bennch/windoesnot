"""Right-click a folder: share it in the network (opens the WinDoesNot sharing dialog)."""
import json
import os
import subprocess
from pathlib import Path
from gi.repository import GObject, Nautilus


def german():
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'quickshell/default/settings.txt'
    try:
        for line in config.read_text().splitlines():
            if line.startswith('uiLanguage='):
                return line.partition('=')[2] == 'de'
    except OSError:
        pass
    return os.environ.get('LANG', '').startswith('de')


def shared_paths():
    """Folders that are shared right now (read from the helper; never blocks the file manager for long)."""
    try:
        result = subprocess.run(['windoesnot-share', 'status'], capture_output=True, text=True, timeout=2, check=False)
        return {share['path'] for share in json.loads(result.stdout).get('shares', [])}
    except (OSError, ValueError, subprocess.SubprocessError):
        return set()


class WinDoesNotShare(GObject.GObject, Nautilus.MenuProvider):
    def _item(self, path):
        editing = path in shared_paths()
        de = german()
        label = ('Netzwerkfreigabe bearbeiten …' if de else 'Edit network share …') if editing else ('Im Netzwerk freigeben …' if de else 'Share in the network …')
        item = Nautilus.MenuItem(name='WinDoesNot::share', label=label)
        item.connect('activate', lambda *_: subprocess.Popen(['qs', 'ipc', 'call', 'windoesnot-share', 'open', path]))
        return [item]

    def get_file_items(self, *args):
        files = args[-1]
        if len(files) != 1 or not files[0].is_directory():
            return []
        path = files[0].get_location().get_path()
        home = str(Path.home())
        if not path or not (path == home or path.startswith(home + '/')):
            return []
        return self._item(path)

    def get_background_items(self, *args):
        folder = args[-1]
        path = folder.get_location().get_path() if folder else None
        home = str(Path.home())
        if not path or path == home or not path.startswith(home + '/'):
            return []
        return self._item(path)
