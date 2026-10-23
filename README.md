# WinDoesNot

Hyprland-/Quickshell-Desktop mit CachyOS-Live-System und Online-/Offline-Installation.
Entwicklungsstand: Live-Start, vollständige Offline-Installation und installierter
Desktop in QEMU geprüft. Noch kein veröffentlichter Release; Asset-Lizenzen und
Tests auf echter Hardware stehen aus. [Testbericht](docs/TEST-REPORT.md).

```sh
./build-and-run.sh                            # bauen und QEMU starten
./build-and-run.sh --build-only               # nur ISO erzeugen
./build-and-run.sh --run-only /pfad/test.iso   # schnell erneut starten
./build-and-run.sh --boot-installed           # installierte VM-Platte booten
./build-and-run.sh --run-only /pfad/test.iso --fresh-vm
```

Den bereits installierten Referenzstand mit Fenster starten:

```sh
./build-and-run.sh --boot-installed --vm-name release-packaged-18
```

Das synthetische Testkonto heißt `vmtest`, Passwort `Vmtest2026`.
Die aktuelle geprüfte ISO liegt unter `out/store-r8-20261023/` (auch `out/latest.iso`),
Desktop-Pakete 0.1.0-15 mit Store 0.3.0. GRUB offline sowie Limine online,
rEFInd offline und systemd-boot offline sind auf r8 geprüft. Die neuen Test-VMs
heißen `modes-r8-limine-online`, `modes-r8-refind-offline` und
`modes-r8-sdboot-offline`; Konto `vmtest` / `Test12345`.
[Modi und Bootloader](docs/INSTALLATION-MODES.md),
[genaue r8-Testmatrix](checks/R8-BOOT-MODES-20261023.md).
Online lädt genau die passenden ISO-Paketversionen, keine neue Systembasis.
Der ältere Referenzstand ISO18 liegt weiterhin unter `out/packaged-test-18/`.
Ein [echtes signiertes Komponentenupdate15→16](docs/SIGNED-UPDATE-REPO.md) ist
in einer eigenen VM getestet; öffentliche Updates sind noch nicht freigeschaltet.
[Ruhiger Start mit Logo/Spinner und Fehlerkonsole](docs/BOOT-SPLASH.md) ist in den
Quellen vorbereitet und im installierten VM-System geprüft, noch nicht in einer
neu gebauten Live-ISO. [Abstimmung mit Claude](docs/WORK-COORDINATION.md).

Für einen sichtbaren VM-Test im Desktop-Terminal starten. KVM wird verwendet,
wenn verfügbar; sonst TCG. `--graphics soft` hilft bei VirGL-Problemen,
`--headless` startet ohne Fenster. Die VM erhält ausschließlich ihre eigene
64-GiB-qcow2-Datei. Vorhandene VM-Platten werden wiederverwendet; `--fresh-vm`
erstellt ein neues Verzeichnis und behält die bisherigen Platten.

UEFI-Code wird schreibgeschützt genutzt, UEFI-Variablen liegen separat pro VM.
Protokolle: `out/<Build-ID>/build.log`, `vm/<Name>/{serial.log,qemu.log}`.
`qmp.sock` erlaubt Screenshots und Steuerung. `--build-id ID` setzt einen
vorbereiteten Build fort; nach Quelländerungen eine neue ID verwenden.

Benötigt: Archiso 91, arch-install-scripts, squashfs-tools, grub, syslinux,
xorriso, mtools, dosfstools, Python/PyYAML, Git, QEMU und edk2-ovmf. Der Build läuft
standardmäßig ohne sudo in User-Namespaces mit eigenem Paketcache/Schlüsselbund.
Auf Systemen ohne User-Namespaces gibt es `--sudo-build`. QEMU läuft als normaler
Benutzer. Keine Paketupdates auf dem Host.

Desktop-Prüfung: `python3 tools/validate-desktop.py`. Quellen für aktive Benutzer
über `tools/install-user.py` prüfen und mit `--apply` installieren. Vorher die
Hilfsbefehle mit `sudo tools/install-system.sh` bereitstellen. Bestehende
Benutzerdaten bleiben erhalten; jede Installation legt eine Dateisicherung unter
`~/Backups/windoesnot-release/` an. Das ersetzt kein Systembackup.

[Unsere Änderungen und spätere Upstream-Updates](docs/UPSTREAM-UPDATES.md)

[Desktop-Pakete, persönliche Daten und Update-Repository](docs/PACKAGE-UPDATES.md)

[Projektwebsite windoesnot.me: Quellen, Logo und statischer Upload](website/README.md)

Die Website wird separat im privaten GitHub-Repository
`Bennch/windoesnot.me` verwaltet (`website/.git`). Der fertige Upload liegt in
`website/dist/`, zusätzlich als `out/website/windoesnot-me-static.zip`.
Cloudflare-Veröffentlichung und Domain-Zuordnung erfolgen separat.
