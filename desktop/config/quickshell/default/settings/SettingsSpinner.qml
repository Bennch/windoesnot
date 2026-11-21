import QtQuick

// A loading spinner drawn in one explicit colour. The stock BusyIndicator takes its colour from the Controls palette, which is
// near-invisible on the light settings background; this one is always the accent colour (or the colour you pass), light and dark.
Item {
    id: spinner
    property bool running: true
    property color color: "#fe6f2d"
    readonly property int dots: 8
    implicitWidth: 32
    implicitHeight: 32

    Item {
        id: wheel
        anchors.fill: parent
        NumberAnimation on rotation { from: 0; to: 360; duration: 1000; loops: Animation.Infinite; running: spinner.running && spinner.visible }

        Repeater {
            model: spinner.dots
            delegate: Rectangle {
                required property int index
                readonly property real size: Math.max(3, Math.min(spinner.width, spinner.height) / 6)
                width: size
                height: size
                radius: size / 2
                color: spinner.color
                opacity: 0.25 + 0.75 * (index / (spinner.dots - 1))
                x: wheel.width / 2 - size / 2 + Math.sin(index * 2 * Math.PI / spinner.dots) * (wheel.width / 2 - size)
                y: wheel.height / 2 - size / 2 - Math.cos(index * 2 * Math.PI / spinner.dots) * (wheel.height / 2 - size)
            }
        }
    }
}
