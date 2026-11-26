import QtQuick

// Button of the capture toolbar. Plain buttons are transparent and light up on hover; `active` (selected segment or
// mode) and `primary` (Capture / Start recording) use the accent colour with matching text colour.
Rectangle {
    id: btn

    property bool active: false
    property bool primary: false
    property bool danger: false
    property string label: ""
    property real labelPadding: 14
    property int pixel: 13
    default property alias content: slot.data
    readonly property bool hovered: area.containsMouse
    readonly property bool filled: primary || active || danger
    signal clicked()

    implicitHeight: 36
    implicitWidth: label.length > 0 ? labelText.implicitWidth + 2 * labelPadding : 36
    radius: CaptureTheme.borderRadius
    color: danger ? (hovered ? Qt.lighter(CaptureTheme.danger, 1.1) : CaptureTheme.danger)
                  : (primary || active) ? (hovered ? Qt.lighter(CaptureTheme.accentColor, 1.08) : CaptureTheme.accentColor)
                  : (hovered ? CaptureTheme.hover : "transparent")

    Item {
        id: slot
        anchors.centerIn: parent
        width: 20
        height: 20
    }

    Text {
        id: labelText
        anchors.centerIn: parent
        visible: btn.label.length > 0
        text: btn.label
        font.pixelSize: btn.pixel
        font.weight: btn.primary ? Font.DemiBold : Font.Normal
        color: btn.filled ? (btn.danger ? "#ffffff" : CaptureTheme.onAccent) : CaptureTheme.text
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        onClicked: btn.clicked()
    }
}
