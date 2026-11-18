import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang
import "FlatpakPermissionParser.js" as Permissions

Column {
    id: page
    property var settingsMenu: null
    property string language: settingsMenu ? settingsMenu.uiLanguage : "de"
    property var appList: []
    property string appId: ""
    property var permissions: ({})
    property string infoText: ""
    property var portalRows: []
    property bool showTech: false
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color cardColor: dark ? "#232323" : "#f4f4f4"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d6d6d6"
    readonly property color textColor: dark ? "#ffffff" : "#1a1a1a"
    readonly property color mutedColor: dark ? "#aaaaaa" : "#666666"
    property string stage: "list"
    property bool ready: false
    property bool failed: false
    spacing: 12
    function tr(key) { return Lang.get("appPermissions." + key, language) }
    function tableName(name) { var k = "appPermissions.t." + name; var v = Lang.get(k, language); return v === k ? name : v }
    function permText(list) {
        return list.map(function(p) { var k = "appPermissions.p." + p; var v = Lang.get(k, language); return v === k ? p : v }).join(" · ")
    }
    function yesNo(group, value) { return Permissions.has(permissions, group, value) }
    function start(command, nextStage) { stage = nextStage; ready = false; worker.command = command; worker.running = true }
    function load(id) { if (Permissions.validId(id) && !worker.running) { appId = id; start(Permissions.command("info", id), "info") } }
    function change(action, enabled) { if (!worker.running && appId) start(Permissions.command(action, appId, enabled), "changed") }
    Component.onCompleted: start(["windoesnot-bounded", "15", "flatpak", "list", "--app", "--columns=application,name"], "list")
    Process {
        id: worker
        stdout: StdioCollector { id: output }
        onExited: function(code) {
            if (code !== 0) { page.failed = true; page.ready = true; return }
            page.failed = false
            if (page.stage === "list") {
                page.appList = Permissions.apps(output.text)
                if (page.appList.length) page.load(page.appList[0].id)
                else page.ready = true
            } else if (page.stage === "info") {
                page.infoText = output.text
                page.start(Permissions.command("show", page.appId), "show")
            } else if (page.stage === "show") {
                page.permissions = Permissions.parse(output.text, Permissions.parse(page.infoText))
                page.start(["windoesnot-bounded", "15", "flatpak", "permissions"], "portals")
            } else if (page.stage === "portals") {
                page.portalRows = Permissions.portalRows(output.text, page.appId)
                page.ready = true
            } else if (page.stage === "changed") page.load(page.appId)
        }
    }
    Text { text: page.tr("title"); font.pixelSize: 18; font.bold: true; color: page.textColor }
    Text { width: parent.width; text: page.tr("intro"); wrapMode: Text.WordWrap; color: page.mutedColor }
    Text { visible: page.ready && !page.failed && page.appList.length === 0; text: page.tr("empty"); color: page.mutedColor }
    Text { visible: page.failed; text: page.tr("error"); color: "#cc4444" }
    Tools.SystemToolsButton { visible: page.failed; settingsMenu: page.settingsMenu; text: page.tr("retry"); onClicked: page.appId ? page.load(page.appId) : page.start(["windoesnot-bounded", "15", "flatpak", "list", "--app", "--columns=application,name"], "list") }
    Tools.SystemToolsChoice {
        settingsMenu: page.settingsMenu
        width: Math.min(parent.width, 400); visible: page.appList.length > 0; enabled: page.ready
        model: page.appList.map(function(app) { return app.name })
        onActivated: function(index) { page.load(page.appList[index].id) }
    }

    // Reusable table card: rows separated by thin lines
    component Card: Rectangle {
        default property alias rows: rowColumn.data
        width: parent.width; height: rowColumn.height + 2; radius: 8
        color: page.cardColor; border.color: page.lineColor; border.width: 1; clip: true
        Column { id: rowColumn; x: 1; y: 1; width: parent.width - 2 }
    }
    component Line: Rectangle { width: parent.width; height: 1; color: page.lineColor }
    component Pill: Rectangle {
        property string label: ""
        property bool good: false
        implicitWidth: pillText.implicitWidth + 20; implicitHeight: 24; radius: 12
        color: good ? Qt.rgba(settingsMenu.accentColor.r, settingsMenu.accentColor.g, settingsMenu.accentColor.b, 0.2) : (page.dark ? "#333333" : "#e4e4e4")
        Text { id: pillText; anchors.centerIn: parent; text: parent.label; font.pixelSize: 12; font.bold: parent.good
               color: parent.good ? settingsMenu.accentColor : page.mutedColor }
    }

    Column {
        width: parent.width; spacing: 16; visible: page.appId !== "" && page.ready && !page.failed

        Text { width: parent.width; text: page.tr("restart"); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.mutedColor }

        Text { text: page.tr("section.access"); font.pixelSize: 14; font.bold: true; color: page.textColor }
        Card {
            Repeater {
                model: [
                    { title: "files", detail: "filesHint", action: "home", group: "filesystems", value: "home" },
                    { title: "network", detail: "networkHint", action: "network", group: "shared", value: "network" },
                    { title: "devices", detail: "devicesHint", action: "devices", group: "devices", value: "all" }
                ]
                Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    Item {
                        width: parent.width; height: 58
                        Column {
                            anchors.verticalCenter: parent.verticalCenter; x: 14; width: parent.width - 100; spacing: 2
                            Text { text: page.tr(modelData.title); font.pixelSize: 14; color: page.textColor }
                            Text { width: parent.width; text: page.tr(modelData.detail); font.pixelSize: 12; color: page.mutedColor; elide: Text.ElideRight }
                        }
                        Tools.SystemToolsToggle {
                            settingsMenu: page.settingsMenu; text: ""; width: 50
                            anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                            checked: Permissions.has(page.permissions, modelData.group, modelData.value)
                            onToggled: page.change(modelData.action, checked)
                        }
                    }
                    Line { visible: modelData.title !== "devices" }
                }
            }
        }

        Text { text: page.tr("section.others"); font.pixelSize: 14; font.bold: true; color: page.textColor }
        Card {
            Repeater {
                model: [
                    { label: "downloads", group: "filesystems", value: "xdg-download" },
                    { label: "gpu", group: "devices", value: "dri" },
                    { label: "session", group: "shared", value: "ipc" }
                ]
                Column {
                    required property var modelData
                    width: parent.width
                    Item {
                        width: parent.width; height: 44
                        Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: page.tr(modelData.label); font.pixelSize: 13; color: page.textColor }
                        Pill {
                            anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                            good: page.yesNo(modelData.group, modelData.value)
                            label: good ? page.tr("on") : page.tr("off")
                        }
                    }
                    Line { visible: modelData.label !== "session" }
                }
            }
        }

        Row {
            spacing: 10
            Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: page.tr("reset"); onClicked: page.change("reset", false) }
            Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: page.showTech ? page.tr("hideTech") : page.tr("showTech"); onClicked: page.showTech = !page.showTech }
        }

        Column {
            width: parent.width; spacing: 8; visible: page.showTech
            Text { text: page.tr("section.tech"); font.pixelSize: 14; font.bold: true; color: page.textColor }
            Card {
                Rectangle {
                    width: parent.width; height: 32; color: page.dark ? "#2c2c2c" : "#e9e9e9"
                    Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: page.tr("col.group"); font.pixelSize: 12; font.bold: true; color: page.mutedColor }
                    Text { x: 130; anchors.verticalCenter: parent.verticalCenter; text: page.tr("col.value"); font.pixelSize: 12; font.bold: true; color: page.mutedColor }
                }
                Repeater {
                    model: Permissions.detailRows(page.permissions)
                    Column {
                        required property var modelData
                        width: parent.width
                        Line {}
                        Item {
                            width: parent.width; height: Math.max(36, techValue.implicitHeight + 16)
                            Text { x: 14; y: 8; text: modelData.group; font.pixelSize: 12; font.family: "monospace"; color: page.textColor }
                            Text { id: techValue; x: 130; y: 8; width: parent.width - 144; text: modelData.values; wrapMode: Text.WrapAnywhere
                                   font.pixelSize: 12; font.family: "monospace"; color: page.mutedColor }
                        }
                    }
                }
            }
        }

        Text { text: page.tr("section.portals"); font.pixelSize: 14; font.bold: true; color: page.textColor }
        Text { width: parent.width; text: page.tr("portalHint"); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.mutedColor }
        Card {
            Rectangle {
                width: parent.width; height: 32; color: page.dark ? "#2c2c2c" : "#e9e9e9"
                Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: page.tr("col.area"); font.pixelSize: 12; font.bold: true; color: page.mutedColor }
                Text { x: 170; anchors.verticalCenter: parent.verticalCenter; text: page.tr("col.what"); font.pixelSize: 12; font.bold: true; color: page.mutedColor }
                Text { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; text: page.tr("col.access"); font.pixelSize: 12; font.bold: true; color: page.mutedColor }
            }
            Text { visible: page.portalRows.length === 0; x: 14; height: 44; verticalAlignment: Text.AlignVCenter; text: page.tr("noRows"); font.pixelSize: 13; color: page.mutedColor }
            Repeater {
                model: page.portalRows
                Column {
                    required property var modelData
                    width: parent.width
                    Line {}
                    Item {
                        width: parent.width; height: Math.max(46, accessFlow.height + 16)
                        Text { x: 14; width: 150; anchors.verticalCenter: parent.verticalCenter; text: page.tableName(modelData.table); font.pixelSize: 13; color: page.textColor; elide: Text.ElideRight }
                        Column {
                            x: 170; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 170 - 190; spacing: 1
                            Text { width: parent.width; visible: text !== ""; text: modelData.path ? Permissions.baseName(modelData.path) : (/^(yes|no|0x[0-9a-fA-F]+)$/.test(modelData.data) ? "" : modelData.data)
                                   font.pixelSize: 13; color: page.textColor; elide: Text.ElideMiddle }
                            Text { width: parent.width; visible: modelData.path !== ""; text: modelData.path; font.pixelSize: 11; color: page.mutedColor; elide: Text.ElideMiddle }
                        }
                        Flow {
                            id: accessFlow
                            width: 176; spacing: 4; layoutDirection: Qt.RightToLeft
                            anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                            Repeater {
                                model: modelData.permissions.length ? modelData.permissions : [modelData.data === "no" ? "no" : "yes"]
                                Pill { required property string modelData; good: modelData !== "no"; label: page.permText([modelData]) }
                            }
                        }
                    }
                }
            }
        }
        Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: page.tr("portalReset"); onClicked: page.change("portalReset", false) }
    }
}
