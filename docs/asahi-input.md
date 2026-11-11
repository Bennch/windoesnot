# MacBook-Eingabe in WinDoesNot (Asahi)

Dieses Profil gilt nur für die Asahi-Variante. Es ordnet macOS-Funktionen den
WinDoesNot-Anwendungen zu. Die gemeinsame x86-64-Variante behält ihre Belegung.

| Bedienung | Entsprechung in WinDoesNot |
| --- | --- |
| Ein Finger tippen oder klicken | Linksklick |
| Zwei Finger tippen oder klicken | Rechtsklick, unabhängig von der Klickposition |
| Zwei Finger bewegen | Natürliches Scrollen in der Anwendung |
| Zwei Finger zusammenziehen / spreizen | App-eigenes Pinch-Zoom, z. B. Firefox; wird nicht global abgefangen |
| Zwei Finger horizontal bewegen | Horizontales Scrollen bzw. Zurück/Vor in unterstützenden Apps; Firefox enthält entsprechende History-Aktionen |
| Drei Finger bewegen | Ziehen/Markieren über libinput; Fenster am Fenstertitel ziehen |
| Vier Finger links / rechts | Arbeitsfläche wechseln |
| Vier Finger hoch | WinDoesNot-Fensterübersicht (Mission Control) |
| Vier Finger runter | Fensterübersicht gefiltert auf die aktuelle App (App Exposé); Escape schließt |
| Vier Finger zusammenziehen (Daumen + drei Finger) | App-Menü mit allen Anwendungen (Launchpad) |
| Vier Finger spreizen | Desktop anzeigen / vorherige Fenster zurückholen |
| Control+C im Terminal | Markierten Text kopieren; ohne Markierung laufenden Befehl abbrechen |
| Control+V im Terminal | Zwischenablage einfügen, ohne Shift |

Drei-Finger-Wischgesten für Arbeitsflächen sind im Asahi-Profil aufgehoben,
damit sie nicht mit dem Drei-Finger-Ziehen konkurrieren. Stattdessen vier Finger
für die Navigation verwenden. Das normale Tap-and-drag bleibt ebenfalls verfügbar.

App-Gesten werden durchgereicht, nicht in globale Tastenkürzel umgewandelt:
Rotation, Smart-Zoom per Doppeltippen und weitere app-spezifische Gesten hängen
von der Anwendung ab. Force Touch, druckabhängige Vorschau und haptisches Feedback
wurden nicht implementiert; dafür ist passende Treiber-/App-Unterstützung nötig.
Nicht alle macOS-Spezialfunktionen werden dadurch automatisch nachgebildet.

## Implementierung und Prüfung

- `desktop/config/hypr/lua/init.lua`: Apple-Geräteerkennung, Trackpad-Defaults,
  Vier-Finger-Gesten; explizite Trackpad-Werte im Benutzer-State gewinnen.
- `desktop/bin/windoesnot-gesture`: übersetzt Gesten in lokale IPC-Aufrufe.
- Hauptshell: passiver IPC-Endpunkt `desktop-gestures` für Apps/Desktop.
- Overview: `appWindows`-IPC und Filter nach Fensterklasse, auch im Scrolling-Layout.
- `desktop/defaults/asahi/config/ghostty/asahi-keybindings.conf` und Initialisierung:
  Clipboard-Kürzel für neue Asahi-Konfigurationen; vorhandene Nutzerdateien erhalten.
- Host am 2026-11-11 aktiviert, Hauptshell/Overview-IPC geprüft, keine Hyprland-
  Konfigurationsfehler. Backup: `~/Backups/windoesnot-release/20261111-180802-asahi-gestures`.
- Hauptshell und Overview laden in isolierter Wayland-Sitzung. Neue Asahi- und
  x86-64-Initialisierung sowie Erhalt bestehender Ghostty-Dateien geprüft.
- Physische Gesten einschließlich Dreifinger-Ziehen und Vierfinger-Pinch müssen
  auf dem Trackpad noch vom Benutzer bestätigt werden. Keine neuen Images gebaut.

Quellen: [Hyprland-Gesten](https://wiki.hypr.land/configuring/core/binds/gestures/),
[libinput-Dreifinger-Ziehen](https://wayland.freedesktop.org/libinput/doc/1.28.1/drag-3fg.html),
[Ghostty-Keybindings](https://ghostty.org/docs/config/keybind).

## @-Zeichen wählen

Unter Einstellungen → Eingabe → Tastatur lässt sich beim deutschen Layout
zwischen **Option+L (macOS)** und **Option+Q (PC)** wählen. Beide Option-Tasten
funktionieren. Die Auswahl wird gespeichert und sofort angewendet. Standard für
neue deutsche Asahi-Installationen ist Option+L; x86-64 erhält diese Auswahl nicht.
