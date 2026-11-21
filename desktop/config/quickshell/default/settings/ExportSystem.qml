import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang
import "../i18n" as UiI

// "Export my system": software profile, other packages, AUR, Flatpak and desktop preferences into one folder.
Rectangle {
    id: card
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    property bool busy: false
    property string resultText: ""
    property bool failed: false
    function tr(key) { return Lang.get("exportSystem." + key, _lang) }
    width: parent ? parent.width : 650
    height: column.implicitHeight + 32
    radius: settingsMenu ? settingsMenu.borderRadius : 10
    color: dark ? "#141414" : "#f5f5f5"
    border.width: 1; border.color: dark ? "#3a3a3a" : "#d0d0d0"

    Process {
        id: exportProc
        command: ["windoesnot-export-system"]
        stdout: StdioCollector { id: out }
        onExited: function(code) {
            card.busy = false
            try {
                var d = JSON.parse(out.text)
                card.failed = !d.ok
                card.resultText = d.ok ? card.tr("done").replace("%1", d.path).replace("%2", d.apps).replace("%3", d.other + d.aur + d.flatpak) : card.tr("failed")
            } catch (e) { card.failed = true; card.resultText = card.tr("failed") }
        }
    }
    Column {
        id: column
        x: 16; y: 16; width: parent.width - 32; spacing: 10
        Text { text: card.tr("title"); font.pixelSize: UiI.UiScale.px(15); font.bold: true; color: card.dark ? "#fff" : "#1a1a1a" }
        Text { width: parent.width; text: card.tr("hint"); wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(13); color: card.dark ? "#aaa" : "#555" }
        Tools.SystemToolsButton {
            settingsMenu: card.settingsMenu
            primary: true
            enabled: !card.busy
            text: card.busy ? card.tr("working") : card.tr("button")
            onClicked: { card.busy = true; card.resultText = ""; exportProc.running = true }
        }
        Text { visible: card.resultText !== ""; width: parent.width; text: card.resultText; wrapMode: Text.WrapAnywhere; font.pixelSize: UiI.UiScale.px(12); color: card.failed ? "#cc4444" : (card.dark ? "#aaa" : "#555") }
    }
}
