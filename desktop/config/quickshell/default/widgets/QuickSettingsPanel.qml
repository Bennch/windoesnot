import QtQuick
import QtQuick.Layouts
import "../i18n/Lang.js" as Lang

Rectangle {
    id: quickSettings
    width: 360
    height: 340
    radius: 12
    color: Qt.rgba(0.125, 0.125, 0.125, 0.95)
    border.color: "#3a3a3f"
    border.width: 1

    property color accentColor: "#FE6F2D"
    property string uiLanguage: "de"  // Bound from shell.qml

    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

    Column {
        anchors.fill: parent
        anchors.margins: 15
        spacing: 10

        // Quick Settings Title
        Text {
            text: Lang.get("quickSettings.title", uiLanguage)
            font.pixelSize: 16
            font.bold: true
            color: "#fff"
        }

        // Quick Settings Grid (Audio, Bluetooth, Network)
        Grid {
            width: parent.width
            columns: 3
            columnSpacing: 10
            rowSpacing: 10

            // Audio Toggle
            Rectangle {
                width: 103
                height: 80
                radius: 8
                color: audioMouseArea.containsMouse ? "#2a2a2a" : "#1f1f1f"
                border.width: 1
                border.color: "#3a3a3a"

                Behavior on color { ColorAnimation { duration: 150 } }

                Column {
                    anchors.centerIn: parent
                    spacing: 8

                    ProjectIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        name: "audio"
                        font.pixelSize: 24
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: Lang.get("audio.title", uiLanguage)
                        font.pixelSize: 12
                        color: "#ccc"
                    }
                }

                MouseArea {
                    id: audioMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        // TODO: Öffne Audio Widget
                        console.log("Audio clicked")
                    }
                }
            }

            // Bluetooth Toggle
            Rectangle {
                width: 103
                height: 80
                radius: 8
                color: bluetoothMouseArea.containsMouse ? "#2a2a2a" : "#1f1f1f"
                border.width: 1
                border.color: "#3a3a3a"

                Behavior on color { ColorAnimation { duration: 150 } }

                Column {
                    anchors.centerIn: parent
                    spacing: 8

                    ProjectIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        name: "bluetooth"
                        font.pixelSize: 24
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: Lang.get("bluetooth.title", uiLanguage)
                        font.pixelSize: 12
                        color: "#ccc"
                    }
                }

                MouseArea {
                    id: bluetoothMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        // TODO: Öffne Bluetooth Widget
                        console.log("Bluetooth clicked")
                    }
                }
            }

            // Network Toggle
            Rectangle {
                width: 103
                height: 80
                radius: 8
                color: networkMouseArea.containsMouse ? "#2a2a2a" : "#1f1f1f"
                border.width: 1
                border.color: "#3a3a3a"

                Behavior on color { ColorAnimation { duration: 150 } }

                Column {
                    anchors.centerIn: parent
                    spacing: 8

                    ProjectIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        name: "network"
                        font.pixelSize: 24
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: Lang.get("network.title", uiLanguage)
                        font.pixelSize: 12
                        color: "#ccc"
                    }
                }

                MouseArea {
                    id: networkMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        // TODO: Öffne Network Widget
                        console.log("Network clicked")
                    }
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#3a3a3a"
        }

        // Brightness Slider
        Column {
            width: parent.width
            spacing: 8

            Row {
                width: parent.width
                spacing: 10

                ProjectIcon {
                    name: "brightness"
                    font.pixelSize: 18
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: Lang.get("quickSettings.brightness", uiLanguage)
                    font.pixelSize: 13
                    color: "#ccc"
                    anchors.verticalCenter: parent.verticalCenter
                }

                Item { Layout.fillWidth: true; width: parent.width - 150 }

                Text {
                    text: "75%"
                    font.pixelSize: 12
                    color: "#999"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Rectangle {
                width: parent.width
                height: 6
                radius: 3
                color: "#2a2a2a"

                Rectangle {
                    width: parent.width * 0.75
                    height: parent.height
                    radius: 3
                    color: quickSettings.accentColor
                }
            }
        }

        // Volume Slider
        Column {
            width: parent.width
            spacing: 8

            Row {
                width: parent.width
                spacing: 10

                ProjectIcon {
                    name: "audio"
                    font.pixelSize: 18
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: Lang.get("quickSettings.volume", uiLanguage)
                    font.pixelSize: 13
                    color: "#ccc"
                    anchors.verticalCenter: parent.verticalCenter
                }

                Item { Layout.fillWidth: true; width: parent.width - 150 }

                Text {
                    text: "50%"
                    font.pixelSize: 12
                    color: "#999"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Rectangle {
                width: parent.width
                height: 6
                radius: 3
                color: "#2a2a2a"

                Rectangle {
                    width: parent.width * 0.5
                    height: parent.height
                    radius: 3
                    color: quickSettings.accentColor
                }
            }
        }

    }
}
