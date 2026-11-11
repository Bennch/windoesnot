import QtQuick

// Portable UPower battery glyph: percentage, low-battery warning and AC state.
Item {
    id: root
    property bool available: false
    property real percentage: 0
    property bool pluggedIn: false
    property bool darkMode: true
    readonly property real level: Math.max(0, Math.min(100, percentage))
    readonly property color foreground: darkMode ? "#ffffff" : "#333333"
    readonly property bool desktopPower: !available && pluggedIn

    Rectangle { visible: !root.desktopPower; x: 1; y: 3; width: 17; height: 12; radius: 2; color: "transparent"; border.width: 1; border.color: root.foreground
        Rectangle { x: 2; y: 2; height: 8; width: root.available ? 13 * root.level / 100 : 0; radius: 1; color: root.level <= 15 && !root.pluggedIn ? "#ef5350" : root.foreground }
    }
    Rectangle { visible: !root.desktopPower; x: 18; y: 7; width: 2; height: 4; radius: 1; color: root.foreground }
    Rectangle { visible: root.pluggedIn; x: 11; y: 8; width: 11; height: 10; radius: 2; color: root.darkMode ? "#202020" : "#fafafa"
        Rectangle { x: 3; y: 3; width: 6; height: 4; radius: 1; color: root.foreground }
        Rectangle { x: 4; y: 1; width: 1; height: 3; color: root.foreground }
        Rectangle { x: 7; y: 1; width: 1; height: 3; color: root.foreground }
        Rectangle { x: 5; y: 6; width: 2; height: 3; color: root.foreground }
    }
    // Desktop without a battery: use a power plug, never a misleading empty cell.
    Item { visible: root.desktopPower; anchors.centerIn: parent; width: 16; height: 16
        Rectangle { x: 4; y: 5; width: 8; height: 7; radius: 2; color: root.foreground }
        Rectangle { x: 5; y: 1; width: 2; height: 5; radius: 1; color: root.foreground }
        Rectangle { x: 9; y: 1; width: 2; height: 5; radius: 1; color: root.foreground }
        Rectangle { x: 7; y: 11; width: 2; height: 4; radius: 1; color: root.foreground }
    }
    Text { visible: !root.available && !root.desktopPower; anchors.centerIn: parent; text: "?"; color: root.foreground; font.pixelSize: 9 }
}
