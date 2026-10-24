import QtQuick
import QtQuick.Controls
import "." as Tools
import "../i18n/Lang.js" as Lang

// Same dimensions, colors and states as existing Settings controls.
Popup {
    id: dialog
    property var settingsMenu: null
    property string title: ""
    property string description: ""
    property string confirmText: ""
    property bool destructive: false
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property string language: settingsMenu ? settingsMenu.uiLanguage : "de"
    signal accepted()
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(500, parent ? parent.width - 32 : 500)
    height: Math.min(body.implicitHeight + 40, parent ? parent.height - 32 : 600)
    padding: 20; modal: true; focus: true
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { radius: dialog.settingsMenu ? dialog.settingsMenu.borderRadius : 10; color: dialog.dark ? "#222222" : "#ffffff"; border.width: 1; border.color: dialog.dark ? "#444444" : "#cccccc" }
    contentItem: Flickable {
        contentWidth: width; contentHeight: body.implicitHeight; clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: body; width: parent.width; spacing: 20
            Text { width: parent.width; text: dialog.title; font.pixelSize: 18; font.bold: true; wrapMode: Text.WordWrap; color: dialog.dark ? "#ffffff" : "#1a1a1a" }
            Text { width: parent.width; text: dialog.description; font.pixelSize: 13; wrapMode: Text.Wrap; textFormat: Text.PlainText; color: dialog.dark ? "#cccccc" : "#444444" }
            Flow {
                width: parent.width; spacing: 10
                Tools.SystemToolsButton { settingsMenu: dialog.settingsMenu; text: Lang.get("common.cancel", dialog.language); onClicked: dialog.close() }
                Tools.SystemToolsButton {
                    settingsMenu: dialog.settingsMenu; primary: !dialog.destructive; destructive: dialog.destructive
                    text: dialog.confirmText || Lang.get("systemTools.apply", dialog.language)
                    onClicked: { dialog.close(); dialog.accepted() }
                }
            }
        }
        ScrollIndicator.vertical: ScrollIndicator {}
    }
}
