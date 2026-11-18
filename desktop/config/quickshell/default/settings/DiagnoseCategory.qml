import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

// Diagnosis: failed services, errors since boot, package changes before them, Hyprland problems.
// Data comes from windoesnot-diagnose (read-only). Time proximity is shown as proximity, never as a cause.
Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color cardColor: dark ? "#232323" : "#f4f4f4"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d6d6d6"
    readonly property color textColor: dark ? "#ffffff" : "#1a1a1a"
    readonly property color mutedColor: dark ? "#aaaaaa" : "#666666"
    readonly property color warnColor: "#e8a020"
    property bool autoLoad: true
    property bool busy: false
    property bool ready: false
    property bool failedToLoad: false
    property var diag: ({failed: [], errors: {available: true, entries: []}, packages: {available: true, entries: []}, hyprland: {available: false, errors: [], plugins: []}, disk: [], checks: []})
    property string resultKey: ""
    width: parent ? parent.width : 650
    spacing: 16

    function tr(key) { return Lang.get("diagnose." + key, _lang) }
    function stamp(t) { return Qt.formatDateTime(new Date(t * 1000), "dd.MM. hh:mm") }
    function sizeText(bytes) { return (bytes / 1073741824).toFixed(1) + " GiB" }
    readonly property var realErrors: diag.errors.entries.filter(function(e) { return e.known === "" })
    readonly property int findings: diag.failed.length + realErrors.length + diag.hyprland.errors.length + diag.checks.filter(function(c) { return c.status === "warn" }).length
    function refresh() { if (busy) return; busy = true; failedToLoad = false; probe.running = true }
    function copyReport() { resultKey = ""; copyProc.running = true }
    function saveReport() { resultKey = ""; saveProc.running = true }
    Component.onCompleted: if (autoLoad) refresh()

    Process {
        id: probe
        command: ["windoesnot-diagnose"]
        stdout: StdioCollector { id: probeOut }
        onExited: function(code) {
            page.busy = false
            try { page.diag = JSON.parse(probeOut.text); page.ready = true } catch (e) { page.failedToLoad = true }
            if (code !== 0) page.failedToLoad = true
        }
    }
    Process {
        id: copyProc
        command: ["bash", "-c", "windoesnot-diagnose --report | wl-copy"]
        onExited: function(code) { page.resultKey = code === 0 ? "copied" : "failed" }
    }
    Process {
        id: saveProc
        command: ["bash", "-c", "d=\"$(xdg-user-dir DOWNLOAD 2>/dev/null || echo \"$HOME\")\"; mkdir -p \"$d\"; windoesnot-diagnose --report > \"$d/windoesnot-diagnose-$(date +%Y%m%d-%H%M).txt\""]
        onExited: function(code) { page.resultKey = code === 0 ? "saved" : "failed" }
    }

    component Card: Rectangle {
        default property alias rows: rowColumn.data
        width: parent.width; height: rowColumn.height + 2; radius: 8
        color: page.cardColor; border.color: page.lineColor; border.width: 1; clip: true
        Column { id: rowColumn; x: 1; y: 1; width: parent.width - 2 }
    }
    component Line: Rectangle { width: parent.width; height: 1; color: page.lineColor }
    component Pill: Rectangle {
        property string label: ""
        property bool warn: false
        implicitWidth: pillText.implicitWidth + 20; implicitHeight: 24; radius: 12
        color: warn ? Qt.rgba(0.91, 0.63, 0.13, 0.2) : (page.dark ? "#333333" : "#e4e4e4")
        Text { id: pillText; anchors.centerIn: parent; text: parent.label; font.pixelSize: 12; font.bold: parent.warn; color: parent.warn ? page.warnColor : page.mutedColor }
    }
    component Heading: Text { font.pixelSize: 14; font.bold: true; color: page.textColor }
    component Empty: Text { x: 14; height: 44; verticalAlignment: Text.AlignVCenter; font.pixelSize: 13; color: page.mutedColor }

    Text { text: page.tr("title"); font.pixelSize: 18; font.bold: true; color: page.textColor }
    Text { width: parent.width; text: page.tr("intro"); wrapMode: Text.WordWrap; color: page.mutedColor; font.pixelSize: 13 }
    Text { visible: page.failedToLoad; text: page.tr("error"); color: "#cc4444" }

    // Summary
    Rectangle {
        visible: page.ready
        width: parent.width; height: summaryText.implicitHeight + 28; radius: 8
        color: page.findings === 0 ? Qt.rgba(0.2, 0.7, 0.35, 0.12) : Qt.rgba(0.91, 0.63, 0.13, 0.12)
        border.color: page.findings === 0 ? "#3aa655" : page.warnColor; border.width: 1
        Text {
            id: summaryText; x: 14; y: 14; width: parent.width - 28; wrapMode: Text.WordWrap; font.pixelSize: 14; font.bold: true; color: page.textColor
            text: page.findings === 0 ? page.tr("allGood") : page.tr("findings").replace("%1", page.findings)
        }
    }
    Row {
        spacing: 10
        Tools.SystemToolsButton { settingsMenu: page.settingsMenu; primary: true; enabled: !page.busy; text: page.busy ? page.tr("checking") : page.tr("recheck"); onClicked: page.refresh() }
        Tools.SystemToolsButton { settingsMenu: page.settingsMenu; enabled: page.ready; text: page.tr("copy"); onClicked: page.copyReport() }
        Tools.SystemToolsButton { settingsMenu: page.settingsMenu; enabled: page.ready; text: page.tr("save"); onClicked: page.saveReport() }
    }
    Text { visible: page.resultKey !== ""; text: page.resultKey ? page.tr("result." + page.resultKey) : ""; font.pixelSize: 12; color: page.resultKey === "failed" ? "#cc4444" : page.mutedColor }

    Column {
        visible: page.ready
        width: parent.width; spacing: 16

        Heading { text: page.tr("checks") }
        Card {
            Repeater {
                model: page.diag.checks
                Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    Line { visible: index > 0 }
                    Item {
                        width: parent.width; height: 44
                        Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: page.tr("check." + modelData.id); font.pixelSize: 13; color: page.textColor }
                        Pill {
                            anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                            warn: modelData.status === "warn"
                            label: modelData.status === "ok" ? page.tr("statusOk") : (modelData.status === "warn" ? page.tr("statusWarn") : page.tr("statusUnknown"))
                        }
                    }
                    Text {
                        visible: modelData.status === "warn"
                        x: 14; width: parent.width - 28; bottomPadding: 10; wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.warnColor
                        text: page.tr("check." + modelData.id + "." + (modelData.detail || "warn")).replace("%1", modelData.detail)
                    }
                }
            }
        }

        Heading { text: page.tr("services") }
        Card {
            Empty { visible: page.diag.failed.length === 0; text: page.tr("noFailed") }
            Repeater {
                model: page.diag.failed
                Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    Line { visible: index > 0 }
                    Item {
                        width: parent.width; height: 46
                        Column {
                            x: 14; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 120; spacing: 1
                            Text { width: parent.width; text: modelData.unit; font.pixelSize: 13; color: page.textColor; elide: Text.ElideMiddle }
                            Text { width: parent.width; visible: text !== ""; text: modelData.description; font.pixelSize: 11; color: page.mutedColor; elide: Text.ElideRight }
                        }
                        Pill { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; warn: true; label: modelData.scope === "user" ? page.tr("scopeUser") : page.tr("scopeSystem") }
                    }
                }
            }
        }

        Heading { text: page.tr("errors") }
        Text { width: parent.width; text: page.tr("errorsHint"); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.mutedColor }
        Card {
            Empty { visible: !page.diag.errors.available; text: page.tr("journalDenied") }
            Empty { visible: page.diag.errors.available && page.diag.errors.entries.length === 0; text: page.tr("noErrors") }
            Repeater {
                model: page.diag.errors.entries
                Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    Line { visible: index > 0 }
                    Item {
                        width: parent.width; height: Math.max(52, msgColumn.implicitHeight + 16)
                        Text { x: 14; y: 10; width: 86; text: page.stamp(modelData.time); font.pixelSize: 12; color: page.mutedColor }
                        Column {
                            id: msgColumn
                            x: 106; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 106 - (modelData.known !== "" ? 170 : 60); spacing: 1
                            Text { width: parent.width; text: modelData.source; font.pixelSize: 12; font.bold: true; color: modelData.known !== "" ? page.mutedColor : page.textColor; elide: Text.ElideRight }
                            Text { width: parent.width; text: modelData.message; wrapMode: Text.WrapAnywhere; maximumLineCount: 3; elide: Text.ElideRight; font.pixelSize: 12; color: page.mutedColor }
                        }
                        Row {
                            anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                            Pill { visible: modelData.count > 1; label: "×" + modelData.count }
                            Pill { visible: modelData.known !== ""; label: page.tr("harmless") }
                        }
                    }
                    Text { visible: modelData.known !== ""; x: 106; width: parent.width - 120; bottomPadding: 8; text: page.tr("known." + modelData.known); wrapMode: Text.WordWrap; font.pixelSize: 11; color: page.mutedColor }
                }
            }
        }

        Heading { text: page.tr("packages") }
        Text { width: parent.width; text: page.tr("packagesHint"); wrapMode: Text.WordWrap; font.pixelSize: 12; color: page.mutedColor }
        Card {
            Empty { visible: page.diag.packages.entries.length === 0; text: page.tr("noPackages") }
            Repeater {
                model: page.diag.packages.entries
                Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    Line { visible: index > 0 }
                    Item {
                        width: parent.width; height: 38
                        Text { x: 14; anchors.verticalCenter: parent.verticalCenter; width: 86; text: page.stamp(modelData.time); font.pixelSize: 12; color: page.mutedColor }
                        Text { x: 106; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 106 - 130; text: modelData.package + "  " + modelData.version; elide: Text.ElideRight; font.pixelSize: 12; color: page.textColor }
                        Pill { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; label: page.tr("action." + modelData.action) }
                    }
                }
            }
        }

        Heading { text: page.tr("hyprland") }
        Card {
            Empty { visible: !page.diag.hyprland.available; text: page.tr("hyprlandNone") }
            Empty { visible: page.diag.hyprland.available && page.diag.hyprland.errors.length === 0; text: page.tr("hyprlandOk") }
            Repeater {
                model: page.diag.hyprland.errors
                Text { required property string modelData; x: 14; width: parent.width - 28; topPadding: 8; bottomPadding: 8; text: modelData; wrapMode: Text.WrapAnywhere; font.pixelSize: 12; color: page.warnColor }
            }
        }

        Heading { text: page.tr("disk") }
        Card {
            Repeater {
                model: page.diag.disk
                Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    Line { visible: index > 0 }
                    Item {
                        width: parent.width; height: 44
                        Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: modelData.path; font.pixelSize: 13; color: page.textColor }
                        Pill {
                            anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                            warn: modelData.free < modelData.total * 0.1
                            label: page.tr("free").replace("%1", page.sizeText(modelData.free)).replace("%2", page.sizeText(modelData.total))
                        }
                    }
                }
            }
        }
    }
}
