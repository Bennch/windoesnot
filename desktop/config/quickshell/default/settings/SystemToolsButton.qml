import QtQuick
import QtQuick.Controls
import "../i18n/Lang.js" as Lang

// Same dimensions, colors and states as existing Settings controls.
Button {
    id: control
    property var settingsMenu: null
    property bool primary: false
    property bool destructive: false
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    leftPadding: 16; rightPadding: 16; topPadding: 8; bottomPadding: 8
    implicitHeight: 36
    opacity: enabled ? 1 : 0.5
    hoverEnabled: true
    contentItem: Text {
        text: control.text
        color: control.primary || control.destructive ? "#ffffff" : (control.dark ? "#cccccc" : "#444444")
        font.pixelSize: 13; font.bold: control.primary || control.destructive
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: 6
        color: control.destructive ? "#c23838" : control.primary ? control.accent
            : control.down ? (control.dark ? "#333333" : "#dddddd")
            : control.hovered ? (control.dark ? "#333333" : "#dddddd") : (control.dark ? "#2a2a2a" : "#e8e8e8")
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? control.accent : control.destructive ? "#e65555"
            : control.primary ? control.accent : (control.dark ? "#444444" : "#cccccc")
    }
    HoverHandler { cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
