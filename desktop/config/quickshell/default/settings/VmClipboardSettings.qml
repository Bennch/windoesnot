import QtQuick
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

// Shared clipboard with virtual machines (spice-vdagent, VMware tools, X11 bridge).
Column {
    id: page
    property var settingsMenu: null
    property string language: settingsMenu ? settingsMenu.uiLanguage : "de"
    property bool sharing: true
    property bool ready: false
    spacing: 12
    function tr(key) { return Lang.get(key, language) }

    Component.onCompleted: { worker.command = ["windoesnot-vm-clipboard", "status"]; worker.running = true }

    Process {
        id: worker
        stdout: StdioCollector { id: output }
        onExited: {
            page.sharing = output.text.trim() !== "off"
            page.ready = true
        }
    }

    Text {
        text: page.tr("apps.vmClipboardTitle"); font.pixelSize: 18; font.bold: true
        color: settingsMenu && !settingsMenu.darkMode ? "#1a1a1a" : "#ffffff"
    }
    Text {
        width: parent.width; text: page.tr("apps.vmClipboardHint"); wrapMode: Text.WordWrap
        font.pixelSize: 13; color: settingsMenu && !settingsMenu.darkMode ? "#555555" : "#bbbbbb"
    }
    Tools.SystemToolsToggle {
        settingsMenu: page.settingsMenu
        text: page.tr("apps.vmClipboardToggle")
        enabled: page.ready
        checked: page.sharing
        onToggled: {
            page.sharing = checked
            worker.command = ["windoesnot-vm-clipboard", checked ? "on" : "off"]
            worker.running = true
        }
    }
}
