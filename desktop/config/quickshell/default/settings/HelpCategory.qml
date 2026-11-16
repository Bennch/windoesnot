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

    Button {
        text: Lang.get("shortcuts.open", _lang)
        Accessible.name: text
        onClicked: shortcutsProcess.running = true
        Process {
            id: shortcutsProcess
            command: ["windoesnot-bounded", "5", "windoesnot-hyprctl", "dispatch", "global", "quickshell:toggle-shortcuts"]
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
