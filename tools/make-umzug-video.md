# Umzugsvideo erstellen

Benötigt werden Python 3 mit NumPy und Pillow sowie ffmpeg mit libx264, AAC und libvpx-vp9; für Tests zusätzlich ffprobe und ImageMagick (`magick`). Eingaben bleiben unverändert, gleichnamige Ausgaben werden überschrieben.

Unter `footage/01-windows/` mindestens eines der Bilder `windows-7.png`, `windows-8.1.png`, `windows-10.png`, `windows-11.png` ablegen. In `02-boot/`, `03-installer/` und `04-desktop/` jeweils `frame-0001.png` usw. und eine `fps.txt` mit positiver Aufnahmebildrate ablegen. Bilder mit mittlerer RGB-Helligkeit unter 2 werden überall ausgelassen; vollständig dunkle Szenen sind ein Fehler. Die übrigen Bilder werden chronologisch gleichmäßig ausgewählt oder wiederholt, ohne Zwischenbilder zu erzeugen. Die Aufnahmebildrate wird validiert; die Zielzeit bestimmt die Wiedergabegeschwindigkeit.

```sh
python3 tools/make-umzug-video.py --footage /pfad/zum/material --out /pfad/zur/ausgabe
python3 tools/make-umzug-video.py --footage /pfad/zum/material --out /pfad/zur/ausgabe --only reel --lang de --music /pfad/zur/musik.wav --music-start 0 --duration 20 --cut-on kicks --every 2
```

Ohne Einschränkung entstehen beide Sprachen, Reel, Web-MP4 und WebM, GIF und Poster. `--only reel|web|gif` und `--lang de|en|both` beschränken die Ausgabe. Eingabe und Ausgabe müssen getrennte Verzeichnisse sein. `--preview-without-windows` erlaubt eine unvollständige Vorschau ohne Windows-Bild; diese ist nicht zur Veröffentlichung bestimmt.

`--config /pfad/config.json` überschreibt Dauern in Sekunden und die Reihenfolge, z. B. `{"order":["windows","installer","boot","desktop"],"installer":9,"boot":6,"desktop":6}`. `order` muss alle vier Szenen genau einmal enthalten. Standardwerte: Windows 1,3 Sekunden je Bild, Installer 9, Boot 6, Desktop 6 und Schlusskarte (`end`) 3. Das GIF darf höchstens 8 MB groß sein.

`--music` akzeptiert von ffmpeg lesbare MP3-, WAV-, FLAC- und OGG-Dateien. Nur das Reel erhält Musik und Beat-Schnitt; die übrigen Formate behalten ihre normalen Dauern. Die Musik wird für die Analyse auf 44,1 kHz mono dekodiert, das Reel erhält AAC mit 192 kbit/s und 0,2 Sekunden Ein- und einer Sekunde Ausblendung. `--music-start` wählt den Beginn in Sekunden, `--duration` die Länge (Standard 20 Sekunden). `--cut-on kicks|beats|bars` wählt das erkannte Raster bzw. jeden vierten Schlag; `--every N` verwendet zusätzlich nur jeden N-ten Rasterpunkt. Kick und Beat verwenden dasselbe tiefbassbasierte Raster. Die Analyse nutzt Tiefbass-Spektrum, Energieanstieg und Spectral Flux, adaptive Peaks sowie Autokorrelation und Phasenglättung. `beats.json` enthält geschätztes BPM und Rasterzeiten relativ zum Anfang der Eingabedatei. Das Verfahren setzt ein einigermaßen regelmäßiges Tempo voraus; bei ungeeignetem Material oder zu wenigen Schnitten wird ein Fehler gemeldet. Die Szenen bekommen proportional zur eingestellten Dauer mindestens zwei Schnitte; die Schlusskarte belegt den letzten Abschnitt. Die Musikdatei wird nicht kopiert.

Test: `python3 tests/test-make-umzug-video.py` oder `env -u LC_ALL python3 tools/run-offline-tests.py`. Der Videotest erzeugt temporäre Platzhalter und eine synthetische 124-BPM-Spur und prüft Beat-Abweichung, Formate und Audiospur mit ffprobe.
