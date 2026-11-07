import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: gpuPanel
    width: 340
    height: 410

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property bool windowVisible: false
    property bool darkMode: true
    property string uiLanguage: "de"
    signal openLact()

    property var gpus: []
    property var processes: []
    property bool lactAvailable: false
    property bool daemonRunning: false
    property bool daemonUnit: false
    property bool loaded: false

    readonly property color textColor: darkMode ? "#ffffff" : "#000000"
    readonly property color subColor: darkMode ? "#999999" : "#666666"
    readonly property color trackColor: darkMode ? "#2a2a2a" : "#d0d0d0"

    function tr(key) { return Lang.get(key, uiLanguage) }

    function refresh() { if (!statusProc.running) statusProc.running = true }

    function tempColor(t) {
        if (t >= 85) return "#e5484d"
        if (t >= 75) return "#f5a524"
        return accentColor
    }

    function fmt(value, unit, digits) {
        return (value === null || value === undefined) ? "" : value.toFixed(digits || 0) + " " + unit
    }

    onWindowVisibleChanged: if (windowVisible) refresh()
    Component.onCompleted: refresh()

    // Polls only while the popup is open.
    Timer {
        interval: 2000
        running: gpuPanel.windowVisible
        repeat: true
        onTriggered: gpuPanel.refresh()
    }

    Process {
        id: statusProc
        command: ["/usr/bin/python3", "-I", Qt.resolvedUrl("gpu_status.py").toString().replace("file://", "")]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(this.text)
                    gpuPanel.gpus = data.gpus || []
                    gpuPanel.processes = data.processes || []
                    gpuPanel.lactAvailable = !!data.lact
                    gpuPanel.daemonRunning = !!data.running
                    gpuPanel.daemonUnit = !!data.unit
                    gpuPanel.loaded = true
                } catch (error) {}
            }
        }
    }

    Process {
        id: daemonProc
        running: false
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onExited: gpuPanel.refresh()
    }

    // Installed systems have lactd.service (needs authorisation); without it
    // (e.g. a development host) a per-user daemon is started or stopped.
    function toggleDaemon() {
        if (daemonUnit)
            daemonProc.command = ["pkexec", "systemctl", daemonRunning ? "stop" : "start", "lactd.service"]
        else if (daemonRunning)
            daemonProc.command = ["pkill", "-f", "lact daemon"]
        else
            daemonProc.command = ["bash", "-c", "setsid lact daemon >/dev/null 2>&1 & sleep 2"]
        daemonProc.running = true
    }

    Rectangle {
        anchors.fill: parent
        color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        border.color: darkMode ? "#3a3a3f" : "#c0c0c0"
        border.width: 1
        topLeftRadius: borderRadius
        topRightRadius: borderRadius
        bottomLeftRadius: 0
        bottomRightRadius: 0
    }

    // One labelled bar row: label, value text, filled track.
    component StatBar: Column {
        property string label
        property string valueText
        property real fraction: 0
        property color barColor: gpuPanel.accentColor
        width: parent ? parent.width : 0
        spacing: 3
        Row {
            width: parent.width
            Text { text: label; font.pixelSize: 12; color: gpuPanel.subColor; width: parent.width - valueLabel.implicitWidth }
            Text { id: valueLabel; text: valueText; font.pixelSize: 12; color: gpuPanel.textColor }
        }
        Rectangle {
            width: parent.width; height: 5; radius: 2.5; color: gpuPanel.trackColor
            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, fraction)); height: parent.height; radius: 2.5
                color: barColor
                Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
            }
        }
    }

    Item {
        anchors.fill: parent
        anchors.margins: 15

        Column {
            id: content
            width: parent.width
            spacing: 12

            Text {
                text: gpuPanel.tr("graphics.title")
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: gpuPanel.textColor
            }

            Rectangle { width: parent.width; height: 1; color: darkMode ? "#3a3a3a" : "#d0d0d0" }

            Text {
                visible: gpuPanel.loaded && gpuPanel.daemonRunning && gpuPanel.gpus.length === 0
                text: gpuPanel.tr("graphics.noGpu")
                font.pixelSize: 13
                color: gpuPanel.subColor
            }

            // LACT service stopped: explain and offer to start it right here
            Column {
                width: parent.width
                spacing: 10
                visible: gpuPanel.loaded && !gpuPanel.daemonRunning
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: gpuPanel.lactAvailable ? gpuPanel.tr("graphics.daemonOff") : gpuPanel.tr("graphics.noLact")
                    font.pixelSize: 13
                    color: gpuPanel.subColor
                }
                Rectangle {
                    visible: gpuPanel.lactAvailable
                    width: parent.width; height: 32; radius: 6
                    color: gpuPanel.accentColor
                    Text { anchors.centerIn: parent; text: gpuPanel.tr("graphics.daemonStartNow"); font.pixelSize: 13; color: "#ffffff" }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: gpuPanel.toggleDaemon()
                    }
                }
            }

            Repeater {
                model: gpuPanel.gpus
                delegate: Column {
                    id: card
                    required property var modelData
                    required property int index
                    width: content.width
                    spacing: 7

                    Row {
                        width: parent.width
                        spacing: 8
                        Text {
                            text: card.modelData.name
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: gpuPanel.textColor
                            elide: Text.ElideRight
                            width: parent.width - (tempText.visible ? tempText.implicitWidth + 8 : 0)
                        }
                        Text {
                            id: tempText
                            visible: card.modelData.temp !== null && card.modelData.temp !== undefined
                            text: visible ? Math.round(card.modelData.temp) + " °C" + (card.modelData.tempHotspot ? " (" + Math.round(card.modelData.tempHotspot) + ")" : "") + (card.modelData.throttling ? " ⚠" : "") : ""
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: visible ? gpuPanel.tempColor(card.modelData.temp) : gpuPanel.textColor
                        }
                    }

                    StatBar {
                        visible: card.modelData.util !== null && card.modelData.util !== undefined
                        label: gpuPanel.tr("graphics.load")
                        valueText: gpuPanel.fmt(card.modelData.util, "%")
                        fraction: (card.modelData.util || 0) / 100
                    }
                    StatBar {
                        visible: card.modelData.vramTotal !== undefined && card.modelData.vramTotal > 0
                        label: gpuPanel.tr("graphics.vram")
                        valueText: visible ? (card.modelData.vramUsed / 1024).toFixed(1) + " / " + (card.modelData.vramTotal / 1024).toFixed(1) + " GB" : ""
                        fraction: visible ? card.modelData.vramUsed / card.modelData.vramTotal : 0
                    }
                    StatBar {
                        visible: card.modelData.power !== null && card.modelData.power !== undefined
                        label: gpuPanel.tr("graphics.power")
                        valueText: visible ? Math.round(card.modelData.power) + (card.modelData.powerLimit ? " / " + Math.round(card.modelData.powerLimit) : "") + " W" : ""
                        fraction: card.modelData.powerLimit ? card.modelData.power / card.modelData.powerLimit : 0
                    }
                    Row {
                        width: parent.width
                        visible: card.modelData.fanPct !== undefined || card.modelData.fanRpm !== undefined
                                 || card.modelData.clockCore !== undefined
                        spacing: 0
                        Text {
                            visible: card.modelData.fanPct !== undefined || card.modelData.fanRpm !== undefined
                            width: visible ? parent.width / 2 : 0
                            font.pixelSize: 12
                            color: gpuPanel.subColor
                            text: {
                                var m = card.modelData
                                var v = m.fanRpm !== undefined && m.fanRpm !== null ? Math.round(m.fanRpm) + " RPM"
                                    : (m.fanPct ? Math.round(m.fanPct) + " %" : gpuPanel.tr("graphics.fanIdle"))
                                return gpuPanel.tr("graphics.fan") + ": " + v
                            }
                        }
                        Text {
                            visible: card.modelData.clockCore !== undefined
                            font.pixelSize: 12
                            color: gpuPanel.subColor
                            text: visible ? gpuPanel.tr("graphics.clock") + ": " + Math.round(card.modelData.clockCore)
                                + (card.modelData.clockMem ? " / " + Math.round(card.modelData.clockMem) : "") + " MHz" : ""
                        }
                    }

                    Rectangle {
                        visible: index < gpuPanel.gpus.length - 1
                        width: parent.width; height: 1; color: darkMode ? "#2f2f2f" : "#dcdcdc"
                    }
                }
            }

            Column {
                width: parent.width
                spacing: 3
                visible: gpuPanel.processes.length > 0
                Text { text: gpuPanel.tr("graphics.apps"); font.pixelSize: 12; color: gpuPanel.subColor }
                Repeater {
                    model: gpuPanel.processes
                    delegate: Row {
                        required property var modelData
                        width: content.width
                        Text { text: modelData.name; font.pixelSize: 12; color: gpuPanel.textColor; width: parent.width - 70; elide: Text.ElideRight }
                        Text { text: modelData.vram ? Math.round(modelData.vram) + " MB" : ""; font.pixelSize: 12; color: gpuPanel.subColor }
                    }
                }
            }

            // LACT service (only where the lactd unit is installed)
            Row {
                width: parent.width
                visible: gpuPanel.daemonRunning
                spacing: 8
                Rectangle {
                    width: 8; height: 8; radius: 4
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#3fb950"
                }
                Text {
                    text: gpuPanel.tr("graphics.daemon")
                    font.pixelSize: 13
                    color: gpuPanel.textColor
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 8 - 8 - 90
                }
                Rectangle {
                    width: 82; height: 26; radius: 6
                    color: darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 1
                    border.color: darkMode ? "#3a3a3a" : "#d0d0d0"
                    Text {
                        anchors.centerIn: parent
                        text: gpuPanel.tr("graphics.daemonStop")
                        font.pixelSize: 12
                        color: gpuPanel.textColor
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: gpuPanel.toggleDaemon()
                    }
                }
            }

            Rectangle {
                visible: gpuPanel.lactAvailable && gpuPanel.daemonRunning
                width: parent.width; height: 32; radius: 6
                color: gpuPanel.accentColor
                Text { anchors.centerIn: parent; text: gpuPanel.tr("graphics.open"); font.pixelSize: 13; color: "#ffffff" }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: gpuPanel.openLact()
                }
            }
        }
    }
}
