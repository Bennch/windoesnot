import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"  // Trigger für Bindings

    width: parent.width
    spacing: 30

    // Desktop Icon Size
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("desktop.iconSize", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Text {
            text: Lang.get("desktop.iconSizeDesc", _lang)
            font.pixelSize: 12
            color: settingsMenu.darkMode ? "#666" : "#888"
            wrapMode: Text.WordWrap
        }

        Row {
            width: parent.width
            spacing: 15

            Slider {
                id: iconSizeSlider
                width: parent.width - 80
                from: 32
                to: 128
                stepSize: 8
                value: settingsMenu ? settingsMenu.desktopIconSize : 64

                background: Rectangle {
                    x: iconSizeSlider.leftPadding
                    y: iconSizeSlider.topPadding + iconSizeSlider.availableHeight / 2 - height / 2
                    implicitWidth: 200
                    implicitHeight: 4
                    width: iconSizeSlider.availableWidth
                    height: implicitHeight
                    radius: 2
                    color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    Rectangle {
                        width: iconSizeSlider.visualPosition * parent.width
                        height: parent.height
                        color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        radius: 2
                    }
                }

                handle: Rectangle {
                    x: iconSizeSlider.leftPadding + iconSizeSlider.visualPosition * (iconSizeSlider.availableWidth - width)
                    y: iconSizeSlider.topPadding + iconSizeSlider.availableHeight / 2 - height / 2
                    implicitWidth: 18
                    implicitHeight: 18
                    radius: 9
                    color: iconSizeSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                    border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 2

                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                onMoved: {
                    if (settingsMenu) {
                        settingsMenu.desktopIconSize = value
                    }
                }
            }

            Text {
                text: iconSizeSlider.value + " px"
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#ccc" : "#555"
                width: 60
                horizontalAlignment: Text.AlignRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Grid Size
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("desktop.grid", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Text {
            text: Lang.get("desktop.gridDesc", _lang)
            font.pixelSize: 12
            color: settingsMenu.darkMode ? "#666" : "#888"
            wrapMode: Text.WordWrap
        }

        Row {
            width: parent.width
            spacing: 15

            Slider {
                id: gridSizeSlider
                width: parent.width - 80
                from: 0
                to: 64
                stepSize: 8
                value: settingsMenu ? settingsMenu.desktopGridSize : 16

                background: Rectangle {
                    x: gridSizeSlider.leftPadding
                    y: gridSizeSlider.topPadding + gridSizeSlider.availableHeight / 2 - height / 2
                    implicitWidth: 200
                    implicitHeight: 4
                    width: gridSizeSlider.availableWidth
                    height: implicitHeight
                    radius: 2
                    color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    Rectangle {
                        width: gridSizeSlider.visualPosition * parent.width
                        height: parent.height
                        color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        radius: 2
                    }
                }

                handle: Rectangle {
                    x: gridSizeSlider.leftPadding + gridSizeSlider.visualPosition * (gridSizeSlider.availableWidth - width)
                    y: gridSizeSlider.topPadding + gridSizeSlider.availableHeight / 2 - height / 2
                    implicitWidth: 18
                    implicitHeight: 18
                    radius: 9
                    color: gridSizeSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                    border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 2

                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                onMoved: {
                    if (settingsMenu) {
                        settingsMenu.desktopGridSize = value
                    }
                }
            }

            Text {
                text: gridSizeSlider.value === 0 ? Lang.get("desktop.gridOff", _lang) : gridSizeSlider.value + " px"
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#ccc" : "#555"
                width: 60
                horizontalAlignment: Text.AlignRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Label Lines
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("desktop.labelLines", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Text {
            text: Lang.get("desktop.labelLinesDesc", _lang)
            font.pixelSize: 12
            color: settingsMenu.darkMode ? "#666" : "#888"
            wrapMode: Text.WordWrap
        }

        Row {
            spacing: 10

            Repeater {
                model: [1, 2, 3]

                Rectangle {
                    width: 50
                    height: 32
                    radius: 6
                    color: settingsMenu && settingsMenu.desktopLabelLines === modelData ? (settingsMenu.accentColor) : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                    border.color: settingsMenu && settingsMenu.desktopLabelLines === modelData ? settingsMenu.accentColor : "#555"
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 100 } }
                    Behavior on border.color { ColorAnimation { duration: 100 } }

                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        font.pixelSize: 14
                        color: settingsMenu && settingsMenu.desktopLabelLines === modelData
                            ? "#fff"
                            : (settingsMenu.darkMode ? "#aaa" : "#333")
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (settingsMenu) {
                                settingsMenu.desktopLabelLines = modelData
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Show Trash
    Row {
        width: parent.width
        spacing: 15

        Column {
            spacing: 5
            width: parent.width - 80

            Text {
                text: Lang.get("desktop.showTrash", _lang)
                font.pixelSize: 16
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            Text {
                text: Lang.get("desktop.showTrashDesc", _lang)
                font.pixelSize: 12
                color: settingsMenu.darkMode ? "#666" : "#888"
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            width: 50
            height: 26
            radius: 13
            color: settingsMenu && settingsMenu.desktopShowTrash ? (settingsMenu.accentColor) : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
            anchors.verticalCenter: parent.verticalCenter

            Behavior on color { ColorAnimation { duration: 150 } }

            Rectangle {
                width: 20
                height: 20
                radius: 10
                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                x: settingsMenu && settingsMenu.desktopShowTrash ? parent.width - width - 3 : 3
                anchors.verticalCenter: parent.verticalCenter

                Behavior on x { NumberAnimation { duration: 150 } }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (settingsMenu) {
                        settingsMenu.desktopShowTrash = !settingsMenu.desktopShowTrash
                    }
                }
            }
        }
    }
}
