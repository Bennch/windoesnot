// SPDX-License-Identifier: GPL-3.0-or-later
// WinDoesNot start page of the installer: logo, a short text, the language choice. Replaces the stock welcomeq page
// (found through qmlSearch "both": a file in the branding directory wins over the built-in one).
import io.calamares.core 1.0
import io.calamares.ui 1.0

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: welcome

    // Texts follow the language chosen below. Qt.locale() is not reactive, so it is re-read after a change.
    property bool german: Qt.locale().name.indexOf("de") === 0

    background: Rectangle { color: "#202024" }
    palette.window: "#202024"
    palette.windowText: "#eeeeee"
    palette.button: "#29292e"
    palette.buttonText: "#eeeeee"
    palette.base: "#29292e"
    palette.text: "#eeeeee"
    palette.highlight: "#fe6f2d"
    palette.highlightedText: "#ffffff"

    Timer {
        id: relocale
        interval: 200
        onTriggered: welcome.german = Qt.locale().name.indexOf("de") === 0
    }
    Connections {
        target: config
        function onLocaleIndexChanged() { relocale.restart() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        spacing: 16

        Item { Layout.fillHeight: true }

        Image {
            Layout.alignment: Qt.AlignHCenter
            source: "file:///etc/windoesnot-calamares/branding/windoesnot/windoesnot-logo-hell.png"
            fillMode: Image.PreserveAspectFit
            Layout.preferredWidth: 300
            Layout.preferredHeight: 300 * 459 / 2446
            sourceSize.width: 600
            smooth: true
            mipmap: true
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: 640
            horizontalAlignment: Text.AlignHCenter
            color: "#fe6f2d"
            font.pixelSize: 22
            font.bold: true
            wrapMode: Text.WordWrap
            text: welcome.german ? "Du bist auf der richtigen Seite." : "You're on the right side."
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: 640
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            color: "#eeeeee"
            font.pixelSize: 15
            lineHeight: 1.15
            wrapMode: Text.WordWrap
            text: welcome.german
                ? "Keine Sorge: Telemetrie, Datenkraken und ungebetene Updates gehören der Vergangenheit an. Hier sammelt niemand deine Gewohnheiten, niemand schickt deine Suchanfragen nach Redmond, und kein Update startet deinen Rechner um 3 Uhr nachts neu."
                : "No worries: telemetry, data harvesting and unwanted updates are a thing of the past. Nobody is collecting your habits, nobody is sending your searches to Redmond, and no update will restart your machine at 3am."
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: 640
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            color: "#9a9aa2"
            font.pixelSize: 13
            wrapMode: Text.WordWrap
            text: welcome.german
                ? "Wir sind kurz vor der ersten Version. Sichere vorher deine Daten, die Installation verändert den gewählten Datenträger."
                : "We are close to the first release. Back up your data first: the installation changes the disk you select."
        }

        Item { Layout.fillHeight: true }

        // Unmet requirements (RAM, storage, ...): the stock page of the module explains them.
        Loader {
            Layout.fillWidth: true
            active: !config.requirementsModel.satisfiedRequirements
            source: "qrc:/Requirements.qml"
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Image {
                source: "qrc:/img/language-icon-48px.png"
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                fillMode: Image.PreserveAspectFit
            }

            ComboBox {
                id: languages
                Layout.fillWidth: true
                textRole: "label"
                model: config.languagesModel
                currentIndex: config.localeIndex
                onCurrentIndexChanged: config.localeIndex = currentIndex
            }
        }
    }
}
