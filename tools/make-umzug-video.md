# Umzugsvideo erstellen

Benötigt werden Python 3, ffmpeg mit libx264 und libvpx-vp9 sowie ffprobe für den Test. Alle Dateien bleiben lokal. Das Werkzeug überschreibt gleichnamige Ausgabedateien.

Unter `deliverables/umzug-video/footage/01-windows/` mindestens eines der Bilder `windows-7.png`, `windows-8.1.png`, `windows-10.png`, `windows-11.png` ablegen. In `02-boot/`, `03-installer/` und `04-desktop/` jeweils `frame-0001.png` usw. sowie eine `fps.txt` mit positiver Aufnahmebildrate ablegen. Die Bilder werden sortiert und gleichmäßig über die Zielzeit verteilt oder wiederholt; es werden keine Zwischenbilder berechnet. Die Aufnahmebildrate wird validiert, die Zielzeit bestimmt die Wiedergabegeschwindigkeit.

```sh
python3 tools/make-umzug-video.py
python3 tools/make-umzug-video.py --footage /pfad/zum/material --out /pfad/zur/ausgabe --only web --lang de
```

Ohne Einschränkung entstehen beide Sprachen, Reel, Web-MP4 und WebM, GIF und Poster. `--only reel|web|gif` beschränkt die Ausgabe auf das gewählte Format; `--lang de|en|both` wählt die Sprache. Eingabe und Ausgabe müssen getrennte Verzeichnisse sein.

Mit `--config /pfad/dauern.json` lassen sich einzelne Dauern in Sekunden überschreiben, etwa `{"boot": 4, "installer": 8, "desktop": 6}`. Weitere Schlüssel sind `windows` (Dauer je Bild, Standard 1.3) und `end` (Standard 3). Die Standarddauer beträgt bei vier Windows-Bildern etwa 26,2 Sekunden. Bei besonders bewegtem Material kann das GIF 8 MB überschreiten; in diesem Fall meldet das Werkzeug einen Fehler und kürzere Szenen können helfen.

Test: `python3 tests/test-make-umzug-video.py`. Dieser erstellt ausschließlich temporäre, mit PLATZHALTER markierte Bilder und prüft die erzeugten Formate mit ffprobe.
