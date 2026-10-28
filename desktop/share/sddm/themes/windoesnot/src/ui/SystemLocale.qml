import QtQuick
import QtCore

// Read the system selection for each new greeter, even when the SDDM daemon
// still has the language inherited at boot. No settings are written here.
QtObject {
    id: language
    property string name: "en_US"
    readonly property bool german: name.indexOf("de") === 0
    readonly property var locale: Qt.locale(name)
    property Settings reader: Settings { location: "file:///etc/locale.conf" }
    function refresh() {
        reader.sync()
        const selected = String(reader.value("LC_MESSAGES", "")) || String(reader.value("LANG", "en_US.UTF-8"))
        name = /^(de|en)([_\.\-]|$)/.test(selected) ? selected.split(".")[0] : "en_US"
    }
    function text(key) {
        const de = {userName: "Benutzername", password: "Passwort", login: "Anmelden", shutdown: "Herunterfahren", reboot: "Neustarten", suspend: "Ruhezustand", session: "Sitzung"}
        const en = {userName: "Username", password: "Password", login: "Log in", shutdown: "Shut down", reboot: "Restart", suspend: "Sleep", session: "Session"}
        return (german ? de : en)[key] || key
    }
    Component.onCompleted: refresh()
}
