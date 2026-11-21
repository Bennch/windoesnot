import QtQuick
import Quickshell
import Quickshell.Io
import "./i18n" as UiI

FloatingWindow {
    id: taskbarPreview
    visible: false
    color: "transparent"
    title: "quickshell-taskpreview"

    property var settingsMenu: null
    property var appWindows: []
    property string appName: ""
    property string appIcon: ""
    property bool appCustomIcon: false
    property int captureSession: 0
    property var previewPaths: ({})
    property var captureQueue: []
    property bool captureBusy: false
    // Last known picture per window: a hidden (minimized) window cannot be captured, so its card shows the last image taken
    // while it was visible (hover capture or the snapshot right before minimizing), dimmed, instead of a black box.
    property var lastKnown: ({})

    function rememberImage(address, path) {
        var known = Object.assign({}, taskbarPreview.lastKnown)
        known[address] = path
        taskbarPreview.lastKnown = known
    }

    // Shell snippet that takes the picture of a visible window just before it is minimized (and remembers it).
    function snapshotCommand(win) {
        if (!win || win.hidden || !win.size || win.size[0] <= 0 || win.size[1] <= 0) return ""
        var path = "/tmp/qs-preview-last-" + win.address + "-" + Date.now() + ".png"
        rememberImage(win.address, path)
        return "windoesnot-bounded 4 grim -s 1 -g '" + win.at[0] + "," + win.at[1] + " " + win.size[0] + "x" + win.size[1] + "' " + path + " 2>/dev/null; "
    }
    function snapshotCommandFor(address) {
        for (var i = 0; i < appWindows.length; i++) {
            if (appWindows[i].address === address) return snapshotCommand(appWindows[i])
        }
        return ""
    }

    function captureNext() {
        if (captureBusy || captureQueue.length === 0) return
        var item = captureQueue.shift()
        captureQueue = captureQueue
        if (item.session !== captureSession) { captureNext(); return }
        captureBusy = true
        var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', taskbarPreview)
        proc.command = ["windoesnot-bounded", "8", "grim", "-s", "1", "-g", item.geometry, item.path]
        proc.exited.connect(function(code) {
            if (item.session === taskbarPreview.captureSession && code === 0) {
                var paths = Object.assign({}, taskbarPreview.previewPaths)
                paths[item.address] = item.path
                taskbarPreview.previewPaths = paths
                taskbarPreview.rememberImage(item.address, item.path)
            }
            taskbarPreview.captureBusy = false
            proc.destroy()
            taskbarPreview.captureNext()
        })
        proc.running = true
    }

    // Set by the triggering icon in shell.qml
    property bool iconHovering: false
    property string _pendingX: "0"
    property string _pendingY: "0"

    // Stored for recalculation after close
    property int _lastIconCenterX: 0
    property int _lastMonW: screen ? screen.width : 1280
    property int _lastMonH: screen ? screen.height : 800

    readonly property int cardW:   185
    readonly property int cardH:   128
    readonly property int cardGap: 8
    readonly property int pad:     10

    implicitWidth:  pad * 2 + Math.max(1, appWindows.length) * cardW
                    + Math.max(0, appWindows.length - 1) * cardGap
    implicitHeight: pad * 2 + cardH

    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    // ── HoverHandler (non-consuming) ──────────────────────────────────────────
    HoverHandler {
        id: popupHover
        onHoveredChanged: {
            if (hovered) {
                hideTimer.stop()
            } else if (!taskbarPreview.iconHovering) {
                hideTimer.restart()
            }
        }
    }

    onIconHoveringChanged: {
        if (!iconHovering && visible) {
            iconLeaveTimer.restart()
        }
    }

    // ── Timers ────────────────────────────────────────────────────────────────

    Timer {
        id: showTimer
        interval: 380
        onTriggered: {
            if (!taskbarPreview.iconHovering || taskbarPreview.appWindows.length === 0)
                return
            var self = taskbarPreview
            var w = self.implicitWidth
            var h = self.implicitHeight
            var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', taskbarPreview)
            proc.command = ["windoesnot-bounded", "8", "bash", "-c",
                "windoesnot-hyprctl keyword 'windowrule[taskpreview-config]:size " + w + " " + h + "' ; " +
                "windoesnot-hyprctl keyword 'windowrule[taskpreview-config]:move " + self._pendingX + " " + self._pendingY + "'"]
            proc.exited.connect(function() {
                if (self.iconHovering)
                    self.visible = true
            })
            proc.running = true
        }
    }

    Timer {
        id: hideTimer
        interval: 280
        onTriggered: taskbarPreview.visible = false
    }


    // Bounce-guard: 300ms covers the Hyprland surface-map pointer bounce (< 50ms)
    // and gives the user time to move cursor from icon to popup.
    Timer {
        id: iconLeaveTimer
        interval: 300
        onTriggered: {
            if (!popupHover.hovered)
                hideTimer.restart()
        }
    }

    function prepareFor(name, wins, iconCenterX, monW, monH, icon, customIcon) {
        var self = taskbarPreview
        self.appName       = name
        self.appWindows    = wins
        self.appIcon       = icon || ""
        self.appCustomIcon = customIcon || false
        self.captureSession = self.captureSession + 1
        self.previewPaths   = {}
        self.captureQueue   = []
        self._lastIconCenterX = iconCenterX
        self._lastMonW        = monW
        self._lastMonH        = monH
        var session = self.captureSession

        for (var i = 0; i < wins.length; i++) {
            var win = wins[i]
            if (!win.hidden && win.size && win.size[0] > 0 && win.size[1] > 0) {
                var outFile = "/tmp/qs-preview-" + win.address + "-" + session + ".png"
                var geom = win.at[0] + "," + win.at[1] + " " + win.size[0] + "x" + win.size[1]
                self.captureQueue.push({address: win.address, path: outFile, geometry: geom, session: session})
            }
        }
        self.captureNext()

        var w = self.pad * 2 + wins.length * self.cardW + Math.max(0, wins.length - 1) * self.cardGap
        var h = self.pad * 2 + self.cardH
        self._pendingX = String(Math.max(4, Math.min(monW - w - 4, Math.round(iconCenterX - w / 2))))
        self._pendingY = String(monH - 45 - h)

        // If already visible (from a previous app), hide immediately so Hyprland
        // gets the new size before we show again — avoids the stale-size glitch.
        if (self.visible) self.visible = false

        showTimer.restart()
    }

    function cancelShow() { showTimer.stop() }
    function startHide()  { hideTimer.restart() }
    function cancelHide() { hideTimer.stop(); iconLeaveTimer.stop() }

    // ── Visual shell ──────────────────────────────────────────────────────────

    Rectangle {
        anchors.fill: parent
        topLeftRadius:     taskbarPreview.settingsMenu ? taskbarPreview.settingsMenu.borderRadius + 2 : 8
        topRightRadius:    taskbarPreview.settingsMenu ? taskbarPreview.settingsMenu.borderRadius + 2 : 8
        bottomLeftRadius:  0
        bottomRightRadius: 0
        color: taskbarPreview.settingsMenu
            ? (taskbarPreview.settingsMenu.darkMode
                ? Qt.rgba(0.10, 0.10, 0.10, 0.97)
                : Qt.rgba(0.97, 0.97, 0.97, 0.97))
            : "#1a1a1a"
        border.color: taskbarPreview.settingsMenu
            ? (taskbarPreview.settingsMenu.darkMode ? "#3a3a3a" : "#cccccc")
            : "#3a3a3a"
        border.width: 1

        Row {
            id: cardRow
            anchors {
                fill: parent
                margins: taskbarPreview.pad
            }
            spacing: taskbarPreview.cardGap

            // ── Delegate helpers (defined here so taskbarPreview is in scope) ──
            // Repeater delegates cannot access the FloatingWindow's id directly
            // due to Quickshell's proxy wrapping — so we call these instead.

            function minimizeCard(addr) {
                taskbarPreview.visible = false
                var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', cardRow)
                proc.command = ["windoesnot-bounded", "12", "bash", "-c", taskbarPreview.snapshotCommandFor(addr) +
                    "windoesnot-hyprctl dispatch movetoworkspacesilent special:minimized,address:" + addr]
                proc.running = true
            }

            function closeCard(addr) {
                var newWins = []
                for (var i = 0; i < taskbarPreview.appWindows.length; i++) {
                    if (taskbarPreview.appWindows[i].address !== addr)
                        newWins.push(taskbarPreview.appWindows[i])
                }
                // Close the window
                var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', cardRow)
                proc.command = ["windoesnot-bounded", "8", "windoesnot-hyprctl", "dispatch", "closewindow", "address:" + addr]
                proc.running = true
                // Update model and hide — re-hover will show correct size
                taskbarPreview.appWindows = newWins
                taskbarPreview.appName = ""   // allow prepareFor on next hover
                taskbarPreview.visible = false
            }

            function focusCard(addr, hidden, rws) {
                taskbarPreview.visible = false
                var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', cardRow)
                if (hidden) {
                    var target = (rws !== undefined && rws > 0) ? rws : -1
                    var moveCmd = target > 0
                        ? "windoesnot-hyprctl dispatch movetoworkspace " + target + ",address:" + addr
                        : "windoesnot-hyprctl dispatch movetoworkspace e+0,address:" + addr
                    var floatingRestore = taskbarPreview.settingsMenu &&
                                         taskbarPreview.settingsMenu.windowMode === "floating"
                    var suffix = floatingRestore ? " && windoesnot-hyprctl dispatch bringactivetotop" : ""
                    proc.command = ["windoesnot-bounded", "8", "bash", "-c",
                        moveCmd + " && windoesnot-hyprctl dispatch focuswindow address:" + addr + suffix]
                } else {
                    var floating = taskbarPreview.settingsMenu &&
                                   taskbarPreview.settingsMenu.windowMode === "floating"
                    if (floating) {
                        // Floating mode: focus and raise to front.
                        // Windows maximized via toggle-maximize.sh are regular floating windows
                        // (no fullscreen state), so bringactivetotop works correctly.
                        proc.command = ["windoesnot-bounded", "8", "bash", "-c",
                            "windoesnot-hyprctl dispatch focuswindow address:" + addr +
                            " && windoesnot-hyprctl dispatch bringactivetotop"]
                    } else {
                        proc.command = ["windoesnot-bounded", "8", "windoesnot-hyprctl", "dispatch", "focuswindow", "address:" + addr]
                    }
                }
                proc.running = true
            }

            Repeater {
                model: taskbarPreview.appWindows

                delegate: Rectangle {
                    id: card
                    width:  taskbarPreview.cardW
                    height: taskbarPreview.cardH
                    radius: 6
                    color: cardHover
                        ? (taskbarPreview.settingsMenu && taskbarPreview.settingsMenu.darkMode
                            ? Qt.rgba(1, 1, 1, 0.08)
                            : Qt.rgba(0, 0, 0, 0.06))
                        : "transparent"
                    border.width: modelData.focused ? 1 : 0
                    border.color: taskbarPreview.settingsMenu
                        ? taskbarPreview.settingsMenu.accentColor : "#0078d4"

                    property bool cardHover: false
                    Behavior on color { ColorAnimation { duration: 100 } }

                    // ── Header: Icon + Title + × ──────────────────────────────
                    Item {
                        id: cardHeader
                        anchors { top: parent.top; left: parent.left; right: parent.right }
                        height: 30

                        Image {
                            id: iconImg
                            anchors { left: parent.left; leftMargin: 7; verticalCenter: parent.verticalCenter }
                            width: 14; height: 14
                            source: taskbarPreview.appCustomIcon
                                ? Qt.resolvedUrl("img/" + taskbarPreview.appIcon + ".svg")
                                : ("image://icon/" + taskbarPreview.appIcon)
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }

                        Text {
                            anchors {
                                left: iconImg.right; leftMargin: 5
                                right: minimizeBtn.visible ? minimizeBtn.left : closeBtn.left; rightMargin: 4
                                verticalCenter: parent.verticalCenter
                            }
                            text: modelData.title || taskbarPreview.appName
                            font.pixelSize: UiI.UiScale.px(11)
                            font.bold: modelData.focused
                            color: taskbarPreview.settingsMenu
                                ? (taskbarPreview.settingsMenu.darkMode ? "#dddddd" : "#222222")
                                : "#dddddd"
                            elide: Text.ElideRight
                        }

                        Rectangle {
                            id: minimizeBtn
                            visible: !modelData.hidden
                            anchors { right: closeBtn.left; rightMargin: 2; verticalCenter: parent.verticalCenter }
                            width: 24; height: 24
                            radius: 5
                            color: minimizeBtnHover.hovered
                                ? (taskbarPreview.settingsMenu
                                    ? taskbarPreview.settingsMenu.accentColor : "#0078d4")
                                : "transparent"
                            Behavior on color { ColorAnimation { duration: 100 } }

                            HoverHandler { id: minimizeBtnHover }

                            Text {
                                anchors.centerIn: parent
                                text: "−"
                                font.pixelSize: UiI.UiScale.px(16)
                                color: minimizeBtnHover.hovered ? "#ffffff"
                                    : (taskbarPreview.settingsMenu
                                        ? (taskbarPreview.settingsMenu.darkMode ? "#888" : "#777")
                                        : "#888")
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: cardRow.minimizeCard(modelData.address)
                            }
                        }

                        Rectangle {
                            id: closeBtn
                            anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                            width: 24; height: 24
                            radius: 5
                            color: closeBtnHover.hovered
                                ? (taskbarPreview.settingsMenu
                                    ? taskbarPreview.settingsMenu.accentColor : "#0078d4")
                                : "transparent"
                            Behavior on color { ColorAnimation { duration: 100 } }

                            HoverHandler { id: closeBtnHover }

                            Text {
                                anchors.centerIn: parent
                                text: "✕"
                                font.pixelSize: UiI.UiScale.px(12)
                                color: closeBtnHover.hovered ? "#ffffff"
                                    : (taskbarPreview.settingsMenu
                                        ? (taskbarPreview.settingsMenu.darkMode ? "#888" : "#777")
                                        : "#888")
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: cardRow.closeCard(modelData.address)
                            }
                        }
                    }

                    // Thin separator
                    Rectangle {
                        id: headerSep
                        anchors { top: cardHeader.bottom; left: parent.left; right: parent.right
                                  leftMargin: 6; rightMargin: 6 }
                        height: 1
                        color: taskbarPreview.settingsMenu
                            ? (taskbarPreview.settingsMenu.darkMode ? "#2a2a2a" : "#e0e0e0")
                            : "#2a2a2a"
                    }

                    // ── Preview image with padding ────────────────────────────
                    Rectangle {
                        id: imgZone
                        anchors {
                            top: headerSep.bottom; left: parent.left; right: parent.right
                            bottom: parent.bottom; margins: 6
                        }
                        radius: 4
                        color: taskbarPreview.settingsMenu
                            ? (taskbarPreview.settingsMenu.darkMode ? "#0d0d0d" : "#d0d0d0")
                            : "#0d0d0d"
                        layer.enabled: true

                        Image {
                            id: cardImage
                            anchors.fill: parent
                            readonly property string lastImage: taskbarPreview.lastKnown[modelData.address] || ""
                            readonly property bool showsLast: modelData.hidden && lastImage !== ""
                            visible: (!modelData.hidden && modelData.size && modelData.size[0] > 0) || showsLast
                            source: modelData.hidden ? lastImage : (taskbarPreview.previewPaths[modelData.address] || "")
                            fillMode: Image.PreserveAspectCrop
                            cache: false
                            asynchronous: true
                            opacity: showsLast ? 0.5 : 1.0
                        }

                        // Badge on the dimmed last picture of a hidden window
                        Text {
                            visible: cardImage.showsLast
                            anchors { right: parent.right; bottom: parent.bottom; margins: 4 }
                            text: "⊟ " + (taskbarPreview.settingsMenu && taskbarPreview.settingsMenu.uiLanguage === "en" ? "Hidden" : "Ausgeblendet")
                            font.pixelSize: UiI.UiScale.px(9)
                            color: "#ffffff"
                            style: Text.Outline
                            styleColor: "#000000"
                        }

                        Column {
                            visible: (modelData.hidden && !cardImage.showsLast) || (!modelData.hidden && (!modelData.size || modelData.size[0] === 0))
                            anchors.centerIn: parent
                            spacing: 5

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "⊟"
                                font.pixelSize: UiI.UiScale.px(20)
                                color: taskbarPreview.settingsMenu
                                    ? (taskbarPreview.settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                                    : "#3a3a3a"
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: taskbarPreview.settingsMenu && taskbarPreview.settingsMenu.uiLanguage === "en"
                                    ? "Hidden" : "Ausgeblendet"
                                font.pixelSize: UiI.UiScale.px(9)
                                color: taskbarPreview.settingsMenu
                                    ? (taskbarPreview.settingsMenu.darkMode ? "#555" : "#999")
                                    : "#555"
                                visible: modelData.hidden
                            }
                        }
                    }

                    // ── Card-level click/hover (z:-1 so closeBtn stays on top) ──
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        z: -1

                        onEntered: card.cardHover = true
                        onExited:  card.cardHover = false
                        onClicked: cardRow.focusCard(modelData.address, modelData.hidden,
                                                     modelData.restoreWorkspace)
                    }
                }
            }
        }
    }
}
