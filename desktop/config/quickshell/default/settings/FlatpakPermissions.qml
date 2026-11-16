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
    property string portalText: ""
    property string stage: "list"
    property bool ready: false
    property bool failed: false
    spacing: 12
    function tr(key) { return Lang.get("appPermissions." + key, language) }
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
                page.portalText = Permissions.portals(output.text, page.appId)
                page.ready = true
            } else if (page.stage === "changed") page.load(page.appId)
        }
    }
    Text { text: page.tr("title"); font.pixelSize: 18; font.bold: true; color: settingsMenu.darkMode ? "#fff" : "#1a1a1a" }
    Text { width: parent.width; text: page.tr("intro"); wrapMode: Text.WordWrap; color: settingsMenu.darkMode ? "#bbb" : "#555" }
    Text { visible: page.ready && !page.failed && page.appList.length === 0; text: page.tr("empty"); color: settingsMenu.darkMode ? "#bbb" : "#555" }
    Text { visible: page.failed; text: page.tr("error"); color: "#cc4444" }
    Button { visible: page.failed; text: page.tr("retry"); onClicked: page.appId ? page.load(page.appId) : page.start(["windoesnot-bounded", "15", "flatpak", "list", "--app", "--columns=application,name"], "list") }
    ComboBox {
        width: Math.min(parent.width, 400); visible: page.appList.length > 0; enabled: page.ready
        model: page.appList; textRole: "name"
        onActivated: page.load(page.appList[index].id)
    }
    Column {
        width: parent.width; spacing: 12; visible: page.appId !== "" && page.ready && !page.failed
        Text { width: parent.width; text: page.tr("restart"); wrapMode: Text.WordWrap; color: settingsMenu.darkMode ? "#bbb" : "#555" }
        Repeater {
            model: [
                { title: "files", detail: "filesHint", action: "home", group: "filesystems", value: "home" },
                { title: "network", detail: "networkHint", action: "network", group: "shared", value: "network" },
                { title: "devices", detail: "devicesHint", action: "devices", group: "devices", value: "all" }
            ]
            Column {
                required property var modelData
                width: parent.width; spacing: 4
                Tools.SystemToolsToggle {
                    settingsMenu: page.settingsMenu
                    text: page.tr(modelData.title)
                    checked: Permissions.has(page.permissions, modelData.group, modelData.value)
                    onToggled: page.change(modelData.action, checked)
                }
                Text { width: parent.width; text: page.tr(modelData.detail); wrapMode: Text.WordWrap; color: settingsMenu.darkMode ? "#aaa" : "#666" }
            }
        }
        Text { width: parent.width; text: page.tr("other") + "\n" + page.tr("downloads") + ": " + (Permissions.has(page.permissions, "filesystems", "xdg-download") ? page.tr("yes") : page.tr("no")) + "\n" + page.tr("gpu") + ": " + (Permissions.has(page.permissions, "devices", "dri") ? page.tr("yes") : page.tr("no")) + "\n" + page.tr("session") + ": " + (Permissions.has(page.permissions, "shared", "ipc") ? page.tr("yes") : page.tr("no")); wrapMode: Text.WordWrap; color: settingsMenu.darkMode ? "#bbb" : "#555" }
        Text { width: parent.width; text: page.tr("details") + "\n" + Permissions.details(page.permissions); wrapMode: Text.WrapAnywhere; color: settingsMenu.darkMode ? "#bbb" : "#555" }
        Button { text: page.tr("reset"); onClicked: page.change("reset", false) }
        Text { width: parent.width; text: page.tr("portalHint"); wrapMode: Text.WordWrap; color: settingsMenu.darkMode ? "#bbb" : "#555" }
        Text { width: parent.width; text: page.portalText || page.tr("portalEmpty"); wrapMode: Text.WrapAnywhere; color: settingsMenu.darkMode ? "#bbb" : "#555" }
        Button { text: page.tr("portalReset"); onClicked: page.change("portalReset", false) }
    }
}
