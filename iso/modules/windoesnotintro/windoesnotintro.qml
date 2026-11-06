// SPDX-License-Identifier: GPL-3.0-or-later
// "About WinDoesNot" page of the installer. Texts follow the installer language (German / English).
import QtQuick 2.7
import QtQuick.Controls 2.2

Rectangle {
    id: page
    width: 740
    height: 420
    color: "#202024"
    radius: 10

    readonly property bool german: Qt.locale().name.indexOf("de") === 0

    Flickable {
        anchors.fill: parent
        anchors.margins: 28
        contentHeight: column.height
        clip: true
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: column
            width: parent.width - 14
            spacing: 14

            Image {
                source: "file:///etc/windoesnot-calamares/branding/windoesnot/windoesnot-logo-hell.png"
                fillMode: Image.PreserveAspectFit
                width: 260
                height: width * 459 / 2446
                sourceSize.width: 520
                smooth: true
                mipmap: true
            }

            Text {
                width: parent.width
                color: "#fe6f2d"
                font.pixelSize: 22
                font.bold: true
                wrapMode: Text.WordWrap
                text: page.german ? "Du bist auf der richtigen Seite." : "You're on the right side."
            }

            Text {
                width: parent.width
                color: "#eeeeee"
                font.pixelSize: 15
                lineHeight: 1.15
                wrapMode: Text.WordWrap
                text: page.german
                    ? "Keine Sorge: Telemetrie, Datenkraken und ungebetene Updates gehören der Vergangenheit an. Hier sammelt niemand deine Gewohnheiten, niemand schickt deine Suchanfragen nach Redmond, und kein Update startet deinen Rechner um 3 Uhr nachts neu. Du hast die volle Kontrolle."
                    : "No worries: telemetry, data harvesting and unwanted updates are a thing of the past. Nobody is collecting your habits, nobody is sending your searches to Redmond, and no update will restart your machine at 3am. You're in full control."
            }

            Text {
                width: parent.width
                color: "#c9c9cf"
                font.pixelSize: 14
                lineHeight: 1.15
                wrapMode: Text.WordWrap
                text: page.german
                    ? "WinDoesNot ist ein vertrauter Desktop auf Basis von CachyOS mit Hyprland und Quickshell: Startmenü, Taskleiste und Einstellungen wie du sie kennst, dazu ein Store für Programme und ein Installer, der auch ohne Internet funktioniert. Das Projekt ist quelloffen (GPL-3.0)."
                    : "WinDoesNot is a familiar desktop built on CachyOS with Hyprland and Quickshell: a start menu, taskbar and settings you know, plus a Store for apps and an installer that also works without internet. The project is open source (GPL-3.0)."
            }

            Text {
                width: parent.width
                color: "#9a9aa2"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                text: page.german
                    ? "Wir sind kurz vor der ersten Version. Sichere trotzdem vorher deine Daten: Die Installation verändert den gewählten Datenträger."
                    : "We are close to the first release. Still, back up your data first: the installation changes the disk you select."
            }
        }
    }
}
