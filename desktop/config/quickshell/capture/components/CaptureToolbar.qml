import QtQuick
import "Strings.js" as Strings

// Floating top-center pill: [Screenshot | Record]  region window screen  delay  options  Capture  X
Item {
    id: bar

    property var controller: null
    readonly property string lang: controller ? controller.lang : "en"
    readonly property bool recordTab: controller ? controller.tab === "record" : false
    readonly property var delays: [0, 3, 5, 10]

    function tr(key, arg) { return Strings.t(key, bar.lang, arg) }
    function delayLabel(value) { return value === 0 ? tr("delay.none") : tr("delay.seconds", String(value)) }

    width: pill.width
    height: pill.height

    Rectangle {
        id: pill
        height: 52
        width: row.width + 16
        radius: Math.min(height / 2, CaptureTheme.borderRadius + 14)
        color: CaptureTheme.panel
        border.width: 1
        border.color: CaptureTheme.panelBorder

        // Swallow clicks on the pill so they do not start a selection behind it.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onPressed: if (bar.controller) bar.controller.openMenu = ""
        }

        Row {
            id: row
            anchors.verticalCenter: parent.verticalCenter
            x: 8
            spacing: 6

            // Segmented switch
            Rectangle {
                height: 40
                width: seg.width + 6
                anchors.verticalCenter: parent.verticalCenter
                radius: CaptureTheme.borderRadius + 2
                color: CaptureTheme.hover
                Row {
                    id: seg
                    x: 3
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    CapButton {
                        label: bar.tr("tab.screenshot")
                        active: !bar.recordTab
                        height: 34
                        onClicked: bar.controller.tab = "screenshot"
                    }
                    CapButton {
                        label: bar.tr("tab.record")
                        active: bar.recordTab
                        height: 34
                        onClicked: bar.controller.tab = "record"
                    }
                }
            }

            Rectangle { width: 1; height: 24; anchors.verticalCenter: parent.verticalCenter; color: CaptureTheme.separator }

            // Mode buttons
            Repeater {
                model: ["region", "window", "screen"]
                CapButton {
                    required property string modelData
                    active: bar.controller && bar.controller.mode === modelData
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: bar.controller.setMode(modelData)
                    ModeIcon {
                        anchors.centerIn: parent
                        kind: modelData
                        tint: parent.parent.filled ? CaptureTheme.onAccent : CaptureTheme.text
                    }
                }
            }

            Rectangle { width: 1; height: 24; anchors.verticalCenter: parent.verticalCenter; color: CaptureTheme.separator }

            // Delay dropdown
            Item {
                id: delayHolder
                width: delayButton.width
                height: 36
                anchors.verticalCenter: parent.verticalCenter

                CapButton {
                    id: delayButton
                    labelPadding: 0
                    implicitWidth: delayRow.width + 20
                    onClicked: bar.controller.openMenu = (bar.controller.openMenu === "delay" ? "" : "delay")
                    Row {
                        id: delayRow
                        anchors.centerIn: parent
                        spacing: 6
                        ModeIcon { kind: "timer"; tint: CaptureTheme.text; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: bar.delayLabel(bar.controller ? bar.controller.delay : 0)
                            font.pixelSize: 13
                            color: CaptureTheme.text
                        }
                        ModeIcon { kind: "chevron"; tint: CaptureTheme.mutedText; anchors.verticalCenter: parent.verticalCenter }
                    }
                }

                Rectangle {
                    id: delayMenu
                    visible: bar.controller && bar.controller.openMenu === "delay"
                    y: delayHolder.height + 14
                    width: 168
                    height: delayColumn.height + 12
                    radius: CaptureTheme.borderRadius + 2
                    color: CaptureTheme.panel
                    border.width: 1
                    border.color: CaptureTheme.panelBorder
                    z: 10
                    MouseArea { anchors.fill: parent }
                    Column {
                        id: delayColumn
                        x: 6
                        y: 6
                        spacing: 2
                        Repeater {
                            model: bar.delays
                            CapButton {
                                required property int modelData
                                width: 156
                                height: 32
                                active: bar.controller && bar.controller.delay === modelData
                                label: bar.delayLabel(modelData)
                                onClicked: {
                                    bar.controller.delay = modelData
                                    bar.controller.openMenu = ""
                                }
                            }
                        }
                    }
                }
            }

            // Options button + popover
            Item {
                id: optionsHolder
                width: 36
                height: 36
                anchors.verticalCenter: parent.verticalCenter

                CapButton {
                    id: optionsButton
                    active: bar.controller && bar.controller.openMenu === "options"
                    onClicked: bar.controller.openMenu = (bar.controller.openMenu === "options" ? "" : "options")
                    ModeIcon {
                        anchors.centerIn: parent
                        kind: "options"
                        tint: parent.parent.filled ? CaptureTheme.onAccent : CaptureTheme.text
                    }
                }

                Rectangle {
                    id: optionsMenu
                    visible: bar.controller && bar.controller.openMenu === "options"
                    x: optionsHolder.width - width
                    y: optionsHolder.height + 14
                    width: 270
                    height: optionsColumn.height + 12
                    radius: CaptureTheme.borderRadius + 2
                    color: CaptureTheme.panel
                    border.width: 1
                    border.color: CaptureTheme.panelBorder
                    z: 10
                    MouseArea { anchors.fill: parent }
                    Column {
                        id: optionsColumn
                        x: 6
                        y: 6
                        spacing: 2
                        Repeater {
                            model: [
                                { key: "copy", text: "opt.copy" },
                                { key: "pointer", text: "opt.pointer" },
                                { key: "audio", text: "opt.audio" }
                            ]
                            Rectangle {
                                id: optRow
                                required property var modelData
                                readonly property bool on: bar.controller ? bar.controller[modelData.key] === true : false
                                width: 258
                                height: 34
                                radius: CaptureTheme.borderRadius
                                color: optArea.containsMouse ? CaptureTheme.hover : "transparent"
                                Text {
                                    x: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: bar.tr(optRow.modelData.text)
                                    font.pixelSize: 13
                                    color: CaptureTheme.text
                                }
                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 20
                                    height: 20
                                    radius: Math.min(10, CaptureTheme.borderRadius)
                                    color: optRow.on ? CaptureTheme.accentColor : "transparent"
                                    border.width: 2
                                    border.color: optRow.on ? CaptureTheme.accentColor : CaptureTheme.mutedText
                                    Text {
                                        anchors.centerIn: parent
                                        visible: optRow.on
                                        text: "✓"
                                        font.pixelSize: 13
                                        color: CaptureTheme.onAccent
                                    }
                                }
                                MouseArea {
                                    id: optArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: bar.controller[optRow.modelData.key] = !optRow.on
                                }
                            }
                        }
                    }
                }
            }

            // Primary button
            CapButton {
                primary: true
                height: 38
                labelPadding: 20
                anchors.verticalCenter: parent.verticalCenter
                label: bar.recordTab ? bar.tr("startRecording") : bar.tr("capture")
                onClicked: bar.controller.capture()
            }

            // Close
            CapButton {
                anchors.verticalCenter: parent.verticalCenter
                onClicked: bar.controller.cancel()
                ModeIcon { anchors.centerIn: parent; kind: "close"; tint: CaptureTheme.text }
            }
        }
    }
}
