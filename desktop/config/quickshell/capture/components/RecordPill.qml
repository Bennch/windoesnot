import QtQuick
import Quickshell
import Quickshell.Wayland
import "Strings.js" as Strings

// Small floating pill during the countdown and while recording: red dot, running timer, Stop.
PanelWindow {
    id: pillWindow

    property var controller: null
    readonly property string lang: controller ? controller.lang : "en"
    readonly property bool counting: controller ? controller.phase === "countdown" : false
    readonly property bool recording: controller ? controller.phase === "recording" : false

    function tr(key, arg) { return Strings.t(key, pillWindow.lang, arg) }
    function clock(seconds) {
        var m = Math.floor(seconds / 60)
        var s = seconds % 60
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
    }

    visible: controller !== null && screen !== null && controller.pillMonitor === screen.name && (counting || recording)
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    anchors { top: true }
    margins { top: 16 }
    implicitWidth: card.width
    implicitHeight: card.height
    WlrLayershell.namespace: "quickshell-capture-pill"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    Rectangle {
        id: card
        width: content.width + 20
        height: 48
        radius: Math.min(height / 2, CaptureTheme.borderRadius + 14)
        color: CaptureTheme.panel
        border.width: 1
        border.color: CaptureTheme.accentColor

        Row {
            id: content
            x: 10
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            Rectangle {
                width: 12
                height: 12
                radius: 6
                anchors.verticalCenter: parent.verticalCenter
                color: CaptureTheme.danger
                visible: pillWindow.recording
                SequentialAnimation on opacity {
                    running: pillWindow.recording
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 700 }
                    NumberAnimation { to: 1.0; duration: 700 }
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: pillWindow.recording ? pillWindow.clock(pillWindow.controller.elapsed)
                                           : pillWindow.tr("startsIn", String(pillWindow.controller ? pillWindow.controller.countdown : 0))
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: CaptureTheme.text
            }

            CapButton {
                anchors.verticalCenter: parent.verticalCenter
                danger: pillWindow.recording
                primary: !pillWindow.recording
                label: pillWindow.recording ? pillWindow.tr("stop") : pillWindow.tr("cancel")
                onClicked: pillWindow.recording ? pillWindow.controller.stopRecording() : pillWindow.controller.cancel()
            }
        }
    }
}
