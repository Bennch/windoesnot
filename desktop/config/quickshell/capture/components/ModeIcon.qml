import QtQuick

// Small drawn icons (no icon theme needed): region, window, screen, close, chevron, options.
Item {
    id: icon

    property string kind: "region"
    property color tint: "#ffffff"
    width: 20
    height: 20

    // region: rectangle outline
    Rectangle {
        visible: icon.kind === "region"
        anchors.centerIn: parent
        width: 16
        height: 14
        radius: 2
        color: "transparent"
        border.width: 2
        border.color: icon.tint
    }

    // window: outline with a title bar line
    Rectangle {
        visible: icon.kind === "window"
        anchors.centerIn: parent
        width: 18
        height: 14
        radius: 2
        color: "transparent"
        border.width: 2
        border.color: icon.tint
        Rectangle {
            x: 0
            y: 3
            width: parent.width
            height: 2
            color: icon.tint
        }
    }

    // screen: monitor with a stand
    Rectangle {
        visible: icon.kind === "screen"
        x: 1
        y: 3
        width: 18
        height: 11
        radius: 2
        color: "transparent"
        border.width: 2
        border.color: icon.tint
    }
    Rectangle {
        visible: icon.kind === "screen"
        x: 6
        y: 16
        width: 8
        height: 2
        radius: 1
        color: icon.tint
    }

    // close: X
    Text {
        visible: icon.kind === "close"
        anchors.centerIn: parent
        text: "✕"
        font.pixelSize: 14
        color: icon.tint
    }

    // chevron
    Text {
        visible: icon.kind === "chevron"
        anchors.centerIn: parent
        text: "▾"
        font.pixelSize: 12
        color: icon.tint
    }

    // options: three sliders
    Column {
        visible: icon.kind === "options"
        anchors.centerIn: parent
        spacing: 4
        Repeater {
            model: 3
            Rectangle {
                width: 16
                height: 2
                radius: 1
                color: icon.tint
                Rectangle {
                    x: index === 1 ? 9 : 3
                    y: -2
                    width: 6
                    height: 6
                    radius: 3
                    color: icon.tint
                }
            }
        }
    }

    // timer: circle with a hand
    Rectangle {
        visible: icon.kind === "timer"
        anchors.centerIn: parent
        width: 16
        height: 16
        radius: 8
        color: "transparent"
        border.width: 2
        border.color: icon.tint
        Rectangle {
            x: 6
            y: 3
            width: 2
            height: 5
            color: icon.tint
        }
    }
}
