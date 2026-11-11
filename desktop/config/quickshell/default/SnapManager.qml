import "DisplayGeometry.js" as DisplayGeometry
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

// Snap Manager - handles window snapping logic and edge detection
Item {
    id: snapManager

    // External reference to settings
    property var settingsMenu: null

    signal previewChanged(string zone, rect rect, string screenName, int monX, int monY)
    signal hidePreview()

    property rect previewRect: Qt.rect(0, 0, 0, 0)

    property bool enabled: settingsMenu && settingsMenu.windowMode === "floating"
    property bool isDragging: false
    property string currentZone: "none"
    property string currentMonitorName: ""   // which monitor currently shows the preview
    property var draggedWindow: null
    property var activeWindowAddress: null
    property var dragStartMonitor: null
    property rect pendingSnapRect: Qt.rect(0, 0, 0, 0)
    property string pendingSnapZone: "none"
    property var currentSnapResult: null     // Full result from calculateSnapZone (zone+rect+displayRect+usable+monitorName)
    property var pendingSnapInfo: null       // Snap info passed to snapWindowProc for snap-group registration

    // Snap group tracking: addr (no 0x) → { zone, monitorName, usableX/Y/W/H, halfW/halfH, gapInner, lastX/Y/W/H }
    property var snapMembers: ({})

    // Cooldown after a snap: ignore hyprdrag-movestart for ~400ms so the cursor
    // pressing against the bottom edge/taskbar doesn't immediately re-grab the window.
    property bool snapCooldown: false

    Timer {
        id: snapCooldownTimer
        interval: 600
        running: false
        repeat: false
        onTriggered: snapManager.snapCooldown = false
    }

    // Latest snapshot of all floating clients — updated by snapGroupQueryProc every 300 ms.
    // Used by calculateSnapZone to detect manually-positioned adjacent windows.
    property var cachedClients: null

    // Edge detection thresholds (pixels from screen edge)
    property int edgeThreshold: 30       // left/right/bottom edges
    property int topEdgeThreshold: 60    // top edge: larger because notification bar is in the way
    property int cornerThreshold: 200

    // Cached data for processing
    property var cachedCursorPos: null
    property var cachedWindowInfo: null
    property var cachedMonitors: null    // kept current so movestop can check zone instantly
    property var lastWindowPos: null
    property var lastCursorPos: null
    property int unchangedCount: 0
    property int cursorUnchangedCount: 0
    property int zoneStableCount: 0  // Track how long zone has been stable

    // Safety timer: if a drag has been active for >8 s without movestop, force-reset.
    // This prevents isDragging from getting permanently stuck (which makes blockHover
    // stick at true, hiding the TopNotificationBar trigger zone indefinitely).
    Timer {
        id: dragSafetyTimer
        interval: 8000
        running: false
        repeat: false
        onTriggered: {
            if (snapManager.isDragging) {
                console.log("Drag safety timeout — resetting stuck isDragging")
                snapManager.isDragging = false
                dragPollTimer.running = false
                snapManager.hidePreview()
                snapManager.currentZone = "none"
                snapManager.currentMonitorName = ""
                snapManager.currentSnapResult = null
                snapManager.activeWindowAddress = null
                snapManager.lastCursorPos = null
                snapManager.lastWindowPos = null
                snapManager.cursorUnchangedCount = 0
                snapManager.unchangedCount = 0
            }
        }
    }

    // Delay timer for snap execution (allows Hyprland to clean up grab state)
    Timer {
        id: snapDelayTimer
        interval: 50  // 50ms delay
        running: false
        repeat: false
        onTriggered: {
            if (snapManager.pendingSnapZone !== "none") {
                console.log("Executing delayed snap to zone:", snapManager.pendingSnapZone);
                snapWindowProc.running = true;
            }
        }
    }

    // hyprdrag plugin events for TRUE mouse release detection
    Connections {
        target: Hyprland
        function onRawEvent(ev) {
            var name = "" + ev.name;
            var data = ("" + ev.data).trim();

            // Only handle events if snapping is enabled (floating mode)
            if (!snapManager.enabled) {
                return;
            }

            if (name === "hyprdrag-movestart") {
                if (snapManager.snapCooldown) {
                    console.log("Drag start ignored (snap cooldown active)");
                    return;
                }
                console.log("Drag started:", data, "enabled:", snapManager.enabled);
                snapManager.isDragging = true;
                snapManager.activeWindowAddress = data;
                snapManager.dragStartMonitor = null;
                snapManager.unchangedCount = 0;
                snapManager.zoneStableCount = 0;
                snapManager.lastWindowPos = null;  // Reset position tracking
                dragPollTimer.running = true;  // Start polling for preview updates only
                dragSafetyTimer.restart();     // Safety: force-reset if movestop never fires
            } else if (name === "hyprdrag-movestop") {
                console.log("Drag stopped:", data);
                // Normalize addresses for comparison (remove 0x prefix)
                var normalizedData = data.replace(/^0x/, "")
                var normalizedActive = snapManager.activeWindowAddress ?
                    snapManager.activeWindowAddress.replace(/^0x/, "") : null

                if (normalizedActive && normalizedActive === normalizedData) {
                    snapManager.isDragging = false;
                    dragPollTimer.running = false;
                    dragSafetyTimer.stop();

                    // If no zone yet (poll may not have fired in time), do an immediate
                    // synchronous zone check using the last cached cursor + monitor data.
                    if (snapManager.currentZone === "none" &&
                            snapManager.cachedCursorPos && snapManager.cachedMonitors) {
                        var cx = snapManager.cachedCursorPos.x
                        var cy = snapManager.cachedCursorPos.y
                        for (var mi = 0; mi < snapManager.cachedMonitors.length; mi++) {
                            var m = snapManager.cachedMonitors[mi]
                            var mw = (m.transform === 1 || m.transform === 3) ? m.height : m.width
                            var mh = (m.transform === 1 || m.transform === 3) ? m.width  : m.height
                            if (cx >= m.x && cx < m.x + mw && cy >= m.y && cy < m.y + mh) {
                                var finalResult = snapManager.calculateSnapZone(cx, cy, m, snapManager.cachedMonitors)
                                if (finalResult.zone !== "none") {
                                    snapManager.currentZone = finalResult.zone
                                    snapManager.previewRect  = finalResult.rect
                                    snapManager.currentSnapResult = {
                                        zone: finalResult.zone,
                                        rect: finalResult.rect,
                                        displayRect: finalResult.displayRect,
                                        usable: finalResult.usable,
                                        monitorName: m.name
                                    }
                                    console.log("Final zone check on movestop:", finalResult.zone)
                                }
                                break
                            }
                        }
                    }

                    // Snap if we have an active zone (with small delay for Hyprland cleanup)
                    if (snapManager.currentZone !== "none") {
                        snapManager.pendingSnapZone = snapManager.currentZone;
                        snapManager.pendingSnapRect = snapManager.previewRect;
                        snapManager.pendingSnapInfo = snapManager.currentSnapResult;
                        snapManager.hidePreview();
                        snapManager.currentZone = "none";
                        console.log("Preparing snap to zone:", snapManager.pendingSnapZone);
                        // Start cooldown immediately — hyprdrag-movestart can fire before
                        // snapWindowProc finishes (cursor bounce at bottom edge / taskbar).
                        snapManager.snapCooldown = true;
                        snapCooldownTimer.restart();
                        snapDelayTimer.start();
                    } else {
                        snapManager.hidePreview();
                        snapManager.pendingSnapZone = "none";
                        snapManager.pendingSnapInfo = null;
                    }

                    // Clean up
                    snapManager.activeWindowAddress = null;
                    snapManager.dragStartMonitor = null;
                    snapManager.lastCursorPos = null;
                    snapManager.lastWindowPos = null;
                    snapManager.unchangedCount = 0;
                    snapManager.zoneStableCount = 0;
                    snapManager.currentMonitorName = "";
                    snapManager.currentSnapResult = null;
                }
            }
        }
    }

    // Poll mouse position and window state continuously for snap preview
    Timer {
        id: dragPollTimer
        interval: 100  // 10 FPS for preview (lighter on system)
        running: false
        repeat: true

        onTriggered: {
            snapManager.updateSnapPreview()
        }
    }


    // Update snap preview based on cursor position
    function updateSnapPreview() {
        activeWindowProc.running = true
    }

    Process {
        id: activeWindowProc
        command: ["bash", "-c", "windoesnot-hyprctl activewindow -j; echo '---SEPARATOR---'; windoesnot-hyprctl cursorpos -j"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var parts = this.text.trim().split("---SEPARATOR---")
                    if (parts.length < 2) return

                    var windowInfo = JSON.parse(parts[0].trim())
                    var cursorPos = JSON.parse(parts[1].trim())

                    snapManager.cachedWindowInfo = windowInfo
                    snapManager.cachedCursorPos = cursorPos

                    // Check if window is floating
                    if (!windowInfo.floating) {
                        dragPollTimer.running = false
                        if (snapManager.currentZone !== "none") {
                            snapManager.hidePreview()
                            snapManager.currentZone = "none"
                            snapManager.zoneStableCount = 0
                        }
                        return
                    }

                    // Check if window position is changing (being dragged)
                    var currentPos = {x: windowInfo.at[0], y: windowInfo.at[1]}
                    var addr = windowInfo.address

                    // Normalize addresses: remove "0x" prefix for comparison
                    var normalizedAddr = addr.replace(/^0x/, "")
                    var normalizedActive = snapManager.activeWindowAddress ?
                        snapManager.activeWindowAddress.replace(/^0x/, "") : null

                    // Skip if not the active drag window (set by hyprdrag movestart)
                    if (normalizedActive && normalizedActive !== normalizedAddr) {
                        return
                    }

                    // Initialize position tracking if needed
                    if (!snapManager.lastWindowPos) {
                        snapManager.lastWindowPos = currentPos
                        snapManager.unchangedCount = 0
                    }

                    // Check cursor movement
                    if (!snapManager.lastCursorPos ||
                        snapManager.lastCursorPos.x !== cursorPos.x ||
                        snapManager.lastCursorPos.y !== cursorPos.y) {
                        snapManager.lastCursorPos = cursorPos
                        snapManager.cursorUnchangedCount = 0
                    } else {
                        snapManager.cursorUnchangedCount++
                    }

                    // Track window movement
                    if (snapManager.lastWindowPos.x !== currentPos.x ||
                        snapManager.lastWindowPos.y !== currentPos.y) {
                        snapManager.lastWindowPos = currentPos
                        snapManager.unchangedCount = 0
                    } else {
                        snapManager.unchangedCount++
                    }

                    // Fallback: hyprdrag-movestop sometimes requires cursor movement to fire.
                    // If cursor has been stationary for 600 ms while drag is active, treat
                    // it as a drop — the user almost certainly released the mouse button.
                    if (snapManager.isDragging && snapManager.cursorUnchangedCount >= 6) {
                        snapManager.isDragging = false
                        dragPollTimer.running = false

                        // Final zone check with cached data (same logic as movestop handler)
                        if (snapManager.currentZone === "none" &&
                                snapManager.cachedCursorPos && snapManager.cachedMonitors) {
                            var fx = snapManager.cachedCursorPos.x
                            var fy = snapManager.cachedCursorPos.y
                            for (var fi = 0; fi < snapManager.cachedMonitors.length; fi++) {
                                var fm = snapManager.cachedMonitors[fi]
                                var fmw = (fm.transform===1||fm.transform===3) ? fm.height : fm.width
                                var fmh = (fm.transform===1||fm.transform===3) ? fm.width  : fm.height
                                if (fx >= fm.x && fx < fm.x + fmw && fy >= fm.y && fy < fm.y + fmh) {
                                    var fr = snapManager.calculateSnapZone(fx, fy, fm, snapManager.cachedMonitors)
                                    if (fr.zone !== "none") {
                                        snapManager.currentZone = fr.zone
                                        snapManager.previewRect  = fr.rect
                                        snapManager.currentSnapResult = {
                                            zone: fr.zone,
                                            rect: fr.rect,
                                            displayRect: fr.displayRect,
                                            usable: fr.usable,
                                            monitorName: fm.name
                                        }
                                    }
                                    break
                                }
                            }
                        }

                        if (snapManager.currentZone !== "none") {
                            snapManager.pendingSnapZone = snapManager.currentZone
                            snapManager.pendingSnapRect = snapManager.previewRect
                            snapManager.pendingSnapInfo = snapManager.currentSnapResult
                            snapManager.hidePreview()
                            snapManager.currentZone = "none"
                            snapManager.currentMonitorName = ""
                            snapManager.snapCooldown = true
                            snapCooldownTimer.restart()
                            snapDelayTimer.start()
                        } else {
                            snapManager.hidePreview()
                            snapManager.pendingSnapZone = "none"
                            snapManager.pendingSnapInfo = null
                        }

                        snapManager.activeWindowAddress = null
                        snapManager.lastCursorPos = null
                        snapManager.lastWindowPos = null
                        snapManager.cursorUnchangedCount = 0
                        snapManager.unchangedCount = 0
                        snapManager.zoneStableCount = 0
                        snapManager.currentMonitorName = ""
                        snapManager.currentSnapResult = null
                        dragSafetyTimer.stop()
                        return
                    }

                    // Second fallback: window stopped moving but cursor IS moving.
                    // During a real drag, cursor movement always moves the window.
                    // If the window has been stationary for 500 ms while the cursor
                    // is actively moving, the user almost certainly released the mouse.
                    if (snapManager.isDragging &&
                            snapManager.unchangedCount >= 5 &&
                            snapManager.cursorUnchangedCount === 0) {
                        console.log("Window-stopped-but-cursor-moving fallback: ending drag")
                        snapManager.isDragging = false
                        dragPollTimer.running = false
                        dragSafetyTimer.stop()
                        snapManager.hidePreview()
                        snapManager.currentZone = "none"
                        snapManager.currentMonitorName = ""
                        snapManager.currentSnapResult = null
                        snapManager.pendingSnapZone = "none"
                        snapManager.pendingSnapInfo = null
                        snapManager.activeWindowAddress = null
                        snapManager.lastCursorPos = null
                        snapManager.lastWindowPos = null
                        snapManager.cursorUnchangedCount = 0
                        snapManager.unchangedCount = 0
                        snapManager.zoneStableCount = 0
                        return
                    }

                    // Normal poll: update zone preview while dragging
                    if (dragPollTimer.running && snapManager.isDragging) {
                        monitorQueryProc.running = true
                    }

                } catch (e) {
                    // Window might be closed or invalid
                    if (snapManager.currentZone !== "none") {
                        snapManager.hidePreview()
                        snapManager.currentZone = "none"
                        snapManager.zoneStableCount = 0
                    }
                }
            }
        }
    }

    Process {
        id: monitorQueryProc
        command: ["bash", "-c", "windoesnot-hyprctl monitors -j"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var monitors = JSON.parse(this.text).map(DisplayGeometry.normalize)
                    if (!snapManager.cachedCursorPos || monitors.length === 0) return
                    snapManager.cachedMonitors = monitors

                    var cursorX = snapManager.cachedCursorPos.x
                    var cursorY = snapManager.cachedCursorPos.y

                    // Determine monitor based on CURSOR position (allows multi-monitor snapping)
                    var targetMonitor = null

                    for (var i = 0; i < monitors.length; i++) {
                        var mon = monitors[i]
                        var monWidth = mon.width
                        var monHeight = mon.height

                        if (mon.transform === 1 || mon.transform === 3) {
                            monWidth = mon.height
                            monHeight = mon.width
                        }

                        if (cursorX >= mon.x && cursorX < mon.x + monWidth &&
                            cursorY >= mon.y && cursorY < mon.y + monHeight) {
                            targetMonitor = mon
                            break
                        }
                    }

                    if (!targetMonitor) return

                    // Abort if drag ended while this query was in flight (prevents phantom previews)
                    if (!snapManager.isDragging) {
                        snapManager.hidePreview()
                        return
                    }

                    // Calculate snap zone using cursor position
                    var result = snapManager.calculateSnapZone(cursorX, cursorY, targetMonitor, monitors)

                    var monitorChanged = targetMonitor.name !== snapManager.currentMonitorName
                    var zoneChanged    = result.zone !== snapManager.currentZone

                    if (!zoneChanged && !monitorChanged) {
                        if (result.zone !== "none") {
                            snapManager.zoneStableCount++
                        }
                    } else {
                        snapManager.zoneStableCount = (result.zone === "none") ? 0 : 1

                        if (result.zone === "none") {
                            snapManager.currentZone = "none"
                            snapManager.currentMonitorName = ""
                            snapManager.currentSnapResult = null
                            snapManager.hidePreview()
                            snapManager.previewRect = Qt.rect(0, 0, 0, 0)
                        } else {
                            // Hide old monitor's preview first to avoid two-monitor ghost
                            if (monitorChanged && snapManager.currentZone !== "none") {
                                snapManager.hidePreview()
                            }
                            snapManager.currentZone = result.zone
                            snapManager.currentMonitorName = targetMonitor.name
                            snapManager.previewRect = result.rect
                            snapManager.currentSnapResult = {
                                zone: result.zone,
                                rect: result.rect,
                                displayRect: result.displayRect,
                                usable: result.usable,
                                monitorName: targetMonitor.name
                            }
                            // Send displayRect so the preview starts at the title-bar position
                            snapManager.previewChanged(result.zone, result.displayRect, targetMonitor.name, targetMonitor.x, targetMonitor.y)
                        }
                    }


                } catch (e) {
                    console.log("Error in monitorQueryProc:", e);
                    dragPollTimer.running = false
                    snapManager.isDragging = false
                    snapManager.hidePreview()
                    snapManager.currentZone = "none"
                    snapManager.activeWindowAddress = null
                    snapManager.dragStartMonitor = null
                    snapManager.zoneStableCount = 0
                }
            }
        }
    }

    // Calculate snap zone based on cursor position and monitor
    function calculateSnapZone(cursorX, cursorY, monitor, allMonitors) {
        var x = monitor.x
        var y = monitor.y
        var w = monitor.width
        var h = monitor.height

        var transform = monitor.transform || 0
        if (transform === 1 || transform === 3) {
            var temp = w
            w = h
            h = temp
        }

        // Mirror hyprland.conf: gaps_out = 15, 8, 8, 8 (top, right, bottom, left)
        var gapOuter = 8
        var gapInner = 8
        var gapTop   = 15

        // hyprbars renders its title bar ABOVE the window's content area (above at.y),
        // so we must add this to usableY to keep the title bar on-screen.
        var hyprbarsHeight = (snapManager.settingsMenu && snapManager.settingsMenu.hyprbarsHeight > 0)
                             ? snapManager.settingsMenu.hyprbarsHeight : 30

        // Layer-shell reservations follow whichever monitor hosts the taskbar.
        var reserved = monitor.reserved || [0, 0, 0, 0]
        var taskbarHeight = reserved[3] || 0

        // usableY is the content position (at.y as reported by windoesnot-hyprctl).
        var usableX = x + reserved[0] + gapOuter
        var usableY = y + reserved[1] + gapTop + hyprbarsHeight
        var usableW = w - reserved[0] - reserved[2] - 2 * gapOuter
        var usableH = h - reserved[1] - gapTop - hyprbarsHeight - gapOuter - taskbarHeight

        var distLeft   = cursorX - x
        var distRight  = (x + w) - cursorX
        var distTop    = cursorY - y
        var distBottom = (y + h) - cursorY

        var isNearLeft   = distLeft   >= 0 && distLeft   < edgeThreshold
        var isNearRight  = distRight  >= 0 && distRight  < edgeThreshold
        var isNearTop    = distTop    >= 0 && distTop    < topEdgeThreshold
        var isNearBottom = distBottom >= 0 && distBottom < edgeThreshold

        var isInTopLeftCorner     = distLeft  < cornerThreshold && distTop    < cornerThreshold
        var isInTopRightCorner    = distRight < cornerThreshold && distTop    < cornerThreshold
        var isInBottomLeftCorner  = distLeft  < cornerThreshold && distBottom < cornerThreshold
        var isInBottomRightCorner = distRight < cornerThreshold && distBottom < cornerThreshold

        var halfW = (usableW - gapInner) / 2
        var halfH = (usableH - gapInner) / 2

        var usable = { x: usableX, y: usableY, w: usableW, h: usableH,
                       halfW: halfW, halfH: halfH, gapInner: gapInner }

        // Helper: build result with snap rect (content pos) + display rect (title-bar pos)
        function makeResult(zone, rx, ry, rw, rh) {
            return {
                zone: zone,
                rect: Qt.rect(rx, ry, rw, rh),
                displayRect: Qt.rect(rx, ry - hyprbarsHeight, rw, rh + hyprbarsHeight),
                usable: usable
            }
        }

        // Corners (quarter screen)
        if (isNearTop && isNearLeft && isInTopLeftCorner)
            return makeResult("top-left", usableX, usableY, halfW, halfH)
        if (isNearTop && isNearRight && isInTopRightCorner)
            return makeResult("top-right", usableX + halfW + gapInner, usableY, halfW, halfH)
        if (isNearBottom && isNearLeft && isInBottomLeftCorner)
            return makeResult("bottom-left", usableX, usableY + halfH + gapInner, halfW, halfH)
        if (isNearBottom && isNearRight && isInBottomRightCorner)
            return makeResult("bottom-right", usableX + halfW + gapInner, usableY + halfH + gapInner, halfW, halfH)

        // Edges (half/full screen)
        if (isNearTop)
            return makeResult("maximize", usableX, usableY, usableW, usableH)

        if (isNearLeft) {
            var leftW = halfW
            var dragAddr = snapManager.activeWindowAddress ?
                           snapManager.activeWindowAddress.replace(/^0x/, "") : null

            // 1. Prefer tracked snap-group partner
            var membs = snapManager.snapMembers
            if (membs) {
                for (var pa in membs) {
                    var pm = membs[pa]
                    if (pm.monitorName === monitor.name && pm.zone === "right" && pa !== dragAddr) {
                        var adj = pm.lastX - gapInner - usableX
                        if (adj > 150) { leftW = adj; break }
                    }
                }
            }

            // 2. Fallback: scan cachedClients for a manually-positioned right-side window.
            // Anchor on cursor position: any floating window whose left edge is to the
            // right of the cursor is a valid "right partner" for a left snap.
            if (leftW === halfW && snapManager.cachedClients) {
                var bestLeft = Infinity   // want the leftmost right-side window
                for (var ci2 = 0; ci2 < snapManager.cachedClients.length; ci2++) {
                    var cc = snapManager.cachedClients[ci2]
                    if (!cc.floating) continue
                    if (cc.address.replace(/^0x/, "") === dragAddr) continue
                    // Must be on this monitor
                    if (cc.at[0] < x || cc.at[0] >= x + w || cc.at[1] < y || cc.at[1] >= y + h) continue
                    // Left edge must be to the right of the cursor and window must have reasonable size
                    if (cc.at[0] > cursorX && cc.size[0] >= usableW * 0.1) {
                        if (cc.at[0] < bestLeft) bestLeft = cc.at[0]
                    }
                }
                if (bestLeft < Infinity) {
                    var adjFb = bestLeft - gapInner - usableX
                    if (adjFb > 150) leftW = adjFb
                }
            }
            return makeResult("left", usableX, usableY, leftW, usableH)
        }

        if (isNearRight) {
            var rightX = usableX + halfW + gapInner
            var rightW = halfW
            var dragAddr2 = snapManager.activeWindowAddress ?
                            snapManager.activeWindowAddress.replace(/^0x/, "") : null

            // 1. Prefer tracked snap-group partner
            var membs2 = snapManager.snapMembers
            if (membs2) {
                for (var pb in membs2) {
                    var pm2 = membs2[pb]
                    if (pm2.monitorName === monitor.name && pm2.zone === "left" && pb !== dragAddr2) {
                        var adjX = pm2.lastX + pm2.lastW + gapInner
                        var adjW = usableX + usableW - adjX
                        if (adjW > 150) { rightX = adjX; rightW = adjW; break }
                    }
                }
            }

            // 2. Fallback: scan cachedClients for a manually-positioned left-side window.
            // Anchor on cursor position: any floating window whose right edge is to the
            // left of the cursor is a valid "left partner" for a right snap.
            if (rightX === usableX + halfW + gapInner && snapManager.cachedClients) {
                var bestRight = -1   // want the rightmost left-side window
                for (var ci3 = 0; ci3 < snapManager.cachedClients.length; ci3++) {
                    var cc2 = snapManager.cachedClients[ci3]
                    if (!cc2.floating) continue
                    if (cc2.address.replace(/^0x/, "") === dragAddr2) continue
                    if (cc2.at[0] < x || cc2.at[0] >= x + w || cc2.at[1] < y || cc2.at[1] >= y + h) continue
                    var cc2Right = cc2.at[0] + cc2.size[0]
                    // Right edge must be to the left of the cursor and window must have reasonable size
                    if (cc2Right < cursorX && cc2.size[0] >= usableW * 0.1) {
                        if (cc2Right > bestRight) bestRight = cc2Right
                    }
                }
                if (bestRight > 0) {
                    var adjRx = bestRight + gapInner
                    var adjRw = usableX + usableW - adjRx
                    if (adjRw > 150) { rightX = adjRx; rightW = adjRw }
                }
            }
            return makeResult("right", rightX, usableY, rightW, usableH)
        }

        return { zone: "none", rect: Qt.rect(0, 0, 0, 0), displayRect: Qt.rect(0, 0, 0, 0), usable: usable }
    }


    // Snap window to the pending position/size
    Process {
        id: snapWindowProc
        command: ["bash", "-c", generateSnapCommand()]
        running: false

        function generateSnapCommand() {
            if (snapManager.pendingSnapZone === "none" || !snapManager.cachedWindowInfo) {
                return "echo 'no snap'";
            }

            var addr = snapManager.cachedWindowInfo.address;
            var r = snapManager.pendingSnapRect;

            var x = Math.round(r.x);
            var y = Math.round(r.y);
            var w = Math.round(r.width);
            var h = Math.round(r.height);

            var cmds = [];

            if (!snapManager.cachedWindowInfo.floating) {
                cmds.push("windoesnot-hyprctl dispatch togglefloating address:" + addr);
            }

            // Resize first, then move twice (corrects drift from center-anchored resize)
            cmds.push("windoesnot-hyprctl dispatch resizewindowpixel 'exact " + w + " " + h + ",address:" + addr + "'");
            cmds.push("windoesnot-hyprctl dispatch movewindowpixel 'exact " + x + " " + y + ",address:" + addr + "'");
            cmds.push("windoesnot-hyprctl dispatch movewindowpixel 'exact " + x + " " + y + ",address:" + addr + "'");

            // Auto-adjust any overlapping floating window on the same monitor.
            // This makes the "Mitte" snap useful: if a window is already present on
            // the other side, it gets resized to fill the remaining space automatically.
            var info = snapManager.pendingSnapInfo
            var zone = snapManager.pendingSnapZone
            if (info && info.usable && snapManager.cachedClients &&
                    (zone === "left" || zone === "right")) {
                var uX  = info.usable.x, uY  = info.usable.y
                var uW  = info.usable.w, uH  = info.usable.h
                var gap = info.usable.gapInner
                var normAddr = addr.replace(/^0x/, "")

                for (var ci = 0; ci < snapManager.cachedClients.length; ci++) {
                    var oc = snapManager.cachedClients[ci]
                    if (!oc.floating) continue
                    if (oc.address.replace(/^0x/, "") === normAddr) continue

                    var ox = oc.at[0], oy = oc.at[1], ow = oc.size[0], oh = oc.size[1]
                    var newOX, newOW, newOY, newOH

                    if (zone === "left") {
                        if (oc.at[0] < uX - 50 || oc.at[0] >= uX + uW + 50) continue
                        var snapRight = x + w + gap
                        if (ox < snapRight && ox + ow > x && ow >= uW * 0.1) {
                            newOX = snapRight; newOW = uX + uW - newOX
                        }
                    } else if (zone === "right") {
                        if (oc.at[0] < uX - 50 || oc.at[0] >= uX + uW + 50) continue
                        var snapLeft = x - gap
                        if (ox + ow > snapLeft && ox < x + w && ow >= uW * 0.1) {
                            newOX = uX; newOW = snapLeft - uX
                        }
                    }

                    if (newOX !== undefined && newOW > 150) {
                        cmds.push("windoesnot-hyprctl dispatch resizewindowpixel 'exact " +
                                  Math.round(newOW) + " " + Math.round(uH) +
                                  ",address:" + oc.address + "'")
                        cmds.push("windoesnot-hyprctl dispatch movewindowpixel 'exact " +
                                  Math.round(newOX) + " " + Math.round(uY) +
                                  ",address:" + oc.address + "'")
                    }
                }
            }

            var cmd = cmds.join(" && ");
            console.log("Snap CMD:", cmd);
            return cmd;
        }

        stdout: StdioCollector {
            onStreamFinished: {
                console.log("Snap result:", this.text.trim());

                // Register snapped window in snap-group tracker (left/right pairs)
                var zone = snapManager.pendingSnapZone
                var info = snapManager.pendingSnapInfo
                var cw   = snapManager.cachedWindowInfo

                if (cw) {
                    var normAddr = cw.address.replace(/^0x/, "")
                    var members  = snapManager.snapMembers

                    // Always remove old entry for this address (zone may have changed)
                    delete members[normAddr]

                    if (zone !== "none" && info && info.usable &&
                            (zone === "left" || zone === "right")) {
                        var r = info.rect   // snap rect = content position
                        members[normAddr] = {
                            zone:        zone,
                            monitorName: info.monitorName,
                            usableX:     info.usable.x,
                            usableY:     info.usable.y,
                            usableW:     info.usable.w,
                            usableH:     info.usable.h,
                            halfW:       info.usable.halfW,
                            halfH:       info.usable.halfH,
                            gapInner:    info.usable.gapInner,
                            lastX: r.x, lastY: r.y,
                            lastW: r.width, lastH: r.height
                        }
                        snapManager.snapMembers = members
                    } else {
                        snapManager.snapMembers = members
                    }
                }

                snapManager.pendingSnapZone = "none";
                snapManager.pendingSnapInfo = null;
            }
        }
    }

    // ── Snap Group Resize (Windows 11 style: drag shared border → both resize) ──

    Timer {
        id: snapGroupTimer
        // 300 ms is fine: group-resize and auto-detection don't need sub-frame precision.
        // We run whenever snap is enabled (floating mode) so manually-positioned adjacent
        // windows are detected even before any snap has happened.
        interval: 300
        running: snapManager.enabled
        repeat: true
        onTriggered: {
            if (!snapGroupQueryProc.running && !snapGroupAdjustProc.running) {
                snapGroupQueryProc.running = true
            }
        }
    }

    Process {
        id: snapGroupQueryProc
        command: ["bash", "-c", "windoesnot-hyprctl clients -j; echo '---MONSEP---'; windoesnot-hyprctl monitors -j"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var parts = this.text.split("---MONSEP---")
                    var clients  = JSON.parse(parts[0].trim())
                    var monitors = parts.length > 1 ? JSON.parse(parts[1].trim()).map(DisplayGeometry.normalize) : (snapManager.cachedMonitors || [])

                    // Keep client list fresh for calculateSnapZone adjacent-window detection
                    snapManager.cachedClients = clients

                    var members = snapManager.snapMembers

                    // ── Auto-detect manually-positioned adjacent pairs ─────────────────────
                    // Two floating windows on the same monitor whose horizontal edges are
                    // within 60 px of each other are treated as a left/right snap group.
                    var adjacencyTolerance = 60
                    var hbHeight = (snapManager.settingsMenu && snapManager.settingsMenu.hyprbarsHeight > 0)
                                   ? snapManager.settingsMenu.hyprbarsHeight : 30

                    // Build monitor lookup (window at[0]/at[1] → monitor)
                    function monitorForWindow(wx, wy) {
                        for (var mi = 0; mi < monitors.length; mi++) {
                            var mon = monitors[mi]
                            var mw = (mon.transform===1||mon.transform===3) ? mon.height : mon.width
                            var mh = (mon.transform===1||mon.transform===3) ? mon.width  : mon.height
                            if (wx >= mon.x && wx < mon.x + mw && wy >= mon.y && wy < mon.y + mh)
                                return mon
                        }
                        return null
                    }

                    var floatingClients = clients.filter(function(c) { return c.floating })

                    for (var ai = 0; ai < floatingClients.length; ai++) {
                        var ca = floatingClients[ai]
                        var caAddr = ca.address.replace(/^0x/, "")
                        var caRight  = ca.at[0] + ca.size[0]
                        var caBottom = ca.at[1] + ca.size[1]

                        for (var bi = 0; bi < floatingClients.length; bi++) {
                            if (ai === bi) continue
                            var cb = floatingClients[bi]
                            var cbAddr = cb.address.replace(/^0x/, "")

                            // ── Horizontal pair (left / right) ────────────────────────────
                            if (Math.abs(caRight - cb.at[0]) <= adjacencyTolerance &&
                                    Math.abs(ca.size[1] - cb.size[1]) <= 200) {
                                if (!(members[caAddr] && members[caAddr].zone === "left" &&
                                      members[cbAddr] && members[cbAddr].zone === "right")) {
                                    var mon = monitorForWindow(ca.at[0], ca.at[1])
                                    if (mon) {
                                        var reserved = mon.reserved || [0, 0, 0, 0]
                                        var taskH = reserved[3] || 0
                                        var uX = mon.x + reserved[0] + 8, uY = mon.y + reserved[1] + 15 + hbHeight
                                        var uW = mon.width - reserved[0] - reserved[2] - 16
                                        var uH = mon.height - reserved[1] - 15 - hbHeight - 8 - taskH
                                        if (ca.size[0] >= uW * 0.15 && cb.size[0] >= uW * 0.15) {
                                            members[caAddr] = { zone: "left",  monitorName: mon.name,
                                                usableX: uX, usableY: uY, usableW: uW, usableH: uH,
                                                halfW: (uW-8)/2, halfH: (uH-8)/2, gapInner: 8,
                                                lastX: ca.at[0], lastY: ca.at[1], lastW: ca.size[0], lastH: ca.size[1] }
                                            members[cbAddr] = { zone: "right", monitorName: mon.name,
                                                usableX: uX, usableY: uY, usableW: uW, usableH: uH,
                                                halfW: (uW-8)/2, halfH: (uH-8)/2, gapInner: 8,
                                                lastX: cb.at[0], lastY: cb.at[1], lastW: cb.size[0], lastH: cb.size[1] }
                                        }
                                    }
                                }
                            }

                        }
                    }
                    // ─────────────────────────────────────────────────────────────────────

                    // Build lookup: normalised address → client
                    var clientMap = {}
                    for (var ci = 0; ci < clients.length; ci++) {
                        var na = clients[ci].address.replace(/^0x/, "")
                        clientMap[na] = clients[ci]
                    }

                    var membersChanged = false
                    var adjustPairs    = []

                    for (var addr in members) {
                        var member = members[addr]
                        var client = clientMap[addr]

                        // Remove if window closed or no longer floating
                        if (!client || !client.floating) {
                            delete members[addr]
                            membersChanged = true
                            continue
                        }

                        var cx = client.at[0],   cy = client.at[1]
                        var cw = client.size[0],  ch = client.size[1]

                        // If window moved far from snap position, user repositioned it
                        if (Math.abs(cx - member.lastX) > 150 || Math.abs(cy - member.lastY) > 150) {
                            delete members[addr]
                            membersChanged = true
                            continue
                        }

                        // If width or height changed, adjust the partner to fill remaining space
                        if (cw !== member.lastW || ch !== member.lastH) {
                            var partnerAddr = null
                            var partner     = null
                            for (var pa in members) {
                                if (pa === addr) continue
                                var pm = members[pa]
                                if (pm.monitorName === member.monitorName &&
                                        ((member.zone === "left"  && pm.zone === "right") ||
                                         (member.zone === "right" && pm.zone === "left"))) {
                                    partnerAddr = pa
                                    partner     = pm
                                    break
                                }
                            }

                            if (partner && partnerAddr) {
                                var newPartnerX, newPartnerW, newPartnerY, newPartnerH
                                if (member.zone === "left") {
                                    newPartnerX = cx + cw + member.gapInner
                                    newPartnerW = member.usableX + member.usableW - newPartnerX
                                } else if (member.zone === "right") {
                                    newPartnerX = member.usableX
                                    newPartnerW = cx - member.gapInner - member.usableX
                                }

                                if (newPartnerW !== undefined && newPartnerW > 100) {
                                    adjustPairs.push({
                                        addr: "0x" + partnerAddr,
                                        x: newPartnerX, y: member.usableY,
                                        w: newPartnerW, h: member.usableH
                                    })
                                    members[partnerAddr].lastX = newPartnerX
                                    members[partnerAddr].lastW = newPartnerW
                                    membersChanged = true
                                }
                            }

                            // Update current member's last known state
                            member.lastX = cx
                            member.lastY = cy
                            member.lastW = cw
                            member.lastH = ch
                            membersChanged = true
                        }
                    }

                    if (membersChanged) {
                        snapManager.snapMembers = members
                    }

                    if (adjustPairs.length > 0) {
                        snapGroupAdjustProc.adjustData = adjustPairs
                        snapGroupAdjustProc.running = true
                    }

                } catch (e) {
                    console.log("snapGroupQuery error:", e)
                }
            }
        }
    }

    Process {
        id: snapGroupAdjustProc
        property var adjustData: []
        command: ["bash", "-c", buildAdjustCmd()]
        running: false

        function buildAdjustCmd() {
            if (!adjustData || adjustData.length === 0) return "echo 'no-op'"
            var cmds = []
            for (var i = 0; i < adjustData.length; i++) {
                var d = adjustData[i]
                var x = Math.round(d.x), y = Math.round(d.y)
                var w = Math.round(d.w), h = Math.round(d.h)
                cmds.push("windoesnot-hyprctl dispatch resizewindowpixel 'exact " + w + " " + h + ",address:" + d.addr + "'")
                cmds.push("windoesnot-hyprctl dispatch movewindowpixel 'exact " + x + " " + y + ",address:" + d.addr + "'")
            }
            return cmds.join(" && ")
        }

        stdout: StdioCollector {
            onStreamFinished: { /* done */ }
        }
    }
}
