import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

// What Super+E does while a file window is already open: a new window (like Explorer) or a tab in the open window.
// windoesnot-file-manager keeps the choice in ~/.config/windoesnot/file-manager-open-mode.
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    property string mode: "window"
    property bool loaded: false
    width: parent ? parent.width : 650
    spacing: 14
    readonly property var modes: ["window", "tab"]

    function tr(key) { return Lang.get("fileManager." + key, _lang) }
    Component.onCompleted: readProc.running = true

    Process {
        id: readProc
        command: ["windoesnot-file-manager", "--open-mode", "get"]
        stdout: StdioCollector { id: readOut }
        onExited: function(code) { var m = readOut.text.trim(); if (m === "tab" || m === "window") page.mode = m; page.loaded = true }
    }
    Process { id: writeProc }
    function setMode(value) { page.mode = value; writeProc.command = ["windoesnot-file-manager", "--open-mode", "set", value]; writeProc.running = true }

    Text { text: page.tr("title"); font.pixelSize: 18; font.bold: true; color: page.dark ? "#fff" : "#1a1a1a" }
    Row {
        width: parent.width; spacing: 15
        Text { text: page.tr("openWith"); font.pixelSize: 14; color: page.dark ? "#aaa" : "#555"; width: parent.width - 260 - parent.spacing; anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.WordWrap }
        Tools.SystemToolsChoice {
            settingsMenu: page.settingsMenu
            width: 260
            enabled: page.loaded
            labelPrefix: "fileManager.mode"
            model: page.modes
            currentIndex: Math.max(0, model.indexOf(page.mode))
            onActivated: function(index) { page.setMode(page.modes[index]) }
        }
    }
    Text { width: parent.width; text: page.tr("hint"); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.dark ? "#888" : "#777" }
}
