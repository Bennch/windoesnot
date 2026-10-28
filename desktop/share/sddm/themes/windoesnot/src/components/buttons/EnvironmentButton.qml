// qmllint disable unqualified
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import SddmComponents 2.0 as SDDM

ComboBox {
    id: environmentSelector
    Layout.alignment: Qt.AlignHCenter
    Layout.preferredHeight: root.height / 15
    Layout.maximumHeight: root.height / 15
    implicitWidth: parent.width / 2
    activeFocusOnTab: true
    model: sessionModel
    currentIndex: model.lastIndex
    textRole: "name"
    padding: 0
    hoverEnabled: true
    indicator: null

    SDDM.TextConstants { id: textConstants }
    contentItem: Text {
        text: root.systemLocale.text("session") + " (" + environmentSelector.currentText + ")"
        color: environmentSelector.activeFocus || environmentSelector.hovered
            ? config.HoverEnvironmentButtonTextColor : config.EnvironmentButtonTextColor
        font.pointSize: root.font.pointSize * 0.9
        font.family: root.font.family
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        color: "transparent"
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            height: environmentSelector.visualFocus ? 2 : 0
            color: config.HoverEnvironmentButtonTextColor
        }
    }
    popup: Popup {
        y: -implicitHeight
        width: environmentSelector.width
        implicitHeight: Math.min(contentItem.implicitHeight + 20, root.height / 3)
        padding: 10
        background: Rectangle {
            radius: 12
            color: config.DropdownBackgroundColor
        }
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: environmentSelector.popup.visible ? environmentSelector.delegateModel : null
            currentIndex: environmentSelector.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
    delegate: ItemDelegate {
        required property string name
        required property int index
        width: environmentSelector.width - 20
        highlighted: environmentSelector.highlightedIndex === index
        contentItem: Text {
            text: name
            font.pointSize: root.font.pointSize * 0.8
            font.family: root.font.family
            color: config.DropdownTextColor
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 4
            color: parent.highlighted ? config.DropdownSelectedBackgroundColor : "transparent"
        }
    }
}
