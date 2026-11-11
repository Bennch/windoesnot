import Quickshell
import QtQuick
import QtQuick.Effects
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: ollamaPanel
    width: 360
    height: 480

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property bool darkMode: true
    property bool windowVisible: false

    property var modelsData: []        // JS-Array: atomisches Update, kein staggering
    property int loadedCount: 0
    property bool ollamaReachable: true
    property bool activeView: true  // true = models, false = settings

    // Source management — auto-detected
    property string currentSource: "native"
    property string nativeUrl: ""   // set by detectProc
    property string dockerUrl: ""   // set by detectProc
    property string apiUrl: currentSource === "docker" ? dockerUrl : nativeUrl
    property bool nativeOnline: false
    property bool dockerOnline: false
    property bool detectionDone: false
    property bool isLoading: true
    property bool showScrollButtons: false
    // Session-ID-System: verhindert stale results von Warmup und alten Sitzungen
    property int  visibleSessionId: 0
    property int  activeDetectSessionId: -1
    property int  activeListSessionId: -1
    property string activeListSource: ""
    property string activeListUrl: ""
    property bool refreshPending: false

    // Settings
    property string defaultTerminal: ""
    property string currentCtx: ""
    readonly property string composeFile: Quickshell.env("HOME") + "/docker/ollama/docker-compose.yml"

    clip: true

    onWindowVisibleChanged: {
        visibleSessionId++   // jede Zustandsänderung (auf+zu) invalidiert alle laufenden Requests
        if (windowVisible) {
            isLoading = true
            refreshPending = false
            activeDetectSessionId = visibleSessionId
            if (detectProc.running) detectProc.running = false
            detectProc.running = true
            if (!activeView) loadSettings()
        } else {
            if (detectProc.running) detectProc.running = false
            if (listProc.running)   listProc.running   = false
        }
    }

    onCurrentSourceChanged: {
        modelsData = []
        loadedCount = 0
        ollamaReachable = true
        refresh(true)
        if (!activeView) loadSettings()
    }

    Timer {
        interval: 4000
        running: ollamaPanel.windowVisible
        repeat: true
        onTriggered: refresh(false)
    }

    // ── Data loading ──────────────────────────────────────────────────────
    function refresh(forceSpinner) {
        if (!ollamaPanel.windowVisible) return
        if (!ollamaPanel.detectionDone) return
        if (!ollamaPanel.apiUrl) return

        if (listProc.running) {
            ollamaPanel.refreshPending = true
            if (forceSpinner) ollamaPanel.isLoading = true
            return
        }

        ollamaPanel.refreshPending = false
        ollamaPanel.activeListSessionId = ollamaPanel.visibleSessionId
        ollamaPanel.activeListSource = ollamaPanel.currentSource
        var url = ollamaPanel.apiUrl
        ollamaPanel.activeListUrl = url

        if (forceSpinner) ollamaPanel.isLoading = true
        listProc.command = ["python3", "-c",
            "import json, subprocess, sys, concurrent.futures\n" +
            "base = '" + url + "'\n" +
            "def fetch(path):\n" +
            "    return json.loads(subprocess.check_output(['curl', '-sf', '--max-time', '3', base + path]))\n" +
            "try:\n" +
            "    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:\n" +
            "        ft = ex.submit(fetch, '/api/tags')\n" +
            "        fp = ex.submit(fetch, '/api/ps')\n" +
            "        tags = ft.result()\n" +
            "        ps   = fp.result()\n" +
            "    running = {m['name']: m for m in ps.get('models', [])}\n" +
            "    for m in tags.get('models', []):\n" +
            "        name   = m['name']\n" +
            "        size   = m['size']\n" +
            "        params = m.get('details', {}).get('parameter_size', '')\n" +
            "        quant  = m.get('details', {}).get('quantization_level', '')\n" +
            "        loaded = '1' if name in running else '0'\n" +
            "        vram   = running.get(name, {}).get('size_vram', 0)\n" +
            "        print(f'{name}|{size}|{params}|{quant}|{loaded}|{vram}')\n" +
            "except Exception as e:\n" +
            "    print('OFFLINE', file=sys.stderr)\n" +
            "    sys.exit(1)\n"
        ]
        listProc.running = true
    }

    // Detection: vollständig autonom — findet Ports, testet Erreichbarkeit parallel
    Process {
        id: detectProc
        command: ["bash", "-c",
            // Docker container PID + published port
            "dock_pid=$(docker inspect ollama --format '{{.State.Pid}}' 2>/dev/null || echo ''); " +
            "dock_port=$(docker inspect ollama --format '{{range $p,$c := .NetworkSettings.Ports}}{{if $c}}{{(index $c 0).HostPort}}{{end}}{{end}}' 2>/dev/null || echo ''); " +
            // Native PID: alle ollama-Prozesse außer dem Docker-Container-Prozess
            "nat_pid=''; for p in $(pgrep -x ollama 2>/dev/null); do [ \"$p\" != \"$dock_pid\" ] && nat_pid=$p && break; done; " +
            // Native port: OLLAMA_HOST aus Process-Env → ss-Fallback → Default 11434
            "nat_port=''; " +
            "if [ -n \"$nat_pid\" ]; then " +
            "  h=$(cat /proc/$nat_pid/environ 2>/dev/null | tr '\\0' '\\n' | grep 'OLLAMA_HOST=' | cut -d= -f2); " +
            "  [ -n \"$h\" ] && nat_port=$(echo \"$h\" | grep -oP '\\d+$'); " +
            "  [ -z \"$nat_port\" ] && nat_port=$(ss -tlnp 2>/dev/null | grep \"pid=$nat_pid,\" | grep -oP ':\\K\\d+' | head -1); " +
            "  [ -z \"$nat_port\" ] && nat_port=11434; " +
            "fi; " +
            // Parallel reachability checks via temp files
            "t1=$(mktemp); t2=$(mktemp); " +
            "[ -n \"$nat_port\" ] && { curl -sf --max-time 2 \"http://localhost:$nat_port/api/tags\" >/dev/null 2>&1 && echo 1 || echo 0; } >\"$t1\" & " +
            "[ -n \"$dock_port\" ] && { curl -sf --max-time 2 \"http://localhost:$dock_port/api/tags\" >/dev/null 2>&1 && echo 1 || echo 0; } >\"$t2\" & " +
            "wait; " +
            "nat_ok=$(cat \"$t1\" 2>/dev/null || echo 0); " +
            "dock_ok=$(cat \"$t2\" 2>/dev/null || echo 0); " +
            "rm -f \"$t1\" \"$t2\"; " +
            "echo \"${nat_port}|${dock_port}|${nat_ok}|${dock_ok}\""
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                // Warmup-Guard: Ergebnis verwerfen wenn Session inzwischen gewechselt hat
                if (ollamaPanel.activeDetectSessionId !== ollamaPanel.visibleSessionId) return
                var parts = text.trim().split('|')
                if (parts.length < 4) { ollamaPanel.refresh(); return }
                var natPort  = parts[0]
                var dockPort = parts[1]
                var natOk    = parts[2] === '1'
                var dockOk   = parts[3] === '1'

                if (natPort)  ollamaPanel.nativeUrl = "http://localhost:" + natPort
                if (dockPort) ollamaPanel.dockerUrl  = "http://localhost:" + dockPort
                ollamaPanel.nativeOnline = natOk
                ollamaPanel.dockerOnline = dockOk

                if (!ollamaPanel.detectionDone) {
                    // Beim ersten Start: beste verfügbare Quelle wählen
                    if (natOk && !dockOk) ollamaPanel.currentSource = "native"
                    else if (dockOk && !natOk) ollamaPanel.currentSource = "docker"
                    ollamaPanel.detectionDone = true
                } else {
                    // Nur wechseln wenn aktuelle Quelle offline geht
                    if (ollamaPanel.currentSource === "native" && !natOk && dockOk)
                        ollamaPanel.currentSource = "docker"
                    else if (ollamaPanel.currentSource === "docker" && !dockOk && natOk)
                        ollamaPanel.currentSource = "native"
                }
                ollamaPanel.refresh(true)
            }
        }
    }

    function loadSettings() {
        console.log("[OllamaPanel] loadSettings() - currentSource:", currentSource)
        if (currentSource === "docker")
            readCtxDockerProc.running = true
        else
            readCtxNativeProc.running = true
    }

    Process {
        id: listProc
        command: ["python3", "-c", ""]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                // Triple-Guard: Session, Source und URL müssen übereinstimmen
                if (ollamaPanel.activeListSessionId !== ollamaPanel.visibleSessionId ||
                    ollamaPanel.activeListSource    !== ollamaPanel.currentSource    ||
                    ollamaPanel.activeListUrl       !== ollamaPanel.apiUrl) {
                    if (ollamaPanel.refreshPending) Qt.callLater(function() { ollamaPanel.refresh(true) })
                    return
                }

                var lines = text.trim().split('\n')
                var newList = []
                var loaded = 0
                ollamaPanel.ollamaReachable = true
                for (var i = 0; i < lines.length; i++) {
                    var l = lines[i].trim()
                    if (!l) continue
                    var p = l.split('|')
                    if (p.length < 6) continue
                    var isLoaded = p[4] === '1'
                    if (isLoaded) loaded++
                    newList.push({
                        name:   p[0],
                        sizeGb: (parseInt(p[1]) / 1e9).toFixed(1),
                        params: p[2],
                        quant:  p[3],
                        loaded: isLoaded,
                        vramGb: parseInt(p[5]) > 0 ? (parseInt(p[5]) / 1e9).toFixed(1) : ""
                    })
                }
                ollamaPanel.loadedCount = loaded
                ollamaPanel.modelsData = newList
                ollamaPanel.isLoading = false

                if (ollamaPanel.refreshPending)
                    Qt.callLater(function() { ollamaPanel.refresh(true) })
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                // Triple-Guard auch für Fehlerfall
                if (ollamaPanel.activeListSessionId !== ollamaPanel.visibleSessionId ||
                    ollamaPanel.activeListSource    !== ollamaPanel.currentSource    ||
                    ollamaPanel.activeListUrl       !== ollamaPanel.apiUrl) {
                    if (ollamaPanel.refreshPending) Qt.callLater(function() { ollamaPanel.refresh(true) })
                    return
                }
                if (text.indexOf('OFFLINE') >= 0) {
                    ollamaPanel.ollamaReachable = false
                    ollamaPanel.isLoading = false
                }
                if (ollamaPanel.refreshPending)
                    Qt.callLater(function() { ollamaPanel.refresh(true) })
            }
        }
    }

    Process {
        id: actionProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: if (!running) refreshTimer.start()
    }

    Timer {
        id: refreshTimer; interval: 800; repeat: false
        onTriggered: refresh(false)
    }

    // Settings: read OLLAMA_NUM_CTX
    Process {
        id: readCtxDockerProc
        command: ["bash", "-c",
            "grep -oP 'OLLAMA_NUM_CTX=\\K\\d+' " + ollamaPanel.composeFile + " 2>/dev/null || echo ''"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var v = text.trim()
                console.log("[OllamaPanel] readCtxDockerProc result:", v, "→ setting to:", v || "4096")
                ollamaPanel.currentCtx = v || "4096"
            }
        }
    }
    Process {
        id: readCtxNativeProc
        command: ["bash", "-c",
            // 1. Direct override.conf file read (most reliable) - handle quotes
            "grep -oP 'OLLAMA_NUM_CTX=\"?\\K\\d+' ~/.config/systemd/user/ollama.service.d/override.conf 2>/dev/null || " +
            // 2. Running process env
            "cat /proc/$(pgrep -x ollama | head -1)/environ 2>/dev/null | tr '\\0' '\\n' | " +
            "grep -oP '(?:OLLAMA_CONTEXT_LENGTH|OLLAMA_NUM_CTX)=\\K\\d+' | head -1 || " +
            // 3. Current env
            "printenv OLLAMA_CONTEXT_LENGTH 2>/dev/null || printenv OLLAMA_NUM_CTX 2>/dev/null || echo ''"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var v = text.trim()
                console.log("[OllamaPanel] readCtxNativeProc result:", v, "→ setting to:", v || "2048")
                ollamaPanel.currentCtx = v || "2048"
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim())
                    console.log("[OllamaPanel] readCtxNativeProc stderr:", text.trim())
            }
        }
    }

    // Settings: save OLLAMA_NUM_CTX
    Process {
        id: writeCtxProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                console.log("[OllamaPanel] writeCtxProc finished, waiting 2s before reload...")
                reloadCtxTimer.start()
            }
        }
    }

    Timer {
        id: reloadCtxTimer
        interval: 2000
        repeat: false
        onTriggered: {
            console.log("[OllamaPanel] Reloading settings after save...")
            loadSettings()
        }
    }

    // ── Background ────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        topLeftRadius: ollamaPanel.borderRadius
        topRightRadius: ollamaPanel.borderRadius
        bottomLeftRadius: 0; bottomRightRadius: 0
        color: ollamaPanel.darkMode
            ? Qt.rgba(0.125, 0.125, 0.125, 0.93)
            : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        border.color: ollamaPanel.darkMode ? "#3a3a3f" : "#c0c0c0"
        border.width: 1
    }

    Column {
        anchors.fill: parent
        anchors.margins: 15
        spacing: 10

        // ── Header ────────────────────────────────────────────────────────
        Item {
            width: parent.width
            height: 26

            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Image {
                    source: Qt.resolvedUrl("../img/simple-icons--ollama.svg")
                    width: 18; height: 18
                    sourceSize.width: 36; sourceSize.height: 36
                    smooth: true; antialiasing: true; mipmap: true
                    anchors.verticalCenter: parent.verticalCenter
                    layer.enabled: !ollamaPanel.darkMode
                    layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                }
                Text {
                    text: "Ollama"
                    font.pixelSize: 16; font.weight: Font.DemiBold
                    color: ollamaPanel.darkMode ? "#ffffff" : "#000000"
                    anchors.verticalCenter: parent.verticalCenter
                    renderType: Text.NativeRendering
                }
            }

            // Status badge
            Rectangle {
                anchors.right: settingsBtn.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                width: badgeText.width + 14; height: 20; radius: 10
                color: !ollamaPanel.ollamaReachable
                    ? Qt.rgba(0.7, 0.2, 0.2, 0.3)
                    : ollamaPanel.loadedCount > 0
                        ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.2)
                        : Qt.rgba(0.3, 0.3, 0.3, 0.4)
                border.width: 1
                border.color: !ollamaPanel.ollamaReachable
                    ? Qt.rgba(0.8, 0.3, 0.3, 0.5)
                    : ollamaPanel.loadedCount > 0
                        ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.5)
                        : "transparent"
                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: !ollamaPanel.ollamaReachable ? Lang.get("ollama.statusOffline")
                          : ollamaPanel.loadedCount > 0 ? ollamaPanel.loadedCount + " " + Lang.get("ollama.statusLoaded")
                          : Lang.get("ollama.statusIdle")
                    font.pixelSize: 11
                    color: !ollamaPanel.ollamaReachable ? "#ef5350"
                           : ollamaPanel.loadedCount > 0 ? ollamaPanel.accentColor
                           : (ollamaPanel.darkMode ? "#888" : "#666")
                }
            }

            // Settings toggle
            Rectangle {
                id: settingsBtn
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 26; height: 26; radius: 6
                color: settingsBtnArea.containsMouse
                    ? Qt.rgba(0.3, 0.3, 0.3, 0.5)
                    : !ollamaPanel.activeView
                        ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.15)
                        : "transparent"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text {
                    anchors.centerIn: parent; text: "⚙"; font.pixelSize: 14
                    color: !ollamaPanel.activeView ? ollamaPanel.accentColor
                           : (ollamaPanel.darkMode ? "#888" : "#555")
                }
                MouseArea {
                    id: settingsBtnArea; anchors.fill: parent
                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        ollamaPanel.activeView = !ollamaPanel.activeView
                        if (!ollamaPanel.activeView) ollamaPanel.loadSettings()
                    }
                }
            }
        }

        // ── Source toggle ─────────────────────────────────────────────────
        Row {
            width: parent.width
            spacing: 6

            Repeater {
                model: ["native", "docker"]

                delegate: Rectangle {
                    width: (parent.width - 6) / 2
                    height: 28; radius: 6
                    property bool isActive: ollamaPanel.currentSource === modelData
                    color: isActive
                        ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.25)
                        : (ollamaPanel.darkMode ? Qt.rgba(0.15, 0.15, 0.15, 0.8) : Qt.rgba(0.9, 0.9, 0.9, 0.8))
                    border.width: 1
                    border.color: isActive
                        ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.5)
                        : (ollamaPanel.darkMode ? "#333" : "#ccc")
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6

                        Rectangle {
                            width: 6; height: 6; radius: 3
                            anchors.verticalCenter: parent.verticalCenter
                            property bool online: modelData === "native" ? ollamaPanel.nativeOnline : ollamaPanel.dockerOnline
                            color: online ? "#4caf50" : (ollamaPanel.darkMode ? "#444" : "#bbb")
                            Behavior on color { ColorAnimation { duration: 300 } }
                        }
                        Text {
                            text: modelData === "native" ? "Native" : "Docker"
                            font.pixelSize: 12
                            font.weight: isActive ? Font.DemiBold : Font.Normal
                            color: isActive ? ollamaPanel.accentColor : (ollamaPanel.darkMode ? "#888" : "#666")
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: ollamaPanel.currentSource = modelData
                    }
                }
            }
        }

        // Divider
        Rectangle {
            width: parent.width; height: 1
            color: ollamaPanel.darkMode ? "#3a3a3a" : "#d0d0d0"
        }

        // ── Models view ───────────────────────────────────────────────────
        Rectangle {
            width: parent.width
            height: ollamaPanel.height - 120
            radius: 8
            color: ollamaPanel.darkMode
                ? Qt.rgba(0.1, 0.1, 0.1, 0.5)
                : Qt.rgba(0.9, 0.9, 0.9, 0.8)
            border.width: 1
            border.color: ollamaPanel.darkMode
                ? Qt.rgba(0.23, 0.23, 0.23, 0.5)
                : Qt.rgba(0.7, 0.7, 0.7, 0.8)
            clip: true
            visible: ollamaPanel.activeView

            // ── Loading: pulsating dot ───────────────────────────────────
            Item {
                anchors.centerIn: parent
                width: 48; height: 60
                visible: ollamaPanel.isLoading

                // Ripple A
                Rectangle {
                    id: rippleA
                    anchors.centerIn: parent
                    width: 40; height: 40; radius: 20
                    color: "transparent"
                    border.width: 1.5
                    border.color: ollamaPanel.accentColor
                    scale: 0.25; opacity: 0
                    SequentialAnimation {
                        running: ollamaPanel.isLoading; loops: Animation.Infinite
                        ParallelAnimation {
                            NumberAnimation { target: rippleA; property: "scale";   from: 0.25; to: 1.0; duration: 1100; easing.type: Easing.OutCubic }
                            NumberAnimation { target: rippleA; property: "opacity"; from: 0.55; to: 0;   duration: 1100; easing.type: Easing.OutCubic }
                        }
                        PauseAnimation { duration: 300 }
                    }
                }

                // Ripple B (versetzt)
                Rectangle {
                    id: rippleB
                    anchors.centerIn: parent
                    width: 40; height: 40; radius: 20
                    color: "transparent"
                    border.width: 1.5
                    border.color: ollamaPanel.accentColor
                    scale: 0.25; opacity: 0
                    SequentialAnimation {
                        running: ollamaPanel.isLoading; loops: Animation.Infinite
                        PauseAnimation { duration: 700 }
                        ParallelAnimation {
                            NumberAnimation { target: rippleB; property: "scale";   from: 0.25; to: 1.0; duration: 1100; easing.type: Easing.OutCubic }
                            NumberAnimation { target: rippleB; property: "opacity"; from: 0.55; to: 0;   duration: 1100; easing.type: Easing.OutCubic }
                        }
                    }
                }

                // Center dot
                Rectangle {
                    id: centerDot
                    anchors.centerIn: parent
                    width: 10; height: 10; radius: 5
                    color: ollamaPanel.accentColor
                    SequentialAnimation {
                        running: ollamaPanel.isLoading; loops: Animation.Infinite
                        NumberAnimation { target: centerDot; property: "scale"; from: 1.0; to: 0.7; duration: 500; easing.type: Easing.InOutSine }
                        NumberAnimation { target: centerDot; property: "scale"; from: 0.7; to: 1.0; duration: 500; easing.type: Easing.InOutSine }
                        PauseAnimation { duration: 400 }
                    }
                }

                Text {
                    anchors.top: parent.verticalCenter
                    anchors.topMargin: 26
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Lang.get("ollama.loading")
                    font.pixelSize: 11
                    color: ollamaPanel.darkMode ? "#666" : "#999"
                }
            }

            Column {
                anchors.centerIn: parent
                spacing: 8
                visible: !ollamaPanel.isLoading && !ollamaPanel.ollamaReachable
                ProjectIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "bolt"; font.pixelSize: 28; color: "#ef5350" }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ollamaPanel.currentSource === "docker" ? Lang.get("ollama.offlineDocker") : Lang.get("ollama.offlineNative")
                    font.pixelSize: 13; color: ollamaPanel.darkMode ? "#888" : "#666"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ollamaPanel.apiUrl
                    font.pixelSize: 11; color: ollamaPanel.darkMode ? "#555" : "#999"
                }
            }

            Column {
                anchors.centerIn: parent; spacing: 8
                visible: !ollamaPanel.isLoading && ollamaPanel.ollamaReachable && ollamaPanel.modelsData.length === 0
                ProjectIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "assistant"; font.pixelSize: 28 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Lang.get("ollama.noModels")
                    font.pixelSize: 13; color: ollamaPanel.darkMode ? "#888" : "#666"
                }
            }

            // Timer for scroll buttons (sibling of ListView, not inside it)
            Timer {
                id: scrollButtonTimer
                interval: 2000
                onTriggered: ollamaPanel.showScrollButtons = false
            }

            ListView {
                id: modelsList
                anchors.fill: parent; anchors.margins: 5
                spacing: 4; clip: true
                model: ollamaPanel.modelsData
                visible: !ollamaPanel.isLoading && ollamaPanel.ollamaReachable

                onMovementStarted: {
                    ollamaPanel.showScrollButtons = true
                    scrollButtonTimer.restart()
                }

                delegate: Rectangle {
                    id: modelCard
                    width: ListView.view.width; height: 62; radius: 6
                    color: (cardArea.containsMouse || btnLoad.containsMouse || btnDelete.containsMouse)
                        ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4)
                    Behavior on color { ColorAnimation { duration: 150 } }

                    Row {
                        anchors { top: parent.top; left: parent.left; bottom: parent.bottom; margins: 10 }
                        width: parent.width - 102
                        spacing: 10

                        Item {
                            width: 10; height: 10
                            anchors.verticalCenter: parent.verticalCenter

                            // Outer ring (always visible)
                            Rectangle {
                                anchors.fill: parent; radius: 5
                                color: "transparent"
                                border.width: 1.5
                                border.color: modelData.loaded ? "#4caf50" : (ollamaPanel.darkMode ? "#555" : "#bbb")
                                Behavior on border.color { ColorAnimation { duration: 300 } }
                            }
                            // Inner fill (only when loaded)
                            Rectangle {
                                anchors.centerIn: parent
                                width: 5; height: 5; radius: 2.5
                                color: "#4caf50"
                                opacity: modelData.loaded ? 1.0 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 300 } }
                            }
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 3; width: parent.width - 18

                            Text {
                                text: modelData.name; font.pixelSize: 12; font.weight: Font.Medium
                                color: ollamaPanel.darkMode ? "#ffffff" : "#111111"
                                elide: Text.ElideRight; width: parent.width
                                renderType: Text.NativeRendering
                            }
                            Row {
                                spacing: 6
                                Text { text: modelData.sizeGb + " GB"; font.pixelSize: 11; color: ollamaPanel.darkMode ? "#777" : "#666" }
                                Text { visible: modelData.params !== ""; text: modelData.params; font.pixelSize: 11; color: ollamaPanel.darkMode ? "#555" : "#999" }
                                Text { visible: modelData.quant !== "";  text: modelData.quant;  font.pixelSize: 11; color: ollamaPanel.darkMode ? "#555" : "#999" }
                            }
                            Text {
                                visible: modelData.loaded && modelData.vramGb !== ""
                                text: "VRAM: " + modelData.vramGb + " GB"
                                font.pixelSize: 10; color: "#4caf50"; opacity: 0.8
                            }
                            Text {
                                visible: !modelData.loaded
                                text: Lang.get("ollama.onDisk")
                                font.pixelSize: 10
                                color: ollamaPanel.darkMode ? "#555" : "#aaa"
                            }
                        }
                    }

                    MouseArea {
                        id: cardArea
                        anchors { top: parent.top; left: parent.left; bottom: parent.bottom }
                        width: parent.width - 102
                        hoverEnabled: true
                    }

                    Row {
                        anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        spacing: 4

                        Rectangle {
                            width: 28; height: 28; radius: 6
                            color: btnLoad.containsMouse
                                ? (modelData.loaded ? Qt.rgba(0.85, 0.25, 0.25, 0.4) : Qt.rgba(0.25, 0.7, 0.25, 0.4))
                                : Qt.rgba(0.18, 0.18, 0.18, 0.8)
                            border.width: 1
                            border.color: modelData.loaded ? Qt.rgba(0.7, 0.3, 0.3, 0.4) : Qt.rgba(0.3, 0.65, 0.3, 0.4)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text { anchors.centerIn: parent; text: modelData.loaded ? "⏹" : "▶"; font.pixelSize: 11; color: modelData.loaded ? "#ef5350" : "#66bb6a" }
                            MouseArea {
                                id: btnLoad; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var ka = modelData.loaded ? "0" : "-1"
                                    actionProc.command = ["bash", "-c",
                                        "curl -s -X POST " + ollamaPanel.apiUrl + "/api/generate " +
                                        "-d '{\"model\":\"" + modelData.name + "\",\"keep_alive\":" + ka + "}' > /dev/null &"]
                                    actionProc.running = true
                                }
                            }
                        }

                        Rectangle {
                            width: 28; height: 28; radius: 6
                            color: btnTerminal.containsMouse ? Qt.rgba(0.2, 0.45, 0.7, 0.35) : Qt.rgba(0.18, 0.18, 0.18, 0.8)
                            border.width: 1; border.color: Qt.rgba(0.3, 0.5, 0.75, 0.4)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text { anchors.centerIn: parent; text: ">_"; font.pixelSize: 9; font.family: "Monospace"; color: "#64b5f6" }
                            MouseArea {
                                id: btnTerminal; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var host = ollamaPanel.apiUrl.replace("http://", "")
                                    var innerCmd = ollamaPanel.currentSource === "docker"
                                        ? "docker exec -it ollama ollama run " + modelData.name
                                        : "OLLAMA_HOST=" + host + " ollama run " + modelData.name
                                    actionProc.command = ["bash", "-c",
                                        ollamaPanel.defaultTerminal + " -e bash -c '" +
                                        innerCmd + "; exec bash' & disown"]
                                    actionProc.running = true
                                }
                            }
                        }

                        Rectangle {
                            width: 28; height: 28; radius: 6
                            color: btnDelete.containsMouse ? Qt.rgba(0.85, 0.2, 0.2, 0.35) : Qt.rgba(0.18, 0.18, 0.18, 0.8)
                            border.width: 1; border.color: Qt.rgba(0.6, 0.2, 0.2, 0.4)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 11; color: "#ef5350" }
                            MouseArea {
                                id: btnDelete; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    actionProc.command = ["bash", "-c",
                                        "curl -s -X DELETE " + ollamaPanel.apiUrl + "/api/delete " +
                                        "-d '{\"model\":\"" + modelData.name + "\"}' > /dev/null"]
                                    actionProc.running = true
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Settings view ─────────────────────────────────────────────────
        Rectangle {
            width: parent.width
            height: ollamaPanel.height - 120
            radius: 8
            color: ollamaPanel.darkMode ? Qt.rgba(0.1, 0.1, 0.1, 0.5) : Qt.rgba(0.9, 0.9, 0.9, 0.8)
            border.width: 1
            border.color: ollamaPanel.darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)
            clip: true
            visible: !ollamaPanel.activeView

            Column {
                anchors.fill: parent; anchors.margins: 14; spacing: 14

                // Context length with Slider
                Column {
                    id: ctxColumn
                    width: parent.width; spacing: 10
                    property int ctxValue: parseInt(ollamaPanel.currentCtx) || 4096

                    // Update slider when currentCtx changes (from loadSettings)
                    Connections {
                        target: ollamaPanel
                        function onCurrentCtxChanged() {
                            var newVal = parseInt(ollamaPanel.currentCtx) || 4096
                            console.log("[OllamaPanel] currentCtx changed to:", ollamaPanel.currentCtx, "→ updating slider to:", newVal)
                            ctxSlider.value = newVal
                            ctxColumn.ctxValue = newVal
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 8

                        Text {
                            text: Lang.get("ollama.contextLength")
                            font.pixelSize: 12; font.weight: Font.Medium
                            color: ollamaPanel.darkMode ? "#ccc" : "#333"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Item { width: parent.width - 250; height: 1 }

                        Text {
                            text: ctxColumn.ctxValue.toString()
                            font.pixelSize: 14; font.weight: Font.Bold
                            color: ctxColumn.ctxValue > 32768 ? "#f39c12" : (ctxColumn.ctxValue > 65536 ? "#e74c3c" : ollamaPanel.accentColor)
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Rectangle {
                            width: 45; height: 24; radius: 4
                            color: maxBtn.containsMouse ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.2) : "transparent"
                            border.width: 1
                            border.color: ollamaPanel.accentColor
                            anchors.verticalCenter: parent.verticalCenter

                            Text {
                                anchors.centerIn: parent
                                text: "MAX"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: ollamaPanel.accentColor
                            }

                            MouseArea {
                                id: maxBtn
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    ctxSlider.value = 131072
                                    ctxColumn.ctxValue = 131072
                                }
                            }
                        }
                    }

                    // Slider
                    Item {
                        width: parent.width; height: 30

                        Rectangle {
                            id: sliderTrack
                            width: parent.width
                            height: 4
                            radius: 2
                            y: 13
                            color: ollamaPanel.darkMode ? "#2a2a2a" : "#ddd"

                            Rectangle {
                                width: (ctxSlider.value - ctxSlider.from) / (ctxSlider.to - ctxSlider.from) * parent.width
                                height: parent.height
                                radius: parent.radius
                                color: ctxColumn.ctxValue > 65536 ? "#e74c3c" : (ctxColumn.ctxValue > 32768 ? "#f39c12" : ollamaPanel.accentColor)
                            }
                        }

                        Rectangle {
                            id: sliderHandle
                            width: 18; height: 18
                            radius: 9
                            x: (ctxSlider.value - ctxSlider.from) / (ctxSlider.to - ctxSlider.from) * (sliderTrack.width - width)
                            y: 6
                            color: sliderMouse.pressed ? Qt.lighter(ollamaPanel.accentColor, 1.2) : ollamaPanel.accentColor
                            border.width: 2
                            border.color: ollamaPanel.darkMode ? "#fff" : "#333"

                            MouseArea {
                                id: sliderMouse
                                anchors.fill: parent
                                anchors.margins: -10
                                drag.target: parent
                                drag.axis: Drag.XAxis
                                drag.minimumX: 0
                                drag.maximumX: sliderTrack.width - parent.width
                                cursorShape: Qt.PointingHandCursor

                                onPositionChanged: {
                                    if (drag.active) {
                                        var ratio = parent.x / (sliderTrack.width - parent.width)
                                        var rawValue = ctxSlider.from + ratio * (ctxSlider.to - ctxSlider.from)
                                        // Snap to 1024 increments
                                        var snapped = Math.round(rawValue / 1024) * 1024
                                        ctxSlider.value = Math.max(ctxSlider.from, Math.min(ctxSlider.to, snapped))
                                        ctxColumn.ctxValue = ctxSlider.value
                                    }
                                }
                            }

                            property int ctxSliderValue: 4096
                            Component.onCompleted: {
                                ctxSlider.value = parseInt(ollamaPanel.currentCtx) || 4096
                                ctxColumn.ctxValue = ctxSlider.value
                            }
                        }

                        property alias value: ctxSlider.value
                        property int from: 2048
                        property int to: 131072

                        QtObject {
                            id: ctxSlider
                            property int value: 4096
                            property int from: 2048
                            property int to: 131072
                        }
                    }

                    // Warning text
                    Text {
                        visible: parent.ctxValue > 32768
                        text: parent.ctxValue > 65536
                            ? "⚠️ Very high! May cause slowness or crashes"
                            : "⚠️ High context - may impact performance"
                        font.pixelSize: 10
                        color: parent.ctxValue > 65536 ? "#e74c3c" : "#f39c12"
                        width: parent.width
                        wrapMode: Text.Wrap
                    }

                    // Quick presets
                    Row {
                        width: parent.width
                        spacing: 6

                        Repeater {
                            model: [2048, 4096, 8192, 16384, 32768, 65536, 131072]

                            Rectangle {
                                width: (parent.width - 36) / 7
                                height: 22
                                radius: 4
                                color: ctxColumn.ctxValue === modelData
                                    ? ollamaPanel.accentColor
                                    : (presetHover.containsMouse ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.15) : "transparent")
                                border.width: 1
                                border.color: ctxColumn.ctxValue === modelData
                                    ? ollamaPanel.accentColor
                                    : Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.3)

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData >= 1024 ? (modelData / 1024) + "K" : modelData.toString()
                                    font.pixelSize: 9
                                    color: ctxColumn.ctxValue === modelData
                                        ? (ollamaPanel.darkMode ? "#ffffff" : "#111111")
                                        : ollamaPanel.accentColor
                                }

                                MouseArea {
                                    id: presetHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        ctxSlider.value = modelData
                                        ctxColumn.ctxValue = modelData
                                    }
                                }
                            }
                        }
                    }

                    // Save button
                    Rectangle {
                        width: parent.width; height: 32; radius: 6
                        color: saveBtn.containsMouse
                            ? Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.3)
                            : Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.15)
                        border.width: 1
                        border.color: Qt.rgba(ollamaPanel.accentColor.r, ollamaPanel.accentColor.g, ollamaPanel.accentColor.b, 0.5)
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Text {
                            anchors.centerIn: parent
                            text: Lang.get("ollama.btnSave") + " & Restart"
                            font.pixelSize: 11
                            color: ollamaPanel.accentColor
                        }

                        MouseArea {
                            id: saveBtn
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var val = ctxColumn.ctxValue.toString()
                                console.log("[OllamaPanel] Saving context:", val, "for source:", ollamaPanel.currentSource)

                                if (ollamaPanel.currentSource === "docker") {
                                    // Docker: edit docker-compose.yml
                                    writeCtxProc.command = ["python3", "-c",
                                        "import re\n" +
                                        "path = '" + ollamaPanel.composeFile + "'\n" +
                                        "with open(path) as f: content = f.read()\n" +
                                        "pattern = r'OLLAMA_NUM_CTX=\\d+'\n" +
                                        "replacement = 'OLLAMA_NUM_CTX=" + val + "'\n" +
                                        "if re.search(pattern, content):\n" +
                                        "    content = re.sub(pattern, replacement, content)\n" +
                                        "else:\n" +
                                        "    content = content.replace('environment:', 'environment:\\n      - OLLAMA_NUM_CTX=" + val + "')\n" +
                                        "with open(path, 'w') as f: f.write(content)\n"
                                    ]
                                } else {
                                    // Native: create systemd override
                                    writeCtxProc.command = ["bash", "-c",
                                        "mkdir -p ~/.config/systemd/user/ollama.service.d && " +
                                        "echo -e '[Service]\\nEnvironment=\"OLLAMA_NUM_CTX=" + val + "\"' > ~/.config/systemd/user/ollama.service.d/override.conf && " +
                                        "systemctl --user daemon-reload && " +
                                        "systemctl --user restart ollama.service"
                                    ]
                                }
                                writeCtxProc.running = true
                                ollamaPanel.currentCtx = val
                            }
                        }
                    }
                }

                Rectangle { width: parent.width; height: 1; color: ollamaPanel.darkMode ? "#2a2a2a" : "#ddd" }

                // Model location
                Column {
                    width: parent.width; spacing: 6

                    Text {
                        text: "Model Location"
                        font.pixelSize: 12; font.weight: Font.Medium
                        color: ollamaPanel.darkMode ? "#ccc" : "#333"
                    }
                    Rectangle {
                        width: parent.width; height: 32; radius: 6
                        color: ollamaPanel.darkMode ? "#141414" : "#f0f0f0"
                        border.color: ollamaPanel.darkMode ? "#2a2a2a" : "#d0d0d0"; border.width: 1
                        Text {
                            anchors.fill: parent; anchors.margins: 8
                            verticalAlignment: Text.AlignVCenter
                            text: ollamaPanel.currentSource === "docker"
                                ? "Docker Volume: ollama"
                                : "~/.ollama/models"
                            font.pixelSize: 11; color: ollamaPanel.darkMode ? "#666" : "#999"
                        }
                    }

                    // Erkannter Port + Status
                    Row {
                        spacing: 8
                        Rectangle {
                            width: 6; height: 6; radius: 3
                            anchors.verticalCenter: parent.verticalCenter
                            color: (ollamaPanel.currentSource === "native" ? ollamaPanel.nativeOnline : ollamaPanel.dockerOnline)
                                ? "#4caf50" : "#ef5350"
                            Behavior on color { ColorAnimation { duration: 300 } }
                        }
                        Text {
                            property string url: ollamaPanel.currentSource === "docker"
                                ? ollamaPanel.dockerUrl : ollamaPanel.nativeUrl
                            text: url !== "" ? url : "nicht erkannt"
                            font.pixelSize: 11
                            color: ollamaPanel.darkMode ? "#555" : "#999"
                        }
                    }
                }

                Rectangle { width: parent.width; height: 1; color: ollamaPanel.darkMode ? "#2a2a2a" : "#ddd" }

                // Service control
                Column {
                    width: parent.width; spacing: 8

                    Text {
                        text: ollamaPanel.currentSource === "docker" ? "Container" : "Service"
                        font.pixelSize: 12; font.weight: Font.Medium
                        color: ollamaPanel.darkMode ? "#ccc" : "#333"
                    }

                    Row {
                        width: parent.width; spacing: 6

                        Repeater {
                            model: 3
                            delegate: Rectangle {
                                property bool srcOnline: ollamaPanel.currentSource === "native"
                                    ? ollamaPanel.nativeOnline : ollamaPanel.dockerOnline
                                // Start (0): nur wenn offline · Stop (1) + Restart (2): nur wenn online
                                visible: index === 0 ? !srcOnline : srcOnline
                                width: visible ? (srcOnline ? (parent.width - 6) / 2 : parent.width) : 0
                                height: 32; radius: 6
                                property string btnLabel: index === 0 ? "▶ " + Lang.get("ollama.btnStart") : index === 1 ? "⏹ " + Lang.get("ollama.btnStop") : "↺ " + Lang.get("ollama.btnRestart")
                                property string btnColor: index === 0 ? "#66bb6a" : index === 1 ? "#ef5350" : "#ffa726"
                                property string btnCmd: {
                                    var base = ollamaPanel.currentSource === "docker"
                                        ? "cd \"$HOME/docker/ollama\" && docker compose "
                                        : "systemctl --user "
                                    return base + (index === 0 ? "up -d" : index === 1 ? "stop ollama" : "restart ollama")
                                }
                                color: svcBtnArea.containsMouse
                                    ? Qt.rgba(0.25, 0.25, 0.25, 0.8)
                                    : Qt.rgba(0.18, 0.18, 0.18, 0.6)
                                border.width: 1; border.color: "#333"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text { anchors.centerIn: parent; text: btnLabel; font.pixelSize: 11; color: btnColor }
                                MouseArea {
                                    id: svcBtnArea; anchors.fill: parent
                                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        actionProc.command = ["bash", "-c", parent.btnCmd]
                                        actionProc.running = true
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Scroll buttons - positioned absolutely to appear over the models list
        Rectangle {
            id: scrollTopBtn
            x: ollamaPanel.width - 44  // far right
            y: 140  // Below header
            width: 32; height: 32; radius: 16
            color: ollamaPanel.darkMode ? Qt.rgba(0.18, 0.18, 0.18, 0.95) : Qt.rgba(0.95, 0.95, 0.95, 0.95)
            border.width: 1; border.color: ollamaPanel.darkMode ? "#444" : "#ccc"
            visible: ollamaPanel.showScrollButtons && modelsList.contentY > 50 && modelsList.visible
            opacity: visible ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: 200 } }
            z: 100

            Text {
                anchors.centerIn: parent
                text: "↑"; font.pixelSize: 18
                color: ollamaPanel.darkMode ? "#fff" : "#333"
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: modelsList.positionViewAtBeginning()
            }
        }

        Rectangle {
            id: scrollBottomBtn
            x: ollamaPanel.width - 44  // far right
            y: ollamaPanel.height - 48
            width: 32; height: 32; radius: 16
            color: ollamaPanel.darkMode ? Qt.rgba(0.18, 0.18, 0.18, 0.95) : Qt.rgba(0.95, 0.95, 0.95, 0.95)
            border.width: 1; border.color: ollamaPanel.darkMode ? "#444" : "#ccc"
            visible: ollamaPanel.showScrollButtons && !modelsList.atYEnd && modelsList.visible
            opacity: visible ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: 200 } }
            z: 100

            Text {
                anchors.centerIn: parent
                text: "↓"; font.pixelSize: 18
                color: ollamaPanel.darkMode ? "#fff" : "#333"
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: modelsList.positionViewAtEnd()
            }
        }
    }
}
