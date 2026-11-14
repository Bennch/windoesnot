# VM-Prüfung einer ISO (headless, GL)

Skripte, mit denen eine frisch gebaute ISO in einer Wegwerf-VM installiert und geprüft wird.
Alle Skripte laufen auf dem Entwicklungsrechner, die VM wird mit `build-and-run.sh` gestartet.

1. VM starten (GL, ohne Fenster): `./build-and-run.sh --run-only <iso> --fresh-vm --headless --graphics gl --vm-name fin --memory 4096 --cpus 2 [--language de]`
2. `tools/vmctl.py --vm-name <voller Ordnername> push tools/vm-test/guest-env.sh /tmp/guest-env.sh`
3. Installer durchfahren: `tools/vm-test/drive-install-de.sh <VM> 536` (systemd-boot, DE) oder `drive-install-en.sh <VM> 0` (GRUB, EN). Koordinaten gelten für 1280x800.
4. Installierte Platte booten: `./build-and-run.sh --boot-installed --headless --graphics gl --vm-name <VM> --memory 4096 --cpus 2`, anmelden (Benutzer `maxt`, Passwort `Test12345`, nur Wegwerf-VM).
5. Prüfungen: `tools/vmctl.py --vm-name <VM> push tools/vm-test/checks.sh /tmp/checks.sh` und `exec /usr/bin/bash /tmp/checks.sh`.
6. Szenen für Screenshots: `tools/vm-test/capture-scenes.sh <VM> maxt <Ausgabeordner>`.

Wichtig: Klicks in headless VMs kommen nur an, wenn vorher `vmctl hmp "mouse_set 4"` (USB-Tablet) gesetzt wurde. Mit GL
geht QEMU-`screendump` nicht; Bilder entstehen im Gast per `grim` (`shot.sh`). Nach jeder Installation das Quickshell-Log
auf Warnungen prüfen: `qs log -c default | grep -E "WARN|ERROR"` (so wurden mehrere stille Fehler gefunden).

## CPU-Kompatibilität (alte Prozessoren)

Die ISO mit der ältesten Ziel-CPU starten und alle gelieferten Programme prüfen:

1. `WINDOESNOT_VM_CPU=Conroe ./build-and-run.sh --run-only <iso> --fresh-vm --headless --graphics soft --vm-name cpu --memory 4096 --cpus 2 --language de` (Conroe: nur SSSE3, entspricht Pentium T4500 / Core 2).
2. `tools/vmctl.py --vm-name <voller Ordnername> push tools/vm-test/cpu-compat.sh /tmp/cpu-compat.sh`, im Gast per `exec /usr/bin/bash -c 'nohup /usr/bin/bash /tmp/cpu-compat.sh > /tmp/cc.out 2>&1 &'` starten (exec hat ein 30-s-Limit), danach `/tmp/cc.out` lesen. Erwartet: `CPU-COMPAT: OK`, `invalid-opcode traps: 0`.
3. Die ISO einer älteren Stufe schlägt hier fehl (Gegenprobe, dass der Test den Fehler findet).

`WINDOESNOT_VM_RES=1920x1080` startet die VM direkt in dieser Auflösung (für Screenshots).

## Popup-Platzierung

`tools/verify-popup-placement.py` im Gast als Benutzer der grafischen Sitzung ausführen (Umgebung wie in `checks.sh`:
`XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE`). Es öffnet jedes Panel über `qs ipc -c default call windoesnot-panels toggle <name>`
und prüft Sprünge, Bündigkeit zur Taskleiste und Monitorgrenzen.

