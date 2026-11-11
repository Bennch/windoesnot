import "../widgets"
import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    property color accent: settingsMenu ? settingsMenu.accentColor : "#0078d4"
    // Installed WinDoesNot version; empty when running from files (development)
    property string installedVersion: ""

    Process {
        command: ["pacman", "-Q", "windoesnot-desktop"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                var parts = text.trim().split(" ")
                if (parts.length > 1) installedVersion = parts[1]
            }
        }
    }

    width: parent.width
    spacing: 22

    // === Privacy Banner ===
    Rectangle {
        width: parent.width
        height: bannerCol.implicitHeight + 22
        radius: settingsMenu.borderRadius
        color: settingsMenu.darkMode ? Qt.rgba(0.08, 0.08, 0.08, 1) : Qt.rgba(0.96, 0.96, 0.96, 1)
        border.color: accent
        border.width: 1

        Column {
            id: bannerCol
            anchors { left: parent.left; right: parent.right; margins: 14 }
            anchors.verticalCenter: parent.verticalCenter
            spacing: 7

            Text {
                text: Lang.get("about.privacyBanner", _lang)
                font.pixelSize: 14
                font.bold: true
                color: accent
                width: parent.width
                wrapMode: Text.WordWrap
            }

            Text {
                text: Lang.get("about.privacyIntro", _lang)
                font.pixelSize: 12
                color: settingsMenu.darkMode ? "#bbbbbb" : "#555555"
                width: parent.width
                wrapMode: Text.WordWrap
                lineHeight: 1.5
            }

            Text {
                text: Lang.get("about.office365Joke", _lang)
                font.pixelSize: 11
                font.italic: true
                color: settingsMenu.darkMode ? "#666666" : "#aaaaaa"
                width: parent.width
                wrapMode: Text.WordWrap
                lineHeight: 1.4
            }
        }
    }

    // === Report Title ===
    Text {
        text: Lang.get("about.reportTitle", _lang)
        font.pixelSize: 13
        font.bold: true
        color: settingsMenu.darkMode ? "#cccccc" : "#333333"
    }

    // === Stats Table ===
    Column {
        width: parent.width
        spacing: 1

        Repeater {
            model: ListModel {
                ListElement { statKey: "telemetry"; valKey: "zero" }
                ListElement { statKey: "ads";       valKey: "forever" }
                ListElement { statKey: "restarts";  valKey: "zero" }
                ListElement { statKey: "phonehome"; valKey: "never" }
                ListElement { statKey: "cortana";   valKey: "na" }
                ListElement { statKey: "account";   valKey: "zero" }
            }

            delegate: Rectangle {
                width: parent.width
                height: 30
                radius: 3
                color: index % 2 === 0
                    ? (settingsMenu.darkMode ? Qt.rgba(1,1,1,0.03) : Qt.rgba(0,0,0,0.03))
                    : "transparent"

                property var labels: ({
                    "de": {
                        "telemetry":  "Telemetrie-Daten gesendet",
                        "ads":        "Werbeanzeigen im Startmenü",
                        "restarts":   "Ungewollte Neustarts heute Nacht",
                        "phonehome":  "Mal nach Redmond telefoniert",
                        "cortana":    "Cortana-Aktivierungen",
                        "account":    "Pflichtfelder für Microsoft-Konto"
                    },
                    "en": {
                        "telemetry":  "Telemetry data sent",
                        "ads":        "Ads in the start menu",
                        "restarts":   "Unwanted restarts tonight",
                        "phonehome":  "Times phoned home to Redmond",
                        "cortana":    "Cortana activations",
                        "account":    "Mandatory Microsoft account fields"
                    }
                })
                property var values: ({
                    "de": { "zero": "0", "forever": "0 (für immer)", "never": "Nie wieder", "na": "N/A (Gott sei Dank)" },
                    "en": { "zero": "0", "forever": "0 (forever)",   "never": "Never again",  "na": "N/A (thank god)" }
                })

                property string lmap: _lang === "en" ? "en" : "de"
                property string displayLabel: labels[lmap][statKey] || statKey
                property string displayVal:   values[lmap][valKey]  || valKey

                Row {
                    anchors { left: parent.left; right: parent.right; leftMargin: 10; rightMargin: 10; verticalCenter: parent.verticalCenter }

                    Text {
                        text: displayLabel
                        font.pixelSize: 12
                        color: settingsMenu.darkMode ? "#888888" : "#666666"
                        width: parent.width - valText.implicitWidth - checkText.implicitWidth - 8
                        elide: Text.ElideRight
                    }
                    Text {
                        id: valText
                        text: displayVal
                        font.pixelSize: 12
                        font.bold: true
                        color: settingsMenu.darkMode ? "#dddddd" : "#222222"
                    }
                    Text {
                        id: checkText
                        text: "  ✓"
                        font.pixelSize: 11
                        color: accent
                    }
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 28
            radius: 3
            color: settingsMenu.darkMode ? Qt.rgba(1,1,1,0.03) : Qt.rgba(0,0,0,0.03)
            border.color: accent
            border.width: 1

            Text {
                anchors { left: parent.left; right: parent.right; leftMargin: 10; rightMargin: 10; verticalCenter: parent.verticalCenter }
                text: _lang === "de"
                    ? "Bericht vollständig leer — genau so soll es sein."
                    : "Report completely empty — exactly as it should be."
                font.pixelSize: 11
                font.italic: true
                color: accent
            }
        }
    }

    // === Divider ===
    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // === Title ===
    Column {
        spacing: 4

        Image {
            width: 280
            height: width * 459 / 2446
            source: settingsMenu && settingsMenu.darkMode
                ? "../img/brand/windoesnot-logo-hell.png"
                : "../img/brand/windoesnot-logo-dunkel.png"
            sourceSize.width: 560
            fillMode: Image.PreserveAspectFit
            mipmap: true
            Accessible.name: "WinDoesNot"
        }

        Text {
            text: installedVersion !== "" ? Lang.get("about.version", _lang).replace("{}", installedVersion) : Lang.get("about.versionDev", _lang)
            font.pixelSize: 12
            color: settingsMenu.darkMode ? "#666666" : "#999999"
        }
    }

    Text {
        text: Lang.get("about.description", _lang)
        font.pixelSize: 13
        color: settingsMenu.darkMode ? "#aaaaaa" : "#555555"
        wrapMode: Text.WordWrap
        width: parent.width
        lineHeight: 1.5
    }

    // === Feature Bullet Points ===
    Column {
        width: parent.width
        spacing: 6

        Text {
            text: Lang.get("about.features", _lang)
            font.pixelSize: 13
            font.bold: true
            color: settingsMenu.darkMode ? "#ffffff" : "#1a1a1a"
        }

        Repeater {
            model: _lang === "de" ? [
                "Windows 11-inspiriertes Design — Taskbar, Startmenü, Einstellungen",
                "Snap-Vorschau & Fensterverwaltung mit Hyprland-Integration",
                "Arbeitsbereich-Übersicht & Multi-Monitor-Unterstützung",
                "Eingebaute Suche: Apps, Dateien, Rechner, Emoji & Zwischenablage",
                "Audio-, Bluetooth- & WLAN-Schnellzugriff aus der Taskbar",
                "Desktop-Icons mit Dateimanager-Integration",
                "Mediensteuerung direkt in der Oberfläche",
                "Dark & Light Mode mit live Akzentfarbe",
                "Drag & Drop App-Verwaltung & Taskbar-Pinning",
                "Vollständig zweisprachig: Deutsch & Englisch"
            ] : [
                "Windows 11-inspired design — taskbar, start menu, settings",
                "Snap preview & window management with Hyprland integration",
                "Workspace overview & multi-monitor support",
                "Built-in search: apps, files, calculator, emoji & clipboard",
                "Quick access to audio, Bluetooth & WiFi from the taskbar",
                "Desktop icons with file manager integration",
                "Media controls built into the shell",
                "Dark & light mode with live accent color",
                "Drag & drop app management & taskbar pinning",
                "Fully bilingual: German & English"
            ]

            delegate: Row {
                width: parent.width
                spacing: 8

                Rectangle {
                    width: 5; height: 5; radius: 3
                    color: accent
                    anchors.verticalCenter: featureText.verticalCenter
                }

                Text {
                    id: featureText
                    text: modelData
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#aaaaaa" : "#555555"
                    width: parent.width - 13
                    wrapMode: Text.WordWrap
                    lineHeight: 1.4
                }
            }
        }
    }

    // === Divider ===
    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    ProjectIcon { name: "heart"; color: settingsMenu.accentColor; anchors.horizontalCenter: parent.horizontalCenter }
    Text {
        text: Lang.get("about.builtWith", _lang)
        font.pixelSize: 12
        color: settingsMenu.darkMode ? "#555555" : "#aaaaaa"
    }

}
