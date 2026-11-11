"""Offer the desktop's LocalSend panel for selected local files."""
import os
from pathlib import Path
from gi.repository import Gio, GObject, Nautilus


def german():
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'quickshell/default/settings.txt'
    try:
        for line in config.read_text().splitlines():
            if line.startswith('uiLanguage='):
                return line.partition('=')[2] == 'de'
    except OSError:
        pass
    return os.environ.get('LANG', '').startswith('de')


class WinDoesNotNearby(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, *args):
        files = args[-1]
        if not files or len(files) > 1000:
            return []
        paths = []
        for item in files:
            path = item.get_location().get_path()
            if not path or item.is_directory():
                return []
            paths.append(path)
        menu = Nautilus.MenuItem(name='WinDoesNot::nearby',
                                 label='Mit Gerät in der Nähe teilen' if german() else 'Share with a nearby device',
                                 icon='document-send')
        menu.connect('activate', lambda *_: Gio.Subprocess.new(['windoesnot-nearby', 'share', *paths], Gio.SubprocessFlags.NONE))
        return [menu]
