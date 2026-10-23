> **Neueste Übergabe (Claude, 23.10. Mittag): [docs/HANDOFF-CLAUDE-20261023.md](docs/HANDOFF-CLAUDE-20261023.md)** — Store, Does, Update-Seite, Host-Stand, Rückwege, offene Punkte.

# Aktuelle Pause — 23.10.2026: Backup-/Auth-Integration auf Host aktiv

**Heute Abend zuerst lesen:** [Übergabe Codex → Claude](docs/HANDOFF-CLAUDE-BACKUPS.md).

Backup-Seite und eingebetteter Passwortdialog sind auf Bennis ausdrücklich
freigegebenem Host aktiv. Benutzer-Auswahl auf Rückmeldung auf 40 px korrigiert.
Sicherungen, Rückweg, sieben bestandene Tests und noch offene echte Tests stehen
in der Übergabe. Persönliche Settings/Pin-Dateien unverändert. Andere ISO-Fixes
vor Host-Übernahme mit Benni besprechen; kein neuer ISO-/Paketbuild oder Release.
Codex pausiert; keine aktive Dateireservierung. Ältere Notizen darunter sind
historisch, insbesondere deren pauschales „Host unverändert“.

---

# Codex-Abschluss — 23.10.2026, Repo-Test und Bootscreen

Privater signierter Komponentenupdate-Test 15→16 vollständig ausgeführt:
fehlerhafte DB-Signatur und manipuliertes Paket abgewiesen; echtes volles
pacman -Syu, normale erneute Anmeldung, beide Plugins, sechs unveränderte
private Dateien, Windows-Tipp und natives Terminal bestanden. Auch getrennten
zertifizierenden Haupt-/Signatur-Unterschlüssel mit Einmal-Testschlüssel geprüft.
Belege: checks/repository-update-20261023/; docs/SIGNED-UPDATE-REPO.md.
Temporäre private Testschlüssel entfernt, HTTP-Testserver beendet, eigene
Update-VM regulär heruntergefahren. Permanenter geschützter Release-Schlüssel
noch nicht erzeugt; Werkzeug zur lokalen Passphrase-Eingabe liegt bereit.
Vor Veröffentlichung: CachyOS-Pacman-Pfadfehler beim Speichern aktueller Hinweise
regulär beheben und ohne temporäre VM-Umleitung wiederholen. Keine ABI-Pins umgangen.

Neuer Auftrag: ruhiger Start mit Logo/Spinner, Fehlerkonsole automatisch und per
Esc. In Quellen + finalem generierten Profil eingebunden, in eigener installierter
VM normaler Start, absichtlicher Bootfehler, Esc und Desktopstart bestanden.
Eigene Boot-VM heruntergefahren, Testverzögerungen entfernt. Noch KEIN neuer ISO-Bau
und KEIN Live-/Installer-Test der neuen Bootergänzung. Details: docs/BOOT-SPLASH.md,
checks/boot-splash-20261023/.

Host unverändert; latest.iso bleibt r8/15, Store-Pin ec92e22. Nichts gepusht,
veröffentlicht oder hochgeladen. Claude kann im Store weiterarbeiten; Aufteilung
unter docs/WORK-COORDINATION.md. ISO-/Release-Integration erst mit gemeinsamem
aktuellen Quellenstand und den noch offenen Tests. Die folgenden Notizen sind
historische Zwischenstände.

---

# Aktive Arbeit Codex — signiertes Komponentenupdate, 23.10.2026

Autorisiert: privates signiertes Repo und Update in eigener r8-VM-Kopie testen.
Keine Veröffentlichung, kein Host-Paket-/Desktop-Update, keine Änderung an latest.iso.
VM `modes-repo-r8-update` nutzt ein neues Overlay der gestoppten, geprüften
`modes-r8-sdboot-offline`-Platte. Desktop 15 → Test-pkgrel16 wird nativ in der
Kopie gebaut; globale packaging/version.json bleibt15. Quellen/PKGBUILD unter
`build/repository-update-20261023/source/`.

Dauerhafter Schlüssel: eigener geschützter Release-Schlüssel vorgesehen, nicht
Bennis persönlicher Schlüssel. Frage zur lokalen Passphrase-Eingabe ist offen;
bis dahin ausschließlich separater kurzlebiger Testschlüssel. Werkzeug
`tools/create-release-key.sh` für spätere lokale interaktive Erzeugung.
Repo- und Client-Werkzeuge werden jetzt um öffentlichen Schlüssel, signiertes
Manifest und Fingerprint-Prüfung ergänzt. Ergebnisse folgen nach echtem VM-Test.

---

# Aktueller Übergabestand — 23.10.2026, r8-Nachprüfung abgeschlossen

`out/latest.iso` zeigt jetzt auf `out/store-r8-20261023/windoesnot-2026.10.23-x86_64.iso`.
SHA256: 13295f24f2cb2068f0dc6543ee1e66e2b79931157d6c0cc3c2a6579b5596634f.
Desktop 0.1.0-15, Store 0.3.0-1@ec92e22. Kein Neubau und keine Änderung am Image.

Codex hat in frischen eigenen VMs ergänzt: Limine online, rEFInd offline und
systemd-boot offline. Je 39/39 Jobs, automatischer Start ohne ISO, normaler
SDDM-Login, beide Plugins, Paket-/Dienst-/Sprach-/Snapper-Prüfungen und echter
Windows-Tipp bestanden. Hauptkernel 7.2.7; rEFInd automatisch LTS 6.18.50.
Zusammen mit Claudes r8-GRUB/offline-Test sind die vier UEFI-Loader plus Online
abgedeckt, nicht jede Loader-/Moduskombination. Alle drei neuen VMs gestoppt.

Nachweise: `checks/R8-BOOT-MODES-20261023.md`, zugehörige JSON-Übersicht und
`vm/modes-r8-*/`. Claudes Store-Tests bleiben in RELEASE-WORK.md dokumentiert.
Keine Host-Aktivierung, kein Push/Tag/Release und kein Upload erfolgt. Alte ISOs
bleiben vorhanden. Store-Arbeitsbaum weiterhin sauber auf ec92e22.

Nächste Hauptaufgabe: signiertes WinDoesNot-Update-Repo mit dauerhaftem Schlüssel,
Vertrauensbootstrap und echten kompatiblen Komponentenupdates testen. Nicht die
ABI-Pins umgehen. Interaktives Terminal mit API-Key und reale Hardware bleiben
ungetestet. Store-Kleinigkeiten: Installiert-Status nach Transaktion, doppelte
Passwortabfrage, Polkit-Fenstericon. Veröffentlichung des Stores 0.3.0 und
Host-Desktopkorrekturen sind weiterhin nicht ausgeführt; Host-Komponenten bei
späterer Aktivierung gegen dessen tatsächliche Paketvarianten bauen.

Die folgenden Arbeitsstände sind historisch und durch diesen Stand ersetzt.

---

# Zwischenstand — 23.10.2026, r8-Nachprüfung läuft

Claude hat Store 0.3.0@ec92e22 und Desktop-Pakete 0.1.0-15 in r8 integriert.
Offline/GRUB samt tatsächlichen Store-Installationen sind laut den protokollierten
VM-Tests bestanden. Details: neuester Abschnitt RELEASE-WORK.md und Anfang von
docs/HANDOFF-CODEX-STORE.md. Der Store-Arbeitsbaum ist sauber und die Änderungen
sind lokal committed, noch nicht gepusht oder veröffentlicht.

Codex ergänzt jetzt frische r8-Tests: Limine online, rEFInd offline,
systemd-boot offline. Eigene VMs modes-r8-*, kein Zugriff auf Claudes veränderte
Testinstallationen. ISO-Prüfsumme bestätigt:
13295f24f2cb2068f0dc6543ee1e66e2b79931157d6c0cc3c2a6579b5596634f.
latest.iso bleibt während dieser Prüfungen beim bisherigen Paketstand13.
Keine Host-Aktivierung und keine Veröffentlichung in diesem Testblock.

Die folgenden Arbeitsstände sind älter und werden durch den obigen Stand ersetzt.

---

# Übergabestand 22.10.2026, Installationsmodi abgeschlossen

**Neuer Codex-Block: Store-Vorarbeit abgeschlossen.** Weiterarbeit für Claude:
`docs/HANDOFF-CODEX-STORE.md`. Uncommitted Store-Quellen: gemeinsame volle Updates
mit App-Installation, Helfer-Erkennung und Validierung; 20 Rust-Tests plus Build
bestanden. Repository-Bau erlaubt optional Store mit eigener Version; 6 echte
Metadaten-/repo-add-Tests bestanden. Keine echten Systemtransaktionen getestet.
Suchdatenbank, Zielpaketbau, signiertes Update-Repo, VM-Test und neue ISO offen.
Cargo/PKGBUILD noch auf alter 0.2.0; nicht unverändert für neue Pakete verwenden.
Nachweise/Quellpatch: `checks/store-integration-20261022/`. Host/Preview und
latest.iso unverändert, nichts veröffentlicht.

**Store und Desktop-Änderungen außerhalb von 0.1.0-13:** siehe `docs/HANDOFF-STORE.md` (Claude, 22.10. abends). Diese Änderungen brauchen ein Desktop-Release ≥ 0.1.0-14.

Codex hat die Übergabe gegen die lokalen Quellen geprüft. Konkreter nächster
Integrationsblock und Korrektur zum aktuellen `-S`-/`-Syu`-Verhalten:
`docs/STORE-INTEGRATION.md`. SourceForge benötigt für automatischen ISO-Upload
SSH/rsync zusätzlich zum Releases-API-Key: `docs/SOURCEFORGE.md`.
Keine neue ISO/Host-Änderung oder Veröffentlichung bei dieser Übergabeprüfung;
keine Zugangsdaten gespeichert oder verwendet. latest bleibt beim geprüften
Paketstand13. SourceForge-Projekt vom Benutzer bestätigt: `windoesnot`
(https://sourceforge.net/projects/windoesnot/), Benutzername `bennch90`.
Vorhandener öffentlicher ED25519-Schlüssel: `~/.ssh/id_ed25519.pub`.
SourceForge-SSH-Anmeldung und rein lesendes Auflisten des Projektordners
bestanden; Projekt-API aktiv und Benutzerzuordnung bestätigt. Server-Fingerprint
gegen die offizielle Liste geprüft und in known_hosts gespeichert. Nachweis:
checks/sourceforge-access-20261022.json. Transferbefehl mit --dry-run in
docs/SOURCEFORGE.md vorbereitet, noch kein Upload und keine entfernte Änderung.
Release-Signierschlüssel und Store-/Update-Repo-Integration stehen noch aus.

Neue lokale Test-ISO: `out/installer-modes-20261022/`, auch `out/latest.iso`.
Pakete 0.1.0-13, SHA256:
648dafd06be518d270be466f733e55dd379b57a25eb5ac6aa7fe6e15784c8886.
Offline-/Online-Bootmenü, native Auswahl GRUB/rEFInd/systemd-boot/Limine,
Btrfs-Snapper und Windows-Tasten-Dienstkorrektur enthalten.
Online lädt passende ISO-Versionen, aktualisiert nicht die gesamte Systembasis.

Aktuelle ISO in frischen VMs: Limine online und rEFInd offline 39/39 Jobs,
automatischer Start ohne ISO und normaler SDDM-Login bestanden. rEFInd wählt
aktuell LTS; Limine den Hauptkernel. systemd-boot13 und GRUB12 wurden vorher
separat geprüft; die genaue Versions-/Testmatrix steht unter
`checks/INSTALLATION-MODES-TEST-20261022.md` und `docs/TEST-REPORT.md`.
Alle neuen Test-VMs sind gestoppt; Platten/Logs/Screenshots bleiben erhalten.
Testkonto dieser VMs: vmtest / Test12345.

Host-Desktop, Host-Pakete und Host-Bootloader unverändert. Keine Veröffentlichung,
kein Export der Pakete13 ins Update-Repo und keine Store-Integration in diesem
Arbeitsblock. rEFInd+AI SDK nicht implementiert. Hardware/BIOS/Secure Boot/
Windows-Dual-Boot bleiben ungetestet. Vorherige r5-ISO bleibt erhalten.
Wartungshinweise: `docs/INSTALLATION-MODES.md`; Desktop-Audit einschließlich
nachträglich entdecktem Sandbox-Fehler: `checks/DESKTOP-FIX-AUDIT-20261022.md`.

Die folgenden Notizen sind älter; Aussagen zu latest/Paketstand und zum
Arbeitsstatus gelten nur noch, soweit sie oben nicht ersetzt werden.

---

# Session state 2026-10-22 (late evening)

Current tested candidate: ISO r5 `out/after-apps-20261022-r5/` (= out/latest.iso),
desktop packages 0.1.0-12. Full offline install + installed boot PASSED in VM
`r5-install-test-20261022` (vmtest / Zyklus-test-42; German layout: type "-" via
US "/" key and z/y swapped when driving QMP). r4 is defective (installer deadlock).
Details: RELEASE-WORK.md (last sections), docs/TEST-REPORT.md.

Fixed and verified this session: summary clipping (noexpand), GRUB default kernel/
BootNext clutter/os-prober, Firefox German langpack + hunspell-de, new app
`usb-writer` (Impression), live keyboard follows installer (Settings IPC +
live-language.py --keyboard + LiveDesktopBridge queued GlobalStorage hook),
branded hostname suggestion `${first}-windoesnot`.

Website: support section (PayPal donate link for info@lichtauf.computer, needs a
PayPal business account) committed 0532741 and pushed; live on windoesnot.me
within ~40 s (Cloudflare deploys from GitHub main).

Store (commit 4454d1a on branch `windoesnot`): app id me.windoesnot.Store,
icon system-software-install (taskbar via IconMap after next login/session
start), accent + light/dark live from settings.txt, DE/EN by uiLanguage/locale
(on start), robust -Ss parser + stale-search guard. cargo test: 4 passed.
Host desktop entry now ~/.local/share/applications/me.windoesnot.Store.desktop;
IconMap regenerated with the desktop's own generator (only that entry added).
Store: Bazaar-style home + catalogue icons + WinDoesNot logo committed after
9e0790d (see `git log` in store/). Icons for not-installed apps: icon theme ->
/usr/share/swcatalog/icons (archlinux-appstream-data) -> Flathub appstream
cache -> letter tile. cargo test: 6 passed. Host test used copied prefs only.
Store commit 9e0790d: Quickshell-settings look (Settings.qml values), wide
equal-width search tiles, relevance sort. Verified in VM r5 (store binary in
/tmp there, paru set in ~/.config/aurora/settings.json, `pacman -Sy` done in VM).
Integration findings for the ISO:
- Installed system has NO synced pacman DB after offline install: store search
  finds nothing until a sync. Installing single packages after a bare -Sy is a
  partial upgrade -> store must sync+full-upgrade or use a separate DB.
- Default AUR helper is yay, ISO ships only paru: detect installed helper.
- ISO lacks appstream + archlinux-appstream-data (~21 MiB) and flatpak: no app
  icons/screenshots/categories until added (needed for the Bazaar-like home).
Desktop source changes (NOT yet packaged/deployed, need desktop release bump):
- shell.qml: windowIcon() falls back to DesktopEntries.heuristicLookup when
  IconMap has no entry -> apps installed during a session get taskbar icons.
  VM test: name resolved live (log). Hot-reload clean. Not applied to host.
- img/Win11-dark: added apps/scalable/system-software-install.svg (Win11 store
  bag), GPL-3.0 COPYING + AUTHORS of the Win11 theme (were missing), rebuilt
  icon-theme.cache. GTK lookup verified.
Store preview on HOST (user-level only, no root, no packages changed):
~/.local/bin/windoesnot-store + ~/.local/share/applications/me.windoesnot.Store.desktop.
Source: ~/Projekte/WinDoesNot/store (clone of ahmoodio/aurora, branch `windoesnot`,
local commit only, no GitHub repo). aurora-helper/polkit policy deliberately NOT
installed on the host, so installs/updates fail there by design. Codex will
integrate it into the distro. Website commits 0532741 + 981c8dc (tech view
download/support) pushed and live.

App store: user chose to evaluate a fork of ahmoodio/aurora (MIT, Rust, GTK4,
pkexec helper with allowlisted pacman ops). Built and run in disposable VM
r3-install-test-20261022 (rust/clang added there; Aurora in /usr/bin).
Screenshots: vm/r3-install-test-20261022/aurora-*.png. Gaps for a fork: per-
package updates (partial upgrades, e.g. hyprutils alone) must be removed; no
app icons/screenshots (generic gear), raw package names, English only, no
curated home. Not forked yet.

Open / for the user to decide:
- App store: fork an existing store and brand it; user has a saved candidate
  (not found locally; Firefox bookmarks not accessible) — ask for name/link.
  Comparison of candidates in the chat summary (Shelly-ALPM, Bazaar, Aurora, Octopi).
- hyprpaper crash without 3D acceleration is upstream hyprtoolkit; report upstream?
- Cosmetic: SDDM layout box shows "us" until first key; upstream German string
  "Erstelle<strong>neue</strong>"; default location New York; faint dark-mode
  checkbox/radio indicators on the partition page; GRUB "Advanced options" English.
- Packages 0.1.0-12 not exported to out/packages or the signed update repo.
- Host desktop not updated with the new Settings IPC (not required on host).
- Untested: real hardware, Windows dual boot, BIOS, manual partitioning, Secure Boot.

---

# Earlier pause notes — 2026-10-22 (afternoon, superseded where stated above)

User explicitly requested a pause due to the token limit. Do not continue work
until the user resumes it. No host packages, host boot configuration or personal
host desktop files were changed during this ISO work.

## Current deliverable

Final candidate packages: **0.1.0-11**.
ISO: `out/after-apps-20261022-r2/windoesnot-2026.10.22-x86_64.iso`
Size: 4090740736 bytes.
SHA256: f8280da508c745adc08989a99d52148710a02589c623426134fdfca0c9c009e3
Checksum verification passed. Intermediate images are retained in archive-*
subdirectories. Before ISO remains `out/before-apps-20261022/` (0.1.0-5).
Source hashes: `build/after-apps-20261022-r2/SOURCE-STATE.json`.
Native-module builds and refresh logs are in that build directory.

## Implemented and tested

- Native installer app chooser: 14 catalogue entries, profiles, descriptions,
  real icons, search/category filters, strict JSON import/export; Firefox is base.
- Signed offline repository: 276 packages, target-version dependency closure;
  actual full offline installation STILL PENDING.
- German live defaults; localized desktop entries and Start-menu labels.
- Correct installer sidebar/welcome logos and actual io.calamares.calamares
  desktop alias/icon; old Install System launcher hidden/configured safely.
- Personal Keys launcher removed from release; host personal setup preserved.
- Docker and Ollama switches under Apps, both false by default, disabled loaders
  and no warmup/polling. Real guest settings IPC confirms both false.
- Live backups disabled with a notice before any Snapper/polkit call.
- Missing tray chevron replaced with an original project SVG.
- Settings initialization scope fixed; real VM reports loading=false and no
  ReferenceError/TypeError/failed configuration load.
- Own LiveDesktopBridge in our Calamares module: complete light/dark palette,
  QSS, sidebar delegate, matching wordmark, live appearance following Settings.
  Program cards retain selection during theme changes. Checkbox contrast fixed.
- Calamares language changes update live Quickshell and desktop preferences
  through restricted IPC/live-only helper; actual American English and Deutsch
  checked. Other installer languages use English fallback in the DE/EN desktop.
  Installed locale remains Calamares' normal locale job + initializer adoption.
- Pins now match desktop-entry translated name aliases, keep saved order and
  reuse existing icon overrides. Pin file was unchanged; three pins recognized
  after switching back to German (previous bug lost Files/Dateien).
- GRUB live theme uses the ISO root device, not standalone memdisk prefix.
  Separate 480x90 boot logo avoids oversized layout. Real 1280x800 boot screenshot
  correct, no missing-theme error. Original 2446x459 logo exports unchanged.

Meaningful checks passed: test-live-feedback, test-software, shared C++ widget
(profile/import/filter/selection + light/dark), Appearance dynamic loader,
branding sync, desktop validation (32 layouts, locale adoption, Lua verify),
Lua-placement and icon-map startup regression tests. Actual image SDK module
compile/link passed. Upstream checkout remains untouched; overlays/custom
modules live in canonical iso/ and generated build copies.

## Exact pending test state

`apps-install-test-20261022` is a separate HEADLESS QEMU VM (4 GiB, 2 vCPUs)
booted freshly from the 0.1.0-11 ISO, with a private 64 GiB qcow2.
Guest network was disconnected with HMP `set_link net0 off`.
No installation has been confirmed; NO partitions have been written yet.

Installer is currently on **Zusammenfassung / Summary**, ready for review and
then the installation confirmation. Test selections:

- Erase ONLY guest `/dev/vda`, 1 GiB FAT32 /boot + remaining Btrfs root.
- All 14 app IDs imported through normal profile file dialog (13 optional apps).
- German interface/system language, German Standard keyboard.
- Actual map selection is **Europe/Helsinki**, Finnish number/date formats
  (the approximate map click landed there, not Berlin). This is a valid independent
  locale-adoption test; expect Helsinki/Finnish formats if continuing as-is.
- Full name VM Test, username `vmtest`, hostname `windoesnot-test`.
- Disposable TEST-ONLY password `windoesnot-test-42`, same root password.

Latest screenshot: `vm/apps-install-test-20261022/screen.png`.
The Summary content extends to the bottom at 1280x800; action buttons appear
partly clipped in the last screenshot. Check whether it needs scrolling or a
layout correction before claiming low-resolution installer usability. Navigation
via `alt-w` works in German (source translation for &Next is &Weiter).
Do not start installation in the user-facing comparison VM.

Next required work after resume:
1. Confirm Summary/next usability; start and finish actual offline installation
   in this disposable VM only. Fix any actual installer errors.
2. Verify selected apps, German localization packages, profile record, CUPS
   enablement, cleanup of offline archive stash and live-only rules.
3. Boot installed disk, normal SDDM login as vmtest; verify both plugins,
   language/keyboard/timezone, package integrity and clean desktop startup.
4. Record real final results/limitations in RELEASE-WORK.md and release checklist.
5. Keep/offer visible final comparison VM for user; do not publish anything.

## VM/tool notes

User-facing `after-apps-20261022` was opened visibly with final ISO (6 GiB,
software graphics), installer opened for viewing only. User often closes its
window; check socket existence before attempting to stop it. Before comparison
VM may also still exist. No need to close user-view VMs just because agent pauses.
Last exec sessions: headless test 21309, visible after 11167; may have exited.

`tools/vmctl.py --vm-name NAME` supports screenshot, exec, push/pull, hmp, click,
type, stop. VM IPC/GUI/build user namespaces require escalated sandbox execution.
Use guest-agent exec for scripts; commands over 30 seconds need detached launch
and later status/log checks. Tool screenshots need a short delay after UI input.
QMP click default coordinates assume 1280x800. Use alt-w for Next rather than
hardcoded button positions after theme changes.

`tools/test-live-preferences.py` supports --state / --language / --appearance
and a VM-only --restart. Its manual restart environment omits some session/DBus
variables; avoid relying on manual-restart global shortcuts/focus behavior.
Fresh ISO startup has the normal complete session environment. Final full test
VM has not been hotpatched; only a test JSON profile was copied into /tmp.

Build: `./build-and-run.sh --build-only --build-id after-apps-20261022-r2`.
Desktop refresh: `tools/refresh-image-desktop.sh BUILD_ID` (backup guard; inspect
and rename previous desktop-before-refresh folder first); --resume skips already
built project packages after a module build failure. Own installer module can
be rebuilt with tools/build-installer-module.sh only INSIDE marked image chroot.
For upstream Calamares or distro ABI changes use a regular full fresh build.

Relevant docs: docs/INSTALLER-APPS.md, docs/UPSTREAM-UPDATES.md,
docs/RELEASE-CHECKLIST.md, RELEASE-WORK.md. Developer launchers (Qt/CMake etc.)
were explicitly deferred by user; leave dependencies installed for now.
Website/brand source exports belong to user's completed website work; don't edit
website. Public-release asset/license/hardware caveats in release checklist are
still outstanding; no public release/push was authorized by this VM test work.
