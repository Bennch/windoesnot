import QtQuick
import QtQuick.Controls
import "../i18n/Lang.js" as Lang

// Same dimensions, colors and states as existing Settings controls.
ComboBox {
    id: control
    property var settingsMenu: null
    property string labelPrefix: ""
    function valueLabel(value) { return labelPrefix ? Lang.get(labelPrefix + "." + String(value), settingsMenu ? settingsMenu.uiLanguage : "de") : String(value) }
    displayText: valueLabel(currentText)
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    height: 40
    opacity: enabled ? 1 : 0.5
    background: Rectangle {
        color: control.pressed ? (control.dark ? "#1a1a1a" : "#e0e0e0") : (control.dark ? "#2a2a2a" : "#f0f0f0")
        border.color: control.visualFocus ? control.accent : (control.dark ? "#3a3a3a" : "#d0d0d0")
        border.width: 1; radius: 6
    }
    contentItem: Text {
        leftPadding: 12; rightPadding: 32
        text: control.displayText; font.pixelSize: 13
        color: control.dark ? "#ffffff" : "#1a1a1a"
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
    indicator: Text {
        x: control.width - width - 12; anchors.verticalCenter: parent.verticalCenter
        text: "▼"; font.pixelSize: 10; color: control.dark ? "#999999" : "#666666"
    }
    popup: Popup {
        y: control.height + 2; width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + 2, 300); padding: 1
        contentItem: ListView {
            clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle { color: control.dark ? "#2a2a2a" : "#f0f0f0"; border.color: control.dark ? "#3a3a3a" : "#d0d0d0"; border.width: 1; radius: 6 }
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width - 2; height: 36
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: control.valueLabel(modelData); leftPadding: 12; font.pixelSize: 13
            color: parent.highlighted ? "#ffffff" : (control.dark ? "#ffffff" : "#1a1a1a")
            verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        background: Rectangle { color: parent.highlighted ? control.accent : parent.hovered ? (control.dark ? "#333333" : "#e5e5e5") : "transparent"; radius: 4 }
    }
}
