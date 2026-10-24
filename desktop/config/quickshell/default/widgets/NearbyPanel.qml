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
    readonly property var viewState: service ? service.state : ({devices:[],selected:[],history:[]})
    readonly property color foreground: darkMode ? "#eeeeee" : "#202020"
    readonly property color secondary: darkMode ? "#bbbbbb" : "#555555"
    color: darkMode ? "#1a1a1a" : "#ffffff"
    border.width: 1
    border.color: darkMode ? "#3a3a3a" : "#d0d0d0"
    radius: borderRadius
    width: 400; height: 580

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
    ScrollView {
        anchors.fill: parent; anchors.margins: 20
        clip: true; contentWidth: availableWidth
        Column {
            width: parent.width; spacing: 16
            Heading { text: panel.tr("nearby.title"); font.pixelSize: 20 }
            Label { text: panel.tr("nearby.intro") }
            Tools.SystemToolsToggle {
                settingsMenu: panel
                text: panel.tr("nearby.receive")
                checked: panel.viewState.requestedReceiving === true
                onToggled: panel.act("receive", {value:checked})
            }
            Label { text: panel.tr(panel.viewState.receiving ? "nearby.receivingOn" : "nearby.receivingOff") }
            Label { visible: !!panel.viewState.error; text: panel.tr("nearby.error." + panel.viewState.error) }
            Row {
                spacing: 8
                Action { text: panel.tr("nearby.chooseFiles"); onClicked: picker.open() }
                Action { text: panel.tr("nearby.refresh"); onClicked: panel.act("discover") }
            }
            Label { visible: panel.viewState.selected.length > 0; text: panel.viewState.selected.join("\n") }
            Action { visible: panel.viewState.selected.length > 0; text: panel.tr("nearby.clearSelection"); onClicked: panel.act("clear") }
            Heading { text: panel.tr("nearby.devices") }
            Label { visible: panel.viewState.devices.length === 0; text: panel.tr("nearby.noDevices") }
            Repeater {
                model: panel.viewState.devices
                delegate: Column {
                    required property var modelData
                    width: parent.width; spacing: 6
                    Action {
                        width: parent.width
                        text: modelData.alias
                        enabled: panel.viewState.selected.length > 0 && !panel.viewState.outgoing
                        onClicked: panel.act("send", {peer:modelData.id})
                    }
                    Label { visible: modelData.protocol !== "https"; text: panel.tr("nearby.unencrypted") }
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
            Action { text: panel.tr("nearby.openFolder"); onClicked: panel.act("folder") }
            Heading { text: panel.tr("nearby.history") }
            Label { visible: panel.viewState.history.length === 0; text: panel.tr("nearby.noHistory") }
            Repeater {
                model: panel.viewState.history
                delegate: Column {
                    required property var modelData
                    width: parent.width; spacing: 4
                    Label { color: panel.foreground; text: modelData.peer + " · " + panel.tr("nearby.status." + modelData.status) }
                    Label { text: modelData.files.join(", ") + " · " + new Date(modelData.time * 1000).toLocaleString(Qt.locale(panel.uiLanguage), Locale.ShortFormat) }
                }
            }
            Label { text: panel.tr("nearby.networkHint") }
        }
    }
}
