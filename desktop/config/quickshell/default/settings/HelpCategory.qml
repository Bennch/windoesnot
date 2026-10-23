import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"

    width: parent.width
    spacing: 30

    Text {
        text: Lang.get("help.shortcuts", _lang)
        font.pixelSize: 18
        font.bold: true
        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
    }

    Column {
        width: parent.width
        spacing: 12

        Repeater {
            model: ListModel {
                ListElement { key1: "SUPER"; key2: "M"; descKey: "help.openStartmenu" }
                ListElement { key1: "SUPER"; key2: "S"; descKey: "help.openSettings" }
                ListElement { key1: "SUPER"; key2: "Q"; descKey: "help.openTerminal" }
                ListElement { key1: "SUPER"; key2: "E"; descKey: "help.openFileManager" }
                ListElement { key1: "SUPER"; key2: "C"; descKey: "help.closeWindow" }
                ListElement { key1: "SUPER"; key2: "TAB"; descKey: "help.workspaceOverview" }
                ListElement { key1: "SUPER"; key2: "V"; descKey: "help.pinWindow" }
                ListElement { key1: "SUPER"; key2: "F"; descKey: "help.fullscreen" }
                ListElement { key1: "SUPER"; key2: "H"; descKey: "help.showDesktop" }
                ListElement { key1: "SUPER"; key2: "N"; descKey: "help.notifications" }
                ListElement { key1: "SUPER"; key2: "P"; descKey: "help.colorPicker" }
                ListElement { key1: "SUPER"; key2: "DRUCK"; descKey: "help.screenshot" }
                ListElement { key1: "SUPER"; key2: "F12"; descKey: "help.gamescopeFix" }
                ListElement { key1: "SUPER"; key2: "LMB"; descKey: "help.moveWindow" }
            }

            delegate: Row {
                width: parent.width
                spacing: 15

                // Linker Bereich: Tastenkombination
                Row {
                    spacing: 8
                    width: 200

                    Rectangle {
                        width: key1Text.width + 16
                        height: 32
                        radius: 6
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                        Text {
                            id: key1Text
                            anchors.centerIn: parent
                            text: key1
                            font.pixelSize: 11
                            font.bold: true
                            color: settingsMenu.accentColor
                        }
                    }

                    Text {
                        text: "+"
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#666" : "#888"
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Rectangle {
                        width: key2Text.width + 16
                        height: 32
                        radius: 6
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                        Text {
                            id: key2Text
                            anchors.centerIn: parent
                            text: key2
                            font.pixelSize: 11
                            font.bold: true
                            color: settingsMenu.accentColor
                        }
                    }
                }

                // Rechter Bereich: Beschreibung
                Text {
                    text: Lang.get(descKey)
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 220
                    wrapMode: Text.WordWrap
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    Text {
        text: Lang.get("help.startmenuManagement", _lang)
        font.pixelSize: 18
        font.bold: true
        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
    }

    Text {
        text: Lang.get("help.startmenuTips", _lang)
        font.pixelSize: 13
        color: settingsMenu.darkMode ? "#999" : "#666"
        lineHeight: 1.5
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    Column {
        width: parent.width
        spacing: 10

        Text {
            text: _lang === "de" ? "Quickshell" : "Quickshell"
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Text {
            text: _lang === "de"
                ? "Startet die Shell neu — neue Instanz läuft zuerst, dann wird die alte beendet. Einstellungen, Pins und Taskbar bleiben erhalten."
                : "Restarts the shell — new instance starts first, then the old one exits. Settings, pins and taskbar are preserved."
            font.pixelSize: 12
            color: settingsMenu.darkMode ? "#777" : "#888"
            wrapMode: Text.WordWrap
            width: parent.width
            lineHeight: 1.5
        }

        Rectangle {
            width: restartLabel.implicitWidth + 28
            height: 34
            radius: settingsMenu.borderRadius
            color: "transparent"
            border.color: settingsMenu.darkMode ? "#555" : "#ccc"
            border.width: 1

            property bool hovered: false
            Behavior on color { ColorAnimation { duration: 120 } }

            states: State {
                when: parent.hovered
                PropertyChanges { target: parent; color: settingsMenu.darkMode ? Qt.rgba(1,1,1,0.07) : Qt.rgba(0,0,0,0.05) }
            }

            Row {
                anchors.centerIn: parent
                spacing: 8

                Image {
                    source: "../img/Win11-dark/actions/symbolic/view-refresh-symbolic.svg"
                    width: 14; height: 14
                    anchors.verticalCenter: parent.verticalCenter
                    opacity: settingsMenu.darkMode ? 0.7 : 0.5
                }

                Text {
                    id: restartLabel
                    text: _lang === "de" ? "Quickshell neu starten" : "Restart Quickshell"
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#cccccc" : "#444444"
                }
            }

            Process {
                id: restartProc
                command: ["bash", "-c",
                    "setsid bash -c 'sleep 0.2; killall quickshell; sleep 0.4; QT_QPA_PLATFORMTHEME=gtk3 quickshell' &>/dev/null &"]
            }

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: parent.hovered = true
                onExited:  parent.hovered = false
                onClicked: restartProc.running = true
            }
        }
    }
}
