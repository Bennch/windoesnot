import QtQuick
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

Column {
    id: page
    property var settingsMenu: null
    property string language: settingsMenu ? settingsMenu.uiLanguage : "de"
    property var available: []
    property string current: ""
    property string result: ""
    property bool busy: false
    spacing: 12
    function tr(key) { return Lang.get(key, language) }
    function run(action, args) {
        if (busy) return
        busy = true
        if (settingsMenu) settingsMenu.fileDialogOpen = true
        worker.operation = action
        worker.command = (action === "shell-status" ? ["/usr/bin/python3", "-I"] : ["/usr/bin/pkexec", "--disable-internal-agent"])
            .concat(["/usr/lib/windoesnot/system_tools.py", action, JSON.stringify(args)])
        worker.running = true
    }
    Component.onCompleted: run("shell-status", {})
    Process {
        id: worker
        property string operation
        stdout: StdioCollector { id: output }
        onExited: code => {
            page.busy = false
            if (page.settingsMenu) page.settingsMenu.fileDialogOpen = false
            let data = {}
            try { data = JSON.parse(output.text) } catch (error) {}
            if (code !== 0 || data.error) {
                page.result = page.tr(code === 126 ? "systemTools.cancelled" : "systemTools.failed")
            } else if (operation === "shell-status") {
                page.available = data.available || []
                page.current = data.current || ""
                choice.currentIndex = page.available.indexOf(page.current)
            } else {
                page.result = page.tr("apps.shellSaved")
                page.run("shell-status", {})
            }
        }
    }
    Text {
        text: page.tr("apps.shellTitle"); font.pixelSize: 18; font.bold: true
        color: settingsMenu && !settingsMenu.darkMode ? "#1a1a1a" : "#ffffff"
    }
    Text {
        width: parent.width; text: page.tr("apps.shellHint"); wrapMode: Text.WordWrap
        font.pixelSize: 13; color: settingsMenu && !settingsMenu.darkMode ? "#555555" : "#bbbbbb"
    }
    Row {
        spacing: 12
        Tools.SystemToolsChoice {
            id: choice
            width: 180; settingsMenu: page.settingsMenu
            model: page.available; enabled: !page.busy
        }
        Tools.SystemToolsButton {
            settingsMenu: page.settingsMenu
            text: page.tr("systemTools.apply")
            enabled: !page.busy && choice.currentIndex >= 0 && choice.currentText !== page.current
            onClicked: page.run("shell-set", {shell: choice.currentText})
        }
    }
    Text {
        width: parent.width; text: page.result; visible: text.length > 0
        wrapMode: Text.WordWrap; font.pixelSize: 13
        color: settingsMenu && !settingsMenu.darkMode ? "#555555" : "#bbbbbb"
    }
}
