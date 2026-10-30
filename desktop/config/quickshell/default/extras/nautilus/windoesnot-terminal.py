"""
WindoesNot Terminal Extension for Nautilus
Opens the terminal configured in WindoesNot Settings (settings.txt).
Falls back to ghostty, then xterm if no config found.
"""

import os
from gi.repository import Nautilus, GObject, Gio, GLib

SETTINGS_FILE = os.path.expanduser("~/.config/quickshell/default/settings.txt")
FALLBACK_TERMINAL = "ghostty"


def _german():
    try:
        with open(SETTINGS_FILE, "r") as f:
            for line in f:
                if line.startswith("uiLanguage="):
                    return line.partition("=")[2].strip() == "de"
    except OSError:
        pass
    return os.environ.get("LANG", "").startswith("de")


def _read_configured_terminal():
    try:
        with open(SETTINGS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("defaultTerminal="):
                    val = line[len("defaultTerminal="):].strip()
                    if val:
                        return val
    except OSError:
        pass
    return FALLBACK_TERMINAL


class WindoesNotTerminalAction(GObject.GObject, Nautilus.MenuProvider):

    def _open_terminal(self, path):
        terminal = _read_configured_terminal()
        # Build launch command based on known terminals
        if "ghostty" in terminal:
            cmd = [terminal, f"--working-directory={path}", "--gtk-single-instance=false"]
        elif "kitty" in terminal:
            cmd = [terminal, "--directory", path]
        elif "alacritty" in terminal:
            cmd = [terminal, "--working-directory", path]
        elif "wezterm" in terminal:
            cmd = [terminal, "start", "--cwd", path]
        elif "foot" in terminal:
            cmd = [terminal, "--working-directory", path]
        else:
            # Generic: most terminals support -e or --working-directory
            # Try with --working-directory first; worst case it opens in $HOME
            cmd = ["bash", "-c",
                   f"cd {GLib.shell_quote(path)} && exec {GLib.shell_quote(terminal)}"]
        try:
            Gio.Subprocess.new(cmd, Gio.SubprocessFlags.NONE)
        except Exception:
            # Fallback: launch via bash
            Gio.Subprocess.new(
                ["bash", "-c", f"cd {GLib.shell_quote(path)} && exec {GLib.shell_quote(FALLBACK_TERMINAL)}"],
                Gio.SubprocessFlags.NONE
            )

    def _menu_item_activated(self, _menu, paths):
        for path in paths:
            self._open_terminal(path)

    def _make_item(self, name, paths):
        item = Nautilus.MenuItem(
            name=name,
            label="Im Terminal öffnen" if _german() else "Open in Terminal",
            icon="utilities-terminal"
        )
        item.connect("activate", self._menu_item_activated, paths)
        return item

    def _paths_to_open(self, files):
        paths = []
        for f in files:
            loc = f.get_location() if f.is_directory() else f.get_parent_location()
            path = loc.get_path()
            if path and path not in paths:
                paths.append(path)
        return paths if len(paths) <= 10 else []

    def get_file_items(self, *args):
        files = args[0] if len(args) == 1 else args[1]
        paths = self._paths_to_open(files)
        if paths:
            return [self._make_item("WindoesNotTerminal::open_file", paths)]
        return []

    def get_background_items(self, *args):
        file = args[0] if len(args) == 1 else args[1]
        paths = self._paths_to_open([file])
        if paths:
            return [self._make_item("WindoesNotTerminal::open_folder", paths)]
        return []
