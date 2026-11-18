#!/usr/bin/env python3
"""Build the Windows bundle using the local SDK and restored project dependencies."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/windows-bundle'
PROJECT = ROOT / 'igloo-windoesnot'
SDK = ROOT / 'build/host-tools/dotnet'
START = r'''@echo off
setlocal
for /f "tokens=2 delims=[]" %%v in ('ver') do set "osver=%%v"
echo %osver% | findstr /r /c:" 6\.1\." /c:" 6\.2\." /c:" 6\.3\." >nul
if not errorlevel 1 (call "%~dp0legacy\WinDoesNotSetup.cmd" & exit /b %errorlevel%)
echo %osver% | findstr /r /c:" 10\.0\." >nul
if not errorlevel 1 (
  set "WDN_APP=%~dp0app\WinDoesNotSetup.exe"
  powershell.exe -NoProfile -Command "Start-Process -FilePath $env:WDN_APP -Verb RunAs"
  exit /b
)
echo Unsupported Windows version: %osver%
pause
exit /b 1
'''
README = '''WinDoesNot Umzug / Windows move tool

DE: Experimentell: noch nicht auf allen Windows-Versionen vollstaendig getestet.
ZIP vollstaendig entpacken und "Umzug starten.cmd" starten. Windows 7/8.1
startet den Exporter (PowerShell 2 und .NET Framework 3.5), Windows 10/11
die eigenstaendige 64-Bit-App (Windows 10 ab Build 17763). Eine UAC-Abfrage
ist erforderlich; Administratorzugang wird benoetigt. Bei SmartScreen nur nach
Pruefung der SHA256-Summe: Weitere Informationen -> Trotzdem ausfuehren.
Auswahl speichern: Das Programm schreibt C:\\WinDoesNotHandoff auf das
Systemlaufwerk; ein vorhandenes Handoff wird ersetzt. Windows-Quelldateien
werden dabei nicht geloescht. WLAN-Schluessel koennen im Export im Klartext
stehen. Zugang schuetzen, Handoff nach erfolgreichem Umzug loeschen. Browser-
Passwoerter sind nicht garantiert; Chrome/Edge v20 werden nicht uebernommen.
Die App (Windows 10/11) und der Exporter (Windows 7/8.1, Schaltflaeche "USB-Stick
erstellen..." auf der letzten Seite) laden auf Wunsch die aktuelle WinDoesNot-ISO, pruefen
sie per SHA-256 und schreibt sie auf einen USB-Stick. ACHTUNG: Der gewaehlte
Stick wird vollstaendig GELOESCHT; nur USB-Wechselmedien mit 512-Byte-Sektoren
werden angeboten, zur Bestaetigung muss LOESCHEN getippt werden. Windows
selbst wird dabei nicht veraendert. Danach vom Stick starten (Bootmenue) und im
Installer "Parallel dazu installieren" waehlen.
Sichere wichtige Daten auf einem separaten Laufwerk. Im WinDoesNot-Installer
Windows-Daten auswaehlen und die Zusammenfassung pruefen. Rueckweg: Vorgang
abbrechen und Windows normal starten; das Handoff kann entfernt werden.

EN: Experimental: not yet fully tested on every Windows version. Extract the complete ZIP and run
"Umzug starten.cmd". Windows 7/8.1 uses the PowerShell 2 / .NET Framework
3.5 exporter; Windows 10/11 uses the self-contained 64-bit app (Windows 10
build 17763 or newer). UAC and administrator access are required. After
verifying SHA256, SmartScreen may offer More info -> Run anyway.
Saving writes C:\\WinDoesNotHandoff on the system drive and replaces any prior
handoff; Windows source files are not deleted by this operation. Exported Wi-Fi
keys can be plaintext; protect the folder and remove it after migration.
Browser passwords are not guaranteed; Chrome/Edge v20 cannot be migrated.
On request the app (Windows 10/11) and the exporter (Windows 7/8.1, button "Create USB
stick..." on the last page) download the current WinDoesNot ISO,
verifies it with SHA-256 and writes it to a USB stick. WARNING: the chosen
stick is completely ERASED; only removable USB drives with 512-byte sectors
are offered, and you must type ERASE to confirm. Windows itself is not changed.
Then boot from the stick (boot menu) and choose "Install alongside".
Back up important data separately. Select Windows data in the WinDoesNot
installer and check the summary. To return, cancel and boot Windows normally;
the handoff can be removed.
'''
def main():
    v = json.loads((ROOT / 'packaging/version.json').read_text())
    version = f"{v['version']}-{v['release']}"
    OUT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(DOTNET_ROOT=str(SDK), DOTNET_CLI_HOME=str(PROJECT / '.dotnet-home'), NUGET_PACKAGES=str(PROJECT / '.nuget/packages'), DOTNET_CLI_TELEMETRY_OPTOUT='1')
    with tempfile.TemporaryDirectory(prefix='publish-', dir=OUT) as tmp:
        publish = Path(tmp)
        subprocess.run([str(SDK / 'dotnet'), 'publish', str(PROJECT / 'src/Igloo.App/Igloo.App.csproj'), '-c', 'Release', '-r', 'win-x64', '--self-contained', 'true', '--no-restore', '-p:EnableWindowsTargeting=true', '-p:DebugType=None', '-p:DebugSymbols=false', '-o', str(publish)], cwd=ROOT, env=env, check=True)
        files = {'Umzug starten.cmd': START.replace('\n', '\r\n').encode('ascii'), 'README.txt': README.replace('\n', '\r\n').encode('ascii')}
        for name in ('WinDoesNotSetup.cmd', 'WinDoesNotSetup.ps1', 'WinDoesNotStick.ps1', 'WinDoesNotStick.cs'):
            files['legacy/' + name] = (ROOT / 'windows' / name).read_bytes()
        for p in sorted(publish.rglob('*')):
            if p.is_symlink():
                raise ValueError(f'Unexpected symlink: {p}')
            if p.is_file() and p.suffix.lower() not in ('.pdb',):
                files['app/' + p.relative_to(publish).as_posix()] = p.read_bytes()
        if 'app/WinDoesNotSetup.exe' not in files:
            raise RuntimeError('Publish did not produce the executable')
        target = OUT / f'WinDoesNot-Umzug-{version}.zip'
        temp = OUT / (target.name + '.tmp')
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temp.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        target.with_suffix(target.suffix + '.sha256').write_text(f'{digest}  {target.name}\n', encoding='ascii')
        print(target, target.stat().st_size, digest)
if __name__ == '__main__':
    main()
