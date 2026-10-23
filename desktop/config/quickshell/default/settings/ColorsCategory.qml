import Qt5Compat.GraphicalEffects
import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"

    width: parent.width
    spacing: 30
    // Akzentfarbe (active border)
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("colors.accentColor", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Row {
            spacing: 15

            // Color Palette Button (opens palette dialog)
            Rectangle {
                width: 50
                height: 50
                radius: 25
                color: settingsMenu.accentColor
                border.width: 2
                border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"

                // Color palette icon overlay
                Image {
                    anchors.centerIn: parent
                    source: "../img/Win11-dark/actions/symbolic/color-palette-symbolic.svg"
                    width: 24
                    height: 24
                    sourceSize.width: 24
                    sourceSize.height: 24
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                    mipmap: true
                    layer.enabled: !settingsMenu.darkMode
                    layer.smooth: true
                    layer.effect: ColorOverlay { color: "#000000" }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: {
                        settingsMenu.colorPaletteTarget = "accent"
                        settingsMenu.colorPaletteVisible = true
                    }

                    property bool hovered: false
                    onEntered: hovered = true
                    onExited: hovered = false
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width + 4
                    height: parent.height + 4
                    radius: (parent.width + 4) / 2
                    color: "transparent"
                    border.width: 2
                    border.color: settingsMenu.accentColor
                    opacity: parent.children[1].hovered ? 0.6 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: 150 }
                    }
                }
            }

            // Custom Color Picker Button (hyprpicker)
            Rectangle {
                width: 50
                height: 50
                radius: 25
                color: settingsMenu.accentColor
                border.width: 2
                border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"

                // Color picker icon overlay
                Image {
                    anchors.centerIn: parent
                    source: "../img/Win11-dark/actions/symbolic/color-picker-symbolic.svg"
                    width: 24
                    height: 24
                    sourceSize.width: 24
                    sourceSize.height: 24
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                    mipmap: true
                    layer.enabled: !settingsMenu.darkMode
                    layer.smooth: true
                    layer.effect: ColorOverlay { color: "#000000" }
                }

                Process {
                    id: colorPickerProc
                    command: ["bash", "-c", "hyprpicker -a"]
                    running: false
                    stdout: StdioCollector {
                        onStreamFinished: {
                            var color = this.text.trim()
                            if (color && color.startsWith("#")) {
                                settingsMenu.accentColor = color
                            }
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: colorPickerProc.running = true

                    property bool hovered: false
                    onEntered: hovered = true
                    onExited: hovered = false
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width + 4
                    height: parent.height + 4
                    radius: (parent.width + 4) / 2
                    color: "transparent"
                    border.width: 2
                    border.color: settingsMenu.accentColor
                    opacity: parent.children[1].hovered ? 0.6 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: 150 }
                    }
                }
            }

            Repeater {
                model: ["#FE6F2D", "#0078d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]

                delegate: Rectangle {
                    width: 50
                    height: 50
                    radius: 25
                    color: modelData
                    border.width: settingsMenu.accentColor === modelData ? 3 : 0
                    border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: settingsMenu.accentColor = modelData
                    }
                }
            }
        }
    }

    // Inactive Border Color
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("colors.inactiveBorder", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Row {
            spacing: 15

            // Color Palette Button for Inactive Border
            Rectangle {
                width: 50
                height: 50
                radius: 25
                color: settingsMenu.inactiveBorderColor
                border.width: 2
                border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"

                // Color palette icon overlay
                Image {
                    anchors.centerIn: parent
                    source: "../img/Win11-dark/actions/symbolic/color-palette-symbolic.svg"
                    width: 24
                    height: 24
                    sourceSize.width: 24
                    sourceSize.height: 24
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                    mipmap: true
                    layer.enabled: !settingsMenu.darkMode
                    layer.smooth: true
                    layer.effect: ColorOverlay { color: "#000000" }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: {
                        settingsMenu.colorPaletteTarget = "inactive"
                        settingsMenu.colorPaletteVisible = true
                    }

                    property bool hovered: false
                    onEntered: hovered = true
                    onExited: hovered = false
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width + 4
                    height: parent.height + 4
                    radius: (parent.width + 4) / 2
                    color: "transparent"
                    border.width: 2
                    border.color: settingsMenu.accentColor
                    opacity: parent.children[1].hovered ? 0.6 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: 150 }
                    }
                }
            }

            // Custom Color Picker Button for Inactive Border (hyprpicker)
            Rectangle {
                width: 50
                height: 50
                radius: 25
                color: settingsMenu.inactiveBorderColor
                border.width: 2
                border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"

                // Color picker icon overlay
                Image {
                    anchors.centerIn: parent
                    source: "../img/Win11-dark/actions/symbolic/color-picker-symbolic.svg"
                    width: 24
                    height: 24
                    sourceSize.width: 24
                    sourceSize.height: 24
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                    mipmap: true
                    layer.enabled: !settingsMenu.darkMode
                    layer.smooth: true
                    layer.effect: ColorOverlay { color: "#000000" }
                }

                Process {
                    id: inactiveBorderColorPickerProc
                    command: ["bash", "-c", "hyprpicker -a"]
                    running: false
                    stdout: StdioCollector {
                        onStreamFinished: {
                            var color = this.text.trim()
                            if (color && color.startsWith("#")) {
                                settingsMenu.inactiveBorderColor = color
                            }
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: inactiveBorderColorPickerProc.running = true

                    property bool hovered: false
                    onEntered: hovered = true
                    onExited: hovered = false
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width + 4
                    height: parent.height + 4
                    radius: (parent.width + 4) / 2
                    color: "transparent"
                    border.width: 2
                    border.color: settingsMenu.accentColor
                    opacity: parent.children[1].hovered ? 0.6 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: 150 }
                    }
                }
            }

            Repeater {
                model: ["#595959", "#3a3a3a", "#2a2a2a", "#4a4a4a", "#6a6a6a", "#1a1a1a"]

                delegate: Rectangle {
                    width: 50
                    height: 50
                    radius: 25
                    color: modelData
                    border.width: settingsMenu.inactiveBorderColor === modelData ? 3 : 0
                    border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: settingsMenu.inactiveBorderColor = modelData
                    }
                }
            }
        }

        Text {
            text: Lang.get("colors.changesApplied", _lang)
            font.pixelSize: 11
            color: settingsMenu.darkMode ? "#666" : "#888"
            font.italic: true
        }
}
}
