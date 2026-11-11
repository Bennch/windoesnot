import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import "../settings" as Tools
import "../i18n/Lang.js" as Lang

Rectangle {
    id: panel
    property var service: null
    property bool darkMode: true
    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property string uiLanguage: "de"
    readonly property bool dialogOpen: picker.visible
    // True while files are dragged over the panel (highlights the file card).
    property bool dropping: false
    property int tab: 0
    readonly property var viewState: service ? service.state : ({devices:[],selected:[],history:[]})
    readonly property color foreground: darkMode ? "#eeeeee" : "#202020"
    readonly property color secondary: darkMode ? "#bbbbbb" : "#555555"
    color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
    border.width: 1
    border.color: darkMode ? "#3a3a3f" : "#c0c0c0"
    topLeftRadius: borderRadius
    topRightRadius: borderRadius
    bottomLeftRadius: 0
    bottomRightRadius: 0
    // Exactly as tall as the content, up to 580 px; the window follows this height.
    implicitWidth: 400
    implicitHeight: Math.min(580, nearbyColumn.height + 36)
    width: implicitWidth
    height: implicitHeight

    function tr(key) { return Lang.get(key, uiLanguage) }
    function act(action, extra) {
        if (service) service.command(Object.assign({action:action}, extra || {}))
    }
    function size(bytes) {
        if (bytes < 1024) return bytes + " B"
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KiB"
        return (bytes / 1048576).toFixed(1) + " MiB"
    }
    component Label: Text {
        width: parent.width; wrapMode: Text.WordWrap; textFormat: Text.PlainText
        color: panel.secondary; font.pixelSize: 13
    }
    component Heading: Label { color: panel.foreground; font.bold: true; font.pixelSize: 16 }
    component Action: Tools.SystemToolsButton { settingsMenu: panel }

    FileDialog {
        id: picker
        title: panel.tr("nearby.chooseFiles")
        fileMode: FileDialog.OpenFiles
        onAccepted: panel.act("select", {files:selectedFiles.map(url => url.toString())})
    }
    // Drop files anywhere on the panel to select them for the devices below.
    DropArea {
        anchors.fill: parent
        onEntered: panel.dropping = true
        onExited: panel.dropping = false
        onDropped: function(drop) {
            panel.dropping = false
            panel.tab = 0
            if (drop.hasUrls) panel.act("select", {files: drop.urls.map(url => url.toString())})
        }
    }
    ScrollView {
        anchors.fill: parent; anchors.margins: 18
        clip: true; contentWidth: availableWidth
        Column {
            id: nearbyColumn
            width: parent.width; spacing: 14

            // Header: what this panel is, and whether it accepts files.
            Heading { text: panel.tr("nearby.title"); font.pixelSize: 18 }
            Row {
                spacing: 20
                Repeater {
                    model: ["nearby.tabSend", "nearby.history"]
                    delegate: Item {
                        required property int index
                        required property string modelData
                        width: tabText.width; height: 28
                        Text { id: tabText; text: panel.tr(modelData); font.pixelSize: 14; font.bold: panel.tab === index
                               color: panel.tab === index ? panel.foreground : panel.secondary }
                        Rectangle { visible: panel.tab === index; width: parent.width; height: 2; y: parent.height - 2; color: panel.accentColor }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: panel.tab = index }
                    }
                }
            }
            Column {
                id: sendTab
                width: parent.width; spacing: 14
                visible: panel.tab === 0
            Tools.SystemToolsToggle {
                settingsMenu: panel
                text: panel.tr(panel.viewState.receiving ? "nearby.receivingOn" : "nearby.receivingOff")
                checked: panel.viewState.requestedReceiving === true
                onToggled: panel.act("receive", {value:checked})
            }
            Label { visible: !!panel.viewState.error; color: "#ef5350"; text: panel.tr("nearby.error." + panel.viewState.error) }

            // Firewall: only shown when the LocalSend ports are closed, with the one fix.
            Column {
                width: parent.width; spacing: 8
                visible: panel.viewState.portsOpen === false
                Label { text: panel.tr("nearby.portsClosed") }
                Action { text: panel.tr("nearby.openPorts"); onClicked: panel.act("ports", {value:true}) }
            }

            // Files to send: one button when empty, the selection otherwise.
            Rectangle {
                width: parent.width; height: filesContent.height + 24
                radius: 8; color: panel.darkMode ? "#141414" : "#f5f5f5"
                border.width: panel.dropping ? 2 : 1
                border.color: panel.dropping ? panel.accentColor : (panel.darkMode ? "#3a3a3a" : "#d0d0d0")
                Column {
                    id: filesContent
                    x: 12; y: 12; width: parent.width - 24; spacing: 10
                    Label { visible: panel.viewState.selected.length === 0; text: panel.tr("nearby.dropHint") }
                    Label {
                        visible: panel.viewState.selected.length > 0
                        color: panel.foreground
                        text: panel.viewState.selected.slice(0, 3).join("\n") + (panel.viewState.selected.length > 3 ? "\n+ " + (panel.viewState.selected.length - 3) : "")
                    }
                    Row {
                        spacing: 8
                        Action { primary: panel.viewState.selected.length === 0; text: panel.tr("nearby.chooseFiles"); onClicked: picker.open() }
                        Action { visible: panel.viewState.selected.length > 0; text: panel.tr("nearby.clearSelection"); onClicked: panel.act("clear") }
                    }
                }
            }

            // Devices: tap one to send the selected files to it.
            Row {
                width: parent.width; spacing: 8
                Text { text: panel.tr("nearby.devices"); color: panel.foreground; font.bold: true; font.pixelSize: 15; anchors.verticalCenter: parent.verticalCenter }
            }
            Label { visible: panel.viewState.devices.length === 0; text: panel.tr("nearby.noDevices") }
            Repeater {
                model: panel.viewState.devices
                delegate: Action {
                    required property var modelData
                    width: parent.width
                    text: modelData.alias
                    enabled: panel.viewState.selected.length > 0 && !panel.viewState.outgoing
                    onClicked: panel.act("send", {peer:modelData.id})
                }
            }

            Repeater {
                model: [panel.viewState.incoming, panel.viewState.outgoing].filter(value => !!value)
                delegate: Rectangle {
                    id: transferCard
                    required property var modelData
                    width: parent.width; height: transferContent.height + 24
                    radius: 8; color: panel.darkMode ? "#141414" : "#f5f5f5"
                    border.width: 1; border.color: panel.darkMode ? "#3a3a3a" : "#d0d0d0"
                    Column {
                        id: transferContent
                        x: 12; y: 12; width: parent.width - 24; spacing: 10
                        Heading { text: panel.tr(transferCard.modelData.direction === "receive" ? "nearby.from" : "nearby.to") + " " + transferCard.modelData.peer }
                        Label { text: transferCard.modelData.files.join("\n") }
                        Label { text: panel.tr("nearby.status." + transferCard.modelData.status) + " · " + panel.size(transferCard.modelData.bytes) + " / " + panel.size(transferCard.modelData.total) }
                        Rectangle {
                            width: parent.width; height: 4; radius: 2
                            color: panel.darkMode ? "#3a3a3a" : "#d0d0d0"
                            Rectangle { height: parent.height; radius: 2; color: panel.accentColor; width: parent.width * Math.min(1, transferCard.modelData.total ? transferCard.modelData.bytes / transferCard.modelData.total : 0) }
                        }
                        Row {
                            spacing: 8
                            visible: transferCard.modelData.direction === "receive" && transferCard.modelData.status === "waiting"
                            Action { primary: true; text: panel.tr("nearby.accept"); onClicked: panel.act("accept", {id:transferCard.modelData.id}) }
                            Action { text: panel.tr("nearby.reject"); onClicked: panel.act("reject", {id:transferCard.modelData.id}) }
                        }
                        Action {
                            visible: transferCard.modelData.direction === "send" || transferCard.modelData.status !== "waiting"
                            text: panel.tr("nearby.cancel"); onClicked: panel.act("cancel", {id:transferCard.modelData.id})
                        }
                    }
                }
            }
            // Keeps the window as tall as the Send tab, so switching tabs does not resize it.
            Item { width: 1; visible: panel.tab === 1; height: Math.max(0, sendTab.height - historyTab.height) }
            // Footer: the received-files folder and the transfer history popup.
            Action { width: parent.width; text: panel.tr("nearby.openFolder"); onClicked: panel.act("folder") }
            }
            Column {
                id: historyTab
                width: parent.width; spacing: 12
                visible: panel.tab === 1
                Label { visible: panel.viewState.history.length === 0; text: panel.tr("nearby.noHistory") }
                Repeater {
                    model: panel.viewState.history
                    delegate: Column {
                        required property var modelData
                        width: parent.width; spacing: 2
                        Label { color: panel.foreground; text: modelData.peer + " \u00b7 " + panel.tr("nearby.status." + modelData.status) }
                        Label { text: modelData.files.join(", ") }
                        Label { font.pixelSize: 11; text: new Date(modelData.time * 1000).toLocaleString(Qt.locale(panel.uiLanguage), Locale.ShortFormat) }
                    }
                }
            }
        }
    }
}
