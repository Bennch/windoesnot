"""Offline companion for the physical recovery handoff; never controls the Mac."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

COPY = {
    "de": {
        "title": "Dein Mac. Schritt für Schritt.",
        "intro": "Die Dateien sind installiert. Jetzt erlaubst du deinem Mac, WinDoesNotMac zu starten. Wir begleiten dich durch den Wechsel zu Apple Recovery.",
        "language": "Sprache", "back": "Zurück", "next": "Nächster Schritt",
        "step": "Schritt", "of": "von", "expected": "Daran erkennst du es",
        "help": "Wenn es anders aussieht", "overview": "Alle Schritte anzeigen",
        "save": "Anleitung speichern", "motion": "Animationen pausieren",
        "resume": "Animationen fortsetzen", "print": "Drucken / als PDF sichern",
        "manual": "Du blätterst selbst weiter. Diese Anleitung erkennt den Zustand deines Macs nicht.",
        "offline": "Vor dem Ausschalten: Öffne diese Anleitung auch auf einem zweiten Gerät oder sichere sie als PDF. Auf diesem Mac ist sie während des Neustarts nicht sichtbar. Die gespeicherte HTML-Datei funktioniert offline.",
        "illustration": "Schematische Darstellung – Apples Ansicht kann je nach Modell und Sprache abweichen.",
        "ready": "Wenn du die Anleitung gesichert hast, kehre zum Terminal zurück. Erst dort bestätigst du das Ausschalten mit Enter.",
        "steps": [
            ["Vorbereiten", "Lass das Netzteil angeschlossen. Sichere diese Anleitung, lies alle Schritte und kehre danach zum Installer-Terminal zurück. Bestätige dort das Ausschalten mit Enter.", "Der Installer wartet auf deine Bestätigung. Er schaltet den Mac nicht allein aus.", "Noch nicht bereit? Lass das Terminal einfach offen.", "prepare"],
            ["Ganz ausschalten lassen", "Warte nach dem Ausschalten mindestens 25 Sekunden. Drücke währenddessen keine Taste.", "Das Display bleibt vollständig dunkel. Warte trotzdem die vollen 25 Sekunden.", "Ein schwarzes Display allein bedeutet noch nicht, dass der Mac vollständig aus ist.", "wait"],
            ["Einmal drücken und gedrückt halten", "Drücke jetzt den Einschaltknopf / Touch ID und halte ihn ohne Unterbrechung gedrückt. Nicht erst kurz drücken und dann erneut halten.", "Lass erst los, wenn ein Hinweis zum Laden der Startoptionen oder ein Ladeindikator erscheint. Die Formulierung kann abweichen.", "Startet direkt macOS? Fahre den Mac vollständig herunter, warte 25 Sekunden und versuche es mit durchgehend gedrücktem Knopf erneut.", "hold"],
            ["Dein neues System auswählen", "Warte auf die Startvolumes. Wähle „{volume}“ und bestätige die Auswahl.", "Das von dir benannte neue Installationsvolume ist ausgewählt.", "Fehlt das Volume? Starte macOS und führe den Installer erneut aus. Nutze dort gegebenenfalls die angebotene Option zum Fortsetzen / Reparieren (p). Starte keine neue Partitionierung auf Verdacht.", "volume"],
            ["Apple Recovery öffnen lassen", "Ein Dialog von macOS Recovery ist an dieser Stelle erwartet. Falls Apple nach einem wiederherzustellenden Volume fragt, wähle deine normale macOS-Installation und klicke auf Weiter.", "Apple fragt gegebenenfalls nach einem macOS-Benutzer und dessen Passwort.", "Ein Recovery-Dialog bedeutet hier nicht, dass du macOS neu installieren sollst. Wird ausdrücklich eine Neuinstallation verlangt oder startet der Mac im Kreis, kehre über die Startoptionen zu macOS zurück und nutze die Fortsetzen-Option des Installers.", "recovery"],
            ["Startfreigabe bestätigen", "Folge dem WinDoesNotMac-Installer in Recovery. Gib deine macOS-Administratordaten nur in den tatsächlichen System-/Terminal-Abfragen ein. Der Ablauf kann sie zweimal anfordern.", "Der Installer richtet die Startfreigabe für das neue System ein. Die Sicherheitsrichtlinie deiner bestehenden macOS-Installation bleibt davon unberührt.", "Diese Anleitung fragt nie nach einem Passwort. Bei einer Fehlermeldung lies die Ausgabe im Installer; Wiederholen ist dort ausdrücklich möglich.", "auth"],
            ["WinDoesNotMac starten", "Wenn der Installer den Abschluss meldet, bestätige den Neustart dort. Danach startet dein neues System.", "Für unsere geplanten Images folgt die grafische Ersteinrichtung für Benutzer, Sprache und Tastatur. Diese Calamares-Integration ist noch in Arbeit.", "Startet wieder macOS? Öffne durch Gedrückthalten des Einschaltknopfs beim Einschalten die Startoptionen und wähle „{volume}“.", "done"],
        ],
    },
    "en": {
        "title": "Your Mac. One step at a time.",
        "intro": "The files are installed. Next, you will allow your Mac to start WinDoesNotMac. We will guide you through the handoff to Apple Recovery.",
        "language": "Language", "back": "Back", "next": "Next step",
        "step": "Step", "of": "of", "expected": "What you should see",
        "help": "If it looks different", "overview": "Show all steps",
        "save": "Save guide", "motion": "Pause animations",
        "resume": "Resume animations", "print": "Print / save as PDF",
        "manual": "You advance the steps yourself. This guide cannot detect your Mac’s state.",
        "offline": "Before shutting down: open this guide on another device or save it as a PDF. It will not be visible on this Mac during the restart. The saved HTML file works offline.",
        "illustration": "Schematic illustration — Apple’s screens may differ by model and language.",
        "ready": "Once you have saved the instructions, return to Terminal. Only pressing Enter there confirms shutdown.",
        "steps": [
            ["Get ready", "Keep the power adapter connected. Save this guide, read every step, then return to the installer terminal. Press Enter there to confirm shutdown.", "The installer waits for your confirmation. It will not shut down the Mac on its own.", "Not ready yet? Leave the terminal open.", "prepare"],
            ["Let it shut down completely", "After shutdown, wait at least 25 seconds. Do not press any keys yet.", "The display stays completely dark. Still wait the full 25 seconds.", "A black display alone does not mean the Mac has finished shutting down.", "wait"],
            ["Press once and keep holding", "Press and hold the power / Touch ID button continuously. Do not tap it first and then press it again.", "Release only when you see a startup-options loading message or loading indicator. The wording may vary.", "If macOS starts directly, shut down fully, wait 25 seconds and retry with one continuous press.", "hold"],
            ["Choose your new system", "Wait for the startup volumes. Select “{volume}” and confirm your choice.", "The new installation volume with your chosen name is selected.", "Volume missing? Start macOS and run the installer again. Use its offered resume / repair option (p) if available. Do not repartition just to try again.", "volume"],
            ["Let Apple Recovery open", "A macOS Recovery dialog is expected here. If asked to select a volume to recover, choose your normal macOS installation and click Next.", "Apple may ask for a macOS user and their password.", "This Recovery dialog does not mean you should reinstall macOS. If explicitly told to reinstall, or if the Mac loops, return to macOS through startup options and use the installer’s resume option.", "recovery"],
            ["Authorize the new system to boot", "Follow the WinDoesNotMac installer in Recovery. Enter your macOS administrator credentials only in the actual system / terminal prompts. The process may ask twice.", "The installer configures the new system’s boot policy. Your existing macOS installation’s security policy is unaffected.", "This guide never asks for a password. If an operation fails, read the installer output; it provides explicit retry prompts.", "auth"],
            ["Start WinDoesNotMac", "When the installer reports completion, confirm the restart there. Your new system will then boot.", "Our planned images will show graphical first-boot setup for user, language and keyboard. This Calamares integration is still being developed.", "If macOS starts instead, hold the power button while powering on to open startup options and choose “{volume}”.", "done"],
        ],
    },
}


def render(volume, language="de"):
    template = Path(__file__).with_name("recovery-guide.html").read_text()
    # Escape script delimiters even when a user-supplied volume label contains HTML.
    payload = json.dumps({"copy": COPY, "volume": volume,
                          "language": language if language in COPY else "de"}, ensure_ascii=False)
    return template.replace("/*GUIDE_DATA*/null", payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def show(volume, language="de"):
    """Open a companion if possible; failure never removes the terminal fallback."""
    directory = Path(tempfile.mkdtemp(prefix="windoesnot-guide-"))
    directory.chmod(0o755)
    path = directory / "WinDoesNotMac.html"
    path.write_text(render(volume, language))
    path.chmod(0o644)
    print(f"\nOffline guide / Offline-Anleitung: {path}")
    if sys.platform == "darwin":
        command = ["/usr/bin/open", str(path)]
        if os.geteuid() == 0:
            user = os.environ.get("SUDO_USER", "")
            try:
                account = pwd.getpwnam(user)
            except KeyError:
                return path
            if account.pw_uid == 0:
                return path
            command = ["/usr/bin/sudo", "-u", account.pw_name, *command]
        try:
            subprocess.run(command, check=True, timeout=10, capture_output=True)
        except (OSError, subprocess.SubprocessError):
            print("Open the file manually / Datei bitte manuell öffnen.")
    return path


def terminal_steps(volume, language):
    copy = COPY[language]
    print("\n" + copy["title"] + "\n" + copy["intro"] + "\n")
    print(copy["offline"] + "\n")
    for index, step in enumerate(copy["steps"], 1):
        print(f"{index}. {step[0]}\n   {step[1].replace('{volume}', volume)}")
        print(f"   {copy['expected']}: {step[2].replace('{volume}', volume)}")
        print(f"   {copy['help']}: {step[3].replace('{volume}', volume)}\n")
    print(copy["ready"])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--volume", default="WinDoesNotMac")
    parser.add_argument("--language", choices=COPY, default="de")
    args = parser.parse_args()
    args.output.write_text(render(args.volume, args.language))
