# WinDoesNot component updates

[Deutsch](#deutsch)

This channel supplies the four WinDoesNot desktop packages. CachyOS/Arch system
packages continue to come from their existing repositories. Use a full system
upgrade so the desktop, native plugins and system libraries stay compatible.
The published 0.1.0-18 ISO needs the one-time setup below; its download is unchanged.

## Verify and set up once

The release signing key's **primary fingerprint** is:

```text
ED9530A990C6D39EB7D4BA8F9BDCA578FBF1DDB0
```

Compare this with the [public key in the project repository](https://github.com/Bennch/windoesnot/blob/main/packaging/release-key/RELEASE-KEY.asc).
Do not establish trust using a fingerprint downloaded only from the package server.
The following commands download public verification material and a signed setup
bundle. Run them as your normal user in a new working directory:

```sh
curl -fLO https://raw.githubusercontent.com/Bennch/windoesnot/main/packaging/release-key/RELEASE-KEY.asc
curl -fLO https://download.windoesnot.me/repo/bootstrap/windoesnot-update-client-0.1.0-19.tar.gz
curl -fLO https://download.windoesnot.me/repo/bootstrap/windoesnot-update-client-0.1.0-19.tar.gz.sig
gpg --show-keys --with-fingerprint RELEASE-KEY.asc
gpg --dearmor --output windoesnot-release.gpg RELEASE-KEY.asc
gpgv --keyring "$PWD/windoesnot-release.gpg" windoesnot-update-client-0.1.0-19.tar.gz.sig windoesnot-update-client-0.1.0-19.tar.gz
```

Check the full primary fingerprint above and require a successful `gpgv`
verification before continuing. Back up your system, then:

```sh
tar -xzf windoesnot-update-client-0.1.0-19.tar.gz
cd windoesnot-update-client-0.1.0-19
sudo ./bootstrap.sh
sudo pacman -Syu
```

The bootstrap adds only the WinDoesNot public key and repository configuration,
backs up `/etc/pacman.conf`, and preserves the existing distribution repositories.
It requires signed packages and a signed database from trusted keys. It refuses
to overwrite an existing WinDoesNot repository configuration. After updating,
log out and back in; follow any reboot instructions for system updates.
Once configured and refreshed, Settings and the Store use the normal package
databases to show available WinDoesNot updates.

The 18 → 19 upgrade and login were checked in a UEFI VM, including native plugins
and preservation of private settings. During the CachyOS CPU-package transition,
the regulatory-domain service failed in the test system without the `nl80211`
wireless subsystem. This is recorded separately from the component-update result;
real-hardware coverage is still open.

## If you need to disable it

The bootstrap prints the exact `pacman.conf.before-windoesnot-…` backup path.
Restore that backup if you have made no subsequent repository changes; otherwise
remove only `Include = /etc/pacman.d/windoesnot.conf` from `/etc/pacman.conf`.
Disabling the repository does not downgrade already installed packages.

For an installed-system rollback, use an appropriate pre-update Btrfs restore
point, or restore all four matching previous WinDoesNot packages together if
you retained them. Keep native ABI requirements intact. Preserve personal files
separately; system snapshots are not a backup of your documents.

## Deutsch

Der Kanal liefert die vier WinDoesNot-Desktop-Pakete. CachyOS-/Arch-Systempakete
kommen weiterhin aus ihren bisherigen Quellen. Aktualisiere immer das ganze
System, damit Desktop, native Plugins und Bibliotheken zusammenpassen.
Die veröffentlichte ISO 0.1.0-18 bleibt unverändert und braucht diese einmalige
Einrichtung.

Vergleiche den vollständigen Hauptschlüssel-Fingerprint oben mit dem öffentlichen
Schlüssel im Projekt-Repository. Führe die Download- und Prüf-Befehle unter
„Verify and set up once“ als normaler Benutzer in einem neuen Verzeichnis aus.
Erst wenn der Fingerprint stimmt und `gpgv` die Signatur erfolgreich bestätigt,
entpackst du das Bündel und startest `sudo ./bootstrap.sh`, danach `sudo pacman -Syu`.

Das Skript sichert `/etc/pacman.conf`, trägt den öffentlichen WinDoesNot-Schlüssel
und die Paketquelle ein und erhält deine bestehenden Systemquellen. Pakete und
Datenbank müssen gültig signiert sein. Eine vorhandene WinDoesNot-Konfiguration
wird nicht überschrieben. Nach dem Update einmal ab- und wieder anmelden;
Neustarthinweise für Systemupdates beachten. Einstellungen und Store zeigen den
Kanal über die normalen Paketdatenbanken an, sobald er eingerichtet und geprüft ist.

Das Update 18 → 19 mit erneuter Anmeldung, nativen Plugins und Erhalt der privaten
Einstellungen wurde in einer UEFI-VM geprüft. Beim Wechsel auf die CachyOS-CPU-Pakete
meldete der Länderkennungsdienst im Testsystem ohne WLAN-Subsystem (`nl80211`)
einen Fehler. Dieser Hinweis ist separat dokumentiert; echte Hardware ist weiterhin
noch nicht mit diesem Updateweg geprüft.

Zum Abschalten kannst du die beim Einrichten genannte Konfigurationssicherung
zurückspielen, sofern du die Paketquellen seitdem nicht weiter geändert hast.
Andernfalls entfernst du nur die WinDoesNot-Include-Zeile. Bereits installierte
Pakete bleiben dabei installiert. Für eine Rückkehr zum früheren Systemstand
nutze einen passenden Wiederherstellungspunkt oder einen vollständig erhaltenen
älteren Satz aller vier WinDoesNot-Pakete; ABI-Anforderungen bleiben bestehen.
