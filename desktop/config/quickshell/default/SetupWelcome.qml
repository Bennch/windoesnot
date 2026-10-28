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
