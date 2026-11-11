import QtQuick
import QtQuick.Dialogs as Dialogs
import Quickshell.Io
import "../widgets"
import "../i18n/Lang.js" as Lang

Column {
    id: orbSettings
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    property bool importFailed: false
    width: parent.width
    spacing: 15

    Column {
        width: parent.width
        spacing: 5
        Text {
            text: Lang.get("appearance.startOrb", orbSettings._lang)
            font.pixelSize: 18
            font.bold: true
            color: orbSettings.settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }
        Text {
            width: parent.width
            text: Lang.get("appearance.startOrbDesc", orbSettings._lang)
            wrapMode: Text.WordWrap
            font.pixelSize: 12
            color: orbSettings.settingsMenu.darkMode ? "#666" : "#888"
        }
    }
    Row {
        width: parent.width
        spacing: 15
        Repeater {
            model: ["classic", "dot", "custom"]
            delegate: Rectangle {
                id: choice
                required property string modelData
                property bool selected: orbSettings.settingsMenu.startOrbStyle === modelData
                width: (orbSettings.width - 30) / 3
                height: 120
                radius: 8
                color: selected ? orbSettings.settingsMenu.accentColor : (orbSettings.settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                border.width: 2
                border.color: selected ? orbSettings.settingsMenu.accentColor : (orbSettings.settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                enabled: modelData !== "custom" || orbSettings.settingsMenu.startOrbCustomSource !== ""
                opacity: enabled ? 1.0 : 0.5
                activeFocusOnTab: enabled
                Accessible.role: Accessible.RadioButton
                Accessible.name: Lang.get("appearance.startOrb." + modelData, orbSettings._lang)
                Accessible.checked: selected
                Keys.onSpacePressed: orbSettings.settingsMenu.startOrbStyle = modelData
                Keys.onReturnPressed: orbSettings.settingsMenu.startOrbStyle = modelData

                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on border.color { ColorAnimation { duration: 150 } }

                Column {
                    anchors.centerIn: parent
                    width: parent.width - 30
                    spacing: 10
                    StartOrb {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 32
                        height: 32
                        style: choice.modelData
                        customSource: orbSettings.settingsMenu.startOrbCustomSource
                    }
                    Text {
                        width: parent.width
                        text: Lang.get("appearance.startOrb." + choice.modelData, orbSettings._lang)
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        color: choice.selected ? "#fff" : (orbSettings.settingsMenu.darkMode ? "#fff" : "#1a1a1a")
                        font.pixelSize: 14
                        font.bold: true
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: orbSettings.settingsMenu.startOrbStyle = choice.modelData
                }
            }
        }
    }
    Rectangle {
        width: Math.min(parent.width, uploadLabel.implicitWidth + 32)
        height: 36
        radius: 6
        color: importOrb.running ? (orbSettings.settingsMenu.darkMode ? "#444444" : "#cccccc") : orbSettings.settingsMenu.accentColor
        opacity: importOrb.running ? 0.5 : 1.0
        activeFocusOnTab: !importOrb.running
        Accessible.role: Accessible.Button
        Accessible.name: uploadLabel.text
        function chooseImage() {
            orbSettings.importFailed = false
            orbSettings.settingsMenu.fileDialogOpen = true
            picker.open()
        }
        Keys.onSpacePressed: if (!importOrb.running) chooseImage()
        Keys.onReturnPressed: if (!importOrb.running) chooseImage()
        Text {
            id: uploadLabel
            anchors.centerIn: parent
            text: Lang.get("appearance.startOrbChoose", orbSettings._lang)
            color: "#fff"
            font.pixelSize: 13
            font.bold: true
        }
        MouseArea {
            anchors.fill: parent
            enabled: !importOrb.running
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: parent.chooseImage()
        }
    }
    Text {
        visible: orbSettings.importFailed
        width: parent.width
        text: Lang.get("appearance.startOrbError", orbSettings._lang)
        wrapMode: Text.WordWrap
        color: orbSettings.settingsMenu.darkMode ? "#ff9999" : "#a82222"
        font.pixelSize: 12
    }
    Dialogs.FileDialog {
        id: picker
        title: Lang.get("appearance.startOrbChoose", orbSettings._lang)
        nameFilters: [Lang.get("appearance.startOrbImages", orbSettings._lang) + " (*.png *.jpg *.jpeg *.webp *.svg)"]
        onAccepted: {
            orbSettings.settingsMenu.fileDialogOpen = false
            importOrb.command = ["windoesnot-import-orb", selectedFile.toString()]
            importOrb.running = true
        }
        onRejected: orbSettings.settingsMenu.fileDialogOpen = false
    }
    Process {
        id: importOrb
        stdout: StdioCollector {
            onStreamFinished: {
                var path = this.text.trim()
                if (path.indexOf("file://") === 0) {
                    orbSettings.settingsMenu.startOrbCustomSource = path
                    orbSettings.settingsMenu.startOrbStyle = "custom"
                    orbSettings.importFailed = false
                } else orbSettings.importFailed = true
            }
        }
    }
}
