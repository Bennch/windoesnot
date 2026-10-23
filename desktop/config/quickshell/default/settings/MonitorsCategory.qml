import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    id: monitorsCategory
    spacing: 0
    width: parent ? parent.width : 640

    property var settingsMenu: null
    property string uiLanguage: settingsMenu ? settingsMenu.uiLanguage : "de"
    property string accentColor: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
    property bool darkMode: settingsMenu ? settingsMenu.darkMode : true

    // Monitor state
    property var monitors: []
    property int selectedIndex: -1
    property bool isApplying: false
    property bool hasChanges: false
    property var monitorWallpapers: ({})

    // Working copies (edited values before Apply)
    property var editedMonitors: []

    Component.onCompleted: {
        loadMonitors()
        wallpaperLoader.running = true
    }

    // ─── Load monitors from windoesnot-hyprctl ───────────────────────────────────────────
    Process {
        id: loadProc
        command: ["bash", "-c", "windoesnot-hyprctl monitors -j all"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var raw = JSON.parse(this.text)
                    var result = []
                    for (var i = 0; i < raw.length; i++) {
                        var m = raw[i]
                        var modes = []
                        if (m.availableModes) {
                            for (var j = 0; j < m.availableModes.length; j++) {
                                modes.push(m.availableModes[j])
                            }
                        }
                        result.push({
                            name:        m.name,
                            description: m.description || m.name,
                            width:       m.width,
                            height:      m.height,
                            x:           m.x,
                            y:           m.y,
                            scale:       m.scale,
                            transform:   m.transform,
                            refreshRate: m.refreshRate,
                            disabled:    m.disabled || false,
                            modes:       modes
                        })
                    }
                    monitorsCategory.monitors = result
                    var edited = []
                    for (var k = 0; k < result.length; k++) {
                        edited.push(JSON.parse(JSON.stringify(result[k])))
                    }
                    monitorsCategory.editedMonitors = edited
                    if (result.length > 0) monitorsCategory.selectedIndex = 0
                } catch(e) {
                    console.log("Error parsing monitor JSON:", e)
                }
            }
        }
    }

    function loadMonitors() {
        loadProc.running = true
    }

    // ─── Wallpaper loader ─────────────────────────────────────────────────────
    Process {
        id: wallpaperLoader
        command: ["bash", "-c",
            "awk '/wallpaper/{b=1} b&&/monitor/{m=$3} b&&/path/{p=$3} b&&/}/{if(m&&p)print m\"|\"p;b=0;m=\"\";p=\"\"}' \"$HOME\"/.config/hypr/hyprpaper.conf"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var result = {}
                var lines = this.text.trim().split("\n")
                for (var i = 0; i < lines.length; i++) {
                    var sep = lines[i].indexOf("|")
                    if (sep > 0)
                        result[lines[i].substring(0, sep)] = lines[i].substring(sep + 1)
                }
                monitorsCategory.monitorWallpapers = result
            }
        }
    }

    // ─── Auto cursor alignment ────────────────────────────────────────────────
    // Center-aligns all monitors vertically relative to primary.
    // Result: cursor at 50% height on any monitor → 50% on adjacent monitor.
    function autoAlignCursors() {
        if (editedMonitors.length <= 1) return
        var primary = null
        for (var i = 0; i < editedMonitors.length; i++) {
            if (settingsMenu && editedMonitors[i].name === settingsMenu.primaryMonitor) {
                primary = editedMonitors[i]; break
            }
        }
        if (!primary) primary = editedMonitors[0]
        var primaryCenterY = primary.y + effectiveHeight(primary) / 2
        var copy = JSON.parse(JSON.stringify(editedMonitors))
        for (var j = 0; j < copy.length; j++) {
            if (copy[j].name === primary.name) continue
            var newY = Math.round(primaryCenterY - effectiveHeight(copy[j]) / 2)
            copy[j].y = Math.max(0, newY)
        }
        editedMonitors = copy
        hasChanges = true
    }

    // ─── Helper functions ─────────────────────────────────────────────────────
    function effectiveWidth(m) {
        var t = m.transform
        return (t === 1 || t === 3 || t === 5 || t === 7) ? m.height : m.width
    }
    function effectiveHeight(m) {
        var t = m.transform
        return (t === 1 || t === 3 || t === 5 || t === 7) ? m.width : m.height
    }

    function transformLabel(t) {
        var labels = ["Normal","90° (UZS)","180°","270° (UZS)","Gespiegelt","Gesp. + 90°","Gesp. + 180°","Gesp. + 270°"]
        return labels[t] || "Normal"
    }

    // Scale so all monitors fit in monitorContainer (max 0.15 to avoid huge monitors)
    function monitorScale() {
        var mons = editedMonitors
        if (mons.length === 0) return 1
        var maxX = 0, maxY = 0
        for (var i = 0; i < mons.length; i++) {
            var m = mons[i]
            maxX = Math.max(maxX, m.x + effectiveWidth(m))
            maxY = Math.max(maxY, m.y + effectiveHeight(m))
        }
        if (maxX === 0) return 1
        var sx = (monitorContainer.width  - 24) / maxX
        var sy = (monitorContainer.height - 24) / maxY
        return Math.min(sx, sy, 0.15)
    }

    // ─── Section header helper ────────────────────────────────────────────────
    component SectionHeader: Item {
        property string text: ""
        width: parent ? parent.width : 640
        height: 64
        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -8
            anchors.left: parent.left
            anchors.leftMargin: 16
            text: parent.text
            color: monitorsCategory.darkMode ? "#ffffff" : "#1a1a1a"
            font.pixelSize: 18
            font.bold: true
        }
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 16
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            height: 1
            color: monitorsCategory.darkMode ? "#333333" : "#dddddd"
        }
    }

    // ─── Section: Monitor Arrange ──────────────────────────────────────────────
    SectionHeader { text: Lang.get("monitors.arrange", uiLanguage) }

    Text {
        width: parent.width
        leftPadding: 16
        rightPadding: 16
        topPadding: 8
        bottomPadding: 8
        text: Lang.get("monitors.dragHint", uiLanguage)
        color: darkMode ? "#888888" : "#999999"
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }

    // ── Monitor tile container (replaces Canvas entirely) ─────────────────────
    Rectangle {
        id: monitorContainer
        width: parent.width - 32
        height: 200
        x: 16
        radius: 8
        color: darkMode ? "#1a1a1a" : "#f0f0f0"
        border.color: darkMode ? "#333333" : "#cccccc"
        border.width: 1
        clip: true

        // One Rectangle per monitor — fixes the selection bug (no shared canvas)
        Repeater {
            model: monitorsCategory.editedMonitors.length

            delegate: Item {
                id: monDelegate

                // Reactive reference — re-evaluates when editedMonitors is replaced
                property var m: index < monitorsCategory.editedMonitors.length
                                ? monitorsCategory.editedMonitors[index] : null
                // Scale is also reactive (depends on editedMonitors via monitorScale())
                property real s: monitorsCategory.monitorScale()

                property bool isSelected: index === monitorsCategory.selectedIndex
                property bool isPrimary:  monitorsCategory.settingsMenu && m
                                          && m.name === monitorsCategory.settingsMenu.primaryMonitor

                // Drag tracking: stored once at press-time so dragging stays smooth
                // (we use container-absolute coords → no "ghost mouse" on model update)
                property real pressedContainerX: 0
                property real pressedContainerY: 0
                property real pressedMonX: 0
                property real pressedMonY: 0
                property real pressedScale:  1

                x:      m ? 12 + m.x * s                          : 0
                y:      m ? 12 + m.y * s                          : 0
                width:  m ? monitorsCategory.effectiveWidth(m)  * s : 0
                height: m ? monitorsCategory.effectiveHeight(m) * s : 0

                // ── Visual tile ───────────────────────────────────────────────
                Rectangle {
                    anchors.fill: parent
                    radius: 4
                    color: {
                        if (!monDelegate.m) return "transparent"
                        return monDelegate.m.disabled
                            ? (monitorsCategory.darkMode ? "#222222" : "#dddddd")
                            : (monitorsCategory.darkMode ? "#2d2d2d" : "#e8e8e8")
                    }
                    // Per-tile border — fixes selection bug (each tile owns its border)
                    border.width: monDelegate.isPrimary ? 2.5 : (monDelegate.isSelected ? 2 : 1)
                    border.color: monDelegate.isPrimary
                        ? monitorsCategory.accentColor
                        : (monDelegate.isSelected
                           ? "#888888"
                           : (monitorsCategory.darkMode ? "#444444" : "#bbbbbb"))

                    Text {
                        anchors.centerIn: parent
                        anchors.verticalCenterOffset: -7
                        text: monDelegate.m ? monDelegate.m.name : ""
                        color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                        font.pixelSize: 10
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        width: parent.width - 4
                    }

                    Text {
                        anchors.centerIn: parent
                        anchors.verticalCenterOffset: 7
                        text: monDelegate.m ? monDelegate.m.width + "x" + monDelegate.m.height : ""
                        color: monitorsCategory.darkMode ? "#888888" : "#666666"
                        font.pixelSize: 8
                        horizontalAlignment: Text.AlignHCenter
                    }

                    // Primary star badge
                    Text {
                        anchors.top:   parent.top
                        anchors.right: parent.right
                        anchors.topMargin:   3
                        anchors.rightMargin: 5
                        text: "★"
                        font.pixelSize: 9
                        color: monitorsCategory.accentColor
                        visible: monDelegate.isPrimary
                    }
                }

                // ── MouseArea: selection + smooth drag ───────────────────────
                MouseArea {
                    anchors.fill: parent
                    preventStealing: true

                    onPressed: function(mouse) {
                        monitorsCategory.selectedIndex = index

                        // Capture press position in container coords (stable frame of reference)
                        var cp = mapToItem(monitorContainer, mouse.x, mouse.y)
                        monDelegate.pressedContainerX = cp.x
                        monDelegate.pressedContainerY = cp.y
                        monDelegate.pressedMonX  = monDelegate.m ? monDelegate.m.x : 0
                        monDelegate.pressedMonY  = monDelegate.m ? monDelegate.m.y : 0
                        monDelegate.pressedScale = monDelegate.s
                    }

                    onPositionChanged: function(mouse) {
                        if (!pressed || !monDelegate.m) return

                        // Convert current mouse pos to container coords
                        var cp = mapToItem(monitorContainer, mouse.x, mouse.y)

                        // Total displacement from press point (in monitor pixel units)
                        var dx = (cp.x - monDelegate.pressedContainerX) / monDelegate.pressedScale
                        var dy = (cp.y - monDelegate.pressedContainerY) / monDelegate.pressedScale

                        var newX = Math.max(0, Math.round(monDelegate.pressedMonX + dx))
                        var newY = Math.max(0, Math.round(monDelegate.pressedMonY + dy))

                        var copy = JSON.parse(JSON.stringify(monitorsCategory.editedMonitors))
                        copy[index].x = newX
                        copy[index].y = newY
                        monitorsCategory.editedMonitors = copy
                        monitorsCategory.hasChanges = true
                    }

                    onReleased: function(mouse) {
                        if (!monDelegate.m) return
                        // Snap to nearest monitor edge
                        var copy = JSON.parse(JSON.stringify(monitorsCategory.editedMonitors))
                        var dm   = copy[index]
                        var dew  = monitorsCategory.effectiveWidth(dm)
                        var deh  = monitorsCategory.effectiveHeight(dm)
                        // Edge snap: for attaching monitors side-by-side (coarser)
                        var snapEdge  = Math.round(12 / (monDelegate.pressedScale || 0.1))
                        // Align snap: for matching top-edges (much finer → precise vertical positioning)
                        var snapAlign = Math.round(3  / (monDelegate.pressedScale || 0.1))

                        for (var i = 0; i < copy.length; i++) {
                            if (i === index) continue
                            var om  = copy[i]
                            var oew = monitorsCategory.effectiveWidth(om)
                            var oeh = monitorsCategory.effectiveHeight(om)

                            // Horizontal snap (edge-to-edge)
                            if (Math.abs((dm.x + dew) - om.x)       < snapEdge) dm.x = om.x - dew
                            if (Math.abs(dm.x        - (om.x + oew)) < snapEdge) dm.x = om.x + oew
                            // Vertical snap (edge-to-edge)
                            if (Math.abs((dm.y + deh) - om.y)       < snapEdge) dm.y = om.y - deh
                            if (Math.abs(dm.y        - (om.y + oeh)) < snapEdge) dm.y = om.y + oeh
                            // Y-alignment snap (only when very close — for precise cursor alignment)
                            if (Math.abs(dm.y - om.y) < snapAlign) dm.y = om.y
                        }
                        dm.x = Math.max(0, dm.x)
                        dm.y = Math.max(0, dm.y)
                        copy[index] = dm
                        monitorsCategory.editedMonitors = copy
                    }
                }
            }
        }

        // Empty state
        Text {
            anchors.centerIn: parent
            text: Lang.get("monitors.noMonitors", monitorsCategory.uiLanguage)
            color: monitorsCategory.darkMode ? "#666666" : "#aaaaaa"
            font.pixelSize: 13
            visible: monitorsCategory.editedMonitors.length === 0
        }
    }

    // ─── Auto-Align Button ─────────────────────────────────────────────────────
    RowLayout {
        width: parent.width - 32
        x: 16
        height: 52
        spacing: 12

        Column {
            Layout.fillWidth: true
            spacing: 3
            Text {
                text: Lang.get("monitors.autoAlign", monitorsCategory.uiLanguage)
                color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                font.pixelSize: 13
            }
            Text {
                text: Lang.get("monitors.autoAlignDesc", monitorsCategory.uiLanguage)
                color: monitorsCategory.darkMode ? "#888888" : "#777777"
                font.pixelSize: 11
            }
        }

        Rectangle {
            width: 36; height: 36; radius: 6
            color: alignHover ? (monitorsCategory.darkMode ? "#3a3a3a" : "#d8d8d8")
                              : (monitorsCategory.darkMode ? "#2a2a2a" : "#e8e8e8")
            border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"
            property bool alignHover: false
            Behavior on color { ColorAnimation { duration: 100 } }
            Text {
                anchors.centerIn: parent
                text: "⇕"
                color: monitorsCategory.accentColor
                font.pixelSize: 18
            }
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                onEntered: parent.alignHover = true
                onExited:  parent.alignHover = false
                onClicked: monitorsCategory.autoAlignCursors()
            }
        }
    }

    // ─── Section: Monitor Properties ──────────────────────────────────────────
    Item { width: 1; height: 28 }

    SectionHeader { text: Lang.get("monitors.properties", uiLanguage) }

    // No monitor selected hint
    Text {
        width: parent.width
        leftPadding: 16
        topPadding: 14
        bottomPadding: 14
        text: Lang.get("monitors.selectMonitor", uiLanguage)
        color: darkMode ? "#888888" : "#999999"
        font.pixelSize: 12
        visible: monitorsCategory.selectedIndex < 0 || monitorsCategory.editedMonitors.length === 0
    }

    // Properties panel (visible when a monitor is selected)
    Column {
        visible: monitorsCategory.selectedIndex >= 0 && monitorsCategory.editedMonitors.length > 0
        width: parent.width
        spacing: 0

        property var mon: monitorsCategory.selectedIndex >= 0
                          && monitorsCategory.editedMonitors.length > monitorsCategory.selectedIndex
                          ? monitorsCategory.editedMonitors[monitorsCategory.selectedIndex]
                          : null

        // Monitor name + description header
        Rectangle {
            width: parent.width - 32
            x: 16
            height: 64
            color: "transparent"
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                spacing: 12

                Rectangle {
                    width: 64; height: 40; radius: 6
                    color: monitorsCategory.darkMode ? "#2a2a2a" : "#e0e0e0"
                    clip: true

                    Image {
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectCrop
                        smooth: true
                        mipmap: true
                        source: {
                            var idx = monitorsCategory.selectedIndex
                            if (idx < 0 || idx >= monitorsCategory.editedMonitors.length) return ""
                            var name = monitorsCategory.editedMonitors[idx].name
                            var wp = monitorsCategory.monitorWallpapers[name] || ""
                            return wp ? ("file://" + wp) : ""
                        }
                    }

                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "transparent"
                        border.color: monitorsCategory.darkMode ? "#444" : "#bbb"
                        border.width: 1
                    }
                }
                Column {
                    spacing: 3
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        text: parent.parent.parent.parent.mon
                              ? parent.parent.parent.parent.mon.name : ""
                        color: monitorsCategory.darkMode ? "#ffffff" : "#111111"
                        font.pixelSize: 14
                        font.bold: true
                    }
                    Text {
                        text: parent.parent.parent.parent.mon
                              ? parent.parent.parent.parent.mon.description : ""
                        color: monitorsCategory.darkMode ? "#888888" : "#666666"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        width: 400
                    }
                }
            }
        }

        // ── Row: Resolution + Refresh Rate ────────────────────────────────────
        Rectangle {
            width: parent.width - 32; x: 16; height: 1
            color: monitorsCategory.darkMode ? "#2a2a2a" : "#e5e5e5"
        }

        RowLayout {
            width: parent.width - 32
            x: 16
            height: 64
            spacing: 16

            // Resolution dropdown
            Column {
                Layout.fillWidth: true
                spacing: 5
                Text {
                    text: Lang.get("monitors.resolution", monitorsCategory.uiLanguage)
                    color: monitorsCategory.darkMode ? "#cccccc" : "#444444"
                    font.pixelSize: 12
                }
                Rectangle {
                    id: resolutionDropRect
                    width: parent.width; height: 32; radius: 4
                    color: monitorsCategory.darkMode ? "#2a2a2a" : "#eeeeee"
                    border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"

                    property var mon: monitorsCategory.selectedIndex >= 0
                                      && monitorsCategory.editedMonitors.length > 0
                                      ? monitorsCategory.editedMonitors[monitorsCategory.selectedIndex]
                                      : null
                    property var uniqueResolutions: {
                        if (!mon || !mon.modes) return []
                        var seen = {}, res = []
                        for (var i = 0; i < mon.modes.length; i++) {
                            var parts = mon.modes[i].split("@")
                            if (parts.length > 0 && !seen[parts[0]]) {
                                seen[parts[0]] = true
                                res.push(parts[0])
                            }
                        }
                        return res
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 10
                        text: resolutionDropRect.mon ? resolutionDropRect.mon.width + "x" + resolutionDropRect.mon.height : ""
                        color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                        font.pixelSize: 12
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right; anchors.rightMargin: 8
                        text: "▾"
                        color: monitorsCategory.darkMode ? "#888888" : "#666666"
                        font.pixelSize: 10
                    }
                    MouseArea { anchors.fill: parent; onClicked: resolutionPopup.open() }

                    Popup {
                        id: resolutionPopup
                        y: resolutionDropRect.height + 2; x: 0
                        width: resolutionDropRect.width
                        height: Math.min(resolutionDropRect.uniqueResolutions.length * 32 + 8, 200)
                        padding: 4
                        background: Rectangle {
                            color: monitorsCategory.darkMode ? "#2a2a2a" : "#f8f8f8"
                            border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"
                            radius: 4
                        }
                        contentItem: ListView {
                            model: resolutionDropRect.uniqueResolutions
                            clip: true
                            delegate: Rectangle {
                                width: resolutionPopup.width - 8
                                height: 32; radius: 3
                                color: hovered
                                       ? (monitorsCategory.darkMode ? "#3a3a3a" : "#e0e0e0")
                                       : "transparent"
                                property bool hovered: false
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left; anchors.leftMargin: 8
                                    text: modelData
                                    color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onEntered: parent.hovered = true
                                    onExited:  parent.hovered = false
                                    onClicked: {
                                        var parts = modelData.split("x")
                                        var copy = JSON.parse(JSON.stringify(monitorsCategory.editedMonitors))
                                        copy[monitorsCategory.selectedIndex].width  = parseInt(parts[0])
                                        copy[monitorsCategory.selectedIndex].height = parseInt(parts[1])
                                        monitorsCategory.editedMonitors = copy
                                        monitorsCategory.hasChanges = true
                                        resolutionPopup.close()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Refresh rate dropdown
            Column {
                Layout.preferredWidth: 130
                spacing: 5
                Text {
                    text: Lang.get("monitors.refreshRate", monitorsCategory.uiLanguage)
                    color: monitorsCategory.darkMode ? "#cccccc" : "#444444"
                    font.pixelSize: 12
                }
                Rectangle {
                    id: refreshDropRect
                    width: 130; height: 32; radius: 4
                    color: monitorsCategory.darkMode ? "#2a2a2a" : "#eeeeee"
                    border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"

                    property var mon: monitorsCategory.selectedIndex >= 0
                                      && monitorsCategory.editedMonitors.length > 0
                                      ? monitorsCategory.editedMonitors[monitorsCategory.selectedIndex]
                                      : null
                    property var refreshRates: {
                        if (!mon || !mon.modes) return []
                        // Check both orientations (native vs. effective) so portrait monitors work too
                        var r1 = mon.width  + "x" + mon.height
                        var r2 = mon.height + "x" + mon.width
                        var rates = [], seen = {}
                        for (var i = 0; i < mon.modes.length; i++) {
                            var parts = mon.modes[i].split("@")
                            if (parts.length === 2 && (parts[0] === r1 || parts[0] === r2)) {
                                var rate = parts[1].replace("Hz","").trim()
                                if (!seen[rate]) { seen[rate] = true; rates.push(rate) }
                            }
                        }
                        return rates
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 10
                        text: refreshDropRect.mon ? Math.round(refreshDropRect.mon.refreshRate) + " Hz" : ""
                        color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                        font.pixelSize: 12
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right; anchors.rightMargin: 8
                        text: "▾"
                        color: monitorsCategory.darkMode ? "#888888" : "#666666"
                        font.pixelSize: 10
                    }
                    MouseArea { anchors.fill: parent; onClicked: refreshPopup.open() }

                    Popup {
                        id: refreshPopup
                        y: refreshDropRect.height + 2; x: 0
                        width: refreshDropRect.width
                        height: Math.min(refreshDropRect.refreshRates.length * 32 + 8, 180)
                        padding: 4
                        background: Rectangle {
                            color: monitorsCategory.darkMode ? "#2a2a2a" : "#f8f8f8"
                            border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"
                            radius: 4
                        }
                        contentItem: ListView {
                            model: refreshDropRect.refreshRates
                            clip: true
                            delegate: Rectangle {
                                width: refreshPopup.width - 8
                                height: 32; radius: 3
                                color: hovered
                                       ? (monitorsCategory.darkMode ? "#3a3a3a" : "#e0e0e0")
                                       : "transparent"
                                property bool hovered: false
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left; anchors.leftMargin: 8
                                    text: modelData + " Hz"
                                    color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onEntered: parent.hovered = true
                                    onExited:  parent.hovered = false
                                    onClicked: {
                                        var copy = JSON.parse(JSON.stringify(monitorsCategory.editedMonitors))
                                        copy[monitorsCategory.selectedIndex].refreshRate = parseFloat(modelData)
                                        monitorsCategory.editedMonitors = copy
                                        monitorsCategory.hasChanges = true
                                        refreshPopup.close()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Row: Rotation + Scale ─────────────────────────────────────────────
        Rectangle {
            width: parent.width - 32; x: 16; height: 1
            color: monitorsCategory.darkMode ? "#2a2a2a" : "#e5e5e5"
        }

        RowLayout {
            width: parent.width - 32
            x: 16
            height: 64
            spacing: 16

            // Rotation dropdown
            Column {
                Layout.preferredWidth: 200
                spacing: 5
                Text {
                    text: Lang.get("monitors.rotation", monitorsCategory.uiLanguage)
                    color: monitorsCategory.darkMode ? "#cccccc" : "#444444"
                    font.pixelSize: 12
                }
                Rectangle {
                    width: 200; height: 32; radius: 4
                    color: monitorsCategory.darkMode ? "#2a2a2a" : "#eeeeee"
                    border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 10
                        text: {
                            var m = monitorsCategory.selectedIndex >= 0
                                    && monitorsCategory.editedMonitors.length > 0
                                    ? monitorsCategory.editedMonitors[monitorsCategory.selectedIndex]
                                    : null
                            return m ? monitorsCategory.transformLabel(m.transform) : ""
                        }
                        color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                        font.pixelSize: 12
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right; anchors.rightMargin: 8
                        text: "▾"
                        color: monitorsCategory.darkMode ? "#888888" : "#666666"
                        font.pixelSize: 10
                    }
                    MouseArea { anchors.fill: parent; onClicked: transformPopup.open() }

                    Popup {
                        id: transformPopup
                        y: parent.height + 2; x: 0
                        width: parent.width
                        height: 8 * 32 + 8
                        padding: 4
                        background: Rectangle {
                            color: monitorsCategory.darkMode ? "#2a2a2a" : "#f8f8f8"
                            border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"
                            radius: 4
                        }
                        contentItem: ListView {
                            model: [0,1,2,3,4,5,6,7]
                            clip: true
                            delegate: Rectangle {
                                width: transformPopup.width - 8
                                height: 32; radius: 3
                                color: hovered
                                       ? (monitorsCategory.darkMode ? "#3a3a3a" : "#e0e0e0")
                                       : "transparent"
                                property bool hovered: false
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left; anchors.leftMargin: 8
                                    text: monitorsCategory.transformLabel(modelData)
                                    color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onEntered: parent.hovered = true
                                    onExited:  parent.hovered = false
                                    onClicked: {
                                        var copy = JSON.parse(JSON.stringify(monitorsCategory.editedMonitors))
                                        copy[monitorsCategory.selectedIndex].transform = modelData
                                        monitorsCategory.editedMonitors = copy
                                        monitorsCategory.hasChanges = true
                                        transformPopup.close()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Scale slider
            Column {
                Layout.fillWidth: true
                spacing: 5
                Text {
                    text: Lang.get("monitors.scale", monitorsCategory.uiLanguage) + ": " +
                          (monitorsCategory.selectedIndex >= 0 && monitorsCategory.editedMonitors.length > 0
                           ? monitorsCategory.editedMonitors[monitorsCategory.selectedIndex].scale.toFixed(2)
                           : "1.00")
                    color: monitorsCategory.darkMode ? "#cccccc" : "#444444"
                    font.pixelSize: 12
                }
                Slider {
                    width: parent.width
                    from: 0.5; to: 3.0; stepSize: 0.25
                    value: monitorsCategory.selectedIndex >= 0 && monitorsCategory.editedMonitors.length > 0
                           ? monitorsCategory.editedMonitors[monitorsCategory.selectedIndex].scale : 1.0
                    onMoved: {
                        var copy = JSON.parse(JSON.stringify(monitorsCategory.editedMonitors))
                        copy[monitorsCategory.selectedIndex].scale = value
                        monitorsCategory.editedMonitors = copy
                        monitorsCategory.hasChanges = true
                    }
                    background: Rectangle {
                        x: parent.leftPadding
                        y: parent.topPadding + parent.availableHeight / 2 - height / 2
                        implicitWidth: 200; implicitHeight: 4
                        width: parent.availableWidth; height: implicitHeight
                        radius: 2
                        color: monitorsCategory.darkMode ? "#333333" : "#dddddd"
                        Rectangle {
                            width: parent.parent.visualPosition * parent.width
                            height: parent.height; radius: 2
                            color: monitorsCategory.accentColor
                        }
                    }
                    handle: Rectangle {
                        x: parent.leftPadding + parent.visualPosition * (parent.availableWidth - width)
                        y: parent.topPadding + parent.availableHeight / 2 - height / 2
                        implicitWidth: 16; implicitHeight: 16; radius: 8
                        color: monitorsCategory.accentColor
                    }
                }
            }
        }

        // ── Row: Primary + Enabled toggles ────────────────────────────────────
        Rectangle {
            width: parent.width - 32; x: 16; height: 1
            color: monitorsCategory.darkMode ? "#2a2a2a" : "#e5e5e5"
        }

        RowLayout {
            width: parent.width - 32
            x: 16
            height: 64
            spacing: 0

            // Primary label
            Column {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    text: Lang.get("monitors.primary", monitorsCategory.uiLanguage)
                    color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                    font.pixelSize: 13
                }
                Text {
                    text: Lang.get("monitors.primaryDesc", monitorsCategory.uiLanguage)
                    color: monitorsCategory.darkMode ? "#888888" : "#777777"
                    font.pixelSize: 11
                }
            }

            // Primary toggle
            Rectangle {
                width: 44; height: 24; radius: 12
                property bool on: monitorsCategory.selectedIndex >= 0
                                   && monitorsCategory.editedMonitors.length > 0
                                   && monitorsCategory.settingsMenu
                                   && monitorsCategory.editedMonitors[monitorsCategory.selectedIndex].name
                                      === monitorsCategory.settingsMenu.primaryMonitor
                color: on ? monitorsCategory.accentColor
                           : (monitorsCategory.darkMode ? "#444444" : "#cccccc")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 18; height: 18; radius: 9
                    anchors.verticalCenter: parent.verticalCenter
                    x: parent.on ? parent.width - width - 3 : 3
                    Behavior on x { NumberAnimation { duration: 150 } }
                    color: "white"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (monitorsCategory.selectedIndex >= 0
                            && monitorsCategory.editedMonitors.length > 0
                            && monitorsCategory.settingsMenu) {
                            monitorsCategory.settingsMenu.primaryMonitor =
                                monitorsCategory.editedMonitors[monitorsCategory.selectedIndex].name
                            monitorsCategory.hasChanges = true
                        }
                    }
                }
            }

            Item { width: 32 }

            // Enabled label
            Column {
                Layout.preferredWidth: 80
                spacing: 3
                Text {
                    text: Lang.get("monitors.enabled", monitorsCategory.uiLanguage)
                    color: monitorsCategory.darkMode ? "#eeeeee" : "#222222"
                    font.pixelSize: 13
                }
            }

            // Enabled toggle
            Rectangle {
                width: 44; height: 24; radius: 12
                property bool on: {
                    if (monitorsCategory.selectedIndex < 0
                        || monitorsCategory.editedMonitors.length === 0) return true
                    return !monitorsCategory.editedMonitors[monitorsCategory.selectedIndex].disabled
                }
                color: on ? monitorsCategory.accentColor
                           : (monitorsCategory.darkMode ? "#444444" : "#cccccc")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 18; height: 18; radius: 9
                    anchors.verticalCenter: parent.verticalCenter
                    x: parent.on ? parent.width - width - 3 : 3
                    Behavior on x { NumberAnimation { duration: 150 } }
                    color: "white"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        var copy = JSON.parse(JSON.stringify(monitorsCategory.editedMonitors))
                        copy[monitorsCategory.selectedIndex].disabled =
                            !copy[monitorsCategory.selectedIndex].disabled
                        monitorsCategory.editedMonitors = copy
                        monitorsCategory.hasChanges = true
                    }
                }
            }
        }
    }

    // ─── Apply / Reset buttons ────────────────────────────────────────────────
    Item { width: 1; height: 28 }

    Rectangle {
        width: parent.width - 32; x: 16; height: 1
        color: monitorsCategory.darkMode ? "#2a2a2a" : "#e5e5e5"
    }

    RowLayout {
        width: parent.width - 32
        x: 16
        height: 64
        spacing: 12

        Rectangle {
            Layout.preferredWidth: 140; height: 36; radius: 6
            color: monitorsCategory.isApplying
                   ? (monitorsCategory.darkMode ? "#444444" : "#cccccc")
                   : monitorsCategory.accentColor
            opacity: monitorsCategory.hasChanges ? 1.0 : 0.5
            Behavior on color { ColorAnimation { duration: 150 } }
            Text {
                anchors.centerIn: parent
                text: monitorsCategory.isApplying
                      ? Lang.get("monitors.applying", monitorsCategory.uiLanguage)
                      : Lang.get("monitors.apply",    monitorsCategory.uiLanguage)
                color: "white"; font.pixelSize: 13; font.bold: true
            }
            MouseArea {
                anchors.fill: parent
                enabled: monitorsCategory.hasChanges && !monitorsCategory.isApplying
                onClicked: monitorsCategory.applyChanges()
            }
        }

        Rectangle {
            Layout.preferredWidth: 120; height: 36; radius: 6
            color: monitorsCategory.darkMode ? "#2a2a2a" : "#e8e8e8"
            border.color: monitorsCategory.darkMode ? "#444444" : "#cccccc"
            opacity: monitorsCategory.hasChanges ? 1.0 : 0.5
            Text {
                anchors.centerIn: parent
                text: Lang.get("monitors.reset", monitorsCategory.uiLanguage)
                color: monitorsCategory.darkMode ? "#cccccc" : "#444444"
                font.pixelSize: 13
            }
            MouseArea {
                anchors.fill: parent
                enabled: monitorsCategory.hasChanges
                onClicked: {
                    monitorsCategory.loadMonitors()
                    monitorsCategory.hasChanges = false
                }
            }
        }

        Item { Layout.fillWidth: true }
    }

    Item { width: 1; height: 28 }

    // ─── Apply logic ──────────────────────────────────────────────────────────
    Process {
        id: applyProc
        running: false
        onExited: function(code) {
            monitorsCategory.isApplying = false
            monitorsCategory.hasChanges = (code !== 0)
            if (code === 0) monitorsCategory.loadMonitors()
        }
    }

    function applyChanges() {
        if (editedMonitors.length === 0) return
        isApplying = true
        var enabled = editedMonitors.filter(function(m) { return !m.disabled })
        if (enabled.length === 0) {
            isApplying = false
            return
        }
        var primary = settingsMenu ? settingsMenu.primaryMonitor : enabled[0].name
        if (!enabled.some(function(m) { return m.name === primary })) primary = enabled[0].name
        applyProc.command = ["windoesnot-settings", JSON.stringify({monitors: {
            primary: primary, monitors: editedMonitors
        }})]
        applyProc.running = true
        if (settingsMenu) {
            settingsMenu.primaryMonitor = primary
            settingsMenu.saveSettings()
        }
    }
}
