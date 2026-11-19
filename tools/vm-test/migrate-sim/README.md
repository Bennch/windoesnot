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
