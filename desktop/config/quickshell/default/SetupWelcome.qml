import QtQuick
import QtQuick.Window
import QtQuick.Controls
import Quickshell
import "settings" as Tools

ShellRoot {
    Window {
        id: welcome
        readonly property var payload: JSON.parse(Quickshell.env("WINDOESNOT_WELCOME") || "{}")
        property bool darkMode: payload.dark !== false
        property color accentColor: payload.accent || "#FE6F2D"
        readonly property color foreground: darkMode ? "#eeeeee" : "#202020"
        readonly property color secondary: darkMode ? "#bbbbbb" : "#555555"
        title: "WinDoesNot"
        visible: true
        width: Math.min(820, screen.width - 32)
        height: Math.min(640, screen.height - 80)
        color: darkMode ? "#1a1a1a" : "#ffffff"
        onClosing: Qt.quit()

        ScrollView {
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: start.top; margins: 32 }
            clip: true
            contentWidth: availableWidth
            Column {
                width: parent.width
                spacing: 24
                Text { text: "WinDoesNot"; color: welcome.accentColor; font.pixelSize: 22; font.bold: true }
                Text {
                    width: parent.width; text: welcome.payload.title || ""; color: welcome.foreground
                    font.pixelSize: 28; font.bold: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                }
                Text {
                    width: parent.width; text: welcome.payload.intro || ""; color: welcome.secondary
                    font.pixelSize: 14; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                }
                Repeater {
                    model: welcome.payload.lines || []
                    delegate: Rectangle {
                        required property string modelData
                        width: parent.width; height: line.implicitHeight + 32; radius: 10
                        color: welcome.darkMode ? "#141414" : "#f5f5f5"
                        border.width: 1; border.color: welcome.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Text {
                            id: line
                            x: 16; y: 16; width: parent.width - 32
                            text: modelData; color: welcome.foreground; font.pixelSize: 15
                            wrapMode: Text.WordWrap; textFormat: Text.PlainText
                        }
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
