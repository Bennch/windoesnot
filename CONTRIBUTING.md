# Try WinDoesNot and share feedback

[Deutsch](#deutsch)

Security issues: please follow [SECURITY.md](SECURITY.md) and do not open a public issue.

WinDoesNot is an early public preview. A short test on your own hardware is useful;
you do not need to be a developer or install the system to help.

1. Download the ISO from [the download page](https://windoesnot.me/en/download/)
   and verify its SHA256 checksum.
2. Start the live USB in UEFI mode. Follow the
   [installation guide](https://windoesnot.me/en/help/installation/) for USB preparation.
3. Try the display, keyboard/mouse, Wi-Fi or Ethernet, sound, settings and Store.
   Opening the Store is enough; installing software is optional.
4. If you choose to test installation, back up your data first and use a spare disk
   or test computer. Check reboot and login afterwards. Installation is optional.
5. [Report your hardware result](https://github.com/Bennch/windoesnot/issues/new?template=hardware_test.yml)
   or [report a problem](https://github.com/Bennch/windoesnot/issues/new?template=bug_report.yml).

Include the version, computer/CPU/GPU if known, and whether you used a live USB,
an installed system or a virtual machine. Partial results are welcome: distinguish
**works**, **fails** and **not tested**. Screenshots are useful; console commands
and logs are not required. Remove private information and API keys before posting.
English and German are both welcome.

The release was tested in UEFI virtual machines. Real-hardware coverage is still
being collected; BIOS boot and Secure Boot remain unverified. There is no public
signed WinDoesNot component-update repository yet. See the current
[release status](https://windoesnot.me/en/help/release-status/).

## Build host requirements

Only needed if you build the ISO yourself; testing the released ISO needs none of this.

- Linux with archiso (`mkarchiso`), python, python-yaml, git, librsvg and rust (the
  store sources are vendored with cargo).
- Boot and image tools: grub tools, squashfs-tools, libisoburn, dosfstools, mtools
  and erofs-utils.
- The CachyOS package signing key must be in the host pacman keyring: run
  `pacman-key --init`, install `cachyos-keyring` from the CachyOS repository, then
  `pacman-key --populate cachyos`.
- The pins in `sources.json` must be present as git repositories (store,
  device-manager, bluetooth, network, audio, graphics). On the working branch
  `tools/fetch-sources.py` takes care of this.
- The systemd v262.1 source tarball for the translated bootloaders can be rebuilt
  bit-identically with
  `git archive --format=tar --prefix=systemd-262.1/ v262.1 | gzip -n -6`.
  It must match the sha256 in `iso/boot-language/sources.json`.
- An x86_64 ISO cannot be built or tested at useful speed on Apple Silicon.

## Deutsch

WinDoesNot ist eine frühe öffentliche Vorschau. Ein kurzer Test auf deinem Rechner
hilft bereits. Du musst weder entwickeln können noch das System installieren.

1. Lade die ISO von der [Downloadseite](https://windoesnot.me/download/) und prüfe
   die SHA256-Prüfsumme.
2. Starte den Live-USB im UEFI-Modus. Wie du den USB-Stick vorbereitest, steht in
   der [Installationsanleitung](https://windoesnot.me/hilfe/installation/).
3. Probiere Anzeige, Tastatur/Maus, WLAN oder LAN, Ton, Einstellungen und Store aus.
   Den Store zu öffnen reicht; du musst keine Programme installieren.
4. Falls du die Installation testen möchtest, sichere vorher deine Daten und nutze
   einen freien Datenträger oder Testrechner. Prüfe anschließend Neustart und Anmeldung.
   Eine Installation ist freiwillig.
5. [Melde dein Hardware-Ergebnis](https://github.com/Bennch/windoesnot/issues/new?template=hardware_test.yml)
   oder [beschreibe einen Fehler](https://github.com/Bennch/windoesnot/issues/new?template=bug_report.yml).

Nenne die Version, möglichst Rechner/CPU/GPU und ob du einen Live-USB, ein
installiertes System oder eine VM benutzt hast. Auch Teiltests helfen:
Unterscheide **funktioniert**, **fehlerhaft** und **nicht getestet**. Bilder sind
hilfreich; Konsolenbefehle und Protokolle sind keine Voraussetzung. Entferne private
Daten und API-Schlüssel vor dem Posten. Deutsch und Englisch sind willkommen.

Der Release wurde in UEFI-VMs geprüft. Rückmeldungen zu echter Hardware sammeln wir
erst; BIOS-Start und Secure Boot sind noch ungeprüft. Ein öffentlicher signierter
Updatekanal für WinDoesNot-Komponenten fehlt noch. Den aktuellen
[Release-Stand findest du hier](https://windoesnot.me/hilfe/release-stand/).
