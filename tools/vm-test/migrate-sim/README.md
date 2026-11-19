# Linux-Umzugssimulation

Voraussetzungen: Python 3, `qemu-img`, `setfacl`, `unshare`, `mount`, `mkfs.ext4`, `truncate`, Dateisystem mit Hardlinks, ACLs und user-xattrs; für den Mount muss ein unprivilegierter User-Namespace erlaubt sein. Keine Root-Rechte. Arbeitsdaten auf Platte, nicht in `/tmp`; nach Gebrauch löschen:

```sh
mkdir -p out/migrate-sim
python3 tools/vm-test/migrate-sim/make-fixture.py out/migrate-sim/source
python3 tools/vm-test/migrate-sim/verify.py out/migrate-sim/source out/migrate-sim/target --uid-map 1000:1002
```

`target` ist die Wurzel des Ziel-Dateisystems; Pfade bleiben relativ zur jeweiligen Wurzel. UID- und GID-Zuordnungen (`--uid-map ALT:NEU`, `--gid-map ALT:NEU`, mehrfach möglich) gelten für tatsächlich gespeicherte numerische Besitzer. Ohne Root gehören die erzeugten Dateien dem ausführenden Benutzer; `/etc/passwd` enthält die simulierten IDs 1000 und 1001, setzt aber keine Dateibesitzer. Für einen echten Eigentümertest muss die Umgebung die IDs selbst korrekt herstellen.

Der Vergleich prüft alle vorhandenen und fehlenden Pfade, Typ, SHA-256 und Größe regulärer Dateien, Symlink-Ziele, Hardlink-Gruppen, Modi, Besitzer und sämtliche lesbaren xattrs einschließlich Linux-POSIX-ACL-xattrs. Er meldet Kategorien mit Zählern und bis zu fünf Fehlerbeispielen. Cache und Papierkorb jedes Homes werden auf beiden Seiten ignoriert. Zusätzliche Dateien außerhalb dieser Ausnahmen zählen als Fehler; daher ein isoliertes Ziel oder einen entsprechend vorbereiteten Vergleichsbaum verwenden. Exitcodes: 0 PASS, 1 Abweichung, 2 Fehler beim Vergleich. Die 2-GiB-Datei ist sparse, wird beim Hashen vollständig gelesen.

Ein Mount ist nur während des Kindprozesses sichtbar; Mount-Punkt und sichtbarer Inhalt unterscheiden sich vom darunterliegenden Verzeichnis. Er wird automatisch beim Verlassen des Namespace entfernt:

```sh
python3 tools/vm-test/migrate-sim/make-fixture.py out/migrate-sim/source --with-mount -- \
  python3 tools/vm-test/migrate-sim/verify.py out/migrate-sim/source out/migrate-sim/target
```

Für eine spätere Live-VM eine zweite Platte ohne Root erstellen:

```sh
tools/vm-test/migrate-sim/make-disk.sh out/migrate-sim/source out/migrate-sim/old-linux.qcow2
```

Das Skript erzeugt ein temporäres 4-GiB-raw-Image neben der Ausgabe, befüllt ext4 mit `mkfs.ext4 -d`, wandelt es in qcow2 um und entfernt raw. Genügend Plattenplatz vorsehen. Es wird keine VM gestartet. Die Platte als **zusätzliche** qcow2-Platte an eine eigens dafür vorbereitete Live-VM anschließen; keine bestehende VM-Platte überschreiben. Das ext4-Abbild enthält den gerade sichtbaren Baum: Für den Bind-Mount-Fall das Skript innerhalb von `--with-mount -- ...` starten. `mkfs.ext4 -d` bildet keinen separaten verschachtelten Mount im Image ab; dieser muss im Gast zusätzlich eingerichtet werden. Eigentümer entsprechen den tatsächlichen Fixture-Dateien, nicht den IDs aus passwd. ACL-/xattr-Erhalt beim Imagebau hängt von e2fsprogs ab und muss im Gast geprüft werden. qcow2 ist echt; die VDI ist ein Platzhalter.

Danach eigene Arbeitsdaten mit `rm -rf -- out/migrate-sim` entfernen. Keine persönlichen Daten verwenden.

## CachyOS-Quell-VM (Vorbereitung)

`start-cachy-vm.sh iso` startet die angegebene CachyOS-ISO mit einer eigenen
60-GiB-qcow2 unter `out/migrate-sim/`. Im Installer Btrfs, Hyprland,
`benni` und `cachy-demo` auswählen. `start-cachy-vm.sh disk` startet später
die bestehende Platte. Der Starter überschreibt keine existierende Platte;
`vm/migrate-cachy` verweist für `tools/vmctl.py` auf das Arbeitsverzeichnis.
Beide Varianten verlangen vor dem Start mindestens 8 GiB verfügbaren RAM und
laufen mit 4096 MiB, zwei CPUs und dem vorgegebenen systemd-Scope. Der
Guest-Agent-Socket funktioniert erst, wenn der Dienst im Gast läuft. Die
Einrichtung der Daten und der anschließende Live-Umzug sind durch diesen
Starter allein noch nicht automatisiert.

`populate-cachy-guest.sh` ist für den Weg nach der Installation gedacht: Es
benötigt den Fixture-Generator unter `/home/benni/make-fixture.py`, die in
seinem Kopf genannten Gastpakete und Root im `cachy-demo`-KVM-Gast. Es
legt eine echte Docker-Volume-Datei und ein Loop-Dateisystem an. Der
Fixture-Generator enthält keine verwendbaren Browser-Passwörter. Ein
Testlauf muss daher browserseitig selbst Testzugänge ergänzen, wenn diese
geprüft werden sollen. Das Skript ist für eine frische VM gedacht und
bricht bei vorhandener Fixture-Staging-Struktur ab.

`hash-home.py HOME OUTPUT.json` speichert SHA-256 und Größen regulärer
Dateien sowie Symlink-Ziele; Cache, Papierkorb und aktuell eingehängte
Dateisysteme werden ausgespart. Dieses JSON ist ein eigenes Format, kein
Eingabeformat von `verify.py`: Letzteres vergleicht Verzeichnisbäume direkt.

`start-move-vm.sh` startet die angegebene Live-ISO mit einer eigenen
40-GiB-Zielplatte unter `out/migrate-sim/live/target.qcow2` und hängt
`cachy-src.qcow2` ausdrücklich schreibgeschützt an. Die Quell-VM vorher
sauber herunterfahren. Für den Vergleich geschützter Konfigurationsordner
müssen diese aus `Umzug-benni/original` in einem separaten Vergleichsbaum
an ihre ursprünglichen Pfade zurückgelegt werden; WinDoesNot schützt diese
Ordner absichtlich vor dem Überschreiben. Ein Vergleich muss die
Verzeichnismodi, Dateiinhalte und Hardlinks weiter prüfen.

`run-move-test.sh` überträgt den aktuellen Arbeitsbaumstand von `mirror.py`
und startet `run-move-test-guest.sh` in der laufenden Live-VM. Dieses neu
zusammengestellte Automatisierungsskript ist syntaktisch geprüft; der
beschriebene Lauf wurde mit denselben Schritten einzeln ausgeführt, nicht
mit diesem Skript als Ganzem. Es verweigert das Formatieren, wenn auf der
Zielplatte bereits ein Dateisystem erkannt wird. Ergebnis und Logs liegen
im Gast unter `/root/move-test.status`, `/root/move-test.log` und auf der
Zielplatte unter `/mnt/move-target/`. Eine bestehende Testplatte muss für
einen neuen Lauf ausdrücklich durch eine neue leere ersetzt werden.
