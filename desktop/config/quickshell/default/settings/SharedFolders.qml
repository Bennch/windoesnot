import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

// List of folders shared in the network (Samba usershares) with a button to stop each one.
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color cardColor: dark ? "#232323" : "#f4f4f4"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d6d6d6"
    readonly property color textColor: dark ? "#ffffff" : "#1a1a1a"
    readonly property color mutedColor: dark ? "#aaaaaa" : "#666666"
    property var shares: []
    property bool available: false
    width: parent ? parent.width : 650
    spacing: 12
    function tr(key) { return Lang.get("share." + key, _lang) }
    function refresh() { statusProc.running = true }
    Component.onCompleted: refresh()

    Process {
        id: statusProc
        command: ["windoesnot-share", "status"]
        stdout: StdioCollector { id: statusOut }
        onExited: {
            try { var d = JSON.parse(statusOut.text); page.shares = d.shares || []; page.available = d.installed !== false } catch (e) { page.available = false }
        }
    }
    Process { id: removeProc; onExited: page.refresh() }
    function stop(name) { removeProc.command = ["windoesnot-share", "remove", name]; removeProc.running = true }

    Text { visible: page.available; text: page.tr("folders.title"); font.pixelSize: 18; font.bold: true; color: page.textColor }
    Rectangle {
        visible: page.available
        width: parent.width; height: rows.height + 2; radius: 8; color: page.cardColor; border.color: page.lineColor; border.width: 1; clip: true
        Column {
            id: rows; x: 1; y: 1; width: parent.width - 2
            Column {
                visible: page.shares.length === 0
                x: 20; width: parent.width - 40; topPadding: 28; bottomPadding: 28; spacing: 12
                Image { anchors.horizontalCenter: parent.horizontalCenter; width: 48; height: 48; source: Qt.resolvedUrl("../img/folder.svg"); sourceSize.width: 96; sourceSize.height: 96; fillMode: Image.PreserveAspectFit; opacity: 0.8 }
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: page.tr("folders.empty"); font.pixelSize: 13; color: page.mutedColor }
            }
            Repeater {
                model: page.shares
                Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    Rectangle { visible: index > 0; width: parent.width; height: 1; color: page.lineColor }
                    Item {
                        width: parent.width; height: 64
                        Column {
                            x: 14; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 130; spacing: 2
                            Text { width: parent.width; text: modelData.name + "   " + modelData.unc; elide: Text.ElideMiddle; font.pixelSize: 13; color: page.textColor }
                            Text { width: parent.width; elide: Text.ElideMiddle; font.pixelSize: 11; color: page.mutedColor
                                   text: modelData.path + " · " + (modelData.access === "write" ? page.tr("folders.readWrite") : page.tr("folders.readOnly")) + (modelData.guest ? " · " + page.tr("folders.guest") : "") }
                        }
                        Tools.SystemToolsButton {
                            anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                            settingsMenu: page.settingsMenu; text: page.tr("folders.stop"); onClicked: page.stop(modelData.name)
                        }
                    }
                }
            }
        }
    }
}
