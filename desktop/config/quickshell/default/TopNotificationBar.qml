import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import Quickshell.Wayland
import QtQuick
import QtQuick.Controls
import "i18n/Lang.js" as Lang

PanelWindow {
    id: topNotificationBar
    visible: true
    implicitWidth: Math.min(853, screen ? screen.width : 853)  // 1/3 Bildschirmbreite (zentriert via hyprland.conf)
    implicitHeight: 45  // Feste Höhe - Fenster wird verschoben statt resized
    color: "transparent"
    anchors.top: true
    anchors.left: true
    anchors.right: true
    margins.left: (screen ? (screen.width - implicitWidth) / 2 : 0)
    margins.right: margins.left
    exclusionMode: ExclusionMode.Ignore  // Keine exclusive zone reservieren
    exclusiveZone: 0                     // Hyprland soll keinen Platz freihalten

    // Während ein Fenster gezogen wird: Bar komplett deaktivieren damit
    // Snap-Zonen zuverlässig erkannt werden und kein Hand-Cursor hängen bleibt
    property bool blockHover: false

    // Kurz nach Drag-Ende: Bar noch 400 ms nicht-interaktiv lassen, damit der
    // Cursor die Bar-Zone verlassen kann bevor Hover-Events wieder registriert werden
    Timer {
        id: dragCooldownTimer
        interval: 400
        repeat: false
        running: false
    }

    onBlockHoverChanged: {
        if (!blockHover) {
            hovered = false          // Bar sofort einklappen
            dragCooldownTimer.restart()  // 400 ms Sperrzeit starten
        }
    }

    mask: Region {
        width: topNotificationBar.width
        height: (topNotificationBar.blockHover || dragCooldownTimer.running)
                    ? 0   // Drag aktiv oder Cooldown → komplett durchklickbar
                : topNotificationBar.mediaPlayerVisible
                    ? 0   // keine Eingriffe wenn Player offen
                : (topNotificationBar.hovered || topNotificationBar.swayncOpen)
                    ? topNotificationBar.implicitHeight
                    : 10
    }
    property string primaryMonitorName: ""

    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === primaryMonitorName) {
                return Quickshell.screens[i]
            }
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    property bool hasNotifications: false
    property int notificationCount: 0
    property bool hovered: false
    property bool swayncOpen: false  // Tracking ob swaync geöffnet ist
    property bool lastSwayncOpen: false  // Für Logging nur bei Änderung
    property string accentColor: "#FE6F2D"  // Wird von shell.qml per Binding gesetzt
    property int borderRadius: 6            // Wird von shell.qml per Binding gesetzt
    property bool darkMode: true            // Wird von shell.qml per Binding gesetzt
    property string uiLanguage: "de"         // Wird von shell.qml per Binding gesetzt
    property bool mediaPlayerVisible: false // Wird von shell.qml gebunden

    // Timer um Bar-Schließen beim Scrollen zu verhindern
    Timer {
        id: hoverExitTimer
        interval: 150
        running: false
        repeat: false
        onTriggered: {
            if (!notifMouseArea.containsMouse && !mediaMouseArea.containsMouse && !playPauseButton.containsMouse) {
                topNotificationBar.hovered = false
            }
        }
    }

    // Media Player Properties
    property var activePlayer: Mpris.players.values.filter(p => p.playbackState === MprisPlaybackState.Playing)[0] ||
                                Mpris.players.values.filter(p => p.playbackState === MprisPlaybackState.Paused)[0] ||
                                Mpris.players.values[0] || null
    property string mediaTitle: activePlayer?.trackTitle || Lang.get("notificationBar.noTitle", uiLanguage)
    property string mediaArtist: activePlayer?.trackArtists || ""  // trackArtists ist ein String, kein Array!
    property bool isPlaying: activePlayer?.playbackState === MprisPlaybackState.Playing
    property bool hasActivePlayer: activePlayer !== null

    // Signal zum Öffnen des Media Players
    signal openMediaPlayer()

    // Update swaync CSS when settings change
    Component.onCompleted: {
        topNotificationBar.hovered = false
        updateSwayncCssProc.running = true
    }

    onAccentColorChanged: updateSwayncCssProc.running = true
    onBorderRadiusChanged: updateSwayncCssProc.running = true

    Process {
        id: updateSwayncCssProc
        command: ["bash", "-c",
            "sed -i 's/border-radius: [0-9]*px;/border-radius: " + topNotificationBar.borderRadius + "px;/g' \"$HOME/.config/swaync/style.css\" && " +
            "sed -i 's/border-bottom-left-radius: [0-9]*px;/border-bottom-left-radius: " + topNotificationBar.borderRadius + "px;/g' \"$HOME/.config/swaync/style.css\" && " +
            "sed -i 's/border-bottom-right-radius: [0-9]*px;/border-bottom-right-radius: " + topNotificationBar.borderRadius + "px;/g' \"$HOME/.config/swaync/style.css\" && " +
            "sed -i 's/border: 1px solid #[a-fA-F0-9]\\{6\\};/border: 1px solid " + topNotificationBar.accentColor + ";/g' \"$HOME/.config/swaync/style.css\" && " +
            "swaync-client --reload-css"
        ]
        running: false
    }

    // Trigger-Zone am oberen Rand - 10px für gutes Triggering
    MouseArea {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 10  // 10px Trigger-Zone
        hoverEnabled: true
        enabled: !topNotificationBar.hovered && !topNotificationBar.swayncOpen  // Nur aktiv wenn geschlossen
        z: 500
        onEntered: {
            topNotificationBar.hovered = true
            hoverExitTimer.stop()
        }
    }

    // Prüfe ob Notifications vorhanden sind und ob swaync offen ist
    Timer {
        interval: 500  // Schnelleres Polling für besseres Feedback
        running: true
        repeat: true
        onTriggered: {
            checkNotificationsProc.running = true
            checkSwayncVisibilityProc.running = true
        }
    }

    Process {
        id: checkNotificationsProc
        command: ["swaync-client", "-c"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                topNotificationBar.notificationCount = parseInt(this.text.trim()) || 0
                topNotificationBar.hasNotifications = topNotificationBar.notificationCount > 0
            }
        }
    }

    Process {
        id: checkSwayncVisibilityProc
        command: ["bash", "-c", "windoesnot-hyprctl clients -j | grep -q 'swaync-control-center' && echo 'open' || echo 'closed'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var status = this.text.trim()
                var newStatus = (status === "open")

                if (newStatus !== topNotificationBar.lastSwayncOpen) {
                    topNotificationBar.lastSwayncOpen = newStatus
                }
                topNotificationBar.swayncOpen = newStatus
            }
        }
    }

    // Container verschiebt sich - Fenster bleibt bei y=0
    Item {
        id: barContainer
        width: parent.width
        height: 45  // Feste Höhe für den Inhalt
        x: 0
        y: topNotificationBar.mediaPlayerVisible
            ? -topNotificationBar.implicitHeight // Schiebe Bar komplett hoch wenn Player offen
            : (topNotificationBar.hovered || topNotificationBar.swayncOpen) ? 0 : -35  // -35px = 10px sichtbar
        enabled: !topNotificationBar.mediaPlayerVisible && (topNotificationBar.hovered || topNotificationBar.swayncOpen)  // Blockiert keine Events wenn geschlossen oder Player offen
        clip: true

        Behavior on y {
            NumberAnimation {
                duration: 200
                easing.type: Easing.OutCubic
            }
        }

        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 1
            color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.85) : Qt.rgba(0.95, 0.95, 0.95, 0.90)
            radius: 0
            topLeftRadius: 0
            topRightRadius: 0
            bottomLeftRadius: topNotificationBar.borderRadius
            bottomRightRadius: topNotificationBar.borderRadius
            border.width: 1
            border.color: darkMode ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0.7, 0.7, 0.7, 0.8)

            // Overlay um oberen Border zu verstecken
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: -1
                height: 2
                color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.85) : Qt.rgba(0.95, 0.95, 0.95, 0.90)
                z: 1
            }

            // Kein extra MouseArea hier - wird von den Section-MouseAreas gehandhabt

            Row {
                anchors.fill: parent
                spacing: 0

                // Benachrichtigungen Section (Links)
                Rectangle {
                    width: parent.width / 2
                    height: parent.height
                    color: notifMouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"
                    radius: 0
                    bottomLeftRadius: topNotificationBar.borderRadius

                    Behavior on color { ColorAnimation { duration: 150 } }

                    // Border-Stripe unter der Benachrichtigungs-Section
                    Rectangle {
                        visible: topNotificationBar.hasNotifications
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 4
                        height: 3
                        radius: 2
                        color: topNotificationBar.accentColor

                        Behavior on opacity { NumberAnimation { duration: 150 } }
                    }

                    MouseArea {
                        id: notifMouseArea
                        anchors.fill: parent
                        enabled: topNotificationBar.hovered || topNotificationBar.swayncOpen
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: {
                            topNotificationBar.hovered = true
                            hoverExitTimer.stop()
                        }
                        onExited: {
                            hoverExitTimer.restart()
                        }
                        onClicked: toggleSwayncProc.running = true
                        onWheel: function(wheel) {
                            var delta = wheel.angleDelta.y / 120
                            var player = topNotificationBar.activePlayer

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
                                            notifMouseArea
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
                                            notifMouseArea
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
                                    notifMouseArea
                                )
                            }
                            wheel.accepted = true
                        }
                        z: 100
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: 10
                        enabled: false  // Macht die Row transparent für Maus-Events

                        // Notification Icon
                        Rectangle {
                            width: 25
                            height: 25
                            radius: 14
                            color: topNotificationBar.hasNotifications ? topNotificationBar.accentColor : "transparent"
                            anchors.verticalCenter: parent.verticalCenter

                            Behavior on color { ColorAnimation { duration: 150 } }

                            Image {
                                anchors.centerIn: parent
                                source: "img/Win11-dark/status/symbolic/notification-symbolic.svg"
                                width: 16
                                height: 16
                                sourceSize.width: 16
                                sourceSize.height: 16
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                antialiasing: true
                                mipmap: true
                                layer.enabled: true
                                layer.smooth: true
                            }

                            // Badge mit Anzahl
                            Rectangle {
                                visible: topNotificationBar.notificationCount > 0
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.rightMargin: -4
                                anchors.topMargin: -4
                                width: Math.max(16, countText.width + 8)  // etwas mehr Padding für zentrierte Zahl
                                height: 16
                                radius: 8
                                color: "#ff4444"
                                border.color: "#ffffff"
                                border.width: 1

                                Text {
                                    id: countText
                                    anchors.centerIn: parent
                                    text: topNotificationBar.notificationCount > 9 ? "9+" : topNotificationBar.notificationCount
                                    color: "#ffffff"
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }
                        }

                        Text {
                            text: topNotificationBar.hasNotifications
                                ? (topNotificationBar.notificationCount === 1
                                    ? Lang.get("notificationBar.oneMessage", uiLanguage)
                                    : topNotificationBar.notificationCount + " " + Lang.get("notificationBar.messages", uiLanguage))
                                : Lang.get("notificationBar.notifications", uiLanguage)
                            color: darkMode ? "#cccccc" : "#333333"
                            font.pixelSize: 12
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    Process {
                        id: toggleSwayncProc
                        command: ["bash", "-c", "swaync-client -t -sw"]
                        running: false
                    }
                }

                // Trennlinie
                Rectangle {
                    width: 1
                    height: parent.height - 16
                    anchors.verticalCenter: parent.verticalCenter
                    color: Qt.rgba(1, 1, 1, 0.1)  // Hellere Trennlinie
                }

                // Media Section (Rechts)
                Rectangle {
                    id: mediaSection
                    width: parent.width / 2
                    height: parent.height
                    color: mediaMouseArea.containsMouse && !playPauseButton.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"
                    radius: 0
                    bottomRightRadius: topNotificationBar.borderRadius

                    Behavior on color { ColorAnimation { duration: 150 } }

                    MouseArea {
                        id: mediaMouseArea
                        anchors.fill: parent
                        enabled: topNotificationBar.hovered || topNotificationBar.swayncOpen
                        hoverEnabled: true
                        cursorShape: playPauseButton.containsMouse ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onEntered: {
                            topNotificationBar.hovered = true
                            hoverExitTimer.stop()
                        }
                        onExited: {
                            hoverExitTimer.restart()
                        }
                        onClicked: {
                            if (!playPauseButton.containsMouse) {
                                topNotificationBar.openMediaPlayer()
                            }
                        }
                        onWheel: function(wheel) {
                            var delta = wheel.angleDelta.y / 120
                            var player = topNotificationBar.activePlayer

                            // Smarte Lautstärke: Erst Player, dann System
                            if (player && player.canControl && player.volumeSupported) {
                                var currentVol = player.volume
                                var newVol = currentVol + (delta * 0.05)

                                if (delta > 0) {
                                    // Scroll UP: Erhöhe
                                    if (currentVol < 1.0) {
                                        // Player-Volume noch nicht bei 100%
                                        player.volume = Math.min(1.0, newVol)
                                    } else {
                                        // Player schon bei 100%, erhöhe System
                                        Qt.createQmlObject(
                                            'import Quickshell.Io; Process { ' +
                                            'command: ["bash", "-c", "wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+"]; ' +
                                            'running: true }',
                                            mediaMouseArea
                                        )
                                    }
                                } else {
                                    // Scroll DOWN: Verringere
                                    if (currentVol > 0.0) {
                                        // Player-Volume noch nicht bei 0%
                                        player.volume = Math.max(0.0, newVol)
                                    } else {
                                        // Player schon bei 0%, verringere System
                                        Qt.createQmlObject(
                                            'import Quickshell.Io; Process { ' +
                                            'command: ["bash", "-c", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"]; ' +
                                            'running: true }',
                                            mediaMouseArea
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
                                    mediaMouseArea
                                )
                            }
                            wheel.accepted = true
                        }
                    }

                     Row {
                         id: mediaRow
                         anchors.centerIn: parent
                         spacing: 10
                         enabled: false  // Macht die Row transparent für Maus-Events

                         // Play/Pause Toggle Button (visuell)
                         Rectangle {
                             id: visualPlayPauseButton
                             width: 25
                             height: 25
                             radius: 14
                             color: topNotificationBar.hasActivePlayer ? topNotificationBar.accentColor : "transparent"
                             anchors.verticalCenter: parent.verticalCenter

                             Behavior on color { ColorAnimation { duration: 150 } }

                             Image {
                                 anchors.centerIn: parent
                                 source: topNotificationBar.isPlaying
                                     ? "img/Win11-dark/actions/symbolic/media-playback-pause-symbolic.svg"
                                     : "img/Win11-dark/actions/symbolic/media-playback-start-symbolic.svg"
                                 width: 16
                                 height: 16
                                 sourceSize.width: 16
                                 sourceSize.height: 16
                                 fillMode: Image.PreserveAspectFit
                                 smooth: true
                                 antialiasing: true
                                 mipmap: true
                                 layer.enabled: true
                                 layer.smooth: true
                             }
                         }

                         Column {
                             spacing: 2
                             anchors.verticalCenter: parent.verticalCenter

                             Text {
                                 text: topNotificationBar.mediaTitle
                                 color: darkMode ? "#cccccc" : "#333333"
                                 font.pixelSize: 12
                                 font.bold: topNotificationBar.isPlaying
                                 elide: Text.ElideRight
                                 width: Math.min(implicitWidth, 150)
                             }

                             Text {
                                 visible: topNotificationBar.mediaArtist.length > 0
                                 text: topNotificationBar.mediaArtist
                                 color: darkMode ? "#999999" : "#666666"
                                 font.pixelSize: 10
                                 elide: Text.ElideRight
                                 width: Math.min(implicitWidth, 150)
                             }
                         }
                     }

                    // Play/Pause Button MouseArea (etwas größer für bessere Hover-Erkennung)
                    MouseArea {
                        id: playPauseButton
                        x: visualPlayPauseButton.x + mediaRow.x - 3
                        y: visualPlayPauseButton.y + mediaRow.y - 3
                        width: 31  // 25 + 6px Puffer
                        height: 31
                        enabled: topNotificationBar.hovered || topNotificationBar.swayncOpen
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: {
                            topNotificationBar.hovered = true
                            hoverExitTimer.stop()
                        }
                        onExited: {
                            hoverExitTimer.restart()
                        }
                        onClicked: {
                            if (topNotificationBar.activePlayer) {
                                if (topNotificationBar.isPlaying) {
                                    topNotificationBar.activePlayer.pause()
                                } else {
                                    topNotificationBar.activePlayer.play()
                                }
                            }
                            mouse.accepted = true
                        }
                        z: 200
                    }
                }
            }
        }
    }
}
