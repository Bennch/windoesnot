import QtQuick
import QtQuick.Effects
import Quickshell

Item {
    id: root
    property var snapManager
    property var settingsMenu: null

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: preview
            required property var modelData
            screen: modelData
            visible: false
            color: "transparent"
            exclusionMode: ExclusionMode.Ignore
            property string snapZone: "none"
            property rect snapRect: Qt.rect(0, 0, 0, 0)
            mask: Region { width: 0; height: 0 }
            anchors { top: true; bottom: true; left: true; right: true }

            Connections {
                target: root.snapManager
                function onPreviewChanged(zone, rect, screenName, monX, monY) {
                    if (screenName !== preview.modelData.name) {
                        preview.visible = false
                        return
                    }
                    preview.snapZone = zone
                    preview.snapRect = Qt.rect(rect.x - monX, rect.y - monY, rect.width, rect.height)
                    preview.visible = true
                }
                function onHidePreview() {
                    preview.visible = false
                    preview.snapZone = "none"
                }
            }

            Rectangle {
                x: preview.snapRect.x
                y: preview.snapRect.y
                width: preview.snapRect.width
                height: preview.snapRect.height
                visible: preview.snapZone !== "none"
                color: root.settingsMenu ? Qt.rgba(root.settingsMenu.accentColor.r, root.settingsMenu.accentColor.g, root.settingsMenu.accentColor.b, 0.25) : Qt.rgba(1, 0.44, 0.18, 0.25)
                border.color: root.settingsMenu ? root.settingsMenu.accentColor : "#fe6f2d"
                border.width: 2
                radius: 10
                Behavior on x { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
                Behavior on y { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
                Behavior on width { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
                Behavior on height { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: Qt.rgba(0, 0, 0, 0.3)
                    shadowBlur: 0.4
                    shadowHorizontalOffset: 0
                    shadowVerticalOffset: 4
                }
            }
        }
    }
}
