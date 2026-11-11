import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland

// Keyboard-accessible snap picker.  It deliberately lives in the layer shell:
// it is an overlay, never a normal client that can itself be tiled or snapped.
Scope {
    id: root

    property var snapManager: null
    property var settingsMenu: null
    property bool opened: false
    property string targetMonitor: ""
    property int anchorX: -1
    property int anchorY: -1
    property bool menuHovered: false

    function openOn(monitorName, x, y) {
        targetMonitor = monitorName || ""
        anchorX = x === undefined ? -1 : x
        anchorY = y === undefined ? -1 : y
        opened = true
    }

    function close() {
        opened = false
        menuHovered = false
        closeTimer.stop()
    }

    function scheduleClose() {
        if (opened && !menuHovered)
            closeTimer.restart()
    }

    Timer {
        id: closeTimer
        interval: 260
        repeat: false
        onTriggered: {
            if (!root.menuHovered)
                root.close()
        }
    }

    function choose(layout) {
        if (snapManager)
            snapManager.applyKeyboardLayout(layout)
        close()
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: overlay
            required property var modelData
            screen: modelData
            visible: root.opened && (!root.targetMonitor || root.targetMonitor === modelData.name)
            color: "transparent"
            exclusionMode: ExclusionMode.Ignore
            anchors { top: true; bottom: true; left: true; right: true }
            WlrLayershell.namespace: "quickshell-snap-layouts"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

            Keys.onEscapePressed: root.close()

            MouseArea {
                anchors.fill: parent
                onClicked: root.close()
            }

            Rectangle {
                id: card
                anchors.centerIn: root.anchorX < 0 ? parent : undefined
                x: root.anchorX < 0 ? 0 : Math.max(8, Math.min(parent.width - width - 8, root.anchorX - modelData.x - width + 28))
                y: root.anchorY < 0 ? 0 : Math.max(8, Math.min(parent.height - height - 8, root.anchorY - modelData.y + 18))
                width: 424
                height: 232
                radius: 14
                color: root.settingsMenu && root.settingsMenu.darkMode ? "#e91c1d20" : "#f5f6f8"
                border.width: 1
                border.color: root.settingsMenu ? Qt.rgba(root.settingsMenu.accentColor.r, root.settingsMenu.accentColor.g, root.settingsMenu.accentColor.b, 0.7) : "#fe6f2d"

                // Prevent the backdrop click handler from closing the picker.
                HoverHandler {
                    onHoveredChanged: {
                        root.menuHovered = hovered
                        if (hovered) closeTimer.stop()
                        else root.scheduleClose()
                    }
                }
                MouseArea { anchors.fill: parent; onClicked: function(mouse) { mouse.accepted = true } }

                Text {
                    id: heading
                    x: 20; y: 16
                    text: "Fenster anordnen"
                    color: root.settingsMenu && root.settingsMenu.darkMode ? "#f4f4f4" : "#202124"
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }
                Text {
                    x: 20; y: 42
                    text: "Super + Z  ·  Esc zum Schließen"
                    color: root.settingsMenu && root.settingsMenu.darkMode ? "#b7b7b7" : "#62666d"
                    font.pixelSize: 12
                }

                Grid {
                    x: 20; y: 74
                    columns: 4
                    spacing: 10

                    Repeater {
                        model: [
                            { id: "left", label: "Linke Hälfte" },
                            { id: "right", label: "Rechte Hälfte" },
                            { id: "third-left", label: "Linkes Drittel" },
                            { id: "third-right", label: "Rechtes Drittel" },
                            { id: "top-left", label: "Oben links" },
                            { id: "top-right", label: "Oben rechts" },
                            { id: "bottom-left", label: "Unten links" },
                            { id: "bottom-right", label: "Unten rechts" }
                        ]

                        delegate: Rectangle {
                            required property var modelData
                            readonly property string layoutId: modelData.id
                            width: 88; height: 58; radius: 8
                            color: layoutMouse.containsMouse
                                   ? (root.settingsMenu ? root.settingsMenu.accentColor : "#fe6f2d")
                                   : (root.settingsMenu && root.settingsMenu.darkMode ? "#292a2e" : "#e5e7eb")
                            border.width: 1
                            border.color: layoutMouse.containsMouse ? color : (root.settingsMenu && root.settingsMenu.darkMode ? "#45464b" : "#c9ccd2")

                            Rectangle {
                                anchors.centerIn: parent
                                width: 32; height: 26; radius: 3
                                color: "transparent"
                                border.width: 1
                                border.color: layoutMouse.containsMouse ? "white" : (root.settingsMenu && root.settingsMenu.darkMode ? "#d9d9d9" : "#44474e")
                                Rectangle {
                                    readonly property string layout: parent.parent.layoutId
                                    x: (layout === "right" || layout === "third-right" || layout === "top-right" || layout === "bottom-right") ? parent.width / 2 : 0
                                    y: (layout === "bottom-left" || layout === "bottom-right") ? parent.height / 2 : 0
                                    width: (layout.indexOf("third") === 0) ? parent.width / 3 : parent.width / 2
                                    height: (layout.indexOf("top-") === 0 || layout.indexOf("bottom-") === 0) ? parent.height / 2 : parent.height
                                    color: layoutMouse.containsMouse ? "white" : (root.settingsMenu ? root.settingsMenu.accentColor : "#fe6f2d")
                                    opacity: 0.9
                                }
                            }
                            ToolTip { visible: layoutMouse.containsMouse; text: parent.modelData.label }
                            MouseArea {
                                id: layoutMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: root.choose(parent.modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }
}
