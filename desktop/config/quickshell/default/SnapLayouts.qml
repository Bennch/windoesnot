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

    // Windows 11 layouts: two rows of three. x/w are fractions of the width, row/rows split a column vertically.
    readonly property var layoutModel: [
        { id: "halves", zones: [ { x: 0, w: 0.5, row: 0, rows: 1 }, { x: 0.5, w: 0.5, row: 0, rows: 1 } ] },
        { id: "wide-narrow", zones: [ { x: 0, w: 2 / 3, row: 0, rows: 1 }, { x: 2 / 3, w: 1 / 3, row: 0, rows: 1 } ] },
        { id: "thirds", zones: [ { x: 0, w: 1 / 3, row: 0, rows: 1 }, { x: 1 / 3, w: 1 / 3, row: 0, rows: 1 }, { x: 2 / 3, w: 1 / 3, row: 0, rows: 1 } ] },
        { id: "half-stack", zones: [ { x: 0, w: 0.5, row: 0, rows: 1 }, { x: 0.5, w: 0.5, row: 0, rows: 2 }, { x: 0.5, w: 0.5, row: 1, rows: 2 } ] },
        { id: "quarters", zones: [ { x: 0, w: 0.5, row: 0, rows: 2 }, { x: 0.5, w: 0.5, row: 0, rows: 2 }, { x: 0, w: 0.5, row: 1, rows: 2 }, { x: 0.5, w: 0.5, row: 1, rows: 2 } ] },
        { id: "narrow-wide-narrow", zones: [ { x: 0, w: 0.25, row: 0, rows: 1 }, { x: 0.25, w: 0.5, row: 0, rows: 1 }, { x: 0.75, w: 0.25, row: 0, rows: 1 } ] }
    ]

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

            // PanelWindow is not an Item, so the Escape handler lives on a focused item inside it.
            Item {
                anchors.fill: parent
                focus: true
                Keys.onEscapePressed: root.close()
            }

            MouseArea {
                anchors.fill: parent
                onClicked: root.close()
            }

            Rectangle {
                id: card
                readonly property bool dark: root.settingsMenu && root.settingsMenu.darkMode
                readonly property color accent: root.settingsMenu ? root.settingsMenu.accentColor : "#fe6f2d"
                anchors.centerIn: root.anchorX < 0 ? parent : undefined
                x: root.anchorX < 0 ? 0 : Math.max(8, Math.min(parent.width - width - 8, root.anchorX - modelData.x - width / 2))
                y: root.anchorY < 0 ? 0 : Math.max(8, Math.min(parent.height - height - 8, root.anchorY - modelData.y + 22))
                width: 3 * 96 + 4 * 12
                height: 2 * 62 + 3 * 12
                radius: 12
                color: dark ? "#f0252528" : "#f5f6f8"
                border.width: 1
                border.color: dark ? "#4a4a50" : "#c9ccd2"

                // Prevent the backdrop click handler from closing the picker.
                HoverHandler {
                    onHoveredChanged: {
                        root.menuHovered = hovered
                        if (hovered) closeTimer.stop()
                        else root.scheduleClose()
                    }
                }
                MouseArea { anchors.fill: parent; onClicked: function(mouse) { mouse.accepted = true } }

                // Six layouts, as in Windows 11: every zone is a clickable area of its own and lights up in the accent colour.
                // A zone is [column, columnShare, row, rowsInColumn].
                Grid {
                    x: 12; y: 12
                    columns: 3
                    spacing: 12

                    Repeater {
                        model: root.layoutModel

                        delegate: Rectangle {
                            id: tile
                            required property var modelData
                            width: 96; height: 62; radius: 8
                            color: card.dark ? "#2e2e33" : "#e3e5ea"
                            border.width: 1
                            border.color: tileHover.hovered ? Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.55) : "transparent"

                            HoverHandler { id: tileHover }

                            Repeater {
                                model: tile.modelData.zones

                                delegate: Rectangle {
                                    id: zone
                                    required property var modelData
                                    required property int index
                                    readonly property real pad: 6
                                    readonly property real gap: 3
                                    readonly property real innerW: tile.width - 2 * pad
                                    readonly property real innerH: tile.height - 2 * pad
                                    // modelData = { x, w, row, rows } with x/w as fractions of the width
                                    x: pad + modelData.x * innerW + (modelData.x > 0 ? gap / 2 : 0)
                                    width: modelData.w * innerW - ((modelData.x > 0 ? gap / 2 : 0) + (modelData.x + modelData.w < 0.999 ? gap / 2 : 0))
                                    y: pad + modelData.row * (innerH / modelData.rows) + (modelData.row > 0 ? gap / 2 : 0)
                                    height: innerH / modelData.rows - ((modelData.row > 0 ? gap / 2 : 0) + (modelData.row < modelData.rows - 1 ? gap / 2 : 0))
                                    radius: 3
                                    color: zoneMouse.containsMouse ? card.accent : (card.dark ? "#6a6a70" : "#a7acb5")

                                    MouseArea {
                                        id: zoneMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.choose(tile.modelData.id + ":" + zone.index)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
