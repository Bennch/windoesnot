#!/usr/bin/env python3
"""Stage only the authorized backup/auth changes on top of the current host code."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / 'desktop/config/quickshell/default'
HOST = Path.home() / '.config/quickshell/default'
STAGE = ROOT / 'build/backup-integration/host'
NEW_FILES = ['settings/BackupsCategory.qml', 'widgets/AuthenticationCard.qml', 'widgets/SystemAuthentication.qml']
STRINGS = {
 'de': {'backups.timerInactive':'Der Zeitgeber ist derzeit nicht aktiv. Anwenden aktiviert den gespeicherten Plan.', 'auth.title':'Administrator-Freigabe','auth.confirm':'Bestätigen','auth.wait':'Freigabe wird geprüft …',
        'backups.scopeHint':'Sicherungspunkte schützen den Systemzustand. Sie ersetzen keine externe Sicherung persönlicher Dateien.',
        'backups.authHint':'Für Änderungen ist eine Administrator-Freigabe erforderlich. Das Anzeigen der Sicherungspunkte benötigt kein Passwort.',
        'backups.scheduleHint':'Snapper erstellt stündlich Sicherungspunkte und behält die ausgewählte Anzahl je Zeitraum. Bestehende Punkte werden hierdurch nicht sofort gelöscht.',
        'backups.scheduleCustom':'Ein bestehender Aufbewahrungsbereich wird beim Anwenden durch die angezeigte Anzahl ersetzt.',
        'backups.cancelled':'Freigabe abgebrochen. Es wurde nichts geändert.'},
 'en': {'backups.timerInactive':'The timer is currently inactive. Apply activates the saved schedule.', 'auth.title':'Administrator authorization','auth.confirm':'Confirm','auth.wait':'Checking authorization …',
        'backups.scopeHint':'Restore points protect the system state. They do not replace an external backup of personal files.',
        'backups.authHint':'Changes require administrator authorization. Viewing restore points does not require a password.',
        'backups.scheduleHint':'Snapper creates hourly restore points and retains the selected number for each period. Existing points are not deleted immediately.',
        'backups.scheduleCustom':'Applying replaces an existing retention range with the displayed count.',
        'backups.cancelled':'Authorization cancelled. Nothing was changed.'}}


def modify_settings(text):
    if 'id: backupAuthenticationOverlay' in text:
        return text
    text = text.replace('import "i18n/Lang.js" as Lang', 'import "i18n/Lang.js" as Lang\nimport "widgets"')
    text = text.replace('property bool fileDialogOpen: false', 'property bool fileDialogOpen: false\n    property var authentication: null\n    readonly property bool backupAuthenticationActive: authentication !== null && authentication.embedded')
    # Maintain the existing focus handling, especially file/color picker behavior.
    text = text.replace('!settingsMenu.fileDialogOpen && !settingsMenu.colorPaletteVisible', '!settingsMenu.fileDialogOpen && !settingsMenu.backupAuthenticationActive && !settingsMenu.colorPaletteVisible')
    text = text.replace('if (!settingsMenu.fileDialogOpen) {', 'if (!settingsMenu.fileDialogOpen && !settingsMenu.backupAuthenticationActive) {')
    pos = text.rfind('}')
    return text[:pos] + '''
    Rectangle {
        id: backupAuthenticationOverlay
        anchors.fill: parent
        z: 10000
        visible: settingsMenu.backupAuthenticationActive
        color: "#99000000"
        MouseArea { anchors.fill: parent; onWheel: (wheel) => wheel.accepted = true }
        AuthenticationCard {
            anchors.centerIn: parent
            width: Math.min(460, parent.width - 40)
            height: implicitHeight
            settingsMenu: settingsMenu
            flow: settingsMenu.backupAuthenticationActive ? settingsMenu.authentication.flow : null
        }
    }
''' + text[pos:]


def modify_shell(text):
    if 'id: systemAuthentication' in text:
        return text
    marker = 'Settings {\n    id: settingsMenu'
    if text.count(marker) != 1:
        raise ValueError('Expected exactly one Settings instance')
    return text.replace(marker, '''SystemAuthentication {
    id: systemAuthentication
    settingsMenu: settingsMenu
}

Settings {
    id: settingsMenu
    authentication: systemAuthentication''')


def translations(text, language):
    for key, value in STRINGS[language].items():
        if json.dumps(key) not in text:
            text = text.replace('var strings = {', 'var strings = {\n    ' + json.dumps(key) + ': ' + json.dumps(value, ensure_ascii=False) + ',', 1)
    return text


def main():
    for base in (SHARED, STAGE):
        base.mkdir(parents=True, exist_ok=True)
        for name, modifier in [('Settings.qml', modify_settings), ('shell.qml', modify_shell)]:
            original = (SHARED if base == SHARED else HOST) / name
            (base / name).write_text(modifier(original.read_text()))
        for language in STRINGS:
            relative = 'i18n/' + language + '.js'
            original = (SHARED if base == SHARED else HOST) / relative
            (base / 'i18n').mkdir(exist_ok=True)
            (base / relative).write_text(translations(original.read_text(), language))
    qmldir = (HOST / 'widgets/qmldir').read_text()
    for name in ('AuthenticationCard', 'SystemAuthentication'):
        if name + ' 1.0' not in qmldir:
            qmldir += '\n' + name + ' 1.0 ' + name + '.qml\n'
    (STAGE / 'widgets').mkdir(exist_ok=True)
    (STAGE / 'widgets/qmldir').write_text(qmldir)
    for name in NEW_FILES:
        target = STAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SHARED / name, target)
    print('Staged only backup/auth files; host is unchanged: ' + str(STAGE))


if __name__ == '__main__':
    main()
