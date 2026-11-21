import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang
import "../i18n" as UiI

// What Super+E does while a file window is already open: a new window (like Explorer) or a tab in the open window.
// windoesnot-file-manager keeps the choice in ~/.config/windoesnot/file-manager-open-mode.
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    property string mode: "window"
    property var hiddenPlaces: []
    property bool sidebarAvailable: false
    property bool loaded: false
    width: parent ? parent.width : 650
    spacing: 14
    readonly property var modes: ["window", "tab"]

    function tr(key) { return Lang.get("fileManager." + key, _lang) }
    Component.onCompleted: { readProc.running = true; sidebarAvailProc.running = true }

    Process {
        id: readProc
        command: ["windoesnot-file-manager", "--open-mode", "get"]
        stdout: StdioCollector { id: readOut }
        onExited: function(code) { var m = readOut.text.trim(); if (m === "tab" || m === "window") page.mode = m; page.loaded = true }
    }
    // Built-in places of the sidebar (Recent, Starred, Network, Trash) can be hidden; needs the adapted Files package
    Process {
        id: sidebarAvailProc
        command: ["windoesnot-file-manager", "--sidebar", "available"]
        onExited: function(code) { page.sidebarAvailable = (code === 0); if (code === 0) sidebarReadProc.running = true }
    }
    Process {
        id: sidebarReadProc
        command: ["windoesnot-file-manager", "--sidebar", "get"]
        stdout: StdioCollector { id: sidebarOut }
        onExited: function(code) { page.hiddenPlaces = sidebarOut.text.trim() === "" ? [] : sidebarOut.text.trim().split(/\s+/) }
    }
    Process { id: sidebarWriteProc; onExited: sidebarReadProc.running = true }
    function setPlace(name, show) {
        sidebarWriteProc.command = ["windoesnot-file-manager", "--sidebar", show ? "show" : "hide", name]
        sidebarWriteProc.running = true
    }
    Process { id: writeProc }
    function setMode(value) { page.mode = value; writeProc.command = ["windoesnot-file-manager", "--open-mode", "set", value]; writeProc.running = true }

    Text { text: page.tr("title"); font.pixelSize: UiI.UiScale.px(18); font.bold: true; color: page.dark ? "#fff" : "#1a1a1a" }
    Row {
        width: parent.width; spacing: 15
        Text { text: page.tr("openWith"); font.pixelSize: UiI.UiScale.px(14); color: page.dark ? "#aaa" : "#555"; width: parent.width - 260 - parent.spacing; anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.WordWrap }
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
    Text { width: parent.width; text: page.tr("hint"); wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(12); color: page.dark ? "#888" : "#777" }
    Text { text: page.tr("sidebar"); font.pixelSize: UiI.UiScale.px(14); color: page.dark ? "#aaa" : "#555"; topPadding: 6 }
    Repeater {
        model: ["recent", "starred", "network", "trash"]
        delegate: Tools.SystemToolsToggle {
            required property string modelData
            width: page.width
            settingsMenu: page.settingsMenu
            text: page.tr("place." + modelData)
            checked: page.hiddenPlaces.indexOf(modelData) < 0
            enabled: page.sidebarAvailable
            onToggled: page.setPlace(modelData, checked)
        }
    }
    Text { visible: !page.sidebarAvailable; width: parent.width; text: page.tr("sidebarMissing"); wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(12); color: page.dark ? "#888" : "#777" }
}
