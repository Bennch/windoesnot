# Debug-Kanal

Temporärer, tokengebundener LAN-Kanal für ein WinDoesNot-Live-Testgerät. Benötigt Python 3, `ssh-keygen` und auf dem Testgerät `curl`, `sudo`, `timeout` sowie `bash`.

```sh
tools/debug-channel/debug-channel start --bind 192.168.1.20
tools/debug-channel/debug-channel run 'lspci -nnk'
tools/debug-channel/debug-channel push ./patch.qml ~/.config/quickshell/patch.qml
tools/debug-channel/debug-channel hot-patch desktop/config/quickshell/default/shell.qml
```

`--bind` muss eine konkrete lokale Adresse sein. Für Wildcard-Bind sind `--allow-any` und `--advertise HOST` (vom Testgerät erreichbare Adresse) erforderlich. Standardlaufzeit: 2 Stunden; Ende auch mit Strg+C. Queue, Uploads, Ausgaben und Zugriffslog liegen im privaten Laufzeitverzeichnis (`$XDG_RUNTIME_DIR`, sonst `/tmp`). Der temporäre ed25519-Schlüssel liegt außerhalb des Repos; `start` zeigt seinen Pfad und einen SSH-Befehl. Er wird beim Ende des Servers gelöscht.

Nur im vertrauenswürdigen LAN und nur auf ausdrücklich ausgewählten Live-/Testgeräten verwenden, niemals auf Produktivsystemen. Der zufällige Token ist ein Bearer-Geheimnis: die Setup-Zeile enthält ihn und erlaubt einem Besitzer der Zeile, als root beliebige Befehle auszuführen. Nicht teilen oder in Tickets/Logs kopieren. Der Server und sein lokaler SSH-Privatschlüssel enden spätestens mit der Laufzeit oder beim Server-Neustart; am Testgerät beendet `sudo touch /tmp/stop-agent` den Agenten. Ein Neustart beendet den Live-System-Agenten. Die vom Setup hinzugefügten SSH-Zeilen werden beim Agent-Ende entfernt; vorhandenes sshd wird nicht gestoppt.

## Testgerät und bekannte Fallstricke

- Auf dem Text-Terminal mit Strg+Alt+F2 als `liveuser` anmelden und nur die ausgegebene `curl .../TOKEN/s | sh`-Zeile ausführen.
- `grim` wird bewusst nicht aufgerufen: auf alter Hardware kann es hängen. `bluetoothctl` läuft ausschließlich mit Timeout, da ohne Dienst/Adapter kein verlässliches Ende garantiert ist. Diagnose- und Queue-Befehle haben Timeouts; Queue-Befehle maximal 180 Sekunden und Ausgaben maximal 400 KB.
- Für GUI-Befehle `G ...` verwenden; die Funktion setzt die Liveuser-Hyprland-/DBus-Umgebung. `hot-patch` legt Dateien flach nach `~/.config/quickshell` und ruft `windoesnot-restart-shell` auf. `G` übernimmt die Renderer-Einstellungen der Hyprland-Sitzung (`QT_QUICK_BACKEND`, `GSK_RENDERER`, `LIBGL_ALWAYS_SOFTWARE`), damit neu gestartete Programme sich wie in der echten Sitzung verhalten.
- Kein `pkill -f` mit einem Suchmuster, das auch die eigene Shell-/Befehlszeile trifft. Netzwerkdiagnose bevorzugt `ip`/`nmcli`; `nmcli`-Abfragen ebenfalls begrenzen und keine Ausgabe mit Zugangsdaten weitergeben.

Offline-Tests: `python3 -m unittest discover -s tests -p 'test_debug_channel.py'` (aus dem Repository, ohne VM oder Paket-/ISO-Build).

Hinweis: `debug-channel start` gibt die Setup-Zeile erst nach dem Start aus; bei Umleitung in eine Datei `python3 -u` verwenden. Die Setup-Datei lässt sich auch per `curl <Server>/<Token>/s -o wdn-ssh.sh` erzeugen und per LocalSend verschicken (dann auf dem Gerät in einem Terminal `sh wdn-ssh.sh` ausführen, nicht per Doppelklick).

