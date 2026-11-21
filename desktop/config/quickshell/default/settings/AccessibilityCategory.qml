import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

// Accessibility: magnifier, on-screen keyboard, colour filters, cursor and text size, reduced motion.
// The source of truth is windoesnot-accessibility (get/set); the page only shows and changes it.
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    property bool loaded: false
    property string colorFilter: "none"
    property int cursorSize: 24
    property real textScale: 1.0
    property bool reduceMotion: false
    property real zoom: 1.0
    property bool keyboardInstalled: false
    width: parent ? parent.width : 650
    spacing: 22
    readonly property var filters: ["none", "grayscale", "invert", "contrast", "protanopia", "deuteranopia", "tritanopia"]
    readonly property var cursorSizes: [24, 32, 48, 64]
    readonly property var textScales: [1.0, 1.25, 1.5, 1.75]

    function titleColor() { return dark ? "#fff" : "#1a1a1a" }
    function hintColor() { return dark ? "#888" : "#777" }
    Component.onCompleted: readProc.running = true

    Process {
        id: readProc
        command: ["windoesnot-accessibility", "get"]
        stdout: StdioCollector { id: readOut }
        onExited: function(code) {
            try {
                var d = JSON.parse(readOut.text)
                page.colorFilter = d.colorFilter; page.cursorSize = d.cursorSize; page.textScale = d.textScale
                page.reduceMotion = d.reduceMotion; page.zoom = d.zoom; page.keyboardInstalled = d.keyboardInstalled
                page.loaded = true
            } catch (e) {}
        }
    }
    Process { id: actionProc; onExited: readProc.running = true }
    function run(args) { actionProc.command = ["windoesnot-accessibility"].concat(args); actionProc.running = true }

    // Magnifier
    Column {
        width: parent.width; spacing: 10
        Text { text: Lang.get("a11y.magnifier", page._lang); font.pixelSize: 18; font.bold: true; color: page.titleColor() }
        Row {
            spacing: 10
            Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: "−"; enabled: page.loaded; width: 48; onClicked: page.run(["zoom", "out"]) }
            Text { text: "× " + page.zoom.toFixed(1); width: 70; horizontalAlignment: Text.AlignHCenter; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 15; color: page.titleColor() }
            Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: "+"; enabled: page.loaded; width: 48; onClicked: page.run(["zoom", "in"]) }
            Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: Lang.get("a11y.zoomReset", page._lang); enabled: page.loaded && page.zoom > 1.0; onClicked: page.run(["zoom", "reset"]) }
        }
        Text { width: parent.width; text: Lang.get("a11y.magnifierHint", page._lang); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.hintColor() }
    }

    // On-screen keyboard
    Column {
        width: parent.width; spacing: 10
        Text { text: Lang.get("a11y.keyboard", page._lang); font.pixelSize: 18; font.bold: true; color: page.titleColor() }
        Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: Lang.get("a11y.keyboardToggle", page._lang); enabled: page.loaded && page.keyboardInstalled; onClicked: page.run(["keyboard", "toggle"]) }
        Text { width: parent.width; text: page.keyboardInstalled ? Lang.get("a11y.keyboardHint", page._lang) : Lang.get("a11y.keyboardMissing", page._lang); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.hintColor() }
    }

    // Colours
    Column {
        width: parent.width; spacing: 10
        Text { text: Lang.get("a11y.colors", page._lang); font.pixelSize: 18; font.bold: true; color: page.titleColor() }
        Row {
            width: parent.width; spacing: 15
            Text { text: Lang.get("a11y.filter", page._lang); font.pixelSize: 14; color: page.dark ? "#aaa" : "#555"; width: parent.width - 260 - parent.spacing; anchors.verticalCenter: parent.verticalCenter }
            Tools.SystemToolsChoice {
                settingsMenu: page.settingsMenu; width: 260; enabled: page.loaded
                labelPrefix: "a11y.filter"; model: page.filters
                currentIndex: Math.max(0, model.indexOf(page.colorFilter))
                onActivated: function(index) { page.colorFilter = page.filters[index]; page.run(["set", "colorFilter", page.filters[index]]) }
            }
        }
        Text { width: parent.width; text: Lang.get("a11y.filterHint", page._lang); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.hintColor() }
    }

    // Cursor and text
    Column {
        width: parent.width; spacing: 10
        Text { text: Lang.get("a11y.size", page._lang); font.pixelSize: 18; font.bold: true; color: page.titleColor() }
        Row {
            width: parent.width; spacing: 15
            Text { text: Lang.get("a11y.cursor", page._lang); font.pixelSize: 14; color: page.dark ? "#aaa" : "#555"; width: parent.width - 260 - parent.spacing; anchors.verticalCenter: parent.verticalCenter }
            Tools.SystemToolsChoice {
                settingsMenu: page.settingsMenu; width: 260; enabled: page.loaded
                labelPrefix: "a11y.cursorSize"; model: page.cursorSizes
                currentIndex: Math.max(0, model.indexOf(page.cursorSize))
                onActivated: function(index) { page.cursorSize = page.cursorSizes[index]; page.run(["set", "cursorSize", String(page.cursorSizes[index])]) }
            }
        }
        Row {
            width: parent.width; spacing: 15
            Text { text: Lang.get("a11y.text", page._lang); font.pixelSize: 14; color: page.dark ? "#aaa" : "#555"; width: parent.width - 260 - parent.spacing; anchors.verticalCenter: parent.verticalCenter }
            Tools.SystemToolsChoice {
                settingsMenu: page.settingsMenu; width: 260; enabled: page.loaded
                labelPrefix: "a11y.textScale"; model: page.textScales
                currentIndex: Math.max(0, model.indexOf(page.textScale))
                onActivated: function(index) { page.textScale = page.textScales[index]; page.run(["set", "textScale", String(page.textScales[index])]) }
            }
        }
        Text { width: parent.width; text: Lang.get("a11y.textHint", page._lang); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.hintColor() }
    }

    // Motion
    Column {
        width: parent.width; spacing: 10
        Text { text: Lang.get("a11y.motion", page._lang); font.pixelSize: 18; font.bold: true; color: page.titleColor() }
        Tools.SystemToolsToggle {
            settingsMenu: page.settingsMenu; text: Lang.get("a11y.reduceMotion", page._lang); checked: page.reduceMotion; enabled: page.loaded
            onToggled: { page.reduceMotion = checked; page.run(["set", "reduceMotion", checked ? "true" : "false"]) }
        }
        Text { width: parent.width; text: Lang.get("a11y.motionHint", page._lang); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.hintColor() }
    }
}
