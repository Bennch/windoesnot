# Plattform-Fixes und Arbeitsstand

Für jeden Fix wird entschieden: **beide**, **nur x86-64** oder **nur Asahi**.
Die Zuordnung beschreibt das Ziel; sie bedeutet nicht, dass beide Images gebaut
oder auf echter Hardware getestet wurden.

| Datum | Änderung | Ziel | Begründung / Quellen | Validierung / offen |
| --- | --- | --- | --- | --- |
| 2026-11-11 | Akku-Füllstand und Netzanschluss im Tray | beide | Gemeinsame Quickshell-Oberfläche: `shell.qml`, `widgets/BatteryTrayIcon.qml`, `widgets/qmldir`; UPower liefert Änderungen auch bei geschlossenem Popup. Netzsymbol auch bei vollem Akku. | QML-Ladetest in isolierter Wayland-Sitzung erfolgreich; Kabelwechsel und Füllstände live noch prüfen; x86-64 und beide Images ungetestet. |
| 2026-11-11 | Fehlende Desktop-Pakete | beide | `tools/install-desktop.sh`: Firefox samt DE/EN-Sprachpaketen und brightnessctl ergänzen. `iso/packages-extra.txt`: Firefox und brightnessctl explizit. Vorherige Sprachpakete konnten Firefox im ISO transitiv ziehen; der Desktop-Installer enthielt keinen Browser. | Paketlisten geprüft; Installation auf Host benötigt sudo, noch nicht ausgeführt. Keine neuen Images gebaut. |
| 2026-11-11 | Doppeltes Terminal in der Taskleiste | beide | Gemeinsame Fenstererkennung in `shell.qml`: angeheftetes `windoesnot-terminal` muss laufende Kitty-/Ghostty-Fenster erkennen. Vorher wurde Kitty als zusätzliche Anwendung geführt. | Host hat genau ein Kitty-Fenster und einen Terminal-Pin; Host-Deployment erfolgreich; visuelle Bestätigung noch offen. |
| 2026-11-11 | Helligkeitsbereich und Aktualisierung | beide | `widgets/BatteryPanel.qml`: bei nicht verfügbarer Helligkeitssteuerung Hinweis anzeigen; beim Öffnen des Fensters aktualisieren. Bestehenden Backlight-/DDC-Pfad beibehalten. | QML-Ladetest; Backlight- und DDC-Regelung auf passender Hardware ungetestet. |
| 2026-11-11 | Fehlende Displayhelligkeit auf M3 Pro | nur Asahi | Host: MacBook Pro 14 Zoll M3 Pro, Kernel `7.2.12-3-1-ARCH`, DRM `simple-framebuffer`, `/sys/class/backlight` leer; außerdem brightnessctl nicht installiert. Kein hardwareseitiges Backlight verfügbar. | Noch ungelöst auf Host. Asahi meldet DCP-Unterstützung mit Linux 7.3 und kommende Kernel-/m1n1-Updates. Lokale pacman-Metadaten bieten noch linux-asahi 7.2.12.asahi3-1. Unterstützte Updates prüfen, sobald verfügbar; keine Bootloader-/Kernel-Änderungen vorgenommen. |

## Helligkeit: Referenzen und nächster Schritt

- [Asahi Linux 7.3: M3 goes GA](https://asahilinux.org/2026/11/progress-report-7-3/)
  beschreibt die neue DCP-Unterstützung und erforderliche kommende Updates.
- `brightnessctl` allein erzeugt keinen fehlenden Kernel-Backlight-Treiber.
- Nach unterstütztem Kernel-/m1n1-Update und Neustart DRM-Treiber sowie
  `/sys/class/backlight` erneut prüfen, dann Helligkeit live testen.
- Die frühere pauschale Aussage, ARM sei geprüft, ersetzt keine M3-Hardwareprüfung.

## Bereits vor dieser Sitzung vorhandene Änderungen

Desktop-Installer, ARM-Build-Flags, Terminal-Fallback, Auth-Guard-Pfad und weitere
Anpassungen waren bereits uncommittet vorhanden. Ihr ursprünglicher Verlauf fehlt.
Diese Änderungen nicht als vollständig geprüft oder neu erstellt ausgeben.

## Terminal-Vorgabe (2026-11-11)

Beide Varianten sollen wie WinDoesNot Ghostty verwenden. Benutzer lehnt Kitty ab.
Den zuvor vorhandenen Kitty-Fallback im Starter entfernen; keine Kitty-Abhängigkeit
für neue Installationen. Laufende Kitty-Sitzung nicht beenden.
Auf dem Asahi-Host fehlt Ghostty und ist in den konfigurierten Paketquellen nicht
verfügbar. Offiziellen Quellbau prüfen; fehlendes Terminal nicht still ersetzen.
Die Paketvorlage `packaging/PKGBUILD.in` erhält ebenfalls explizite Abhängigkeiten
für Firefox und brightnessctl.

## Host-Deployment

Akku- und Taskleistenänderungen wurden am 2026-11-11 auf diesem Host aktiviert.
Backup: `~/Backups/windoesnot-release/20261111-174445-battery-tray`.
Quickshell startet; Authentifizierungsagent registriert; persönliche Einstellungen
unverändert. Akku-/Kabelwechsel visuell noch nicht bestätigt.
GitHub-Lesezugriff auf Bennch/windoesnot geprüft; nichts gepusht.

Ghostty-Quellbau: `python3 tools/build-ghostty.py --prefix "$HOME/.local"`.
Offizielles Release 1.4.0 und Zig 0.17.0, Archive mit festen SHA256-Prüfsummen.
Der Desktop-Installer verwendet diesen Pfad, wenn Ghostty weder installiert noch
in den Paketquellen verfügbar ist. Ziel: beide; ARM-Build auf dem Host läuft,
x86-64-Quellbau und Integration in ein Asahi-Image noch ungetestet.

## Zeiger und Ruckeln (2026-11-11)

- **Beide:** `input.force_no_accel` war in der gemeinsamen Referenz auf 1.
  Auf false korrigiert; der Input-State-Writer schaltet ihn beim Anwenden der
  normalen Geschwindigkeits-/Beschleunigungseinstellungen ebenfalls aus.
  Laut [Hyprland-Dokumentation](https://wiki.hypr.land/configuring/core/config-options/#input)
  umgeht die Option normale Einstellungen und kann Desynchronisation verursachen.
- **Nur dieser Host:** Apple-MTP-Trackpad erkannt, keine externe Maus.
  Empfindlichkeit auf -0.25 gesetzt (vorher 0); kein neuer ISO-Standard.
- **Nur Asahi:** konservatives Effektprofil in `lua/init.lua`, ausschließlich
  bei Apple-Gerät + simple-framebuffer + fehlendem DRM-Render-Node.
  Blur, Schatten und Animationen entfallen in diesem Fall. Explizite Werte aus
  Benutzer-State gewinnen. Hardware mit Render-Node und x86-64 unverändert.
- Host angewendet, keine Hyprland-Konfigurationsfehler. Backup:
  `~/Backups/windoesnot-release/20261111-174912-pointer`.
- Kurze CPU-Stichprobe für den Compositor vor/nach Effektreduktion: etwa
  390 % / 324 % (100 % = ein CPU-Kern). Keine isolierte Benchmarkmessung;
  Hintergrund-Build und laufende Terminalausgabe beeinflussen die Last.
- Vollständige Beseitigung des Ruckelns nicht nachgewiesen. Ohne M3-GPU-Treiber
  bleibt Software-Rendering eine wesentliche Einschränkung.
- Lua-Platzierungstest: 16 Fälle bestanden; haptische Bestätigung ausstehend.

## Rückmeldung und Last (2026-11-11)

- Benutzer meldet -0.25 als zu langsam: auf diesem Host wieder 0 eingestellt,
  `force_no_accel=false` bleibt. Auch `settings.txt` entsprechend aktualisiert.
- Ghostty-Quellbau erfolgreich auf ARM, lokal unter `~/.local` installiert.
  Der erste direkte Build meldet mangels Versions-Override
  `1.4.0-dev+0000000`; der reproduzierbare Helper setzt künftig 1.4.0 explizit.
  Launcher auf Host verwendet Ghostty, kein Kitty-Fallback mehr.
  Fensterstart noch nicht getestet. Aktuelle Kitty-/Codex-Sitzung bleibt offen.
- Während des Builds zusätzliche CPU-Last; Build abgeschlossen, keine Zig-Prozesse
  mehr aktiv. Hyprland und Kitty bleiben CPU-intensiv (Software-Rendering).
- Nur Host, temporäre Kitty-Mitigation für laufende Sitzung: repaint_delay 33 ms,
  Cursorblinken aus; Konfiguration per SIGUSR1 neu geladen. Kein ISO-Standard.
- Gemeinsame Doku und AGENTS.md waren durch .gitignore ausgeschlossen; explizite
  Ausnahmen ergänzt, damit diese Entscheidungen ins Repository gelangen können.

## Abschließende Prüfungen dieser Sitzung

- Ghostty-Fenster auf diesem Host geöffnet, Klasse `com.mitchellh.ghostty`,
  Testkommando beendet sich mit Exit 0. Laufzeitlog bestätigt CPU-Presentation
  nach fehlgeschlagenem DMABUF-Export: Ghostty umgeht die fehlende GPU nicht.
- Kitty-Repaint-Experiment und temporärer Softwarecursor-Test zeigten keine
  belastbare Lastsenkung und wurden zurückgenommen. Effektreduktion bleibt.
- Eingabe-State-Regression und fünf Plattformfälle geprüft: Apple-Framebuffer
  ohne Render-Node, Apple mit Render-Node, Nicht-Apple, nativer Displaytreiber,
  explizite Blur-Einstellung. Alle erfolgreich.
- `tools/validate-desktop.py` erfolgreich (Layout, Python/SVG, Initialisierung,
  Konfigurationserhalt, Hyprland-Lua); `git diff --check` sauber.
- Weiter offen: native Display-/GPU-Unterstützung bzw. unterstützte Systemupdates,
  echte Akku-Kabelwechsel, subjektives Trackpad-Gefühl, beide ISO-Builds und Tests.
- Firefox und brightnessctl auf diesem Host weiter nicht installiert: sudo
  benötigt Benutzerpasswort. Für den Host im eigenen Terminal ausführen:
  `sudo pacman -Syu --needed firefox firefox-i18n-de firefox-i18n-en-us brightnessctl`.

## Zwischenablage ohne Shift (2026-11-11)

- **Nur Asahi**, ausdrücklicher Benutzerwunsch: Control+C kopiert markierten Text,
  Control+V fügt ein. Ohne Markierung bleibt Control+C der Befehlsabbruch.
- `desktop/defaults/asahi/config/ghostty/asahi-keybindings.conf`: Ghostty nutzt
  `performable:ctrl+c=copy_to_clipboard` und `ctrl+v=paste_from_clipboard`.
- `windoesnot-initialize` bindet dies für neue Ghostty-Konfigurationen nur auf
  Apple-aarch64 ein. Vorhandene Benutzerkonfigurationen bleiben bei Initialisierung
  erhalten; Host wurde ausdrücklich separat angepasst. x86-64 bleibt unverändert.
- Ghostty-Konfiguration validiert und laufendes Ghostty per SIGUSR2 neu geladen.
  Für die noch offene Kitty-Sitzung nur lokal entsprechende Kürzel gesetzt
  und per SIGUSR1 neu geladen; Kitty wird dadurch kein Teil des Images.
- Backup: `~/Backups/windoesnot-release/20261111-175813-clipboard`.
- Benutzer hat Tools installiert: Firefox 159.0.1-1 und brightnessctl 0.5.1-3
  sind jetzt per pacman bestätigt. Der ältere Eintrag „noch nicht installiert“
  ist damit überholt. Backlight-Gerät weiterhin separat prüfen.

## Asahi-Gesten: endgültige Zuordnung dieser Sitzung

Die vorherige Zuordnung mit Drei-Finger-Arbeitsflächenwechsel wurde durch das
[vollständige Asahi-Eingabeprofil](asahi-input.md) ersetzt: drei Finger ziehen,
vier Finger navigieren. Benutzer möchte macOS-Entsprechungen mit unseren Apps.
Gestenprofil: **nur Asahi**. Passive IPC-Endpunkte und App-Fensterfilter in der
geteilten Shell/Overview: **beide**, werden auf x86-64 nicht automatisch belegt.
Host aktiviert, Hauptshell und Overview IPC registriert, Lua-Konfiguration fehlerfrei.
Physische Gestenbestätigung und beide ISO-Builds weiter offen.

## Firefox-Icon / Quellinstallation

**Beide:** Firefox samt Icons war installiert, aber das eingestellte Theme Win11
fehlte im Icon-Suchpfad. `windoesnot-initialize` registriert bei Quellinstallationen
`$XDG_DATA_HOME/icons/Win11` als Link auf das eigene Theme, sofern weder Paket-Theme
noch ein Benutzer-Theme vorhanden ist. Host-Link angelegt und Shell neu gestartet.
Qt-Test mit echtem `AppIcon`: `image://icon/firefox`, Image.Ready (1).

## GitHub-Abgleich (2026-11-11)

GitHub main: `e143c4d`, lokal HEAD: `439a510`. 15 fehlende Commits, 32 geänderte
Dateien. Remote-Referenz per fetch aktualisiert, Arbeitsbranch nicht gemergt.
Direkte Überschneidungen mit unseren Änderungen: `shell.qml`, `BatteryPanel.qml`.
Dreiwege-Probezusammenführung beider Dateien konfliktfrei. Weitere Änderungen
betreffen Settings, Input/Kernel/Backup, Netzwerk und Taskleistenverhalten.
Remote bringt außerdem robustere Erkennung laufender Quickshell-Instanzen über
`quickshell list --json --path`; beim Host-Deployment als temporäre Toolversion
genutzt, da die vom Nutzer neu gestartete Shell ohne Kommandozeilenargument lief.
Alle lokalen Änderungen bleiben uncommittet; nichts auf GitHub geschrieben.

## Übernahme in WinDoesNotMac (2026-11-11)

- Alle 15 gemeinsamen Commits bis `e143c4d` per Fast-forward übernommen; lokale
  Änderungen über Sicherung und beibehaltenen Stash wieder eingespielt. Keine Konflikte.
- Lokaler Branch `windoesnotmac`; privates Ziel `Bennch/WinDoesNotMac` am
  2026-11-11 über GitHub bestätigt. Öffentliches `Bennch/windoesnot` bleibt unverändert.
  Dessen lokaler Push-Endpunkt ist vorsorglich deaktiviert; Remote `mac` ist privat.
- Tests für Power-/Backup-UI an die upstream geänderte Loader-Struktur, deutsche
  Texte und vorhandene Restore-Policy angepasst. Zehn betroffene Testskripte bestanden
  nach diesen Aktualisierungen; Gesamt-Ladetest und Desktop-Validierung erfolgreich.
- **Nur Asahi:** Einstellung Eingabe → Tastatur für Option+L (Mac) / Option+Q (PC).
  Beide Option-Tasten verwenden die gewählte deutsche XKB-Belegung. Andere Layouts
  bleiben ohne diese Zuordnung; unabhängige Compose-/Caps-Lock-Optionen bleiben erhalten.
  Auf Host angewendet; beide Optionen live umgeschaltet und gespeichert, zuletzt L.
- Neuer Test `tests/test-asahi-keyboard.py` prüft echte XKB-Ausgabe statt Textmuster.
- **Beide:** Grafikwerkzeug-Installation über festen Paketumfang im sichtbaren Terminal.
  **Nur Asahi:** Apple-Grafikstatus statt irreführender LACT-Fehlermeldung; Diagnose-
  Installation und Zugang zu Updates, ohne GPU-Unterstützung durch Tools vorzutäuschen.
  `tests/test-graphics-platform.py` prüft Apple mit/ohne Render-Node sowie PC ohne LACT.
- Noch offen: physische Gestenbestätigung, native M3-Grafik-/Displayunterstützung,
  tatsächliche ISO-/Asahi-Installationsartefakte und echte Hardwaretests beider Varianten.

## Deckel und einheitliche Steuerelemente (2026-11-11)

- **Beide, bei vorhandenem Deckelschalter:** Akku & Energie enthält getrennte
  Aktionen für Akku, Netzteil und Dock/externes Display. Systemvorgabe, Energiesparen,
  nur sperren, nichts tun. Defaults bleiben Systemvorgabe.
- `windoesnot-lid-controller` verwendet loginds low-level handle-lid-switch-Inhibitor
  nur bei expliziter Benutzerabweichung und reagiert auf LidClosed-Änderungen.
  Keine konkurrierenden Hyprland-Lid-Binds und keine root-Konfigurationsänderung.
  Shell-Kindprozess, Sitzungs-Lock gegen Duplikate. Temporäre Schreibfehler behalten
  die letzte Präferenz. Schlafaktionen erfordern vorher bestätigte Bildschirmsperre.
- Host-Befund: HandleLidSwitch=suspend, ExternalPower erbt suspend, Docked=ignore;
  kein vorhandener Deckel-Inhibitor. Beim Zuklappen würde daher Suspend angefordert.
  Das ist kein Poweroff; tatsächliches Suspend/Resume wurde nicht ausgeführt.
- **Nur Asahi:** Hinweis bei Apple-Boot-Framebuffer, dass Resume noch nicht geprüft
  ist. Aktueller Kernel 7.2.12 bietet ausschließlich 3024×1890@60Hz, kein VRR; keine
  künstliche 120-Hz-Konfiguration eingespielt.
- @-Auswahl auf `SystemToolsChoice` umgestellt, mit bestehenden Abmessungen, Farben,
  Dropdown- und Fokuszuständen sowie DE/EN-Labels. Keine ungestaltete Standard-ComboBox.
- Host-Deployment: `~/.local/state/windoesnot/desktop-sync/20261111-183444`; Auth-Agent
  registriert, persönliche Einstellungsdateien beim Deployment unverändert.
- Tests: vier Logind-Policy-/Kantenfälle ohne Poweraktion; Power-UI mit sichtbarer
  Deckelkarte, gemeinsamem Control-Stil und echter Auswahländerung; Gesamt-QML und
  Desktop-Validierung bestanden. Inhibitor im Benutzerkontext kurz erworben/freigegeben,
  ohne Deckel-, Sperr- oder Schlafaktion. Physisches Suspend/Resume bleibt offen.

## Technische C-Locale in den Spracheinstellungen (2026-11-11)

- **Beide:** portable Minimalinstallationen können nur C/C.utf8/POSIX enthalten.
  Host bestätigt `/etc/locale.conf`: LANG=C; `locale -a`: nur C, C.utf8, POSIX.
  Dies ist kein fälschlich erkannter Sprachname; menschliche Sprachdaten fehlen.
- `LocaleNames.js` normalisiert UTF-8-Namen und schließt technische Locales aus
  der Sprachauswahl aus. Anzeige: „Keine Systemsprache eingerichtet“, kein C als
  auswählbare Sprache und kein irreführender Hinweis auf eine unbekannte Sprache.
- Deutsch/Englisch werden bei fehlenden Locales mit „einrichten“ angeboten.
  Auswahl verwendet den vorhandenen WinDoesNot-Passwortdialog, aktiviert nur die
  gewählte Locale in locale.gen, führt locale-gen aus und setzt sie per localectl.
  Andere Locale-Einträge und Dateirechte bleiben erhalten. Kein automatisches
  Generieren ohne Auswahl; aktuelle Session-Locale erfordert erneute Anmeldung.
- Der autorisierte Systemhelfer prüft die erzeugten Sprachdaten und den Erfolg
  von localectl, statt sich auf die LC_ALL-Umgebung des Agenten zu verlassen. Vorhandene
  Locales verwenden weiter den bisherigen localectl-Pfad. Dateimanager werden
  bei Auswahl nicht vorzeitig mit SIGKILL beendet.
- Tests: echte QML-Spracheinstellungen mit C-Anzeige, Einrichtungspfad, vorhandenen
  Sprachen, Fehlerbehandlung; technische/humane Locale-Fälle; temporäre locale.gen
  (Rechte, Erhalt fremder Einträge, Idempotenz, ungültige Locale). Keine Host-Locale
  und kein Root-Systemzustand während der Tests geändert.

## Gemeinsamer Passwortdialog mit Arbeitsfortschritt (2026-11-11)

- **Beide:** Spracheinrichtung verwendet die vorhandene AuthenticationCard und den
  registrierten Polkit-Agenten. Keine Console, kein sudo-Prompt und keine zweite
  Passwortimplementierung. Die Karte hat wiederverwendbare Task-Eigenschaften für
  Arbeitsstatus, Schritte, indeterminierten Fortschritt, Erfolg, Abbruch und Fehler.
- Passwortfeld nur während der Polkit-Abfrage; nach Freigabe bleibt dieselbe Karte
  sichtbar und zeigt die tatsächlichen Backend-Schritte 1–3. Keine erfundenen Prozentwerte.
- Neue feste Aktion `org.windoesnot.system.locale-set`: nur de_DE.UTF-8/en_US.UTF-8,
  exakte Argumentprüfung, auth_admin, ausführbarer Pfad auf den root-eigenen Helfer
  festgelegt. Root-Helfer schreibt Fortschrittsereignisse; Fehler stellen locale.gen
  wieder her. Andere Locales und Dateirechte bleiben erhalten.
- Quellinstallationen ohne passenden Systemhelfer können ihn beim ersten Aufruf
  über denselben grafischen Dialog aktualisieren; feste zwei Ziele mit Root-Backup,
  dann Spracheinrichtung im autorisierten Prozess. Paketverwaltete Helfer werden
  dabei nicht überschrieben. Neue Quellinstallationen installieren Helfer/Policy zusammen.
- Tests: vier Backend-/Allowlist-/Rollback-/Polkit-Aufruffälle, vorhandene Systemtools-
  und Backup-Dialogtests, Sprachwechsel-UI, neue Dialogkarte mit Passwortlöschung,
  Übergang zu Fortschritt, Erfolgs-/Fehlerzustand und DE/EN/Hell-/Dunkelmodus.
- Kein echtes Passwort und keine Host-Locale für Tests verwendet. Autorisierung und
  tatsächliche Erzeugung starten erst bei einer bewussten Sprachauswahl.

## Privater Asahi-Installer-Fork (2026-11-11)

- **Asahi only:** Quellfork unter `installer/asahi`, ALARM-Stand
  `3cfef52bc372a7b84b59823027c75327e129d6ec`, MIT samt Herkunft erhalten.
  Keine öffentliche Fork-Repo und keine übernommenen Publish-Workflows.
- Standardname/Supportlink auf WinDoesNotMac; Build verlangt macOS und eigenes
  ICNS-Logo. Apple-Partitionierung, Firmware und Recovery-Logik unverändert.
- Bootstrap-Einstiege absichtlich gesperrt, bis eigene geprüfte Installer-Artefakte
  und ARM-Images existieren. Keine umetikettierte Installation fremder Images.
- Ablauf und offene Aufgaben in `installer/asahi/DOWNSTREAM.md`: macOS-Setup,
  physischer Recovery-Schritt, Linux-Boot, danach Calamares als Ersteinrichtung.
- Prüfung: Python-Quellen kompiliert, Shell-Syntax geprüft, Linux-Build und
  Bootstrap verweigern Ausführung erwartungsgemäß. Kein echter Installationslauf,
  kein macOS-Build und kein Recovery-Test. x86-Installer unverändert.
