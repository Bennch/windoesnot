"""Nautilus action for launching supported files through WinDoesNot polkit CLI."""
import os
from pathlib import Path
import subprocess
from gi.repository import Gio, GObject, Nautilus


def german():
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'quickshell/default/settings.txt'
    try:
        for line in config.read_text().splitlines():
            if line.startswith('uiLanguage='):
                return line.partition('=')[2].strip() == 'de'
    except OSError:
        pass
    return os.environ.get('LANG', '').lower().startswith('de')


class WinDoesNotAdmin(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, *args):
        files = args[-1]
        if not files or len(files) != 1:
            return []
        item = files[0]
        if item.is_directory():
            return []
        path = item.get_location().get_path()
        if not path:
            return []
        path = Path(path)
        try:
            if not path.is_file():
                return []
        except OSError:
            return []
        if path.suffix.lower() not in ('.sh', '.py') and not os.access(path, os.X_OK):
            return []
        label = 'Als Administrator ausführen' if german() else 'Run as administrator'
        menu = Nautilus.MenuItem(name='WinDoesNot::run_as_admin', label=label, icon='system-run')
        menu.connect('activate', self._activate, str(path))
        return [menu]

    @staticmethod
    def _activate(_menu, path):
        try:
            Gio.Subprocess.new(['windoesnot-run-as-admin', path], Gio.SubprocessFlags.NONE)
        except Exception:
            # Surface a useful error via the desktop notification system.
            subprocess.Popen(['notify-send', 'WinDoesNot', 'Could not start the administrator terminal'])
