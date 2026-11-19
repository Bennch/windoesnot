import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

// Turn any website into an app of its own (start menu entry with the site's icon, own window, own taskbar entry).
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    readonly property color textColor: dark ? "#ffffff" : "#1a1a1a"
    readonly property color mutedColor: dark ? "#aaaaaa" : "#666666"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d0d0d0"
    property string appName: ""
    property string appUrl: ""
    property string message: ""
    property bool failure: false
    readonly property string normalizedUrl: {
        var u = appUrl.trim()
        if (u === "") return ""
        if (u.indexOf("://") < 0) u = "https://" + u
        return u
    }
    readonly property bool valid: appName.trim() !== "" && /^https:\/\/[^\s\/]+\.[^\s\/]+/.test(normalizedUrl)
    width: parent ? parent.width : 650
    spacing: 10
    function tr(key) { return Lang.get("webapp." + key, _lang) }

    Process {
        id: creator
        stdout: StdioCollector { id: created }
        onExited: (code) => {
            page.failure = code !== 0
            page.message = code === 0 ? page.tr("created").replace("{}", page.appName.trim()) : page.tr("failed")
            if (code === 0) { page.appName = ""; page.appUrl = "" }
        }
    }
    function create() {
        if (!valid || creator.running) return
        creator.command = ["windoesnot-webapp", "--create", "--name", appName.trim(), normalizedUrl]
        creator.running = true
        message = tr("working"); failure = false
    }

    Text { text: page.tr("title"); font.pixelSize: 18; font.bold: true; color: page.textColor }
    Text { width: parent.width; wrapMode: Text.WordWrap; text: page.tr("hint"); font.pixelSize: 12; color: page.mutedColor }
    Row {
        width: parent.width; spacing: 8
        TextField {
            width: (parent.width - 8) * 0.35; height: 38; maximumLength: 40; selectByMouse: true
            placeholderText: page.tr("name"); text: page.appName
            onTextEdited: page.appName = text
            color: page.textColor; font.pixelSize: 13
            background: Rectangle { radius: 6; color: page.dark ? "#2a2a2a" : "#f0f0f0"; border.width: 1; border.color: parent.activeFocus ? page.accent : page.lineColor }
        }
        TextField {
            width: (parent.width - 8) * 0.65; height: 38; selectByMouse: true
            placeholderText: page.tr("url"); text: page.appUrl
            onTextEdited: page.appUrl = text
            onAccepted: page.create()
            color: page.textColor; font.pixelSize: 13
            background: Rectangle { radius: 6; color: page.dark ? "#2a2a2a" : "#f0f0f0"; border.width: 1; border.color: parent.activeFocus ? page.accent : page.lineColor }
        }
    }
    Tools.SystemToolsButton {
        settingsMenu: page.settingsMenu; primary: true
        enabled: page.valid && !creator.running
        text: page.tr("create")
        onClicked: page.create()
    }
    Text { visible: page.message !== ""; width: parent.width; wrapMode: Text.WordWrap; text: page.message; font.pixelSize: 13; font.bold: true; color: page.failure ? "#cc4444" : "#3aa655" }
}
