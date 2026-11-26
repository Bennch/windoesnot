import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang
import "../i18n" as UiI

// Security overview: one traffic light plus one row per protection. Read-only; the data comes from
// security_status.py (no root). The buttons only jump to the page or tool that changes the setting.
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color cardColor: dark ? "#232323" : "#f4f4f4"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d6d6d6"
    readonly property color textColor: dark ? "#ffffff" : "#1a1a1a"
    readonly property color mutedColor: dark ? "#aaaaaa" : "#666666"
    readonly property color okColor: "#3aa655"
    readonly property color warnColor: "#e8a020"
    readonly property color badColor: "#cc4444"
    property bool autoLoad: true
    property bool busy: false
    property bool ready: false
    property bool failedToLoad: false
    property var status: ({level: "unknown", items: []})
    width: parent ? parent.width : 650
    spacing: 16

    function tr(key) { return Lang.get("security." + key, _lang) }
    function stateColor(state) { return state === "ok" ? okColor : (state === "warn" ? warnColor : (state === "bad" ? badColor : mutedColor)) }
    function detailText(entry) {
        var parts = String(entry.detail).split(":")
        return tr("d." + entry.id + "." + parts[0]).replace("%1", parts.length > 1 ? parts.slice(1).join(":") : "")
    }
    // Where the setting lives: a Settings page, or a tool of its own. Items without a target show no button.
    readonly property var pages: ({ updates: "updates", backups: "backups", restore_points: "backups", screen_lock: "power", password: "maintenance" })
    readonly property var pageLabels: ({ updates: "updates", backups: "backups", restore_points: "backups", screen_lock: "power", password: "account" })
    readonly property var tools: ({ firewall: ["windoesnot-open-network", "--page", "firewall"] })
    function hasTarget(id) { return pages[id] !== undefined || tools[id] !== undefined }
    function openItem(id) {
        if (pages[id]) { settingsMenu.currentCategory = pages[id]; return }
        if (tools[id]) { openApp.command = tools[id]; openApp.running = true }
    }
    function refresh() { if (busy) return; busy = true; failedToLoad = false; probe.running = true }
    Component.onCompleted: if (autoLoad) refresh()

    Process {
        id: probe
        command: ["python3", "-I", "/usr/lib/windoesnot/security_status.py"]
        stdout: StdioCollector { id: probeOut }
        onExited: function(code) {
            page.busy = false
            try { page.status = JSON.parse(probeOut.text); page.ready = code === 0 } catch (e) { page.failedToLoad = true }
            if (code !== 0) page.failedToLoad = true
        }
    }
    Process { id: openApp }

    component Card: Rectangle {
        default property alias rows: rowColumn.data
        width: parent.width; height: rowColumn.height + 2; radius: 8
        color: page.cardColor; border.color: page.lineColor; border.width: 1; clip: true
        Column { id: rowColumn; x: 1; y: 1; width: parent.width - 2 }
    }
    component Line: Rectangle { width: parent.width; height: 1; color: page.lineColor }
    component Pill: Rectangle {
        property string label: ""
        property color tint: page.mutedColor
        implicitWidth: pillText.implicitWidth + 20; implicitHeight: 24; radius: 12
        color: Qt.rgba(tint.r, tint.g, tint.b, 0.2)
        Text { id: pillText; anchors.centerIn: parent; text: parent.label; font.pixelSize: UiI.UiScale.px(12); font.bold: true; color: parent.tint }
    }

    Text { text: page.tr("title"); font.pixelSize: UiI.UiScale.px(18); font.bold: true; color: page.textColor }
    Text { width: parent.width; text: page.tr("intro"); wrapMode: Text.WordWrap; color: page.mutedColor; font.pixelSize: UiI.UiScale.px(13) }
    Text { visible: page.failedToLoad; text: page.tr("error"); color: page.badColor }

    // Traffic light
    Rectangle {
        visible: page.ready
        width: parent.width; height: summaryText.implicitHeight + 28; radius: 8
        color: Qt.rgba(page.stateColor(page.status.level).r, page.stateColor(page.status.level).g, page.stateColor(page.status.level).b, 0.12)
        border.color: page.stateColor(page.status.level); border.width: 1
        Text {
            id: summaryText; x: 14; y: 14; width: parent.width - 28; wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(14); font.bold: true; color: page.textColor
            text: page.tr("level." + page.status.level)
        }
    }
    Tools.SystemToolsButton { settingsMenu: page.settingsMenu; primary: true; enabled: !page.busy; text: page.busy ? page.tr("checking") : page.tr("recheck"); onClicked: page.refresh() }

    Card {
        visible: page.ready
        Repeater {
            model: page.status.items
            Column {
                required property var modelData
                required property int index
                width: parent.width
                Line { visible: index > 0 }
                Item {
                    width: parent.width; height: 44
                    Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: page.tr("item." + modelData.id); font.pixelSize: UiI.UiScale.px(13); color: page.textColor }
                    Pill {
                        anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                        tint: page.stateColor(modelData.state)
                        label: page.tr("state." + modelData.state)
                    }
                }
                Text {
                    x: 14; width: parent.width - 28; bottomPadding: openButton.visible ? 6 : 10; wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(12); color: page.mutedColor
                    text: page.detailText(modelData)
                }
                Item {
                    id: openButton
                    visible: page.hasTarget(modelData.id)
                    width: parent.width; height: visible ? 46 : 0
                    Tools.SystemToolsButton {
                        x: 14; y: 0; settingsMenu: page.settingsMenu
                        text: page.tr("open." + (page.pageLabels[modelData.id] ? page.pageLabels[modelData.id] : modelData.id))
                        onClicked: page.openItem(modelData.id)
                    }
                }
            }
        }
    }
}
