import Quickshell
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import Quickshell.Io
import QtQuick
import QtQuick.Controls

FloatingWindow {
    id: mediaPlayerWindow
    visible: false
    implicitWidth: Math.min(853, screen ? Math.max(1, screen.width - 16) : 853)
    implicitHeight: Math.min(500, screen ? Math.max(1, screen.height - 61) : 500)
    color: "transparent"
    title: "quickshell-mediaplayer"

    property var player: null
    property int borderRadius: 6
    property string accentColor: "#FE6F2D"
    property bool darkMode: true
    property var cavaData: []
    property string primaryMonitorName: ""

    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === primaryMonitorName) {
                return Quickshell.screens[i]
            }
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    // Timer für verzögerte FocusGrab Aktivierung
    property bool shouldBeActive: false

    Timer {
        id: focusGrabActivationTimer
        interval: 50
        running: false
        repeat: false
        onTriggered: mediaPlayerWindow.shouldBeActive = true
    }

    onVisibleChanged: {
        if (visible) {
            focusGrabActivationTimer.start()
            cavaProcess.running = true
        } else {
            focusGrabActivationTimer.stop()
            mediaPlayerWindow.shouldBeActive = false
            cavaProcess.running = false
        }
    }

    // Cava Config erstellen beim Start
    Process {
        id: cavaConfigProc
        running: true
        command: ["bash", "-c", "mkdir -p ~/.config/cava && cat > ~/.config/cava/config_mediaplayer << 'EOF'\n[general]\nframerate = 60\nautosens = 1\nbars = 32\nlower_cutoff_freq = 50\nhigher_cutoff_freq = 10000\n\n[input]\nmethod = pulse\nsource = auto\n\n[output]\nmethod = raw\nraw_target = /dev/stdout\ndata_format = ascii\nascii_max_range = 100\nbar_delimiter = 59\n\n[smoothing]\nmonstercat = 0\nwaves = 0\nnoise_reduction = 0.77\nEOF"]
    }

    // Cava starten/stoppen (schreibt in Datei)
    Process {
        id: cavaProcess
        running: false
        command: ["bash", "-c", "cava -p ~/.config/cava/config_mediaplayer 2>/dev/null | while IFS= read -r line; do echo \"$line\" > /tmp/cava_output_qs; done"]
    }

    // Timer um Cava-Output aus Datei zu lesen
    Timer {
        id: cavaUpdateTimer
        interval: 50
        running: mediaPlayerWindow.visible
        repeat: true
        onTriggered: {
            cavaReadProc.running = true
        }
    }

    Process {
        id: cavaReadProc
        running: false
        command: ["cat", "/tmp/cava_output_qs"]

        stdout: StdioCollector {
            onStreamFinished: {
                var line = this.text.trim()
                if (line.length > 0) {
                    var values = line.split(";")
                    var bars = []
                    for (var j = 0; j < Math.min(32, values.length); j++) {
                        var val = parseInt(values[j]) || 0
                        bars.push(Math.min(100, val))
                    }
                    if (bars.length > 0) {
                        mediaPlayerWindow.cavaData = bars
                    }
                }
            }
        }
    }

    // Timer für Position-Update
    Timer {
        id: positionTimer
        interval: 1000
        running: mediaPlayerWindow.visible && mediaPlayerWindow.player
        repeat: true
        onTriggered: {
            // Trigger re-evaluation von position
            if (mediaPlayerWindow.player) {
                positionSlider.updatePosition()
            }
        }
    }

    HyprlandFocusGrab {
        id: mediaPlayerFocusGrab
        windows: [mediaPlayerWindow]
        active: mediaPlayerWindow.shouldBeActive
        onCleared: mediaPlayerWindow.visible = false
    }

    // Scrollrad für smarte Lautstärke (erst Player, dann System)
    MouseArea {
        id: volumeScrollArea
        anchors.fill: parent
        onWheel: function(wheel) {
            var delta = wheel.angleDelta.y / 120
            var player = mediaPlayerWindow.player

            // Smarte Lautstärke: Erst Player, dann System
            if (player && player.canControl && player.volumeSupported) {
                var currentVol = player.volume
                var newVol = currentVol + (delta * 0.05)

                if (delta > 0) {
                    // Scroll UP: Erhöhe
                    if (currentVol < 1.0) {
                        player.volume = Math.min(1.0, newVol)
                    } else {
                        Qt.createQmlObject(
                            'import Quickshell.Io; Process { ' +
                            'command: ["bash", "-c", "wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+"]; ' +
                            'running: true }',
                            volumeScrollArea
                        )
                    }
                } else {
                    // Scroll DOWN: Verringere
                    if (currentVol > 0.0) {
                        player.volume = Math.max(0.0, newVol)
                    } else {
                        Qt.createQmlObject(
                            'import Quickshell.Io; Process { ' +
                            'command: ["bash", "-c", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"]; ' +
                            'running: true }',
                            volumeScrollArea
                        )
                    }
                }
            } else {
                // Kein Player oder Volume nicht unterstützt -> direkt System-Volume
                var changeCmd = delta > 0 ? "5%+" : "5%-"
                Qt.createQmlObject(
                    'import Quickshell.Io; Process { ' +
                    'command: ["bash", "-c", "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ ' + changeCmd + '"]; ' +
                    'running: true }',
                    volumeScrollArea
                )
            }
            wheel.accepted = true
        }
        propagateComposedEvents: true
        z: -1  // Hinter allen anderen MouseAreas
    }

    // Cava Visualisierung - GANZ UNTEN, volle Höhe
    Item {
        anchors.fill: parent
        clip: false
        z: 0

        Row {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 3
            height: parent.height

            Repeater {
                model: mediaPlayerWindow.cavaData.length > 0 ? mediaPlayerWindow.cavaData.length : 32

                Rectangle {
                    width: 18
                    height: {
                        if (mediaPlayerWindow.cavaData.length > index) {
                            var val = mediaPlayerWindow.cavaData[index] || 0
                            return Math.max(4, (val / 100) * parent.height)
                        }
                        return 4
                    }
                    anchors.bottom: parent.bottom
                    radius: 3
                    opacity: 0.7

                    gradient: Gradient {
                        GradientStop { position: 0.0; color: mediaPlayerWindow.accentColor }
                        GradientStop { position: 0.3; color: Qt.lighter(mediaPlayerWindow.accentColor, 1.2) }
                        GradientStop { position: 0.6; color: Qt.lighter(mediaPlayerWindow.accentColor, 1.5) }
                        GradientStop { position: 1.0; color: "#FFD966" }
                    }

                    Behavior on height {
                        NumberAnimation { duration: 100; easing.type: Easing.OutQuad }
                    }
                }
            }
        }
    }

    Rectangle {
        id: playerBackground
        anchors.fill: parent
        color: "transparent"
        radius: 0
        topLeftRadius: 0
        topRightRadius: 0
        bottomLeftRadius: mediaPlayerWindow.borderRadius
        bottomRightRadius: mediaPlayerWindow.borderRadius
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.2)
        z: 1

        // Gradient Background
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.95) : Qt.rgba(0.95, 0.95, 0.95, 0.95) }
                GradientStop { position: 0.3; color: Qt.darker(mediaPlayerWindow.accentColor, darkMode ? 3.5 : 1.8) }
                GradientStop { position: 1.0; color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.95) : Qt.rgba(0.95, 0.95, 0.95, 0.95) }
            }
            opacity: 0.8
        }

        // Overlay um oberen Border zu verstecken
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: -1
            height: 2
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.125, 0.125, 0.125, 0.95) }
                GradientStop { position: 0.5; color: Qt.darker(mediaPlayerWindow.accentColor, 3.5) }
                GradientStop { position: 1.0; color: Qt.rgba(0.125, 0.125, 0.125, 0.95) }
            }
            z: 1
        }

        Column {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 15

            // Header mit App-Name
            Row {
                width: parent.width
                spacing: 10

                Rectangle {
                    width: appIcon.width + 12
                    height: appIcon.height + 12
                    radius: 8
                    color: Qt.rgba(1, 1, 1, 0.1)

                    Image {
                        id: appIcon
                        anchors.centerIn: parent
                        source: {
                            var identity = mediaPlayerWindow.player?.identity || ""
                            if (identity.toLowerCase().includes("spotify")) {
                                return "img/scalable/spotify-client.svg"
                            } else if (identity.toLowerCase().includes("firefox") || identity.toLowerCase().includes("mozilla")) {
                                return "img/scalable/firefox.svg"
                            } else if (identity.toLowerCase().includes("chrome")) {
                                return "img/scalable/chrome.svg"
                            } else {
                                return "img/Win11-dark/actions/symbolic/media-playback-start-symbolic.svg"
                            }
                        }
                        width: 24
                        height: 24
                        sourceSize.width: 24
                        sourceSize.height: 24
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        antialiasing: true
                        mipmap: true
                        layer.enabled: true
                        layer.smooth: true
                    }
                }

                Text {
                    text: mediaPlayerWindow.player?.identity || "Media Player"
                    color: "#ffffff"
                    font.pixelSize: 16
                    font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Cover Art + Info in Row Layout
            Row {
                width: parent.width
                spacing: 15

                // Cover Art
                Rectangle {
                    width: 140
                    height: 140
                    radius: mediaPlayerWindow.borderRadius
                    color: Qt.rgba(1, 1, 1, 0.05)
                    clip: true

                    Image {
                        id: coverArt
                        anchors.fill: parent
                        source: mediaPlayerWindow.player?.trackArtUrl || ""
                        fillMode: Image.PreserveAspectCrop
                        smooth: true
                        visible: status === Image.Ready
                    }

                    // Fallback Icon
                    Text {
                        anchors.centerIn: parent
                        text: "♫"
                        color: mediaPlayerWindow.accentColor
                        font.pixelSize: 56
                        visible: coverArt.status !== Image.Ready
                    }

                    // Gradient Overlay für bessere Text-Lesbarkeit
                    Rectangle {
                        anchors.fill: parent
                        radius: mediaPlayerWindow.borderRadius
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "transparent" }
                            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.3) }
                        }
                        visible: coverArt.status === Image.Ready
                    }
                }

                // Track Info
                Column {
                    width: parent.width - 155
                    spacing: 8
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        text: mediaPlayerWindow.player?.trackTitle || "Kein Titel"
                        color: "#ffffff"
                        font.pixelSize: 18
                        font.bold: true
                        elide: Text.ElideRight
                        width: parent.width
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                    }

                    Text {
                        visible: text.length > 0
                        text: mediaPlayerWindow.player?.trackArtists || ""
                        color: mediaPlayerWindow.accentColor
                        font.pixelSize: 14
                        font.bold: true
                        elide: Text.ElideRight
                        width: parent.width
                    }

                    Text {
                        visible: text.length > 0
                        text: mediaPlayerWindow.player?.trackAlbum || ""
                        color: "#aaaaaa"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        width: parent.width
                    }
                }
            }

            // Progress Bar mit Zeit
            Column {
                width: parent.width
                spacing: 8

                // Zeit-Display
                Row {
                    width: parent.width
                    Text {
                        id: currentTimeText
                        text: {
                            if (!mediaPlayerWindow.player) return "0:00"
                            var pos = mediaPlayerWindow.player.positionMs || 0
                            var seconds = Math.floor(pos / 1000000)
                            var mins = Math.floor(seconds / 60)
                            var secs = seconds % 60
                            return mins + ":" + (secs < 10 ? "0" : "") + secs
                        }
                        color: "#ffffff"
                        font.pixelSize: 13
                        width: 50
                    }

                    Item { width: parent.width - 100; height: 1 }

                    Text {
                        id: totalTimeText
                        text: {
                            if (!mediaPlayerWindow.player) return "0:00"
                            var len = mediaPlayerWindow.player.lengthMs || 0
                            var seconds = Math.floor(len / 1000000)
                            var mins = Math.floor(seconds / 60)
                            var secs = seconds % 60
                            return mins + ":" + (secs < 10 ? "0" : "") + secs
                        }
                        color: "#aaaaaa"
                        font.pixelSize: 13
                        width: 50
                        horizontalAlignment: Text.AlignRight
                    }
                }

                // Progress Slider
                Rectangle {
                    id: positionSlider
                    width: parent.width
                    height: 6
                    radius: 3
                    color: Qt.rgba(1, 1, 1, 0.2)

                    property real currentPosition: {
                        if (!mediaPlayerWindow.player) return 0
                        var pos = mediaPlayerWindow.player.positionMs || 0
                        var len = mediaPlayerWindow.player.lengthMs || 1
                        return len > 0 ? (pos / len) : 0
                    }

                    function updatePosition() {
                        // Force re-evaluation
                        currentPosition = currentPosition
                    }

                    Rectangle {
                        id: progressBar
                        width: parent.currentPosition * parent.width
                        height: parent.height
                        radius: parent.radius
                        color: mediaPlayerWindow.accentColor

                        Behavior on width {
                            NumberAnimation { duration: 200 }
                        }

                        // Handle am Ende
                        Rectangle {
                            x: parent.width - 6
                            y: -3
                            width: 12
                            height: 12
                            radius: 6
                            color: "#ffffff"
                            border.width: 2
                            border.color: mediaPlayerWindow.accentColor
                            visible: sliderMouseArea.containsMouse || sliderMouseArea.pressed
                        }
                    }

                    MouseArea {
                        id: sliderMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor

                        onClicked: function(mouse) {
                            if (mediaPlayerWindow.player && mediaPlayerWindow.player.canSeek) {
                                var clickPos = mouse.x / width
                                var len = mediaPlayerWindow.player.lengthMs || 0
                                var newPos = clickPos * len
                                mediaPlayerWindow.player.positionMs = newPos
                            }
                        }

                        onPositionChanged: function(mouse) {
                            if (pressed && mediaPlayerWindow.player && mediaPlayerWindow.player.canSeek) {
                                var clickPos = Math.max(0, Math.min(1, mouse.x / width))
                                var len = mediaPlayerWindow.player.lengthMs || 0
                                var newPos = clickPos * len
                                mediaPlayerWindow.player.positionMs = newPos
                            }
                        }
                    }
                }
            }

            // Controls
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 15

                // Previous Button
                Rectangle {
                    visible: mediaPlayerWindow.player?.canGoPrevious || false
                    width: 50
                    height: 50
                    radius: 25
                    color: prevMouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.2)

                    Image {
                        anchors.centerIn: parent
                        source: "img/Win11-dark/actions/symbolic/media-skip-backward-symbolic.svg"
                        width: 20
                        height: 20
                        sourceSize.width: 20
                        sourceSize.height: 20
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        antialiasing: true
                        mipmap: true
                        layer.enabled: true
                        layer.smooth: true
                    }

                    MouseArea {
                        id: prevMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (mediaPlayerWindow.player) {
                                mediaPlayerWindow.player.previous()
                            }
                        }
                    }
                }

                // Play/Pause Button
                Rectangle {
                    width: 60
                    height: 60
                    radius: 30
                    color: playMouseArea.containsMouse ? Qt.lighter(mediaPlayerWindow.accentColor, 1.2) : mediaPlayerWindow.accentColor

                    Behavior on color { ColorAnimation { duration: 150 } }

                    Image {
                        anchors.centerIn: parent
                        source: (mediaPlayerWindow.player?.playbackState === MprisPlaybackState.Playing)
                            ? "img/Win11-dark/actions/symbolic/media-playback-pause-symbolic.svg"
                            : "img/Win11-dark/actions/symbolic/media-playback-start-symbolic.svg"
                        width: 24
                        height: 24
                        sourceSize.width: 24
                        sourceSize.height: 24
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        antialiasing: true
                        mipmap: true
                        layer.enabled: true
                        layer.smooth: true
                    }

                    MouseArea {
                        id: playMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (mediaPlayerWindow.player) {
                                if (mediaPlayerWindow.player.playbackState === MprisPlaybackState.Playing) {
                                    mediaPlayerWindow.player.pause()
                                } else {
                                    mediaPlayerWindow.player.play()
                                }
                            }
                        }
                    }
                }

                // Next Button
                Rectangle {
                    visible: mediaPlayerWindow.player?.canGoNext || false
                    width: 50
                    height: 50
                    radius: 25
                    color: nextMouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.2)

                    Image {
                        anchors.centerIn: parent
                        source: "img/Win11-dark/actions/symbolic/media-skip-forward-symbolic.svg"
                        width: 20
                        height: 20
                        sourceSize.width: 20
                        sourceSize.height: 20
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        antialiasing: true
                        mipmap: true
                        layer.enabled: true
                        layer.smooth: true
                    }

                    MouseArea {
                        id: nextMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (mediaPlayerWindow.player) {
                                mediaPlayerWindow.player.next()
                            }
                        }
                    }
                }
            }
        }
    }
}
