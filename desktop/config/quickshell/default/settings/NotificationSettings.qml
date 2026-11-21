import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang
import "../i18n" as UiI

// Where notification popups appear, and whether they appear at all (Do Not Disturb off).
// The source of truth is the swaync config; windoesnot-notifications reads and writes it.
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    property string position: "top-right"
    property bool popupsOn: true
    property bool loaded: false
    width: parent ? parent.width : 650
    spacing: 14
    readonly property var positions: ["top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"]

    function tr(key) { return Lang.get("notifySettings." + key, _lang) }
    Component.onCompleted: readProc.running = true

    Process {
        id: readProc
        command: ["windoesnot-notifications", "get"]
        stdout: StdioCollector { id: readOut }
        onExited: function(code) {
            try { var d = JSON.parse(readOut.text); page.position = d.position; page.popupsOn = !d.dnd; page.loaded = true } catch (e) {}
        }
    }
    Process { id: writeProc; onExited: readProc.running = true }
    function run(args) { writeProc.command = ["windoesnot-notifications"].concat(args); writeProc.running = true }

    Text { text: page.tr("title"); font.pixelSize: UiI.UiScale.px(18); font.bold: true; color: page.dark ? "#fff" : "#1a1a1a" }

    Tools.SystemToolsToggle {
        settingsMenu: page.settingsMenu
        text: page.tr("popups")
        checked: page.popupsOn
        enabled: page.loaded
        onToggled: { page.popupsOn = checked; page.run(["dnd", checked ? "off" : "on"]) }
    }
    Text { width: parent.width; text: page.tr("popupsHint"); wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(12); color: page.dark ? "#888" : "#777" }

    Row {
        width: parent.width; spacing: 15
        Text { text: page.tr("position"); font.pixelSize: UiI.UiScale.px(14); color: page.dark ? "#aaa" : "#555"; width: parent.width - 260 - parent.spacing; anchors.verticalCenter: parent.verticalCenter }
        Tools.SystemToolsChoice {
            settingsMenu: page.settingsMenu
            width: 260
            enabled: page.loaded
            labelPrefix: "notifySettings.pos"
            model: page.positions
            currentIndex: Math.max(0, model.indexOf(page.position))
            onActivated: function(index) { page.position = page.positions[index]; page.run(["position", page.positions[index]]) }
        }
    }
}
