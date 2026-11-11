import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "settings" as Tools

ShellRoot {
    Window {
        id: welcome
        readonly property var payload: JSON.parse(Quickshell.env("WINDOESNOT_WELCOME") || "{}")
        property bool darkMode: payload.dark !== false
        property color accentColor: payload.accent || "#FE6F2D"
        readonly property color foreground: darkMode ? "#eeeeee" : "#202020"
        readonly property color secondary: darkMode ? "#aaaaaa" : "#666666"
        property string launchError: ""
        title: "WinDoesNot"
        visible: true
        width: Math.min(920, screen.width - 32)
        height: Math.min(800, screen.height - 80)
        color: darkMode ? "#202020" : "#f2f2f2"
        onClosing: Qt.quit()
        Rectangle { anchors.fill: parent; color: welcome.color }

        ScrollView {
            id: scroll
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: start.top; margins: 30 }
            clip: true
            contentWidth: availableWidth
            Column {
                width: scroll.availableWidth
                spacing: 20
                Image {
                    source: welcome.darkMode ? "img/brand/windoesnot-logo-hell.png" : "img/brand/windoesnot-logo-dunkel.png"
                    width: 158; height: 32; fillMode: Image.PreserveAspectFit
                    horizontalAlignment: Image.AlignLeft
                }
                Text {
                    width: parent.width; text: welcome.payload.title || ""; color: welcome.foreground
                    font.pixelSize: 28; font.bold: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                }
                Text {
                    width: parent.width; text: welcome.payload.intro || ""; color: welcome.secondary
                    font.pixelSize: 14; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                }
                // Display and mouse: set at the first start, so the desktop is usable right away.
                Rectangle {
                    id: displayCard
                    visible: !!welcome.payload.display
                    readonly property var texts: welcome.payload.display || ({})
                    property var info: ({name: "", modes: [], scales: [], width: 0, height: 0, scale: 1})
                    property var previous: null
                    property int countdown: 0
                    readonly property bool haveDisplay: info.name !== ""
                    width: parent.width; height: displayContent.height + 32
                    radius: 8; color: welcome.darkMode ? "#141414" : "#f5f5f5"
                    border.width: 1; border.color: welcome.darkMode ? "#3a3a3a" : "#d0d0d0"

                    function resolutionIndex() {
                        for (var i = 0; i < info.modes.length; i++)
                            if (info.modes[i].width === info.width && info.modes[i].height === info.height) return i
                        return -1
                    }
                    function applyDisplay(width, height, scale) {
                        if (applyProc.running) return
                        if (!previous) previous = {width: info.width, height: info.height, scale: info.scale}
                        applyProc.command = ["windoesnot-display-setup", "apply", String(width), String(height), String(scale)]
                        applyProc.running = true
                        countdown = 12
                        revertTimer.restart()
                    }
                    function keepDisplay() { revertTimer.stop(); countdown = 0; previous = null }
                    function revertDisplay() {
                        revertTimer.stop(); countdown = 0
                        var old = previous; previous = null
                        if (old && !applyProc.running) {
                            applyProc.command = ["windoesnot-display-setup", "apply", String(old.width), String(old.height), String(old.scale)]
                            applyProc.running = true
                        }
                    }

                    Component.onCompleted: statusProc.running = true
                    Process {
                        id: statusProc
                        command: ["windoesnot-display-setup", "status"]
                        stdout: StdioCollector {
                            onStreamFinished: {
                                try { var data = JSON.parse(text); if (data.name) displayCard.info = data } catch (error) {}
                            }
                        }
                    }
                    Process {
                        id: applyProc
                        onExited: statusProc.running = true
                    }
                    Process { id: mouseProc }
                    Timer {
                        id: revertTimer
                        interval: 1000; repeat: true
                        onTriggered: { displayCard.countdown -= 1; if (displayCard.countdown <= 0) displayCard.revertDisplay() }
                    }

                    Column {
                        id: displayContent
                        x: 16; y: 16; width: parent.width - 32; spacing: 14
                        Text {
                            text: displayCard.texts.title || ""; color: welcome.foreground
                            font.pixelSize: 20; font.bold: true; textFormat: Text.PlainText
                        }
                        Text {
                            width: parent.width; text: displayCard.texts.hint || ""; color: welcome.secondary
                            font.pixelSize: 13; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                        }
                        RowLayout {
                            visible: displayCard.haveDisplay && displayCard.info.modes.length > 1
                            width: parent.width; spacing: 12
                            Text { Layout.preferredWidth: 150; text: displayCard.texts.resolution || ""; color: welcome.foreground; font.pixelSize: 14 }
                            Tools.SystemToolsChoice {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40
                                settingsMenu: welcome
                                model: displayCard.info.modes.map(function(m) { return m.width + " × " + m.height })
                                currentIndex: displayCard.resolutionIndex()
                                enabled: !applyProc.running && displayCard.countdown === 0
                                onActivated: function(index) {
                                    var mode = displayCard.info.modes[index]
                                    displayCard.applyDisplay(mode.width, mode.height, displayCard.info.scale)
                                }
                            }
                        }
                        RowLayout {
                            visible: displayCard.haveDisplay
                            width: parent.width; spacing: 12
                            Text { Layout.preferredWidth: 150; text: displayCard.texts.zoom || ""; color: welcome.foreground; font.pixelSize: 14 }
                            Flow {
                                Layout.fillWidth: true; spacing: 8
                                Repeater {
                                    model: displayCard.info.scales
                                    delegate: Tools.SystemToolsButton {
                                        required property real modelData
                                        settingsMenu: welcome
                                        text: Math.round(modelData * 100) + " %"
                                        primary: Math.abs(modelData - displayCard.info.scale) < 0.01
                                        enabled: !applyProc.running && displayCard.countdown === 0
                                        onClicked: displayCard.applyDisplay(displayCard.info.width, displayCard.info.height, modelData)
                                    }
                                }
                            }
                        }
                        RowLayout {
                            width: parent.width; spacing: 12
                            Text { Layout.preferredWidth: 150; text: displayCard.texts.mouse || ""; color: welcome.foreground; font.pixelSize: 14 }
                            Text { text: displayCard.texts.slow || ""; color: welcome.secondary; font.pixelSize: 12 }
                            Slider {
                                id: speed
                                Layout.fillWidth: true
                                from: -1; to: 1; stepSize: 0.1
                                value: displayCard.texts.mouseSensitivity || 0
                                background: Rectangle {
                                    x: speed.leftPadding
                                    y: speed.topPadding + speed.availableHeight / 2 - height / 2
                                    implicitWidth: 200; implicitHeight: 4
                                    width: speed.availableWidth; height: implicitHeight
                                    radius: 2; color: welcome.darkMode ? "#3a3a3a" : "#d0d0d0"
                                    Rectangle {
                                        width: speed.visualPosition * parent.width
                                        height: parent.height; radius: 2; color: welcome.accentColor
                                    }
                                }
                                handle: Rectangle {
                                    x: speed.leftPadding + speed.visualPosition * (speed.availableWidth - width)
                                    y: speed.topPadding + speed.availableHeight / 2 - height / 2
                                    implicitWidth: 20; implicitHeight: 20; radius: 10
                                    color: speed.pressed ? Qt.darker(welcome.accentColor, 1.2) : (welcome.darkMode ? "#ffffff" : "#ffffff")
                                    border.color: welcome.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 2
                                }
                                onPressedChanged: if (!pressed) {
                                    var base = Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")
                                    mouseProc.command = ["quickshell", "ipc", "--path", base + "/quickshell/default/shell.qml",
                                                         "call", "windoesnot-settings", "setMouseSensitivity", String(value)]
                                    mouseProc.running = true
                                }
                            }
                            Text { text: displayCard.texts.fast || ""; color: welcome.secondary; font.pixelSize: 12 }
                        }
                        // After a change: keep it, or it is reverted, so a bad picture never sticks.
                        Rectangle {
                            visible: displayCard.countdown > 0
                            width: parent.width; height: 44; radius: 6
                            color: welcome.darkMode ? "#2a2a2a" : "#e6e6e6"
                            RowLayout {
                                anchors { fill: parent; leftMargin: 12; rightMargin: 8 }
                                spacing: 8
                                Text {
                                    Layout.fillWidth: true
                                    text: (displayCard.texts.confirm || "") + " (" + displayCard.countdown + ")"
                                    color: welcome.foreground; font.pixelSize: 13; elide: Text.ElideRight
                                }
                                Tools.SystemToolsButton { settingsMenu: welcome; primary: true; text: displayCard.texts.keep || ""; onClicked: displayCard.keepDisplay() }
                                Tools.SystemToolsButton { settingsMenu: welcome; text: displayCard.texts.revert || ""; onClicked: displayCard.revertDisplay() }
                            }
                        }
                    }
                }
                Text {
                    text: welcome.payload.appsTitle || ""; color: welcome.foreground
                    font.pixelSize: 20; font.bold: true; textFormat: Text.PlainText
                }
                GridLayout {
                    id: appGrid
                    width: parent.width
                    columns: width >= 640 ? 2 : 1
                    columnSpacing: 12; rowSpacing: 12
                    Repeater {
                        model: welcome.payload.apps || []
                        delegate: Rectangle {
                            id: appCard
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: (appGrid.width - (appGrid.columns - 1) * 12) / appGrid.columns
                            implicitHeight: Math.max(104, appInfo.implicitHeight + 32)
                            radius: 10
                            color: welcome.darkMode ? "#141414" : "#f5f5f5"
                            border.width: 1; border.color: welcome.darkMode ? "#3a3a3a" : "#d0d0d0"
                            RowLayout {
                                anchors { fill: parent; margins: 16 }
                                spacing: 12
                                Image {
                                    Layout.preferredWidth: 32; Layout.preferredHeight: 32
                                    source: appCard.modelData.icon
                                    fillMode: Image.PreserveAspectFit
                                }
                                ColumnLayout {
                                    id: appInfo
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Text {
                                        Layout.fillWidth: true; text: appCard.modelData.name
                                        color: welcome.foreground; font.pixelSize: 16; font.bold: true
                                        wrapMode: Text.WordWrap; textFormat: Text.PlainText
                                    }
                                    Text {
                                        Layout.fillWidth: true; text: appCard.modelData.description
                                        color: welcome.secondary; font.pixelSize: 13
                                        wrapMode: Text.WordWrap; textFormat: Text.PlainText
                                    }
                                }
                                Tools.SystemToolsButton {
                                    settingsMenu: welcome
                                    text: appCard.modelData.available ? welcome.payload.open : welcome.payload.unavailable
                                    enabled: appCard.modelData.available && !launch.running
                                    onClicked: { welcome.launchError = ""; launch.running = true }
                                    Accessible.name: text + ": " + appCard.modelData.name
                                }
                            }
                            Process {
                                id: launch
                                // Keep the app alive when the welcome window closes; no shell expansion.
                                command: ["setsid", "--fork"].concat(appCard.modelData.command || [])
                                onExited: (code) => { if (code !== 0) welcome.launchError = welcome.payload.launchError }
                            }
                        }
                    }
                }
                Text {
                    visible: text.length > 0; text: welcome.launchError
                    width: parent.width; color: welcome.secondary; font.pixelSize: 14; wrapMode: Text.WordWrap
                    textFormat: Text.PlainText
                }
                Text {
                    text: welcome.payload.setupTitle || ""; color: welcome.foreground
                    font.pixelSize: 20; font.bold: true; textFormat: Text.PlainText
                }
                Repeater {
                    model: welcome.payload.lines || []
                    delegate: Text {
                        required property string modelData
                        width: parent.width; text: "•  " + modelData
                        color: welcome.secondary; font.pixelSize: 14
                        wrapMode: Text.WordWrap; textFormat: Text.PlainText
                    }
                }
                Text {
                    width: parent.width; text: welcome.payload.hint || ""; color: welcome.secondary
                    font.pixelSize: 13; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                }
            }
        }
        Tools.SystemToolsButton {
            id: start
            anchors { right: parent.right; bottom: parent.bottom; margins: 24 }
            settingsMenu: welcome
            primary: true
            text: welcome.payload.close || "OK"
            onClicked: Qt.quit()
        }
    }
}
