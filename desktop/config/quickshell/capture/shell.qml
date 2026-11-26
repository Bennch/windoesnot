//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env QT_QPA_PLATFORMTHEME=

// Capture overlay: screenshot and screen recording with one toolbar.
// Started on demand by `windoesnot-capture overlay` (capture.py), which first grabs the frozen picture and writes the
// monitor / window geometry next to it. Environment: WINDOESNOT_CAPTURE_TAB, WINDOESNOT_CAPTURE_IMAGE, WINDOESNOT_CAPTURE_DATA.
// The process ends when the capture is done, on Esc / X, or when a recording has stopped.

import "./components/"

import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    Scope {
        id: ctl

        // ---- state shown by the toolbar
        property string tab: Quickshell.env("WINDOESNOT_CAPTURE_TAB") === "record" ? "record" : "screenshot"
        property string mode: "region"           // region | window | screen
        property int delay: 0                    // 0, 3, 5 or 10 (allowlist in capture.py)
        property bool copy: true
        property bool pointer: false
        property bool audio: false
        property string openMenu: ""             // "", "delay" or "options"
        property string phase: "select"          // select | busy | countdown | recording
        property string lang: Qt.locale().name.indexOf("de") === 0 ? "de" : "en"
        property bool spaceHeld: false
        property int countdown: 0
        property int elapsed: 0

        // ---- snapshot (from capture.py)
        property bool ready: false
        property string imagePath: Quickshell.env("WINDOESNOT_CAPTURE_IMAGE") || ""
        property string dataPath: Quickshell.env("WINDOESNOT_CAPTURE_DATA") || ""
        property var monitors: []
        property var windows: []
        property real bx: 0
        property real by: 0
        property real scaleFactor: 1
        property string focusedName: ""
        property string pillMonitor: ""

        // ---- selection in global logical coordinates
        property bool hasSel: false
        property real selX: 0
        property real selY: 0
        property real selW: 0
        property real selH: 0
        property string selMonitor: ""
        property var selBounds: ({ x: 0, y: 0, w: 0, h: 0 })
        property real anchorX: 0
        property real anchorY: 0
        property real rl: 0
        property real rt: 0
        property real rr: 0
        property real rb: 0
        property int resizeDX: 0
        property int resizeDY: 0
        property var hoverWindow: null
        property string hoverMonitor: ""
        property string recordGeometry: ""
        property string recordOutput: ""

        // What the overlay highlights: the selection, else the hovered window / screen.
        readonly property var activeRect: {
            if (hasSel && selW >= 1 && selH >= 1) return { x: selX, y: selY, w: selW, h: selH }
            if (hasSel) return null
            if (mode === "window" && hoverWindow) return { x: hoverWindow.x, y: hoverWindow.y, w: hoverWindow.width, h: hoverWindow.height }
            if (mode === "screen" && hoverMonitor !== "") {
                var m = monitorByName(hoverMonitor)
                if (m) return { x: m.x, y: m.y, w: m.width, h: m.height }
            }
            return null
        }

        function monitorByName(name) {
            for (var i = 0; i < monitors.length; ++i)
                if (monitors[i].name === name) return monitors[i]
            return null
        }
        function windowAt(gx, gy) {
            for (var i = 0; i < windows.length; ++i) {
                var w = windows[i]
                if (gx >= w.x && gx < w.x + w.width && gy >= w.y && gy < w.y + w.height) return w
            }
            return null
        }
        function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

        function setMode(m) {
            console.log("[capture] mode " + m)
            mode = m
            hasSel = false
            selW = 0
            selH = 0
            selMonitor = ""
            hoverWindow = null
            hoverMonitor = ""
            openMenu = ""
        }

        // ---- region selection
        function beginRegion(gx, gy, mx, my, mw, mh) {
            if (spaceHeld && hasSel && selW >= 1) return           // Space + drag moves the existing selection
            selBounds = { x: mx, y: my, w: mw, h: mh }
            anchorX = clamp(gx, mx, mx + mw)
            anchorY = clamp(gy, my, my + mh)
            selX = anchorX
            selY = anchorY
            selW = 0
            selH = 0
            hasSel = true
            selMonitor = ""
        }
        function dragRegion(gx, gy) {
            var cx = clamp(gx, selBounds.x, selBounds.x + selBounds.w)
            var cy = clamp(gy, selBounds.y, selBounds.y + selBounds.h)
            selX = Math.min(anchorX, cx)
            selY = Math.min(anchorY, cy)
            selW = Math.abs(cx - anchorX)
            selH = Math.abs(cy - anchorY)
        }
        function moveRegion(dx, dy) {
            var nx = clamp(selX + dx, selBounds.x, selBounds.x + selBounds.w - selW)
            var ny = clamp(selY + dy, selBounds.y, selBounds.y + selBounds.h - selH)
            anchorX += nx - selX
            anchorY += ny - selY
            selX = nx
            selY = ny
        }
        function endRegion() {
            if (selW < 4 || selH < 4) {
                hasSel = false
                selW = 0
                selH = 0
            } else {
                console.log("[capture] region " + geometryString())
            }
        }
        function beginResize(dx, dy) {
            resizeDX = dx
            resizeDY = dy
            rl = selX
            rt = selY
            rr = selX + selW
            rb = selY + selH
        }
        function dragResize(gx, gy) {
            var cx = clamp(gx, selBounds.x, selBounds.x + selBounds.w)
            var cy = clamp(gy, selBounds.y, selBounds.y + selBounds.h)
            if (resizeDX < 0) rl = cx
            else if (resizeDX > 0) rr = cx
            if (resizeDY < 0) rt = cy
            else if (resizeDY > 0) rb = cy
            selX = Math.min(rl, rr)
            selY = Math.min(rt, rb)
            selW = Math.abs(rr - rl)
            selH = Math.abs(rb - rt)
        }

        // ---- window / screen picking
        function hoverAt(gx, gy, name) {
            if (mode === "window") hoverWindow = windowAt(gx, gy)
            else if (mode === "screen") hoverMonitor = name
        }
        function pickWindowAt(gx, gy) {
            var w = windowAt(gx, gy)
            if (!w) return
            selX = w.x
            selY = w.y
            selW = w.width
            selH = w.height
            selMonitor = ""
            hasSel = true
            console.log("[capture] window " + w.address + " " + w.title)
        }
        function pickMonitor(name) {
            var m = monitorByName(name)
            if (!m) return
            selX = m.x
            selY = m.y
            selW = m.width
            selH = m.height
            selMonitor = name
            hasSel = true
            console.log("[capture] screen " + name)
        }

        function geometryString() {
            var r = activeRect
            if (!r && mode === "screen") {
                var m = monitorByName(focusedName)
                if (m) r = { x: m.x, y: m.y, w: m.width, h: m.height }
            }
            if (!r || r.w < 1 || r.h < 1) return ""
            return Math.round(r.x) + "," + Math.round(r.y) + " " + Math.round(r.w) + "x" + Math.round(r.h)
        }

        // ---- actions
        function capture() {
            var geo = geometryString()
            if (geo === "") {
                console.log("[capture] nothing selected yet")
                return
            }
            openMenu = ""
            spaceHeld = false
            console.log("[capture] " + tab + " " + mode + " " + geo + " delay=" + delay)
            if (tab === "record") {
                recordGeometry = geo
                recordOutput = mode === "screen" ? (selMonitor !== "" ? selMonitor : focusedName) : ""
                pillMonitor = focusedName
                if (delay > 0) {
                    countdown = delay
                    phase = "countdown"
                    countdownTimer.start()
                } else {
                    phase = "busy"
                    startTimer.start()
                }
            } else {
                phase = "busy"
                var cmd = ["windoesnot-capture", "shoot", "--geometry", geo, "--snapshot", imagePath,
                           "--delay", String(delay), "--settle", "0.4"]
                if (copy) cmd.push("--copy")
                if (pointer) cmd.push("--pointer")
                shootProc.command = cmd
                shootProc.running = true
            }
        }
        function beginRecord() {
            var cmd = ["windoesnot-capture", "record-start"]
            if (recordOutput !== "") cmd.push("--output", recordOutput)
            else cmd.push("--geometry", recordGeometry)
            if (audio) cmd.push("--audio")
            console.log("[capture] " + cmd.join(" "))
            recStartProc.command = cmd
            recStartProc.running = true
        }
        function stopRecording() {
            console.log("[capture] stop recording")
            statusTimer.stop()
            recStopProc.running = true
        }
        function cancel() {
            console.log("[capture] cancelled")
            countdownTimer.stop()
            Qt.quit()
        }

        // ---- snapshot data written by capture.py
        FileView {
            id: dataFile
            path: ctl.dataPath
            onLoaded: {
                try {
                    var data = JSON.parse(text())
                    ctl.monitors = data.monitors
                    ctl.windows = data.windows
                    ctl.bx = data.bounds.x
                    ctl.by = data.bounds.y
                    ctl.scaleFactor = data.scale
                    for (var i = 0; i < data.monitors.length; ++i)
                        if (data.monitors[i].focused) ctl.focusedName = data.monitors[i].name
                    if (ctl.focusedName === "" && data.monitors.length > 0) ctl.focusedName = data.monitors[0].name
                    ctl.pillMonitor = ctl.focusedName
                    ctl.ready = true
                    console.log("[capture] ready: " + data.monitors.length + " monitors, " + data.windows.length + " windows, tab " + ctl.tab)
                } catch (e) {
                    console.log("[capture] bad snapshot data: " + e)
                    Qt.quit()
                }
            }
            onLoadFailed: {
                console.log("[capture] cannot read " + ctl.dataPath)
                Qt.quit()
            }
        }

        Timer {
            id: countdownTimer
            interval: 1000
            repeat: true
            onTriggered: {
                ctl.countdown -= 1
                if (ctl.countdown <= 0) {
                    stop()
                    ctl.phase = "busy"
                    startTimer.start()
                }
            }
        }
        // Gives the compositor a moment to remove the overlay before wf-recorder starts.
        Timer {
            id: startTimer
            interval: 400
            onTriggered: ctl.beginRecord()
        }
        Timer {
            id: statusTimer
            interval: 1000
            repeat: true
            onTriggered: statusProc.running = true
        }

        Process {
            id: shootProc
            running: false
            stdout: StdioCollector {
                onStreamFinished: console.log("[capture] saved " + this.text.trim())
            }
            stderr: StdioCollector {
                onStreamFinished: if (this.text.trim() !== "") console.log("[capture] shoot error: " + this.text.trim())
            }
            onExited: function(exitCode, exitStatus) {
                console.log("[capture] shoot finished, exit " + exitCode)
                Qt.quit()
            }
        }
        Process {
            id: recStartProc
            running: false
            stderr: StdioCollector {
                onStreamFinished: if (this.text.trim() !== "") console.log("[capture] record-start error: " + this.text.trim())
            }
            onExited: function(exitCode, exitStatus) {
                console.log("[capture] record-start exit " + exitCode)
                if (exitCode === 0) {
                    ctl.elapsed = 0
                    ctl.phase = "recording"
                    statusTimer.start()
                    statusProc.running = true
                } else {
                    Qt.quit()
                }
            }
        }
        Process {
            id: recStopProc
            command: ["windoesnot-capture", "record-stop"]
            running: false
            onExited: function(exitCode, exitStatus) {
                console.log("[capture] record-stop exit " + exitCode)
                Qt.quit()
            }
        }
        Process {
            id: statusProc
            command: ["windoesnot-capture", "record-status"]
            running: false
            stdout: StdioCollector {
                onStreamFinished: {
                    try {
                        var status = JSON.parse(this.text)
                        if (!status.recording) {
                            console.log("[capture] recording ended")
                            Qt.quit()
                        } else {
                            ctl.elapsed = Math.max(0, status.now - status.started)
                        }
                    } catch (e) {
                        console.log("[capture] bad status: " + e)
                    }
                }
            }
        }

        Variants {
            model: ctl.ready ? Quickshell.screens : []
            Scope {
                id: perScreen
                required property var modelData
                ScreenWindow { screen: perScreen.modelData; controller: ctl }
                RecordPill { screen: perScreen.modelData; controller: ctl }
            }
        }
    }
}
