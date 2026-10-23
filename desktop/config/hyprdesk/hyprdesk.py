#!/usr/bin/env python3
# hyprdesk.py — Hyprland Desktop-Icons (GTK4 + gtk4-layer-shell)
# - Eine Layer-Surface pro Monitor (Icons auf allen Monitoren)
# - Icons pro Monitor gespeichert (Geometrie-ID)
# - Drag & Drop mit Klick-Unterdrückung
# - LD_PRELOAD wird beim Starten von Programmen entfernt
# - Layer: BOTTOM (Wallpaper bleibt sichtbar)

import json, os, sys, signal, subprocess, shutil, mimetypes
import cairo
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, Gtk4LayerShell, Pango, GLib, Graphene, Gio

APP_ID = "hyprdesk"
CONFIG_DIR = Path.home() / ".config" / APP_ID
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = CONFIG_DIR / "icons.json"

# Debug-Logging (auf True setzen für ausführliche Logs)
DEBUG = False

def debug(msg):
    """Debug-Ausgabe nur wenn DEBUG aktiviert."""
    if DEBUG:
        try:
            print(f"{msg}", file=sys.stderr)
        except Exception:
            pass

def drag_log(msg):
    """Drag-spezifisches Logging (nur wenn DEBUG aktiv)."""
    if DEBUG:
        try:
            print(f"DRAG: {msg}", file=sys.stderr, flush=True)
        except Exception:
            pass

# Desktop-Ordner multilingual ermitteln (Schreibtisch, Desktop, Bureau, etc.)
_desktop_path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
DESKTOP_DIR = Path(_desktop_path) if _desktop_path else Path.home() / "Desktop"
debug(f"DESKTOP_DIR resolved to: {DESKTOP_DIR}")

# Default-Icons entfernt - nur Desktop-Dateien verwenden
DEFAULT_ICONS = []

GRID = 16                  # 0 = kein Snap
CLICK_DRAG_THRESHOLD = 6   # Pixel: ab hier gilt es als Drag (Klick wird unterdrückt)

# UI-Übersetzungen (DE / EN)
_TR = {
    "de": {
        "trash":            "Papierkorb",
        "open":             "Öffnen",
        "delete":           "Löschen",
        "empty":            "Leeren",
        "hide":             "Ausblenden",
        "show_trash":       "Papierkorb anzeigen",
        "hide_trash":       "Papierkorb ausblenden",
        "change_wallpaper": "Hintergrund ändern",
        "delete_n":         "{n} Icons löschen",
        "new":              "Neu",
        "new_folder":       "Ordner",
        "new_document":     "Dokument",
        "rename":           "Umbenennen",
        "new_folder_name":  "Neuer Ordner",
        "new_document_name":"Neues Dokument",
        "kino_modus":       "Kino-Modus",
        "kino_stop":        "Kino-Modus beenden",
    },
    "en": {
        "trash":            "Trash",
        "open":             "Open",
        "delete":           "Delete",
        "empty":            "Empty",
        "hide":             "Hide",
        "show_trash":       "Show Trash",
        "hide_trash":       "Hide Trash",
        "change_wallpaper": "Change Wallpaper",
        "delete_n":         "Delete {n} Icons",
        "new":              "New",
        "new_folder":       "Folder",
        "new_document":     "Document",
        "rename":           "Rename",
        "new_folder_name":  "New Folder",
        "new_document_name":"New Document",
        "kino_modus":       "Cinema Mode",
        "kino_stop":        "Exit Cinema Mode",
    },
}

def tr(key, lang="de", **kwargs):
    strings = _TR.get(lang, _TR["de"])
    s = strings.get(key, _TR["de"].get(key, key))
    return s.format(**kwargs) if kwargs else s

# Quickshell Settings
QUICKSHELL_SETTINGS = Path.home() / ".config/quickshell/default/settings.txt"
SNAPPY_CONFIG = Path.home() / ".config/snappy-switcher/config.ini"
SWAYNC_DIR = Path.home() / ".config/swaync"
SWAYNC_STYLE = SWAYNC_DIR / "style.css"


def update_snappy_config(accent_color, border_radius):
    """Aktualisiert snappy-switcher config.ini mit Accent-Color und Border-Radius."""
    if not SNAPPY_CONFIG.exists():
        return
    try:
        import re
        text = SNAPPY_CONFIG.read_text()
        text = re.sub(r'^border_color\s*=.*$', f'border_color = {accent_color}', text, flags=re.MULTILINE)
        text = re.sub(r'^corner_radius\s*=.*$', f'corner_radius = {border_radius}', text, flags=re.MULTILINE)
        SNAPPY_CONFIG.write_text(text)
        debug(f"snappy config: border_color={accent_color} corner_radius={border_radius}")
    except Exception as e:
        print(f"snappy config update error: {e}", file=sys.stderr)

_SWAYNC_STRINGS = {
    "de": {
        "title":           "Benachrichtigungen",
        "clear_all":       "Alle löschen",
        "dnd":             "Nicht stören",
        "inhibitors":      "Aktive Sperren",
        "inhibitors_clear":"Alle freigeben",
    },
    "en": {
        "title":           "Notifications",
        "clear_all":       "Clear All",
        "dnd":             "Do Not Disturb",
        "inhibitors":      "Inhibitors",
        "inhibitors_clear":"Clear All",
    },
}

SWAYNC_CONFIG_JSON = SWAYNC_DIR / "config.json"


def update_swaync_language(lang):
    """Aktualisiert swaync config.json mit übersetzten Widget-Texten."""
    if not SWAYNC_CONFIG_JSON.exists():
        return
    s = _SWAYNC_STRINGS.get(lang, _SWAYNC_STRINGS["en"])
    try:
        with open(SWAYNC_CONFIG_JSON, "r") as f:
            cfg = json.load(f)
        wc = cfg.setdefault("widget-config", {})
        wc.setdefault("title", {}).update({"text": s["title"], "button-text": s["clear_all"]})
        wc.setdefault("dnd", {})["text"] = s["dnd"]
        wc.setdefault("inhibitors", {}).update({"text": s["inhibitors"], "button-text": s["inhibitors_clear"]})
        with open(SWAYNC_CONFIG_JSON, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        subprocess.run(["swaync-client", "--reload-config"], capture_output=True)
        debug(f"swaync language updated: {lang}")
    except Exception as e:
        print(f"swaync language update error: {e}", file=sys.stderr)


def _build_swaync_css(accent, r, dark):
    """Generiert swaync CSS direkt aus Python-Templates (kein externer File nötig)."""
    if dark:
        bg       = "rgba(32, 32, 32, 0.85)"
        border   = "rgba(58, 58, 63, 1)"
        switch_bg= "rgba(58, 58, 58, 1)"
        txt      = "#ffffff"
        subtxt   = "#cccccc"
        timetxt  = "#999999"
        low_col  = "#999999"
        scroll   = "rgba(255, 255, 255, 0.2)"
        scroll_h = "rgba(255, 255, 255, 0.3)"
        btn_bg   = "rgba(255, 255, 255, 0.05)"
        btn_hov  = "rgba(255, 255, 255, 0.1)"
        close_bg = "rgba(255, 255, 255, 0.1)"
        close_hov= "rgba(255, 255, 255, 0.2)"
    else:
        bg       = "rgba(242, 242, 242, 0.90)"
        border   = "rgba(192, 192, 192, 1)"
        switch_bg= "rgba(200, 200, 200, 1)"
        txt      = "#000000"
        subtxt   = "#333333"
        timetxt  = "#666666"
        low_col  = "#666666"
        scroll   = "rgba(0, 0, 0, 0.2)"
        scroll_h = "rgba(0, 0, 0, 0.3)"
        btn_bg   = "rgba(0, 0, 0, 0.03)"
        btn_hov  = "rgba(0, 0, 0, 0.08)"
        close_bg = "rgba(0, 0, 0, 0.05)"
        close_hov= "rgba(0, 0, 0, 0.1)"

    return f"""/* generated by hyprdesk – do not edit manually */
* {{
  all: unset;
  font-family: "Cantarell", sans-serif;
  font-size: 13px;
}}
.control-center {{
  background: {bg};
  border: 1px solid {border};
  border-radius: {r}px;
  border-top-left-radius: 0px;
  border-top-right-radius: 0px;
  border-bottom-left-radius: {r}px;
  border-bottom-right-radius: {r}px;
  padding: 15px;
  border-top: none;
}}
.control-center .notification-row {{ margin-bottom: 8px; }}
.control-center .notification-row:last-child {{ margin-bottom: 0; }}
.notification {{
  background: {bg};
  border: 1px solid {border};
  border-radius: {r}px;
  padding: 15px;
  margin: 8px;
}}
.notification.critical {{ border: 1px solid {accent}; }}
.notification-content {{ padding: 5px; }}
.summary {{ font-weight: bold; color: {txt}; font-size: 14px; margin-bottom: 5px; }}
.body {{ color: {subtxt}; font-size: 12px; }}
.time {{ color: {timetxt}; font-size: 11px; margin-top: 5px; }}
.notification-default-action .notification-content {{ padding-left: 10px; }}
.image {{ margin-right: 10px; border-radius: {r}px; }}
.app-icon {{ margin-right: 10px; }}
.close-button {{
  background: {close_bg};
  color: {subtxt};
  border-radius: {r}px;
  padding: 4px 8px;
  margin-left: 10px;
}}
.close-button:hover {{ background: {close_hov}; }}
.notification-action {{
  background: {btn_bg};
  color: {subtxt};
  border: 1px solid {border};
  border-radius: {r}px;
  padding: 6px 12px;
  margin: 4px;
}}
.notification-action:hover {{ background: {btn_hov}; }}
.notification-action:active {{ background: {accent}; color: #ffffff; }}
.control-center .widget-title {{
  color: {txt};
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 10px;
}}
.control-center .widget-title button {{
  background: {btn_bg};
  color: {subtxt};
  border: 1px solid {border};
  border-radius: {r}px;
  padding: 6px 12px;
  margin-left: 10px;
}}
.control-center .widget-title button:hover {{ background: {btn_hov}; }}
.control-center .widget-dnd {{
  background: {btn_bg};
  border: 1px solid {border};
  border-radius: {r}px;
  padding: 10px;
  margin-bottom: 10px;
}}
.control-center .widget-dnd label {{ color: {txt}; }}
.control-center .widget-dnd>switch {{
  background: {switch_bg};
  border-radius: {r}px;
  min-width: 50px;
  min-height: 28px;
}}
.control-center .widget-dnd>switch:checked {{ background: {accent}; }}
.control-center .widget-dnd>switch slider {{
  background: #ffffff;
  border-radius: {r}px;
  min-width: 22px;
  min-height: 22px;
}}
.control-center .widget-inhibitors {{
  background: {btn_bg};
  border: 1px solid {border};
  border-radius: {r}px;
  padding: 10px;
  margin-bottom: 10px;
}}
.control-center .widget-inhibitors button {{
  background: {btn_bg};
  color: {subtxt};
  border: 1px solid {border};
  border-radius: {r}px;
  padding: 6px 12px;
}}
.control-center .widget-inhibitors button:hover {{ background: {btn_hov}; }}
scrollbar {{ background: transparent; width: 6px; }}
scrollbar slider {{ background: {scroll}; border-radius: {r}px; }}
scrollbar slider:hover {{ background: {scroll_h}; }}
.blank-window {{ background: transparent; }}
.notification-group {{ margin-bottom: 10px; }}
.notification-group-headers {{ font-weight: bold; color: {txt}; margin-bottom: 5px; }}
.low {{ border-left: 3px solid {low_col}; }}
.normal {{ border-left: 3px solid {accent}; }}
.critical {{ border-left: 3px solid #ff4444; background: rgba(255, 68, 68, 0.1); }}
"""


def update_swaync_css(accent_color, border_radius, dark_mode):
    """Generiert swaync style.css und lädt swaync neu."""
    if not SWAYNC_DIR.exists():
        return
    try:
        css = _build_swaync_css(accent_color, border_radius, dark_mode)
        SWAYNC_STYLE.write_text(css)
        subprocess.run(["swaync-client", "--reload-css"], capture_output=True)
        debug(f"swaync css updated: dark={dark_mode} accent={accent_color} radius={border_radius}")
    except Exception as e:
        print(f"swaync css update error: {e}", file=sys.stderr)


def parse_quickshell_settings():
    """Liest Desktop-relevante Settings aus quickshell default/settings.txt"""
    settings = {
        "accentColor": "#FE6F2D",  # Default
        "borderRadius": 0,  # Default
        "darkMode": True,  # Default
        "desktopIconSize": 64,  # Default
        "desktopGridSize": 16,  # Default
        "desktopShowTrash": True,  # Default
        "desktopLabelLines": 2,  # Default
        "uiLanguage": "de",  # Default
    }

    if not QUICKSHELL_SETTINGS.exists():
        return settings

    try:
        with open(QUICKSHELL_SETTINGS, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("accentColor="):
                    settings["accentColor"] = line.split("=", 1)[1]
                elif line.startswith("borderRadius="):
                    try:
                        settings["borderRadius"] = int(line.split("=", 1)[1])
                    except ValueError:
                        pass
                elif line.startswith("desktopIconSize="):
                    try:
                        settings["desktopIconSize"] = int(line.split("=", 1)[1])
                    except ValueError:
                        pass
                elif line.startswith("desktopGridSize="):
                    try:
                        settings["desktopGridSize"] = int(line.split("=", 1)[1])
                    except ValueError:
                        pass
                elif line.startswith("desktopShowTrash="):
                    settings["desktopShowTrash"] = line.split("=", 1)[1] == "true"
                elif line.startswith("desktopLabelLines="):
                    try:
                        settings["desktopLabelLines"] = int(line.split("=", 1)[1])
                    except ValueError:
                        pass
                elif line.startswith("darkMode="):
                    settings["darkMode"] = line.split("=", 1)[1].strip() == "true"
                elif line.startswith("uiLanguage="):
                    settings["uiLanguage"] = line.split("=", 1)[1][:2]  # "de", "en", ...
    except Exception as e:
        debug(f"failed to parse quickshell settings: {e}")

    return settings

def load_state():
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH) as f:
                data = json.load(f)
                if isinstance(data, dict) and "monitors" in data:
                    return data
        except Exception as e:
            debug(f"error loading state: {e}")
            pass
    debug("creating new state file")
    return {"monitors": {}}

def save_state(global_state):
    tmp = STATE_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(global_state, f, indent=2)
    os.replace(tmp, STATE_PATH)
    debug(f"state saved -> {STATE_PATH}")

def get_monitor_connector_name(monitor: Gdk.Monitor) -> str:
    """Holt den Connector-Namen (z.B. HDMI-A-1, DP-1) aus Hyprctl.

    Fallback auf Geometrie wenn Hyprctl nicht verfügbar ist.
    """
    geo = monitor.get_geometry()
    try:
        import subprocess
        result = subprocess.run(
            ["windoesnot-hyprctl", "monitors", "-j"],
            capture_output=True,
            text=True,
            check=True
        )
        monitors_data = json.loads(result.stdout)

        # Unser Monitor per Geometrie identifizieren
        # WICHTIG: Bei transform 1/3 sind width/height vertauscht!
        for mon in monitors_data:
            # Bei geraden transforms (0, 2): width/height normal
            # Bei ungeraden transforms (1, 3): width/height vertauscht
            hypr_width = mon["width"]
            hypr_height = mon["height"]
            transform = mon.get("transform", 0)

            # Bei Transform 1 oder 3 vertauschen width/height für GTK-Match
            if transform in [1, 3]:
                hypr_width, hypr_height = hypr_height, hypr_width

            if (mon["x"] == geo.x and mon["y"] == geo.y and
                hypr_width == geo.width and hypr_height == geo.height):
                connector_name = mon["name"]
                debug(f"Monitor at ({geo.x},{geo.y}) {geo.width}x{geo.height} (transform={transform}) -> {connector_name}")
                return connector_name  # z.B. "HDMI-A-1", "DP-1"

        debug(f"WARNING: No matching monitor found in windoesnot-hyprctl for ({geo.x},{geo.y} {geo.width}x{geo.height})")
    except Exception as e:
        debug(f"ERROR: could not get connector name from windoesnot-hyprctl: {e}")

    # Fallback auf alte Geometrie-basierte ID
    # WICHTIG: Alte Format war NICHT einheitlich - verwende das Format aus der originalen Funktion
    fallback_id = f"{geo.x}_{geo.y}_{geo.width}_{geo.height}"
    debug(f"Using fallback ID: {fallback_id}")
    return fallback_id

def monitor_id_from_geometry(geo: Gdk.Rectangle) -> str:
    """Legacy-Funktion für Kompatibilität. Wird durch get_monitor_connector_name ersetzt."""
    # WICHTIG: Alte Reihenfolge war x_y_height_width (nicht width_height!)
    return f"{geo.x}_{geo.y}_{geo.height}_{geo.width}"

def parse_desktop_file(filepath, language=None):
    """Parst eine .desktop Datei und gibt Icon-Spec zurück."""
    try:
        name = None
        localized_names = {}
        icon_name = None
        exec_cmd = None
        file_type = None

        with open(filepath, 'r', encoding='utf-8') as f:
            in_desktop_entry = False
            for line in f:
                line = line.strip()
                if line == "[Desktop Entry]":
                    in_desktop_entry = True
                    continue
                elif line.startswith("["):
                    in_desktop_entry = False
                    continue

                if not in_desktop_entry:
                    continue

                if line.startswith("Name=") and not name:
                    name = line.split("=", 1)[1]
                elif line.startswith("Name[") and "]=" in line:
                    key, value = line.split("]=", 1)
                    localized_names[key[5:]] = value
                elif line.startswith("Icon="):
                    icon_name = line.split("=", 1)[1]
                elif line.startswith("Exec="):
                    exec_cmd = line.split("=", 1)[1]
                elif line.startswith("Type="):
                    file_type = line.split("=", 1)[1]

        language = language or parse_quickshell_settings()["uiLanguage"]
        name = localized_names.get(language, localized_names.get(language.split("_")[0], name))
        if name and icon_name and exec_cmd and file_type == "Application":
            # Exec field kann %U, %F, etc. enthalten - entfernen
            import shlex
            exec_parts = shlex.split(exec_cmd)
            exec_parts = [p for p in exec_parts if not p.startswith("%")]

            return {
                "name": name,
                "icon_name": icon_name,
                "cmd": exec_parts,
                "desktop_file": str(filepath)
            }
    except Exception as e:
        debug(f"failed to parse {filepath}: {e}", file=sys.stderr)
    return None

def get_desktop_files():
    """Scannt ~/Schreibtisch nach .desktop Dateien und anderen Dateien."""
    items = []
    if not DESKTOP_DIR.exists():
        return items

    for filepath in DESKTOP_DIR.iterdir():
        if filepath.name.startswith("."):
            continue

        if filepath.suffix == ".desktop":
            spec = parse_desktop_file(filepath)
            if spec:
                items.append(spec)
        elif filepath.is_file():
            # Reguläre Datei (Bild, Dokument, etc.)
            items.append({
                "name": filepath.name,
                "icon_name": get_icon_for_file(filepath),
                "cmd": ["xdg-open", str(filepath)],
                "file_path": str(filepath)
            })
        elif filepath.is_dir():
            # Ordner
            items.append({
                "name": filepath.name,
                "icon_name": "folder",
                "cmd": ["xdg-open", str(filepath)],
                "file_path": str(filepath)
            })

    return items

def get_icon_for_file(filepath):
    """Bestimmt ein passendes Icon für eine Datei basierend auf Mime-Type."""
    suffix = filepath.suffix.lower()

    # Bild-Dateien
    if suffix in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"]:
        return "image-x-generic"
    # Dokumente
    elif suffix in [".pdf"]:
        return "application-pdf"
    elif suffix in [".doc", ".docx", ".odt"]:
        return "x-office-document"
    elif suffix in [".xls", ".xlsx", ".ods"]:
        return "x-office-spreadsheet"
    elif suffix in [".ppt", ".pptx", ".odp"]:
        return "x-office-presentation"
    # Text
    elif suffix in [".txt", ".md", ".log"]:
        return "text-x-generic"
    # Archive
    elif suffix in [".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"]:
        return "package-x-generic"
    # Video
    elif suffix in [".mp4", ".mkv", ".avi", ".mov", ".webm"]:
        return "video-x-generic"
    # Audio
    elif suffix in [".mp3", ".flac", ".ogg", ".wav", ".m4a"]:
        return "audio-x-generic"
    else:
        return "text-x-generic"

def launch_command(cmd):
    # LD_PRELOAD aus Kinder-Umgebung entfernen, damit Firefox/Thunar etc. nicht crashen
    env = os.environ.copy()
    env.pop("LD_PRELOAD", None)

    # Für xdg-open: MIME-Typ direkt abfragen und gtk-launch verwenden,
    # um den Browser-Fallback von xdg-open zu umgehen
    if len(cmd) >= 2 and cmd[0] == "xdg-open":
        path = Path(cmd[1])
        if path.exists():
            if path.is_dir():
                mime_type = "inode/directory"
            else:
                r = subprocess.run(["xdg-mime", "query", "filetype", str(path)],
                                   capture_output=True, text=True)
                mime_type = r.stdout.strip().split(";")[0]
                # xdg-mime uses content sniffing; fall back to extension if too generic
                if not mime_type or mime_type == "application/octet-stream":
                    guessed, _ = mimetypes.guess_type(str(path))
                    if guessed:
                        mime_type = guessed
            if mime_type:
                r2 = subprocess.run(["xdg-mime", "query", "default", mime_type],
                                    capture_output=True, text=True)
                desktop_file = r2.stdout.strip()
                if desktop_file:
                    cmd = ["gtk-launch", desktop_file, str(path)]
                    debug(f"opening {path.name} ({mime_type}) with {desktop_file}")

    try:
        subprocess.Popen(cmd, env=env)
    except Exception as e:
        debug(f"launch failed {cmd}: {e}", file=sys.stderr)

class DesktopIcon(Gtk.Box):
    def __init__(self, manager, spec, pos=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.manager = manager
        self.spec = spec
        self.x = int((pos or {}).get("x", 32))
        self.y = int((pos or {}).get("y", 32))
        grid = getattr(manager, 'grid_size', GRID)
        if grid > 0:
            self.x = int(round(self.x / grid) * grid)
            self.y = int(round(self.y / grid) * grid)
        self._dragging = False
        self._was_dragging = False  # Gesetzt beim Drag-Start, bleibt bis on_released es prüft
        self._being_transferred = False
        self._press_start = (0, 0)  # Fallback; wird in on_pressed gesetzt
        self._select_timer = None  # Verzögerte Selection für Doppelklick-Erkennung
        self.selected = False  # Selection-Status
        self._over_trash = False  # Ist Icon über Papierkorb?
        self._delete_overlay = None  # Rotes X Overlay

        # Debug: Prüfen ob Icon mit diesem Namen bereits auf diesem Monitor existiert
        existing_count = len([i for i in manager.icons if i.spec['name'] == spec['name']])
        if existing_count > 0:
            debug(f"⚠️  WARNING: Creating icon '{spec['name']}' but {existing_count} already exist on this monitor!")

        # Transparenten Hintergrund für Icon-Box
        self.add_css_class("desktop-icon")

        # Icon mit konfigurierbarer Größe aus Settings
        icon_size = getattr(manager, 'icon_size', 64)
        # Unterstütze absolute Pfade für benutzerdefinierte Icons
        if spec["icon_name"].startswith("/"):
            img = Gtk.Image.new_from_file(spec["icon_name"])
            img.set_pixel_size(icon_size)
        else:
            img = Gtk.Image.new_from_icon_name(spec["icon_name"])
            img.set_pixel_size(icon_size)
        self.icon_image = img  # Referenz speichern für Live-Updates

        # Label mit fester Breite, damit Text nicht abgeschnitten wird
        label_lines = getattr(manager, 'label_lines', 2)
        _lang = getattr(getattr(manager, 'app', None), 'current_language', 'de')
        _display_name = tr("trash", _lang) if spec.get("is_trash") else spec["name"]
        lbl = Gtk.Label(label=_display_name)
        self._name_label = lbl  # Referenz für Live-Updates
        lbl.set_width_chars(12)  # Platz für ~12 Zeichen
        lbl.set_max_width_chars(12)
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_lines(label_lines)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)  # Nötig damit set_lines() wirkt
        self.icon_label = lbl  # Referenz speichern für Live-Updates

        self.append(img)
        self.append(lbl)

        # --- Linksklick / Doppelklick ---
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("pressed", self.on_pressed)
        click.connect("released", self.on_released)
        self.add_controller(click)

        # --- Rechtsklick für Kontextmenü ---
        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_right_click)
        self.add_controller(right_click)

        # Platzieren
        self.manager.overlay.put(self, self.x, self.y)

    # ---- Klicks ----
    def on_pressed(self, gesture, n_press, x, y):
        self._press_start = (x, y)
        # DragSession wird in on_selection_pressed (CAPTURE) initialisiert — zuverlässiger
        if n_press == 2 and not self._dragging:
            # Pending-Selection des ersten Klicks canceln
            if self._select_timer:
                GLib.source_remove(self._select_timer)
                self._select_timer = None
            # Bei Doppelklick: Programm starten und Selection aufheben
            launch_command(self.spec["cmd"])
            # Alle Icons deselektieren (inkl. diesem)
            for icon in self.manager.icons:
                if icon.selected:
                    icon.set_selected(False)

    def on_released(self, gesture, n_press, x, y):
        # Wenn Icon transferiert wird, nichts tun
        if self._being_transferred:
            return

        if self._dragging or self._was_dragging:
            self._was_dragging = False
            # Prüfen ob Icon auf Papierkorb gedroppt wurde
            dropped_on_trash = False
            debug(f"checking drag-to-trash: trash_icon={self.manager.trash_icon}, is_trash={self.spec.get('is_trash')}, dragging={self._dragging}")
            if self.manager.trash_icon and not self.spec.get("is_trash"):
                # Kleinere Zone mit 15px Inset (gleich wie beim Drag)
                inset = 15
                trash_x = self.manager.trash_icon.x + inset
                trash_y = self.manager.trash_icon.y + inset
                trash_w = 100 - (inset * 2)
                trash_h = 100 - (inset * 2)

                # Überschneidung prüfen (muss tatsächlich über dem Icon sein)
                icon_right = self.x + 100
                icon_bottom = self.y + 100
                trash_right = trash_x + trash_w
                trash_bottom = trash_y + trash_h

                # Prüfen ob Icons sich überschneiden
                overlaps = (self.x < trash_right and
                           icon_right > trash_x and
                           self.y < trash_bottom and
                           icon_bottom > trash_y)

                debug(f"icon at ({self.x}, {self.y})-({icon_right}, {icon_bottom}), trash at ({trash_x}, {trash_y})-({trash_right}, {trash_bottom}), overlaps={overlaps}")

                if overlaps:
                    dropped_on_trash = True
                    debug(f"✓ icon '{self.spec['name']}' dropped on trash!")
                    trashed_icons = []

                    # Wenn selektiert, alle selektierten Icons löschen
                    if self.selected:
                        selected_icons = [icon for icon in self.manager.icons if icon.selected and not icon.spec.get("is_trash")]
                        for icon in selected_icons:
                            try:
                                if "desktop_file" in icon.spec:
                                    filepath = Path(icon.spec["desktop_file"])
                                elif "file_path" in icon.spec:
                                    filepath = Path(icon.spec["file_path"])
                                else:
                                    continue

                                if filepath.exists():
                                    file = Gio.File.new_for_path(str(filepath))
                                    file.trash(None)
                                    debug(f"moved to trash: {filepath}")
                                    trashed_icons.append(icon)
                            except Exception as e:
                                debug(f"failed to trash: {e}", file=sys.stderr)
                    else:
                        # Nur dieses Icon löschen
                        try:
                            if "desktop_file" in self.spec:
                                filepath = Path(self.spec["desktop_file"])
                            elif "file_path" in self.spec:
                                filepath = Path(self.spec["file_path"])
                            else:
                                filepath = None

                            if filepath and filepath.exists():
                                file = Gio.File.new_for_path(str(filepath))
                                file.trash(None)
                                debug(f"moved to trash: {filepath}")
                                trashed_icons.append(self)
                        except Exception as e:
                            debug(f"failed to trash: {e}", file=sys.stderr)

                    # Sofort aus UI/Selection entfernen, dann sauber reloaden
                    if trashed_icons:
                        self.manager.remove_icons_by_refs(trashed_icons)
                    GLib.timeout_add(500, self.manager.reload_icons)

            if not dropped_on_trash:
                # Kollisionsprüfung beim Release - Icon zur freien Position verschieben
                collision_icon = self.manager.check_collision(self, self.x, self.y)
                if collision_icon:
                    debug(f"collision detected at release with '{collision_icon.spec['name']}'")
                    # Freie Position in der Nähe suchen
                    geo = self.manager.monitor.get_geometry()
                    found_free_spot = False

                    # Spirale: erst rechts, dann unten, dann links, dann oben
                    offsets = [(96, 0), (0, 120), (-96, 0), (0, -120),
                               (96, 120), (-96, 120), (96, -120), (-96, -120)]

                    for dx, dy in offsets:
                        test_x = self.x + dx
                        test_y = self.y + dy

                        # Bounds checking
                        if test_x < 0 or test_x > geo.width - 120:
                            continue
                        if test_y < 0 or test_y > geo.height - 140:
                            continue

                        # Kollisionsprüfung
                        if not self.manager.check_collision(self, test_x, test_y):
                            debug(f"found free spot at ({test_x}, {test_y})")
                            self.manager.overlay.move(self, test_x, test_y)
                            self.x, self.y = test_x, test_y
                            found_free_spot = True
                            break

                    if not found_free_spot:
                        debug(f"no free spot found nearby, placing at grid start")
                        # Fallback: Finde ersten freien Platz im Raster
                        _g = getattr(self.manager, 'grid_size', GRID)
                        _fb_start = int(round(32 / _g) * _g) if _g > 0 else 32
                        for y in range(_fb_start, geo.height - 140, 120):
                            for x in range(_fb_start, geo.width - 120, 96):
                                if not self.manager.check_collision(self, x, y):
                                    self.manager.overlay.move(self, x, y)
                                    self.x, self.y = x, y
                                    found_free_spot = True
                                    break
                            if found_free_spot:
                                break

                # Position nach Drag speichern
                self.manager.save_monitor_state()

            # Opacity und Overlay zurücksetzen nach Drag
            self.set_opacity(1.0)
            self._over_trash = False
            if self._delete_overlay:
                self._delete_overlay.set_visible(False)
        else:
            # Kein Drag → einfacher Click → Selection verzögert (Doppelklick-Erkennung)
            if n_press == 1:
                target_state = not self.selected
                icon_ref = self

                def _apply_select():
                    icon_ref.set_selected(target_state)
                    for ic in icon_ref.manager.icons:
                        if ic is not icon_ref and ic.selected:
                            ic.set_selected(False)
                    icon_ref._select_timer = None
                    return False

                dbl_ms = Gtk.Settings.get_default().get_property('gtk-double-click-time')
                self._select_timer = GLib.timeout_add(dbl_ms, _apply_select)

        self._dragging = False
        if self.manager._dragged_icon is self:
            self.manager._dragged_icon = None
        if self._being_transferred:
            debug(f"WARNING: _being_transferred was still True in on_released(), resetting flag for '{self.spec['name']}'")
            self._being_transferred = False

    def on_right_click(self, gesture, n_press, x, y):
        """Zeigt Kontextmenü für Icon."""
        # Prüfen ob mehrere Icons selektiert sind
        selected_icons = [icon for icon in self.manager.icons if icon.selected]
        multiple_selected = len(selected_icons) > 1

        menu = Gio.Menu()

        # Multi-Selection-Menü
        _lang = getattr(self.manager.app, 'current_language', 'de')
        if multiple_selected and self.selected:
            menu.append(tr("delete_n", _lang, n=len(selected_icons)), "icon.delete_multiple")
        # Spezial-Menü für Papierkorb
        elif self.spec.get("is_trash"):
            menu.append(tr("open", _lang), "icon.open")
            menu.append(tr("empty", _lang), "icon.empty_trash")
            menu.append(tr("hide", _lang), "icon.hide_trash")
        else:
            menu.append(tr("open", _lang), "icon.open")
            if "file_path" in self.spec:
                menu.append(tr("rename", _lang), "icon.rename")
            menu.append(tr("delete", _lang), "icon.delete")

        # Actions definieren
        action_group = Gio.SimpleActionGroup()

        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", lambda *args: launch_command(self.spec["cmd"]))
        action_group.add_action(open_action)

        # Multi-Delete Action
        if multiple_selected and self.selected:
            delete_multiple_action = Gio.SimpleAction.new("delete_multiple", None)
            delete_multiple_action.connect("activate", self.on_delete_multiple)
            action_group.add_action(delete_multiple_action)

        if self.spec.get("is_trash"):
            empty_action = Gio.SimpleAction.new("empty_trash", None)
            empty_action.connect("activate", self.on_empty_trash)
            action_group.add_action(empty_action)

            hide_action = Gio.SimpleAction.new("hide_trash", None)
            hide_action.connect("activate", lambda *args: self.manager.on_toggle_trash(None, None))
            action_group.add_action(hide_action)
        else:
            if "file_path" in self.spec:
                rename_action = Gio.SimpleAction.new("rename", None)
                rename_action.connect("activate", lambda *args: self.start_rename())
                action_group.add_action(rename_action)
            delete_action = Gio.SimpleAction.new("delete", None)
            delete_action.connect("activate", self.on_delete)
            action_group.add_action(delete_action)

        self.insert_action_group("icon", action_group)

        # Popover erstellen - am Cursor
        popover = Gtk.PopoverMenu()
        popover.set_menu_model(menu)
        popover.insert_action_group("icon", action_group)
        popover.set_parent(self)
        popover.set_has_arrow(False)
        # Offset nach rechts, damit es nicht links erscheint
        rect = Gdk.Rectangle()
        rect.x = int(x) + 10
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    def on_delete(self, action, param):
        """Verschiebt die Datei in den Papierkorb."""
        try:
            # Pfad zur Datei ermitteln
            if "desktop_file" in self.spec:
                filepath = Path(self.spec["desktop_file"])
            elif "file_path" in self.spec:
                filepath = Path(self.spec["file_path"])
            else:
                debug(f"cannot delete: no file path for {self.spec['name']}")
                return

            if filepath.exists():
                # Mit gio trash verwenden (standardisiert)
                file = Gio.File.new_for_path(str(filepath))
                file.trash(None)
                debug(f"moved to trash: {filepath}")

                # Sofort aus UI/Selection entfernen, dann neu laden
                self.manager.remove_icons_by_refs([self])
                GLib.timeout_add(100, self.manager.reload_icons)
        except Exception as e:
            debug(f"failed to trash: {e}", file=sys.stderr)

    def on_delete_multiple(self, action, param):
        """Löscht alle selektierten Icons."""
        selected_icons = [icon for icon in self.manager.icons if icon.selected]
        debug(f"deleting {len(selected_icons)} selected icons")
        trashed_icons = []

        for icon in selected_icons:
            # Papierkorb darf nicht gelöscht werden
            if icon.spec.get("is_trash"):
                debug(f"skipping trash icon")
                continue

            try:
                if "desktop_file" in icon.spec:
                    filepath = Path(icon.spec["desktop_file"])
                elif "file_path" in icon.spec:
                    filepath = Path(icon.spec["file_path"])
                else:
                    continue

                if filepath.exists():
                    file = Gio.File.new_for_path(str(filepath))
                    file.trash(None)
                    debug(f"moved to trash: {filepath}")
                    trashed_icons.append(icon)
            except Exception as e:
                debug(f"failed to trash: {e}", file=sys.stderr)

        # Sofort aus UI/Selection entfernen, dann neu laden
        if trashed_icons:
            self.manager.remove_icons_by_refs(trashed_icons)
        GLib.timeout_add(500, self.manager.reload_icons)

    def on_empty_trash(self, action, param):
        """Leert den Papierkorb."""
        try:
            trash_dir = Path.home() / ".local/share/Trash/files"
            info_dir = Path.home() / ".local/share/Trash/info"

            if trash_dir.exists():
                for item in trash_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            if info_dir.exists():
                for item in info_dir.iterdir():
                    item.unlink()

            debug("trash emptied")
            # Icon aktualisieren
            self.manager.reload_icons()
        except Exception as e:
            debug(f"failed to empty trash: {e}", file=sys.stderr)

    # ---- Bewegung (kein echtes Drag-Objekt) ----
    def _make_motion_controller(self):
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self.on_motion)
        return motion

    def on_motion(self, controller, x, y):
        if self._being_transferred:
            return
        ds = self.manager.app.drag_session
        # Wenn Cursor auf anderem Monitor (cross-monitor proxy drag), hier nichts tun
        if ds.active and ds.current_win is not self.manager:
            return

        state = controller.get_current_event_state()
        lmb = bool(state & Gdk.ModifierType.BUTTON1_MASK) or ds.active
        if lmb:
            self._dragging = True
            # Neue Position berechnen
            dx = int(x - self._press_start[0])
            dy = int(y - self._press_start[1])
            nx = int(self.x + dx)
            ny = int(self.y + dy)
            grid = getattr(self.manager, 'grid_size', GRID)
            if grid > 0:
                nx = int(round(nx / grid) * grid)
                ny = int(round(ny / grid) * grid)

            # Prüfen ob Icon Monitor verlässt (Cross-Monitor-Drag)
            geo = self.manager.monitor.get_geometry()

            # Innerhalb Monitor-Grenzen halten (Cross-monitor passiert via on_drag_enter)
            nx = max(0, min(nx, geo.width - 120))  # 120px Icon-Breite
            ny = max(0, min(ny, geo.height - 140))  # 140px Icon-Höhe

            # KEINE Kollisionserkennung während Drag - nur visuelle Bewegung erlauben
            # Kollision wird erst beim Release geprüft und Position ggf. korrigiert

            # Delta von aktueller zu neuer Position
            actual_dx = nx - self.x
            actual_dy = ny - self.y

            # Wenn dieses Icon selektiert ist, alle selektierten Icons mitbewegen
            if self.selected:
                for icon in self.manager.icons:
                    if icon.selected and icon != self:
                        new_icon_x = icon.x + actual_dx
                        new_icon_y = icon.y + actual_dy
                        # Bounds checking
                        new_icon_x = max(0, min(new_icon_x, geo.width - 120))
                        new_icon_y = max(0, min(new_icon_y, geo.height - 140))
                        self.manager.overlay.move(icon, new_icon_x, new_icon_y)
                        icon.x, icon.y = new_icon_x, new_icon_y

            self.manager.overlay.move(self, nx, ny)
            self.x, self.y = nx, ny

            # Selection-Overlay mitziehen
            if any(icon.selected for icon in self.manager.icons):
                self.manager.selection_area.queue_draw()

            # Prüfen ob über Papierkorb (für visuelles Feedback)
            if self.manager.trash_icon and not self.spec.get("is_trash"):
                # Kleinere Zone mit 15px Inset für präziseres Feedback
                inset = 15
                trash_x = self.manager.trash_icon.x + inset
                trash_y = self.manager.trash_icon.y + inset
                trash_w = 100 - (inset * 2)
                trash_h = 100 - (inset * 2)

                icon_right = self.x + 100
                icon_bottom = self.y + 100
                trash_right = trash_x + trash_w
                trash_bottom = trash_y + trash_h

                overlaps = (self.x < trash_right and
                           icon_right > trash_x and
                           self.y < trash_bottom and
                           icon_bottom > trash_y)

                if overlaps and not self._over_trash:
                    self._over_trash = True
                    self.set_opacity(0.5)  # Halbtransparent
                    # Rotes X Overlay erstellen
                    if not self._delete_overlay:
                        self._delete_overlay = Gtk.Label(label="✕")
                        self._delete_overlay.add_css_class("delete-overlay")
                        self.append(self._delete_overlay)
                    self._delete_overlay.set_visible(True)
                    debug(f"🗑️  icon over trash")
                elif not overlaps and self._over_trash:
                    self._over_trash = False
                    self.set_opacity(1.0)  # Normal
                    if self._delete_overlay:
                        self._delete_overlay.set_visible(False)
                    debug(f"icon left trash zone")

    def update_language(self, lang):
        """Aktualisiert sichtbare Labels wenn die UI-Sprache wechselt."""
        if self.spec.get("is_trash"):
            self._name_label.set_label(tr("trash", lang))
        elif self.spec.get("desktop_file"):
            localized = parse_desktop_file(self.spec["desktop_file"], lang)
            if localized:
                self._name_label.set_label(localized["name"])

    # ---- Inline-Umbenennen ----
    def start_rename(self):
        """Öffnet Rename-Popover (xdg_popup bekommt automatisch Tastatur-Fokus)."""
        if getattr(self, '_rename_popover', None) is not None:
            return
        self._original_name = self.spec['name']
        self._original_file_path = self.spec.get('file_path', '')
        self._rename_escape = False
        self._rename_done = False
        self.manager._icon_being_renamed = self

        entry = Gtk.Entry()
        entry.set_text(self.spec['name'])
        entry.select_region(0, -1)
        entry.set_alignment(0.5)
        entry.set_width_chars(16)
        self._rename_entry_ref = entry

        popover = Gtk.Popover()
        popover.set_child(entry)
        popover.set_parent(self)
        popover.set_has_arrow(True)
        popover.set_autohide(True)
        self._rename_popover = popover

        # Enter → schließt Popover → "closed" bestätigt
        entry.connect("activate", lambda e: popover.popdown())

        # Escape → Flag setzen → schließt Popover → "closed" bricht ab
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._rename_on_key)
        entry.add_controller(key_ctrl)

        popover.connect("closed", self._on_rename_closed)
        popover.popup()

    def _rename_on_key(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._rename_escape = True
            self._rename_popover.popdown()
            return True
        return False

    def _on_rename_closed(self, popover):
        """Wird aufgerufen wenn Rename-Popover geschlossen wird (Enter, Escape, Klick außen)."""
        if self._rename_done:
            return
        self._rename_done = True

        new_name = self._rename_entry_ref.get_text().strip() if self._rename_entry_ref else ''
        self._rename_popover = None
        self._rename_entry_ref = None
        self.manager._icon_being_renamed = None

        if self._rename_escape:
            return

        if not new_name or new_name == self._original_name:
            return

        old_path = Path(self._original_file_path)
        if old_path.exists():
            new_path = old_path.parent / new_name
            try:
                old_path.rename(new_path)
                self.spec['name'] = new_name
                self.spec['file_path'] = str(new_path)
                self.spec['cmd'] = ['xdg-open', str(new_path)]
                self.icon_label.set_text(new_name)
                self.manager.save_monitor_state()
            except Exception as e:
                print(f"rename failed: {e}", file=sys.stderr)

    def to_dict(self):
        """Speichert Icon-Position und Daten."""
        result = {
            "name": self.spec["name"],
            "icon_name": self.spec["icon_name"],
            "cmd": self.spec["cmd"],
            "x": self.x,
            "y": self.y
        }
        # Optional: desktop_file, file_path, is_trash wenn vorhanden
        if "desktop_file" in self.spec:
            result["desktop_file"] = self.spec["desktop_file"]
        if "file_path" in self.spec:
            result["file_path"] = self.spec["file_path"]
        if "is_trash" in self.spec:
            result["is_trash"] = self.spec["is_trash"]
        return result

    def set_selected(self, selected):
        """Setzt den Selection-Status und aktualisiert das visuelle Feedback."""
        self.selected = selected
        if selected:
            self.add_css_class("selected")
        else:
            self.remove_css_class("selected")
        self.manager._update_selection_overlay()

    def destroy_completely(self):
        """Zerstört das Icon komplett und entfernt alle Event-Handler."""
        debug(f"destroying icon '{self.spec['name']}' completely")
        # Flag setzen um weitere Events zu blockieren
        self._being_transferred = True
        # Widget verstecken und deaktivieren
        self.set_visible(False)
        self.set_sensitive(False)
        self.set_can_focus(False)
        self.set_can_target(False)
        # Alle Event-Controller entfernen
        for controller in list(self.observe_controllers()):
            self.remove_controller(controller)


class MonitorWindow:
    """Eine Layer-Surface pro Monitor, mit eigener Icon-Liste."""
    def __init__(self, app, monitor: Gdk.Monitor, global_state: dict):
        self.app = app
        self.monitor = monitor
        self.global_state = global_state
        self.drag_in_progress = False
        self.icons = []
        self.show_trash = True  # Papierkorb standardmäßig anzeigen
        self.trash_icon = None

        # Auswahl-Rechteck
        self.selection_active = False
        self.selection_visible = False  # Erst anzeigen nach Mindest-Bewegung
        self.selection_start = None
        self.selection_current = None

        # Icon-Drag (overlay-level tracking)
        self._dragged_icon = None
        self._reload_timeout = None

        # Event-Controller-Tracking (für späteres Cleanup)
        self.event_controllers = []

        # Aktives Kontextmenü-Widget (kein xdg_popup, um Hyprland-Focus-Bug zu vermeiden)
        self._context_menu = None
        self._icon_being_renamed = None

        self.win = Gtk.ApplicationWindow(application=self.app)

        # Layer: BACKGROUND (hinter allem, über dem Wallpaper)
        Gtk4LayerShell.init_for_window(self.win)
        Gtk4LayerShell.set_layer(self.win, Gtk4LayerShell.Layer.BACKGROUND)

        # Namespace setzen für Hyprland-Identifikation
        Gtk4LayerShell.set_namespace(self.win, "hyprdesk-desktop")

        for e in (Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.BOTTOM,
                  Gtk4LayerShell.Edge.LEFT, Gtk4LayerShell.Edge.RIGHT):
            Gtk4LayerShell.set_anchor(self.win, e, True)
        Gtk4LayerShell.set_exclusive_zone(self.win, 0)
        Gtk4LayerShell.set_monitor(self.win, monitor)

        # ON_DEMAND: Compositor kann Fokus geben wenn Popup schliesst (verhindert special:minimized-Bug).
        # Auf BACKGROUND-Layer gibt Hyprland ohnehin nie aktiv Fokus an diese Fläche.
        Gtk4LayerShell.set_keyboard_mode(self.win, Gtk4LayerShell.KeyboardMode.ON_DEMAND)

        # CSS laden - Settings werden direkt gelesen (kein Cache nötig!)
        self.load_css_theme()

        # FileMonitor für Theme-Settings (nur einmal pro App!)
        if not hasattr(self.app, '_theme_monitor_setup'):
            self.setup_theme_monitor()
            self.app._theme_monitor_setup = True

        # WICHTIG: CSS-Klasse zum Fenster hinzufügen!
        self.win.add_css_class("transparent-window")

        # Monitor-ID setzen (jetzt Connector-Name statt Geometrie)
        self.monitor_id = get_monitor_connector_name(monitor)
        geo = monitor.get_geometry()

        # Fixed-Container für Icons - jetzt mit transparentem Fenster-Hintergrund
        self.overlay = Gtk.Fixed()
        # WICHTIG: Größe setzen damit Overlay Events empfängt auch wenn leer
        self.overlay.set_size_request(geo.width, geo.height)

        # Unsichtbarer Event-Catcher im Hintergrund (damit leere Overlays Events empfangen)
        self.event_catcher = Gtk.DrawingArea()
        self.event_catcher.set_size_request(geo.width, geo.height)
        self.event_catcher.set_can_target(True)  # Events empfangen
        self.event_catcher.set_content_width(geo.width)
        self.event_catcher.set_content_height(geo.height)
        # Transparent zeichnen (nichts tun)
        self.event_catcher.set_draw_func(lambda area, cr, w, h: None)
        self.overlay.put(self.event_catcher, 0, 0)
        debug(f"event_catcher created: {geo.width}x{geo.height} on monitor {self.monitor_id}")

        # Selection-Area erstellen
        self.setup_selection_area()

        # Drag & Drop Target einrichten
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self.on_drop)
        self.overlay.add_controller(drop_target)

        # Event-Controller einrichten (Selection, Rechtsklick, etc.)
        self.setup_event_controllers()

        self.win.set_child(self.overlay)
        self.win.present()

        # Desktop-Dateien laden
        self.load_desktop_icons()

        # FileMonitor für ~/Schreibtisch einrichten
        self.setup_file_monitor()

        # Polling-Fallback nur auf primärem Monitor (stabile ID, auch nach Reload)
        if self.monitor_id == getattr(self.app, "primary_monitor_id", self.monitor_id):
            self.setup_desktop_polling()

    def setup_event_controllers(self):
        """Richtet alle Event-Controller für das Overlay ein (Selection, Rechtsklick, etc.)."""
        # Alte Controller entfernen falls vorhanden
        for controller in self.event_controllers:
            try:
                self.overlay.remove_controller(controller)
            except:
                pass
        self.event_controllers.clear()

        # Rechtsklick-Menü für Desktop-Hintergrund
        # WICHTIG: Mit CAPTURE phase um Events VOR den Icons zu bekommen
        right_click = Gtk.GestureClick()
        right_click.set_button(3)  # Rechte Maustaste
        right_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        right_click.connect("pressed", self.on_desktop_right_click)
        self.overlay.add_controller(right_click)
        self.event_controllers.append(right_click)

        # Linksklick für Auswahl-Rechteck (nur auf Hintergrund)
        left_click = Gtk.GestureClick()
        left_click.set_button(1)  # Linke Maustaste
        left_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        left_click.connect("pressed", self.on_selection_pressed)
        left_click.connect("released", self.on_selection_released)
        self.overlay.add_controller(left_click)
        self.event_controllers.append(left_click)

        # Motion-Events für Auswahl-Rechteck, Icon-Drag und Cross-Monitor-Proxy
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self.on_selection_motion)
        motion.connect("enter", self.on_drag_enter)
        self.overlay.add_controller(motion)
        self.event_controllers.append(motion)

        # Legacy-Events: LMB-Release zuverlässig erkennen (auch nach Cross-Monitor-Transfer,
        # wo GestureClick kein 'released' sendet weil es den 'pressed' nicht gesehen hat)
        legacy = Gtk.EventControllerLegacy()
        legacy.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        legacy.connect("event", self.on_raw_event)
        self.overlay.add_controller(legacy)
        self.event_controllers.append(legacy)

        # Keyboard-Events für DEL-Taste
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(key_controller)
        self.event_controllers.append(key_controller)

        debug(f"setup_event_controllers: {len(self.event_controllers)} controllers on overlay for monitor {self.monitor_id}")

    def setup_selection_area(self):
        """Erstellt die Selection DrawingArea im Overlay."""
        geo = self.monitor.get_geometry()
        self.selection_area = Gtk.DrawingArea()
        self.selection_area.set_draw_func(self.draw_selection_rectangle)
        # Volle Monitor-Größe setzen um Resize zu vermeiden
        self.selection_area.set_size_request(geo.width, geo.height)
        self.selection_area.set_can_target(False)  # Keine Events abfangen
        self.selection_area.set_visible(True)
        self.overlay.put(self.selection_area, 0, 0)

    def load_desktop_icons(self, reload_from_state_only=False, exclude_names=None):
        """Lädt Icons aus ~/Schreibtisch und gespeicherten Positionen.

        Args:
            reload_from_state_only: Wenn True, nur aus gespeichertem State laden (kein Desktop-Scan)
        """
        debug(f"=== LOADING ICONS FOR MONITOR {self.monitor_id} (state_only={reload_from_state_only}) ===")

        # State für diesen Monitor holen
        mon_state = self.global_state.setdefault("monitors", {}).setdefault(self.monitor_id, {})
        debug(f"Monitor state: {mon_state}")

        geo = self.monitor.get_geometry()

        # Primärmonitor stabil über App-State bestimmen (auch bei Reloads korrekt)
        is_primary = (self.monitor_id == getattr(self.app, "primary_monitor_id", self.monitor_id))

        # Aber wenn dieser Monitor bereits Icons gespeichert hat, lade sie
        has_saved_icons = "icons" in mon_state and len(mon_state["icons"]) > 0

        debug(f"monitor #{len(self.app.windows)}: {self.monitor_id}, x={geo.x}, y={geo.y}, primary={is_primary}, has_saved={has_saved_icons}")

        # Desktop-Dateien scannen - nur primary scannt Desktop, um neue Dateien zu entdecken
        if reload_from_state_only:
            debug(f"Reload from state only - skipping desktop scan")
            desktop_items = []
        else:
            # Nur primary scannt Desktop, um neue Dateien zu entdecken
            desktop_items = get_desktop_files() if is_primary else []
            if desktop_items:
                debug(f"Desktop scan found {len(desktop_items)} items (primary={is_primary})")
            else:
                debug(f"Desktop scan found 0 items (primary={is_primary})")

        # Gespeicherte Positionen laden
        saved_positions = {item["name"]: item for item in mon_state.get("icons", [])}

        # Helper: Icon-Spec aus saved item rekonstruieren
        def spec_from_saved(saved_item):
            if saved_item.get("is_trash"):
                trash_icon_full = str(Path.home() / ".config/quickshell/default/img/icons8-full-bin-windows.svg")
                trash_icon_empty = str(Path.home() / ".config/quickshell/default/img/icons8-bin-windows-96.png")
                icon_name = trash_icon_full if self.is_trash_full() else trash_icon_empty
            else:
                icon_name = saved_item["icon_name"]

            icon_spec = {"name": saved_item["name"], "icon_name": icon_name, "cmd": saved_item["cmd"]}
            if "desktop_file" in saved_item: icon_spec["desktop_file"] = saved_item["desktop_file"]
            if "file_path" in saved_item:   icon_spec["file_path"] = saved_item["file_path"]
            if "is_trash" in saved_item:    icon_spec["is_trash"] = saved_item["is_trash"]
            return icon_spec

        # Icons erstellen - IMMER STATE-FIRST
        debug(f"Rendering {len(saved_positions)} saved icons (state-first)")

        # 1) Render saved icons - aber nur wenn die Datei noch existiert!
        # WICHTIG: Beim reload_from_state_only auch Trash aus State laden (keine separate Trash-Logik!)
        for name, saved_item in saved_positions.items():
            if exclude_names and name in exclude_names:
                continue  # Wird manuell als Soft-Reparent hinzugefügt (laufender Drag)
            if saved_item.get("is_trash") and not reload_from_state_only:
                continue  # Trash wird weiter unten separat behandelt (nur im Normalmodus)

            # Prüfen ob die Datei noch existiert (außer für Papierkorb)
            if not saved_item.get("is_trash"):
                file_exists = False
                if "desktop_file" in saved_item:
                    file_exists = Path(saved_item["desktop_file"]).exists()
                elif "file_path" in saved_item:
                    file_exists = Path(saved_item["file_path"]).exists()

                if not file_exists:
                    debug(f"Skipping '{name}' - file no longer exists")
                    continue

            pos = {"x": saved_item["x"], "y": saved_item["y"]}
            icon = DesktopIcon(self, spec_from_saved(saved_item), pos=pos)
            self.icons.append(icon)
            # Trash-Referenz speichern
            if saved_item.get("is_trash"):
                self.trash_icon = icon

        # 2) Primary: neue Desktop-Dateien hinzufügen (nur wenn NICHT schon irgendwo im global State existieren)
        if is_primary and desktop_items and not reload_from_state_only:
            # Sammle alle Icon-Namen die im GLOBALEN STATE existieren (über alle Monitore)
            # WICHTIG: Beim Startup sind noch nicht alle Monitore geladen, daher State-basiert prüfen!
            existing_in_state = set()
            for monitor_id, monitor_data in self.global_state.get("monitors", {}).items():
                for icon_data in monitor_data.get("icons", []):
                    name = icon_data.get("name")
                    if name:
                        existing_in_state.add(name)

            debug(f"Icons in global state (all monitors): {len(existing_in_state)} icons")

            # Neue Desktop-Dateien hinzufügen
            _g = getattr(self, 'grid_size', GRID)
            _start = int(round(32 / _g) * _g) if _g > 0 else 32
            next_x, next_y = _start, _start
            new_count = 0
            for item in desktop_items:
                if item["name"] in existing_in_state:
                    debug(f"  Skipping '{item['name']}' - already in state")
                    continue  # Existiert bereits im State (auf irgendeinem Monitor)
                debug(f"  Adding NEW icon: '{item['name']}' at ({next_x}, {next_y})")
                pos = {"x": next_x, "y": next_y}
                next_x += 96
                if next_x > 800:
                    next_x = 32
                    next_y += 120
                self.icons.append(DesktopIcon(self, item, pos=pos))
                new_count += 1
            if new_count > 0:
                debug(f"✅ Added {new_count} new desktop items")
            else:
                debug(f"⚠️  No new items added (all {len(desktop_items)} already in state)")

        # Papierkorb Icon hinzufügen - nur auf einem Monitor!
        trash_in_saved = "Papierkorb" in saved_positions

        # Beim Reload: Papierkorb wurde bereits im saved state geladen, NICHT nochmal erstellen!
        if reload_from_state_only:
            show_trash_here = False
            if trash_in_saved:
                debug(f"Reload mode: Trash already loaded from saved state, skipping duplicate")
        else:
            # Prüfen ob Papierkorb bereits auf einem ANDEREN Monitor existiert
            trash_on_other_monitor = False
            for mon_id, mon_data in self.global_state.get("monitors", {}).items():
                if mon_id != self.monitor_id:
                    other_icons = mon_data.get("icons", [])
                    if any(i.get("name") == "Papierkorb" for i in other_icons):
                        trash_on_other_monitor = True
                        debug(f"Trash already exists on monitor {mon_id}")
                        break

            # Zeige Papierkorb wenn:
            # 1. Hier gespeichert (wurde hierhin verschoben) ODER
            # 2. Primärer Monitor UND nicht woanders gespeichert UND Show-Trash aktiviert
            show_trash_here = False
            if trash_in_saved:
                show_trash_here = True
                debug(f"Trash saved on this monitor")
            elif is_primary and not trash_on_other_monitor and self.show_trash:
                show_trash_here = True
                debug(f"This is primary, showing trash here")

        if show_trash_here:
            trash_pos = saved_positions.get("Papierkorb", {"x": 32, "y": next_y + 120 if desktop_items else 32})
            # Benutzerdefinierte Icons für vollen/leeren Papierkorb
            trash_icon_full = str(Path.home() / ".config/quickshell/default/img/icons8-full-bin-windows.svg")
            trash_icon_empty = str(Path.home() / ".config/quickshell/default/img/icons8-bin-windows-96.png")
            self.trash_icon = DesktopIcon(self, {
                "name": "Papierkorb",
                "icon_name": trash_icon_full if self.is_trash_full() else trash_icon_empty,
                "cmd": ["nautilus", "trash:///"],
                "is_trash": True
            }, pos=trash_pos)
            self.icons.append(self.trash_icon)
            debug(f"Added trash icon")

        # Wenn keine Desktop-Dateien vorhanden, zeige Default-Icons (nur auf primärem Monitor UND nicht beim Reload)
        if not desktop_items and is_primary and not reload_from_state_only:
            debug(f"No desktop items, showing {len(DEFAULT_ICONS)} default icons")
            for idx, i in enumerate(DEFAULT_ICONS):
                # Auch für Default-Icons gespeicherte Positionen nutzen
                if i["name"] in saved_positions:
                    pos = saved_positions[i["name"]]
                else:
                    pos = {"x": 32 + idx*96, "y": 32}
                debug(f"Creating default icon: {i['name']} at {pos}")
                self.icons.append(DesktopIcon(self, i, pos=pos))

        debug(f"Total icons on this monitor: {len(self.icons)}")

        # State speichern, damit Icons auch bei Neustart erscheinen
        # WICHTIG: Nur wenn dieser Monitor Icons hat ODER wenn es der primäre ist
        # ABER NICHT beim Reload (reload_from_state_only=True), weil State schon korrekt ist
        if not reload_from_state_only and (self.icons or is_primary):
            debug(f"Saving state for monitor {self.monitor_id}")
            self.save_monitor_state()

        debug(f"=== LOADING COMPLETE ===")

    def load_css_theme(self):
        """Lädt CSS-Theme mit aktueller Akzentfarbe aus Quickshell-Settings."""
        # Quickshell Settings laden
        settings = parse_quickshell_settings()
        accent_color = settings["accentColor"]
        border_radius = settings["borderRadius"]
        self.icon_size = settings["desktopIconSize"]
        self.grid_size = settings["desktopGridSize"]
        self.show_trash = settings["desktopShowTrash"]
        self.label_lines = settings["desktopLabelLines"]

        # Hex-Farbe zu RGB konvertieren
        try:
            if accent_color.startswith("#"):
                hex_color = accent_color[1:]
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
            else:
                r, g, b = 100, 150, 255  # Fallback
        except Exception:
            r, g, b = 100, 150, 255  # Fallback

        # WICHTIG: Globalen CSS-Provider wiederverwenden statt neue zu erstellen!
        if not hasattr(self.app, '_global_css_provider'):
            self.app._global_css_provider = Gtk.CssProvider()
            # Nur beim ersten Mal hinzufügen
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                self.app._global_css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
            debug(f"Global CSS provider created")

        css = f"""
            .transparent-window {{
                background-color: rgba(0, 0, 0, 0.0);
                background: none;
            }}
            .desktop-icon {{
                background: none;
                border: 2px solid transparent;  /* Unsichtbarer Border verhindert Springen */
                padding: 8px;
            }}
            .desktop-icon:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: {border_radius}px;
            }}
            .desktop-icon.selected:hover {{
                background: none;
            }}
            .desktop-icon.selected {{
            }}
            .desktop-icon label {{
                color: white;
                text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.9);
                font-weight: bold;
            }}
            .delete-overlay {{
                color: #ff0000;
                font-size: 48px;
                font-weight: bold;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
                margin-top: -20px;
            }}
            .desktop-context-menu {{
                background-color: rgba(28, 28, 28, 0.97);
                border-radius: {border_radius}px;
                border: 1px solid rgba(255, 255, 255, 0.12);
                padding: 4px 0px;
            }}
            .desktop-context-menu button {{
                background: transparent;
                border: none;
                border-radius: 0px;
                color: white;
                padding: 6px 12px;
                margin: 0 {2 if border_radius > 0 else 0}px;
                min-width: 0px;
            }}
            .desktop-context-menu button:hover {{
                background-color: rgba({r}, {g}, {b}, 0.35);
                border-radius: {max(0, border_radius - 2) if border_radius > 0 else 0}px;
            }}
            popover.menu > contents {{
                border-radius: {border_radius}px;
            }}
        """
        # Gleichen Provider mit neuen Daten laden
        self.app._global_css_provider.load_from_data(css.encode())
        debug(f"CSS reloaded with accent color: {accent_color}")

    def setup_theme_monitor(self):
        """Richtet FileMonitor für Quickshell-Settings ein (nur einmal pro App!)."""
        # WICHTIG: Monitor auf die RICHTIGE Datei setzen (die wir auch lesen!)
        settings_file = QUICKSHELL_SETTINGS
        if not settings_file.exists():
            debug(f"Theme settings file not found: {settings_file}")
            return

        settings_gfile = Gio.File.new_for_path(str(settings_file))
        theme_monitor = settings_gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        theme_monitor.connect("changed", self.on_theme_changed)
        # Monitor an App speichern damit er nicht garbage-collected wird
        self.app._theme_monitor = theme_monitor
        debug(f"Theme monitor setup for: {settings_file}")

    def on_theme_changed(self, monitor, file, other_file, event_type):
        """Callback wenn Theme-Settings geändert werden."""
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            debug(f"Theme settings changed, reloading CSS on all monitors")
            # CSS auf ALLEN Monitoren neu laden
            def reload_theme_on_all():
                for window in self.app.windows:
                    window.load_css_theme()
                    # WICHTIG: Styles auf allen Icons neu anwenden!
                    for icon in window.icons:
                        # CSS-Klasse kurz entfernen und wieder hinzufügen um Neuzeichnung zu erzwingen
                        if icon.selected:
                            icon.remove_css_class("selected")
                            icon.add_css_class("selected")
                        icon.queue_draw()
                debug(f"Theme reload complete - {sum(len(w.icons) for w in self.app.windows)} icons updated")
                return False

            GLib.timeout_add(200, reload_theme_on_all)
            # Snappy-Switcher + swaync synchronisieren
            settings = parse_quickshell_settings()
            update_snappy_config(settings["accentColor"], settings["borderRadius"])
            update_swaync_css(settings["accentColor"], settings["borderRadius"], settings["darkMode"])

    def setup_file_monitor(self):
        """Richtet FileMonitor für ~/Schreibtisch ein."""
        if not DESKTOP_DIR.exists():
            DESKTOP_DIR.mkdir(parents=True, exist_ok=True)

        desktop_file = Gio.File.new_for_path(str(DESKTOP_DIR))
        # WATCH_MOVES aktivieren um auch Wiederherstellungen aus Papierkorb zu erkennen
        self.file_monitor = desktop_file.monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES | Gio.FileMonitorFlags.SEND_MOVED,
            None
        )
        self.file_monitor.connect("changed", self.on_desktop_changed)
        debug(f"monitoring {DESKTOP_DIR} with WATCH_MOVES")

    def setup_desktop_polling(self):
        """Richtet periodisches Polling des Desktop-Ordners ein (Fallback für FileMonitor)."""
        # Aktuellen Zustand speichern
        self._last_desktop_files = set()
        if DESKTOP_DIR.exists():
            self._last_desktop_files = {f.name for f in DESKTOP_DIR.iterdir() if not f.name.startswith(".")}

        debug(f"initial desktop files: {self._last_desktop_files}")

        # Polling alle 2 Sekunden (schneller für besseres Feedback)
        def check_desktop_changes():
            if not DESKTOP_DIR.exists():
                debug(f"WARNING: DESKTOP_DIR does not exist: {DESKTOP_DIR}")
                return True  # Weiter pollen

            try:
                current_files = {f.name for f in DESKTOP_DIR.iterdir() if not f.name.startswith(".")}
            except Exception as e:
                debug(f"ERROR reading desktop dir: {e}")
                return True

            # Debug: Immer ausgeben um zu sehen dass Polling läuft
            debug(f"polling {DESKTOP_DIR}: current={len(current_files)} files, last={len(self._last_desktop_files)} files")

            # Neue oder gelöschte Dateien?
            if current_files != self._last_desktop_files:
                added = current_files - self._last_desktop_files
                removed = self._last_desktop_files - current_files

                if added:
                    debug(f"🆕 polling detected NEW files: {added}")
                if removed:
                    debug(f"🗑️  polling detected REMOVED files: {removed}")

                self._last_desktop_files = current_files

                # Reload triggern - NUR für den primären Monitor (dieser hier)
                # Alle anderen Monitore werden automatisch aktualisiert durch den globalen State
                debug(f"triggering reload on PRIMARY monitor {self.monitor_id}")
                self.schedule_reload(self._reload_all_monitors)

            return True  # Weiter pollen

        self._poll_source = GLib.timeout_add_seconds(2, check_desktop_changes)
        debug(f"✅ desktop polling enabled (every 2 seconds)")

    def on_desktop_changed(self, monitor, file, other_file, event_type):
        """Callback wenn sich ~/Schreibtisch ändert."""
        filename = file.get_basename() if file else "unknown"
        debug(f"desktop changed: {event_type.value_name} for '{filename}'")

        # Immer global reloaden: FileMonitor kann auf jedem Monitor feuern.
        # Nur so werden neue/wiederhergestellte Desktop-Dateien zuverlässig sichtbar.
        self.schedule_reload(self._reload_all_monitors)

    def schedule_reload(self, callback):
        """Debounced Reload-Scheduler ohne GLib source_remove Warnungen."""
        if self._reload_timeout:
            try:
                ctx = GLib.MainContext.default()
                src = ctx.find_source_by_id(self._reload_timeout) if ctx else None
                if src is not None:
                    GLib.source_remove(self._reload_timeout)
            except Exception:
                pass
            self._reload_timeout = None

        def _run():
            self._reload_timeout = None
            return callback()

        self._reload_timeout = GLib.timeout_add(200, _run)

    def _reload_all_monitors(self):
        """Reload für ALLE Monitore - verhindert Race Conditions."""
        # Prüfen ob bereits ein Reload läuft (global lock)
        if hasattr(self.app, '_reload_in_progress') and self.app._reload_in_progress:
            debug(f"⚠️  RELOAD SKIPPED - reload already in progress")
            return False

        # Global lock setzen
        self.app._reload_in_progress = True
        debug(f"🔄 RELOAD ALL MONITORS (triggered by {self.monitor_id})")

        try:
            # ALLE Monitore nacheinander reloaden
            for window in self.app.windows:
                debug(f"  Reloading monitor {window.monitor_id}")
                old_count = len(window.icons)

                # Alte Icons entfernen
                for icon in window.icons:
                    window.overlay.remove(icon)
                window.icons.clear()

                # Neu laden
                window.load_desktop_icons()
                debug(f"    {old_count} -> {len(window.icons)} icons")

                # State speichern
                window.save_monitor_state()
        finally:
            # Global lock freigeben
            self.app._reload_in_progress = False
            debug(f"✅ RELOAD COMPLETE")

        return False  # Timeout nicht wiederholen

    def reload_icons(self):
        """Lädt Icons für DIESEN Monitor neu."""
        if self._icon_being_renamed is not None:
            debug("skipping reload - icon being renamed")
            return False
        debug(f"🔄 RELOAD ICONS on monitor {self.monitor_id}")

        # Alte Icons entfernen
        old_count = len(self.icons)
        for icon in self.icons:
            self.overlay.remove(icon)
        self.icons.clear()
        debug(f"  Removed {old_count} old icons")

        # Neu laden
        self.load_desktop_icons()
        debug(f"  Loaded {len(self.icons)} new icons")

        # State speichern nach Reload, um gelöschte Icons aus State zu entfernen
        self.save_monitor_state()

        return False  # Timeout nicht wiederholen

    def clear_all_selection(self):
        """Entfernt zuverlässig alle Selektionen inkl. Rubber-Band-State."""
        for icon in self.icons:
            if icon.selected:
                icon.set_selected(False)
        self.selection_active = False
        self.selection_visible = False
        self.selection_start = None
        self.selection_current = None
        self.selection_area.queue_draw()

    def remove_icons_by_refs(self, icons_to_remove):
        """Entfernt Widgets sofort aus Overlay + Icon-Liste (gegen Ghost-Selection)."""
        if not icons_to_remove:
            return
        remove_set = set(icons_to_remove)

        for icon in list(icons_to_remove):
            if icon not in self.icons:
                continue
            icon.set_selected(False)
            icon.set_visible(False)
            try:
                self.overlay.remove(icon)
            except Exception:
                pass
            try:
                icon.unparent()
            except Exception:
                pass

        self.icons = [icon for icon in self.icons if icon not in remove_set]
        self.clear_all_selection()

    def on_drop(self, drop_target, value, x, y):
        """Callback wenn Dateien auf den Desktop gedroppt werden."""
        debug(f"drop at ({x}, {y})")

        if isinstance(value, Gdk.FileList):
            files = value.get_files()
            for gfile in files:
                source_path = Path(gfile.get_path())
                dest_path = DESKTOP_DIR / source_path.name

                debug(f"copying {source_path} to {dest_path}")

                try:
                    # Datei oder Ordner kopieren
                    if source_path.is_file():
                        import shutil
                        shutil.copy2(source_path, dest_path)
                    elif source_path.is_dir():
                        import shutil
                        shutil.copytree(source_path, dest_path, dirs_exist_ok=True)

                    debug(f"successfully copied to {dest_path}")
                except Exception as e:
                    debug(f"failed to copy: {e}", file=sys.stderr)

            return True  # Drop akzeptiert

        return False

    def on_desktop_right_click(self, gesture, n_press, x, y):
        """Zeigt Kontextmenü für Desktop-Hintergrund (PopoverMenu)."""
        debug(f"desktop right click at ({x}, {y}) on monitor {self.monitor_id}")

        # Widget unter dem Cursor finden
        widget = self.overlay.pick(x, y, Gtk.PickFlags.DEFAULT)

        # Wenn das Widget ein DesktopIcon ist, lass es sein Event handhaben
        if widget and isinstance(widget.get_parent(), DesktopIcon):
            return Gdk.EVENT_PROPAGATE
        if widget and isinstance(widget, DesktopIcon):
            return Gdk.EVENT_PROPAGATE

        _lang = getattr(self.app, 'current_language', 'de')
        menu = Gio.Menu()

        menu.append(tr("change_wallpaper", _lang), "desktopbg.change_wallpaper")
        trash_label = tr("hide_trash", _lang) if self.show_trash else tr("show_trash", _lang)
        menu.append(trash_label, "desktopbg.toggle_trash")
        _my_curtain = next((cw for cw in self.app.curtain_windows if cw.monitor == self.monitor), None)
        kino_label = tr("kino_stop", _lang) if (_my_curtain and _my_curtain.progress > 0) else tr("kino_modus", _lang)
        menu.append(kino_label, "desktopbg.kino_modus")

        # Neu-Submenu (ganz unten)
        new_submenu = Gio.Menu()
        new_submenu.append(tr("new_folder", _lang), "desktopbg.new_folder")
        new_submenu.append(tr("new_document", _lang), "desktopbg.new_document")
        menu.append_submenu(tr("new", _lang), new_submenu)

        action_group = Gio.SimpleActionGroup()
        wp_action = Gio.SimpleAction.new("change_wallpaper", None)
        wp_action.connect("activate", self.on_change_wallpaper)
        action_group.add_action(wp_action)
        tr_action = Gio.SimpleAction.new("toggle_trash", None)
        tr_action.connect("activate", self.on_toggle_trash)
        action_group.add_action(tr_action)
        km_action = Gio.SimpleAction.new("kino_modus", None)
        km_action.connect("activate", lambda a, p: self.app.toggle_kino_modus(self))
        action_group.add_action(km_action)
        nf_action = Gio.SimpleAction.new("new_folder", None)
        nf_action.connect("activate", lambda a, p, cx=x, cy=y: self.on_new_folder(_lang, cx, cy))
        action_group.add_action(nf_action)
        nd_action = Gio.SimpleAction.new("new_document", None)
        nd_action.connect("activate", lambda a, p, cx=x, cy=y: self.on_new_document(_lang, cx, cy))
        action_group.add_action(nd_action)

        popover = Gtk.PopoverMenu()
        popover.set_menu_model(menu)
        popover.insert_action_group("desktopbg", action_group)
        popover.set_parent(self.event_catcher)
        popover.set_has_arrow(False)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    # ---- Cross-Monitor DragSession ----

    def _handle_cursor_entering_other(self, target_win, local_x, local_y):
        """Cursor wechselte zu einem anderen Monitor (von Source aus gesteuert).
        Entfernt alte Proxies, erstellt neue Proxies für alle Source-Icons auf target_win."""
        ds = self.app.drag_session
        old_target = ds.current_win
        drag_log(f"CURSOR_ENTERING_OTHER: {old_target.monitor_id if old_target else '?'} -> {target_win.monitor_id}")

        # Alle alten Proxies entfernen
        for proxy, _, _ in ds.proxy_widgets:
            try:
                proxy.unparent()
            except Exception:
                pass
        ds.proxy_widgets = []
        ds.proxy_widget = None

        ds.current_win = target_win

        # Alle Source-Icons verstecken
        for src_icon in ds.source_icons:
            src_icon.set_opacity(0.0)

        # Primäre Proxy-Position berechnen
        ps_x = ds.press_offset_x
        ps_y = ds.press_offset_y
        geo = target_win.monitor.get_geometry()
        grid = getattr(target_win, 'grid_size', GRID)
        primary_nx = int(local_x - ps_x)
        primary_ny = int(local_y - ps_y)
        if grid > 0:
            primary_nx = int(round(primary_nx / grid) * grid)
            primary_ny = int(round(primary_ny / grid) * grid)
        primary_nx = max(0, min(primary_nx, geo.width - 120))
        primary_ny = max(0, min(primary_ny, geo.height - 140))
        ds.proxy_x = primary_nx
        ds.proxy_y = primary_ny

        # Proxies für alle Source-Icons erstellen (relative Positionen beibehalten)
        primary = ds.source_icon
        for src_icon in ds.source_icons:
            rel_x = src_icon.x - primary.x
            rel_y = src_icon.y - primary.y
            px = max(0, min(primary_nx + rel_x, geo.width - 120))
            py = max(0, min(primary_ny + rel_y, geo.height - 140))
            try:
                proxy = target_win._make_single_proxy(src_icon, px, py)
                ds.proxy_widgets.append((proxy, rel_x, rel_y))
                if src_icon is primary:
                    ds.proxy_widget = proxy
            except Exception as e:
                drag_log(f"  proxy FEHLER für '{src_icon.spec['name']}': {e}")
        target_win.overlay.queue_draw()

    def on_drag_enter(self, controller, x, y):
        """Cursor betrat diesen Monitor. Cross-monitor-Logik wird von Source-Motion gesteuert."""
        ds = self.app.drag_session
        if ds.active:
            drag_log(f"DRAG_ENTER mon={self.monitor_id} from={ds.current_win.monitor_id if ds.current_win else None}")

    def _handle_cursor_entering(self, cursor_x, cursor_y):
        """Verarbeitet Cursor-Eintritt in diesen Monitor während DragSession.
        Versteckt Source-Icon, erstellt Proxy hier oder stellt Source wieder her."""
        ds = self.app.drag_session
        old_win = ds.current_win
        drag_log(f"ENTERING mon={self.monitor_id} from={old_win.monitor_id if old_win else None} cursor=({cursor_x:.0f},{cursor_y:.0f})")
        ds.current_win = self

        # Alten Zustand auf old_win aufräumen
        if old_win is ds.source_win:
            # Cursor verließ Source-Monitor → Source-Icon verstecken
            if ds.source_icon is not None:
                ds.source_icon.set_opacity(0.0)
        elif ds.proxy_widget is not None:
            # Cursor wechselte zwischen Nicht-Source-Monitoren → alten Proxy entfernen
            try:
                ds.proxy_widget.unparent()
            except Exception:
                pass
            ds.proxy_widget = None

        if self is ds.source_win:
            # Cursor kehrte zu Source-Monitor zurück → alle Icons wieder zeigen, Proxies löschen
            for src_icon in ds.source_icons:
                src_icon.set_opacity(1.0)
            for proxy, _, _ in ds.proxy_widgets:
                try:
                    proxy.unparent()
                except Exception:
                    pass
            ds.proxy_widgets = []
            ds.proxy_widget = None

    def _make_single_proxy(self, source_icon, x, y):
        """Erstellt ein einzelnes Proxy-Widget an Position (x,y) auf diesem Monitor."""
        proxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        proxy.add_css_class("desktop-icon")
        proxy.set_opacity(0.7)
        icon_size = getattr(self, 'icon_size', 64)
        icon_name = source_icon.spec['icon_name']
        if icon_name.startswith('/'):
            img = Gtk.Image.new_from_file(icon_name)
        else:
            img = Gtk.Image.new_from_icon_name(icon_name)
        img.set_pixel_size(icon_size)
        proxy.append(img)
        _lang = getattr(self.app, 'current_language', 'de')
        display_name = tr("trash", _lang) if source_icon.spec.get("is_trash") else source_icon.spec['name']
        lbl = Gtk.Label(label=display_name)
        lbl.set_width_chars(12)
        lbl.set_max_width_chars(12)
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        proxy.append(lbl)
        self.overlay.put(proxy, x, y)
        drag_log(f"PROXY created on {self.monitor_id} at ({x},{y}) for '{source_icon.spec['name']}'")
        return proxy

    def _commit_cross_monitor_drop(self):
        """Commit eines Cross-Monitor-Drops: Source-Widget löschen, neues Icon auf Ziel erstellen."""
        ds = self.app.drag_session
        if not ds.active or ds.current_win is None or ds.current_win is ds.source_win:
            ds.reset()
            return
        ds.active = False  # Verhindert, dass DRAG_ENTER-Events nach Release interferieren

        source_win = ds.source_win
        target_win = ds.current_win
        primary = ds.source_icon
        source_icons = list(ds.source_icons)  # Kopie vor reset
        proxy_widgets = list(ds.proxy_widgets)
        primary_drop_x = ds.proxy_x
        primary_drop_y = ds.proxy_y

        drag_log(f"COMMIT: {len(source_icons)} icon(s) {source_win.monitor_id}→{target_win.monitor_id} primary=({primary_drop_x},{primary_drop_y})")

        # Alle Proxies entfernen
        for proxy, _, _ in proxy_widgets:
            try:
                proxy.unparent()
            except Exception:
                pass

        src_state = source_win.global_state.setdefault("monitors", {}).setdefault(source_win.monitor_id, {})
        tgt_state = target_win.global_state.setdefault("monitors", {}).setdefault(target_win.monitor_id, {})
        geo = target_win.monitor.get_geometry()

        for src_icon in source_icons:
            # Relative Position zum primären Icon → Drop-Position
            rel_x = src_icon.x - primary.x
            rel_y = src_icon.y - primary.y
            drop_x = max(0, min(primary_drop_x + rel_x, geo.width - 120))
            drop_y = max(0, min(primary_drop_y + rel_y, geo.height - 140))

            icon_name = src_icon.spec['name']
            drag_log(f"  transferring '{icon_name}' to ({drop_x},{drop_y})")

            # Source-Icon-State bereinigen
            src_icon.set_opacity(1.0)
            src_icon._dragging = False
            src_icon._was_dragging = False
            src_icon._over_trash = False
            if src_icon._delete_overlay:
                src_icon._delete_overlay.set_visible(False)

            # Source-Widget entfernen
            try:
                src_icon.unparent()
            except Exception as e:
                drag_log(f"  unparent error: {e}")
            source_win.icons = [i for i in source_win.icons if i is not src_icon]

            # Source-State aktualisieren
            if "icons" in src_state:
                src_state["icons"] = [i for i in src_state["icons"] if i.get("name") != icon_name]

            # Neues Icon auf Ziel-Monitor erstellen
            new_icon = DesktopIcon(target_win, src_icon.spec, {"x": drop_x, "y": drop_y})
            new_icon._dragging = False
            if src_icon.selected:
                new_icon.set_selected(True)
            target_win.icons.append(new_icon)

            # Target-State aktualisieren
            entry = {
                "name": src_icon.spec["name"],
                "icon_name": src_icon.spec["icon_name"],
                "cmd": src_icon.spec["cmd"],
                "x": drop_x,
                "y": drop_y,
            }
            for field in ("desktop_file", "file_path", "is_trash"):
                if field in src_icon.spec:
                    entry[field] = src_icon.spec[field]
            tgt_icons = [i for i in tgt_state.setdefault("icons", []) if i.get("name") != icon_name]
            tgt_icons.append(entry)
            tgt_state["icons"] = tgt_icons

        source_win._dragged_icon = None
        save_state(target_win.global_state)
        ds.reset()
        # Selection-Highlights auf Source-Monitor sofort löschen
        source_win.selection_area.queue_draw()
        drag_log(f"COMMIT DONE: {len(source_icons)} icon(s) on {target_win.monitor_id}")

    def on_raw_event(self, controller, event):
        """Raw-Event-Handler: LMB-Release zuverlässig erkennen.
        Bei Cross-Monitor-Drag: hier findet der Commit statt (Wayland implicit grab
        sendet BUTTON_RELEASE immer an die Surface, die den PRESS empfangen hat)."""
        if event is None:
            return False
        if event.get_event_type() == Gdk.EventType.BUTTON_RELEASE:
            if event.get_button() == 1:  # LMB
                ds = self.app.drag_session
                drag_log(f"RAW BUTTON_RELEASE mon={self.monitor_id} ds.active={ds.active} current={ds.current_win.monitor_id if ds.current_win else None}")
                if ds.active:
                    # Backup: on_selection_released sollte bereits commitet haben.
                    # Falls nicht (z.B. GESTURE_RELEASED nicht gefeuert), hier als Fallback:
                    if ds.current_win is not None and ds.current_win is not ds.source_win:
                        drag_log(f"  → RAW fallback cross-monitor commit")
                        self._commit_cross_monitor_drop()
                    else:
                        if ds.source_icon is not None:
                            ds.source_icon.set_opacity(1.0)
                        ds.reset()
                self._dragged_icon = None
        return False  # Event nicht konsumieren

    def on_selection_pressed(self, gesture, n_press, x, y):
        """Start des Auswahl-Rechtecks - nur wenn auf Hintergrund geklickt."""
        geo = self.monitor.get_geometry()
        debug(f"selection_pressed on monitor {self.monitor_id} at geo=({geo.x}, {geo.y}, {geo.width}x{geo.height}), click=({x}, {y})")

        # Widget unter dem Cursor finden und Icon-Drag vorbereiten
        widget = self.overlay.pick(x, y, Gtk.PickFlags.DEFAULT)

        icon_clicked = None
        if widget and isinstance(widget.get_parent(), DesktopIcon):
            icon_clicked = widget.get_parent()
        elif widget and isinstance(widget, DesktopIcon):
            icon_clicked = widget
        else:
            # Bbox-Fallback
            for icon in self.icons:
                if (icon.x <= x <= icon.x + 100 and icon.y <= y <= icon.y + 100):
                    icon_clicked = icon
                    break

        if icon_clicked is not None:
            # Icon-Drag initialisieren (CAPTURE, daher zuverlässiger als on_pressed)
            self._dragged_icon = icon_clicked
            ps_x = x - icon_clicked.x
            ps_y = y - icon_clicked.y
            icon_clicked._press_start = (ps_x, ps_y)
            self.selection_active = False
            # DragSession initialisieren
            ds = self.app.drag_session
            ds.active = True
            ds.source_icon = icon_clicked
            # Alle zu ziehenden Icons erfassen (primäres + selektierte)
            if icon_clicked.selected:
                ds.source_icons = [ic for ic in self.icons if ic.selected]
            else:
                ds.source_icons = [icon_clicked]
            ds.source_win = self
            ds.current_win = self
            ds.proxy_widget = None
            ds.proxy_widgets = []
            ds.press_offset_x = ps_x
            ds.press_offset_y = ps_y
            drag_log(f"PRESS on '{icon_clicked.spec['name']}' mon={self.monitor_id} ps=({ps_x},{ps_y})")
            return Gdk.EVENT_PROPAGATE

        # Klick war auf Hintergrund - Auswahl starten (nicht sofort anzeigen)
        self.selection_active = True
        self.selection_start = (x, y)
        self.selection_current = (x, y)
        # Rechteck erst beim ersten Motion-Event anzeigen
        debug(f"selection ready at ({x}, {y})")

    def on_selection_released(self, gesture, n_press, x, y):
        """Ende des Auswahl-Rechtecks oder Icon-Drag."""
        ds = self.app.drag_session
        drag_log(f"GESTURE_RELEASED mon={self.monitor_id} ds.active={ds.active} source={ds.source_win.monitor_id if ds.source_win else None}")
        if ds.active and ds.source_win is self:
            # Release auf Source-Monitor (zuverlässigste Release-Erkennung via Wayland implicit grab)
            if ds.current_win is not self and ds.current_win is not None:
                # Cross-monitor drop: SOFORT committen bevor DRAG_ENTER-Events stören
                drag_log(f"  → cross-monitor release, commit to {ds.current_win.monitor_id} at ({ds.proxy_x},{ds.proxy_y})")
                self._commit_cross_monitor_drop()
            else:
                # Same-monitor: icon's on_released() übernimmt Position-Speichern
                ds.reset()
        # _dragging NICHT hier löschen – on_released() auf dem Icon muss es sehen
        self._dragged_icon = None
        if self.selection_active:
            debug(f"selection ended at ({x}, {y})")

            # Icons im Rechteck selektieren (wenn sichtbar war)
            if self.selection_visible and self.selection_start is not None:
                start_x, start_y = self.selection_start
                rect_x = min(start_x, x)
                rect_y = min(start_y, y)
                rect_w = abs(x - start_x)
                rect_h = abs(y - start_y)

                # Alle Icons deselektieren
                for icon in self.icons:
                    icon.set_selected(False)

                # Icons im Rechteck selektieren
                selected_count = 0
                for icon in self.icons:
                    # Icon Bounding Box
                    icon_x = icon.x
                    icon_y = icon.y
                    icon_w = 100
                    icon_h = 100

                    # Überschneidung prüfen
                    if (rect_x < icon_x + icon_w and
                        rect_x + rect_w > icon_x and
                        rect_y < icon_y + icon_h and
                        rect_y + rect_h > icon_y):
                        icon.set_selected(True)
                        selected_count += 1

                debug(f"selected {selected_count} icon(s)")
            else:
                # Einfacher Klick (kein Rechteck) -> Alle deselektieren
                debug(f"simple click on background, deselecting all")
                for icon in self.icons:
                    icon.set_selected(False)

            self.selection_active = False
            self.selection_visible = False
            self.selection_start = None
            self.selection_current = None
            self.selection_area.queue_draw()

    def on_selection_motion(self, controller, x, y):
        """Overlay-level motion: icon drag (volle Cursor-Verfolgung), proxy-drag oder Rubber-Band."""
        ds = self.app.drag_session

        # --- Aktiver Drag auf SOURCE-Monitor ---
        # Wayland implicit grab sendet ALLE Motion-Events an die Source-Surface.
        # Wir berechnen die globale Cursor-Position und ermitteln den Ziel-Monitor selbst.
        if ds.active and ds.source_win is self:
            primary = self._dragged_icon
            if primary is None or primary._being_transferred:
                return

            state = controller.get_current_event_state()
            lmb = bool(state & Gdk.ModifierType.BUTTON1_MASK) or ds.active
            drag_log(f"MOTION mon={self.monitor_id} icon='{primary.spec['name']}' lmb={lmb} ds.active={ds.active}")
            if not lmb:
                return

            ps_x, ps_y = primary._press_start

            # Threshold: erst nach CLICK_DRAG_THRESHOLD Pixel tatsächlich draggen
            press_overlay_x = primary.x + ps_x
            press_overlay_y = primary.y + ps_y
            dist = ((x - press_overlay_x) ** 2 + (y - press_overlay_y) ** 2) ** 0.5
            if not primary._dragging and dist < CLICK_DRAG_THRESHOLD:
                return

            primary._dragging = True
            primary._was_dragging = True

            # Globale Cursor-Position berechnen (nutzt lokale Overlay-Koordinaten)
            my_geo = self.monitor.get_geometry()
            global_x = my_geo.x + x
            global_y = my_geo.y + y

            # Prüfen ob Cursor auf anderem Monitor liegt
            other_win = None
            other_local_x, other_local_y = x, y
            for win in self.app.windows:
                if win is self:
                    continue
                wgeo = win.monitor.get_geometry()
                if (wgeo.x <= global_x < wgeo.x + wgeo.width and
                        wgeo.y <= global_y < wgeo.y + wgeo.height):
                    other_win = win
                    other_local_x = global_x - wgeo.x
                    other_local_y = global_y - wgeo.y
                    break

            if other_win is not None:
                # Cursor ist auf einem anderen Monitor → Proxies dort anzeigen/bewegen
                drag_log(f"CURSOR on {other_win.monitor_id} at ({other_local_x:.0f},{other_local_y:.0f})")
                if ds.current_win is not other_win:
                    # Wechsel zu neuem Monitor
                    self._handle_cursor_entering_other(other_win, other_local_x, other_local_y)
                else:
                    # Alle Proxies auf bekanntem Zielmonitor bewegen
                    if ds.proxy_widgets:
                        tgeo = other_win.monitor.get_geometry()
                        grid = getattr(other_win, 'grid_size', GRID)
                        nx = int(other_local_x - ps_x)
                        ny = int(other_local_y - ps_y)
                        if grid > 0:
                            nx = int(round(nx / grid) * grid)
                            ny = int(round(ny / grid) * grid)
                        nx = max(0, min(nx, tgeo.width - 120))
                        ny = max(0, min(ny, tgeo.height - 140))
                        for proxy, rel_x, rel_y in ds.proxy_widgets:
                            px = max(0, min(nx + rel_x, tgeo.width - 120))
                            py = max(0, min(ny + rel_y, tgeo.height - 140))
                            other_win.overlay.move(proxy, px, py)
                        ds.proxy_x = nx
                        ds.proxy_y = ny
                        drag_log(f"PROXY-MOVE on {other_win.monitor_id} pos=({nx},{ny})")
                # Alle Source-Icons unsichtbar halten
                for src_icon in ds.source_icons:
                    if src_icon.get_opacity() > 0:
                        src_icon.set_opacity(0.0)
                return
            else:
                # Cursor ist zurück auf Source-Monitor
                if ds.current_win is not self:
                    # Alle Proxies löschen, alle Source-Icons wieder zeigen
                    drag_log(f"CURSOR returned to source {self.monitor_id}")
                    for proxy, _, _ in ds.proxy_widgets:
                        try:
                            proxy.unparent()
                        except Exception:
                            pass
                    ds.proxy_widgets = []
                    ds.proxy_widget = None
                    ds.current_win = self
                    for src_icon in ds.source_icons:
                        src_icon.set_opacity(1.0)

            # --- Same-monitor Drag (Cursor auf Source) ---
            nx = int(x - ps_x)
            ny = int(y - ps_y)
            grid = getattr(self, 'grid_size', GRID)
            if grid > 0:
                nx = int(round(nx / grid) * grid)
                ny = int(round(ny / grid) * grid)

            geo = self.monitor.get_geometry()
            nx = max(0, min(nx, geo.width - 120))
            ny = max(0, min(ny, geo.height - 140))

            actual_dx = nx - primary.x
            actual_dy = ny - primary.y

            # Alle selektierten Icons mitbewegen
            if primary.selected:
                for ic in self.icons:
                    if ic.selected and ic is not primary:
                        ix = max(0, min(ic.x + actual_dx, geo.width - 120))
                        iy = max(0, min(ic.y + actual_dy, geo.height - 140))
                        self.overlay.move(ic, ix, iy)
                        ic.x, ic.y = ix, iy

            self.overlay.move(primary, nx, ny)
            primary.x, primary.y = nx, ny

            if any(ic.selected for ic in self.icons):
                self.selection_area.queue_draw()

            # Papierkorb-Hover-Feedback
            if self.trash_icon and not primary.spec.get("is_trash"):
                inset = 15
                tx = self.trash_icon.x + inset
                ty = self.trash_icon.y + inset
                tw = 100 - (inset * 2)
                th = 100 - (inset * 2)
                overlaps = (primary.x < tx + tw and primary.x + 100 > tx and
                            primary.y < ty + th and primary.y + 100 > ty)
                if overlaps and not primary._over_trash:
                    primary._over_trash = True
                    primary.set_opacity(0.5)
                    if not primary._delete_overlay:
                        primary._delete_overlay = Gtk.Label(label="✕")
                        primary._delete_overlay.add_css_class("delete-overlay")
                        primary.append(primary._delete_overlay)
                    primary._delete_overlay.set_visible(True)
                elif not overlaps and primary._over_trash:
                    primary._over_trash = False
                    primary.set_opacity(1.0)
                    if primary._delete_overlay:
                        primary._delete_overlay.set_visible(False)
            return

        # --- Rubber-Band-Selektion ---
        if not self.selection_active or self.selection_start is None:
            return

        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.BUTTON1_MASK:
            start_x, start_y = self.selection_start

            # Erst anzeigen wenn Mindest-Bewegung erreicht (wie CLICK_DRAG_THRESHOLD)
            if not self.selection_visible:
                distance = ((x - start_x) ** 2 + (y - start_y) ** 2) ** 0.5
                if distance < CLICK_DRAG_THRESHOLD:
                    return  # Noch nicht genug bewegt
                self.selection_visible = True
                debug(f"selection activated after {distance:.1f}px movement, start=({start_x}, {start_y}), current=({x}, {y})")

            # Aktuelle Position speichern - Zeichnung passiert in draw_selection_rectangle
            self.selection_current = (x, y)

            # Nur Redraw triggern - keine Position/Größe ändern (performanter)
            self.selection_area.queue_draw()

    def _update_selection_overlay(self):
        """Aktualisiert die Selection-Overlay-Zeichnung."""
        self.selection_area.queue_draw()

    def _draw_merged_selection(self, cr, r, g, b, border_radius):
        """Maskenbasiertes Merged-Selection: Fill + Border via A8-Cairo-Surfaces."""
        selected = [icon for icon in self.icons if icon.selected]
        if not selected:
            return

        fill_alpha   = 0.22
        border_alpha = 0.95
        border_w     = 2.0
        # fill_inflate=0 → Fill deckt exakt die Widget-Bounds ab (= Hover-Größe).
        # ring_inflate: Border-Ring knapp außerhalb des Widgets; bestimmt auch
        # wann benachbarte Icons verschmelzen (Lücke < 2*ring_inflate).
        fill_inflate = 0.0
        ring_inflate = border_w  # Ring liegt border_w px außerhalb der Widget-Grenze

        W = self.selection_area.get_width()
        H = self.selection_area.get_height()
        if W <= 0 or H <= 0:
            return

        def _rounded_rect(ctx, x, y, w, h, rad):
            rad = max(0.0, min(rad, w / 2.0, h / 2.0))
            if rad <= 0:
                ctx.rectangle(x, y, w, h)
                return
            ctx.new_sub_path()
            ctx.arc(x + w - rad, y + rad,       rad, -1.5708,  0.0)
            ctx.arc(x + w - rad, y + h - rad,   rad,  0.0,     1.5708)
            ctx.arc(x + rad,     y + h - rad,   rad,  1.5708,  3.1416)
            ctx.arc(x + rad,     y + rad,       rad,  3.1416,  4.7124)
            ctx.close_path()

        # Echte Widget-Bounds im Koordinatensystem der selection_area ermitteln
        rects = []
        for icon in selected:
            ok, rect = icon.compute_bounds(self.selection_area)
            if not ok:
                continue
            rects.append((rect.origin.x, rect.origin.y, rect.size.width, rect.size.height))
        if not rects:
            return

        # Fill-Maske: exakte Widget-Bounds (entspricht Hover-Größe)
        outer = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
        oc = cairo.Context(outer)
        oc.set_operator(cairo.OPERATOR_SOURCE)
        oc.set_source_rgba(1, 1, 1, 1)
        for x, y, w, h in rects:
            _rounded_rect(oc, x, y, w, h, border_radius)
            oc.fill()

        # Ring-Maske: ring_inflate px außerhalb Widget minus exakte Widget-Bounds
        ring = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
        rc = cairo.Context(ring)
        rc.set_operator(cairo.OPERATOR_SOURCE)
        rc.set_source_rgba(1, 1, 1, 1)
        for x, y, w, h in rects:
            _rounded_rect(rc, x - ring_inflate, y - ring_inflate,
                          w + 2 * ring_inflate, h + 2 * ring_inflate, border_radius)
            rc.fill()
        rc.set_operator(cairo.OPERATOR_CLEAR)
        for x, y, w, h in rects:
            _rounded_rect(rc, x, y, w, h, border_radius)
            rc.fill()

        # Fill zeichnen
        cr.save()
        cr.set_source_rgba(r, g, b, fill_alpha)
        cr.mask_surface(outer, 0, 0)
        cr.restore()

        # Border zeichnen
        cr.save()
        cr.set_source_rgba(r, g, b, border_alpha)
        cr.mask_surface(ring, 0, 0)
        cr.restore()

    def draw_selection_rectangle(self, area, cr, width, height):
        """Zeichnet merged Icon-Selection-Borders und das Rubber-Band-Rechteck."""
        has_selection = any(icon.selected for icon in self.icons)
        if not has_selection and not self.selection_visible:
            return

        # Settings einmal lesen
        settings = parse_quickshell_settings()
        accent_color = settings["accentColor"]
        border_radius = settings["borderRadius"]
        try:
            if accent_color.startswith("#"):
                hex_color = accent_color[1:]
                r = int(hex_color[0:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0
            else:
                r, g, b = 1.0, 0.4, 0.18
        except Exception:
            r, g, b = 1.0, 0.4, 0.18

        # 1. Merged Selection-Borders für selektierte Icons
        if has_selection:
            self._draw_merged_selection(cr, r, g, b, border_radius)

        # 2. Rubber-Band Auswahl-Rechteck
        if self.selection_visible and self.selection_start is not None and self.selection_current is not None:
            start_x, start_y = self.selection_start
            current_x, current_y = self.selection_current
            rect_x = min(start_x, current_x)
            rect_y = min(start_y, current_y)
            rect_w = abs(current_x - start_x)
            rect_h = abs(current_y - start_y)
            if rect_w > 0 and rect_h > 0:
                if border_radius > 0:
                    radius = min(border_radius, rect_w / 2, rect_h / 2)
                    degrees = 3.14159 / 180.0
                    cr.new_sub_path()
                    cr.arc(rect_x + rect_w - radius, rect_y + radius, radius, -90 * degrees, 0 * degrees)
                    cr.arc(rect_x + rect_w - radius, rect_y + rect_h - radius, radius, 0 * degrees, 90 * degrees)
                    cr.arc(rect_x + radius, rect_y + rect_h - radius, radius, 90 * degrees, 180 * degrees)
                    cr.arc(rect_x + radius, rect_y + radius, radius, 180 * degrees, 270 * degrees)
                    cr.close_path()
                else:
                    cr.rectangle(rect_x, rect_y, rect_w, rect_h)
                cr.set_source_rgba(r, g, b, 0.2)
                cr.fill_preserve()
                cr.set_source_rgba(r, g, b, 0.8)
                cr.set_line_width(2)
                cr.stroke()

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handler für Tastatur-Events (DEL-Taste)."""
        # DEL oder BACKSPACE für Löschen
        if keyval == 65535 or keyval == 65288:  # DEL oder Backspace
            selected_icons = [icon for icon in self.icons if icon.selected]
            if selected_icons:
                debug(f"deleting {len(selected_icons)} selected icon(s)")
                trashed_icons = []
                for icon in selected_icons:
                    # Papierkorb darf nicht gelöscht werden
                    if icon.spec.get("is_trash"):
                        debug(f"skipping trash icon")
                        continue

                    # Datei in Papierkorb verschieben
                    try:
                        if "desktop_file" in icon.spec:
                            filepath = Path(icon.spec["desktop_file"])
                        elif "file_path" in icon.spec:
                            filepath = Path(icon.spec["file_path"])
                        else:
                            debug(f"cannot delete: no file path for {icon.spec['name']}")
                            continue

                        if filepath.exists():
                            file = Gio.File.new_for_path(str(filepath))
                            file.trash(None)
                            debug(f"moved to trash: {filepath}")
                            trashed_icons.append(icon)
                    except Exception as e:
                        debug(f"failed to trash: {e}", file=sys.stderr)

                # Sofort aus UI/Selection entfernen, dann konsistent neu laden
                if trashed_icons:
                    self.remove_icons_by_refs(trashed_icons)
                GLib.timeout_add(500, self.reload_icons)
                return True  # Event behandelt
        return False  # Event nicht behandelt

    def on_change_wallpaper(self, action, param):
        """Öffnet Wallpaper-Settings (quickshell Integration)."""
        try:
            # Umgebung vorbereiten
            env = os.environ.copy()
            # LD_PRELOAD entfernen (kann Probleme verursachen)
            env.pop("LD_PRELOAD", None)

            # Quickshell mit global binding triggern
            # Verwende "show-settings" statt "toggle-settings" um immer zu öffnen
            result = subprocess.run(
                ["windoesnot-hyprctl", "dispatch", "global", "quickshell:show-settings"],
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            if result.returncode == 0:
                debug(f"opened quickshell settings")
            else:
                debug(f"failed to open settings: {result.stderr.strip()}")
        except Exception as e:
            debug(f"failed to open wallpaper settings: {e}", file=sys.stderr)

    def on_toggle_trash(self, action, param):
        """Zeigt/Versteckt Papierkorb."""
        self.show_trash = not self.show_trash
        self.reload_icons()

    def _unique_desktop_path(self, base_name, suffix=""):
        """Gibt einen freien Pfad im Desktop-Ordner zurück (z.B. 'Neuer Ordner 2')."""
        path = DESKTOP_DIR / (base_name + suffix)
        if not path.exists():
            return path
        n = 2
        while True:
            path = DESKTOP_DIR / (f"{base_name} {n}" + suffix)
            if not path.exists():
                return path
            n += 1

    def on_new_folder(self, lang="de", cx=50, cy=50):
        """Erstellt einen neuen Ordner auf dem Desktop und startet Inline-Rename."""
        name = tr("new_folder_name", lang)
        path = self._unique_desktop_path(name)
        try:
            path.mkdir()
        except Exception as e:
            print(f"failed to create folder: {e}", file=sys.stderr)
            return
        grid = getattr(self, 'grid_size', GRID)
        snap_x = int(round(cx / grid) * grid) if grid > 0 else int(cx)
        snap_y = int(round(cy / grid) * grid) if grid > 0 else int(cy)
        spec = {"name": path.name, "icon_name": "folder",
                "cmd": ["xdg-open", str(path)], "file_path": str(path)}
        icon = DesktopIcon(self, spec, pos={"x": snap_x, "y": snap_y})
        self.icons.append(icon)
        self.save_monitor_state()

    def on_new_document(self, lang="de", cx=50, cy=50):
        """Erstellt ein neues leeres Dokument auf dem Desktop und startet Inline-Rename."""
        name = tr("new_document_name", lang)
        path = self._unique_desktop_path(name, ".txt")
        try:
            path.touch()
        except Exception as e:
            print(f"failed to create document: {e}", file=sys.stderr)
            return
        grid = getattr(self, 'grid_size', GRID)
        snap_x = int(round(cx / grid) * grid) if grid > 0 else int(cx)
        snap_y = int(round(cy / grid) * grid) if grid > 0 else int(cy)
        spec = {"name": path.name, "icon_name": get_icon_for_file(path),
                "cmd": ["xdg-open", str(path)], "file_path": str(path)}
        icon = DesktopIcon(self, spec, pos={"x": snap_x, "y": snap_y})
        self.icons.append(icon)
        self.save_monitor_state()

    def is_trash_full(self):
        """Prüft ob Papierkorb Dateien enthält."""
        trash_dir = Path.home() / ".local/share/Trash/files"
        if trash_dir.exists():
            return any(trash_dir.iterdir())
        return False

    def remove_all_icons_by_name(self, icon_name):
        """Entfernt ALLE Icons mit diesem Namen von DIESEM Monitor (auch Ghosts)."""
        to_remove = [i for i in self.icons if i.spec['name'] == icon_name]
        if to_remove:
            debug(f"Found {len(to_remove)} icon(s) named '{icon_name}' to remove on monitor {self.monitor_id}")
            for ic in to_remove:
                debug(f"  Removing '{icon_name}' at ({ic.x}, {ic.y}), being_transferred={ic._being_transferred}")
                # WICHTIG: Zuerst Widget komplett verstecken und deaktivieren
                ic.set_visible(False)
                ic.set_opacity(0.0)
                ic.destroy_completely()
                # Dann aus Overlay entfernen
                try:
                    self.overlay.remove(ic)
                except Exception as e:
                    debug(f"  Warning: Could not remove from overlay: {e}")
                # Und unparent
                try:
                    ic.unparent()
                except Exception as e:
                    debug(f"  Warning: Could not unparent: {e}")

            # WICHTIG: Aus Liste entfernen NACH dem Loop (um Iteration nicht zu stören)
            self.icons = [i for i in self.icons if i.spec['name'] != icon_name]
            debug(f"  After cleanup: {len(self.icons)} icons remain on monitor {self.monitor_id}")

    def check_collision(self, moving_icon, new_x, new_y):
        """Prüft, ob ein Icon an der neuen Position mit anderen Icons kollidieren würde."""
        # Icon-Größe schätzen (64px Icon + Padding + Label)
        icon_width = 100
        icon_height = 100

        for icon in self.icons:
            if icon is moving_icon:
                continue

            # Bounding-Box-Kollision prüfen
            if (abs(new_x - icon.x) < icon_width and
                abs(new_y - icon.y) < icon_height):
                return True
        return False

    def update_icon_sizes(self, new_size):
        """Aktualisiert die Icon-Größe aller Desktop-Icons live."""
        self.icon_size = new_size
        for icon in self.icons:
            if hasattr(icon, 'icon_image'):
                icon.icon_image.set_pixel_size(new_size)
        # Auch Papierkorb-Icon aktualisieren
        if self.trash_icon and hasattr(self.trash_icon, 'icon_image'):
            self.trash_icon.icon_image.set_pixel_size(new_size)
        debug(f"Updated icon sizes to {new_size}px on {self.monitor_id}")

    def update_grid_size(self, new_grid):
        """Aktualisiert die Grid-Größe (wird beim nächsten Drag verwendet)."""
        self.grid_size = new_grid
        debug(f"Updated grid size to {new_grid}px on {self.monitor_id}")

    def update_trash_visibility(self, show_trash):
        """Zeigt oder versteckt den Papierkorb."""
        self.show_trash = show_trash
        if self.trash_icon:
            if show_trash:
                self.trash_icon.set_visible(True)
            else:
                self.trash_icon.set_visible(False)
        debug(f"Trash visibility set to {show_trash} on {self.monitor_id}")

    def update_label_lines(self, new_lines):
        """Aktualisiert die maximale Anzahl Zeilen für Labels."""
        self.label_lines = new_lines
        for icon in self.icons:
            if hasattr(icon, 'icon_label'):
                icon.icon_label.set_lines(new_lines)
        if self.trash_icon and hasattr(self.trash_icon, 'icon_label'):
            self.trash_icon.icon_label.set_lines(new_lines)
        debug(f"Updated label lines to {new_lines} on {self.monitor_id}")

    def save_monitor_state(self):
        self.global_state.setdefault("monitors", {})[self.monitor_id] = {
            "icons": [icon.to_dict() for icon in self.icons]
        }
        save_state(self.global_state)

    def _dismiss_context_menu(self):
        """Entfernt das aktive Kontextmenü-Widget aus dem Overlay."""
        if self._context_menu is not None:
            try:
                self.overlay.remove(self._context_menu)
            except Exception:
                pass
            self._context_menu = None

    def teardown(self):
        """Gibt alle Ressourcen dieses MonitorWindows frei."""
        # FileMonitor stoppen
        if hasattr(self, 'file_monitor') and self.file_monitor:
            try:
                self.file_monitor.cancel()
            except Exception:
                pass
            self.file_monitor = None

        # Polling-Timeout stoppen
        if hasattr(self, '_poll_source') and self._poll_source:
            try:
                GLib.source_remove(self._poll_source)
            except Exception:
                pass
            self._poll_source = None

        # Icons leeren
        self.icons.clear()

        # Fenster schließen
        try:
            self.win.destroy()
        except Exception:
            pass


class DragSession:
    """App-weite Drag-Session: kein Widget-Transfer zwischen Surfaces während des Drags.
    Proxy-Widgets auf Zielmonitor werden erst bei BUTTON_RELEASE durch echte Icons ersetzt."""
    def __init__(self):
        self.active = False
        self.source_icon = None    # Primäres DesktopIcon (angeklicktes Icon)
        self.source_icons = []     # Alle Icons die bewegt werden (primary + selected)
        self.source_win = None     # MonitorWindow des Drag-Starts
        self.current_win = None    # MonitorWindow wo Cursor gerade ist
        self.proxy_widget = None   # Primärer Proxy (Gtk.Box) auf current_win
        self.proxy_widgets = []    # Alle Proxies: list of (widget, rel_x, rel_y)
        self.press_offset_x = 0   # Cursor-Offset vom primären Icon-Ursprung (x)
        self.press_offset_y = 0   # Cursor-Offset vom primären Icon-Ursprung (y)
        self.proxy_x = 0          # Aktuelle primäre Proxy-Position x
        self.proxy_y = 0          # Aktuelle primäre Proxy-Position y

    def reset(self):
        self.__init__()


class CurtainWindow:
    """Kino-Modus: Legt einen schwarzen Vorhang über einen Monitor."""

    ANIM_CLOSE_MS = 500   # Vorhang fällt: ms für vollständige Animation
    ANIM_OPEN_MS  = 300   # Vorhang hebt sich: ms für vollständige Animation
    ANIM_STEP_MS  = 16    # ~60 fps

    def __init__(self, app, monitor):
        self.app = app
        self.monitor = monitor
        self.progress = 0.0    # 0.0 = offen, 1.0 = vollständig geschlossen
        self._anim_source = None

        self.win = Gtk.Window(application=app)
        self.win.set_decorated(False)

        Gtk4LayerShell.init_for_window(self.win)
        Gtk4LayerShell.set_layer(self.win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_monitor(self.win, monitor)
        for edge in [Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.BOTTOM,
                     Gtk4LayerShell.Edge.LEFT, Gtk4LayerShell.Edge.RIGHT]:
            Gtk4LayerShell.set_anchor(self.win, edge, True)
        Gtk4LayerShell.set_keyboard_mode(self.win, Gtk4LayerShell.KeyboardMode.NONE)
        Gtk4LayerShell.set_namespace(self.win, "hyprdesk-curtain")

        self.win.add_css_class("transparent-window")

        self.drawing = Gtk.DrawingArea()
        self.drawing.set_draw_func(self._draw)
        self.drawing.set_can_target(True)
        self.win.set_child(self.drawing)

        # Linksklick → Kino-Modus beenden
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("released", lambda g, n, x, y: self.hide_curtain())
        self.drawing.add_controller(click)

        # Rechtsklick → Menü mit "Beenden"-Option
        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect("released", self._on_right_click)
        self.drawing.add_controller(right_click)

        self.win.set_visible(False)

    def _draw(self, area, cr, width, height):
        if self.progress <= 0:
            return
        curtain_h = int(height * self.progress)
        cr.set_source_rgba(0, 0, 0, 1.0)
        cr.rectangle(0, 0, width, curtain_h)
        cr.fill()

    def _on_right_click(self, gesture, n_press, x, y):
        _lang = getattr(self.app, 'current_language', 'de')
        menu = Gio.Menu()
        menu.append(tr("kino_stop", _lang), "curtain.exit_kino")

        action_group = Gio.SimpleActionGroup()
        exit_action = Gio.SimpleAction.new("exit_kino", None)
        exit_action.connect("activate", lambda a, p: self.hide_curtain())
        action_group.add_action(exit_action)

        popover = Gtk.PopoverMenu()
        popover.set_menu_model(menu)
        popover.insert_action_group("curtain", action_group)
        popover.set_parent(self.drawing)
        popover.set_has_arrow(False)
        rect = Gdk.Rectangle()
        rect.x = int(x); rect.y = int(y)
        rect.width = 1;  rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    def show_curtain(self):
        """Vorhang fällt – Kino-Modus aktivieren."""
        self._stop_anim()
        self.win.set_visible(True)
        step = self.ANIM_STEP_MS / self.ANIM_CLOSE_MS

        def _tick():
            self.progress = min(1.0, self.progress + step)
            self.drawing.queue_draw()
            if self.progress >= 1.0:
                self._anim_source = None
                return False
            return True

        self._anim_source = GLib.timeout_add(self.ANIM_STEP_MS, _tick)

    def hide_curtain(self):
        """Vorhang hebt sich – Kino-Modus beenden."""
        self._stop_anim()
        step = self.ANIM_STEP_MS / self.ANIM_OPEN_MS

        def _tick():
            self.progress = max(0.0, self.progress - step)
            self.drawing.queue_draw()
            if self.progress <= 0.0:
                self.win.set_visible(False)
                self._anim_source = None
                return False
            return True

        self._anim_source = GLib.timeout_add(self.ANIM_STEP_MS, _tick)

    def _stop_anim(self):
        if self._anim_source is not None:
            GLib.source_remove(self._anim_source)
            self._anim_source = None

    def destroy(self):
        self._stop_anim()
        self.win.destroy()


class HyprDeskApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.benni.hyprdesk")
        self.global_state = load_state()
        self.windows = []
        self.primary_monitor_id = None
        self.drag_session = DragSession()  # App-weite Drag-Session (ersetzt lmb_held/transfer_in_progress)
        self.curtain_windows = []
        self.settings_monitor = None
        # Default settings (werden beim Start überschrieben)
        self.current_icon_size = 64
        self.current_grid_size = 16
        self.current_show_trash = True
        self.current_label_lines = 2
        self.current_language = "de"
        self.current_dark_mode = True

    def setup_settings_monitor(self):
        """Überwacht die Quickshell Settings-Datei auf Änderungen."""
        if not QUICKSHELL_SETTINGS.exists():
            return

        settings_file = Gio.File.new_for_path(str(QUICKSHELL_SETTINGS))
        self.settings_monitor = settings_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.settings_monitor.connect("changed", self.on_settings_file_changed)
        debug(f"Settings monitor started for {QUICKSHELL_SETTINGS}")

    def on_settings_file_changed(self, monitor, file, other_file, event_type):
        """Callback wenn Settings-Datei geändert wird."""
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            settings = parse_quickshell_settings()

            # Icon Size
            new_icon_size = settings["desktopIconSize"]
            if new_icon_size != self.current_icon_size:
                debug(f"Icon size changed: {self.current_icon_size} -> {new_icon_size}")
                self.current_icon_size = new_icon_size
                for win in self.windows:
                    win.update_icon_sizes(new_icon_size)

            # Grid Size
            new_grid_size = settings["desktopGridSize"]
            if new_grid_size != self.current_grid_size:
                debug(f"Grid size changed: {self.current_grid_size} -> {new_grid_size}")
                self.current_grid_size = new_grid_size
                for win in self.windows:
                    win.update_grid_size(new_grid_size)

            # Show Trash
            new_show_trash = settings["desktopShowTrash"]
            if new_show_trash != self.current_show_trash:
                debug(f"Show trash changed: {self.current_show_trash} -> {new_show_trash}")
                self.current_show_trash = new_show_trash
                for win in self.windows:
                    win.update_trash_visibility(new_show_trash)

            # Label Lines
            new_label_lines = settings["desktopLabelLines"]
            if new_label_lines != self.current_label_lines:
                debug(f"Label lines changed: {self.current_label_lines} -> {new_label_lines}")
                self.current_label_lines = new_label_lines
                for win in self.windows:
                    win.update_label_lines(new_label_lines)

            # UI-Sprache
            new_language = settings["uiLanguage"]
            if new_language != self.current_language:
                debug(f"Language changed: {self.current_language} -> {new_language}")
                self.current_language = new_language
                for win in self.windows:
                    for icon in win.icons:
                        icon.update_language(new_language)
                update_swaync_language(new_language)

            # Dark/Light Mode → swaync CSS neu generieren
            new_dark_mode = settings["darkMode"]
            if new_dark_mode != self.current_dark_mode:
                debug(f"Dark mode changed: {self.current_dark_mode} -> {new_dark_mode}")
                self.current_dark_mode = new_dark_mode
                update_swaync_css(settings["accentColor"], settings["borderRadius"], new_dark_mode)

    def on_monitors_changed(self, list_model, position, removed, added):
        """Wird aufgerufen wenn Monitore verbunden oder getrennt werden."""
        debug(f"monitors-changed: position={position}, removed={removed}, added={added}")
        # Debounce: 1 Sekunde warten bis der Compositor fertig neu konfiguriert hat
        if getattr(self, '_monitor_change_timer', None) is not None:
            GLib.source_remove(self._monitor_change_timer)
        self._monitor_change_timer = GLib.timeout_add(1000, self._reinitialize_monitors)

    def _reinitialize_monitors(self):
        """Alle MonitorWindows neu erstellen nach Monitor-Topologie-Änderung."""
        debug("reinitializing all monitors after topology change")
        self._monitor_change_timer = None

        # State sichern bevor Fenster zerstört werden
        save_state(self.global_state)

        # Theme-Monitor zurücksetzen (wird vom ersten neuen MonitorWindow neu eingerichtet)
        if hasattr(self, '_theme_monitor'):
            try:
                self._theme_monitor.cancel()
            except Exception:
                pass
            del self._theme_monitor
        if hasattr(self, '_theme_monitor_setup'):
            del self._theme_monitor_setup

        # Alle vorhandenen Fenster abbauen
        for window in self.windows:
            window.teardown()
        self.windows.clear()
        self.drag_session.reset()

        # Curtain-Windows abbauen
        for cw in self.curtain_windows:
            cw.destroy()
        self.curtain_windows.clear()

        # Neue Monitore ermitteln
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        n = monitors.get_n_items()
        if n == 0:
            debug("no monitors found after topology change")
            return False

        # State neu laden
        self.global_state = load_state()

        # Aktive Monitor-IDs bestimmen und veraltete State-Einträge bereinigen
        active_monitor_ids = set()
        for i in range(n):
            m = monitors.get_item(i)
            active_monitor_ids.add(get_monitor_connector_name(m))
        # Disconnected outputs retain their icon positions for reconnection.

        # Primärmonitor-ID stabil setzen (erster Monitor der aktuellen Topologie)
        if n > 0:
            self.primary_monitor_id = get_monitor_connector_name(monitors.get_item(0))

        # Neue MonitorWindows erstellen
        for i in range(n):
            m = monitors.get_item(i)
            self.windows.append(MonitorWindow(self, m, self.global_state))

        # Neue CurtainWindows erstellen
        for i in range(n):
            m = monitors.get_item(i)
            self.curtain_windows.append(CurtainWindow(self, m))

        debug(f"monitor reinitialization complete: {len(self.windows)} windows")
        return False  # Timeout nicht wiederholen

    def migrate_old_monitor_ids(self, monitors, n):
        """Migriert alte Geometrie-basierte Monitor-IDs zu Connector-Namen."""
        debug(f"migrate_old_monitor_ids called with {n} monitors")

        saved_monitors = self.global_state.get("monitors", {})
        if not saved_monitors:
            debug("No saved monitors, skipping migration")
            return

        debug(f"Saved monitor IDs: {list(saved_monitors.keys())}")

        # Prüfen ob Migration nötig ist (alte IDs enthalten Unterstriche mit Zahlen)
        old_style_ids = [mid for mid in saved_monitors.keys() if "_" in mid and mid.count("_") == 3]
        if not old_style_ids:
            debug("No old-style monitor IDs found, skipping migration")
            return

        debug(f"🔄 MIGRATION: Found {len(old_style_ids)} old-style monitor IDs: {old_style_ids}")

        # Mapping von alter Geometrie zu neuem Connector-Namen erstellen
        # Verwende windoesnot-hyprctl um sicherzustellen dass wir dieselbe Geometrie wie im State haben
        try:
            result = subprocess.run(
                ["windoesnot-hyprctl", "monitors", "-j"],
                capture_output=True,
                text=True,
                check=True
            )
            monitors_data = json.loads(result.stdout)

            migration_map = {}
            for mon in monitors_data:
                # Alte ID: x_y_height_width
                old_id = f"{mon['x']}_{mon['y']}_{mon['height']}_{mon['width']}"
                new_id = mon['name']
                if old_id != new_id:
                    migration_map[old_id] = new_id
                    debug(f"  {old_id} -> {new_id}")
        except Exception as e:
            debug(f"  Error getting monitor info: {e}")
            migration_map = {}

        # Migration durchführen
        if migration_map:
            new_monitors = {}
            for old_id, config in saved_monitors.items():
                if old_id in migration_map:
                    new_id = migration_map[old_id]
                    debug(f"  Migrating config from {old_id} to {new_id}")
                    # Wenn neue ID bereits existiert, Icons mergen
                    if new_id in new_monitors:
                        debug(f"    Merging with existing config")
                        existing_icon_names = {icon["name"] for icon in new_monitors[new_id].get("icons", [])}
                        for icon in config.get("icons", []):
                            if icon["name"] not in existing_icon_names:
                                new_monitors[new_id].setdefault("icons", []).append(icon)
                    else:
                        new_monitors[new_id] = config
                else:
                    # Behalte neue IDs wie sie sind
                    new_monitors[old_id] = config

            self.global_state["monitors"] = new_monitors
            save_state(self.global_state)
            debug(f"✅ Migration complete")

    def toggle_kino_modus(self, source_win):
        """Kino-Modus für einen bestimmten Monitor ein-/ausschalten."""
        curtain = next((cw for cw in self.curtain_windows if cw.monitor == source_win.monitor), None)
        if curtain is None:
            return
        if curtain.progress > 0 or curtain.win.get_visible():
            curtain.hide_curtain()
        else:
            curtain.show_curtain()

    def do_activate(self, *args):
        # Icon labels and geometry use the saved settings from their first frame.
        settings = parse_quickshell_settings()
        self.current_icon_size = settings["desktopIconSize"]
        self.current_grid_size = settings["desktopGridSize"]
        self.current_show_trash = settings["desktopShowTrash"]
        self.current_label_lines = settings["desktopLabelLines"]
        self.current_language = settings["uiLanguage"]
        self.current_dark_mode = settings["darkMode"]
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        n = monitors.get_n_items()
        if n == 0:
            debug("no monitors found", file=sys.stderr)
            return
        debug("initializing Gtk4LayerShell...")

        # CLEANUP: Sammle aktive Monitor-IDs (Connector-Namen)
        active_monitor_ids = set()
        for i in range(n):
            m = monitors.get_item(i)
            monitor_id = get_monitor_connector_name(m)
            active_monitor_ids.add(monitor_id)

        debug(f"Active monitors: {active_monitor_ids}")

        # MIGRATION: Konvertiere alte Geometrie-basierte IDs zu Connector-Namen
        self.migrate_old_monitor_ids(monitors, n)

        # Keep disconnected monitor state, including during a remote session.

        # Primärmonitor-ID stabil setzen (erster Monitor der aktuellen Topologie)
        self.primary_monitor_id = get_monitor_connector_name(monitors.get_item(0))

        # Monitore initialisieren
        for i in range(n):
            m = monitors.get_item(i)
            self.windows.append(MonitorWindow(self, m, self.global_state))

        # CurtainWindows für Kino-Modus
        for i in range(n):
            m = monitors.get_item(i)
            self.curtain_windows.append(CurtainWindow(self, m))

        # Monitor-Topologie-Änderungen überwachen (Monitor trennen/verbinden)
        # Referenz auf self halten damit GC das Objekt nicht freigibt
        self._monitors_model = monitors
        self._monitors_model.connect("items-changed", self.on_monitors_changed)

        # Settings-Datei überwachen für Live-Updates
        self.setup_settings_monitor()
        # Initiale Settings speichern
        settings = parse_quickshell_settings()
        self.current_icon_size = settings["desktopIconSize"]
        self.current_grid_size = settings["desktopGridSize"]
        self.current_show_trash = settings["desktopShowTrash"]
        self.current_label_lines = settings["desktopLabelLines"]
        self.current_language = settings["uiLanguage"]
        self.current_dark_mode = settings["darkMode"]
        # Initiales swaync CSS + Sprache setzen
        update_swaync_css(settings["accentColor"], settings["borderRadius"], settings["darkMode"])
        update_swaync_language(settings["uiLanguage"])

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = HyprDeskApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()
