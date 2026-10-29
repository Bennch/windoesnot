//@ pragma UseQApplication

import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.SystemTray
import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Qt5Compat.GraphicalEffects
import QtQml.Models
import "widgets"
import "IconMap.js" as IconMap
import "i18n/Lang.js" as Lang

ShellRoot {
    id: desktopShell

// Current Does window (null while it is being rebuilt).
property var copilotWindow: copilotWindowLoader.item

// FocusGrab Warmup Timer - initialisiert alle HyprlandFocusGrabs beim Start
Timer {
    id: focusGrabWarmupTimer
    interval: 500  // Warte 500ms nach Start
    running: true
    repeat: false
    onTriggered: {
        console.log("Warming up FocusGrabs...")
        // Öffne und schließe jedes Menü kurz um FocusGrab zu initialisieren
        startMenu.visible = true
        settingsMenu.visible = true
        audioWindow.visible = true
        bluetoothWindow.visible = true
        networkWindow.visible = true
        calendarWindow.visible = true
        powerMenu.visible = true
        powerSubMenu.visible = true
        searchWindow.visible = true
        appContextMenu.visible = true
        taskbarBgMenu.visible = true
        weatherPopup.visible = true
        if (copilotWindow) copilotWindow.visible = true

        // Schließe alles nach kurzer Zeit
        Qt.callLater(function() {
            startMenu.visible = false
            settingsMenu.visible = false
            audioWindow.visible = false
            bluetoothWindow.visible = false
            networkWindow.visible = false
            nearbyWindow.visible = false
            calendarWindow.visible = false
            powerMenu.visible = false
            powerSubMenu.visible = false
            searchWindow.visible = false
            appContextMenu.visible = false
            taskbarBgMenu.visible = false
            weatherPopup.visible = false
            dockerWindow.visible = false
            ollamaWindow.visible = false
            if (copilotWindow) copilotWindow.visible = false
            console.log("FocusGrabs warmed up!")
        })
    }
}

// App Override System
Loader {
    id: appReplaceLoader
    source: "replace.qml"
}

property var appReplace: appReplaceLoader.item

GlobalShortcut {
    name: "toggle-startmenu"
    description: "Toggle Start Menu"
    onPressed: {
        settingsMenu.visible = false
        audioWindow.visible = false
        bluetoothWindow.visible = false
        networkWindow.visible = false
        nearbyWindow.visible = false
        calendarWindow.visible = false
        startMenu.visible = !startMenu.visible
    }
}

GlobalShortcut {
    name: "toggle-settings"
    description: "Toggle Settings Menu"
    onPressed: {
        startMenu.visible = false
        audioWindow.visible = false
        bluetoothWindow.visible = false
        networkWindow.visible = false
        nearbyWindow.visible = false
        calendarWindow.visible = false
        settingsMenu.visible = !settingsMenu.visible
    }
}

Timer {
    id: settingsReopenTimer
    interval: 100  // Erhöht von 10ms auf 100ms für mehr Zuverlässigkeit
    running: false
    repeat: false
    onTriggered: {
        settingsMenu.visible = true
    }
}

GlobalShortcut {
    name: "show-settings"
    description: "Show Settings Menu (always open)"
    onPressed: {
        startMenu.visible = false
        audioWindow.visible = false
        bluetoothWindow.visible = false
        networkWindow.visible = false
        nearbyWindow.visible = false
        calendarWindow.visible = false
        // WICHTIG: Erst schließen, dann mit Timer wieder öffnen um FocusGrab neu zu triggern
        settingsMenu.visible = false
        settingsReopenTimer.start()
    }
}

// Snap Preview Manager - Loaded from separate file
SnapManager {
    id: snapManager
    settingsMenu: settingsMenu
}

PanelWindow {
    id: panelWindow
    anchors { bottom: true; left: true; right: true }
    implicitHeight: 45
    color: settingsMenu.darkMode ? Qt.rgba(0.11, 0.11, 0.12, 0.78) : Qt.rgba(0.95, 0.95, 0.95, 0.85)

    property bool menuVisible: false
    property var taskbarApps: []
    property string taskbarAlignment: "center"  // "center" oder "left"
    property var openWindows: ({})  // Map von app names zu window addresses
    property var storeWindows: []  // Store windows, shown on the fixed store button instead of as an app
    property var windowLastWorkspace: ({})  // Track last known workspace for each window address
    property string internalCopilotCmd: "__internal_copilot__"
    property bool _copilotJustOpened: false
    property var primaryScreen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor) return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }
    screen: primaryScreen
    property real weatherScaleRaw: primaryScreen ? (primaryScreen.height / 1080.0) : 1.0
    property real weatherScale: Math.max(1.0, Math.min(1.8, weatherScaleRaw))
    property int weatherInnerMargin: Math.round(4 * weatherScale)
    property int weatherInnerSpacing: Math.round(4 * weatherScale)
    property int weatherIconSize: Math.min(40, Math.round(32 * (1.0 + (weatherScale - 1.0) * 0.6)))
    property int weatherDescFontSize: Math.round(9 * weatherScale)
    property int weatherTempFontSize: Math.round(10 * weatherScale)
    property int weatherTextWidth: Math.round(54 * weatherScale)
    property int weatherSlotWidth: weatherIconSize + weatherTextWidth + (weatherInnerMargin * 2) + weatherInnerSpacing

    Timer {
        id: copilotOpenGuard
        interval: 400
        repeat: false
        onTriggered: panelWindow._copilotJustOpened = false
    }

    ListModel { id: taskbarAppsModel }
    ListModel { id: trayIconModel }

    // Poll Hyprland for open windows
    Timer {
        interval: 1000  // Update every second
        running: true
        repeat: true
        onTriggered: {
            hyprlandWindowProc.running = true
        }
    }

    Process {
        id: hyprlandWindowProc
        command: ["bash", "-c", "windoesnot-hyprctl clients -j"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var clients = JSON.parse(this.text)
                    var newOpenWindows = {}
                    var temporaryApps = []  // Apps that are open but not pinned
                    var newStoreWindows = []

                    // Helper function to normalize strings for matching (remove spaces, dashes, etc.)
                    function normalize(str) {
                        return str.toLowerCase().replace(/[\s\-_]/g, "")
                    }

                    // IconMap is generated at session start. Quickshell watches the
                    // application directories, so apps installed later still resolve.
                    function windowIcon(appClass) {
                        // System dialogs without a desktop entry
                        if (appClass.toLowerCase() === "polkit-gnome-authentication-agent-1") return "system-lock-screen"
                        var mapped = IconMap.smartFix(appClass)
                        if (mapped !== appClass && mapped !== appClass.toLowerCase()) return mapped
                        var entry = appClass.length > 0 ? DesktopEntries.heuristicLookup(appClass) : null
                        return entry && entry.icon ? entry.icon : mapped
                    }

                    for (var i = 0; i < clients.length; i++) {
                        var client = clients[i]
                        var clientClass = client.class ? client.class.toLowerCase() : ""
                        var clientInitialClass = client.initialClass ? client.initialClass.toLowerCase() : ""
                        var clientTitle = client.title ? client.title.toLowerCase() : ""
                        // The store has its own fixed taskbar button (unless disabled).
                        var isStoreWindow = clientClass === "me.windoesnot.store" && settingsMenu.showStoreButton
                        if (isStoreWindow) {
                            newStoreWindows.push({
                                address: client.address,
                                focused: client.focusHistoryID === 0,
                                hidden: (client.workspace.name || "").includes("special:minimized")
                            })
                        }

                        // Map window class/title to taskbar app names
                        for (var j = 0; j < panelWindow.taskbarApps.length; j++) {
                            var app = panelWindow.taskbarApps[j]
                            var appName = app.name.toLowerCase()
                            var appCmd = app.cmd.toLowerCase()

                            // Normalized versions for flexible matching
                            var appNameNorm = normalize(appName)
                            var clientClassNorm = normalize(clientClass)

                            // Extract executable name from command (e.g., "nautilus" from "/usr/bin/nautilus")
                            var cmdParts = appCmd.split(/[\s\/]/).filter(function(p) { return p.length > 0 })
                            var execName = ""
                            for (var k = cmdParts.length - 1; k >= 0; k--) {
                                if (cmdParts[k].length > 2 && !cmdParts[k].startsWith("-")) {
                                    execName = cmdParts[k]
                                    break
                                }
                            }
                            var execNameNorm = normalize(execName)

                            var matched = false

                            // Match strategies (in order of preference):
                            // 1. Exact class match
                            if (clientClass === appName || clientClass === execName) {
                                matched = true
                            }
                            // 2. Class contains app name or vice versa
                            else if (clientClass.includes(appName) || appName.includes(clientClass)) {
                                matched = true
                            }
                            // 3. Class contains executable name or vice versa
                            else if (execName && (clientClass.includes(execName) || execName.includes(clientClass))) {
                                matched = true
                            }
                            // 4. Initial class match
                            else if (clientInitialClass && (clientInitialClass.includes(appName) ||
                                     appName.includes(clientInitialClass) ||
                                     (execName && clientInitialClass.includes(execName)))) {
                                matched = true
                            }
                            // 5. Check if class parts match (e.g., "org.gnome.Nautilus" contains "nautilus")
                            else if (clientClass.includes(".")) {
                                var classParts = clientClass.split(".")
                                // Only check the last part (e.g., "Nautilus" from "org.gnome.Nautilus")
                                // This avoids false matches on generic parts like "gnome"
                                var lastPart = classParts[classParts.length - 1].toLowerCase()
                                var lastPartNorm = normalize(lastPart)

                                // Try exact and normalized matches
                                if (lastPart === appName || lastPart === execName ||
                                    appName.includes(lastPart) || lastPart.includes(appName) ||
                                    (execName && (execName.includes(lastPart) || lastPart.includes(execName))) ||
                                    lastPartNorm === appNameNorm || lastPartNorm === execNameNorm) {
                                    matched = true
                                }
                            }

                            if (matched) {
                                var isMinimized = (client.workspace.name || "").includes("special:minimized")

                                // Track last known workspace for restore
                                if (!isMinimized) {
                                    panelWindow.windowLastWorkspace[client.address] = client.workspace.id
                                }

                                // Get the workspace to restore to (either current or last known)
                                var restoreWorkspace = client.workspace.id
                                if (isMinimized && panelWindow.windowLastWorkspace[client.address] !== undefined) {
                                    restoreWorkspace = panelWindow.windowLastWorkspace[client.address]
                                }

                                var windowInfo = {
                                    address: client.address,
                                    title: client.title || "",
                                    workspace: client.workspace.id,
                                    workspaceName: client.workspace.name || "",
                                    restoreWorkspace: restoreWorkspace,
                                    monitor: client.monitor,
                                    focused: client.focusHistoryID === 0,
                                    zOrder: client.focusHistoryID !== undefined ? client.focusHistoryID : 9999,
                                    hidden: isMinimized,
                                    at: client.at || [0, 0],
                                    size: client.size || [0, 0]
                                }

                                // Store all windows for this app in an array
                                if (!newOpenWindows[app.name]) {
                                    newOpenWindows[app.name] = []
                                }
                                newOpenWindows[app.name].push(windowInfo)

                                break
                            }
                        }

                        // If no match found in taskbar, add as temporary app
                        // Filter out Quickshell's internal windows
                        var isQuickshellInternal = clientClass.toLowerCase() === "quickshell" ||
                                                   clientClass.toLowerCase().includes("quickshell")

                        if (!matched && !isStoreWindow && !isQuickshellInternal && clientClass.length > 0 && client.workspace.name !== "special:minimized") {
                            var appName = client.initialClass || client.class || client.title
                            // Only add if not already in temporary apps
                            var alreadyAdded = false
                            for (var t = 0; t < temporaryApps.length; t++) {
                                if (temporaryApps[t].name === appName) {
                                    alreadyAdded = true
                                    break
                                }
                            }
                            if (!alreadyAdded) {
                                // Try to find the correct icon from allAppsModel first (has icon from .desktop file)
                                var iconName = null
                                var clientClassLow = (client.class || "").toLowerCase()
                                var clientNorm2 = normalize(clientClassLow)
                                var lastSeg = clientClassLow.includes(".")
                                    ? clientClassLow.split(".").pop()
                                    : clientClassLow
                                var lastSegNorm = normalize(lastSeg)

                                for (var ai = 0; ai < allAppsModel.count; ai++) {
                                    var cand = allAppsModel.get(ai)
                                    if (cand.customIcon) continue
                                    var cNameNorm = normalize(cand.name.toLowerCase())
                                    var cCmdParts = cand.cmd.toLowerCase().split(/[\s\/]/).filter(function(p) { return p.length > 2 && !p.startsWith("-") })
                                    var cExec = cCmdParts.length > 0 ? cCmdParts[cCmdParts.length - 1] : ""
                                    var cExecNorm = normalize(cExec)
                                    if (clientNorm2 === cNameNorm || clientNorm2 === cExecNorm ||
                                        lastSegNorm === cNameNorm || lastSegNorm === cExecNorm) {
                                        iconName = cand.icon
                                        break
                                    }
                                }

                                // Fall back to IconMap heuristic if no match in allAppsModel
                                if (iconName === null) {
                                    iconName = windowIcon(client.class || "")
                                }

                                temporaryApps.push({
                                    name: appName,
                                    cmd: client.class,  // Use class as command placeholder
                                    icon: iconName,
                                    customIcon: false,
                                    temporary: true,
                                    pinned: false
                                })

                                var windowInfo = {
                                    address: client.address,
                                    title: client.title || "",
                                    workspace: client.workspace.id,
                                    workspaceName: client.workspace.name || "",
                                    focused: client.focusHistoryID === 0,
                                    zOrder: client.focusHistoryID !== undefined ? client.focusHistoryID : 9999,
                                    hidden: false,
                                    at: client.at || [0, 0],
                                    size: client.size || [0, 0]
                                }

                                // Store all windows for this app in an array
                                if (!newOpenWindows[appName]) {
                                    newOpenWindows[appName] = []
                                }
                                newOpenWindows[appName].push(windowInfo)
                            }
                        }

                        // Track minimized temporary apps so they stay in the taskbar and can be restored
                        if (!matched && !isStoreWindow && !isQuickshellInternal && clientClass.length > 0 && (client.workspace.name || "").includes("special:minimized")) {
                            var tempMinName = client.initialClass || client.class || client.title
                            var alreadyAddedMin = false
                            for (var tMin = 0; tMin < temporaryApps.length; tMin++) {
                                if (temporaryApps[tMin].name === tempMinName) {
                                    alreadyAddedMin = true
                                    break
                                }
                            }
                            if (!alreadyAddedMin) {
                                var iconNameMin = windowIcon(client.class || "")
                                temporaryApps.push({
                                    name: tempMinName,
                                    cmd: client.class,
                                    icon: iconNameMin,
                                    customIcon: false,
                                    temporary: true,
                                    pinned: false
                                })
                            }
                            var tempMinRestoreWs = panelWindow.windowLastWorkspace[client.address] !== undefined
                                ? panelWindow.windowLastWorkspace[client.address]
                                : -1
                            if (!newOpenWindows[tempMinName]) {
                                newOpenWindows[tempMinName] = []
                            }
                            newOpenWindows[tempMinName].push({
                                address: client.address,
                                title: client.title || "",
                                workspace: client.workspace.id,
                                workspaceName: client.workspace.name || "",
                                restoreWorkspace: tempMinRestoreWs,
                                monitor: client.monitor,
                                focused: false,
                                hidden: true
                            })
                        }
                    }

                    // Add temporary apps to taskbar model
                    panelWindow.openWindows = newOpenWindows
                    panelWindow.storeWindows = newStoreWindows
                    panelWindow.addTemporaryApps(temporaryApps)
                } catch (e) {
                    console.log("Error parsing windoesnot-hyprctl output:", e)
                }
            }
        }
    }

    function isAppOpen(appName) {
        return panelWindow.openWindows.hasOwnProperty(appName) &&
               panelWindow.openWindows[appName].length > 0
    }

    // Returns true if any other visible window overlaps with win's rect AND is higher in the
    // z-stack (lower focusHistoryID = more recently focused = drawn on top).
    function isWindowOccluded(win) {
        if (!win || !win.at || !win.size || win.size[0] === 0 || win.hidden) return false
        var wx1 = win.at[0], wy1 = win.at[1]
        var wx2 = wx1 + win.size[0], wy2 = wy1 + win.size[1]
        var myZ = win.zOrder !== undefined ? win.zOrder : 9999
        for (var appName in panelWindow.openWindows) {
            var appWins = panelWindow.openWindows[appName]
            for (var i = 0; i < appWins.length; i++) {
                var other = appWins[i]
                if (other.address === win.address || other.hidden) continue
                if (!other.at || !other.size || other.size[0] === 0) continue
                var otherZ = other.zOrder !== undefined ? other.zOrder : 9999
                if (otherZ >= myZ) continue  // other is below or same level — not occluding
                var ox1 = other.at[0], oy1 = other.at[1]
                var ox2 = ox1 + other.size[0], oy2 = oy1 + other.size[1]
                if (ox1 < wx2 && ox2 > wx1 && oy1 < wy2 && oy2 > wy1) return true
            }
        }
        return false
    }

    function addTemporaryApps(tempApps) {
        var hasChanges = false

        // Remove old temporary apps that are no longer open
        for (var i = panelWindow.taskbarApps.length - 1; i >= 0; i--) {
            if (panelWindow.taskbarApps[i].temporary && !panelWindow.isAppOpen(panelWindow.taskbarApps[i].name)) {
                panelWindow.taskbarApps.splice(i, 1)
                hasChanges = true
            }
        }

        // Add new temporary apps
        for (var j = 0; j < tempApps.length; j++) {
            var tempApp = tempApps[j]
            var alreadyExists = false
            for (var k = 0; k < panelWindow.taskbarApps.length; k++) {
                if (panelWindow.taskbarApps[k].name === tempApp.name) {
                    alreadyExists = true
                    break
                }
            }
            if (!alreadyExists) {
                panelWindow.taskbarApps.push(tempApp)
                hasChanges = true
            }
        }

        // Only rebuild if something actually changed
        if (hasChanges) {
            rebuildTaskbarModel()
        }
    }

    // === WEATHER ===
    property int weatherCode: -1
    property real weatherTemp: 0
    property real weatherFeelsLike: 0
    property int weatherHumidity: 0
    property real weatherWindSpeed: 0
    property bool weatherIsDay: true
    property var weatherForecast: []
    property var weatherHourlyToday: []
    property string weatherUpdateTime: ""
    property int weatherActiveTab: 0
    property int weatherHourlyItemWidth: 44
    property int weatherHourlyItemSpacing: 6

    function wmoToIcon(code, isDay) {
        if (code === 0)                        return isDay ? "sunny"            : "clear"
        if (code === 1)                        return isDay ? "mostly_sunny"     : "mostly_clear"
        if (code === 2)                        return isDay ? "partly_cloudy"    : "partly_clear"
        if (code === 3)                        return "cloudy"
        if (code === 45 || code === 48)        return "mist"
        if (code >= 51 && code <= 55)          return "drizzle"
        if (code >= 61 && code <= 65)          return "showers"
        if (code === 66 || code === 67)        return "icy"
        if (code >= 71 && code <= 73)          return "scattered_snow"
        if (code >= 74 && code <= 77)          return "heavy_snow"
        if (code >= 80 && code <= 82)          return "scattered_showers"
        if (code === 85 || code === 86)        return "snow_showers"
        if (code === 95)                       return "isolated_tstorms"
        if (code === 96 || code === 99)        return "strong_tstorms"
        return "cloudy"
    }

    function wmoToDesc(code) {
        var lang = settingsMenu.uiLanguage
        if (code === 0)                        return Lang.get("weather.clear", lang)
        if (code === 1)                        return Lang.get("weather.mainlyClear", lang)
        if (code === 2)                        return Lang.get("weather.partlyCloudy", lang)
        if (code === 3)                        return Lang.get("weather.cloudy", lang)
        if (code === 45 || code === 48)        return Lang.get("weather.fog", lang)
        if (code >= 51 && code <= 55)          return Lang.get("weather.drizzle", lang)
        if (code >= 61 && code <= 65)          return Lang.get("weather.rain", lang)
        if (code === 66 || code === 67)        return Lang.get("weather.freezingRain", lang)
        if (code >= 71 && code <= 77)          return Lang.get("weather.snow", lang)
        if (code >= 80 && code <= 82)          return Lang.get("weather.showers", lang)
        if (code === 85 || code === 86)        return Lang.get("weather.snowShowers", lang)
        if (code === 95)                       return Lang.get("weather.thunderstorm", lang)
        if (code === 96 || code === 99)        return Lang.get("weather.hailstorm", lang)
        return Lang.get("weather.unknown", lang)
    }

    function weatherIconPath(code, isDay) {
        var name = wmoToIcon(code, isDay)
        var theme = settingsMenu.darkMode ? "dark" : "light"
        return "widgets/weather/google-weather-icons-main/sets/set-3/" + theme + "/" + name + ".svg"
    }

    function openWeatherPopup(iconItem) {
        if (weatherPopup.visible) { weatherPopup.visible = false; return }
        var popupW = 380
        var popupH = Math.round((weatherPopupCol ? (weatherPopupCol.height + 30) : weatherPopup.implicitHeight) || 390)
        var primaryScreen = null
        for (var s = 0; s < Quickshell.screens.length; s++) {
            if (Quickshell.screens[s].name === settingsMenu.primaryMonitor) { primaryScreen = Quickshell.screens[s]; break }
        }
        var monW = primaryScreen ? primaryScreen.width  : (panelWindow.screen ? panelWindow.screen.width : 1280)
        var monH = primaryScreen ? primaryScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)
        var iconPos = iconItem.mapToItem(panelWindow.contentItem, 0, 0)
        var px = Math.round(iconPos.x + iconItem.width / 2 - popupW / 2)
        px = Math.max(4, Math.min(monW - popupW - 4, px))
        var taskbarH = panelWindow.implicitHeight || 45
        var py = monH - taskbarH - popupH + 1
        console.log("Weather popup: h=" + popupH + " y=" + py + " (monH=" + monH + ")")
        // Set position BEFORE showing so Hyprland uses it at map time
        var posProc = Qt.createQmlObject('import Quickshell.Io; Process {}', panelWindow)
        posProc.command = ["windoesnot-hyprctl", "keyword", "windowrule[weather-popup-config]:move", px + " " + py]
        posProc.exited.connect(function() {
            weatherPopup.visible = true
            if (panelWindow.weatherActiveTab === 0) Qt.callLater(function() { panelWindow.scrollWeatherHourlyToNow() })
        })
        posProc.running = true
    }

    function scrollWeatherHourlyToNow() {
        if (!weatherHourlyFlick) return
        if (!panelWindow.weatherHourlyToday || panelWindow.weatherHourlyToday.length === 0) return
        var now = new Date()
        var hour = now.getHours()
        var idx = 0
        for (var i = 0; i < panelWindow.weatherHourlyToday.length; i++) {
            var h = parseInt(panelWindow.weatherHourlyToday[i].time.slice(0, 2), 10)
            if (h <= hour) idx = i
        }
        var itemW = panelWindow.weatherHourlyItemWidth
        var itemGap = panelWindow.weatherHourlyItemSpacing
        var centerX = idx * (itemW + itemGap) + (itemW / 2) - (weatherHourlyFlick.width / 2)
        var maxX = Math.max(0, weatherHourlyFlick.contentWidth - weatherHourlyFlick.width)
        weatherHourlyFlick.contentX = Math.max(0, Math.min(maxX, centerX))
    }

    function openCopilotPopup(iconItem) {
        if (!copilotWindow) return
        console.log("[Copilot] openCopilotPopup called, currently visible:", copilotWindow.visible)
        var host = copilotWindow.host
        console.log("[Copilot] copilotPanelItem:", host, "isPinned:", host ? host.isPinned : "N/A")
        if (host) {
            console.log("[Copilot] host.terminalModuleAvailable:", host.terminalModuleAvailable,
                        "availabilityResolved:", host.availabilityResolved,
                        "_agentFailed:", host._agentFailed,
                        "loadedPanel:", host.loadedPanel)
        }
        if (copilotWindow.visible) {
            if (panelWindow._copilotJustOpened) return  // ignore race-condition re-call right after opening
            copilotWindow.visible = false
            return
        }

        var popupW = 1100
        var popupH = 760
        var primaryScreen = null
        for (var s = 0; s < Quickshell.screens.length; s++) {
            if (Quickshell.screens[s].name === settingsMenu.primaryMonitor) { primaryScreen = Quickshell.screens[s]; break }
        }
        var monW = primaryScreen ? primaryScreen.width : (panelWindow.screen ? panelWindow.screen.width : 1280)
        var monH = primaryScreen ? primaryScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)

        var px, py

        if (iconItem) {
            // Pinned mode - position near icon
            var iconPos = iconItem.mapToItem(panelWindow.contentItem, 0, 0)
            px = Math.round(iconPos.x + iconItem.width / 2 - popupW / 2)
            px = Math.max(4, Math.min(monW - popupW - 4, px))
            // Same bottom anchor as display_geometry.py; never above the screen edge.
            py = Math.max(0, monH - 45 - Math.min(popupH, monH - 45 - 16))
        } else {
            // Unpinned mode - center of screen or use current workspace
            px = Math.round((monW - popupW) / 2)
            py = Math.round((monH - popupH) / 2)
        }

        // Only set position for pinned mode (iconItem exists)
        var host = copilotWindow.host
        var isPinned = host ? host.isPinned : true

        if (iconItem && isPinned) {
            // Pinned mode - set position BEFORE showing so Hyprland uses it at map time
            var posProc = Qt.createQmlObject('import Quickshell.Io; Process {}', panelWindow)
            posProc.command = ["windoesnot-hyprctl", "keyword", "windowrule[copilot-config-pinned]:move", px + " " + py]
            posProc.exited.connect(function() {
                console.log("[Copilot] posProc exited, setting visible=true")
                panelWindow._copilotJustOpened = true
                copilotOpenGuard.restart()
                copilotWindow.visible = true
                console.log("[Copilot] visible is now:", copilotWindow.visible)
            })
            posProc.running = true
            console.log("[Copilot] posProc started for PINNED mode, position:", px, py)
        } else {
            // Unpinned mode or no icon - just show, Hyprland will tile it or use default position
            console.log("[Copilot] Unpinned mode - showing without position")
            panelWindow._copilotJustOpened = true
            copilotOpenGuard.restart()
            copilotWindow.visible = true
            console.log("[Copilot] visible is now:", copilotWindow.visible)
        }
    }

    // Returns start area slot (0/1/2) from drop x in taskbarRow coords
    function getStartAreaDragSlot(rowDropX) {
        if (rowDropX < startButton.x + startButton.width / 2) return 0
        if (!settingsButton.visible || rowDropX < settingsButton.x + settingsButton.width / 2) return 1
        return 2
    }

    function fetchWeather() {
        if (!settingsMenu.weatherEnabled) return
        if (settingsMenu.weatherLatitude === 0 && settingsMenu.weatherLongitude === 0) return
        var lat = settingsMenu.weatherLatitude
        var lon = settingsMenu.weatherLongitude
        var url = "https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lon +
                  "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day" +
                  "&hourly=temperature_2m,weather_code,precipitation_probability,wind_speed_10m,is_day" +
                  "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max" +
                  "&timezone=auto&forecast_days=7"
        weatherFetchProc.command = ["bash", "-c", "curl -s --max-time 10 '" + url + "'"]
        weatherFetchProc.running = true
    }

    Process {
        id: weatherFetchProc
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(this.text)
                    if (data.current) {
                        panelWindow.weatherCode      = data.current.weather_code
                        panelWindow.weatherTemp      = Math.round(data.current.temperature_2m * 10) / 10
                        panelWindow.weatherFeelsLike = Math.round(data.current.apparent_temperature * 10) / 10
                        panelWindow.weatherHumidity  = data.current.relative_humidity_2m
                        panelWindow.weatherWindSpeed = Math.round(data.current.wind_speed_10m * 10) / 10
                        panelWindow.weatherIsDay     = data.current.is_day === 1
                    }
                    if (data.daily) {
                        var fc = []
                        for (var i = 0; i < data.daily.time.length; i++) {
                            fc.push({
                                date:      data.daily.time[i],
                                code:      data.daily.weather_code[i],
                                tempMax:   Math.round(data.daily.temperature_2m_max[i]),
                                tempMin:   Math.round(data.daily.temperature_2m_min[i]),
                                precipProb: data.daily.precipitation_probability_max[i] || 0
                            })
                        }
                        panelWindow.weatherForecast = fc
                    }
                    if (data.hourly && data.hourly.time) {
                        var hourly = []
                        var todayStr = ""
                        if (data.daily && data.daily.time && data.daily.time.length > 0) {
                            todayStr = data.daily.time[0]
                        } else {
                            todayStr = new Date().toISOString().slice(0, 10)
                        }
                        for (var h = 0; h < data.hourly.time.length; h++) {
                            var ts = data.hourly.time[h]
                            if (ts.slice(0, 10) !== todayStr) continue
                            hourly.push({
                                time: ts.slice(11, 16),
                                code: data.hourly.weather_code[h],
                                temp: Math.round(data.hourly.temperature_2m[h]),
                                precipProb: data.hourly.precipitation_probability[h] || 0,
                                wind: Math.round(data.hourly.wind_speed_10m[h] || 0),
                                isDay: data.hourly.is_day ? (data.hourly.is_day[h] === 1) : true
                            })
                        }
                        panelWindow.weatherHourlyToday = hourly
                        Qt.callLater(function() { panelWindow.scrollWeatherHourlyToNow() })
                    }
                    var now = new Date()
                    panelWindow.weatherUpdateTime = now.getHours() + ":" + (now.getMinutes() < 10 ? "0" : "") + now.getMinutes()
                } catch(e) {
                    console.log("Weather parse error:", e)
                }
            }
        }
    }

    Timer {
        id: weatherTimer
        interval: 1800000  // 30 Minuten
        repeat: true
        running: settingsMenu.weatherEnabled && settingsMenu.weatherLatitude !== 0
        triggeredOnStart: true
        onTriggered: panelWindow.fetchWeather()
    }

    function focusOrMinimizeApp(appName) {
        if (panelWindow.openWindows.hasOwnProperty(appName)) {
            var win = panelWindow.openWindows[appName]
            var cmdStr = ""

            if (win.focused) {
                // Window is focused, minimize it
                cmdStr = "windoesnot-hyprctl dispatch movetoworkspacesilent special:minimized,address:" + win.address
            } else {
                // Window exists but not focused, focus it
                cmdStr = "windoesnot-hyprctl dispatch focuswindow address:" + win.address
            }

            Qt.createQmlObject(
                'import Quickshell.Io; Process { ' +
                'command: ["bash", "-c", "' + cmdStr + '"]; ' +
                'running: true }',
                panelWindow
            )
            return true
        }
        return false
    }

    // Unified Tooltip Component
    Item {
        id: unifiedTooltip
        visible: false
        z: 9999
        anchors.fill: parent

        property string text: ""

        function show(item, message) {
            if (!item || !message || message.length === 0) {
                return
            }

            text = message

            // Map item position to panelWindow coordinates
            var pos = item.mapToItem(panelWindow.contentItem, 0, 0)

            // Position tooltip above item
            tooltipRect.x = pos.x + (item.width / 2) - (tooltipRect.width / 2)
            tooltipRect.y = pos.y - tooltipRect.height - 8

            visible = true
        }

        function hide() {
            visible = false
            text = ""
        }

        Rectangle {
            id: tooltipRect
            color: Qt.rgba(0.15, 0.15, 0.15, 0.95)
            border.color: "#3a3a3f"
            border.width: 1
            radius: 6
            width: tooltipText.implicitWidth + 16
            height: tooltipText.implicitHeight + 12

            Text {
                id: tooltipText
                text: unifiedTooltip.text
                color: "#ffffff"
                font.pixelSize: 12
                anchors.centerIn: parent
            }
        }

        Behavior on opacity { NumberAnimation { duration: 150 } }
    }

    Component.onCompleted: {
        loadTaskbarApps()
        Qt.callLater(rebuildTrayModel)
    }

    function applyTaskbarOverrides(apps) {
        for (var i = 0; i < apps.length; i++) {
            if (appReplace && appReplace.hasOverride(apps[i].name)) {
                apps[i] = appReplace.applyOverride(apps[i])
                console.log("Applied override to taskbar app:", apps[i].name)
            }
        }
        return apps
    }

    function ensureCopilotTaskbarApp() {
        for (var i = 0; i < panelWindow.taskbarApps.length; i++) {
            if (panelWindow.taskbarApps[i].cmd === panelWindow.internalCopilotCmd) {
                // Saved before the rename: always show the current name and icon.
                panelWindow.taskbarApps[i].name = "Does"
                panelWindow.taskbarApps[i].icon = "img/does.svg"
                panelWindow.taskbarApps[i].customIcon = true
                return
            }
        }

        panelWindow.taskbarApps.unshift({
            name: "Does",
            cmd: panelWindow.internalCopilotCmd,
            icon: "img/does.svg",
            customIcon: true,
            pinned: true,
            temporary: false
        })
    }

    function loadTaskbarApps() {
        var configPath = Qt.resolvedUrl("taskbar.txt").toString().replace("file://", "")
        console.log("Loading taskbar apps from:", configPath)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "if [ -f \'' + configPath + '\' ]; then cat \'' + configPath + '\'; fi"]; ' +
            'running: true; ' +
            'stdout: StdioCollector { ' +
            'onStreamFinished: { ' +
            'var lines = this.text.trim().split("\\n"); ' +
            'panelWindow.taskbarApps = []; ' +
            'for (var i = 0; i < lines.length; i++) { ' +
            'if (lines[i].length > 0) { ' +
            'var parts = lines[i].split("|"); ' +
            'if (parts.length >= 3) { ' +
            'var isCustom = parts.length > 3 && parts[3] === "true"; ' +
            'panelWindow.taskbarApps.push({name: parts[0], cmd: parts[1], icon: parts[2], customIcon: isCustom, pinned: true, temporary: false}); ' +
            '} } } ' +
            'panelWindow.ensureCopilotTaskbarApp(); ' +
            'panelWindow.taskbarApps = panelWindow.applyTaskbarOverrides(panelWindow.taskbarApps); ' +
            'panelWindow.rebuildTaskbarModel(); ' +
            'console.log("Loaded", panelWindow.taskbarApps.length, "taskbar apps"); ' +
            '} } }',
            panelWindow
        )
    }

    function saveTaskbarApps() {
        var configPath = Qt.resolvedUrl("taskbar.txt").toString().replace("file://", "")
        var lines = []
        for (var i = 0; i < panelWindow.taskbarApps.length; i++) {
            var app = panelWindow.taskbarApps[i]
            var customFlag = app.customIcon ? "true" : "false"
            lines.push(app.name + "|" + app.cmd + "|" + app.icon + "|" + customFlag)
        }
        var content = lines.join("\\n")

        console.log("Saving", panelWindow.taskbarApps.length, "taskbar apps")

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "echo \'' + content.replace(/'/g, "'\\''") + '\' > \'' + configPath + '\'"]; ' +
            'running: true; ' +
            'stdout: StdioCollector { onStreamFinished: console.log("Taskbar apps saved") } }',
            panelWindow
        )
    }

    function addToTaskbar(appName, appCmd, appIcon, isCustomIcon) {
        // Check if already in taskbar
        for (var i = 0; i < panelWindow.taskbarApps.length; i++) {
            if (panelWindow.taskbarApps[i].name === appName) {
                console.log("App already in taskbar:", appName)
                return
            }
        }

        panelWindow.taskbarApps.push({
            name: appName,
            cmd: appCmd,
            icon: appIcon,
            customIcon: isCustomIcon,
            pinned: true,
            temporary: false
        })
        saveTaskbarApps()
        rebuildTaskbarModel()
        console.log("Added to taskbar:", appName)
    }

    function removeFromTaskbar(appName) {
        for (var i = 0; i < panelWindow.taskbarApps.length; i++) {
            if (panelWindow.taskbarApps[i].name === appName) {
                panelWindow.taskbarApps.splice(i, 1)
                saveTaskbarApps()
                rebuildTaskbarModel()
                console.log("Removed from taskbar:", appName)
                return
            }
        }
    }

    function rebuildTaskbarModel() {
        taskbarAppsModel.clear()
        var hasWeather = settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot < 0
        var wIdx = hasWeather ? settingsMenu.weatherTaskbarIndex : -2
        if (hasWeather && wIdx < 0) wIdx = panelWindow.taskbarApps.length  // -1 = end
        var weatherInserted = false
        for (var i = 0; i < panelWindow.taskbarApps.length; i++) {
            if (!weatherInserted && hasWeather && i === wIdx) {
                taskbarAppsModel.append({isWeather: true, name: "__weather__", cmd: "", icon: "", customIcon: false, pinned: false, temporary: false})
                weatherInserted = true
            }
            taskbarAppsModel.append(panelWindow.taskbarApps[i])
        }
        if (!weatherInserted && hasWeather) {
            taskbarAppsModel.append({isWeather: true, name: "__weather__", cmd: "", icon: "", customIcon: false, pinned: false, temporary: false})
        }
    }

    function reorderTaskbarApps(fromIndex, toIndex) {
        if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return
        // Weather only affects reorder if in taskbar row (not start/overview area)
        var hasWeather = settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot < 0
        if (!hasWeather) {
            if (fromIndex < panelWindow.taskbarApps.length && toIndex < panelWindow.taskbarApps.length) {
                var item = panelWindow.taskbarApps.splice(fromIndex, 1)[0]
                panelWindow.taskbarApps.splice(toIndex, 0, item)
                saveTaskbarApps()
                rebuildTaskbarModel()
            }
            return
        }
        // Build combined array, reorder, extract new taskbarApps + weatherTaskbarIndex
        var wIdx = settingsMenu.weatherTaskbarIndex
        if (wIdx < 0 || wIdx > panelWindow.taskbarApps.length) wIdx = panelWindow.taskbarApps.length
        var combined = []
        for (var i = 0; i <= panelWindow.taskbarApps.length; i++) {
            if (i === wIdx) combined.push({isWeather: true})
            if (i < panelWindow.taskbarApps.length) combined.push(panelWindow.taskbarApps[i])
        }
        if (fromIndex >= combined.length || toIndex >= combined.length) return
        var moved = combined.splice(fromIndex, 1)[0]
        combined.splice(toIndex, 0, moved)
        var newApps = [], newWIdx = combined.length
        for (var j = 0; j < combined.length; j++) {
            if (combined[j].isWeather) newWIdx = j
            else newApps.push(combined[j])
        }
        panelWindow.taskbarApps = newApps
        settingsMenu.weatherTaskbarIndex = newWIdx
        settingsMenu.saveSettings()
        saveTaskbarApps()
        rebuildTaskbarModel()
    }

    function rebuildTrayModel() {
        trayIconModel.clear()
        var order = settingsMenu.trayOrder.split(",")
        if (order.indexOf("nearby") < 0) order.splice(Math.max(0, order.indexOf("network") + 1), 0, "nearby")
        for (var i = 0; i < order.length; i++) {
            var t = order[i].trim()
            if (t === "weather") {
                if (settingsMenu.weatherEnabled && settingsMenu.weatherLocation !== "taskbar") {
                    trayIconModel.append({iconType: "weather"})
                }
            } else if (t === "docker") {
                if (settingsMenu.showDockerTray) trayIconModel.append({iconType: "docker"})
            } else if (t === "ollama") {
                if (settingsMenu.showOllamaTray) trayIconModel.append({iconType: "ollama"})
            } else if (t === "nearby") {
                if (settingsMenu.showNearbyTray) trayIconModel.append({iconType: "nearby"})
            } else {
                trayIconModel.append({iconType: t})
            }
        }
    }

    function reorderTrayIcons(fromIndex, toIndex) {
        if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return
        // Get currently displayed types
        var displayed = []
        for (var i = 0; i < trayIconModel.count; i++) {
            displayed.push(trayIconModel.get(i).iconType)
        }
        var moved = displayed.splice(fromIndex, 1)[0]
        displayed.splice(toIndex, 0, moved)
        // Build new trayOrder: displayed items + any hidden items at end
        var fullOrder = settingsMenu.trayOrder.split(",").map(function(s) { return s.trim() })
        var hidden = []
        for (var j = 0; j < fullOrder.length; j++) {
            var t = fullOrder[j]
            if (displayed.indexOf(t) < 0) hidden.push(t)
        }
        settingsMenu.trayOrder = displayed.concat(hidden).join(",")
        settingsMenu.saveSettings()
        rebuildTrayModel()
    }

    Connections {
        target: settingsMenu
        function onWeatherLocationChanged() { panelWindow.rebuildTaskbarModel(); panelWindow.rebuildTrayModel() }
        function onWeatherEnabledChanged() { panelWindow.rebuildTaskbarModel(); panelWindow.rebuildTrayModel() }
        function onWeatherStartAreaSlotChanged() { panelWindow.rebuildTaskbarModel() }
        function onTrayOrderChanged() { panelWindow.rebuildTrayModel() }
        function onUiLanguageChanged() { if (!settingsMenu.isLoadingSettings) desktopFilesProc.running = true }
        function onShowOllamaTrayChanged() { panelWindow.rebuildTrayModel() }
        function onShowNearbyTrayChanged() { panelWindow.rebuildTrayModel() }
    }

    // Workspace Toggle Button - Position depends on alignment
    Rectangle {
        id: workspaceContainer
        width: 40
        height: 40
        radius: 18
        anchors.verticalCenter: parent.verticalCenter
        // Dynamic positioning based on taskbar alignment
        x: {
            var base = panelWindow.taskbarAlignment === "left" ? taskbarRow.x + 40 + 10 : 8
            var slot4Active = settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot === 4
            return slot4Active ? base + (panelWindow.weatherSlotWidth + 8) : base
        }
        color: "transparent"
        property bool hovered: false

        Image {
            anchors.centerIn: parent
            source: "img/spaces.svg"
            width: 40
            height: 40
            sourceSize.width: 40
            sourceSize.height: 40
            fillMode: Image.PreserveAspectFit
            smooth: true
            antialiasing: true
            mipmap: true
            opacity: workspaceContainer.hovered ? 0.75 : 1.0

            layer.enabled: !settingsMenu.darkMode
            layer.effect: MultiEffect {
                colorization: 1.0
                colorizationColor: "#333333"
            }
        }

        Process {
            id: overviewProc
            command: ["bash", "-c", "qs ipc -c overview call overview toggle"]
            running: false
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onEntered: workspaceContainer.hovered = true
            onExited: workspaceContainer.hovered = false
            onClicked: overviewProc.running = true
        }
    }

    // Weather Start Area Slot 3 (next to overview/workspace button)
    Item {
        id: weatherSlot3Container
        width: panelWindow.weatherSlotWidth; height: 40
        visible: settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot === 3
        x: workspaceContainer.x + workspaceContainer.width + 8
        anchors.verticalCenter: parent.verticalCenter
        property bool isBeingDragged: false

        Rectangle {
            id: weatherSlot3
            anchors.fill: parent; radius: 8; color: "transparent"
            property bool hovered: false
            scale: weatherSlot3Container.isBeingDragged ? 0.9 : 1.0
            opacity: weatherSlot3Container.isBeingDragged ? 0.5 : 1.0
            Behavior on scale { NumberAnimation { duration: 100 } }
            Behavior on opacity { NumberAnimation { duration: 100 } }
            Rectangle { anchors.fill: parent; radius: 8; color: parent.hovered ? Qt.rgba(1,1,1,0.1) : "transparent"; Behavior on color { ColorAnimation { duration: 150 } } }
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: panelWindow.weatherInnerMargin
                spacing: panelWindow.weatherInnerSpacing
                Image { width: panelWindow.weatherIconSize; height: panelWindow.weatherIconSize; source: panelWindow.weatherCode >= 0 ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay) : ""; sourceSize.width: panelWindow.weatherIconSize * 2; sourceSize.height: panelWindow.weatherIconSize * 2; fillMode: Image.PreserveAspectFit; smooth: true; antialiasing: true; mipmap: true }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: -1
                    Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? panelWindow.wmoToDesc(panelWindow.weatherCode) : Lang.get("weather.label", settingsMenu.uiLanguage); elide: Text.ElideRight; font.pixelSize: panelWindow.weatherDescFontSize; font.bold: true; color: settingsMenu.darkMode ? "#f2f2f2" : "#202124" }
                    Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? (Math.round(panelWindow.weatherTemp) + "°") : "--°"; elide: Text.ElideRight; font.pixelSize: panelWindow.weatherTempFontSize; font.bold: true; color: settingsMenu.darkMode ? "#ffffff" : "#111111" }
                }
            }
            MouseArea {
                id: weatherSlot3Area; anchors.fill: parent; hoverEnabled: true
                property bool dragActive: false; property point dragStartPos; property int dragThreshold: 10
                drag.target: dragActive ? weatherSlot3Container : null; drag.axis: Drag.XAxis
                onEntered: weatherSlot3.hovered = true; onExited: weatherSlot3.hovered = false
                onPressed: function(mouse) { if (mouse.button === Qt.LeftButton) { dragStartPos = Qt.point(mouse.x, mouse.y); dragActive = false; weatherSlot3Container.isBeingDragged = false; mouse.accepted = true } }
                onPositionChanged: function(mouse) { if (!dragActive && mouse.buttons === Qt.LeftButton) { if (Math.abs(mouse.x - dragStartPos.x) > dragThreshold || Math.abs(mouse.y - dragStartPos.y) > dragThreshold) { dragActive = true; weatherSlot3Container.isBeingDragged = true } } }
                onReleased: function(mouse) {
                    var wasDragging = dragActive; dragActive = false; weatherSlot3Container.isBeingDragged = false
                    if (wasDragging) {
                        var cDropX = weatherSlot3Area.mapToItem(taskbarContainer, mouse.x, mouse.y).x
                        weatherSlot3Container.x = Qt.binding(function() { return workspaceContainer.x + workspaceContainer.width + 8 })
                        var ovCX3 = workspaceContainer.x + workspaceContainer.width / 2
                        var rowLeft = taskbarRow.x
                        var firstAppX_abs = taskbarRepeater.count > 0 && taskbarRepeater.itemAt(0) ? taskbarRow.x + taskbarRepeater.itemAt(0).x : taskbarRow.x + taskbarRow.width
                        if (Math.abs(cDropX - ovCX3) < workspaceContainer.width + 10) {
                            settingsMenu.weatherStartAreaSlot = cDropX < ovCX3 ? 4 : 3; settingsMenu.saveSettings()
                        } else if (cDropX >= firstAppX_abs - 10) {
                            var idx = Math.max(0, Math.round((cDropX - firstAppX_abs) / 50))
                            settingsMenu.weatherStartAreaSlot = -1; settingsMenu.weatherTaskbarIndex = Math.min(idx, panelWindow.taskbarApps.length); settingsMenu.saveSettings(); panelWindow.rebuildTaskbarModel()
                        } else if (cDropX >= rowLeft - 10) {
                            var rowDropX3 = cDropX - rowLeft
                            var ns3 = panelWindow.getStartAreaDragSlot(rowDropX3); settingsMenu.weatherStartAreaSlot = ns3; settingsMenu.saveSettings()
                        }
                    } else { panelWindow.openWeatherPopup(weatherSlot3Area) }
                }
            }
        }
    }

    // Weather Start Area Slot 4 (links vom overview/workspace button)
    Item {
        id: weatherSlot4Container
        width: panelWindow.weatherSlotWidth; height: 40
        visible: settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot === 4
        x: workspaceContainer.x - 8 - panelWindow.weatherSlotWidth
        anchors.verticalCenter: parent.verticalCenter
        property bool isBeingDragged: false

        Rectangle {
            id: weatherSlot4
            anchors.fill: parent; radius: 8; color: "transparent"
            property bool hovered: false
            scale: weatherSlot4Container.isBeingDragged ? 0.9 : 1.0
            opacity: weatherSlot4Container.isBeingDragged ? 0.5 : 1.0
            Behavior on scale { NumberAnimation { duration: 100 } }
            Behavior on opacity { NumberAnimation { duration: 100 } }
            Rectangle { anchors.fill: parent; radius: 8; color: parent.hovered ? Qt.rgba(1,1,1,0.1) : "transparent"; Behavior on color { ColorAnimation { duration: 150 } } }
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: panelWindow.weatherInnerMargin
                spacing: panelWindow.weatherInnerSpacing
                Image { width: panelWindow.weatherIconSize; height: panelWindow.weatherIconSize; source: panelWindow.weatherCode >= 0 ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay) : ""; sourceSize.width: panelWindow.weatherIconSize * 2; sourceSize.height: panelWindow.weatherIconSize * 2; fillMode: Image.PreserveAspectFit; smooth: true; antialiasing: true; mipmap: true }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: -1
                    Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? panelWindow.wmoToDesc(panelWindow.weatherCode) : Lang.get("weather.label", settingsMenu.uiLanguage); elide: Text.ElideRight; font.pixelSize: panelWindow.weatherDescFontSize; font.bold: true; color: settingsMenu.darkMode ? "#f2f2f2" : "#202124" }
                    Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? (Math.round(panelWindow.weatherTemp) + "°") : "--°"; elide: Text.ElideRight; font.pixelSize: panelWindow.weatherTempFontSize; font.bold: true; color: settingsMenu.darkMode ? "#ffffff" : "#111111" }
                }
            }
            MouseArea {
                id: weatherSlot4Area; anchors.fill: parent; hoverEnabled: true
                property bool dragActive: false; property point dragStartPos; property int dragThreshold: 10
                drag.target: dragActive ? weatherSlot4Container : null; drag.axis: Drag.XAxis
                onEntered: weatherSlot4.hovered = true; onExited: weatherSlot4.hovered = false
                onPressed: function(mouse) { if (mouse.button === Qt.LeftButton) { dragStartPos = Qt.point(mouse.x, mouse.y); dragActive = false; weatherSlot4Container.isBeingDragged = false; mouse.accepted = true } }
                onPositionChanged: function(mouse) { if (!dragActive && mouse.buttons === Qt.LeftButton) { if (Math.abs(mouse.x - dragStartPos.x) > dragThreshold || Math.abs(mouse.y - dragStartPos.y) > dragThreshold) { dragActive = true; weatherSlot4Container.isBeingDragged = true } } }
                onReleased: function(mouse) {
                    var wasDragging = dragActive; dragActive = false; weatherSlot4Container.isBeingDragged = false
                    if (wasDragging) {
                        var cDropX = weatherSlot4Area.mapToItem(taskbarContainer, mouse.x, mouse.y).x
                        weatherSlot4Container.x = Qt.binding(function() { return workspaceContainer.x - 8 - panelWindow.weatherSlotWidth })
                        var ovCX4 = workspaceContainer.x + workspaceContainer.width / 2
                        var rowLeft = taskbarRow.x
                        var firstAppX_abs = taskbarRepeater.count > 0 && taskbarRepeater.itemAt(0) ? taskbarRow.x + taskbarRepeater.itemAt(0).x : taskbarRow.x + taskbarRow.width
                        if (Math.abs(cDropX - ovCX4) < workspaceContainer.width + 10) {
                            settingsMenu.weatherStartAreaSlot = cDropX < ovCX4 ? 4 : 3; settingsMenu.saveSettings()
                        } else if (cDropX >= firstAppX_abs - 10) {
                            var idx = Math.max(0, Math.round((cDropX - firstAppX_abs) / 50))
                            settingsMenu.weatherStartAreaSlot = -1; settingsMenu.weatherTaskbarIndex = Math.min(idx, panelWindow.taskbarApps.length); settingsMenu.saveSettings(); panelWindow.rebuildTaskbarModel()
                        } else if (cDropX >= rowLeft - 10) {
                            var rowDropX4 = cDropX - rowLeft
                            var ns4 = panelWindow.getStartAreaDragSlot(rowDropX4); settingsMenu.weatherStartAreaSlot = ns4; settingsMenu.saveSettings()
                        }
                    } else { panelWindow.openWeatherPopup(weatherSlot4Area) }
                }
            }
        }
    }

    // System Tray Area
    Rectangle {
        id: systemTrayArea
        width: systemTrayRow.width + 16
        height: 40
        radius: 8
        anchors.right: clockContainer.left
        anchors.verticalCenter: parent.verticalCenter
        anchors.rightMargin: 8
        color: "transparent"

        property bool trayExpanded: false

        Row {
            id: systemTrayRow
            anchors.centerIn: parent
            spacing: 8

            // Expand/Collapse Button
            Rectangle {
                width: 32
                height: 32
                radius: 6
                color: trayToggleMouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.15) : "transparent"
                visible: true

                Behavior on color { ColorAnimation { duration: 150 } }

                Image {
                    anchors.centerIn: parent
                    source: "img/project/chevron-up.svg"
                    width: 16
                    height: 16
                    sourceSize.width: 16
                    sourceSize.height: 16
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                    mipmap: true
                    rotation: systemTrayArea.trayExpanded ? 180 : 0

                    layer.enabled: !settingsMenu.darkMode
                    layer.effect: MultiEffect {
                        colorization: 1.0
                        colorizationColor: "#333333"
                    }
                }

                MouseArea {
                    id: trayToggleMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: systemTrayArea.trayExpanded = !systemTrayArea.trayExpanded
                }
            }

            // Tray Icons (expandable) - Real system tray items
            Row {
                spacing: 4
                visible: systemTrayArea.trayExpanded
                opacity: systemTrayArea.trayExpanded ? 1 : 0

                Behavior on opacity { NumberAnimation { duration: 150 } }

                Repeater {
                    model: SystemTray.items
                    delegate: Rectangle {
                        id: trayItemDelegate
                        width: 32
                        height: 32
                        radius: 6
                        color: trayIconMouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(1, 1, 1, 0.05)

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Image {
                            anchors.centerIn: parent
                            source: modelData.icon
                            width: 20
                            height: 20
                            sourceSize.width: 20
                            sourceSize.height: 20
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            antialiasing: true
                            mipmap: true
                            layer.enabled: true
                            layer.smooth: true
                        }

                        Timer {
                            id: trayTooltipTimer
                            interval: 500
                            running: false
                            repeat: false
                            onTriggered: {
                                unifiedTooltip.show(trayItemDelegate, modelData.tooltipTitle || modelData.title || modelData.id)
                            }
                        }

                        QsMenuAnchor {
                            id: trayMenuAnchor
                            menu: modelData.menu
                            anchor.window: panelWindow
                            anchor.edges: Edges.Top
                            anchor.gravity: Edges.Top
                            anchor.adjustment: PopupAdjustment.None
                        }

                        MouseArea {
                            id: trayIconMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                            onEntered: trayTooltipTimer.start()
                            onExited: {
                                trayTooltipTimer.stop()
                                unifiedTooltip.hide()
                            }
                            onClicked: function(mouse) {
                                trayTooltipTimer.stop()
                                unifiedTooltip.hide()
                                if (mouse.button === Qt.LeftButton) {
                                    modelData.activate()
                                } else if (mouse.button === Qt.MiddleButton) {
                                    modelData.secondaryActivate()
                                } else if (mouse.button === Qt.RightButton) {
                                    if (modelData.hasMenu) {
                                        // Anchor rect spans exactly the icon; gravity: Top (set on
                                        // trayMenuAnchor above, no Left/Right flag) centers the menu
                                        // horizontally on it and grows it upward by its real height,
                                        // so no fixed size guess is needed here.
                                        var pos = trayItemDelegate.mapToItem(panelWindow.contentItem, 0, 0)
                                        trayMenuAnchor.anchor.rect.x = pos.x
                                        trayMenuAnchor.anchor.rect.y = pos.y
                                        trayMenuAnchor.anchor.rect.width = trayItemDelegate.width
                                        trayMenuAnchor.anchor.rect.height = trayItemDelegate.height
                                        trayMenuAnchor.open()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Quick Settings Icons
            Row {
                id: quickSettingsIconsRow
                spacing: 4

                Repeater {
                    id: trayIconRepeater
                    model: trayIconModel

                    delegate: Item {
                        id: trayIconDelegate
                        width: 32
                        height: 32

                        property int visualIndex: index
                        property bool isBeingDragged: false

                        // Hover background (all icon types)
                        Rectangle {
                            anchors.fill: parent
                            radius: 8
                            color: trayDragArea.containsMouse ? Qt.rgba(1,1,1,0.15) : "transparent"
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }

                        // Weather icon content
                        Image {
                            visible: model.iconType === "weather"
                            anchors.centerIn: parent
                            source: panelWindow.weatherCode >= 0
                                ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay)
                                : ""
                            width: 20; height: 20
                            sourceSize.width: 40; sourceSize.height: 40
                            fillMode: Image.PreserveAspectFit
                            smooth: true; antialiasing: true; mipmap: true
                            opacity: trayDragArea.containsMouse ? 0.7 : 1.0
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        // Audio icon content
                        Image {
                            visible: model.iconType === "audio"
                            anchors.centerIn: parent
                            source: "img/Win11-dark/status/symbolic/ephy-audio-playing-symbolic.svg"
                            width: 18; height: 18
                            sourceSize.width: 36; sourceSize.height: 36
                            fillMode: Image.PreserveAspectFit
                            smooth: true; antialiasing: true; mipmap: true
                            opacity: trayDragArea.containsMouse ? 0.7 : 1.0
                            layer.enabled: !settingsMenu.darkMode
                            layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        // Bluetooth icon content
                        Image {
                            visible: model.iconType === "bluetooth"
                            anchors.centerIn: parent
                            source: "img/Win11-dark/status/symbolic/_blueberry-tray-active-symbolic.svg"
                            width: 18; height: 18
                            sourceSize.width: 36; sourceSize.height: 36
                            fillMode: Image.PreserveAspectFit
                            smooth: true; antialiasing: true; mipmap: true
                            opacity: trayDragArea.containsMouse ? 0.7 : 1.0
                            layer.enabled: !settingsMenu.darkMode
                            layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        // Ollama icon content
                        Image {
                            visible: model.iconType === "ollama"
                            anchors.centerIn: parent
                            source: "img/simple-icons--ollama.svg"
                            width: 20; height: 20
                            sourceSize.width: 40; sourceSize.height: 40
                            fillMode: Image.PreserveAspectFit
                            smooth: true; antialiasing: true; mipmap: true
                            opacity: trayDragArea.containsMouse ? 0.7 : 1.0
                            layer.enabled: !settingsMenu.darkMode
                            layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        // Docker icon content
                        Image {
                            visible: model.iconType === "docker"
                            anchors.centerIn: parent
                            source: "img/Win11-dark/places/24/folder-docker.svg"
                            width: 26; height: 26
                            sourceSize.width: 52; sourceSize.height: 52
                            fillMode: Image.PreserveAspectFit
                            smooth: true; antialiasing: true; mipmap: true
                            opacity: trayDragArea.containsMouse ? 0.7 : 1.0
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        Item {
                            visible: model.iconType === "nearby"
                            anchors.centerIn: parent; width: 20; height: 20
                            Image {
                                anchors.fill: parent
                                source: "img/Win11-dark/actions/symbolic/document-send-symbolic.svg"
                                opacity: nearbyService.state.receiving ? 1.0 : 0.45
                                layer.enabled: !settingsMenu.darkMode
                                layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                            }
                            Rectangle {
                                visible: nearbyService.state.receiving
                                anchors.right: parent.right; anchors.bottom: parent.bottom
                                width: 6; height: 6; radius: 3; color: settingsMenu.accentColor
                            }
                        }

                        // Network icon content
                        Image {
                            visible: model.iconType === "network"
                            anchors.centerIn: parent
                            source: {
                                if (networkWindow.connectionType === "wifi")
                                    return "img/Win11-dark/status/symbolic/network-wireless-connected-symbolic.svg"
                                else if (networkWindow.connectionType === "ethernet")
                                    return "img/Win11-dark/status/symbolic/network-idle-symbolic.svg"
                                else
                                    return "img/Win11-dark/status/symbolic/network-offline-symbolic.svg"
                            }
                            width: 18; height: 18
                            sourceSize.width: 36; sourceSize.height: 36
                            fillMode: Image.PreserveAspectFit
                            smooth: true; antialiasing: true; mipmap: true
                            opacity: trayDragArea.containsMouse ? 0.7 : 1.0
                            layer.enabled: !settingsMenu.darkMode
                            layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        scale: trayIconDelegate.isBeingDragged ? 0.9 : 1.0
                        opacity: trayIconDelegate.isBeingDragged ? 0.5 : 1.0
                        Behavior on scale { NumberAnimation { duration: 100 } }
                        Behavior on opacity { NumberAnimation { duration: 100 } }

                        MouseArea {
                            id: trayDragArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor

                            property bool dragActive: false
                            property point dragStartPos
                            property int dragThreshold: 10

                            onEntered: {
                                var tipText = ""
                                if (model.iconType === "weather") tipText = Math.round(panelWindow.weatherTemp) + "°C · " + panelWindow.wmoToDesc(panelWindow.weatherCode)
                                else if (model.iconType === "audio") tipText = "Audio"
                                else if (model.iconType === "bluetooth") tipText = "Bluetooth"
                else if (model.iconType === "network") tipText = Lang.get("shell.network", settingsMenu.uiLanguage)
                                else if (model.iconType === "nearby") tipText = Lang.get("nearby.title", settingsMenu.uiLanguage)
                                    + " · " + Lang.get(nearbyService.state.receiving ? "nearby.receivingOn" : "nearby.receivingOff", settingsMenu.uiLanguage)
                                else if (model.iconType === "ollama") tipText = "Ollama"
                                else if (model.iconType === "docker") tipText = "Docker"
                                if (tipText.length > 0) unifiedTooltip.show(trayIconDelegate, tipText)
                            }
                            onExited: {
                                unifiedTooltip.hide()
                                dragActive = false
                                trayIconDelegate.isBeingDragged = false
                            }

                            onPressed: function(mouse) {
                                dragStartPos = Qt.point(mouse.x, mouse.y)
                                dragActive = false
                                trayIconDelegate.isBeingDragged = false
                            }

                            onPositionChanged: function(mouse) {
                                if (!dragActive && mouse.buttons === Qt.LeftButton) {
                                    var dx = Math.abs(mouse.x - dragStartPos.x)
                                    var dy = Math.abs(mouse.y - dragStartPos.y)
                                    if (dx > dragThreshold || dy > dragThreshold) {
                                        dragActive = true
                                        trayIconDelegate.isBeingDragged = true
                                    }
                                }
                            }

                            onReleased: function(mouse) {
                                if (dragActive) {
                                    var dropX = trayDragArea.mapToItem(quickSettingsIconsRow, mouse.x, mouse.y).x
                                    var targetIndex = Math.floor(dropX / 36)
                                    if (targetIndex < 0) targetIndex = 0
                                    if (targetIndex >= trayIconModel.count) targetIndex = trayIconModel.count - 1
                                    if (targetIndex !== visualIndex) {
                                        panelWindow.reorderTrayIcons(visualIndex, targetIndex)
                                    }
                                } else {
                                    unifiedTooltip.hide()
                                    startMenu.visible = false
                                    settingsMenu.visible = false
                                    if (model.iconType === "weather") {
                                        panelWindow.openWeatherPopup(trayIconDelegate)
                                    } else if (model.iconType === "audio") {
                                        bluetoothWindow.visible = false
                                        networkWindow.visible = false
                                        nearbyWindow.visible = false
                                        calendarWindow.visible = false
                                        audioWindow.visible = !audioWindow.visible
                                    } else if (model.iconType === "bluetooth") {
                                        audioWindow.visible = false
                                        networkWindow.visible = false
                                        nearbyWindow.visible = false
                                        calendarWindow.visible = false
                                        bluetoothWindow.visible = !bluetoothWindow.visible
                                    } else if (model.iconType === "network") {
                                        audioWindow.visible = false
                                        bluetoothWindow.visible = false
                                        nearbyWindow.visible = false
                                        calendarWindow.visible = false
                                        networkWindow.visible = !networkWindow.visible
                                    } else if (model.iconType === "nearby") {
                                        if (nearbyWindow.visible) nearbyWindow.visible = false
                                        else desktopShell.openNearby()
                                    } else if (model.iconType === "ollama") {
                                        audioWindow.visible = false
                                        bluetoothWindow.visible = false
                                        networkWindow.visible = false
                                        nearbyWindow.visible = false
                                        calendarWindow.visible = false
                                        dockerWindow.visible = false
                                        ollamaWindow.visible = !ollamaWindow.visible
                                    } else if (model.iconType === "docker") {
                                        audioWindow.visible = false
                                        bluetoothWindow.visible = false
                                        networkWindow.visible = false
                                        nearbyWindow.visible = false
                                        calendarWindow.visible = false
                                        ollamaWindow.visible = false
                                        dockerWindow.visible = !dockerWindow.visible
                                    }
                                }
                                dragActive = false
                                trayIconDelegate.isBeingDragged = false
                            }

                            onWheel: function(wheel) {
                                if (model.iconType === "audio") {
                                    var delta = wheel.angleDelta.y / 120
                                    var changeCmd = delta > 0 ? "5%+" : "5%-"
                                    Qt.createQmlObject(
                                        'import Quickshell.Io; Process { ' +
                                        'command: ["bash", "-c", "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ ' + changeCmd + '"]; ' +
                                        'running: true }',
                                        trayIconDelegate
                                    )
                                    if (!audioWindow.visible) volumeOverlay.showOverlay()
                                }
                            }
                        }
                    }
                }
            }
        }

        Behavior on width { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
    }

    Rectangle {
        id: clockContainer
        width: clock.width + 16
        height: 40
        radius: 8
        anchors.right: showDesktopButton.left
        anchors.verticalCenter: parent.verticalCenter
        anchors.rightMargin: 8
        color: clockMouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"

        Behavior on color { ColorAnimation { duration: 150 } }

        Text {
            id: clock
            color: settingsMenu.darkMode ? "#ffffff" : "#000000"
            font.pixelSize: 14
            anchors.centerIn: parent
            horizontalAlignment: Text.AlignRight
            text: "00:00\n01.01.1970"
            lineHeight: 0.9

            Process {
                id: dateProc
                command: ["date", "+%H:%M\n%d.%m.%Y"]
                running: true
                stdout: StdioCollector { onStreamFinished: clock.text = this.text.trim() }
            }

            Timer {
                interval: 60000
                running: true
                repeat: true
                onTriggered: dateProc.running = true
            }
        }

        MouseArea {
            id: clockMouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                startMenu.visible = false
                settingsMenu.visible = false
                audioWindow.visible = false
                bluetoothWindow.visible = false
                networkWindow.visible = false
                nearbyWindow.visible = false
                calendarWindow.visible = !calendarWindow.visible
            }
        }
    }

    // Show Desktop Button (Trenner) - ganz rechts
    Rectangle {
        id: showDesktopButton
        width: 3
        height: 40
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.rightMargin: 5
        color: settingsMenu.darkMode
            ? (showDesktopMouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.4) : Qt.rgba(1, 1, 1, 0.2))
            : (showDesktopMouseArea.containsMouse ? Qt.rgba(0, 0, 0, 0.4) : Qt.rgba(0, 0, 0, 0.2))

        Behavior on color { ColorAnimation { duration: 150 } }

        MouseArea {
            id: showDesktopMouseArea
            anchors.fill: parent
            anchors.leftMargin: -5
            anchors.rightMargin: -5
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                Qt.createQmlObject(
                    'import Quickshell.Io; Process { command: ["bash", "-c", "~/.config/hypr/hide_windows.sh"]; running: true }',
                    showDesktopButton
                )
            }
        }
    }

    // Taskbar Drop Area
    DropArea {
        id: taskbarDropArea
        anchors.fill: parent

        property bool isHovered: false

        onEntered: {
            isHovered = true
        }

        onExited: {
            isHovered = false
        }

        onDropped: function(drop) {
            if (drop.hasText) {
                var data = drop.text.split("|")
                if (data.length >= 3) {
                    var appName = data[0]
                    var appCmd = data[1]
                    var appIcon = data[2]
                    var isCustomIcon = data.length > 3 ? data[3] === "true" : false
                    panelWindow.addToTaskbar(appName, appCmd, appIcon, isCustomIcon)
                }
            }
            isHovered = false
        }

        // Visuelles Feedback wenn über Taskbar gedraggt wird
        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(1, 1, 1, 0.05)
            visible: parent.isHovered
            radius: 0

            Behavior on opacity { NumberAnimation { duration: 150 } }
        }
    }

    Item {
        id: taskbarContainer
        anchors.fill: parent

        Row {
            id: taskbarRow
            x: {
                if (panelWindow.taskbarAlignment === "left") {
                    // Left-aligned: start from the left (workspace toggle will be after start button)
                    return 10
                } else {
                    // Centered: leave space for workspace toggle on the left
                    return (parent.width - width) / 2
                }
            }
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            // Weather Start Area Slot 0 (before start button)
            Item {
                id: weatherSlot0Container
                width: panelWindow.weatherSlotWidth; height: 40
                visible: settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot === 0
                property bool isBeingDragged: false
                z: isBeingDragged ? 100 : 0

                Rectangle {
                    id: weatherSlot0
                    width: parent.width; height: parent.height; x: 0; y: 0; radius: 8; color: "transparent"
                    property bool hovered: false
                    scale: weatherSlot0Container.isBeingDragged ? 0.9 : 1.0
                    opacity: weatherSlot0Container.isBeingDragged ? 0.5 : 1.0
                    Behavior on scale { NumberAnimation { duration: 100 } }
                    Behavior on opacity { NumberAnimation { duration: 100 } }
                    Rectangle { anchors.fill: parent; radius: 8; color: parent.hovered ? Qt.rgba(1,1,1,0.1) : "transparent"; Behavior on color { ColorAnimation { duration: 150 } } }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: panelWindow.weatherInnerMargin
                        spacing: panelWindow.weatherInnerSpacing
                        Image { width: panelWindow.weatherIconSize; height: panelWindow.weatherIconSize; source: panelWindow.weatherCode >= 0 ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay) : ""; sourceSize.width: panelWindow.weatherIconSize * 2; sourceSize.height: panelWindow.weatherIconSize * 2; fillMode: Image.PreserveAspectFit; smooth: true; antialiasing: true; mipmap: true }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: -1
                            Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? panelWindow.wmoToDesc(panelWindow.weatherCode) : Lang.get("weather.label", settingsMenu.uiLanguage); elide: Text.ElideRight; font.pixelSize: panelWindow.weatherDescFontSize; font.bold: true; color: settingsMenu.darkMode ? "#f2f2f2" : "#202124" }
                            Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? (Math.round(panelWindow.weatherTemp) + "°") : "--°"; elide: Text.ElideRight; font.pixelSize: panelWindow.weatherTempFontSize; font.bold: true; color: settingsMenu.darkMode ? "#ffffff" : "#111111" }
                        }
                    }
                    MouseArea {
                        id: weatherSlot0Area; anchors.fill: parent; hoverEnabled: true
                        property bool dragActive: false; property point dragStartPos; property int dragThreshold: 10
                        drag.target: dragActive ? weatherSlot0 : null; drag.axis: Drag.XAxis
                        onEntered: weatherSlot0.hovered = true; onExited: weatherSlot0.hovered = false
                        onPressed: function(mouse) { if (mouse.button === Qt.LeftButton) { dragStartPos = Qt.point(mouse.x, mouse.y); dragActive = false; weatherSlot0Container.isBeingDragged = false; mouse.accepted = true } }
                        onPositionChanged: function(mouse) { if (!dragActive && mouse.buttons === Qt.LeftButton) { if (Math.abs(mouse.x - dragStartPos.x) > dragThreshold || Math.abs(mouse.y - dragStartPos.y) > dragThreshold) { dragActive = true; weatherSlot0Container.isBeingDragged = true } } }
                        onReleased: function(mouse) {
                            var wasDragging = dragActive; dragActive = false; weatherSlot0Container.isBeingDragged = false
                            if (wasDragging) {
                                var cDrop0 = weatherSlot0Area.mapToItem(taskbarContainer, mouse.x, mouse.y).x
                                weatherSlot0.x = 0; weatherSlot0.y = 0
                                var ovCX0 = workspaceContainer.x + workspaceContainer.width / 2
                                if (Math.abs(cDrop0 - ovCX0) < workspaceContainer.width + 10) {
                                    settingsMenu.weatherStartAreaSlot = cDrop0 < ovCX0 ? 4 : 3; settingsMenu.saveSettings()
                                } else {
                                    var rowDropX = cDrop0 - taskbarRow.x
                                    var firstAppX = taskbarRepeater.count > 0 && taskbarRepeater.itemAt(0) ? taskbarRepeater.itemAt(0).x : taskbarRow.width
                                    if (rowDropX >= firstAppX - 10) {
                                        var idx = Math.max(0, Math.round((rowDropX - firstAppX) / 50))
                                        settingsMenu.weatherStartAreaSlot = -1; settingsMenu.weatherTaskbarIndex = Math.min(idx, panelWindow.taskbarApps.length); settingsMenu.saveSettings(); panelWindow.rebuildTaskbarModel()
                                    } else {
                                        var ns = panelWindow.getStartAreaDragSlot(rowDropX); if (ns !== 0) { settingsMenu.weatherStartAreaSlot = ns; settingsMenu.saveSettings() }
                                    }
                                }
                            } else { panelWindow.openWeatherPopup(weatherSlot0Area) }
                        }
                    }
                }
            }

            // Start Button
            Rectangle {
                id: startButton
                width: 40; height: 40; radius: 18
                color: "transparent"
                property bool hovered: false

                StartOrb {
                    anchors.centerIn: parent
                    style: settingsMenu.startOrbStyle
                    customSource: settingsMenu.startOrbCustomSource
                    width: 40
                    height: 40
                    layer.enabled: true
                    layer.smooth: true
                    opacity: startButton.hovered ? 0.75 : 1.0
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onEntered: startButton.hovered = true
                    onExited: startButton.hovered = false
                    onClicked: function(mouse) {
                        if (mouse.button === Qt.RightButton) {
                            settingsMenu.visible = false
                            audioWindow.visible = false
                            bluetoothWindow.visible = false
                            networkWindow.visible = false
                            nearbyWindow.visible = false
                            calendarWindow.visible = false
                            startMenu.visible = false
                            appContextMenu.visible = false
                            // Position power menu above the start button
                            var sbPos = startButton.mapToItem(panelWindow.contentItem, 0, 0)
                            var pmW = 220, pmH = 484
                            var primaryScreen = null
                            for (var s = 0; s < Quickshell.screens.length; s++) {
                                if (Quickshell.screens[s].name === settingsMenu.primaryMonitor) {
                                    primaryScreen = Quickshell.screens[s]; break
                                }
                            }
                            var monH = primaryScreen ? primaryScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)
                            var monW = primaryScreen ? primaryScreen.width : (panelWindow.screen ? panelWindow.screen.width : 1280)
                            var pmX = Math.max(0, Math.min(monW - pmW, Math.round(sbPos.x + startButton.width / 2 - pmW / 2)))
                            var pmY = monH - 45 - powerMenu.implicitHeight
                            var pmPosProc = Qt.createQmlObject('import Quickshell.Io; Process { }', panelWindow)
                            pmPosProc.command = ["windoesnot-hyprctl", "keyword", "windowrule[powermenu-config]:move", pmX + " " + pmY]
                            powerMenu.menuX = pmX; powerMenu.menuY = pmY
                            pmPosProc.exited.connect(function() { powerMenu.visible = true })
                            pmPosProc.running = true
                        } else {
                            settingsMenu.visible = false
                            audioWindow.visible = false
                            bluetoothWindow.visible = false
                            networkWindow.visible = false
                            nearbyWindow.visible = false
                            calendarWindow.visible = false
                            powerMenu.visible = false
                            startMenu.visible = !startMenu.visible
                        }
                    }
                }
            }

            // Spacer for workspace toggle when left-aligned
            Item {
                width: (panelWindow.taskbarAlignment === "left" && workspaceContainer.visible) ? 50 : 0
                height: 40
                visible: width > 0
            }

            // Weather Start Area Slot 1 (after start button / workspace spacer, before settings)
            Item {
                id: weatherSlot1Container
                width: panelWindow.weatherSlotWidth; height: 40
                visible: settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot === 1
                property bool isBeingDragged: false
                z: isBeingDragged ? 100 : 0

                Rectangle {
                    id: weatherSlot1
                    width: parent.width; height: parent.height; x: 0; y: 0; radius: 8; color: "transparent"
                    property bool hovered: false
                    scale: weatherSlot1Container.isBeingDragged ? 0.9 : 1.0
                    opacity: weatherSlot1Container.isBeingDragged ? 0.5 : 1.0
                    Behavior on scale { NumberAnimation { duration: 100 } }
                    Behavior on opacity { NumberAnimation { duration: 100 } }
                    Rectangle { anchors.fill: parent; radius: 8; color: parent.hovered ? Qt.rgba(1,1,1,0.1) : "transparent"; Behavior on color { ColorAnimation { duration: 150 } } }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: panelWindow.weatherInnerMargin
                        spacing: panelWindow.weatherInnerSpacing
                        Image { width: panelWindow.weatherIconSize; height: panelWindow.weatherIconSize; source: panelWindow.weatherCode >= 0 ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay) : ""; sourceSize.width: panelWindow.weatherIconSize * 2; sourceSize.height: panelWindow.weatherIconSize * 2; fillMode: Image.PreserveAspectFit; smooth: true; antialiasing: true; mipmap: true }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: -1
                            Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? panelWindow.wmoToDesc(panelWindow.weatherCode) : Lang.get("weather.label", settingsMenu.uiLanguage); elide: Text.ElideRight; font.pixelSize: panelWindow.weatherDescFontSize; font.bold: true; color: settingsMenu.darkMode ? "#f2f2f2" : "#202124" }
                            Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? (Math.round(panelWindow.weatherTemp) + "°") : "--°"; elide: Text.ElideRight; font.pixelSize: panelWindow.weatherTempFontSize; font.bold: true; color: settingsMenu.darkMode ? "#ffffff" : "#111111" }
                        }
                    }
                    MouseArea {
                        id: weatherSlot1Area; anchors.fill: parent; hoverEnabled: true
                        property bool dragActive: false; property point dragStartPos; property int dragThreshold: 10
                        drag.target: dragActive ? weatherSlot1 : null; drag.axis: Drag.XAxis
                        onEntered: weatherSlot1.hovered = true; onExited: weatherSlot1.hovered = false
                        onPressed: function(mouse) { if (mouse.button === Qt.LeftButton) { dragStartPos = Qt.point(mouse.x, mouse.y); dragActive = false; weatherSlot1Container.isBeingDragged = false; mouse.accepted = true } }
                        onPositionChanged: function(mouse) { if (!dragActive && mouse.buttons === Qt.LeftButton) { if (Math.abs(mouse.x - dragStartPos.x) > dragThreshold || Math.abs(mouse.y - dragStartPos.y) > dragThreshold) { dragActive = true; weatherSlot1Container.isBeingDragged = true } } }
                        onReleased: function(mouse) {
                            var wasDragging = dragActive; dragActive = false; weatherSlot1Container.isBeingDragged = false
                            if (wasDragging) {
                                var cDrop1 = weatherSlot1Area.mapToItem(taskbarContainer, mouse.x, mouse.y).x
                                weatherSlot1.x = 0; weatherSlot1.y = 0
                                var ovCX1 = workspaceContainer.x + workspaceContainer.width / 2
                                if (Math.abs(cDrop1 - ovCX1) < workspaceContainer.width + 10) {
                                    settingsMenu.weatherStartAreaSlot = cDrop1 < ovCX1 ? 4 : 3; settingsMenu.saveSettings()
                                } else {
                                    var rowDropX = cDrop1 - taskbarRow.x
                                    var firstAppX = taskbarRepeater.count > 0 && taskbarRepeater.itemAt(0) ? taskbarRepeater.itemAt(0).x : taskbarRow.width
                                    if (rowDropX >= firstAppX - 10) {
                                        var idx = Math.max(0, Math.round((rowDropX - firstAppX) / 50))
                                        settingsMenu.weatherStartAreaSlot = -1; settingsMenu.weatherTaskbarIndex = Math.min(idx, panelWindow.taskbarApps.length); settingsMenu.saveSettings(); panelWindow.rebuildTaskbarModel()
                                    } else {
                                        var ns = panelWindow.getStartAreaDragSlot(rowDropX); if (ns !== 1) { settingsMenu.weatherStartAreaSlot = ns; settingsMenu.saveSettings() }
                                    }
                                }
                            } else { panelWindow.openWeatherPopup(weatherSlot1Area) }
                        }
                    }
                }
            }

            // Settings Button
            Rectangle {
                id: settingsButton
                width: 40; height: 40; radius: 18
                color: "transparent"
                property bool hovered: false
                visible: settingsMenu.showSettingsButton

                Image {
                    anchors.centerIn: parent
                    source: "img/settings.svg"
                    width: 32
                    height: 32
                    sourceSize.width: 32
                    sourceSize.height: 32
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                    mipmap: true
                    layer.enabled: true
                    layer.smooth: true
                    opacity: settingsButton.hovered ? 0.75 : 1.0
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: settingsButton.hovered = true
                    onExited: settingsButton.hovered = false
                    onClicked: {
                        startMenu.visible = false
                        audioWindow.visible = false
                        bluetoothWindow.visible = false
                        networkWindow.visible = false
                        nearbyWindow.visible = false
                        calendarWindow.visible = false
                        settingsMenu.visible = !settingsMenu.visible
                    }
                }
            }

            // Weather Start Area Slot 2 (after settings button, before search)
            Item {
                id: weatherSlot2Container
                width: panelWindow.weatherSlotWidth; height: 40
                visible: settingsMenu.weatherEnabled && settingsMenu.weatherLocation === "taskbar" && settingsMenu.weatherStartAreaSlot === 2
                property bool isBeingDragged: false
                z: isBeingDragged ? 100 : 0

                Rectangle {
                    id: weatherSlot2
                    width: parent.width; height: parent.height; x: 0; y: 0; radius: 8; color: "transparent"
                    property bool hovered: false
                    scale: weatherSlot2Container.isBeingDragged ? 0.9 : 1.0
                    opacity: weatherSlot2Container.isBeingDragged ? 0.5 : 1.0
                    Behavior on scale { NumberAnimation { duration: 100 } }
                    Behavior on opacity { NumberAnimation { duration: 100 } }
                    Rectangle { anchors.fill: parent; radius: 8; color: parent.hovered ? Qt.rgba(1,1,1,0.1) : "transparent"; Behavior on color { ColorAnimation { duration: 150 } } }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: panelWindow.weatherInnerMargin
                        spacing: panelWindow.weatherInnerSpacing
                        Image { width: panelWindow.weatherIconSize; height: panelWindow.weatherIconSize; source: panelWindow.weatherCode >= 0 ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay) : ""; sourceSize.width: panelWindow.weatherIconSize * 2; sourceSize.height: panelWindow.weatherIconSize * 2; fillMode: Image.PreserveAspectFit; smooth: true; antialiasing: true; mipmap: true }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: -1
                            Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? panelWindow.wmoToDesc(panelWindow.weatherCode) : Lang.get("weather.label", settingsMenu.uiLanguage); elide: Text.ElideRight; font.pixelSize: panelWindow.weatherDescFontSize; font.bold: true; color: settingsMenu.darkMode ? "#f2f2f2" : "#202124" }
                            Text { width: panelWindow.weatherTextWidth; text: panelWindow.weatherCode >= 0 ? (Math.round(panelWindow.weatherTemp) + "°") : "--°"; elide: Text.ElideRight; font.pixelSize: panelWindow.weatherTempFontSize; font.bold: true; color: settingsMenu.darkMode ? "#ffffff" : "#111111" }
                        }
                    }
                    MouseArea {
                        id: weatherSlot2Area; anchors.fill: parent; hoverEnabled: true
                        property bool dragActive: false; property point dragStartPos; property int dragThreshold: 10
                        drag.target: dragActive ? weatherSlot2 : null; drag.axis: Drag.XAxis
                        onEntered: weatherSlot2.hovered = true; onExited: weatherSlot2.hovered = false
                        onPressed: function(mouse) { if (mouse.button === Qt.LeftButton) { dragStartPos = Qt.point(mouse.x, mouse.y); dragActive = false; weatherSlot2Container.isBeingDragged = false; mouse.accepted = true } }
                        onPositionChanged: function(mouse) { if (!dragActive && mouse.buttons === Qt.LeftButton) { if (Math.abs(mouse.x - dragStartPos.x) > dragThreshold || Math.abs(mouse.y - dragStartPos.y) > dragThreshold) { dragActive = true; weatherSlot2Container.isBeingDragged = true } } }
                        onReleased: function(mouse) {
                            var wasDragging = dragActive; dragActive = false; weatherSlot2Container.isBeingDragged = false
                            if (wasDragging) {
                                var cDrop2 = weatherSlot2Area.mapToItem(taskbarContainer, mouse.x, mouse.y).x
                                weatherSlot2.x = 0; weatherSlot2.y = 0
                                var ovCX2 = workspaceContainer.x + workspaceContainer.width / 2
                                if (Math.abs(cDrop2 - ovCX2) < workspaceContainer.width + 10) {
                                    settingsMenu.weatherStartAreaSlot = cDrop2 < ovCX2 ? 4 : 3; settingsMenu.saveSettings()
                                } else {
                                    var rowDropX = cDrop2 - taskbarRow.x
                                    var firstAppX = taskbarRepeater.count > 0 && taskbarRepeater.itemAt(0) ? taskbarRepeater.itemAt(0).x : taskbarRow.width
                                    if (rowDropX >= firstAppX - 10) {
                                        var idx = Math.max(0, Math.round((rowDropX - firstAppX) / 50))
                                        settingsMenu.weatherStartAreaSlot = -1; settingsMenu.weatherTaskbarIndex = Math.min(idx, panelWindow.taskbarApps.length); settingsMenu.saveSettings(); panelWindow.rebuildTaskbarModel()
                                    } else {
                                        var ns = panelWindow.getStartAreaDragSlot(rowDropX); if (ns !== 2) { settingsMenu.weatherStartAreaSlot = ns; settingsMenu.saveSettings() }
                                    }
                                }
                            } else { panelWindow.openWeatherPopup(weatherSlot2Area) }
                        }
                    }
                }
            }

            // Search Button
            Rectangle {
                id: searchTaskbarButton
                width: 40; height: 40; radius: 18
                color: "transparent"
                property bool hovered: false
                visible: settingsMenu.showSearchButton

                Image {
                    anchors.centerIn: parent
                    source: "img/search.svg"
                    width: 28; height: 28
                    sourceSize.width: 28; sourceSize.height: 28
                    fillMode: Image.PreserveAspectFit
                    smooth: true; antialiasing: true; mipmap: true
                    layer.enabled: true; layer.smooth: true
                    opacity: searchTaskbarButton.hovered ? 0.75 : 1.0
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: searchTaskbarButton.hovered = true
                    onExited:  searchTaskbarButton.hovered = false
                    onClicked: {
                        startMenu.visible = false
                        powerMenu.visible = false
                        powerSubMenu.visible = false
                        searchWindow.openSearch()
                    }
                }
            }

            // Store Button: opens the WinDoesNot Store or brings its window back
            Rectangle {
                id: storeTaskbarButton
                width: 40; height: 40; radius: 18
                color: "transparent"
                property bool hovered: false
                property var storeWindow: panelWindow.storeWindows.length > 0 ? panelWindow.storeWindows[0] : null
                visible: settingsMenu.showStoreButton

                Image {
                    anchors.centerIn: parent
                    source: "image://icon/system-software-install"
                    width: 28; height: 28
                    sourceSize.width: 28; sourceSize.height: 28
                    fillMode: Image.PreserveAspectFit
                    smooth: true; antialiasing: true; mipmap: true
                    opacity: storeTaskbarButton.hovered ? 0.75 : 1.0
                }

                // Running indicator, as for taskbar apps
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: storeTaskbarButton.storeWindow ? 20 : 0
                    height: 3; radius: 1.5
                    visible: storeTaskbarButton.storeWindow !== null
                    color: storeTaskbarButton.storeWindow && !storeTaskbarButton.storeWindow.hidden
                        ? settingsMenu.accentColor : Qt.rgba(0.5, 0.5, 0.5, 0.6)
                    Behavior on width { NumberAnimation { duration: 150 } }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: storeTaskbarButton.hovered = true
                    onExited:  storeTaskbarButton.hovered = false
                    onClicked: {
                        startMenu.visible = false
                        powerMenu.visible = false
                        powerSubMenu.visible = false
                        var win = storeTaskbarButton.storeWindow
                        var cmd = "windoesnot-store"
                        if (win && win.hidden) {
                            cmd = "windoesnot-hyprctl dispatch movetoworkspace e+0,address:" + win.address +
                                  " && windoesnot-hyprctl dispatch focuswindow address:" + win.address
                        } else if (win && win.focused) {
                            cmd = "windoesnot-hyprctl dispatch movetoworkspacesilent special:minimized,address:" + win.address
                        } else if (win) {
                            cmd = "windoesnot-hyprctl dispatch focuswindow address:" + win.address
                        }
                        Qt.createQmlObject(
                            'import Quickshell.Io; Process { command: ["bash", "-c", "' + cmd + '"]; running: true }',
                            panelWindow
                        )
                    }
                }
            }

            // Dynamische Taskbar Apps
            Repeater {
                id: taskbarRepeater
                model: taskbarAppsModel

                delegate: Item {
                    id: taskbarItemDelegate
                    width: (model.isWeather !== undefined && model.isWeather) ? panelWindow.weatherSlotWidth : (model.cmd === panelWindow.internalCopilotCmd ? 46 : 40)
                    height: 40

                    property int visualIndex: index
                    property bool isBeingDragged: false

                    // Raise z-order when dragging (like weather widget)
                    z: isBeingDragged ? 100 : 0

                    Rectangle {
                        id: taskbarAppItem
                        width: parent.width
                        height: parent.height
                        x: 0
                        y: 0
                        radius: 8
                        color: "transparent"
                        property bool hovered: false
                        property bool isCustomIcon: model.customIcon !== undefined ? model.customIcon : false
                        property bool isWeatherItem: model.isWeather !== undefined ? model.isWeather : false
                        property bool isInternalCopilotApp: model.cmd === panelWindow.internalCopilotCmd
                        property bool isOpen: isWeatherItem ? false : (isInternalCopilotApp ? (copilotWindow ? copilotWindow.visible : false) : panelWindow.isAppOpen(model.name))

                        scale: taskbarItemDelegate.isBeingDragged ? 0.9 : 1.0
                        opacity: taskbarItemDelegate.isBeingDragged ? 0.5 : 1.0

                        Behavior on scale { NumberAnimation { duration: 100 } }
                        Behavior on opacity { NumberAnimation { duration: 100 } }

                        // Drag.active enables Qt visual drag (like weather widget)
                        Drag.active: taskbarDragArea.drag.active
                        Drag.hotSpot.x: width / 2
                        Drag.hotSpot.y: height / 2

                        Rectangle {
                            anchors.fill: parent
                            radius: 8
                            color: taskbarAppItem.hovered ? Qt.rgba(1, 1, 1, 0.1) : "transparent"

                            Behavior on color { ColorAnimation { duration: 150 } }
                        }

                        // Normal app icon
                        AppIcon {
                            visible: !taskbarAppItem.isWeatherItem
                            anchors.centerIn: parent
                            iconName: model.icon
                            isCustomIcon: taskbarAppItem.isCustomIcon
                            width: taskbarAppItem.isInternalCopilotApp ? 36 : 32
                            height: taskbarAppItem.isInternalCopilotApp ? 36 : 32
                            opacity: taskbarAppItem.hovered ? 0.75 : 1.0
                        }

                        // Weather icon with description + temperature
                        Item {
                            visible: taskbarAppItem.isWeatherItem
                            anchors.fill: parent
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: panelWindow.weatherInnerMargin
                                spacing: panelWindow.weatherInnerSpacing
                                Image {
                                    width: panelWindow.weatherIconSize; height: panelWindow.weatherIconSize
                                    source: panelWindow.weatherCode >= 0
                                        ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay)
                                        : ""
                                    sourceSize.width: panelWindow.weatherIconSize * 2; sourceSize.height: panelWindow.weatherIconSize * 2
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true; antialiasing: true; mipmap: true
                                }
                                Column {
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: -1
                                    Text {
                                        width: panelWindow.weatherTextWidth
                                        text: panelWindow.weatherCode >= 0 ? panelWindow.wmoToDesc(panelWindow.weatherCode) : Lang.get("weather.label", settingsMenu.uiLanguage)
                                        elide: Text.ElideRight
                                        font.pixelSize: panelWindow.weatherDescFontSize; font.bold: true
                                        color: settingsMenu.darkMode ? "#f2f2f2" : "#202124"
                                    }
                                    Text {
                                        width: panelWindow.weatherTextWidth
                                        text: panelWindow.weatherCode >= 0 ? (Math.round(panelWindow.weatherTemp) + "°") : "--°"
                                        elide: Text.ElideRight
                                        font.pixelSize: panelWindow.weatherTempFontSize; font.bold: true
                                        color: settingsMenu.darkMode ? "#ffffff" : "#111111"
                                    }
                                }
                            }
                        }

                        // Windows 11-style indicator for open apps
                        Rectangle {
                            anchors {
                                bottom: parent.bottom
                                horizontalCenter: parent.horizontalCenter
                                bottomMargin: -3
                            }
                            width: taskbarAppItem.isOpen ? 20 : 0
                            height: 3
                            radius: 1.5
                            // Accent color if any window visible, gray if all hidden
                            color: {
                                if (!taskbarAppItem.isOpen) return "transparent"
                                if (taskbarAppItem.isInternalCopilotApp) return settingsMenu.accentColor

                                var windows = panelWindow.openWindows[model.name]
                                if (!windows || windows.length === 0) return "transparent"

                                // Check if at least one window is visible (not hidden)
                                var hasVisibleWindow = false
                                for (var i = 0; i < windows.length; i++) {
                                    if (!windows[i].hidden) {
                                        hasVisibleWindow = true
                                        break
                                    }
                                }

                                return hasVisibleWindow ? settingsMenu.accentColor : Qt.rgba(0.5, 0.5, 0.5, 0.6)
                            }
                            visible: taskbarAppItem.isOpen

                            Behavior on width { NumberAnimation { duration: 150 } }
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }

                        MouseArea {
                            id: taskbarDragArea
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton

                            property bool dragActive: false
                            property point dragStartPos
                            property int dragThreshold: 10  // Wie beim Startmenü-Drag

                            // Enable visual dragging when active
                            drag.target: dragActive ? taskbarAppItem : null
                            drag.axis: Drag.XAxis

                            onEntered: {
                                taskbarAppItem.hovered = true
                                if (taskbarAppItem.isInternalCopilotApp) {
                                    taskbarPreview.iconHovering = false
                                    taskbarPreview.cancelShow()
                                    taskbarPreview.startHide()
                                    return
                                }
                                var wins = panelWindow.openWindows[model.name] || []
                                var showPreview = wins.length > 1 ||
                                    (settingsMenu.windowMode === "floating" && wins.length === 1)
                                if (showPreview) {
                                    taskbarPreview.iconHovering = true
                                    taskbarPreview.cancelHide()
                                    // Skip re-capture if already showing this app — avoids black flash
                                    if (taskbarPreview.visible && taskbarPreview.appName === model.name) {
                                        // nothing — keep existing preview as-is
                                    } else {
                                    var itemPos = taskbarDragArea.mapToItem(panelWindow.contentItem, 0, 0)
                                    var iconCenterX = Math.round(itemPos.x + taskbarDragArea.width / 2)
                                    var pScreen = null
                                    for (var s = 0; s < Quickshell.screens.length; s++) {
                                        if (Quickshell.screens[s].name === settingsMenu.primaryMonitor) {
                                            pScreen = Quickshell.screens[s]; break
                                        }
                                    }
                                    var monW = pScreen ? pScreen.width  : (panelWindow.screen ? panelWindow.screen.width : 1280)
                                    var monH = pScreen ? pScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)
                                    taskbarPreview.prepareFor(model.name, wins, iconCenterX, monW, monH, model.icon, model.customIcon)
                                    }
                                } else {
                                    taskbarPreview.iconHovering = false
                                    taskbarPreview.cancelShow()
                                    taskbarPreview.startHide()
                                }
                            }
                            onExited: {
                                taskbarAppItem.hovered = false
                                taskbarPreview.iconHovering = false
                                taskbarPreview.cancelShow()
                                // No startHide() here — iconLeaveTimer in TaskbarPreview
                                // handles the bounce guard for Hyprland surface-map events
                            }

                            onPressed: function(mouse) {
                                if (mouse.button === Qt.LeftButton) {
                                    dragStartPos = Qt.point(mouse.x, mouse.y)
                                    dragActive = false
                                    taskbarItemDelegate.isBeingDragged = false
                                    mouse.accepted = true
                                }
                            }

                            onPositionChanged: function(mouse) {
                                if (!dragActive && mouse.buttons === Qt.LeftButton) {
                                    // Check if moved beyond threshold
                                    var dx = Math.abs(mouse.x - dragStartPos.x)
                                    var dy = Math.abs(mouse.y - dragStartPos.y)
                                    if (dx > dragThreshold || dy > dragThreshold) {
                                        dragActive = true
                                        taskbarItemDelegate.isBeingDragged = true
                                        // Close preview to unblock mouse
                                        taskbarPreview.iconHovering = false
                                        taskbarPreview.cancelShow()
                                        taskbarPreview.startHide()
                                    }
                                } else if (dragActive) {
                                    taskbarItemDelegate.isBeingDragged = true
                                }
                            }

                            onReleased: function(mouse) {
                                var wasDragging = dragActive

                                if (wasDragging) {
                                    // Calculate drop position in taskbar
                                    var dropX = taskbarDragArea.mapToItem(taskbarRow, mouse.x, mouse.y).x

                                    // Check if weather item dragged to start area or overview area
                                    if (taskbarAppItem.isWeatherItem) {
                                        // Check overview area (slot 3) using taskbarContainer coords
                                        var cDropX = taskbarDragArea.mapToItem(taskbarContainer, mouse.x, mouse.y).x
                                        var ovCenterX = workspaceContainer.x + workspaceContainer.width / 2
                                        if (Math.abs(cDropX - ovCenterX) < workspaceContainer.width + 10) {
                                            settingsMenu.weatherStartAreaSlot = cDropX < ovCenterX ? 4 : 3
                                            settingsMenu.saveSettings()
                                            panelWindow.rebuildTaskbarModel()
                                            taskbarItemDelegate.isBeingDragged = false
                                            dragActive = false
                                            return
                                        }
                                        // Check start area (slots 0-2) in taskbarRow coords
                                        var firstAppX = taskbarRepeater.count > 0 && taskbarRepeater.itemAt(0) ? taskbarRepeater.itemAt(0).x : -1
                                        if (firstAppX > 0 && dropX < firstAppX - 10) {
                                            settingsMenu.weatherStartAreaSlot = panelWindow.getStartAreaDragSlot(dropX)
                                            settingsMenu.saveSettings()
                                            panelWindow.rebuildTaskbarModel()
                                            taskbarItemDelegate.isBeingDragged = false
                                            dragActive = false
                                            return
                                        }
                                    }

                                    // Find insertion point: check each item boundary
                                    var targetIndex = 0

                                    for (var i = 0; i < taskbarRepeater.count; i++) {
                                        var item = taskbarRepeater.itemAt(i)
                                        if (!item) continue

                                        var itemMid = item.x + item.width / 2

                                        // If drop left of midpoint, insert here
                                        // Otherwise, try next position
                                        if (dropX <= itemMid) {
                                            targetIndex = i
                                            break
                                        } else {
                                            targetIndex = i + 1
                                        }
                                    }

                                    // Adjust when moving right (array shrinks before reinsertion)
                                    if (targetIndex > visualIndex) {
                                        targetIndex--
                                    }

                                    // Clamp
                                    if (targetIndex < 0) targetIndex = 0
                                    var maxIndex = taskbarRepeater.count - 1
                                    if (targetIndex > maxIndex) targetIndex = maxIndex

                                    if (targetIndex !== visualIndex) {
                                        console.log("Taskbar drag from", visualIndex, "to", targetIndex, "(repeater indices)")
                                        // Note: reorderTaskbarApps expects indices that include weather widget
                                        // visualIndex and targetIndex are already from taskbarRepeater which includes weather
                                        panelWindow.reorderTaskbarApps(visualIndex, targetIndex)
                                    }

                                    // Cleanup after drag
                                    dragActive = false
                                    taskbarItemDelegate.isBeingDragged = false
                                    taskbarAppItem.x = 0
                                    taskbarAppItem.y = 0
                                } else {
                                    // Not dragging - just click
                                    dragActive = false
                                    taskbarItemDelegate.isBeingDragged = false
                                    // Normal click (released before hold delay or without movement)
                                    if (mouse.button === Qt.RightButton && !taskbarAppItem.isWeatherItem && !taskbarAppItem.isInternalCopilotApp) {
                                        // Right click: open context menu
                                        startMenu.visible = false
                                        settingsMenu.visible = false
                                        audioWindow.visible = false
                                        bluetoothWindow.visible = false
                                        networkWindow.visible = false
                                        nearbyWindow.visible = false
                                        calendarWindow.visible = false
                                        powerMenu.visible = false
                                        // Set context data
                                        appContextMenu.ctxAppName = model.name
                                        appContextMenu.ctxAppCmd = model.cmd
                                        appContextMenu.ctxAppPinned = model.pinned !== undefined ? model.pinned : false
                                        appContextMenu.ctxAppTemporary = model.temporary !== undefined ? model.temporary : false
                                        appContextMenu.ctxAppWindows = panelWindow.openWindows[model.name] || []
                                        // Calculate position: center menu above clicked icon
                                        var itemPos = taskbarDragArea.mapToItem(panelWindow.contentItem, 0, 0)
                                        var primaryScreen = null
                                        for (var s = 0; s < Quickshell.screens.length; s++) {
                                            if (Quickshell.screens[s].name === settingsMenu.primaryMonitor) {
                                                primaryScreen = Quickshell.screens[s]; break
                                            }
                                        }
                                        var monH = primaryScreen ? primaryScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)
                                        var monW = primaryScreen ? primaryScreen.width : (panelWindow.screen ? panelWindow.screen.width : 1280)
                                        var acmW = 220
                                        var acmWins = panelWindow.openWindows[model.name] || []
                                        var acmH = acmWins.length > 0 ? 129 : 84
                                        var acmX = Math.max(0, Math.min(monW - acmW, Math.round(itemPos.x + taskbarDragArea.width / 2 - acmW / 2)))
                                        var acmY = monH - 45 - acmH
                                        appContextMenu.menuX = acmX
                                        appContextMenu.visible = true
                                    } else {
                                        // Left click: weather opens popup, others toggle/launch
                                        if (taskbarAppItem.isWeatherItem) {
                                            panelWindow.openWeatherPopup(taskbarDragArea)
                                        } else if (taskbarAppItem.isInternalCopilotApp) {
                                            startMenu.visible = false
                                            settingsMenu.visible = false
                                            audioWindow.visible = false
                                            bluetoothWindow.visible = false
                                            networkWindow.visible = false
                                            nearbyWindow.visible = false
                                            calendarWindow.visible = false
                                            dockerWindow.visible = false
                                            panelWindow.openCopilotPopup(taskbarDragArea)
                                        } else if (taskbarAppItem.isOpen) {
                                            var windows = panelWindow.openWindows[model.name]
                                            var clickProc = Qt.createQmlObject(
                                                'import Quickshell.Io; Process { }',
                                                panelWindow
                                            )

                                            // Collect all visible and hidden windows
                                            var visibleWindows = []
                                            var hiddenWindows = []

                                            for (var i = 0; i < windows.length; i++) {
                                                if (windows[i].hidden) {
                                                    hiddenWindows.push(windows[i])
                                                } else {
                                                    visibleWindows.push(windows[i])
                                                }
                                            }

                                            if (settingsMenu.windowMode === "floating" &&
                                                    (visibleWindows.length > 0 || hiddenWindows.length > 0)) {
                                                // Floating mode: show preview popup.
                                                // Visible windows: click card to raise to front.
                                                // Hidden windows: click card to restore. Minimize via right-click context menu.
                                                var fWins = panelWindow.openWindows[model.name] || []
                                                var fItemPos = taskbarDragArea.mapToItem(panelWindow.contentItem, 0, 0)
                                                var fIconCX = Math.round(fItemPos.x + taskbarDragArea.width / 2)
                                                var fScreen = null
                                                for (var fs = 0; fs < Quickshell.screens.length; fs++) {
                                                    if (Quickshell.screens[fs].name === settingsMenu.primaryMonitor) {
                                                        fScreen = Quickshell.screens[fs]; break
                                                    }
                                                }
                                                var fMonW = fScreen ? fScreen.width  : (panelWindow.screen ? panelWindow.screen.width : 1280)
                                                var fMonH = fScreen ? fScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)
                                                taskbarPreview.prepareFor(model.name, fWins, fIconCX, fMonW, fMonH, model.icon, model.customIcon)
                                                taskbarPreview.iconHovering = true
                                                taskbarPreview.cancelHide()
                                            } else if (visibleWindows.length > 0) {
                                                // Minimize visible windows (tiling mode, or floating single non-occluded window)
                                                console.log("Minimizing", visibleWindows.length, "visible window(s):", model.name)
                                                var minimizeCommands = []
                                                for (var j = 0; j < visibleWindows.length; j++) {
                                                    minimizeCommands.push("windoesnot-hyprctl dispatch movetoworkspacesilent special:minimized,address:" + visibleWindows[j].address)
                                                }
                                                clickProc.command = ["bash", "-c", minimizeCommands.join(" && ")]
                                                clickProc.running = true
                                            } else if (hiddenWindows.length > 0) {
                                                // Tiling mode: restore ALL hidden windows and focus the first one
                                                console.log("Restoring", hiddenWindows.length, "hidden window(s):", model.name)
                                                var restoreCommands = []
                                                for (var k = 0; k < hiddenWindows.length; k++) {
                                                    var targetWorkspace = hiddenWindows[k].restoreWorkspace
                                                    if (targetWorkspace < 0) {
                                                        // No stored workspace: move to current active workspace
                                                        restoreCommands.push("windoesnot-hyprctl dispatch movetoworkspace e+0,address:" + hiddenWindows[k].address)
                                                    } else if (k === 0) {
                                                        // First window: use movetoworkspace (not silent) to force visual workspace switch and proper rendering
                                                        restoreCommands.push("windoesnot-hyprctl dispatch movetoworkspace " + targetWorkspace + ",address:" + hiddenWindows[k].address)
                                                    } else {
                                                        restoreCommands.push("windoesnot-hyprctl dispatch movetoworkspacesilent " + targetWorkspace + ",address:" + hiddenWindows[k].address)
                                                    }
                                                }
                                                // Focus the first restored window, then send a configure event via
                                                // a 1px resize (immediately reverted) to wake up the Wayland client.
                                                // This fixes a Hyprland bug where GTK4 windows restored from
                                                // special:minimized stop rendering until they receive a configure event.
                                                restoreCommands.push("sleep 0.15")
                                                restoreCommands.push("windoesnot-hyprctl dispatch focuswindow address:" + hiddenWindows[0].address)
                                                restoreCommands.push("windoesnot-hyprctl dispatch resizeactive 1 0")
                                                restoreCommands.push("windoesnot-hyprctl dispatch resizeactive -1 0")
                                                clickProc.command = ["bash", "-c", restoreCommands.join(" && ")]
                                                clickProc.running = true
                                            }
                                        } else {
                                            // App is not open, launch it
                                            console.log("Launching app:", model.name, "with command:", model.cmd)
                                            var launchProc = Qt.createQmlObject(
                                                'import Quickshell.Io; Process { }',
                                                panelWindow
                                            )
                                            if (model.cmd === panelWindow.internalCopilotCmd) {
                                                panelWindow.openCopilotPopup(taskbarDragArea)
                                            } else {
                                                launchProc.command = ["bash", "-c", model.cmd + " & disown"]
                                                launchProc.running = true
                                            }
                                        }
                                    }
                                }
                                dragActive = false
                                taskbarItemDelegate.isBeingDragged = false
                            }

                            onCanceled: {
                                dragActive = false
                                taskbarItemDelegate.isBeingDragged = false
                            }
                        }
                    }
                }
            }

        }
    }


    // Right-click on empty taskbar area → show hidden windows menu
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        z: -1
        onClicked: function(mouse) {
            // Collect all hidden windows across all apps
            var hiddenList = []
            for (var appName in panelWindow.openWindows) {
                var wins = panelWindow.openWindows[appName]
                for (var i = 0; i < wins.length; i++) {
                    if (wins[i].hidden) {
                        // Find icon for this app
                        var icon = "application-x-executable"
                        var customIcon = false
                        for (var j = 0; j < taskbarAppsModel.count; j++) {
                            var a = taskbarAppsModel.get(j)
                            if (a.name === appName) { icon = a.icon; customIcon = a.customIcon; break }
                        }
                        hiddenList.push({
                            appName: appName,
                            title: wins[i].title || appName,
                            address: wins[i].address,
                            restoreWorkspace: wins[i].restoreWorkspace,
                            icon: icon,
                            customIcon: customIcon
                        })
                    }
                }
            }
            taskbarBgMenu.hiddenWindows = hiddenList

            // Position above click point
            var pScreen = null
            for (var s = 0; s < Quickshell.screens.length; s++) {
                if (Quickshell.screens[s].name === settingsMenu.primaryMonitor) { pScreen = Quickshell.screens[s]; break }
            }
            var monW = pScreen ? pScreen.width  : (panelWindow.screen ? panelWindow.screen.width : 1280)
            var monH = pScreen ? pScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)
            var menuH = taskbarBgMenu.implicitHeight
            var menuW = taskbarBgMenu.implicitWidth
            var mx = Math.min(mouse.x, monW - menuW - 4)
            var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', panelWindow)
            proc.command = ["bash", "-c",
                "windoesnot-hyprctl keyword 'windowrule[tbgmenu]:size " + menuW + " " + menuH + "' ; " +
                "windoesnot-hyprctl keyword 'windowrule[tbgmenu]:move " + Math.round(mx) + " " + (monH - 45 - menuH) + "'"]
            proc.exited.connect(function() { taskbarBgMenu.visible = true })
            proc.running = true
        }
    }

}

// Top Notification Bar
TopNotificationBar {
    id: topBar
    accentColor: settingsMenu.accentColor
    borderRadius: settingsMenu.borderRadius
    darkMode: settingsMenu.darkMode
    uiLanguage: settingsMenu.uiLanguage
    mediaPlayerVisible: mediaPlayer.visible
    primaryMonitorName: settingsMenu.primaryMonitor
    blockHover: snapManager.isDragging   // Bar deaktivieren während Fenster gezogen wird

    onOpenMediaPlayer: {
        mediaPlayer.player = topBar.activePlayer
        mediaPlayer.visible = true
    }
}

// Media Player Window
MediaPlayerWindow {
    id: mediaPlayer
    accentColor: settingsMenu.accentColor
    borderRadius: settingsMenu.borderRadius
    darkMode: settingsMenu.darkMode
    primaryMonitorName: settingsMenu.primaryMonitor
}

FloatingWindow {
    id: startMenu
    visible: false
    implicitWidth: settingsMenu.startMenuSidebarPosition === "hidden" ? 605 : 820
    implicitHeight: 720
    color: "transparent"
    title: "quickshell-startmenu"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor) {
                return Quickshell.screens[i]
            }
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    HyprlandFocusGrab {
        id: startMenuGrab
        windows: [startMenu]
        active: startMenu.visible
        onCleared: startMenu.visible = false
    }

    property string searchText: ""
    property string currentUser: ""
    property string userAvatar: ""
    property int selectedAppIndex: 0
    property var filteredApps: []
    property bool keyboardNavigation: true
    property var pinnedAppNames: []  // Liste der gepinnten App-Namen
    property bool pinnedAppsLoaded: false
    property string currentSection: "allApps"  // "allApps" | "personalized"

    function loadPinnedApps() {
        var configPath = Qt.resolvedUrl("pinned.txt").toString().replace("file://", "")
        console.log("Loading pinned apps from:", configPath)

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "if [ -f \'' + configPath + '\' ]; then cat \'' + configPath + '\'; fi"]; ' +
            'running: true; ' +
            'stdout: StdioCollector { ' +
            'onStreamFinished: { ' +
            'var lines = this.text.trim().split("\\n"); ' +
            'startMenu.pinnedAppNames = lines.filter(function(l) { return l.length > 0 }); ' +
            'startMenu.pinnedAppsLoaded = true; ' +
            'console.log("Loaded", startMenu.pinnedAppNames.length, "pinned apps:", JSON.stringify(startMenu.pinnedAppNames)); ' +
            '} } }',
            startMenu
        )
    }

    function savePinnedApps() {
        var configPath = Qt.resolvedUrl("pinned.txt").toString().replace("file://", "")
        var content = pinnedAppNames.join("\n")

        console.log("Saving", pinnedAppNames.length, "pinned apps to:", configPath)
        console.log("Content:", JSON.stringify(pinnedAppNames))

        var proc = Qt.createQmlObject(
            'import Quickshell.Io; Process { ' +
            'command: ["bash", "-c", "echo \'' + content.replace(/'/g, "'\\''") + '\' > \'' + configPath + '\'"]; ' +
            'running: true; ' +
            'stdout: StdioCollector { onStreamFinished: console.log("Pinned apps saved successfully") } }',
            startMenu
        )
    }

    function pinIndex(appName, aliases) {
        var names = aliases || [appName]
        for (var i = 0; i < pinnedAppNames.length; i++) {
            if (pinnedAppNames[i] === appName || names.indexOf(pinnedAppNames[i]) >= 0) return i
        }
        return -1
    }

    function togglePin(appName) {
        var aliases = [appName]
        for (var a = 0; a < allAppsModel.count; a++) {
            var candidate = allAppsModel.get(a)
            if (candidate.name === appName) { aliases = JSON.parse(candidate.pinAliases || "[]"); break }
        }
        var idx = pinIndex(appName, aliases)
        if (idx >= 0) {
            // Entpinnen
            pinnedAppNames.splice(idx, 1)
            console.log("Unpinned:", appName)
        } else {
            // Anpinnen
            pinnedAppNames.push(appName)
            console.log("Pinned:", appName)
        }
        pinnedAppNames = pinnedAppNames.slice()  // Array aktualisieren
        savePinnedApps()
        // Apps neu laden um Änderungen anzuzeigen
        desktopFilesProc.running = true
    }

    function reorderPinnedApps(fromIndex, toIndex) {
        // Hole nur die gepinnten Apps in der aktuellen Reihenfolge
        var currentPinned = []
        var currentPinnedData = []

        for (var i = 0; i < allAppsModel.count; i++) {
            var app = allAppsModel.get(i)
            if (app.pinned) {
                currentPinned.push(app.name)
                currentPinnedData.push({
                    name: app.name,
                    cmd: app.cmd,
                    icon: app.icon,
                    customIcon: app.customIcon,
                    pinAliases: app.pinAliases || "[]"
                })
            }
        }

        // Verschiebe das Element
        if (fromIndex >= 0 && fromIndex < currentPinned.length &&
            toIndex >= 0 && toIndex < currentPinned.length && fromIndex !== toIndex) {

            var movedName = currentPinned.splice(fromIndex, 1)[0]
            currentPinned.splice(toIndex, 0, movedName)

            var movedData = currentPinnedData.splice(fromIndex, 1)[0]
            currentPinnedData.splice(toIndex, 0, movedData)

            pinnedAppNames = currentPinned
            savePinnedApps()

            console.log("Reordered:", fromIndex, "->", toIndex, "New order:", JSON.stringify(pinnedAppNames))

            // Model direkt aktualisieren statt neu zu laden
            rebuildModel(currentPinnedData)
        }
    }

    function rebuildModel(pinnedData) {
        // Sammle alle ungepinnten Apps
        var unpinnedApps = []
        for (var i = 0; i < allAppsModel.count; i++) {
            var app = allAppsModel.get(i)
            if (!app.pinned) {
                unpinnedApps.push({
                    name: app.name,
                    cmd: app.cmd,
                    icon: app.icon,
                    customIcon: app.customIcon,
                    pinAliases: app.pinAliases || "[]",
                    pinned: false
                })
            }
        }

        // Model neu aufbauen
        allAppsModel.clear()

        // Erst gepinnte Apps (in neuer Reihenfolge)
        for (var j = 0; j < pinnedData.length; j++) {
            allAppsModel.append({
                name: pinnedData[j].name,
                cmd: pinnedData[j].cmd,
                icon: pinnedData[j].icon,
                customIcon: pinnedData[j].customIcon,
                pinAliases: pinnedData[j].pinAliases || "[]",
                pinned: true
            })
        }

        // Dann ungepinnte Apps
        for (var k = 0; k < unpinnedApps.length; k++) {
            allAppsModel.append(unpinnedApps[k])
        }

        updateFilteredApps()
    }

    function updateFilteredApps() {
        filteredApps = []

        if (searchText.length > 0) {
            // Bei Suche: Erst ungepinnte, dann gepinnte Apps
            for (var j = 0; j < allAppsModel.count; j++) {
                var app2 = allAppsModel.get(j)
                if (!app2.pinned && app2.name.toLowerCase().includes(searchText.toLowerCase())) {
                    filteredApps.push(j)
                }
            }
            for (var i = 0; i < allAppsModel.count; i++) {
                var app = allAppsModel.get(i)
                if (app.pinned && app.name.toLowerCase().includes(searchText.toLowerCase())) {
                    filteredApps.push(i)
                }
            }
        } else {
            // Ohne Suche: Erst gepinnte, dann alle anderen Apps
            for (var k = 0; k < allAppsModel.count; k++) {
                var app3 = allAppsModel.get(k)
                if (app3.pinned) {
                    filteredApps.push(k)
                }
            }
            for (var l = 0; l < allAppsModel.count; l++) {
                var app4 = allAppsModel.get(l)
                if (!app4.pinned) {
                    filteredApps.push(l)
                }
            }
        }

        // Index auf erste sichtbare App setzen und Keyboard-Navigation aktivieren
        if (filteredApps.length > 0) {
            selectedAppIndex = filteredApps[0]
            keyboardNavigation = true
        } else {
            selectedAppIndex = 0
        }

        console.log("FilteredApps updated, count:", filteredApps.length, "selectedIndex:", selectedAppIndex)
    }

    function scrollToSelected() {
        if (selectedAppIndex < 0 || selectedAppIndex >= allAppsModel.count) return

        var app = allAppsModel.get(selectedAppIndex)
        if (!app) return

        var itemHeight = 90
        var rowSpacing = 10
        var headerHeight = 30  // Approximation für Text Header + Spacing
        var columns = 6

        var targetY = 0
        var visualIndex = 0

        // Bei Suche: Alle sichtbaren Apps durchgehen
        if (searchText.length > 0) {
            for (var i = 0; i < selectedAppIndex; i++) {
                var a = allAppsModel.get(i)
                if (a && a.name.toLowerCase().includes(searchText.toLowerCase())) {
                    visualIndex++
                }
            }

            // Berechne Y-Position im Suchergebnisse-Grid
            var row = Math.floor(visualIndex / columns)
            targetY = headerHeight + row * (itemHeight + rowSpacing)
        } else {
            // Ohne Suche: Prüfe ob gepinned oder nicht
            if (app.pinned) {
                // Zähle gepinnte Apps vor diesem Index
                for (var i = 0; i < selectedAppIndex; i++) {
                    var a = allAppsModel.get(i)
                    if (a && a.pinned) visualIndex++
                }

                // Berechne Y-Position im Pinned-Grid
                var row = Math.floor(visualIndex / columns)
                targetY = headerHeight + row * (itemHeight + rowSpacing)
            } else {
                // Unpinned: Berechne Position im "Alle Apps" Grid
                // Zuerst: Höhe des gesamten Pinned-Bereichs
                var pinnedCount = 0
                for (var i = 0; i < allAppsModel.count; i++) {
                    var a = allAppsModel.get(i)
                    if (a && a.pinned) pinnedCount++
                }

                var pinnedRows = Math.ceil(pinnedCount / columns)
                var pinnedHeight = headerHeight + pinnedRows * (itemHeight + rowSpacing)

                // Dann: Position im Alle Apps Grid
                visualIndex = 0
                for (var i = 0; i < selectedAppIndex; i++) {
                    var a = allAppsModel.get(i)
                    if (a && !a.pinned) visualIndex++
                }

                var row = Math.floor(visualIndex / columns)
                targetY = pinnedHeight + headerHeight + row * (itemHeight + rowSpacing)
            }
        }

        // Scroll so dass das Element sichtbar ist
        var viewportTop = appsFlickable.contentY
        var viewportBottom = viewportTop + appsFlickable.height
        var itemTop = targetY
        var itemBottom = targetY + itemHeight

        if (itemBottom > viewportBottom) {
            // Element ist unten außerhalb - scroll nach unten
            appsFlickable.contentY = itemBottom - appsFlickable.height + rowSpacing
        } else if (itemTop < viewportTop) {
            // Element ist oben außerhalb - scroll nach oben
            appsFlickable.contentY = Math.max(0, itemTop - rowSpacing)
        }
    }

    onVisibleChanged: {
        if (visible) {
            console.log("=== START MENU OPENED ===")
            // Reset beim Öffnen
            searchText = ""
            searchInput.text = ""
            currentSection = "allApps"
            updateFilteredApps()
            // selectedAppIndex wird in updateFilteredApps() gesetzt
            appsFlickable.contentY = 0
            keyboardNavigation = true
            // Focus auf keyHandler setzen, damit Keyboard-Navigation sofort funktioniert
            Qt.callLater(function() {
                console.log("=== Setting focus to keyHandler")
                keyHandler.forceActiveFocus()
                console.log("=== keyHandler.activeFocus:", keyHandler.activeFocus)
                console.log("=== searchInput.activeFocus:", searchInput.activeFocus)
            })
        } else {
            console.log("=== START MENU CLOSED ===")
            // Reset beim Schließen
            searchText = ""
            searchInput.text = ""
            selectedAppIndex = 0
            appsFlickable.contentY = 0
        }
    }

    onSearchTextChanged: updateFilteredApps()

    Item {
        id: keyHandler
        focus: true

        onActiveFocusChanged: {
            console.log("=== keyHandler focus changed:", activeFocus)
        }

        Keys.onPressed: function(event) {
            console.log("=== keyHandler received key:", event.key, "focus:", activeFocus)

            if (event.key === Qt.Key_Escape) { startMenu.visible = false; event.accepted = true; return }
            if (startMenu.currentSection !== "allApps") return
            if (allAppsModel.count === 0) return

            // Finde alle sichtbaren Indizes
            var visibleIndices = []
            for (var i = 0; i < allAppsModel.count; i++) {
                var app = allAppsModel.get(i)
                if (startMenu.searchText.length === 0 || app.name.toLowerCase().includes(startMenu.searchText.toLowerCase())) {
                    visibleIndices.push(i)
                }
            }

            if (visibleIndices.length === 0) return

            // Finde aktuelle Position in sichtbaren Items
            var currentPos = visibleIndices.indexOf(startMenu.selectedAppIndex)
            if (currentPos === -1) currentPos = 0

            if (event.key === Qt.Key_Down) {
                startMenu.keyboardNavigation = true
                var newPos = currentPos + 6
                if (newPos < visibleIndices.length) {
                    startMenu.selectedAppIndex = visibleIndices[newPos]
                    startMenu.scrollToSelected()
                }
                event.accepted = true
            } else if (event.key === Qt.Key_Up) {
                startMenu.keyboardNavigation = true
                var newPos = currentPos - 6
                if (newPos >= 0) {
                    startMenu.selectedAppIndex = visibleIndices[newPos]
                    startMenu.scrollToSelected()
                }
                event.accepted = true
            } else if (event.key === Qt.Key_Right) {
                startMenu.keyboardNavigation = true
                var newPos = currentPos + 1
                if (newPos < visibleIndices.length) {
                    startMenu.selectedAppIndex = visibleIndices[newPos]
                    startMenu.scrollToSelected()
                }
                event.accepted = true
            } else if (event.key === Qt.Key_Left) {
                startMenu.keyboardNavigation = true
                var newPos = currentPos - 1
                if (newPos >= 0) {
                    startMenu.selectedAppIndex = visibleIndices[newPos]
                    startMenu.scrollToSelected()
                }
                event.accepted = true
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                console.log("=== ENTER in keyHandler! selectedAppIndex:", startMenu.selectedAppIndex)
                // Enter startet die APP am selectedAppIndex (der ist schon der echte Model-Index)
                var app = allAppsModel.get(startMenu.selectedAppIndex)
                if (app) {
                    console.log("=== Starting app:", app.name, "cmd:", app.cmd)
                    var safeCmd = app.cmd.replace(/\\/g, "\\\\").replace(/"/g, '\\"')
                    Qt.createQmlObject(
                        'import Quickshell.Io; Process { command: ["bash", "-c", "setsid ' +
                        safeCmd + ' >/dev/null 2>&1 &"]; running: true }',
                        startMenu
                    )
                    startMenu.visible = false
                } else {
                    console.log("=== ERROR: No app found at index:", startMenu.selectedAppIndex)
                }
                event.accepted = true
            } else if (event.key === Qt.Key_Tab) {
                searchInput.forceActiveFocus()
                event.accepted = true
            } else if (event.text.length > 0 && !event.modifiers) {
                searchInput.forceActiveFocus()
                searchInput.text = event.text
                event.accepted = true
            }
        }
    }

    ListModel { id: allAppsModel }

    Component.onCompleted: {
        loadPinnedApps()
        // Warte kurz, dann lade Desktop-Apps
        Qt.callLater(function() {
            desktopFilesProc.running = true
        })
    }

    Process {
        id: desktopFilesProc
        command: ["windoesnot-list-apps", settingsMenu.uiLanguage, "--json"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var entries
                try { entries = JSON.parse(this.text) } catch (error) { console.warn("Application list could not be read"); return }
                allAppsModel.clear()

                // Custom Apps (können gepinnt/entpinnt werden)
                var customApps = [
                    {name: Lang.get("shell.calculator", settingsMenu.uiLanguage), icon: "img/calc.svg", cmd: "gnome-calculator", pinNames: ["Taschenrechner", "Calculator"]},
                    {name: Lang.get("shell.colorPicker", settingsMenu.uiLanguage), icon: "img/colorgrab.svg", cmd: "hyprpicker -a -f hex", pinNames: ["Color Picker", "Farbauswahl"]},
                    {name: Lang.get("shell.screenshot", settingsMenu.uiLanguage), icon: "img/screenshot.svg", cmd: "hyprshot -m region", pinNames: ["Screenshot", "Bildschirmfoto"]}
                ]

                // Desktop-Apps laden
                var pinnedApps = []
                var unpinnedApps = []

                // Custom Apps verarbeiten
                for (var k = 0; k < customApps.length; k++) {
                    var customApp = customApps[k]
                    var isCustomPinned = startMenu.pinIndex(customApp.name, customApp.pinNames) >= 0

                    var customAppData = {
                        name: customApp.name,
                        cmd: customApp.cmd,
                        icon: customApp.icon,
                        pinned: isCustomPinned,
                        customIcon: true,
                        pinAliases: JSON.stringify(customApp.pinNames)
                    }

                    if (isCustomPinned) {
                        pinnedApps.push(customAppData)
                    } else {
                        unpinnedApps.push(customAppData)
                    }
                }

                // Desktop-Apps verarbeiten
                for (var i = 0; i < entries.length; i++) {
                    var entry = entries[i]
                    if (entry.name && entry.cmd) {
                        var appName = entry.name
                        var isPinned = startMenu.pinIndex(appName, entry.names) >= 0

                        var appData = {
                            name: appName,
                            cmd: entry.cmd,
                            icon: entry.icon,
                            pinned: isPinned,
                            customIcon: false
                        }

                        // Existing name-based overrides also work after a language switch.
                        var originalName = appData.name
                        if (!appReplace.hasOverride(originalName)) {
                            for (var aliasIndex = 0; aliasIndex < entry.names.length; aliasIndex++) {
                                if (appReplace.hasOverride(entry.names[aliasIndex])) { appData.name = entry.names[aliasIndex]; break }
                            }
                        }
                        appData = appReplace.applyOverride(appData)
                        appData.name = originalName
                        appData.pinAliases = JSON.stringify(entry.names)

                        if (isPinned) {
                            pinnedApps.push(appData)
                        } else {
                            unpinnedApps.push(appData)
                        }
                    }
                }

                // Preserve the saved pin order independently of translated labels.
                pinnedApps.sort(function(a, b) {
                    return startMenu.pinIndex(a.name, JSON.parse(a.pinAliases)) - startMenu.pinIndex(b.name, JSON.parse(b.pinAliases))
                })
                // Erst gepinnte, dann ungepinnte Apps hinzufügen
                for (var j = 0; j < pinnedApps.length; j++) {
                    allAppsModel.append(pinnedApps[j])
                }
                for (var m = 0; m < unpinnedApps.length; m++) {
                    allAppsModel.append(unpinnedApps[m])
                }

                console.log("Loaded", allAppsModel.count, "apps (" + pinnedApps.length + " pinned)")
                startMenu.updateFilteredApps()
            }
        }
    }

    Process {
        id: userProc
        command: ["whoami"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: startMenu.currentUser = this.text.trim()
        }
    }

    Process {
        id: avatarProc
        command: ["bash", "-c", `
            for path in ~/.face ~/.face.icon /var/lib/AccountsService/icons/$USER; do
                if [ -f "$path" ]; then echo "$path"; exit 0; fi
            done
            echo ""
        `]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                var path = this.text.trim()
                if (path.length > 0) startMenu.userAvatar = "file://" + path
            }
        }
    }

    Item {
        anchors.fill: parent
        clip: true

        Rectangle {
            anchors.fill: parent
            color: settingsMenu.darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
            border.color: settingsMenu.darkMode ? "#3a3a3f" : "#c0c0c0"
            border.width: 1
            topLeftRadius: settingsMenu.borderRadius
            topRightRadius: settingsMenu.borderRadius
            bottomLeftRadius: 0
            bottomRightRadius: 0
        }

        Column {
            anchors.fill: parent
            spacing: 0

            // Content area: Sidebar + Inhaltsbereich
            Row {
                width: parent.width
                height: parent.height - 70  // 70 für Footer
                layoutDirection: settingsMenu.startMenuSidebarPosition === "right" ? Qt.RightToLeft : Qt.LeftToRight

                // === SIDEBAR ===
                Item {
                    width: settingsMenu.startMenuSidebarPosition === "hidden" ? 0 : 215
                    height: parent.height
                    visible: settingsMenu.startMenuSidebarPosition !== "hidden"

                    Rectangle {
                        anchors.fill: parent
                        color: settingsMenu.darkMode ? Qt.rgba(0.09, 0.09, 0.09, 1) : Qt.rgba(0.88, 0.88, 0.88, 1)
                    }
                    Rectangle {
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 1
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#c8c8c8"
                    }

                    Column {
                        anchors.fill: parent
                        anchors.topMargin: 20
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 4

                        // Nav-Items
                        Repeater {
                            model: ListModel {
                                ListElement { sectionId: "allApps";      label: "Alle Apps";      icon: "img/Win11-dark/actions/symbolic/view-app-grid-symbolic.svg" }
                                ListElement { sectionId: "personalized"; label: "Personalisiert"; icon: "img/Win11-dark/actions/symbolic/ephy-starred-symbolic.svg" }
                            }
                            delegate: Rectangle {
                                id: sideNavRect
                                width: parent.width
                                height: 44
                                radius: 6
                                visible: sectionId === "allApps" ? settingsMenu.startMenuShowAllApps : settingsMenu.startMenuShowPersonalized
                                property bool isActive: startMenu.currentSection === sectionId
                                color: isActive ? (settingsMenu.darkMode ? "#2a2a2a" : "#d0d0d0")
                                               : sideNavMouse.containsMouse ? (settingsMenu.darkMode ? "#1e1e1e" : "#dedede") : "transparent"

                                Rectangle {
                                    visible: sideNavRect.isActive
                                    width: 3; height: 22; radius: 2
                                    color: settingsMenu.accentColor
                                    anchors.left: parent.left
                                    anchors.leftMargin: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Row {
                                    anchors.fill: parent
                                    anchors.leftMargin: 14
                                    spacing: 10
                                    Image {
                                        source: icon
                                        width: 18; height: 18
                                        sourceSize.width: 18; sourceSize.height: 18
                                        fillMode: Image.PreserveAspectFit
                                        anchors.verticalCenter: parent.verticalCenter
                                        smooth: true; antialiasing: true; mipmap: true
                                        layer.enabled: !settingsMenu.darkMode
                                        layer.smooth: true
                                        layer.effect: ColorOverlay { color: "#000000" }
                                    }
                                    Text {
                                        text: Lang.get("shell." + sectionId, settingsMenu.uiLanguage)
                                        font.pixelSize: 13
                                        color: settingsMenu.darkMode ? "#ccc" : "#333"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: sideNavMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: startMenu.currentSection = sectionId
                                }
                            }
                        }

                        // Trennlinie
                        Rectangle {
                            width: parent.width
                            height: 1
                            color: settingsMenu.darkMode ? "#2a2a2a" : "#c8c8c8"
                        }

                        // Ordner-Links
                        Repeater {
                            model: ListModel {
                                ListElement { label: "Desktop";   icon: "img/Win11-dark/places/symbolic/user-desktop-symbolic.svg";      xdgKey: "DESKTOP" }
                                ListElement { label: "Dokumente"; icon: "img/Win11-dark/places/symbolic/folder-documents-symbolic.svg";  xdgKey: "DOCUMENTS" }
                                ListElement { label: "Downloads"; icon: "img/Win11-dark/places/symbolic/folder-download-symbolic.svg";   xdgKey: "DOWNLOAD" }
                                ListElement { label: "Bilder";    icon: "img/Win11-dark/places/symbolic/folder-pictures-symbolic.svg";   xdgKey: "PICTURES" }
                                ListElement { label: "Musik";     icon: "img/Win11-dark/places/symbolic/folder-music-symbolic.svg";      xdgKey: "MUSIC" }
                                ListElement { label: "Videos";    icon: "img/Win11-dark/places/symbolic/folder-videos-symbolic.svg";     xdgKey: "VIDEOS" }
                            }
                            delegate: Rectangle {
                                width: parent.width
                                height: 42
                                radius: 6
                                visible: {
                                    if (xdgKey === "DESKTOP")   return settingsMenu.startMenuShowDesktop
                                    if (xdgKey === "DOCUMENTS") return settingsMenu.startMenuShowDocuments
                                    if (xdgKey === "DOWNLOAD")  return settingsMenu.startMenuShowDownloads
                                    if (xdgKey === "PICTURES")  return settingsMenu.startMenuShowPictures
                                    if (xdgKey === "MUSIC")     return settingsMenu.startMenuShowMusic
                                    if (xdgKey === "VIDEOS")    return settingsMenu.startMenuShowVideos
                                    return true
                                }
                                color: folderMouse.containsMouse ? (settingsMenu.darkMode ? "#1e1e1e" : "#dedede") : "transparent"

                                Row {
                                    anchors.fill: parent
                                    anchors.leftMargin: 14
                                    spacing: 10
                                    Image {
                                        source: icon
                                        width: 18; height: 18
                                        sourceSize.width: 18; sourceSize.height: 18
                                        fillMode: Image.PreserveAspectFit
                                        anchors.verticalCenter: parent.verticalCenter
                                        smooth: true; antialiasing: true; mipmap: true
                                        layer.enabled: !settingsMenu.darkMode
                                        layer.smooth: true
                                        layer.effect: ColorOverlay { color: "#000000" }
                                    }
                                    Text {
                                        text: Lang.get("shell.folder." + xdgKey, settingsMenu.uiLanguage)
                                        font.pixelSize: 13
                                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: folderMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var key = xdgKey
                                        Qt.createQmlObject(
                                            'import Quickshell.Io; Process { command: ["bash", "-c", "xdg-open \\"$(xdg-user-dir ' + key + ')\\" & disown"]; running: true }',
                                            startMenu
                                        )
                                        startMenu.visible = false
                                    }
                                }
                            }
                        }
                    }

                }  // Ende Sidebar

                // === RECHTER INHALTSBEREICH ===
                Item {
                    width: settingsMenu.startMenuSidebarPosition === "hidden" ? parent.width : parent.width - 215
                    height: parent.height

                    // "Alle Apps" Ansicht
                    Item {
                        anchors.fill: parent
                        visible: startMenu.currentSection === "allApps"

                        Column {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 20
                            anchors.topMargin: 20
                            anchors.bottomMargin: 0
                            spacing: 10

            Rectangle {
                width: parent.width
                height: 40
                radius: 6
                color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"

                Text {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.rightMargin: 10
                    text: {
                        var visible = 0
                        for (var i = 0; i < allAppsModel.count; i++) {
                            var app = allAppsModel.get(i)
                            if (startMenu.searchText.length === 0 || app.name.toLowerCase().includes(startMenu.searchText.toLowerCase())) {
                                visible++
                            }
                        }
                        return visible + " Apps"
                    }
                    color: settingsMenu.darkMode ? "#999" : "#666"
                    font.pixelSize: 10
                }

                Rectangle {
                    width: parent.width
                    height: 2
                    anchors.bottom: parent.bottom
                    color: settingsMenu.accentColor
                }

                Row {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Image {
                        anchors.verticalCenter: parent.verticalCenter
                        source: "img/Win11-dark/actions/symbolic/search-symbolic.svg"
                        width: 18
                        height: 18
                        sourceSize.width: 18
                        sourceSize.height: 18
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        antialiasing: true
                        mipmap: true
                        layer.enabled: !settingsMenu.darkMode
                        layer.smooth: true
                        layer.effect: ColorOverlay { color: "#000000" }
                    }

                    TextInput {
                        id: searchInput
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 40
                        font.pixelSize: 14
                        color: "#ccc"
                        text: startMenu.searchText
                        onTextChanged: startMenu.searchText = text

                        onActiveFocusChanged: {
                            console.log("=== searchInput focus changed:", activeFocus)
                        }

                        Keys.onPressed: function(event) {
                            console.log("=== searchInput received key:", event.key, "focus:", activeFocus, "text:", event.text)

                            // ENTER behandeln (muss VOR der text.length Prüfung kommen!)
                            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                console.log("=== ENTER in searchInput! selectedAppIndex:", startMenu.selectedAppIndex)
                                // Starte die App am selectedAppIndex direkt
                                if (startMenu.selectedAppIndex >= 0 && startMenu.selectedAppIndex < allAppsModel.count) {
                                    var app = allAppsModel.get(startMenu.selectedAppIndex)
                                    if (app) {
                                        console.log("=== Starting app:", app.name, "cmd:", app.cmd)
                                        var safeCmd = app.cmd.replace(/\\/g, "\\\\").replace(/"/g, '\\"')
                                        Qt.createQmlObject(
                                            'import Quickshell.Io; Process { command: ["bash", "-c", "' +
                                            safeCmd + ' & disown"]; running: true }',
                                            startMenu
                                        )
                                        startMenu.visible = false
                                    } else {
                                        console.log("=== ERROR: No app at index:", startMenu.selectedAppIndex)
                                    }
                                } else {
                                    console.log("=== ERROR: Invalid selectedAppIndex:", startMenu.selectedAppIndex)
                                }
                                event.accepted = true
                                return
                            }

                            // Escape behandeln
                            if (event.key === Qt.Key_Escape) {
                                startMenu.visible = false
                                event.accepted = true
                                return
                            }

                            // Tab behandeln
                            if (event.key === Qt.Key_Tab) {
                                keyHandler.forceActiveFocus()
                                event.accepted = true
                                return
                            }

                            // Pfeiltasten behandeln - Navigation SOFORT ausführen
                            if (event.key === Qt.Key_Down || event.key === Qt.Key_Up ||
                                event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
                                console.log("=== Arrow key pressed in searchInput, executing navigation immediately")
                                startMenu.keyboardNavigation = true

                                // Finde alle sichtbaren Indizes
                                var visibleIndices = []
                                for (var i = 0; i < allAppsModel.count; i++) {
                                    var app = allAppsModel.get(i)
                                    if (startMenu.searchText.length === 0 || app.name.toLowerCase().includes(startMenu.searchText.toLowerCase())) {
                                        visibleIndices.push(i)
                                    }
                                }

                                if (visibleIndices.length > 0) {
                                    // Finde aktuelle Position
                                    var currentPos = visibleIndices.indexOf(startMenu.selectedAppIndex)
                                    if (currentPos === -1) currentPos = 0

                                    // Navigation ausführen
                                    var newPos = currentPos
                                    if (event.key === Qt.Key_Down) {
                                        newPos = currentPos + 6
                                    } else if (event.key === Qt.Key_Up) {
                                        newPos = currentPos - 6
                                    } else if (event.key === Qt.Key_Right) {
                                        newPos = currentPos + 1
                                    } else if (event.key === Qt.Key_Left) {
                                        newPos = currentPos - 1
                                    }

                                    // Prüfe ob neue Position gültig ist
                                    if (newPos >= 0 && newPos < visibleIndices.length) {
                                        startMenu.selectedAppIndex = visibleIndices[newPos]
                                    }
                                }

                                // Jetzt Fokus wechseln für weitere Navigation
                                keyHandler.forceActiveFocus()
                                event.accepted = true
                                return
                            }

                            // Normale Buchstaben/Zahlen - bleiben im Suchfeld
                            // (wird automatisch vom TextInput behandelt)
                        }

                        Text {
                            visible: parent.text.length === 0
                            text: Lang.get("shell.searchPlaceholder", settingsMenu.uiLanguage)
                            font.pixelSize: 14
                            color: settingsMenu.darkMode ? "#999" : "#666"
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: parent.height - 50  // Dynamisch: alles außer Suchfeld
                color: "transparent"
                clip: true

                Flickable {
                    id: appsFlickable
                    anchors.fill: parent
                    contentHeight: appsColumn.height
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: appsColumn
                        width: parent.width
                        spacing: 15
                        bottomPadding: 0  // Kein Padding unten

                        Text {
                            text: {
                                if (startMenu.searchText.length > 0) return Lang.get("shell.searchResults", settingsMenu.uiLanguage)
                                return Lang.get("shell.pinned", settingsMenu.uiLanguage)
                            }
                            font.pixelSize: 12
                            font.bold: true
                            color: settingsMenu.darkMode ? "#ccc" : "#333"
                            visible: {
                                // Zeige Header wenn es sichtbare pinned Apps gibt ODER bei Suche
                                if (startMenu.searchText.length > 0) return true
                                for (var i = 0; i < allAppsModel.count; i++) {
                                    var app = allAppsModel.get(i)
                                    if (app.pinned) return true
                                }
                                return false
                            }
                        }

                        Item {
                            width: parent.width
                            height: startMenu.searchText.length === 0 ? pinnedGridLayout.height : 0
                            visible: startMenu.searchText.length === 0

                            property int draggedIndex: -1
                            property int dropTargetIndex: -1

                            Grid {
                                id: pinnedGridLayout
                                width: parent.width
                                columns: 6
                                rowSpacing: 10
                                columnSpacing: 10

                                Repeater {
                                    model: allAppsModel

                                    delegate: Item {
                                        width: 80
                                        height: 90
                                        visible: pinned

                                        property int visualIndex: {
                                            // Berechne den visuellen Index nur für gepinnte Items
                                            var count = 0
                                            for (var i = 0; i < index; i++) {
                                                if (allAppsModel.get(i).pinned) count++
                                            }
                                            return count
                                        }

                                        property var gridParent: pinnedGridLayout.parent
                                        property bool isBeingDragged: gridParent.draggedIndex === visualIndex
                                        property bool isDropTarget: gridParent.dropTargetIndex === visualIndex && !isBeingDragged

                                    Rectangle {
                                        id: appItem
                                        anchors.fill: parent
                                        radius: 8

                                        property bool hovered: false

                                        color: {
                                            if (isDropTarget) return settingsMenu.darkMode ? "#3a3a3a" : "#e0e0e0"
                                            // Zeige Highlight wenn gehovered ODER wenn selektiert (egal ob Keyboard oder Maus)
                                            if (hovered || index === startMenu.selectedAppIndex) return settingsMenu.darkMode ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.05)
                                            return "transparent"
                                        }

                                        Behavior on color { ColorAnimation { duration: 150 } }

                                        opacity: isBeingDragged ? 0.3 : 1.0
                                        scale: {
                                            if (isBeingDragged) return 0.9
                                            if (dragArea.draggedToTaskbar) return 0.8
                                            return 1.0
                                        }

                                        Behavior on opacity { NumberAnimation { duration: 100 } }
                                        Behavior on scale { NumberAnimation { duration: 100 } }

                                        // Drag support for taskbar
                                        Drag.active: dragArea.drag.active
                                        Drag.dragType: Drag.Automatic
                                        Drag.supportedActions: Qt.CopyAction
                                        Drag.mimeData: {
                                            "text/plain": name + "|" + cmd + "|" + icon + "|" + (customIcon ? "true" : "false")
                                        }

                                        // Drop indicator
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: 8
                                            color: "transparent"
                                            border.color: settingsMenu.accentColor
                                            border.width: 2
                                            visible: isDropTarget
                                        }

                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 8

                                            Rectangle {
                                                width: 48
                                                height: 48
                                                radius: 10
                                                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                                                anchors.horizontalCenter: parent.horizontalCenter

                                                AppIcon {
                                                    anchors.centerIn: parent
                                                    iconName: icon
                                                    isCustomIcon: customIcon
                                                    width: 32
                                                    height: 32
                                                }
                                            }

                                            Text {
                                                text: name
                                                font.pixelSize: 11
                                                color: settingsMenu.darkMode ? "#ccc" : "#333"
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                elide: Text.ElideRight
                                                width: 70
                                                horizontalAlignment: Text.AlignHCenter
                                            }
                                        }

                                        MouseArea {
                                            id: dragArea
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                                            preventStealing: true

                                            property bool dragActive: false
                                            property point dragStartPos
                                            property int dragThreshold: 15
                                            property var grid: pinnedGridLayout.parent
                                            property int myVisualIndex: visualIndex
                                            property string myName: name
                                            property string myCmd: cmd
                                            property string myIcon: icon
                                            property bool myCustomIcon: customIcon
                                            property bool draggedToTaskbar: false
                                            property point lastMousePos

                                            onEntered: {
                                                // Setze ERST selectedIndex, DANN hovered - so gibt's keinen Flash
                                                startMenu.selectedAppIndex = index
                                                appItem.hovered = true
                                                startMenu.keyboardNavigation = false
                                            }
                                            onExited: {
                                                appItem.hovered = false
                                            }

                                            onPressed: function(mouse) {
                                                if (mouse.button === Qt.LeftButton) {
                                                    dragStartPos = Qt.point(mouse.x, mouse.y)
                                                    lastMousePos = Qt.point(mouse.x, mouse.y)
                                                    dragActive = false
                                                    draggedToTaskbar = false
                                                    myVisualIndex = visualIndex
                                                    myName = name
                                                    myCmd = cmd
                                                    myIcon = icon
                                                    myCustomIcon = customIcon
                                                    mouse.accepted = true
                                                }
                                            }

                                            onPositionChanged: function(mouse) {
                                                if (mouse.buttons & Qt.LeftButton) {
                                                    lastMousePos = Qt.point(mouse.x, mouse.y)
                                                    var dx = mouse.x - dragStartPos.x
                                                    var dy = mouse.y - dragStartPos.y
                                                    var distance = Math.sqrt(dx * dx + dy * dy)

                                                    if (!dragActive && distance > dragThreshold) {
                                                        dragActive = true
                                                        if (pinned) {
                                                            grid.draggedIndex = myVisualIndex
                                                        }
                                                    }

                                                    if (dragActive) {
                                                        // Check if dragging towards taskbar (nach unten)
                                                        if (dy > 100) {  // Mehr als 100px nach unten
                                                            draggedToTaskbar = true
                                                            grid.dropTargetIndex = -1  // Kein Reorder-Target
                                                        } else {
                                                            draggedToTaskbar = false
                                                            if (pinned) {
                                                                // Reordering innerhalb Grid
                                                                var globalPos = mapToItem(pinnedGridLayout, mouse.x, mouse.y)
                                                                var col = Math.max(0, Math.min(5, Math.floor(globalPos.x / 90)))
                                                                var row = Math.max(0, Math.floor(globalPos.y / 100))
                                                                var targetIdx = row * 6 + col

                                                                var pinnedCount = 0
                                                                for (var i = 0; i < allAppsModel.count; i++) {
                                                                    if (allAppsModel.get(i).pinned) pinnedCount++
                                                                }

                                                                if (targetIdx >= pinnedCount) {
                                                                    targetIdx = pinnedCount - 1
                                                                }
                                                                if (targetIdx < 0) {
                                                                    targetIdx = 0
                                                                }

                                                                if (targetIdx !== grid.dropTargetIndex && targetIdx !== myVisualIndex) {
                                                                    grid.dropTargetIndex = targetIdx
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                            onReleased: function(mouse) {
                                                var wasActive = dragActive
                                                var droppedOnTaskbar = draggedToTaskbar

                                                if (wasActive && droppedOnTaskbar) {
                                                    // Dropped on taskbar
                                                    console.log("Dropped on taskbar:", myName)
                                                    panelWindow.addToTaskbar(myName, myCmd, myIcon, myCustomIcon)
                                                } else if (wasActive && pinned && grid.dropTargetIndex !== -1 && grid.dropTargetIndex !== myVisualIndex) {
                                                    // Reordering
                                                    console.log("Reordering from", myVisualIndex, "to", grid.dropTargetIndex)
                                                    startMenu.reorderPinnedApps(myVisualIndex, grid.dropTargetIndex)
                                                } else if (!wasActive) {
                                                    // Normaler Klick
                                                    if (mouse.button === Qt.RightButton) {
                                                        startMenu.togglePin(myName)
                                                    } else if (mouse.button === Qt.LeftButton) {
                                                        var safeCmd = myCmd.replace(/\\/g, "\\\\").replace(/"/g, '\\"')
                                                        Qt.createQmlObject(
                                                            'import Quickshell.Io; Process { command: ["bash", "-c", "setsid ' +
                                                            safeCmd + ' >/dev/null 2>&1 &"]; running: true }',
                                                            startMenu
                                                        )
                                                        startMenu.visible = false
                                                    }
                                                }
                                                dragActive = false
                                                draggedToTaskbar = false
                                                grid.draggedIndex = -1
                                                grid.dropTargetIndex = -1
                                            }

                                            onCanceled: {
                                                dragActive = false
                                                draggedToTaskbar = false
                                                grid.draggedIndex = -1
                                                grid.dropTargetIndex = -1
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        }

                        Text {
                            text: startMenu.searchText.length > 0 ? Lang.get("shell.pinned", settingsMenu.uiLanguage) : Lang.get("shell.allApps", settingsMenu.uiLanguage)
                            font.pixelSize: 12
                            font.bold: true
                            color: settingsMenu.darkMode ? "#ccc" : "#333"
                            visible: {
                                // Bei Suche: Zeige "Angeheftet" nur wenn es gefilterte pinned Apps gibt
                                if (startMenu.searchText.length > 0) {
                                    for (var i = 0; i < allAppsModel.count; i++) {
                                        var app = allAppsModel.get(i)
                                        if (app.pinned && app.name.toLowerCase().includes(startMenu.searchText.toLowerCase())) {
                                            return true
                                        }
                                    }
                                    return false
                                }
                                // Ohne Suche: Zeige "Alle Apps"
                                return true
                            }
                        }

                        Grid {
                            width: parent.width
                            columns: 6
                            rowSpacing: 10
                            columnSpacing: 10

                            Repeater {
                                model: allAppsModel

                                delegate: Item {
                                    width: 80
                                    height: 90

                                    // Bei Suche: Alle matchenden, ohne Suche: Nur unpinned
                                    visible: {
                                        if (startMenu.searchText.length > 0) {
                                            return name.toLowerCase().includes(startMenu.searchText.toLowerCase())
                                        }
                                        return !pinned
                                    }

                                    Rectangle {
                                        id: allAppItem
                                        anchors.fill: parent
                                        radius: 8

                                        property bool hovered: false

                                        color: {
                                            // Zeige Highlight wenn gehovered ODER wenn selektiert (egal ob Keyboard oder Maus)
                                            if (hovered || index === startMenu.selectedAppIndex) return settingsMenu.darkMode ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.05)
                                            return "transparent"
                                        }

                                        scale: allAppDragArea.draggedToTaskbar ? 0.8 : 1.0

                                        Behavior on scale { NumberAnimation { duration: 100 } }
                                        Behavior on color { ColorAnimation { duration: 150 } }

                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 8

                                            Rectangle {
                                                width: 48
                                                height: 48
                                                radius: 10
                                                color: allAppItem.hovered ? (settingsMenu.darkMode ? "#4a4a4a" : "#d0d0d0") : (settingsMenu.darkMode ? "#3a3a3a" : "#e0e0e0")
                                                anchors.horizontalCenter: parent.horizontalCenter

                                                Behavior on color { ColorAnimation { duration: 150 } }

                                                AppIcon {
                                                    anchors.centerIn: parent
                                                    iconName: icon
                                                    isCustomIcon: customIcon
                                                    width: 32
                                                    height: 32
                                                }
                                            }

                                            Text {
                                                text: name
                                                font.pixelSize: 11
                                                color: settingsMenu.darkMode ? "#ccc" : "#333"
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                elide: Text.ElideRight
                                                width: 70
                                                horizontalAlignment: Text.AlignHCenter
                                            }
                                        }

                                        MouseArea {
                                            id: allAppDragArea
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            acceptedButtons: Qt.LeftButton | Qt.RightButton

                                            property bool dragActive: false
                                            property point dragStartPos
                                            property int dragThreshold: 15
                                            property string myName: name
                                            property string myCmd: cmd
                                            property string myIcon: icon
                                            property bool myCustomIcon: customIcon
                                            property bool draggedToTaskbar: false

                                            onEntered: {
                                                // Setze ERST selectedIndex, DANN hovered - so gibt's keinen Flash
                                                startMenu.selectedAppIndex = index
                                                allAppItem.hovered = true
                                                startMenu.keyboardNavigation = false
                                            }
                                            onExited: {
                                                allAppItem.hovered = false
                                            }

                                            onPressed: function(mouse) {
                                                if (mouse.button === Qt.LeftButton) {
                                                    dragStartPos = Qt.point(mouse.x, mouse.y)
                                                    dragActive = false
                                                    draggedToTaskbar = false
                                                    myName = name
                                                    myCmd = cmd
                                                    myIcon = icon
                                                    myCustomIcon = customIcon
                                                    mouse.accepted = true
                                                }
                                            }

                                            onPositionChanged: function(mouse) {
                                                if (mouse.buttons & Qt.LeftButton) {
                                                    var dx = mouse.x - dragStartPos.x
                                                    var dy = mouse.y - dragStartPos.y
                                                    var distance = Math.sqrt(dx * dx + dy * dy)

                                                    if (!dragActive && distance > dragThreshold) {
                                                        dragActive = true
                                                    }

                                                    if (dragActive) {
                                                        // Check if dragging down (towards taskbar)
                                                        // Wenn Y stark positiv ist, wird nach unten gedraggt
                                                        if (dy > 100) {  // Mehr als 100px nach unten
                                                            draggedToTaskbar = true
                                                        } else {
                                                            draggedToTaskbar = false
                                                        }
                                                    }
                                                }
                                            }

                                            onReleased: function(mouse) {
                                                var wasActive = dragActive
                                                var droppedOnTaskbar = draggedToTaskbar

                                                if (wasActive && droppedOnTaskbar) {
                                                    // Dropped on taskbar
                                                    console.log("Dropped on taskbar:", myName)
                                                    panelWindow.addToTaskbar(myName, myCmd, myIcon, myCustomIcon)
                                                } else if (!wasActive) {
                                                    // Normaler Klick
                                                    if (mouse.button === Qt.RightButton) {
                                                        startMenu.togglePin(myName)
                                                    } else {
                                                        var safeCmd = myCmd.replace(/\\/g, "\\\\").replace(/"/g, '\\"')
                                                        Qt.createQmlObject(
                                                            'import Quickshell.Io; Process { command: ["bash", "-c", "setsid ' +
                                                            safeCmd + ' >/dev/null 2>&1 &"]; running: true }',
                                                            startMenu
                                                        )
                                                        startMenu.visible = false
                                                    }
                                                }
                                                dragActive = false
                                                draggedToTaskbar = false
                                            }

                                            onCanceled: {
                                                dragActive = false
                                                draggedToTaskbar = false
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Custom Scrollbar Indicator - nur wenn nötig
                Rectangle {
                    id: appsScrollIndicator
                    anchors.right: parent.right
                    anchors.rightMargin: 0
                    y: {
                        if (appsScrollIndicatorArea.drag.active) {
                            return appsScrollIndicatorArea.drag.target.y
                        } else {
                            var scrollRange = appsFlickable.height - height - 4
                            var maxScroll = 1 - appsFlickable.visibleArea.heightRatio
                            if (maxScroll <= 0) return 2
                            var normalizedPosition = appsFlickable.visibleArea.yPosition / maxScroll
                            return normalizedPosition * scrollRange + 2
                        }
                    }
                    width: 6
                    height: Math.max(30, appsFlickable.visibleArea.heightRatio * (appsFlickable.height - 4))
                    radius: 3
                    color: settingsMenu.accentColor
                    opacity: appsFlickable.moving || appsScrollIndicatorArea.containsMouse || appsScrollIndicatorArea.drag.active ? 0.8 : 0.4
                    visible: appsFlickable.contentHeight > appsFlickable.height

                    Behavior on opacity {
                        NumberAnimation { duration: 150 }
                    }

                    MouseArea {
                        id: appsScrollIndicatorArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor

                        drag.target: appsScrollIndicator
                        drag.axis: Drag.YAxis
                        drag.minimumY: 2
                        drag.maximumY: appsFlickable.height - appsScrollIndicator.height - 2

                        onPositionChanged: {
                            if (drag.active) {
                                var availableHeight = appsFlickable.height - appsScrollIndicator.height - 4
                                var scrollRatio = (appsScrollIndicator.y - 2) / availableHeight
                                var maxContentY = appsFlickable.contentHeight - appsFlickable.height
                                appsFlickable.contentY = scrollRatio * maxContentY
                            }
                        }
                    }
                }
            }
                        }  // Ende Column (allApps)
                    }  // Ende Item (allApps Ansicht)

                    // "Personalisiert" Ansicht
                    Item {
                        anchors.fill: parent
                        visible: startMenu.currentSection === "personalized"

                        Flickable {
                            anchors.fill: parent
                            contentHeight: personalizedColumn.height
                            boundsBehavior: Flickable.StopAtBounds
                            clip: true

                            Column {
                                id: personalizedColumn
                                width: parent.width
                                topPadding: 20
                                spacing: 15

                                Text {
                                    text: Lang.get("shell.pinned", settingsMenu.uiLanguage)
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: settingsMenu.darkMode ? "#ccc" : "#333"
                                    leftPadding: 20
                                    visible: {
                                        for (var i = 0; i < allAppsModel.count; i++) {
                                            if (allAppsModel.get(i).pinned) return true
                                        }
                                        return false
                                    }
                                }

                                Grid {
                                    x: 20
                                    columns: 6
                                    rowSpacing: 10
                                    columnSpacing: 10
                                    visible: {
                                        for (var i = 0; i < allAppsModel.count; i++) {
                                            if (allAppsModel.get(i).pinned) return true
                                        }
                                        return false
                                    }

                                    Repeater {
                                        model: allAppsModel
                                        delegate: Item {
                                            width: 80
                                            height: 90
                                            visible: pinned

                                            Rectangle {
                                                id: persAppItem
                                                anchors.fill: parent
                                                radius: 8
                                                property bool hovered: false
                                                color: hovered ? (settingsMenu.darkMode ? Qt.rgba(1,1,1,0.07) : Qt.rgba(0,0,0,0.07)) : "transparent"
                                                Behavior on color { ColorAnimation { duration: 150 } }

                                                Column {
                                                    anchors.centerIn: parent
                                                    spacing: 8
                                                    Rectangle {
                                                        width: 48; height: 48; radius: 10
                                                        color: persAppItem.hovered ? (settingsMenu.darkMode ? "#4a4a4a" : "#d0d0d0") : (settingsMenu.darkMode ? "#3a3a3a" : "#e0e0e0")
                                                        anchors.horizontalCenter: parent.horizontalCenter
                                                        Behavior on color { ColorAnimation { duration: 150 } }
                                                        AppIcon {
                                                            anchors.centerIn: parent
                                                            iconName: icon
                                                            isCustomIcon: customIcon
                                                            width: 32; height: 32
                                                        }
                                                    }
                                                    Text {
                                                        text: name
                                                        font.pixelSize: 11
                                                        color: settingsMenu.darkMode ? "#ccc" : "#333"
                                                        anchors.horizontalCenter: parent.horizontalCenter
                                                        elide: Text.ElideRight
                                                        width: 70
                                                        horizontalAlignment: Text.AlignHCenter
                                                    }
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                                    onEntered: persAppItem.hovered = true
                                                    onExited: persAppItem.hovered = false
                                                    onClicked: function(mouse) {
                                                        if (mouse.button === Qt.RightButton) {
                                                            startMenu.togglePin(name)
                                                        } else {
                                                            var safeCmd = cmd.replace(/\\/g, "\\\\").replace(/"/g, '\\"')
                                                            Qt.createQmlObject(
                                                                'import Quickshell.Io; Process { command: ["bash", "-c", "setsid ' + safeCmd + ' >/dev/null 2>&1 &"]; running: true }',
                                                                startMenu
                                                            )
                                                            startMenu.visible = false
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    x: 20
                                    width: parent.width - 40
                                    height: 1
                                    color: settingsMenu.darkMode ? "#2a2a2a" : "#d0d0d0"
                                }

                                Text {
                                    text: Lang.get("shell.frequent", settingsMenu.uiLanguage)
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: settingsMenu.darkMode ? "#ccc" : "#333"
                                    leftPadding: 20
                                }

                                Text {
                                    text: Lang.get("shell.comingLater", settingsMenu.uiLanguage)
                                    font.pixelSize: 12
                                    color: settingsMenu.darkMode ? "#555" : "#aaa"
                                    font.italic: true
                                    leftPadding: 20
                                    bottomPadding: 20
                                }
                            }
                        }
                    }  // Ende Item (personalized)

                }  // Ende Item (rechter Bereich)
            }  // Ende Row (Content area)

            // Footer - volle Breite mit Border oben
            Rectangle {
                width: parent.width
                height: 70
                color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"

                // Border oben
                Rectangle {
                    width: parent.width
                    height: 1
                    anchors.top: parent.top
                    color: settingsMenu.darkMode ? "#3a3a3f" : "#d0d0d0"
                }

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    anchors.topMargin: 15
                    anchors.bottomMargin: 15
                    spacing: 10

                    Row {
                        id: userRow
                        spacing: 10
                        anchors.verticalCenter: parent.verticalCenter

                        Rectangle {
                            width: 40
                            height: 40
                            radius: 20
                            color: "#0078d4"
                            anchors.verticalCenter: parent.verticalCenter

                            layer.enabled: true
                            layer.samples: 8

                            Image {
                                id: avatarImage
                                anchors.fill: parent
                                source: startMenu.userAvatar
                                fillMode: Image.PreserveAspectCrop
                                smooth: true
                                visible: status === Image.Ready
                            }

                            Text {
                                visible: avatarImage.status !== Image.Ready
                                anchors.centerIn: parent
                                text: startMenu.currentUser ? startMenu.currentUser.substring(0, 1).toUpperCase() : "U"
                                font.pixelSize: 16
                                font.bold: true
                                color: settingsMenu.darkMode ? "white" : "#1a1a1a"
                            }
                        }

                        Text {
                            text: startMenu.currentUser || "User"
                            font.pixelSize: 13
                            color: settingsMenu.darkMode ? "#ccc" : "#333"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    Item {
                        width: parent.width - userRow.width - powerRow.width - 30
                        height: 1
                    }

                    Row {
                        id: powerRow
                        spacing: 8
                        anchors.verticalCenter: parent.verticalCenter

                        Rectangle {
                            width: 40; height: 40; radius: 6
                            color: lockMouseArea.containsMouse ? (settingsMenu.darkMode ? "#3a3a3a" : "#e0e0e0") : "transparent"

                            Image {
                                anchors.centerIn: parent
                                source: "img/Win11-dark/status/symbolic/changes-prevent-symbolic.svg"
                                width: 20
                                height: 20
                                sourceSize.width: 20
                                sourceSize.height: 20
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                antialiasing: true
                                mipmap: true
                                layer.enabled: !settingsMenu.darkMode
                                layer.smooth: true
                                layer.effect: ColorOverlay { color: "#000000" }
                            }

                            Process {
                                id: lockProc
                                command: ["bash", "-c", "loginctl terminate-user \"\""]
                                running: false
                            }

                            MouseArea {
                                id: lockMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: {
                                    lockProc.running = true
                                    startMenu.visible = false
                                }
                            }
                        }

                        Rectangle {
                            width: 40; height: 40; radius: 6
                            color: rebootMouseArea.containsMouse ? (settingsMenu.darkMode ? "#3a3a3a" : "#e0e0e0") : "transparent"

                            Image {
                                anchors.centerIn: parent
                                source: "img/Win11-dark/status/symbolic/rotation-allowed-symbolic.svg"
                                width: 20
                                height: 20
                                sourceSize.width: 20
                                sourceSize.height: 20
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                antialiasing: true
                                mipmap: true
                                layer.enabled: !settingsMenu.darkMode
                                layer.smooth: true
                                layer.effect: ColorOverlay { color: "#000000" }
                            }

                            Process {
                                id: rebootProc
                                command: ["bash", "-c", "systemctl reboot"]
                                running: false
                            }

                            MouseArea {
                                id: rebootMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: rebootProc.running = true
                            }
                        }

                        Rectangle {
                            width: 40; height: 40; radius: 6
                            color: powerMouseArea.containsMouse ? (settingsMenu.darkMode ? "#3a3a3a" : "#e0e0e0") : "transparent"

                            Image {
                                anchors.centerIn: parent
                                source: "img/Win11-dark/status/symbolic/system-shutdown-symbolic.svg"
                                width: 20
                                height: 20
                                sourceSize.width: 20
                                sourceSize.height: 20
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                antialiasing: true
                                mipmap: true
                                layer.enabled: !settingsMenu.darkMode
                                layer.smooth: true
                                layer.effect: ColorOverlay { color: "#000000" }
                            }

                            Process {
                                id: poweroffProc
                                command: ["bash", "-c", "systemctl poweroff"]
                                running: false
                            }

                            MouseArea {
                                id: powerMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: poweroffProc.running = true
                            }
                        }
                    }
                }
            }
        }  // Ende Column (Main)
    }  // Ende Item (Clip Container)
}


SystemAuthentication {
    id: systemAuthentication
    settingsMenu: settingsMenu
}

Settings {
    id: settingsMenu
    authentication: systemAuthentication
    workspaceContainer: workspaceContainer
    panelWindow: panelWindow
    appReplace: appReplaceLoader.item
    appReplaceLoader: appReplaceLoader
}

// Color Palette Picker Dialog
FloatingWindow {
    id: colorPaletteDialog
    visible: settingsMenu.colorPaletteVisible
    implicitWidth: 400
    implicitHeight: 480
    color: "transparent"
    title: "quickshell-colorpalette"

    HyprlandFocusGrab {
        id: colorPaletteFocusGrab
        windows: [colorPaletteDialog]
        active: colorPaletteDialog.visible
        onCleared: settingsMenu.colorPaletteVisible = false
    }

    Item {
        anchors.fill: parent
        clip: true

        Rectangle {
            anchors.fill: parent
            radius: settingsMenu.borderRadius
            color: settingsMenu.darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.95) : Qt.rgba(0.95, 0.95, 0.95, 0.95)
            border.color: settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0"
            border.width: 1
        }

        Column {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 0

            // Header
            Text {
                text: Lang.get("shell.colorPicker", settingsMenu.uiLanguage)
                font.pixelSize: 20
                font.bold: true
                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
            }

            Item { width: 1; height: 20 }  // Spacer

            // Scrollable Color Palette
            Flickable {
                width: parent.width
                height: parent.height - 100
                contentHeight: colorGrid.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                // Comprehensive Color Palette (organized by hue)
                Grid {
                    id: colorGrid
                    columns: 8
                    spacing: 10
                    width: parent.width

                Repeater {
                    model: [
                        // Reds
                        "#ff0000", "#ff1a1a", "#ff3333", "#ff4d4d", "#ff6666", "#ff8080", "#ff9999", "#ffb3b3",
                        "#cc0000", "#e60000", "#ff0033", "#ff0066", "#ff0099", "#ff00cc", "#ff00ff", "#cc00ff",
                        // Pinks & Magentas
                        "#ff69b4", "#ff1493", "#c71585", "#db7093", "#ff6eb4", "#ff85d0", "#ffa0e0", "#ffb3eb",
                        // Purples
                        "#9900ff", "#9933ff", "#9966ff", "#9999ff", "#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe",
                        // Blues
                        "#0000ff", "#1a1aff", "#3333ff", "#4d4dff", "#0078d4", "#0084ff", "#0099ff", "#00b3ff",
                        "#0066cc", "#0080ff", "#0099cc", "#00aaff", "#00bfff", "#00d4ff", "#33d4ff", "#66d4ff",
                        // Cyans & Teals
                        "#00ffff", "#00e6e6", "#00cccc", "#00b3b3", "#009999", "#008080", "#006666", "#004d4d",
                        "#06b6d4", "#22d3ee", "#67e8f9", "#a5f3fc", "#14b8a6", "#2dd4bf", "#5eead4", "#99f6e4",
                        // Greens
                        "#00ff00", "#1aff1a", "#33ff33", "#4dff4d", "#10b981", "#34d399", "#6ee7b7", "#a7f3d0",
                        "#00cc00", "#00e600", "#00ff33", "#00ff66", "#00ff99", "#00ffcc", "#22c55e", "#4ade80",
                        // Yellows
                        "#ffff00", "#ffff1a", "#ffff33", "#ffff4d", "#eab308", "#fbbf24", "#fcd34d", "#fde68a",
                        "#f59e0b", "#fbbf24", "#fcd34d", "#fde047", "#facc15", "#fde047", "#fef08a", "#fef9c3",
                        // Oranges
                        "#ff8800", "#ff9500", "#ffa500", "#ffb300", "#fb923c", "#fdba74", "#fed7aa", "#ffedd5",
                        "#FE6F2D", "#ff6600", "#ff7700", "#ff8800", "#ff9900", "#ffaa00", "#ffbb00", "#ffcc00",
                        // Browns
                        "#8b4513", "#a0522d", "#b8860b", "#cd853f", "#d2691e", "#daa520", "#bc8f8f", "#c19a6b",
                        // Grays
                        "#1a1a1a", "#2a2a2a", "#3a3a3a", "#4a4a4a", "#595959", "#6a6a6a", "#808080", "#999999",
                        "#b3b3b3", "#cccccc", "#d9d9d9", "#e6e6e6", "#f0f0f0", "#f5f5f5", "#fafafa", "#ffffff"
                    ]

                    delegate: Rectangle {
                        width: 35
                        height: 35
                        radius: 4
                        color: modelData
                        border.width: {
                            if (settingsMenu.colorPaletteTarget === "accent") {
                                return settingsMenu.accentColor === modelData ? 3 : 1
                            } else {
                                return settingsMenu.inactiveBorderColor === modelData ? 3 : 1
                            }
                        }
                        border.color: {
                            if (settingsMenu.colorPaletteTarget === "accent") {
                                return settingsMenu.accentColor === modelData ? "#fff" : "#555"
                            } else {
                                return settingsMenu.inactiveBorderColor === modelData ? "#fff" : "#555"
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            hoverEnabled: true
                            onClicked: {
                                if (settingsMenu.colorPaletteTarget === "accent") {
                                    settingsMenu.accentColor = modelData
                                } else {
                                    settingsMenu.inactiveBorderColor = modelData
                                }
                                settingsMenu.colorPaletteVisible = false
                            }

                            property bool hovered: false
                            onEntered: hovered = true
                            onExited: hovered = false
                        }

                        // Hover effect
                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: "transparent"
                            border.width: 2
                            border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            opacity: parent.children[0].hovered ? 0.5 : 0
                            Behavior on opacity { NumberAnimation { duration: 100 } }
                        }
                    }
                }
                }  // Ende Grid
            }  // Ende Flickable

            Item { width: 1; height: 20 }  // Spacer

            // Close button
            Rectangle {
                width: parent.width
                height: 40
                radius: 6
                color: closeMouseArea.containsMouse ? (settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0") : (settingsMenu.darkMode ? "#2a2a2a" : "#e0e0e0")
                border.width: 1
                border.color: settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0"

                Behavior on color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.centerIn: parent
                    text: Lang.get("shell.close", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    font.pixelSize: 14
                }

                MouseArea {
                    id: closeMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: settingsMenu.colorPaletteVisible = false
                }
            }
        }
    }  // Ende Item (Clip Container)
}

FloatingWindow {
    id: calendarWindow
    visible: false
    implicitWidth: 320
    implicitHeight: 360
    color: "transparent"
    title: "quickshell-calendar"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    HyprlandFocusGrab {
        id: calendarFocusGrab
        windows: [calendarWindow]
        active: calendarWindow.visible
        onCleared: calendarWindow.visible = false
    }



    onVisibleChanged: {
        if (visible) {
        }
    }

    Loader {
        anchors.fill: parent
        source: "calendar/SimpleCalendarWidget.qml"

        onLoaded: {
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.uiLanguage = Qt.binding(function() { return settingsMenu.uiLanguage })
        }
    }
}

FloatingWindow {
    id: audioWindow
    visible: false
    implicitWidth: 320
    implicitHeight: 400
    color: "transparent"
    title: "quickshell-audio"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    HyprlandFocusGrab {
        id: audioFocusGrab
        windows: [audioWindow]
        active: audioWindow.visible
        onCleared: audioWindow.visible = false
    }

    onVisibleChanged: {
        if (visible) {
        }
    }

    Loader {
        id: audioLoader
        anchors.fill: parent
        source: "widgets/AudioPanel.qml"
        asynchronous: false  // Load immediately, not async

        onLoaded: {
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.windowVisible = Qt.binding(function() { return audioWindow.visible })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.uiLanguage = Qt.binding(function() { return settingsMenu.uiLanguage })

            // Force initial data load
            if (item.updateAudioState) {
                item.updateAudioState()
            }
        }
    }

    Component.onCompleted: {
        // Pre-load audio data at startup (before warmup opens the window)
        if (audioLoader.item && audioLoader.item.updateAudioState) {
            audioLoader.item.updateAudioState()
        }
    }

    // Startup timer to ensure audio data is loaded after shell initialization
    Timer {
        id: audioStartupTimer
        interval: 500
        running: true
        repeat: false
        onTriggered: {
            if (audioLoader.item && audioLoader.item.updateAudioState) {
                audioLoader.item.updateAudioState()
            }
        }
    }
}

FloatingWindow {
    id: bluetoothWindow
    visible: false
    implicitWidth: 320
    implicitHeight: 500
    color: "transparent"
    title: "quickshell-bluetooth"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    HyprlandFocusGrab {
        id: bluetoothFocusGrab
        windows: [bluetoothWindow]
        active: bluetoothWindow.visible
        onCleared: bluetoothWindow.visible = false
    }

    onVisibleChanged: {
        if (visible) {
        }
    }

    Loader {
        anchors.fill: parent
        source: "widgets/BluetoothPanel.qml"

        onLoaded: {
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.windowVisible = Qt.binding(function() { return bluetoothWindow.visible })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.uiLanguage = Qt.binding(function() { return settingsMenu.uiLanguage })
        }
    }
}

FloatingWindow {
    id: networkWindow
    visible: false
    implicitWidth: 320
    implicitHeight: 500
    color: "transparent"
    title: "quickshell-network"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    property string connectionType: "none"

    HyprlandFocusGrab {
        id: networkFocusGrab
        windows: [networkWindow]
        active: networkWindow.visible
        onCleared: networkWindow.visible = false
    }

    onVisibleChanged: {
        if (visible) {
        }
    }

    Loader {
        id: networkLoader
        anchors.fill: parent
        source: "widgets/NetworkPanel.qml"

        onLoaded: {
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.windowVisible = Qt.binding(function() { return networkWindow.visible })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.uiLanguage = Qt.binding(function() { return settingsMenu.uiLanguage })
            networkWindow.connectionType = Qt.binding(function() { return item.connectionType })
        }
    }
}

function openNearby() {
    audioWindow.visible = false
    bluetoothWindow.visible = false
    networkWindow.visible = false
    calendarWindow.visible = false
    startMenu.visible = false
    dockerWindow.visible = false
    ollamaWindow.visible = false
    nearbyWindow.visible = true
}

NearbyService {
    id: nearbyService
    onIncomingRequest: desktopShell.openNearby()
}

IpcHandler {
    target: "windoesnot-nearby"
    function share(files: string): string {
        try {
            const values = JSON.parse(files)
            if (!Array.isArray(values) || !values.length || values.length > 1000) return "invalid"
            nearbyService.command({action:"select", files:values})
            desktopShell.openNearby()
            return "opened"
        } catch (error) { return "invalid" }
    }
}

FloatingWindow {
    id: nearbyWindow
    visible: false
    implicitWidth: 400
    implicitHeight: 580
    color: "transparent"
    title: "quickshell-nearby"
    screen: networkWindow.screen

    onVisibleChanged: nearbyService.command({action:"active", value:visible})

    HyprlandFocusGrab {
        windows: [nearbyWindow]
        active: nearbyWindow.visible && !(nearbyLoader.item && nearbyLoader.item.dialogOpen)
        onCleared: nearbyWindow.visible = false
    }

    Loader {
        id: nearbyLoader
        anchors.fill: parent
        source: "widgets/NearbyPanel.qml"

        onLoaded: {
            item.service = nearbyService
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.uiLanguage = Qt.binding(function() { return settingsMenu.uiLanguage })
        }
    }
}

// Volume Overlay
FloatingWindow {
    id: volumeOverlay
    visible: false
    implicitWidth: 200
    implicitHeight: 80
    color: "transparent"
    title: "quickshell-volume-osd"

    property real currentVolume: 0
    property bool isMuted: false
    property real lastVolume: -1
    property bool lastMuted: false

    // Always show on primary monitor
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor) {
                return Quickshell.screens[i]
            }
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    // Function to manually show overlay
    function showOverlay() {
        volumeCheckProc.running = true
        visible = true
        hideTimer.restart()
    }

    // Timer to hide overlay after 1.5 seconds
    Timer {
        id: hideTimer
        interval: 1500
        running: false
        repeat: false
        onTriggered: {
            volumeOverlay.visible = false
        }
    }

    // Poll volume changes every 100ms
    Timer {
        id: volumePollTimer
        interval: 100
        running: true
        repeat: true
        onTriggered: {
            volumeCheckProc.running = true
        }
    }

    Process {
        id: volumeCheckProc
        command: ["bash", "-c", "wpctl get-volume @DEFAULT_AUDIO_SINK@"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var output = this.text.trim()
                // Output format: "Volume: 0.35" or "Volume: 0.35 [MUTED]"
                var parts = output.split(" ")

                if (parts.length >= 2) {
                    var vol = parseFloat(parts[1])
                    var muted = output.includes("[MUTED]")

                    // Check if volume or mute state changed
                    if (volumeOverlay.lastVolume !== vol || volumeOverlay.lastMuted !== muted) {
                        if (volumeOverlay.lastVolume !== -1 && !audioWindow.visible) {
                            // Not the first check, and audio panel is closed, so show overlay
                            volumeOverlay.currentVolume = vol
                            volumeOverlay.isMuted = muted
                            volumeOverlay.visible = true
                            hideTimer.restart()
                        }
                        volumeOverlay.lastVolume = vol
                        volumeOverlay.lastMuted = muted
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.centerIn: parent
        width: parent.width - 20
        height: parent.height - 20
        color: Qt.rgba(0.11, 0.11, 0.12, 0.95)
        radius: settingsMenu.borderRadius
        border.color: Qt.rgba(1, 1, 1, 0.1)
        border.width: 1

        Column {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            // Icon, Volume text and percentage in one row
            Row {
                spacing: 8
                anchors.horizontalCenter: parent.horizontalCenter

                // Volume icon
                Image {
                    id: volumeIcon
                    width: 20
                    height: 20
                    anchors.verticalCenter: parent.verticalCenter
                    source: volumeOverlay.isMuted ? "img/Win11-dark/status/symbolic/audio-volume-muted-symbolic.svg" :
                            volumeOverlay.currentVolume < 0.33 ? "img/Win11-dark/status/symbolic/audio-volume-low-symbolic.svg" :
                            volumeOverlay.currentVolume < 0.66 ? "img/Win11-dark/status/symbolic/audio-volume-medium-symbolic.svg" :
                            "img/Win11-dark/status/symbolic/audio-volume-high-symbolic.svg"
                    sourceSize.width: 40
                    sourceSize.height: 40
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                    mipmap: true
                    layer.enabled: true
                    layer.smooth: true
                }

                // Volume text
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    font.pixelSize: 14
                    font.weight: Font.Medium
                    color: "white"
                    text: Lang.get("shell.volume", settingsMenu.uiLanguage)
                }

                // Percentage
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    font.pixelSize: 14
                    font.weight: Font.Normal
                    color: "white"
                    text: volumeOverlay.isMuted ? Lang.get("shell.muted", settingsMenu.uiLanguage) :
                          Math.round(volumeOverlay.currentVolume * 100)
                }
            }

            // Volume bar
            Rectangle {
                width: parent.width
                height: 4
                radius: 2
                anchors.horizontalCenter: parent.horizontalCenter
                color: Qt.rgba(1, 1, 1, 0.15)

                Rectangle {
                    width: volumeOverlay.isMuted ? 0 : parent.width * volumeOverlay.currentVolume
                    height: parent.height
                    radius: 2
                    color: settingsMenu.accentColor

                    Behavior on width {
                        NumberAnimation { duration: 100 }
                    }
                }
            }
        }
    }
}

// Search Window
SearchWindow {
    id: searchWindow
    appsModel: allAppsModel
    darkMode: settingsMenu.darkMode
    borderRadius: settingsMenu.borderRadius
    accentColor: settingsMenu.accentColor
    uiLanguage: settingsMenu.uiLanguage
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }
}

// Super+S toggle via FIFO
Process {
    id: searchToggleProc
    command: ["bash", "-c", "mkfifo /tmp/qs-search-toggle 2>/dev/null; cat /tmp/qs-search-toggle"]
    running: true
    stdout: StdioCollector {
        onStreamFinished: {
            if (searchWindow.visible) searchWindow.closeSearch()
            else searchWindow.openSearch()
            searchToggleProc.running = false
            searchToggleProc.running = true
        }
    }
}

Process {
    id: deviceManagerLauncher
    command: ["windoesnot-device-manager"]
}

// Power Menu (StartOrb right-click)
FloatingWindow {
    id: powerMenu
    visible: false
    implicitWidth: 220
    implicitHeight: 528
    color: "transparent"
    title: "quickshell-powermenu"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    property int menuX: 0
    property int menuY: 0

    HyprlandFocusGrab {
        windows: powerSubMenu.visible ? [powerMenu, powerSubMenu] : [powerMenu]
        active: powerMenu.visible
        onCleared: { powerMenu.visible = false; powerSubMenu.visible = false }
    }

    Item {
        anchors.fill: parent
        clip: true
        Rectangle {
            anchors.fill: parent
            topLeftRadius: settingsMenu.borderRadius
            topRightRadius: settingsMenu.borderRadius
            bottomLeftRadius: 0
            bottomRightRadius: 0
            color: settingsMenu.darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        }
        Column {
            anchors { top: parent.top; left: parent.left; right: parent.right; margins: 6; bottomMargin: 8 }
            spacing: 0

            // Installierte Apps
            Rectangle {
                width: parent.width; height: 36; radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.installedApps", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "gnome-software & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // Energieoptionen
            Rectangle {
                width: parent.width; height: 36; radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.powerManagement", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "gnome-power-statistics & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // Ereignisanzeige
            Rectangle {
                width: parent.width; height: 36; radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.eventViewer", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "gnome-logs & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // System (Terminal + fastfetch)
            Rectangle {
                width: parent.width; height: 36; radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.system", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        var term = settingsMenu.defaultTerminal.length > 0
                            ? settingsMenu.defaultTerminal
                            : "ghostty"
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "' + term + ' -e bash -c \\"fastfetch; exec bash\\" & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // Device Manager — same menu row as the neighbouring system tools.
            Rectangle {
                width: parent.width; height: 36; radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.deviceManager", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        deviceManagerLauncher.running = true
                    }
                }
            }

            // Netzwerkverbindungen
            Rectangle {
                width: parent.width; height: 36; radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.networkConnections", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "nm-connection-editor & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // Datenträgerverwaltung
            Rectangle {
                width: parent.width; height: 36; radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.diskManager", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "gnome-disks & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // Separator
            Item {
                width: parent.width; height: 5
                Rectangle {
                    x: 6; width: parent.width - 12; height: 1
                    anchors.verticalCenter: parent.verticalCenter
                    color: settingsMenu.darkMode ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.15)
                }
            }

            // Task-Manager
            Rectangle {
                width: parent.width; height: 36
                radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.taskManager", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "gnome-system-monitor & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // Einstellungen
            Rectangle {
                width: parent.width; height: 36
                radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.settings", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        settingsMenu.visible = true
                    }
                }
            }

            // Explorer
            Rectangle {
                width: parent.width; height: 36
                radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.explorer", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "xdg-open $HOME & disown"]; running: true }', powerMenu)
                    }
                }
            }

            // Suchen
            Rectangle {
                width: parent.width; height: 36
                radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.search", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        searchWindow.openSearch()
                    }
                }
            }

            // Ausführen
            Rectangle {
                width: parent.width; height: 36
                radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.run", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "(kitty || foot || alacritty || xterm) &"]; running: true }', powerMenu)
                    }
                }
            }

            // Separator
            Item {
                width: parent.width; height: 5
                Rectangle {
                    x: 6; width: parent.width - 12; height: 1
                    anchors.verticalCenter: parent.verticalCenter
                    color: settingsMenu.darkMode ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.15)
                }
            }

            // Herunterfahren oder abmelden (öffnet Untermenü)
            Rectangle {
                width: parent.width; height: 36
                radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered || powerSubMenu.visible ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.powerOptions", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                Text {
                    anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                    text: "›"
                    color: settingsMenu.darkMode ? "#aaaaaa" : "#666666"; font.pixelSize: 16
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: {
                        parent.hovered = true
                        if (powerSubMenu.visible) return
                        var primaryScreen = null
                        for (var s = 0; s < Quickshell.screens.length; s++) {
                            if (Quickshell.screens[s].name === settingsMenu.primaryMonitor) {
                                primaryScreen = Quickshell.screens[s]; break
                            }
                        }
                        var monW = primaryScreen ? primaryScreen.width : (panelWindow.screen ? panelWindow.screen.width : 1280)
                        var monH = primaryScreen ? primaryScreen.height : (panelWindow.screen ? panelWindow.screen.height : 800)
                        var subX = powerMenu.menuX + 220
                        if (subX + 220 > monW) subX = powerMenu.menuX - 220
                        var subY = monH - 45 - 156
                        var subProc = Qt.createQmlObject('import Quickshell.Io; Process { }', powerMenu)
                        subProc.command = ["windoesnot-hyprctl", "keyword", "windowrule[powersubmenu-config]:move", subX + " " + subY]
                        subProc.exited.connect(function() { powerSubMenu.visible = true })
                        subProc.running = true
                    }
                    onExited: parent.hovered = false
                }
            }

            // Desktop anzeigen
            Rectangle {
                width: parent.width; height: 36
                radius: settingsMenu.borderRadius
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.showDesktop", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: { parent.hovered = true; powerSubMenu.visible = false }
                    onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", Quickshell.env("HOME") + "/.config/hypr/hide_windows.sh"]; running: true }', powerMenu)
                    }
                }
            }

            Item { width: parent.width; height: 8 }
        }
    }
}

// Power Sub Menu (Herunterfahren oder abmelden)
FloatingWindow {
    id: powerSubMenu
    visible: false
    implicitWidth: 220
    implicitHeight: 156
    color: "transparent"
    title: "quickshell-powersubmenu"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    Item {
        anchors.fill: parent
        clip: true
        Rectangle {
            anchors.fill: parent
            topLeftRadius: settingsMenu.borderRadius
            topRightRadius: settingsMenu.borderRadius
            bottomLeftRadius: 0
            bottomRightRadius: 0
            color: settingsMenu.darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        }
        Column {
            anchors { top: parent.top; left: parent.left; right: parent.right; margins: 6 }
            spacing: 0

            // Abmelden
            Rectangle {
                width: parent.width; height: 36
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.logout", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["bash", "-c", "loginctl terminate-user $USER"]; running: true }', powerSubMenu)
                    }
                }
            }

            // Energie sparen
            Rectangle {
                width: parent.width; height: 36
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.sleep", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["systemctl", "suspend"]; running: true }', powerSubMenu)
                    }
                }
            }

            // Herunterfahren
            Rectangle {
                width: parent.width; height: 36
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.shutdown", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["systemctl", "poweroff"]; running: true }', powerSubMenu)
                    }
                }
            }

            // Neu starten
            Rectangle {
                width: parent.width; height: 36
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("power.restart", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        powerMenu.visible = false; powerSubMenu.visible = false
                        Qt.createQmlObject('import Quickshell.Io; Process { command: ["systemctl", "reboot"]; running: true }', powerSubMenu)
                    }
                }
            }

            Item { width: parent.width; height: 6 }
        }
    }
}

// App Context Menu (Taskbar app right-click)
PopupWindow {
    id: appContextMenu
    visible: false
    implicitWidth: 220
    implicitHeight: ctxIsOpen ? 129 : 84
    color: "transparent"
    property int menuX: 0
    anchor {
        window: panelWindow
        edges: Edges.Top | Edges.Left
        gravity: Edges.Top | Edges.Left
        adjustment: PopupAdjustment.None
        rect.x: appContextMenu.menuX
        rect.y: 0
    }

    HyprlandFocusGrab {
        windows: [appContextMenu]
        active: appContextMenu.visible
        onCleared: appContextMenu.visible = false
    }

    property string ctxAppName: ""
    property string ctxAppCmd: ""
    property bool ctxAppPinned: false
    property bool ctxAppTemporary: false
    property var ctxAppWindows: []
    property bool ctxIsOpen: ctxAppWindows.length > 0
    property bool ctxHasVisible: {
        for (var i = 0; i < ctxAppWindows.length; i++) {
            if (!ctxAppWindows[i].hidden) return true
        }
        return false
    }
    Item {
        anchors.fill: parent
        clip: true
        Rectangle {
            anchors.fill: parent
            topLeftRadius: settingsMenu.borderRadius
            topRightRadius: settingsMenu.borderRadius
            bottomLeftRadius: 0
            bottomRightRadius: 0
            color: settingsMenu.darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        }
        Column {
            anchors { top: parent.top; left: parent.left; right: parent.right; margins: 6 }
            spacing: 0

            // Open (only when app is NOT running)
            Rectangle {
                width: parent.width
                height: !appContextMenu.ctxIsOpen && appContextMenu.ctxAppCmd !== "" ? 36 : 0
                clip: true
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("taskbar.open", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    enabled: !appContextMenu.ctxIsOpen
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        var proc = Qt.createQmlObject('import Quickshell.Io; Process { }', appContextMenu)
                        proc.command = ["bash", "-c", appContextMenu.ctxAppCmd]
                        proc.running = true
                        appContextMenu.visible = false
                    }
                }
            }

            // Hide / Show (only when app is running)
            Rectangle {
                width: parent.width
                height: appContextMenu.ctxIsOpen ? 36 : 0
                clip: true
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: appContextMenu.ctxHasVisible
                          ? Lang.get("taskbar.hide", settingsMenu.uiLanguage)
                          : Lang.get("taskbar.show", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    enabled: appContextMenu.ctxIsOpen
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        var windows = appContextMenu.ctxAppWindows
                        var proc = Qt.createQmlObject('import Quickshell.Io; Process { }', appContextMenu)
                        var visibleWins = [], hiddenWins = []
                        for (var i = 0; i < windows.length; i++) {
                            if (windows[i].hidden) hiddenWins.push(windows[i])
                            else visibleWins.push(windows[i])
                        }
                        if (visibleWins.length > 0) {
                            var cmds = []
                            for (var j = 0; j < visibleWins.length; j++)
                                cmds.push("windoesnot-hyprctl dispatch movetoworkspacesilent special:minimized,address:" + visibleWins[j].address)
                            proc.command = ["bash", "-c", cmds.join(" && ")]
                        } else if (hiddenWins.length > 0) {
                            var cmds = []
                            for (var k = 0; k < hiddenWins.length; k++) {
                                var tw = hiddenWins[k].restoreWorkspace
                                if (tw < 0) cmds.push("windoesnot-hyprctl dispatch movetoworkspace e+0,address:" + hiddenWins[k].address)
                                else if (k === 0) cmds.push("windoesnot-hyprctl dispatch movetoworkspace " + tw + ",address:" + hiddenWins[k].address)
                                else cmds.push("windoesnot-hyprctl dispatch movetoworkspacesilent " + tw + ",address:" + hiddenWins[k].address)
                            }
                            cmds.push("sleep 0.15")
                            cmds.push("windoesnot-hyprctl dispatch focuswindow address:" + hiddenWins[0].address)
                            cmds.push("windoesnot-hyprctl dispatch resizeactive 1 0")
                            cmds.push("windoesnot-hyprctl dispatch resizeactive -1 0")
                            proc.command = ["bash", "-c", cmds.join(" && ")]
                        }
                        proc.running = true
                        appContextMenu.visible = false
                    }
                }
            }

            // Close / Beenden (only when app is running)
            Rectangle {
                width: parent.width
                height: appContextMenu.ctxIsOpen ? 36 : 0
                clip: true
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: Lang.get("taskbar.close", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    enabled: appContextMenu.ctxIsOpen
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        var windows = appContextMenu.ctxAppWindows
                        var cmds = []
                        for (var i = 0; i < windows.length; i++)
                            cmds.push("windoesnot-hyprctl dispatch closewindow address:" + windows[i].address)
                        var proc = Qt.createQmlObject('import Quickshell.Io; Process { }', appContextMenu)
                        proc.command = ["bash", "-c", cmds.join(" && ")]
                        proc.running = true
                        appContextMenu.visible = false
                    }
                }
            }

            // Separator (only when app is running)
            Item {
                width: parent.width
                height: appContextMenu.ctxIsOpen ? 9 : 0
                clip: true
                Rectangle {
                    x: 6; width: parent.width - 12; height: 1
                    anchors.verticalCenter: parent.verticalCenter
                    color: settingsMenu.darkMode ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.15)
                }
            }

            // Pin / Unpin (always visible)
            Rectangle {
                width: parent.width; height: 36
                radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: appContextMenu.ctxAppTemporary
                          ? Lang.get("taskbar.pin", settingsMenu.uiLanguage)
                          : Lang.get("taskbar.unpin", settingsMenu.uiLanguage)
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"; font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        if (appContextMenu.ctxAppTemporary) {
                            for (var i = 0; i < panelWindow.taskbarApps.length; i++) {
                                if (panelWindow.taskbarApps[i].name === appContextMenu.ctxAppName) {
                                    panelWindow.taskbarApps[i].temporary = false
                                    panelWindow.taskbarApps[i].pinned = true
                                    break
                                }
                            }
                            panelWindow.saveTaskbarApps()
                            panelWindow.rebuildTaskbarModel()
                        } else {
                            panelWindow.removeFromTaskbar(appContextMenu.ctxAppName)
                        }
                        appContextMenu.visible = false
                    }
                }
            }
            Item { width: parent.width; height: 6 }
        }
    }
}

// Taskbar background right-click menu
FloatingWindow {
    id: taskbarBgMenu
    visible: false
    color: "transparent"
    title: "quickshell-tbgmenu"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor) return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    property var hiddenWindows: []

    // 3 fixed items + 1 separator + hidden section
    implicitWidth:  220
    implicitHeight: 6 + 36 + 36 + 36 + 1
                    + (hiddenWindows.length > 0 ? (22 + hiddenWindows.length * 36) : 36)
                    + 6

    HyprlandFocusGrab {
        windows: [taskbarBgMenu]
        active: taskbarBgMenu.visible
        onCleared: taskbarBgMenu.visible = false
    }

    Item {
        anchors.fill: parent
        clip: true
        Rectangle {
            anchors.fill: parent
            topLeftRadius: settingsMenu.borderRadius
            topRightRadius: settingsMenu.borderRadius
            bottomLeftRadius: 0
            bottomRightRadius: 0
            color: settingsMenu.darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        }

        Column {
            anchors { top: parent.top; left: parent.left; right: parent.right; margins: 6 }
            spacing: 0

            // Desktop anzeigen / Fenster einblenden
            Rectangle {
                width: parent.width; height: 36; radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Behavior on color { ColorAnimation { duration: 80 } }
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: taskbarBgMenu.hiddenWindows.length > 0
                        ? (settingsMenu.uiLanguage === "en" ? "Show Windows Again" : "Fenster wieder einblenden")
                        : (settingsMenu.uiLanguage === "en" ? "Show Desktop"  : "Desktop anzeigen")
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"
                    font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        taskbarBgMenu.visible = false
                        // Toggle: if any hidden windows exist → restore all, else minimize all
                        var hasHidden = taskbarBgMenu.hiddenWindows.length > 0
                        var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', taskbarBgMenu)
                        if (hasHidden) {
                            // Restore all hidden windows
                            var cmds = []
                            for (var i = 0; i < taskbarBgMenu.hiddenWindows.length; i++) {
                                var w = taskbarBgMenu.hiddenWindows[i]
                                var rws = w.restoreWorkspace
                                var target = (rws !== undefined && rws > 0) ? rws : -1
                                cmds.push(target > 0
                                    ? "windoesnot-hyprctl dispatch movetoworkspace " + target + ",address:" + w.address
                                    : "windoesnot-hyprctl dispatch movetoworkspace e+0,address:" + w.address)
                            }
                            proc.command = ["bash", "-c", cmds.join(" && ")]
                        } else {
                            // Minimize all non-quickshell windows
                            proc.command = ["python3", "-c",
                                "import subprocess,json\n" +
                                "cs=json.loads(subprocess.check_output(['windoesnot-hyprctl','clients','-j']))\n" +
                                "[subprocess.run(['windoesnot-hyprctl','dispatch','movetoworkspacesilent','special:minimized,address:'+c['address']]) for c in cs if 'quickshell' not in c['class'].lower() and 'special' not in (c['workspace']['name'] or '')]"]
                        }
                        proc.running = true
                    }
                }
            }

            // Taskbar-Ausrichtung
            Rectangle {
                width: parent.width; height: 36; radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Behavior on color { ColorAnimation { duration: 80 } }
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: settingsMenu.uiLanguage === "en" ? "Taskbar Alignment" : "Taskbar-Ausrichtung"
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"
                    font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        taskbarBgMenu.visible = false
                        settingsMenu.currentCategory = "alignment"
                        settingsMenu.visible = true
                    }
                }
            }

            // Quickshell neu starten
            Rectangle {
                width: parent.width; height: 36; radius: 6
                property bool hovered: false
                color: hovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                Behavior on color { ColorAnimation { duration: 80 } }
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: settingsMenu.uiLanguage === "en" ? "Restart Quickshell" : "Quickshell neu starten"
                    color: settingsMenu.darkMode ? "white" : "#1a1a1a"
                    font.pixelSize: 13
                }
                Process {
                    id: tbgRestartProc
                    command: ["bash", "-c",
                        "setsid bash -c 'sleep 0.2; killall quickshell; sleep 0.4; QT_QPA_PLATFORMTHEME=gtk3 quickshell' &>/dev/null &"]
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true; onExited: parent.hovered = false
                    onClicked: {
                        taskbarBgMenu.visible = false
                        tbgRestartProc.running = true
                    }
                }
            }

            // Separator
            Rectangle {
                width: parent.width; height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#e0e0e0"
            }

            // Hidden windows section header (only when there are hidden windows)
            Item {
                width: parent.width
                height: taskbarBgMenu.hiddenWindows.length > 0 ? 22 : 0
                clip: true
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: settingsMenu.uiLanguage === "en" ? "Hidden Windows" : "Versteckte Fenster"
                    font.pixelSize: 11
                    color: settingsMenu.darkMode ? "#666" : "#999"
                }
            }

            // Empty state
            Rectangle {
                width: parent.width
                height: taskbarBgMenu.hiddenWindows.length === 0 ? 36 : 0
                clip: true; color: "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: settingsMenu.uiLanguage === "en" ? "No hidden windows" : "Keine versteckten Fenster"
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#555" : "#aaa"
                }
            }

            // Hidden window items
            Repeater {
                model: taskbarBgMenu.hiddenWindows
                delegate: Rectangle {
                    width: parent.width; height: 36; radius: 6
                    property bool itemHovered: false
                    color: itemHovered ? (settingsMenu.darkMode ? "#4A4A4D" : "#e0e0e0") : "transparent"
                    Behavior on color { ColorAnimation { duration: 80 } }

                    Row {
                        anchors { left: parent.left; leftMargin: 8; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        spacing: 8
                        Image {
                            width: 16; height: 16
                            anchors.verticalCenter: parent.verticalCenter
                            source: modelData.customIcon
                                ? Qt.resolvedUrl("img/" + modelData.icon + ".svg")
                                : ("image://icon/" + modelData.icon)
                            fillMode: Image.PreserveAspectFit
                        }
                        Text {
                            text: modelData.title !== modelData.appName
                                  ? modelData.appName + " – " + modelData.title
                                  : modelData.appName
                            font.pixelSize: 13
                            color: settingsMenu.darkMode ? "white" : "#1a1a1a"
                            width: 180; elide: Text.ElideRight
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onEntered: parent.itemHovered = true; onExited: parent.itemHovered = false
                        onClicked: {
                            taskbarBgMenu.visible = false
                            var addr = modelData.address
                            var rws  = modelData.restoreWorkspace
                            var proc = Qt.createQmlObject('import Quickshell.Io; Process {}', taskbarBgMenu)
                            var target = (rws !== undefined && rws > 0) ? rws : -1
                            var cmd = target > 0
                                ? "windoesnot-hyprctl dispatch movetoworkspace " + target + ",address:" + addr
                                : "windoesnot-hyprctl dispatch movetoworkspace e+0,address:" + addr
                            proc.command = ["bash", "-c", cmd + " && windoesnot-hyprctl dispatch focuswindow address:" + addr]
                            proc.running = true
                        }
                    }
                }
            }

            Item { width: parent.width; height: 6 }
        }
    }
}

// Weather Popup
FloatingWindow {
    id: weatherPopup
    visible: false
    color: "transparent"
    title: "quickshell-weather"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor) return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }
    implicitWidth: 380
    implicitHeight: Math.round(weatherPopupCol.height + 30)

    HyprlandFocusGrab {
        windows: [weatherPopup]
        active: weatherPopup.visible
        onCleared: weatherPopup.visible = false
    }

    Item {
        anchors.fill: parent
        clip: true

        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: weatherPopupCol.height + 30
            topLeftRadius: settingsMenu.borderRadius; topRightRadius: settingsMenu.borderRadius
            bottomLeftRadius: 0; bottomRightRadius: 0
            color: settingsMenu.darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.97) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
            border.color: settingsMenu.darkMode ? "#3a3a3f" : "#c0c0c0"
            border.width: 1
        }

        Column {
            id: weatherPopupCol
            anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 20; leftMargin: 20; rightMargin: 20 }
            spacing: 8

            // Header: city name + last update time
            Item {
                width: parent.width
                height: 24
                Text {
                    text: settingsMenu.weatherCity
                    font.pixelSize: 16; font.bold: true
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: panelWindow.weatherUpdateTime.length > 0 ? Lang.get("weather.updated", settingsMenu.uiLanguage) + " " + panelWindow.weatherUpdateTime : ""
                    font.pixelSize: 11
                    color: settingsMenu.darkMode ? "#666" : "#999"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Current conditions
            Row {
                width: parent.width
                spacing: 16

                Image {
                    width: 80; height: 80
                    source: panelWindow.weatherCode >= 0
                        ? panelWindow.weatherIconPath(panelWindow.weatherCode, panelWindow.weatherIsDay)
                        : ""
                    sourceSize.width: 160; sourceSize.height: 160
                    fillMode: Image.PreserveAspectFit
                    smooth: true; antialiasing: true; mipmap: true
                    anchors.verticalCenter: parent.verticalCenter
                }

                Column {
                    spacing: 4
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        text: panelWindow.weatherTemp + "°C"
                        font.pixelSize: 42; font.bold: true
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    }
                    Text {
                        text: panelWindow.wmoToDesc(panelWindow.weatherCode)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#ccc" : "#444"
                    }
                    Row {
                        spacing: 16
                        Text {
                            text: Lang.get("weather.feelsLike", settingsMenu.uiLanguage) + " " + panelWindow.weatherFeelsLike + "°C"
                            font.pixelSize: 12; color: settingsMenu.darkMode ? "#888" : "#666"
                        }
                        Row {
                            spacing: 5
                            ProjectIcon { name: "drop"; font.pixelSize: 14; color: settingsMenu.darkMode ? "#aaa" : "#555" }
                            Text { text: panelWindow.weatherHumidity + "%"; font.pixelSize: 12; color: settingsMenu.darkMode ? "#888" : "#666" }
                        }
                        Row {
                            spacing: 5
                            ProjectIcon { name: "wind"; font.pixelSize: 14; color: settingsMenu.darkMode ? "#aaa" : "#555" }
                            Text { text: panelWindow.weatherWindSpeed + " km/h"; font.pixelSize: 12; color: settingsMenu.darkMode ? "#888" : "#666" }
                        }
                    }
                }
            }

            // Separator
            Rectangle {
                width: parent.width; height: 1
                color: settingsMenu.darkMode ? Qt.rgba(1,1,1,0.1) : Qt.rgba(0,0,0,0.1)
            }

            // Tabs
            Rectangle {
                width: parent.width
                height: 30
                radius: 6
                color: settingsMenu.darkMode ? Qt.rgba(1,1,1,0.04) : Qt.rgba(0,0,0,0.04)
                Row {
                    anchors.fill: parent
                    spacing: 0

                    Rectangle {
                        width: parent.width / 2
                        height: parent.height
                        radius: 6
                        color: panelWindow.weatherActiveTab === 0
                               ? (settingsMenu.darkMode ? Qt.rgba(1,1,1,0.10) : Qt.rgba(0,0,0,0.10))
                               : "transparent"
                        Text {
                            anchors.centerIn: parent
                            text: Lang.get("weather.today", settingsMenu.uiLanguage)
                            font.pixelSize: 12; font.bold: panelWindow.weatherActiveTab === 0
                            color: settingsMenu.darkMode ? "#d7d7d7" : "#4a4a4a"
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                panelWindow.weatherActiveTab = 0
                                Qt.callLater(function() { panelWindow.scrollWeatherHourlyToNow() })
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width / 2
                        height: parent.height
                        radius: 6
                        color: panelWindow.weatherActiveTab === 1
                               ? (settingsMenu.darkMode ? Qt.rgba(1,1,1,0.10) : Qt.rgba(0,0,0,0.10))
                               : "transparent"
                        Text {
                            anchors.centerIn: parent
                            text: Lang.get("weather.forecast7", settingsMenu.uiLanguage)
                            font.pixelSize: 12; font.bold: panelWindow.weatherActiveTab === 1
                            color: settingsMenu.darkMode ? "#d7d7d7" : "#4a4a4a"
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: panelWindow.weatherActiveTab = 1
                        }
                    }
                }
            }

            // Today timeline
            Flickable {
                id: weatherHourlyFlick
                width: parent.width
                height: 108
                visible: panelWindow.weatherActiveTab === 0
                clip: true
                contentWidth: hourlyRow.width
                contentHeight: height
                onVisibleChanged: {
                    if (visible) Qt.callLater(function() { panelWindow.scrollWeatherHourlyToNow() })
                }
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton
                    onWheel: function(wheel) {
                        var rawDelta = wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : wheel.angleDelta.x
                        if (rawDelta === 0) return
                        var steps = rawDelta / 120.0
                        var stepPx = 36
                        var maxX = Math.max(0, weatherHourlyFlick.contentWidth - weatherHourlyFlick.width)
                        var nextX = weatherHourlyFlick.contentX - (steps * stepPx)
                        weatherHourlyFlick.contentX = Math.max(0, Math.min(maxX, nextX))
                        wheel.accepted = true
                    }
                }

                Row {
                    id: hourlyRow
                    spacing: panelWindow.weatherHourlyItemSpacing

                    Repeater {
                        model: panelWindow.weatherHourlyToday
                        delegate: Column {
                            width: panelWindow.weatherHourlyItemWidth
                            spacing: 5

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: modelData.time
                                font.pixelSize: 10
                                color: settingsMenu.darkMode ? "#aaa" : "#666"
                            }
                            Image {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 24; height: 24
                                source: panelWindow.weatherIconPath(modelData.code, modelData.isDay)
                                sourceSize.width: 48; sourceSize.height: 48
                                fillMode: Image.PreserveAspectFit
                                smooth: true; antialiasing: true; mipmap: true
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: modelData.temp + "°"
                                font.pixelSize: 11; font.bold: true
                                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: modelData.precipProb + "%"
                                font.pixelSize: 10
                                color: "#4fc3f7"
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: modelData.wind + " km/h"
                                font.pixelSize: 10
                                color: settingsMenu.darkMode ? "#888" : "#777"
                            }
                        }
                    }
                }
            }

            // 7-day forecast
            Row {
                width: parent.width
                spacing: 0
                visible: panelWindow.weatherActiveTab === 1

                Repeater {
                    model: panelWindow.weatherForecast

                    delegate: Column {
                        width: parent.width / 7
                        spacing: 6

                        property var d: new Date(modelData.date + "T12:00:00")
                        property string dayName: {
                            var idx = d.getDay()
                            return Lang.get("weather.days", settingsMenu.uiLanguage)[idx]
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: index === 0 ? Lang.get("weather.today", settingsMenu.uiLanguage) : dayName
                            font.pixelSize: 11; font.bold: index === 0
                            color: settingsMenu.darkMode ? "#aaa" : "#666"
                        }

                        Image {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 32; height: 32
                            source: panelWindow.weatherIconPath(modelData.code, true)
                            sourceSize.width: 64; sourceSize.height: 64
                            fillMode: Image.PreserveAspectFit
                            smooth: true; antialiasing: true; mipmap: true
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.tempMax + "°"
                            font.pixelSize: 12; font.bold: true
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.tempMin + "°"
                            font.pixelSize: 11
                            color: settingsMenu.darkMode ? "#888" : "#888"
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.precipProb + "%"
                            font.pixelSize: 10
                            color: "#4fc3f7"
                            visible: modelData.precipProb > 0
                        }
                    }
                }
            }

            // Refresh button
            Rectangle {
                width: parent.width; height: 32; radius: 6
                color: refreshMouse.containsMouse ? (settingsMenu.darkMode ? "#2a2a2a" : "#e0e0e0") : "transparent"
                Behavior on color { ColorAnimation { duration: 80 } }
                Text {
                    anchors.centerIn: parent
                    text: Lang.get("weather.refresh", settingsMenu.uiLanguage)
                    font.pixelSize: 12
                    color: settingsMenu.darkMode ? "#888" : "#666"
                }
                MouseArea {
                    id: refreshMouse
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: panelWindow.fetchWeather()
                }
            }
        }
    }
}

// Taskbar Window Preview (hover über Icons mit mehreren Fenstern)
TaskbarPreview {
    id: taskbarPreview
    settingsMenu: settingsMenu
}

// Snap Preview Overlay
SnapPreviewSimple {
    snapManager: snapManager
    settingsMenu: settingsMenu
}

// Docker Panel
FloatingWindow {
    id: dockerWindow
    visible: false
    implicitWidth: 340
    implicitHeight: 420
    color: "transparent"
    title: "quickshell-docker"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    HyprlandFocusGrab {
        windows: [dockerWindow]
        active: dockerWindow.visible
        onCleared: dockerWindow.visible = false
    }

    Loader {
        id: dockerLoader
        anchors.fill: parent
        active: settingsMenu.showDockerTray
        source: "widgets/DockerPanel.qml"
        asynchronous: false

        onLoaded: {
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.windowVisible = Qt.binding(function() { return dockerWindow.visible })
        }
    }
}

// Ollama Panel
FloatingWindow {
    id: ollamaWindow
    visible: false
    implicitWidth: 360
    implicitHeight: 480
    color: "transparent"
    title: "quickshell-ollama"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    HyprlandFocusGrab {
        windows: [ollamaWindow]
        active: ollamaWindow.visible
        onCleared: ollamaWindow.visible = false
    }

    Loader {
        anchors.fill: parent
        active: settingsMenu.showOllamaTray
        source: "widgets/OllamaPanel.qml"
        onLoaded: {
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.windowVisible = Qt.binding(function() { return ollamaWindow.visible })
            item.defaultTerminal = Qt.binding(function() { return settingsMenu.defaultTerminal })
        }
    }
}

Connections {
    target: settingsMenu
    function onShowDockerTrayChanged() { if (!settingsMenu.showDockerTray) dockerWindow.visible = false }
    function onShowOllamaTrayChanged() { if (!settingsMenu.showOllamaTray) ollamaWindow.visible = false }
    function onShowNearbyTrayChanged() { if (!settingsMenu.showNearbyTray) nearbyWindow.visible = false }
}

// Does (AI panel). A window closed by the compositor (title bar X) cannot be
// shown again, so the loader builds a fresh one; chats are stored on disk.
LazyLoader {
    id: copilotWindowLoader
    active: true

FloatingWindow {
    id: copilotFloating
    visible: false
    readonly property var host: copilotLoader.item
    onClosed: Qt.callLater(function() {
        copilotWindowLoader.active = false
        copilotWindowLoader.active = true
    })
    implicitWidth: 1100
    implicitHeight: 760
    color: "transparent"
    title: copilotLoader.item ? (copilotLoader.item.isPinned ? "quickshell-does-pinned" : "quickshell-does") : "quickshell-does"
    screen: {
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === settingsMenu.primaryMonitor)
                return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }

    // Panel is always pinned — no FocusGrab needed

    Loader {
        id: copilotLoader
        anchors.fill: parent
        source: "widgets/CopilotPanelHost.qml"
        asynchronous: false

        onLoaded: {
            console.log("Copilot panel host loaded successfully")
            item.accentColor = Qt.binding(function() { return settingsMenu.accentColor })
            item.borderRadius = Qt.binding(function() { return settingsMenu.borderRadius })
            item.darkMode = Qt.binding(function() { return settingsMenu.darkMode })
            item.windowVisible = Qt.binding(function() { return copilotFloating.visible })
            item.uiLanguage = Qt.binding(function() { return settingsMenu.uiLanguage })

            // Handle pin state changes - close and reopen window
            item.closeAndReopenWindow.connect(function(newPinState) {
                console.log("[Copilot] ========================================")
                console.log("[Copilot] closeAndReopenWindow signal received!")
                console.log("[Copilot] newPinState:", newPinState)
                console.log("[Copilot] Closing window...")
                copilotFloating.visible = false
                Qt.callLater(function() {
                    console.log("[Copilot] Reopening window with newPinState:", newPinState)
                    panelWindow.openCopilotPopup(null)  // null = no icon positioning
                    console.log("[Copilot] ========================================")
                })
            })
        }

        onStatusChanged: {
            if (status === Loader.Error) {
                console.error("Copilot panel host failed to load")
            } else if (status === Loader.Loading) {
                console.log("Copilot panel host is loading...")
            }
        }
    }
}
}

}
