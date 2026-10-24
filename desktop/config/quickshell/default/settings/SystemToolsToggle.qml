import QtQuick
import QtQuick.Controls
import "../i18n/Lang.js" as Lang

// Same dimensions, colors and states as existing Settings controls.
Switch {
    id: control
    property var settingsMenu: null
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    implicitHeight: 40; spacing: 12; padding: 0
    opacity: enabled ? 1 : 0.5
    indicator: Rectangle {
        x: 0; anchors.verticalCenter: parent.verticalCenter
        width: 50; height: 26; radius: 13
        color: control.checked ? control.accent : (control.dark ? "#4a4a4a" : "#cccccc")
        border.color: control.visualFocus ? control.accent : "transparent"; border.width: 2
        Rectangle {
            width: 20; height: 20; radius: 10
            x: control.checked ? 27 : 3; y: 3; color: "#ffffff"
            Behavior on x { NumberAnimation { duration: 150 } }
        }
    }
    contentItem: Text {
        text: control.text; leftPadding: 62; font.pixelSize: 13
        color: control.dark ? "#ffffff" : "#1a1a1a"; verticalAlignment: Text.AlignVCenter
    }
    HoverHandler { cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
