import QtQuick
import QtQuick.Effects
import Quickshell.Io

Item {
    id: dockerPanel
    width: 340
    height: 420

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property bool darkMode: true
    property bool windowVisible: false

    property var containersModel: ListModel {}
    property int runningCount: 0

    clip: true

    Component.onCompleted: if (windowVisible) refreshContainers()

    onWindowVisibleChanged: {
        if (windowVisible) refreshContainers()
    }

    Timer {
        interval: 3000
        running: dockerPanel.windowVisible
        repeat: true
        onTriggered: refreshContainers()
    }

    function refreshContainers() {
        listProc.running = true
    }

    Process {
        id: listProc
        command: ["bash", "-c", "docker ps -a --format '{{.Names}}|{{.State}}|{{.Status}}|{{.Image}}|{{.Ports}}'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.trim().split('\n')
                var newList = []
                var running = 0
                for (var i = 0; i < lines.length; i++) {
                    var l = lines[i].trim()
                    if (l.length === 0) continue
                    var p = l.split('|')
                    if (p.length < 4) continue
                    var state = p[1].trim()
                    if (state === "running") running++
                    var ports = p[4] ? p[4].trim() : ""
                    var hostPorts = []
                    var portMatches = ports.match(/(?:0\.0\.0\.0:|:::)(\d+)->/g)
                    if (portMatches) {
                        for (var m = 0; m < portMatches.length; m++) {
                            var hp = portMatches[m].replace(/(?:0\.0\.0\.0:|:::)/, '').replace('->', '')
                            if (hostPorts.indexOf(hp) < 0) hostPorts.push(hp)
                        }
                    }
                    var portShort = hostPorts.slice(0, 3).map(function(x) { return ":" + x }).join("  ")
                    newList.push({
                        name: p[0].trim(),
                        state: state,
                        image: p[3].trim(),
                        ports: portShort,
                        firstPort: hostPorts.length > 0 ? hostPorts[0] : ""
                    })
                }
                dockerPanel.runningCount = running
                containersModel.clear()
                for (var j = 0; j < newList.length; j++) {
                    containersModel.append(newList[j])
                }
            }
        }
    }

    Process {
        id: actionProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) refreshTimer.start()
        }
    }

    Timer {
        id: refreshTimer
        interval: 600
        repeat: false
        onTriggered: refreshContainers()
    }

    // Background — no radius at bottom (flush on taskbar)
    Rectangle {
        anchors.fill: parent
        topLeftRadius: dockerPanel.borderRadius
        topRightRadius: dockerPanel.borderRadius
        bottomLeftRadius: 0
        bottomRightRadius: 0
        color: dockerPanel.darkMode
            ? Qt.rgba(0.125, 0.125, 0.125, 0.93)
            : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        border.color: dockerPanel.darkMode ? "#3a3a3f" : "#c0c0c0"
        border.width: 1
    }

    Column {
        anchors.fill: parent
        anchors.margins: 15
        spacing: 10

        // Header: icon+title left, badge right
        Item {
            width: parent.width
            height: 26

            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Image {
                    source: Qt.resolvedUrl("../img/Win11-dark/places/24/folder-docker.svg")
                    width: 20; height: 20
                    smooth: true; antialiasing: true
                    anchors.verticalCenter: parent.verticalCenter
                    layer.enabled: !dockerPanel.darkMode
                    layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                }

                Text {
                    text: "Docker"
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: dockerPanel.darkMode ? "#ffffff" : "#000000"
                    anchors.verticalCenter: parent.verticalCenter
                    antialiasing: true
                    renderType: Text.NativeRendering
                }
            }

            Rectangle {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: badgeText.width + 14
                height: 20
                radius: 10
                color: dockerPanel.runningCount > 0
                    ? Qt.rgba(dockerPanel.accentColor.r, dockerPanel.accentColor.g, dockerPanel.accentColor.b, 0.2)
                    : Qt.rgba(0.3, 0.3, 0.3, 0.4)
                border.width: 1
                border.color: dockerPanel.runningCount > 0
                    ? Qt.rgba(dockerPanel.accentColor.r, dockerPanel.accentColor.g, dockerPanel.accentColor.b, 0.5)
                    : "transparent"

                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: dockerPanel.runningCount + " running"
                    font.pixelSize: 11
                    color: dockerPanel.runningCount > 0
                        ? dockerPanel.accentColor
                        : (dockerPanel.darkMode ? "#888" : "#666")
                }
            }
        }

        // Divider
        Rectangle {
            width: parent.width
            height: 1
            color: dockerPanel.darkMode ? "#3a3a3a" : "#d0d0d0"
        }

        // Container list — same outer style as Audio device list
        Rectangle {
            width: parent.width
            height: dockerPanel.height - 82
            radius: 8
            color: dockerPanel.darkMode
                ? Qt.rgba(0.1, 0.1, 0.1, 0.5)
                : Qt.rgba(0.9, 0.9, 0.9, 0.8)
            border.width: 1
            border.color: dockerPanel.darkMode
                ? Qt.rgba(0.23, 0.23, 0.23, 0.5)
                : Qt.rgba(0.7, 0.7, 0.7, 0.8)
            clip: true

            ListView {
                id: containerList
                anchors.fill: parent
                anchors.margins: 5
                spacing: 4
                clip: true
                model: dockerPanel.containersModel

                delegate: Rectangle {
                    id: containerCard
                    width: containerList.width
                    height: 66
                    radius: 6
                    // Audio-style hover colors
                    color: (bodyArea.containsMouse || btnStop.containsMouse || btnRestart.containsMouse || btnRemove.containsMouse)
                        ? Qt.rgba(0.16, 0.16, 0.16, 0.6)
                        : Qt.rgba(0.12, 0.12, 0.12, 0.4)
                    Behavior on color { ColorAnimation { duration: 150 } }

                    // Left body: status dot + text
                    Row {
                        anchors { top: parent.top; left: parent.left; bottom: parent.bottom; margins: 10 }
                        width: parent.width - 106
                        spacing: 10

                        // Status dot
                        Rectangle {
                            width: 8; height: 8; radius: 4
                            anchors.verticalCenter: parent.verticalCenter
                            color: {
                                if (model.state === "running")    return "#4caf50"
                                if (model.state === "restarting") return "#ff9800"
                                if (model.state === "paused")     return "#2196f3"
                                return "#555555"
                            }
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 3
                            width: parent.width - 18

                            Row {
                                spacing: 5
                                Text {
                                    text: model.name
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    color: dockerPanel.darkMode ? "#ffffff" : "#111111"
                                    elide: Text.ElideRight
                                    width: Math.min(implicitWidth, 155)
                                    antialiasing: true
                                    renderType: Text.NativeRendering
                                }
                                ProjectIcon {
                                    visible: model.firstPort.length > 0
                                    name: "network"
                                    font.pixelSize: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    opacity: bodyArea.containsMouse ? 1.0 : 0.4
                                    Behavior on opacity { NumberAnimation { duration: 150 } }
                                }
                            }

                            Text {
                                text: model.image
                                font.pixelSize: 11
                                color: dockerPanel.darkMode ? "#888888" : "#555555"
                                elide: Text.ElideRight
                                width: parent.width
                            }

                            Text {
                                visible: model.ports.length > 0
                                text: model.ports
                                font.pixelSize: 10
                                color: dockerPanel.darkMode ? "#606060" : "#777777"
                            }
                        }
                    }

                    // Clickable overlay on left body
                    MouseArea {
                        id: bodyArea
                        anchors { top: parent.top; left: parent.left; bottom: parent.bottom }
                        width: parent.width - 106
                        hoverEnabled: true
                        cursorShape: model.firstPort.length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (model.firstPort.length > 0) {
                                Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["bash", "-c", "xdg-open http://localhost:' + model.firstPort + ' & disown"]; ' +
                                    'running: true }',
                                    containerCard
                                )
                            }
                        }
                    }

                    // Action buttons (right side)
                    Row {
                        anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        spacing: 4

                        Rectangle {
                            width: 26; height: 26; radius: 6
                            color: btnStop.containsMouse
                                ? (model.state === "running" ? Qt.rgba(0.85, 0.25, 0.25, 0.4) : Qt.rgba(0.25, 0.7, 0.25, 0.4))
                                : Qt.rgba(0.18, 0.18, 0.18, 0.8)
                            border.width: 1
                            border.color: model.state === "running" ? Qt.rgba(0.7, 0.3, 0.3, 0.4) : Qt.rgba(0.3, 0.65, 0.3, 0.4)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text {
                                anchors.centerIn: parent
                                text: model.state === "running" ? "⏹" : "▶"
                                font.pixelSize: 11
                                color: model.state === "running" ? "#ef5350" : "#66bb6a"
                            }
                            MouseArea {
                                id: btnStop
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    actionProc.command = ["bash", "-c",
                                        model.state === "running" ? "docker stop " + model.name : "docker start " + model.name]
                                    actionProc.running = true
                                }
                            }
                        }

                        Rectangle {
                            width: 26; height: 26; radius: 6
                            color: btnRestart.containsMouse ? Qt.rgba(0.85, 0.55, 0.1, 0.35) : Qt.rgba(0.18, 0.18, 0.18, 0.8)
                            border.width: 1
                            border.color: Qt.rgba(0.6, 0.45, 0.1, 0.4)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text {
                                anchors.centerIn: parent
                                text: "↺"
                                font.pixelSize: 14
                                color: "#ffa726"
                            }
                            MouseArea {
                                id: btnRestart
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    actionProc.command = ["bash", "-c", "docker restart " + model.name]
                                    actionProc.running = true
                                }
                            }
                        }

                        Rectangle {
                            width: 26; height: 26; radius: 6
                            color: btnRemove.containsMouse ? Qt.rgba(0.85, 0.2, 0.2, 0.35) : Qt.rgba(0.18, 0.18, 0.18, 0.8)
                            border.width: 1
                            border.color: Qt.rgba(0.6, 0.2, 0.2, 0.4)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text {
                                anchors.centerIn: parent
                                text: "✕"
                                font.pixelSize: 11
                                color: "#ef5350"
                            }
                            MouseArea {
                                id: btnRemove
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    actionProc.command = ["bash", "-c",
                                        model.state === "running" ? "docker rm -f " + model.name : "docker rm " + model.name]
                                    actionProc.running = true
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
