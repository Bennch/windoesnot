import Qt5Compat.GraphicalEffects
import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: root
    anchors.fill: parent

    property string accentColor: "#FE6F2D"
    property int selectedMonitorIndex: -1
    property var monitors: []
    property var monitorWallpapers: ({})  // {monitorName: wallpaperPath}
    property var availableWallpapers: []
    // Wallpapers shipped with WinDoesNot (empty when the package directory is missing)
    property var builtinWallpapers: []
    readonly property string builtinFolder: "/usr/share/backgrounds/windoesnot"
    property string picturesFolder: ""
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"  // Reference to parent settings window

    signal wallpaperChanged(string monitorName, string wallpaperPath)

    Component.onCompleted: {
        console.log("=== MonitorCfg loaded ===")
        detectPicturesFolder()
        loadMonitors()
        loadCurrentWallpapers()
        loadAvailableWallpapers()
        builtinListProc.running = true
    }

    // Detect Pictures folder with multilanguage support
    function detectPicturesFolder() {
        console.log("=== detectPicturesFolder called ===")
        // Check xdg-user-dir first
        xdgUserDirProc.command = ["bash", "-c", "xdg-user-dir PICTURES 2>/dev/null || echo ''"]
        xdgUserDirProc.running = true
    }

    Process {
        id: xdgUserDirProc
        command: ["bash", "-c", ""]
        running: false

        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                xdgUserDirProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running) {
                var xdgPath = accumulatedData.trim()
                console.log("=== xdg-user-dir result:", xdgPath, "===")

                // Get HOME directory via shell
                homeProc.command = ["bash", "-c", "echo $HOME"]
                homeProc.tag = xdgPath
                homeProc.running = true

                accumulatedData = ""
            }
        }
    }

    Process {
        id: homeProc
        command: ["bash", "-c", ""]
        running: false
        property string tag: ""
        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                homeProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running && tag !== undefined) {
                var homePath = accumulatedData.trim()
                var xdgPath = tag

                console.log("=== HOME:", homePath, "XDG:", xdgPath, "===")

                if (xdgPath && xdgPath !== homePath && xdgPath !== "") {
                    picturesFolder = xdgPath
                    console.log("Using XDG Pictures folder:", picturesFolder)
                    loadAvailableWallpapers()
                } else {
                    // Fallback: Check common folders
                    checkFolderProc.command = ["bash", "-c", "test -d ~/Bilder && echo Bilder || test -d ~/Pictures && echo Pictures || echo ''"]
                    checkFolderProc.running = true
                }
                accumulatedData = ""
                tag = ""
            }
        }
    }

    Process {
        id: checkFolderProc
        command: ["bash", "-c", ""]
        running: false

        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                checkFolderProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running) {
                var folder = accumulatedData.trim()

                // Get HOME via shell
                homeFallbackProc.command = ["bash", "-c", "echo $HOME"]
                homeFallbackProc.tag = folder
                homeFallbackProc.running = true

                accumulatedData = ""
            }
        }
    }

    Process {
        id: homeFallbackProc
        command: ["bash", "-c", ""]
        running: false
        property string tag: ""
        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                homeFallbackProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running) {
                var homePath = accumulatedData.trim()
                var folder = tag

                if (folder) {
                    picturesFolder = homePath + "/" + folder
                } else {
                    picturesFolder = homePath + "/Pictures"
                }
                console.log("Using Pictures folder:", picturesFolder)
                loadAvailableWallpapers()

                accumulatedData = ""
                tag = ""
            }
        }
    }

    // Load monitor configuration from monitors.conf
    function loadMonitors() {
        console.log("=== loadMonitors called ===")
        monitorsConfProc.command = ["windoesnot-settings", "--print-monitors-conf"]
        monitorsConfProc.running = true
    }

    Process {
        id: monitorsConfProc
        command: ["bash", "-c", ""]
        running: false

        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                // SplitParser removes newlines, so add them back
                if (monitorsConfProc.accumulatedData.length > 0) {
                    monitorsConfProc.accumulatedData += "\n"
                }
                monitorsConfProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running && accumulatedData) {
                console.log("=== Processing monitors data, length:", accumulatedData.length, "===")
                var lines = accumulatedData.split('\n')
                var monList = []
                var monMap = {}

                console.log("=== Total lines:", lines.length, "===")

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim()

                    // Debug: show each line
                    if (line.length > 0) {
                        console.log("Line", i, ":", line)
                    }

                    if (line.indexOf('monitor=') === 0 && line.indexOf('transform') === -1) {
                        // Parse: monitor=DP-2,2560x1440@144.0,2560x456,1.0
                        console.log("  -> Found monitor definition")
                        var parts = line.substring(8).split(',')
                        console.log("  -> Parts:", JSON.stringify(parts))
                        if (parts.length >= 4) {
                            var name = parts[0]
                            var resolution = parts[1].split('@')[0]
                            var position = parts[2]
                            var scale = parts[3]

                            // Parse resolution
                            var resParts = resolution.split('x')
                            var width = parseInt(resParts[0])
                            var height = parseInt(resParts[1])

                            // Parse position
                            var posParts = position.split('x')
                            var x = parseInt(posParts[0])
                            var y = parseInt(posParts[1])

                            monMap[name] = {
                                name: name,
                                width: width,
                                height: height,
                                x: x,
                                y: y,
                                scale: parseFloat(scale),
                                transform: 0  // Default, will be updated below
                            }
                        }
                    } else if (line.indexOf('monitor=') === 0 && line.indexOf('transform') !== -1) {
                        // Parse: monitor=DP-1,transform,1
                        var parts = line.substring(8).split(',')
                        if (parts.length >= 3 && parts[1] === 'transform') {
                            var name = parts[0]
                            var transform = parseInt(parts[2])
                            if (monMap[name]) {
                                monMap[name].transform = transform
                            }
                        }
                    }
                }

                // Convert map to sorted array
                for (var key in monMap) {
                    monList.push(monMap[key])
                }

                // Sort by X position
                monList.sort(function(a, b) { return a.x - b.x })

                monitors = monList
                console.log("Loaded", monitors.length, "monitors:", JSON.stringify(monitors))

                // Reset for next use
                accumulatedData = ""
            }
        }
    }

    // Load current wallpapers from hyprpaper.conf
    function loadCurrentWallpapers() {
        // Expand ~ to $HOME directly in bash
        hyprpaperConfProc.command = ["bash", "-c", "sed 's|~/|'\"$HOME\"'/|g' ~/.config/hypr/hyprpaper.conf"]
        hyprpaperConfProc.running = true
    }

    Process {
        id: hyprpaperConfProc
        command: ["bash", "-c", ""]
        running: false

        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                if (hyprpaperConfProc.accumulatedData.length > 0) {
                    hyprpaperConfProc.accumulatedData += "\n"
                }
                hyprpaperConfProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running && accumulatedData) {
                var lines = accumulatedData.split('\n')
                var wpMap = {}

                // Parse new block syntax:
                // wallpaper {
                //     monitor = HDMI-A-1
                //     path = ~/Bilder/fire.jpeg
                //     fit_mode = cover
                // }
                var currentMonitor = ""
                var currentPath = ""
                var inWallpaperBlock = false

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim()

                    if (line === "wallpaper {") {
                        inWallpaperBlock = true
                        currentMonitor = ""
                        currentPath = ""
                    } else if (line === "}" && inWallpaperBlock) {
                        if (currentMonitor && currentPath) {
                            wpMap[currentMonitor] = currentPath
                        }
                        inWallpaperBlock = false
                    } else if (inWallpaperBlock) {
                        if (line.startsWith("monitor =")) {
                            currentMonitor = line.substring(9).trim()
                        } else if (line.startsWith("path =")) {
                            currentPath = line.substring(6).trim()
                        }
                    }
                }

                monitorWallpapers = wpMap
                console.log("Loaded wallpapers:", JSON.stringify(monitorWallpapers))

                // Reset for next use
                accumulatedData = ""
            }
        }
    }

    // Load available wallpapers from Pictures folder
    function loadAvailableWallpapers() {
        if (!picturesFolder) {
            Qt.callLater(loadAvailableWallpapers)
            return
        }

        wallpapersListProc.command = [
            "bash", "-c",
            "find '" + picturesFolder + "' -maxdepth 1 -type f \\( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \\) | sort"
        ]
        wallpapersListProc.running = true
    }

    Process {
        id: wallpapersListProc
        command: ["bash", "-c", ""]
        running: false

        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                if (wallpapersListProc.accumulatedData.length > 0) {
                    wallpapersListProc.accumulatedData += "\n"
                }
                wallpapersListProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running && accumulatedData) {
                var lines = accumulatedData.split('\n')
                var wpList = []

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim()
                    if (line) {
                        wpList.push(line)
                    }
                }

                availableWallpapers = wpList
                console.log("Found", availableWallpapers.length, "wallpapers")

                // Reset for next use
                accumulatedData = ""
            }
        }
    }

    Process {
        id: builtinListProc
        command: ["bash", "-c", "find '" + root.builtinFolder + "' -maxdepth 1 -type f \\( -iname '*.jpg' -o -iname '*.png' -o -iname '*.webp' \\) | sort"]
        running: false
        property string accumulatedData: ""
        stdout: SplitParser {
            onRead: function(data) { builtinListProc.accumulatedData += data + "\n" }
        }
        onRunningChanged: {
            if (!running) {
                // The default wallpaper comes first, the rest stay alphabetical.
                var list = accumulatedData.split("\n").filter(function(line) { return line.trim() !== "" })
                list.sort(function(a, b) { return (b.indexOf("-fire.") >= 0) - (a.indexOf("-fire.") >= 0) || a.localeCompare(b) })
                builtinWallpapers = list
                accumulatedData = ""
            }
        }
    }

    // Apply wallpaper to monitor using hyprpaper IPC
    function setWallpaper(monitorName, wallpaperPath) {
        console.log("Setting wallpaper for", monitorName, "to", wallpaperPath)

        // New hyprpaper syntax: windoesnot-hyprctl hyprpaper wallpaper [mon],[path],[fit_mode]
        setWallpaperProc.command = [
            "bash", "-c",
            "windoesnot-hyprctl hyprpaper wallpaper '" + monitorName + "," + wallpaperPath + ",cover'"
        ]
        setWallpaperProc.tag = monitorName + "|" + wallpaperPath
        setWallpaperProc.running = true
    }

    Process {
        id: setWallpaperProc
        command: ["bash", "-c", ""]
        running: false
        property string tag: ""

        onRunningChanged: {
            if (!running && tag) {
                var parts = tag.split('|')
                var monitorName = parts[0]
                var wallpaperPath = parts[1]

                // Update local state
                var newWallpapers = Object.assign({}, monitorWallpapers)
                newWallpapers[monitorName] = wallpaperPath
                monitorWallpapers = newWallpapers

                // Save to config
                saveWallpaperConfig()

                // Emit signal
                wallpaperChanged(monitorName, wallpaperPath)

                // Keep the SilentSDDM login-screen background mirroring the primary
                // monitor's wallpaper. No-op (and no pkexec) if that theme was never
                // set up: the cache directory only exists once sddm-set-theme created it.
                if (settingsMenu && monitorName === settingsMenu.primaryMonitor) {
                    sddmWallpaperSyncProc.command = ["bash", "-c",
                        'test -d "$1" && cp -- "$2" "$1/current.jpg"', "_",
                        "/var/lib/windoesnot/sddm-wallpaper", wallpaperPath]
                    sddmWallpaperSyncProc.running = true
                }

                tag = ""
            }
        }
    }

    Process {
        id: sddmWallpaperSyncProc
        command: ["bash", "-c", ""]
        running: false
    }

    // Save wallpaper configuration to hyprpaper.conf
    function saveWallpaperConfig() {
        var content = "# Wallpaper configuration - managed by Quickshell\n\n"
        content += "# Disable splash screen\n"
        content += "splash = false\n\n"

        // Add wallpaper blocks for each monitor
        for (var mon in monitorWallpapers) {
            var wp = monitorWallpapers[mon]
            content += "wallpaper {\n"
            content += "    monitor = " + mon + "\n"
            content += "    path = " + wp + "\n"
            content += "    fit_mode = cover\n"
            content += "}\n\n"
        }

        saveConfigProc.command = [
            "bash", "-c",
            "cat > ~/.config/hypr/hyprpaper.conf << 'EOFCONFIG'\n" + content + "\nEOFCONFIG"
        ]
        saveConfigProc.running = true
    }

    Process {
        id: saveConfigProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                console.log("Wallpaper config saved")
            }
        }
    }

    // Open file dialog for custom wallpaper selection
    function openWallpaperDialog(monitorName) {
        // Prevent settings menu from closing while file dialog is open
        if (settingsMenu) {
            settingsMenu.fileDialogOpen = true
        }

        fileDialogProc.command = [
            "bash", "-c",
            "zenity --file-selection --title='" + Lang.get("background.selectWallpaper", _lang) + "' --file-filter='Images | *.jpg *.jpeg *.png *.webp' --filename='" + picturesFolder + "/'"
        ]
        fileDialogProc.tag = monitorName
        fileDialogProc.running = true
    }

    Process {
        id: fileDialogProc
        command: ["bash", "-c", ""]
        running: false
        property string tag: ""
        property string accumulatedData: ""

        stdout: SplitParser {
            onRead: function(data) {
                fileDialogProc.accumulatedData += data
            }
        }

        onRunningChanged: {
            if (!running) {
                // Re-enable focus grab when dialog closes
                if (settingsMenu) {
                    settingsMenu.fileDialogOpen = false
                }

                if (tag) {
                    var selectedFile = accumulatedData.trim()
                    if (selectedFile) {
                        setWallpaper(tag, selectedFile)
                    }
                    tag = ""
                    accumulatedData = ""
                }
            }
        }
    }

    // Main UI
    Column {
        anchors.fill: parent
        spacing: 20

        // Monitor Visualization Area
        Item {
            width: parent.width
            height: 300

            Rectangle {
                anchors.fill: parent
                color: settingsMenu.darkMode ? "#1a1a1a" : "#e5e5e5"
                radius: 8
                border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                border.width: 1

                // Monitor visualization canvas
                Item {
                    id: monitorCanvas
                    anchors.fill: parent
                    anchors.margins: 20

                    property real scaleX: 0.1
                    property real scaleY: 0.1
                    property real offsetX: 0
                    property real offsetY: 0

                    Component.onCompleted: Qt.callLater(calculateScale)
                    onWidthChanged:  Qt.callLater(calculateScale)
                    onHeightChanged: Qt.callLater(calculateScale)

                    Connections {
                        target: root
                        function onMonitorsChanged() {
                            Qt.callLater(monitorCanvas.calculateScale)
                        }
                    }

                    function calculateScale() {
                        if (monitors.length === 0) return

                        // Find bounding box
                        var minX = 999999, minY = 999999
                        var maxX = -999999, maxY = -999999

                        for (var i = 0; i < monitors.length; i++) {
                            var mon = monitors[i]
                            var w = mon.width
                            var h = mon.height

                            // Swap width/height for rotated monitors (90°/270°, with or without mirror)
                            if (mon.transform === 1 || mon.transform === 3 || mon.transform === 5 || mon.transform === 7) {
                                w = mon.height
                                h = mon.width
                            }

                            minX = Math.min(minX, mon.x)
                            minY = Math.min(minY, mon.y)
                            maxX = Math.max(maxX, mon.x + w)
                            maxY = Math.max(maxY, mon.y + h)
                        }

                        var totalWidth = maxX - minX
                        var totalHeight = maxY - minY

                        // Calculate scale to fit
                        var availWidth = monitorCanvas.width - 40
                        var availHeight = monitorCanvas.height - 40

                        scaleX = availWidth / totalWidth
                        scaleY = availHeight / totalHeight

                        var scale = Math.min(scaleX, scaleY)
                        scaleX = scale
                        scaleY = scale

                        // Center offset
                        offsetX = (monitorCanvas.width - totalWidth * scale) / 2 - minX * scale
                        offsetY = (monitorCanvas.height - totalHeight * scale) / 2 - minY * scale
                    }

                    Repeater {
                        model: monitors

                        delegate: Rectangle {
                            id: monitorRect

                            property var monitor: modelData
                            property bool isSelected: index === selectedMonitorIndex
                            // Reactive: always correct, even for rotated monitors (transform 1/3/5/7)
                            property real displayWidth:  (monitor && (monitor.transform === 1 || monitor.transform === 3 || monitor.transform === 5 || monitor.transform === 7))
                                                         ? monitor.height : (monitor ? monitor.width  : 0)
                            property real displayHeight: (monitor && (monitor.transform === 1 || monitor.transform === 3 || monitor.transform === 5 || monitor.transform === 7))
                                                         ? monitor.width  : (monitor ? monitor.height : 0)

                            // Track selection changes
                            onIsSelectedChanged: {
                                console.log("Monitor", monitor.name, "selected:", isSelected, "accent:", root.accentColor)
                                updateBorder()
                            }

                            function updateBorder() {
                                if (isSelected) {
                                    border.color = root.accentColor
                                    border.width = 3
                                } else {
                                    border.color = (settingsMenu.darkMode ? "#4a4a4a" : "#c0c0c0")
                                    border.width = 1
                                }
                            }

                            x: monitorCanvas.offsetX + monitor.x * monitorCanvas.scaleX
                            y: monitorCanvas.offsetY + monitor.y * monitorCanvas.scaleY
                            width: displayWidth * monitorCanvas.scaleX
                            height: displayHeight * monitorCanvas.scaleY

                            color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                            border.color: (settingsMenu.darkMode ? "#4a4a4a" : "#c0c0c0")
                            border.width: 1
                            radius: 4

                            Behavior on border.color { ColorAnimation { duration: 200 } }
                            Behavior on border.width { NumberAnimation { duration: 200 } }

                            // Current wallpaper preview (if set)
                            Image {
                                anchors.fill: parent
                                anchors.margins: isSelected ? 3 : 1
                                source: monitorWallpapers[monitor.name] ? "file://" + monitorWallpapers[monitor.name] : ""
                                fillMode: Image.PreserveAspectCrop
                                smooth: true
                                visible: source !== ""
                                opacity: 0.5

                                Behavior on anchors.margins { NumberAnimation { duration: 200 } }
                            }

                            // Monitor name label
                            Rectangle {
                                anchors.centerIn: parent
                                width: nameText.width + 16
                                height: nameText.height + 8
                                color: "#000000"
                                opacity: 0.7
                                radius: 4

                                Text {
                                    id: nameText
                                    anchors.centerIn: parent
                                    text: monitor.name
                                    color: "#ffffff"
                                    font.pixelSize: Math.max(10, Math.min(14, monitorRect.width / 10))
                                    font.bold: true
                                }
                            }

                            // Rotation indicator
                            Text {
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 4
                                text: monitor.transform === 0 ? "" :
                                      monitor.transform === 1 ? "↻90°" :
                                      monitor.transform === 2 ? "↻180°" : "↻270°"
                                color: "#ffffff"
                                font.pixelSize: 10
                                visible: monitor.transform !== 0
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor

                                onClicked: {
                                    selectedMonitorIndex = index
                                }

                                onEntered: {
                                    if (!isSelected) {
                                        monitorRect.border.color = "#6a6a6a"
                                    }
                                }

                                onExited: {
                                    if (!isSelected) {
                                        monitorRect.border.color = (settingsMenu.darkMode ? "#4a4a4a" : "#c0c0c0")
                                    }
                                }
                            }
                        }
                    }

                    // Placeholder when no monitors
                    Text {
                        anchors.centerIn: parent
                        text: Lang.get("background.noMonitors", _lang) + " (monitors.length=" + monitors.length + ")"
                        color: settingsMenu.darkMode ? "#666" : "#888"
                        font.pixelSize: 14
                        visible: monitors.length === 0
                    }
                }
            }
        }

        // Wallpaper selection area (visible when monitor selected)
        Column {
            width: parent.width
            spacing: 15
            visible: selectedMonitorIndex >= 0 && selectedMonitorIndex < monitors.length

            Text {
                text: selectedMonitorIndex >= 0 && selectedMonitorIndex < monitors.length ?
                      Lang.get("background.wallpaperFor", _lang) + " " + monitors[selectedMonitorIndex].name : ""
                color: settingsMenu.darkMode ? "#ccc" : "#1a1a1a"
                font.pixelSize: 16
                font.bold: true
            }

            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // Wallpapers shipped with WinDoesNot
            Text {
                text: Lang.get("background.builtin", _lang)
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                font.pixelSize: 13
                font.bold: true
                visible: builtinWallpapers.length > 0
            }

            Grid {
                width: parent.width
                columns: 5
                spacing: 12
                visible: builtinWallpapers.length > 0

                Repeater {
                    model: builtinWallpapers

                    delegate: Rectangle {
                        property string wallpaperPath: modelData
                        property bool isCurrent: selectedMonitorIndex >= 0 && selectedMonitorIndex < monitors.length
                                                 && monitorWallpapers[monitors[selectedMonitorIndex].name] === wallpaperPath
                        width: (parent.width - 48) / 5
                        height: width * 0.6
                        radius: 8
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: isCurrent ? root.accentColor : (builtinMouseArea.containsMouse ? root.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0"))
                        border.width: isCurrent ? 3 : 2
                        clip: true

                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        Image {
                            anchors.fill: parent
                            anchors.margins: 2
                            source: "file://" + wallpaperPath
                            sourceSize.width: 360
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            smooth: true
                        }

                        MouseArea {
                            id: builtinMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (selectedMonitorIndex >= 0 && selectedMonitorIndex < monitors.length)
                                    setWallpaper(monitors[selectedMonitorIndex].name, wallpaperPath)
                            }
                        }
                    }
                }
            }

            Text {
                text: Lang.get("background.yourPictures", _lang)
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                font.pixelSize: 13
                font.bold: true
                visible: builtinWallpapers.length > 0
            }

            // Wallpaper preview grid (current + 2 quick picks + file dialog button)
            Grid {
                width: parent.width
                columns: 4
                spacing: 15

                // Slot 1: Current wallpaper for selected monitor
                Rectangle {
                    id: currentWallpaperSlot
                    width: (parent.width - 45) / 4
                    height: width * 0.6
                    radius: 8
                    color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.color: root.accentColor
                    border.width: 3
                    clip: true

                    function getCurrentWallpaper() {
                        if (selectedMonitorIndex >= 0 && selectedMonitorIndex < monitors.length) {
                            var monName = monitors[selectedMonitorIndex].name
                            var wp = monitorWallpapers[monName]
                            console.log("Current wallpaper for", monName, ":", wp)
                            return wp || ""
                        }
                        return ""
                    }

                    // Track changes
                    Connections {
                        target: root
                        function onSelectedMonitorIndexChanged() {
                            currentWallpaperImage.source = ""
                            var wp = currentWallpaperSlot.getCurrentWallpaper()
                            if (wp) {
                                currentWallpaperImage.source = "file://" + wp
                            }
                        }
                        function onMonitorWallpapersChanged() {
                            currentWallpaperImage.source = ""
                            var wp = currentWallpaperSlot.getCurrentWallpaper()
                            if (wp) {
                                currentWallpaperImage.source = "file://" + wp
                            }
                        }
                    }

                    Component.onCompleted: {
                        var wp = getCurrentWallpaper()
                        if (wp) {
                            currentWallpaperImage.source = "file://" + wp
                        }
                    }

                    Image {
                        id: currentWallpaperImage
                        anchors.fill: parent
                        anchors.margins: 3
                        fillMode: Image.PreserveAspectCrop
                        smooth: true
                        visible: source !== ""
                    }

                    // "Current" label
                    Rectangle {
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 3
                        height: 20
                        color: root.accentColor
                        radius: 4
                        visible: currentWallpaperImage.source !== ""

                        Text {
                            anchors.centerIn: parent
                            text: Lang.get("background.current", _lang)
                            color: "#ffffff"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }

                    // Placeholder
                    Text {
                        anchors.centerIn: parent
                        text: Lang.get("background.noImage", _lang)
                        color: settingsMenu.darkMode ? "#666" : "#888"
                        font.pixelSize: 12
                        visible: currentWallpaperImage.source === ""
                    }
                }

                // Slots 2-3: First 2 available wallpapers (excluding current)
                Repeater {
                    model: 2

                    delegate: Rectangle {
                        width: (parent.width - 45) / 4
                        height: width * 0.6
                        radius: 8
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: wallpaperMouseArea.containsMouse ? root.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                        border.width: 2
                        clip: true

                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        property string currentWallpaper: {
                            if (selectedMonitorIndex >= 0 && selectedMonitorIndex < monitors.length) {
                                var monName = monitors[selectedMonitorIndex].name
                                return monitorWallpapers[monName] || ""
                            }
                            return ""
                        }

                        property string wallpaperPath: {
                            // Get wallpaper at index, but skip if it's the current one
                            var count = 0
                            for (var i = 0; i < availableWallpapers.length; i++) {
                                if (availableWallpapers[i] !== currentWallpaper) {
                                    if (count === index) {
                                        return availableWallpapers[i]
                                    }
                                    count++
                                }
                            }
                            return ""
                        }

                        Image {
                            anchors.fill: parent
                            anchors.margins: 2
                            source: wallpaperPath ? "file://" + wallpaperPath : ""
                            fillMode: Image.PreserveAspectCrop
                            smooth: true
                            visible: source !== ""
                        }

                        // Placeholder
                        Text {
                            anchors.centerIn: parent
                            text: Lang.get("background.noImage", _lang)
                            color: settingsMenu.darkMode ? "#666" : "#888"
                            font.pixelSize: 12
                            visible: !wallpaperPath
                        }

                        MouseArea {
                            id: wallpaperMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            enabled: wallpaperPath !== ""

                            onClicked: {
                                if (selectedMonitorIndex >= 0 && wallpaperPath) {
                                    var monitor = monitors[selectedMonitorIndex]
                                    setWallpaper(monitor.name, wallpaperPath)
                                }
                            }
                        }

                        // File name tooltip
                        Text {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: 4
                            text: wallpaperPath ? wallpaperPath.split('/').pop() : ""
                            color: "#ffffff"
                            font.pixelSize: 9
                            elide: Text.ElideMiddle
                            horizontalAlignment: Text.AlignHCenter
                            visible: wallpaperMouseArea.containsMouse && wallpaperPath

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: -2
                                color: "#000000"
                                opacity: 0.7
                                radius: 2
                                z: -1
                            }
                        }
                    }
                }

                // File dialog button (4th slot)
                Rectangle {
                    width: (parent.width - 45) / 4
                    height: width * 0.6
                    radius: 8
                    color: fileDialogMouseArea.containsMouse ? root.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: root.accentColor
                    border.width: 2

                    Behavior on color { ColorAnimation { duration: 150 } }

                    Column {
                        anchors.centerIn: parent
                        spacing: 10

                        Image {
                            source: "img/Win11-dark/actions/symbolic/folder-new-symbolic.svg"
                            width: 48
                            height: 48
                            sourceSize.width: 48
                            sourceSize.height: 48
                            anchors.horizontalCenter: parent.horizontalCenter
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            antialiasing: true
                            mipmap: true
                            layer.enabled: !settingsMenu.darkMode
                            layer.smooth: true
                            layer.effect: ColorOverlay { color: "#000000" }
                        }

                        Text {
                            text: Lang.get("background.browse", _lang)
                            color: "#ccc"
                            font.pixelSize: 12
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }

                    MouseArea {
                        id: fileDialogMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor

                        onClicked: {
                            if (selectedMonitorIndex >= 0) {
                                var monitor = monitors[selectedMonitorIndex]
                                openWallpaperDialog(monitor.name)
                            }
                        }
                    }
                }
            }

            // Info text
            Text {
                text: Lang.get("background.clickOrSelect", _lang)
                color: "#888"
                font.pixelSize: 11
                font.italic: true
            }
        }

        // Placeholder when no monitor selected
        Item {
            width: parent.width
            height: 100
            visible: selectedMonitorIndex < 0

            Text {
                anchors.centerIn: parent
                text: Lang.get("background.selectMonitor", _lang)
                color: "#888"
                font.pixelSize: 14
                font.italic: true
            }
        }

        // Login screen (SDDM) theme
        Column {
            id: sddmThemeSection
            width: parent.width
            spacing: 15

            property var sddmThemes: [
                {theme: "windoesnot", preset: "cinder", label: Lang.get("background.sddmCinder", _lang)},
                {theme: "windoesnot", preset: "cinder-still", label: Lang.get("background.sddmCinderStill", _lang)},
                {theme: "windoesnot", preset: "fire", label: Lang.get("background.sddmFire", _lang)},
                {theme: "windoesnot", preset: "glut-dunkel", label: Lang.get("background.sddmGlutDunkel", _lang)},
                {theme: "silentsddm", preset: "default", label: Lang.get("background.sddmSilent", _lang)}
            ]
            property string currentTheme: "windoesnot"
            property string currentPreset: "cinder"
            property bool busy: false
            property string resultText: ""

            Component.onCompleted: sddmThemeStatusProc.running = true

            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            Text {
                text: Lang.get("background.sddmThemeTitle", _lang)
                color: settingsMenu.darkMode ? "#ccc" : "#1a1a1a"
                font.pixelSize: 16
                font.bold: true
            }

            Text {
                text: Lang.get("background.sddmThemeDesc", _lang)
                color: "#888"
                font.pixelSize: 11
                width: parent.width
                wrapMode: Text.WordWrap
            }

            Flow {
                width: parent.width
                spacing: 10

                Repeater {
                    model: sddmThemeSection.sddmThemes

                    delegate: Rectangle {
                        property bool isCurrent: modelData.theme === sddmThemeSection.currentTheme
                                                  && modelData.preset === sddmThemeSection.currentPreset
                        width: Math.max(110, label.implicitWidth + 24)
                        height: 40
                        radius: 6
                        color: isCurrent ? root.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.color: isCurrent ? root.accentColor : (settingsMenu.darkMode ? "#4a4a4a" : "#c0c0c0")
                        border.width: 1
                        opacity: sddmThemeSection.busy ? 0.6 : 1.0

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Text {
                            id: label
                            anchors.centerIn: parent
                            text: modelData.label
                            color: isCurrent ? "#ffffff" : (settingsMenu.darkMode ? "#ccc" : "#1a1a1a")
                            font.pixelSize: 12
                            font.bold: isCurrent
                        }

                        MouseArea {
                            anchors.fill: parent
                            enabled: !sddmThemeSection.busy
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                sddmThemeSection.busy = true
                                sddmThemeSection.resultText = ""
                                sddmThemeApplyProc.command = ["/usr/bin/pkexec", "--disable-internal-agent",
                                    "/usr/lib/windoesnot/system_tools.py", "sddm-set-theme",
                                    JSON.stringify({theme: modelData.theme, preset: modelData.preset})]
                                sddmThemeApplyProc.running = true
                            }
                        }
                    }
                }
            }

            Text {
                text: sddmThemeSection.resultText
                color: sddmThemeSection.resultText.indexOf(Lang.get("systemTools.failed", _lang)) === 0 ? "#e05050" : "#888"
                font.pixelSize: 11
                visible: sddmThemeSection.resultText !== ""
                width: parent.width
                wrapMode: Text.WordWrap
            }
        }
    }

    // Reads which SDDM login-screen theme/preset is currently active (unprivileged, no pkexec).
    Process {
        id: sddmThemeStatusProc
        command: ["/usr/bin/python3", "-I", "/usr/lib/windoesnot/system_tools.py", "sddm-theme-status"]
        running: false
        property string accumulatedData: ""
        stdout: SplitParser {
            onRead: function(data) { sddmThemeStatusProc.accumulatedData += data }
        }
        onRunningChanged: {
            if (!running) {
                try {
                    var status = JSON.parse(sddmThemeStatusProc.accumulatedData)
                    sddmThemeSection.currentTheme = status.theme
                    sddmThemeSection.currentPreset = status.preset
                } catch (e) {}
                sddmThemeStatusProc.accumulatedData = ""
            }
        }
    }

    // Applies the selected SDDM login-screen theme (privileged: writes under /usr/share and /etc).
    Process {
        id: sddmThemeApplyProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector { id: sddmThemeApplyOutput }
        stderr: StdioCollector { id: sddmThemeApplyErrors }
        onExited: (code) => {
            sddmThemeSection.busy = false
            var ok = false
            try { ok = JSON.parse(sddmThemeApplyOutput.text).ok === true } catch (e) {}
            sddmThemeSection.resultText = ok ? Lang.get("systemTools.done", _lang)
                : (code === 126 ? Lang.get("systemTools.cancelled", _lang) : Lang.get("systemTools.failed", _lang))
            if (ok) sddmThemeStatusProc.running = true
        }
    }
}
