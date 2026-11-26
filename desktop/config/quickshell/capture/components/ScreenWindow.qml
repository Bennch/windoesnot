import QtQuick
import Quickshell
import Quickshell.Wayland
import "Strings.js" as Strings

// One full-screen overlay window per monitor: the frozen picture, dimmed, with the selection on top.
// All coordinates the controller keeps are global logical (Hyprland layout) coordinates; this window adds its own origin.
PanelWindow {
    id: win

    property var controller: null
    readonly property var ctl: controller
    readonly property real ox: screen ? screen.x : 0
    readonly property real oy: screen ? screen.y : 0
    readonly property string screenName: screen ? screen.name : ""
    readonly property bool isFocusedMonitor: ctl !== null && ctl.focusedName === screenName
    readonly property var ar: ctl ? ctl.activeRect : null
    readonly property bool hasAr: ar !== null && ar !== undefined
    readonly property real rx: hasAr ? ar.x - ox : 0
    readonly property real ry: hasAr ? ar.y - oy : 0
    readonly property real rw: hasAr ? ar.w : 0
    readonly property real rh: hasAr ? ar.h : 0
    readonly property bool editable: ctl !== null && ctl.hasSel && ctl.mode === "region"

    function tr(key, arg) { return Strings.t(key, ctl ? ctl.lang : "en", arg) }

    visible: ctl !== null && ctl.phase === "select"
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    anchors { top: true; bottom: true; left: true; right: true }
    WlrLayershell.namespace: "quickshell-capture"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: isFocusedMonitor ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

    Item {
        id: root
        anchors.fill: parent
        focus: true

        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Escape) {
                if (win.ctl.openMenu !== "") win.ctl.openMenu = ""
                else win.ctl.cancel()
                event.accepted = true
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                win.ctl.capture()
                event.accepted = true
            } else if (event.key === Qt.Key_Space) {
                if (!event.isAutoRepeat) win.ctl.spaceHeld = true
                event.accepted = true
            }
        }
        Keys.onReleased: function(event) {
            if (event.key === Qt.Key_Space && !event.isAutoRepeat) {
                win.ctl.spaceHeld = false
                event.accepted = true
            }
        }

        // The frozen screen, cut to this monitor
        Image {
            anchors.fill: parent
            source: win.ctl && win.ctl.imagePath !== "" ? "file://" + win.ctl.imagePath : ""
            cache: false
            asynchronous: false
            fillMode: Image.Stretch
            sourceClipRect: win.ctl ? Qt.rect((win.ox - win.ctl.bx) * win.ctl.scaleFactor, (win.oy - win.ctl.by) * win.ctl.scaleFactor,
                                              win.width * win.ctl.scaleFactor, win.height * win.ctl.scaleFactor) : Qt.rect(0, 0, 0, 0)
        }

        // Dimming around the selection (everything when nothing is selected)
        Rectangle { visible: !win.hasAr; anchors.fill: parent; color: CaptureTheme.dim }
        Rectangle { visible: win.hasAr; x: 0; y: 0; width: root.width; height: Math.max(0, win.ry); color: CaptureTheme.dim }
        Rectangle { visible: win.hasAr; x: 0; y: win.ry + win.rh; width: root.width; height: Math.max(0, root.height - win.ry - win.rh); color: CaptureTheme.dim }
        Rectangle { visible: win.hasAr; x: 0; y: win.ry; width: Math.max(0, win.rx); height: win.rh; color: CaptureTheme.dim }
        Rectangle { visible: win.hasAr; x: win.rx + win.rw; y: win.ry; width: Math.max(0, root.width - win.rx - win.rw); height: win.rh; color: CaptureTheme.dim }

        // Background mouse handling: select a region, pick a window or a screen
        MouseArea {
            id: surface
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            property real lastX: 0
            property real lastY: 0
            property bool dragging: false

            onPressed: function(mouse) {
                win.ctl.openMenu = ""
                root.forceActiveFocus()
                var gx = mouse.x + win.ox
                var gy = mouse.y + win.oy
                if (win.ctl.mode === "region") {
                    win.ctl.beginRegion(gx, gy, win.ox, win.oy, win.width, win.height)
                    lastX = gx
                    lastY = gy
                    dragging = true
                }
            }
            onPositionChanged: function(mouse) {
                var gx = mouse.x + win.ox
                var gy = mouse.y + win.oy
                if (dragging && win.ctl.mode === "region") {
                    if (win.ctl.spaceHeld) win.ctl.moveRegion(gx - lastX, gy - lastY)
                    else win.ctl.dragRegion(gx, gy)
                    lastX = gx
                    lastY = gy
                } else if (!pressed) {
                    win.ctl.hoverAt(gx, gy, win.screenName)
                }
            }
            onReleased: function(mouse) {
                var gx = mouse.x + win.ox
                var gy = mouse.y + win.oy
                if (win.ctl.mode === "region") {
                    dragging = false
                    win.ctl.endRegion()
                } else if (win.ctl.mode === "window") {
                    win.ctl.pickWindowAt(gx, gy)
                } else if (win.ctl.mode === "screen") {
                    win.ctl.pickMonitor(win.screenName)
                }
            }
        }

        // Selection frame
        Rectangle {
            visible: win.hasAr
            x: win.rx
            y: win.ry
            width: win.rw
            height: win.rh
            color: "transparent"
            border.width: 2
            border.color: CaptureTheme.accentColor
        }

        // Resize handles (region mode, after a selection exists)
        Repeater {
            model: win.editable && win.hasAr ? 8 : 0
            Rectangle {
                id: handle
                required property int index
                // direction of the edges this handle moves: -1 left/top, 0 none, 1 right/bottom
                readonly property int dx: [-1, 0, 1, -1, 1, -1, 0, 1][index]
                readonly property int dy: [-1, -1, -1, 0, 0, 1, 1, 1][index]
                width: 12
                height: 12
                radius: 6
                x: win.rx + (dx < 0 ? 0 : dx === 0 ? win.rw / 2 : win.rw) - width / 2
                y: win.ry + (dy < 0 ? 0 : dy === 0 ? win.rh / 2 : win.rh) - height / 2
                color: "#ffffff"
                border.width: 2
                border.color: CaptureTheme.accentColor

                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: handle.dx === 0 ? Qt.SizeVerCursor : handle.dy === 0 ? Qt.SizeHorCursor
                                 : (handle.dx === handle.dy ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor)
                    onPressed: function(mouse) { win.ctl.beginResize(handle.dx, handle.dy) }
                    onPositionChanged: function(mouse) {
                        if (!pressed) return
                        var p = mapToItem(root, mouse.x, mouse.y)
                        win.ctl.dragResize(p.x + win.ox, p.y + win.oy)
                    }
                }
            }
        }

        // Live size label
        Rectangle {
            visible: win.hasAr && win.rw >= 1
            width: sizeText.implicitWidth + 20
            height: 28
            radius: Math.min(14, CaptureTheme.borderRadius + 4)
            color: CaptureTheme.panel
            border.width: 1
            border.color: CaptureTheme.panelBorder
            x: Math.max(8, Math.min(root.width - width - 8, win.rx + win.rw / 2 - width / 2))
            y: (win.ry + win.rh + 18 + height < root.height) ? win.ry + win.rh + 18 : Math.max(8, win.ry - height - 12)
            Text {
                id: sizeText
                anchors.centerIn: parent
                text: Math.round(win.rw) + " × " + Math.round(win.rh)
                font.pixelSize: 13
                color: CaptureTheme.text
            }
        }

        // Toolbar and hint on the focused monitor
        CaptureToolbar {
            id: toolbar
            visible: win.isFocusedMonitor
            controller: win.ctl
            x: (root.width - width) / 2
            y: 24
            z: 5
        }
        Rectangle {
            visible: win.isFocusedMonitor
            width: hintText.implicitWidth + 28
            height: 28
            radius: Math.min(14, CaptureTheme.borderRadius + 4)
            color: CaptureTheme.panel
            x: (root.width - width) / 2
            y: 24 + 52 + 8
            Text {
                id: hintText
                anchors.centerIn: parent
                text: win.ctl ? win.tr("hint." + win.ctl.mode, win.tr(win.ctl.tab === "record" ? "verb.record" : "verb.capture")) : ""
                font.pixelSize: 12
                color: CaptureTheme.mutedText
            }
        }
    }
}
