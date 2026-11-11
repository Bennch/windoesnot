# WinDoesNotMac — Mac-Testpaket

**Private Testversion für Apple Silicon. Kein fertiger Linux-Installer.**
Die Apps lassen sich unter dem normalen macOS des MacBooks testen. Nicht in der
laufenden Asahi-Linux-Sitzung öffnen. Es gibt noch kein vollständiges geprüftes
ARM-Systemimage. Deshalb bleibt „Installation starten“ in diesem Paket gesperrt.

## Downloads

Öffne die [privaten Releases](https://github.com/Bennch/WinDoesNotMac/releases)
mit dem GitHub-Konto, das Zugriff auf diese Repo hat. Das neueste **Mac App Test
Kit** enthält:

| Datei | Inhalt |
| --- | --- |
| `WinDoesNotMac-Installer-arm64.zip` | Electron-App für macOS, Deutsch/Englisch, animierte Anleitung und sicherer Testlauf |
| `WinDoesNotMac-Recovery-Preview-arm64.zip` | Native AppKit-Vorschau der Recovery-Oberfläche; startet ohne Recovery-Backend im Testmodus |
| `WinDoesNotMac-Source.zip` | Kompletter Quellstand dieses Builds einschließlich Buildskripten |
| `TESTANLEITUNG.md` | Diese Anleitung |
| `SHA256SUMS` | Prüfsummen der ZIP-Dateien |

Falls noch kein Release vorhanden ist: Der [Mac-Build](https://github.com/Bennch/WinDoesNotMac/actions/workflows/mac-installer-preview.yml)
muss erst erfolgreich durchlaufen. Downloads und Build-Artefakte bleiben privat.

## Auf dem MacBook testen

1. Unter **macOS** die beiden App-ZIPs herunterladen und entpacken. Benötigt wird
   ein Apple-Silicon-Mac mit macOS 13 oder neuer für die Electron-App.
2. Optional alle ZIPs und `SHA256SUMS` im selben Ordner prüfen:
   `shasum -a 256 -c SHA256SUMS`.
3. `WinDoesNotMac Installer.app` öffnen. Die Vorschau weist darauf hin, dass noch
   kein geprüftes Image gebündelt ist. Sie fordert keine Administratorfreigabe an.
4. **Testlauf / Test run** wählen. Beispielauswahl und verdecktes Eingabefeld
   testen. Dafür nur ein frei erfundenes Testpasswort eingeben, keine echten
   Zugangsdaten. Dieser Test startet kein Installer-Backend und verändert keine
   Partitionen, Firmware oder Systemeinstellungen.
5. **Animierte Anleitung ansehen** öffnen, Deutsch/Englisch umschalten, alle
   Schritte ansehen und optional speichern/drucken. Nach dem Ausschalten ist
   das App-Fenster auf demselben Mac nicht verfügbar.
6. `WinDoesNotMac Recovery Preview.app` öffnen. Ohne `step2.sh` startet sie
   ausdrücklich im **TESTMODUS**. „Weiter“ zeigt die vorgesehenen Recovery-Phasen;
   es werden keine Apple-Sicherheitsbefehle, kein Shutdown und kein Reboot ausgeführt.

Die Pakete sind Entwicklungsbuilds ohne Developer-ID-Notarisierung. Wenn macOS
das Öffnen verhindert, kann für diese bewusst heruntergeladene Test-App unter
**Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen** eine
Ausnahme angeboten werden. Nicht pauschal die macOS-Sicherheit deaktivieren.

Notiere macOS-Version und Mac-Modell sowie: Starten beide Apps? Sind Texte,
Skalierung, Sprachwechsel und Animationen lesbar? Funktioniert die Bedienung mit
der Tastatur? Werden Passwortfelder nach Bestätigung geleert? Bei Fehlern reichen
Fehlermeldung und Schritt; keine Passwörter oder persönlichen Installationslogs teilen.

## Was dieser Test noch nicht prüft

Ein App-Start unter macOS validiert **nicht** die echte Recovery-Umgebung oder
eine Linux-Neuinstallation. Dafür fehlen weiterhin das fertige ARM-Image und der
vollständige Installer-Build. Die native Recovery-App wird bei späteren Builds
in die von Asahi vorbereitete Recovery-Installation eingebunden. Kann der native
Launcher seine Voraussetzungen dort nicht laden, bleibt der Terminal-Abschluss
verfügbar. Bitte diese Vorschau nicht manuell in bestehende Recovery-Volumes kopieren.

## Build aus dem Quellpaket

Mit Node.js 22+ und Python 3:

```sh
cd installer/mac-app
npm ci
npm test
npm run package:mac
```

Die App entsteht unter `out/mac-app/`. Für die native App wird zusätzlich das
macOS SDK aus Xcode oder den Command Line Tools benötigt:

```sh
mkdir -p out
cp -R 'installer/asahi/src/step2/Finish Installation.app' 'out/Recovery Preview.app'
bash tools/build-recovery-app.sh 'out/Recovery Preview.app'
```

Den echten macOS-Backendbaum später als `backend/` über
`WINDOESNOT_MAC_BACKEND=/absoluter/pfad/backend npm run package:mac` beilegen.
Er muss den eingebetteten Python-Interpreter, `release.json` mit
`imageValidated: true`, HTTPS-Release-Endpunkten, `metadataSha256` und die dazu
passende `installer_data.json` ausschließlich für WinDoesNotMac enthalten.
Den Marker erst nach einem tatsächlichen vollständigen Hardwaretest setzen.
Details: [ARM-Image-Build](../installer/asahi/IMAGE-BUILD.md).
