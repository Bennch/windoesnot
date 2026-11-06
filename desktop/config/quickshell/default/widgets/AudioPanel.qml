import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: audioPanel
    width: 320
    height: 440
    signal closeRequested()

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12  // Default value, wird von shell.qml gebunden
    property bool windowVisible: false
    property bool darkMode: true  // Wird von shell.qml gesetzt
    property string uiLanguage: "de"  // Bound from shell.qml
    property int volume: 50
    property bool muted: false
    property var outputDevices: []
    property string currentDevice: ""
    property string defaultSink: ""
    property int tab: 0  // 0 = output devices (always shown first), 1 = mixer
    // The lists fill the space between the tabs and the buttons at the bottom, so nothing can overlap them.
    readonly property real listHeight: Math.max(90, audioPanel.height - 15 - quickActionsRow.height - 12
                                                    - (15 + tabRow.y + tabRow.height + mainContent.spacing))

    // Sortiere Geräteliste neu, wenn sich der Standard-Sink ändert
    onDefaultSinkChanged: {
        if (outputDevices.length > 0) {
            sortDevices()
        }
    }

    function sortDevices() {
        var devices = outputDevices.slice() // Kopie erstellen
        devices.sort(function(a, b) {
            if (a.name === audioPanel.defaultSink) return -1
            if (b.name === audioPanel.defaultSink) return 1
            return 0
        })
        outputDevices = devices
    }

    property bool initialized: false

    Component.onCompleted: {
        // Load initial data once at startup
        updateAudioState()
        getOutputDevicesProc.running = true
        initialized = true
    }

    // Startup timer to ensure data is loaded after component initialization
    Timer {
        id: startupTimer
        interval: 300
        running: true
        repeat: false
        onTriggered: {
            updateAudioState()
        }
    }

    // Update when panel becomes visible
    onVisibleChanged: {
        if (visible) {
            audioPanel.tab = 0
            updateAudioState()
        }
    }

    function updateAudioState() {
        getVolumeProc.running = true
        getMuteStatusProc.running = true
        getDefaultSinkProc.running = true
        getOutputDevicesProc.running = true
        getAppStreamsProc.running = true
    }

    Timer {
        interval: 2000
        running: audioPanel.windowVisible  // Only run when window is visible
        repeat: true
        onTriggered: updateAudioState()
    }

    Process {
        id: getDefaultSinkProc
        command: ["bash", "-c", "pactl info | grep 'Default Sink' | awk '{print $3}'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                audioPanel.defaultSink = this.text.trim()
                console.log("Default sink:", audioPanel.defaultSink)
            }
        }
    }

    Process {
        id: getVolumeProc
        command: ["bash", "-c", "pactl get-sink-volume @DEFAULT_SINK@ | grep -oP '\\d+%' | head -1 | tr -d '%'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var vol = parseInt(this.text.trim())
                if (!isNaN(vol)) audioPanel.volume = vol
            }
        }
    }

    Process {
        id: getMuteStatusProc
        command: ["bash", "-c", "pactl get-sink-mute @DEFAULT_SINK@ | grep -oP 'yes|no'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                audioPanel.muted = (this.text.trim() === "yes")
            }
        }
    }

    // Per-app mixer: one row per playing stream (pactl sink inputs), kept in a ListModel that is updated in place
    // so a slider being dragged is never rebuilt by the 2 second refresh.
    ListModel { id: appModel }
    property int draggingApp: -1

    function syncApps(streams) {
        var seen = {}
        for (var i = 0; i < streams.length; i++) {
            var st = streams[i]
            seen[st.id] = true
            var found = -1
            for (var j = 0; j < appModel.count; j++) if (appModel.get(j).streamId === st.id) { found = j; break }
            if (found < 0) {
                appModel.append({ streamId: st.id, appName: st.name, appIcon: st.icon, appVolume: st.volume, appMuted: st.muted })
            } else {
                appModel.setProperty(found, "appName", st.name)
                appModel.setProperty(found, "appIcon", st.icon)
                appModel.setProperty(found, "appMuted", st.muted)
                if (audioPanel.draggingApp !== st.id) appModel.setProperty(found, "appVolume", st.volume)
            }
        }
        for (var k = appModel.count - 1; k >= 0; k--) if (!seen[appModel.get(k).streamId]) appModel.remove(k)
    }

    function setAppVolume(streamId, percent) {
        var value = Math.max(0, Math.min(100, Math.round(percent)))
        for (var j = 0; j < appModel.count; j++) if (appModel.get(j).streamId === streamId) appModel.setProperty(j, "appVolume", value)
        setAppVolumeProc.command = ["pactl", "set-sink-input-volume", String(streamId), value + "%"]
        setAppVolumeProc.running = false
        setAppVolumeProc.running = true
    }

    function toggleAppMute(streamId) {
        toggleAppMuteProc.command = ["pactl", "set-sink-input-mute", String(streamId), "toggle"]
        toggleAppMuteProc.running = true
    }

    Process {
        id: getAppStreamsProc
        command: ["pactl", "-f", "json", "list", "sink-inputs"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var streams = []
                try {
                    var data = JSON.parse(this.text)
                    for (var i = 0; i < data.length; i++) {
                        var props = data[i].properties || {}
                        var name = props["application.name"] || props["media.name"] || "?"
                        if (name.indexOf("speech-dispatcher") === 0) continue
                        var vol = 0
                        for (var ch in data[i].volume) vol = Math.max(vol, parseInt(data[i].volume[ch].value_percent))
                        streams.push({ id: data[i].index, name: name,
                                       icon: props["application.icon_name"] || props["application.process.binary"] || "",
                                       volume: isNaN(vol) ? 0 : vol, muted: data[i].mute === true })
                    }
                } catch (e) {}
                audioPanel.syncApps(streams)
            }
        }
    }

    Process { id: setAppVolumeProc; command: ["true"]; running: false }

    Process {
        id: toggleAppMuteProc
        command: ["true"]
        running: false
        onRunningChanged: if (!running) getAppStreamsProc.running = true
    }

    Process {
        id: setVolumeProc
        command: ["bash", "-c", "pactl set-sink-volume @DEFAULT_SINK@ " + audioPanel.volume + "%"]
        running: false
    }

    Process {
        id: toggleMuteProc
        command: ["bash", "-c", "pactl set-sink-mute @DEFAULT_SINK@ toggle"]
        running: false
        onRunningChanged: {
            if (!running) updateAudioState()
        }
    }

    Process {
        id: getOutputDevicesProc
        command: ["bash", "-c", "pactl list sinks | awk 'BEGIN {id=\"\"; name=\"\"; desc=\"\"} /^Sink #/ {if (id != \"\" && name != \"\" && desc != \"\") print id \"|\" name \"|\" desc; id=$2; name=\"\"; desc=\"\"} /^\\tName:/ {name=$2} /device.description =/ {gsub(/.*device.description = \"/, \"\"); gsub(/\".*/, \"\"); desc=$0} END {if (id != \"\" && name != \"\" && desc != \"\") print id \"|\" name \"|\" desc}'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.trim().split('\n')
                var devices = []
                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].length > 0) {
                        var parts = lines[i].split('|')
                        if (parts.length === 3) {
                            devices.push({
                                id: parts[0].replace('#', ''),
                                name: parts[1].trim(),
                                description: parts[2].trim()
                            })
                            console.log("Device:", parts[0], parts[1], parts[2])
                        }
                    }
                }
                audioPanel.outputDevices = devices
                console.log("Total devices:", devices.length)
                // Sortiere nach dem Laden
                sortDevices()
            }
        }
    }

    Process {
        id: setDefaultSinkProc
        command: ["bash", "-c", ""]
        running: false
    }

    // Content Container
    clip: true

    Rectangle {
        anchors.fill: parent
        color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        border.color: darkMode ? "#3a3a3f" : "#c0c0c0"
        border.width: 1
        topLeftRadius: borderRadius
        topRightRadius: borderRadius
        bottomLeftRadius: 0
        bottomRightRadius: 0

        // MouseArea für Scroll-Wheel Lautstärke-Kontrolle
        // Kein Overlay wird angezeigt, da das Panel selbst offen ist
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.NoButton
            onWheel: function(wheel) {
                var delta = wheel.angleDelta.y / 120
                audioPanel.volume = Math.max(0, Math.min(100, audioPanel.volume + (delta * 5)))
                setVolumeProc.running = true
            }
        }
    }

    Item {
        anchors.fill: parent
        anchors.margins: 15

        Column {
            id: mainContent
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 15

            // Header
            Text {
                text: Lang.get("audio.title", uiLanguage)
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: darkMode ? "#ffffff" : "#000000"
                antialiasing: true
                renderType: Text.NativeRendering
            }

            Rectangle {
                width: parent.width
                height: 1
                color: darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // Volume Slider
            Column {
                width: parent.width
                spacing: 10

            Row {
                width: parent.width
                spacing: 10

                Image {
                    // Same icons and steps as the tray: no waves when muted or 0, then one, two, three waves.
                    source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/" + (audioPanel.muted || audioPanel.volume === 0 ? "audio-volume-muted-symbolic.svg"
                            : audioPanel.volume < 33 ? "audio-volume-low-symbolic.svg"
                            : audioPanel.volume < 66 ? "audio-volume-medium-symbolic.svg" : "audio-volume-high-symbolic.svg"))
                    sourceSize.width: 40
                    sourceSize.height: 40
                    width: 20
                    height: 20
                    smooth: true

                    layer.enabled: !darkMode
                    layer.effect: MultiEffect {
                        colorization: 1.0
                        colorizationColor: "#333333"
                    }
                }

                Text {
                    id: volumeLabel
                    text: Lang.get("audio.volume", uiLanguage)
                    font.pixelSize: 14
                    color: darkMode ? "#cccccc" : "#333333"
                }

                Item {
                    width: parent.width - volumeLabel.width - volumePercent.width - 20 - 30
                    height: 1
                }

                Text {
                    id: volumePercent
                    text: audioPanel.muted ? "0%" : (audioPanel.volume + "%")
                    font.pixelSize: 13
                    color: darkMode ? "#999999" : "#666666"
                    horizontalAlignment: Text.AlignRight
                }
            }

            Rectangle {
                width: parent.width
                height: 8
                radius: 4
                color: darkMode ? "#2a2a2a" : "#d0d0d0"

                Rectangle {
                    width: audioPanel.muted ? 0 : (parent.width * (audioPanel.volume / 100))
                    height: parent.height
                    radius: 4
                    color: audioPanel.accentColor
                }

                MouseArea {
                    anchors.fill: parent
                    onPositionChanged: function(mouse) {
                        if (pressed) {
                            audioPanel.volume = Math.max(0, Math.min(100, Math.round((mouse.x / parent.width) * 100)))
                            setVolumeProc.running = true
                        }
                    }
                    onClicked: function(mouse) {
                        audioPanel.volume = Math.max(0, Math.min(100, Math.round((mouse.x / parent.width) * 100)))
                        setVolumeProc.running = true
                    }
                }
            }
        }

        // Switch between the per-app mixer and the output devices (saves space)
        Row {
            id: tabRow
            width: parent.width
            spacing: 6

            Repeater {
                model: [ { key: "audio.outputDevice", index: 0 }, { key: "audio.apps", index: 1 } ]

                delegate: Rectangle {
                    width: (tabRow.width - 6) / 2
                    height: 32
                    radius: 8
                    property bool active: audioPanel.tab === modelData.index
                    color: active ? Qt.rgba(audioPanel.accentColor.r, audioPanel.accentColor.g, audioPanel.accentColor.b, 0.2)
                                  : (tabMouse.containsMouse ? (darkMode ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.85, 0.85, 0.85, 0.8)) : "transparent")
                    border.width: 1
                    border.color: active ? audioPanel.accentColor : (darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.8) : Qt.rgba(0.7, 0.7, 0.7, 0.8))

                    Behavior on color { ColorAnimation { duration: 150 } }

                    Text {
                        anchors.centerIn: parent
                        text: Lang.get(modelData.key, uiLanguage)
                        font.pixelSize: 12
                        font.weight: active ? Font.DemiBold : Font.Normal
                        color: active ? audioPanel.accentColor : (darkMode ? "#cccccc" : "#333333")
                    }

                    MouseArea {
                        id: tabMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: audioPanel.tab = modelData.index
                    }
                }
            }
        }

        // Apps: one slider per playing application
        Column {
            width: parent.width
            visible: audioPanel.tab === 1
            spacing: 8

            Rectangle {
                width: parent.width
                height: audioPanel.listHeight
                radius: 8
                color: darkMode ? Qt.rgba(0.1, 0.1, 0.1, 0.5) : Qt.rgba(0.9, 0.9, 0.9, 0.8)
                border.width: 1
                border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)
                clip: true

                Text {
                    anchors.centerIn: parent
                    visible: appModel.count === 0
                    text: Lang.get("audio.noApps", uiLanguage)
                    font.pixelSize: 12
                    color: darkMode ? "#777777" : "#777777"
                }

                ListView {
                    id: appListView
                    anchors.fill: parent
                    anchors.margins: 5
                    spacing: 4
                    clip: true
                    model: appModel

                    delegate: Item {
                        id: appRow
                        width: appListView.width
                        height: 40

                        Row {
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 6
                            spacing: 8

                            // App icon, letter tile as fallback
                            Item {
                                width: 24
                                height: 24
                                anchors.verticalCenter: parent.verticalCenter
                                Image {
                                    id: appIconImage
                                    anchors.fill: parent
                                    source: model.appIcon !== "" ? Quickshell.iconPath(model.appIcon, true) : ""
                                    sourceSize.width: 48
                                    sourceSize.height: 48
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                    visible: status === Image.Ready
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 6
                                    color: audioPanel.accentColor
                                    visible: !appIconImage.visible
                                    Text {
                                        anchors.centerIn: parent
                                        text: model.appName.length > 0 ? model.appName.charAt(0).toUpperCase() : "?"
                                        color: "#ffffff"
                                        font.pixelSize: 13
                                        font.bold: true
                                    }
                                }
                            }

                            Column {
                                width: parent.width - 24 - 28 - 16
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 4

                                Row {
                                    width: parent.width
                                    Text {
                                        width: parent.width - appPercent.width
                                        text: model.appName
                                        elide: Text.ElideRight
                                        font.pixelSize: 12
                                        color: darkMode ? "#ffffff" : "#000000"
                                    }
                                    Text {
                                        id: appPercent
                                        text: model.appMuted ? "0%" : (model.appVolume + "%")
                                        font.pixelSize: 11
                                        color: darkMode ? "#999999" : "#666666"
                                    }
                                }

                                Rectangle {
                                    width: parent.width
                                    height: 6
                                    radius: 3
                                    color: darkMode ? "#2a2a2a" : "#d0d0d0"

                                    Rectangle {
                                        width: model.appMuted ? 0 : parent.width * Math.min(1, model.appVolume / 100)
                                        height: parent.height
                                        radius: 3
                                        color: audioPanel.accentColor
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        anchors.topMargin: -8
                                        anchors.bottomMargin: -8
                                        preventStealing: true
                                        onPressed: function(mouse) {
                                            audioPanel.draggingApp = model.streamId
                                            audioPanel.setAppVolume(model.streamId, (mouse.x / width) * 100)
                                        }
                                        onPositionChanged: function(mouse) {
                                            if (pressed) audioPanel.setAppVolume(model.streamId, (mouse.x / width) * 100)
                                        }
                                        onReleased: audioPanel.draggingApp = -1
                                        onCanceled: audioPanel.draggingApp = -1
                                    }
                                }
                            }

                            // Mute this app only
                            Item {
                                width: 28
                                height: 28
                                anchors.verticalCenter: parent.verticalCenter

                                Image {
                                    anchors.centerIn: parent
                                    width: 16
                                    height: 16
                                    sourceSize.width: 32
                                    sourceSize.height: 32
                                    source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/" + (model.appMuted ? "audio-volume-muted-symbolic.svg" : "audio-volume-high-symbolic.svg"))
                                    opacity: appMuteArea.containsMouse ? 1.0 : 0.75
                                    layer.enabled: !darkMode
                                    layer.effect: MultiEffect {
                                        colorization: 1.0
                                        colorizationColor: "#333333"
                                    }
                                }

                                MouseArea {
                                    id: appMuteArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: audioPanel.toggleAppMute(model.streamId)
                                }
                            }
                        }
                    }
                }
            }
        }

        // Output Device
        Column {
            width: parent.width
            visible: audioPanel.tab === 0
            spacing: 10

            Rectangle {
                width: parent.width
                height: audioPanel.listHeight
                radius: 8
                color: darkMode ? Qt.rgba(0.1, 0.1, 0.1, 0.5) : Qt.rgba(0.9, 0.9, 0.9, 0.8)
                border.width: 1
                border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)
                clip: true

                ListView {
                    id: deviceListView
                    anchors.fill: parent
                    anchors.margins: 5
                    spacing: 5
                    clip: true

                    model: audioPanel.outputDevices

                    delegate: Rectangle {
                        width: deviceListView.width
                        height: 50
                        radius: 6
                        color: {
                            if (modelData.name === audioPanel.defaultSink) return Qt.rgba(audioPanel.accentColor.r, audioPanel.accentColor.g, audioPanel.accentColor.b, 0.3)
                            return deviceMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4)
                        }
                        border.width: modelData.name === audioPanel.defaultSink ? 1 : 0
                        border.color: audioPanel.accentColor

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Row {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 10

                            ProjectIcon {
                                name: "headphones"
                                font.pixelSize: 20
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2
                                width: parent.width - 40

                                Text {
                                    text: modelData.description
                                    font.pixelSize: 12
                                    color: darkMode ? "#ffffff" : "#000000"
                                    elide: Text.ElideRight
                                    width: parent.width
                                }

                                Text {
                                    text: modelData.name === audioPanel.defaultSink ? Lang.get("audio.default", uiLanguage) : "Sink " + modelData.id
                                    font.pixelSize: 10
                                    color: modelData.name === audioPanel.defaultSink ? audioPanel.accentColor : (darkMode ? "#666666" : "#444444")
                                }
                            }
                        }

                        MouseArea {
                            id: deviceMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                console.log("Setting default sink to:", modelData.name)
                                setDefaultSinkProc.command = ["bash", "-c", "pactl set-default-sink " + modelData.name]
                                setDefaultSinkProc.running = true
                                // Sofort aktualisieren
                                Qt.callLater(function() {
                                    updateAudioState()
                                })
                            }
                        }
                    }
                }
            }
        }
    }

    // Quick Actions - am unteren Rand verankert
    Row {
        id: quickActionsRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: 10

        Rectangle {
            width: (parent.width - 10) / 2
            height: 40
            radius: 8
            color: darkMode
                ? (muteMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4))
                : (muteMouseArea.containsMouse ? Qt.rgba(0.85, 0.85, 0.85, 0.8) : Qt.rgba(0.88, 0.88, 0.88, 0.7))
            border.width: 1
            border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)

            Behavior on color { ColorAnimation { duration: 150 } }

            Row {
                anchors.centerIn: parent
                spacing: 8

                Image {
                    source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/audio-volume-muted-blocking-symbolic.svg")
                    width: 16
                    height: 16
                    smooth: true
                    anchors.verticalCenter: parent.verticalCenter

                    layer.enabled: !darkMode
                    layer.effect: MultiEffect {
                        colorization: 1.0
                        colorizationColor: "#333333"
                    }
                }

                Text {
                    text: Lang.get("audio.mute", uiLanguage)
                    font.pixelSize: 12
                    color: darkMode ? "#cccccc" : "#333333"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: muteMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: toggleMuteProc.running = true
            }
        }

        Rectangle {
            width: (parent.width - 10) / 2
            height: 40
            radius: 8
            color: darkMode
                ? (mixerMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4))
                : (mixerMouseArea.containsMouse ? Qt.rgba(0.85, 0.85, 0.85, 0.8) : Qt.rgba(0.88, 0.88, 0.88, 0.7))
            border.width: 1
            border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)

            Behavior on color { ColorAnimation { duration: 150 } }

            Row {
                anchors.centerIn: parent
                spacing: 8

                Image {
                    source: Qt.resolvedUrl("../img/Win11-dark/apps/symbolic/hearing-symbolic.svg")
                    width: 16
                    height: 16
                    smooth: true
                    anchors.verticalCenter: parent.verticalCenter

                    layer.enabled: !darkMode
                    layer.effect: MultiEffect {
                        colorization: 1.0
                        colorizationColor: "#333333"
                    }
                }

                Text {
                    text: Lang.get("audio.mixer", uiLanguage)
                    font.pixelSize: 12
                    color: darkMode ? "#cccccc" : "#333333"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Process {
                id: openMixerProc
                command: ["bash", "-c", "easyeffects & disown"]
                running: false
            }

            MouseArea {
                id: mixerMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    audioPanel.closeRequested()
                    openMixerProc.running = true
                }
            }
        }
    }
    }
}
