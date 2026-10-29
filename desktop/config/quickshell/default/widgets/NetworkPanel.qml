import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: networkPanel
    width: 320
    height: networkPanel.showPasswordDialog ? 650 : 500

    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12  // Default value, wird von shell.qml gebunden
    property bool darkMode: true  // Wird von shell.qml gesetzt
    property string uiLanguage: "de"  // Bound from shell.qml
    property bool wifiEnabled: false
    property bool ethernetEnabled: true
    property string connectionType: "none"  // "wifi", "ethernet", "none"
    property bool windowVisible: false
    property string currentConnection: ""
    property var availableNetworks: []
    property string selectedNetwork: ""
    property bool showPasswordDialog: false
    property bool isConnecting: false
    property string connectionStatus: ""  // "success", "failed", ""

    property bool initialized: false

    Component.onCompleted: {
        // Load initial data once at startup
        updateNetworkState()
        // Also scan for WiFi networks immediately
        getAvailableNetworksProc.running = true
        initialized = true
    }

    // Update when panel becomes visible
    onVisibleChanged: {
        if (visible) {
            updateNetworkState()
        }
    }

    Timer {
        interval: 3000
        running: networkPanel.windowVisible  // Only run when panel is visible
        repeat: true
        onTriggered: updateNetworkState()
    }

    function updateNetworkState() {
        getWifiStatusProc.running = true
        getCurrentConnectionProc.running = true
        getActiveWifiProc.running = true
        if (wifiEnabled) {
            getAvailableNetworksProc.running = true
        } else {
            // Clear network list when WiFi is disabled
            networkPanel.availableNetworks = []
            networkPanel.activeWifiSSID = ""
        }
    }

    // Check if WiFi is enabled
    Process {
        id: getWifiStatusProc
        command: ["bash", "-c", "nmcli radio wifi"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var status = this.text.trim()
                networkPanel.wifiEnabled = (status === "enabled")
            }
        }
    }

    // Toggle WiFi
    Process {
        id: toggleWifiProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                Qt.callLater(function() {
                    updateNetworkState()
                })
            }
        }
    }

    // Get current connection
    Process {
        id: getCurrentConnectionProc
        command: ["bash", "-c", "nmcli -t -f NAME,TYPE,DEVICE connection show --active | head -1"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var line = this.text.trim()
                if (line.length > 0) {
                    var parts = line.split(':')
                    if (parts.length >= 2) {
                        networkPanel.currentConnection = parts[0]
                        var type = parts[1]
                        if (type === "802-11-wireless" || type === "wifi") {
                            networkPanel.connectionType = "wifi"
                        } else if (type === "802-3-ethernet" || type === "ethernet") {
                            networkPanel.connectionType = "ethernet"
                        } else {
                            networkPanel.connectionType = "other"
                        }
                    }
                } else {
                    networkPanel.currentConnection = ""
                    networkPanel.connectionType = "none"
                }
                console.log("Connection:", networkPanel.currentConnection, "Type:", networkPanel.connectionType)
            }
        }
    }

    // Get active WiFi connection SSID
    property string activeWifiSSID: ""

    Process {
        id: getActiveWifiProc
        command: ["bash", "-c", "nmcli -t -f NAME,TYPE connection show --active | grep '802-11-wireless' | head -1 | cut -d: -f1"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                networkPanel.activeWifiSSID = this.text.trim()
                console.log("Active WiFi SSID:", networkPanel.activeWifiSSID)
            }
        }
    }

    // Get available WiFi networks (scans for nearby networks)
    Process {
        id: getAvailableNetworksProc
        command: ["bash", "-c", "nmcli -t -f SSID,SIGNAL,SECURITY device wifi list | grep -v '^$'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.trim().split('\n')
                var networks = []
                var seenSSIDs = {}

                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].length > 0) {
                        var parts = lines[i].split(':')
                        if (parts.length >= 2) {
                            var ssid = parts[0].trim()
                            var signal = parts[1].trim()
                            var security = parts.length > 2 ? parts[2].trim() : ""
                            // Use language-independent active detection by comparing with activeWifiSSID
                            var active = (ssid === networkPanel.activeWifiSSID && networkPanel.activeWifiSSID.length > 0)

                            // Skip empty SSIDs
                            if (!ssid || ssid.length === 0 || ssid === "--") {
                                continue
                            }

                            // Skip duplicates (keep strongest signal)
                            if (seenSSIDs[ssid]) {
                                var existingSignal = seenSSIDs[ssid].signal
                                var newSignal = signal ? parseInt(signal) : 0
                                if (newSignal <= existingSignal) {
                                    continue
                                } else {
                                    // Remove old entry
                                    networks = networks.filter(function(n) { return n.ssid !== ssid })
                                }
                            }

                            var networkData = {
                                ssid: ssid,
                                signal: signal ? parseInt(signal) : 0,
                                secured: security.length > 0 && security !== "--",
                                active: active
                            }

                            networks.push(networkData)
                            seenSSIDs[ssid] = networkData
                        }
                    }
                }

                // Sort by signal strength
                networks.sort(function(a, b) {
                    // Active network first
                    if (a.active && !b.active) return -1
                    if (!a.active && b.active) return 1
                    // Then by signal strength
                    return b.signal - a.signal
                })

                networkPanel.availableNetworks = networks
                console.log("Available WiFi networks:", networks.length)
                if (networks.length > 0) {
                    console.log("First network:", networks[0].ssid, "Signal:", networks[0].signal, "Secured:", networks[0].secured, "Active:", networks[0].active)
                }
                // Debug: Log raw nmcli output
                console.log("Raw nmcli output (first 3 lines):")
                for (var j = 0; j < Math.min(3, lines.length); j++) {
                    console.log("  Line", j, ":", lines[j])
                }
            }
        }
    }

    // Connect to network
    Process {
        id: connectToNetworkProc
        command: ["bash", "-c", ""]
        running: false

        property string stdoutText: ""
        property string stderrText: ""

        stdout: StdioCollector {
            onStreamFinished: {
                connectToNetworkProc.stdoutText = this.text
                console.log("Connect stdout:", this.text)
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                connectToNetworkProc.stderrText = this.text
                console.log("Connect stderr:", this.text)
            }
        }
        onExited: {
            console.log("nmcli exit code:", exitCode)

            // Exit code 0 = success
            if (exitCode === 0) {
                networkPanel.connectionStatus = "success"
                networkPanel.isConnecting = false
                console.log("Connection successful! (exit code 0)")
            } else {
                // Check error messages
                var errorText = (connectToNetworkProc.stderrText + " " + connectToNetworkProc.stdoutText).toLowerCase()

                if (errorText.includes("secrets were required") || errorText.includes("password")) {
                    console.log("Wrong password")
                } else if (errorText.includes("no network")) {
                    console.log("Network not found")
                } else {
                    console.log("Connection failed with exit code:", exitCode)
                }

                networkPanel.connectionStatus = "failed"
                networkPanel.isConnecting = false
            }

            // Clear buffers
            connectToNetworkProc.stdoutText = ""
            connectToNetworkProc.stderrText = ""
        }
        onRunningChanged: {
            if (running) {
                networkPanel.isConnecting = true
                networkPanel.connectionStatus = ""
            } else {
                Qt.callLater(function() {
                    // Wait a bit for connection to establish, then update
                    updateNetworkState()
                    // Auto-hide password dialog after 2 seconds if successful
                    if (networkPanel.connectionStatus === "success") {
                        Qt.callLater(function() {
                            networkPanel.showPasswordDialog = false
                            networkPanel.connectionStatus = ""
                        })
                    }
                })
            }
        }
    }

    function connectToWifi(ssid, isSecured, isActive) {
        networkPanel.selectedNetwork = ssid

        if (isActive) {
            // Already connected - show disconnect option instead
            return
        }

        if (isSecured) {
            // Show password dialog
            networkPanel.showPasswordDialog = true
        } else {
            // Connect directly (open network)
            connectToNetworkProc.command = ["bash", "-c", "nmcli device wifi connect \"" + ssid + "\""]
            connectToNetworkProc.running = true
        }
    }

    function connectWithPassword(password) {
        if (networkPanel.selectedNetwork && password) {
            // Escape single quotes for shell safety
            var ssid = networkPanel.selectedNetwork.replace(/'/g, "'\\''")
            var pass = password.replace(/'/g, "'\\''")

            // Delete existing connection if it exists, then create new one with proper WPA settings
            var cmd = "nmcli connection delete '" + ssid + "' 2>/dev/null; " +
                     "nmcli connection add type wifi con-name '" + ssid + "' ifname '*' ssid '" + ssid +
                     "' wifi-sec.key-mgmt wpa-psk wifi-sec.psk '" + pass + "' && " +
                     "nmcli connection up '" + ssid + "'"
            connectToNetworkProc.command = ["bash", "-c", cmd]
            connectToNetworkProc.running = true
        }
    }

    function disconnectFromWifi(ssid) {
        if (ssid) {
            var escapedSsid = ssid.replace(/'/g, "'\\''")
            disconnectNetworkProc.command = ["bash", "-c", "nmcli connection down '" + escapedSsid + "'"]
            disconnectNetworkProc.running = true
        }
    }

    // Disconnect from network
    Process {
        id: disconnectNetworkProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                Qt.callLater(function() {
                    updateNetworkState()
                })
            }
        }
    }

    // Open network settings
    Process {
        id: openNetworkSettingsProc
        command: ["windoesnot-open-network"]
        running: false
    }

    // Content Container
    clip: true

    Rectangle {
        anchors.fill: parent
        color: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.93) : Qt.rgba(0.95, 0.95, 0.95, 0.97)
        border.color: darkMode ? "#3a3a3f" : "#c0c0c0"
        border.width: 1
        topLeftRadius: borderRadius
        topRightRadius: borderRadius
        bottomLeftRadius: 0
        bottomRightRadius: 0
    }

    Item {
        anchors.fill: parent
        anchors.margins: 15

        Column {
            id: mainContent
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 15

            // Header
            Text {
                text: Lang.get("network.title", uiLanguage)
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: darkMode ? "#ffffff" : "#000000"
                antialiasing: true
                renderType: Text.NativeRendering
            }

            Rectangle {
                width: parent.width
                height: 1
                color: darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // Network Type Buttons
            Row {
                width: parent.width
                spacing: 10

                // WiFi Button
                Rectangle {
                    width: (parent.width - 10) / 2
                    height: 50
                    radius: 8
                    color: darkMode
                        ? (wifiButtonMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4))
                        : (wifiButtonMouseArea.containsMouse ? Qt.rgba(0.85, 0.85, 0.85, 0.8) : Qt.rgba(0.88, 0.88, 0.88, 0.7))
                    border.width: networkPanel.wifiEnabled ? 2 : 1
                    border.color: networkPanel.wifiEnabled ? networkPanel.accentColor : (darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8))

                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                    Behavior on border.width { NumberAnimation { duration: 150 } }

                    Column {
                        anchors.centerIn: parent
                        spacing: 4

                        Image {
                            source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/network-wireless-connected-symbolic.svg")
                            width: 20
                            height: 20
                            smooth: true
                            anchors.horizontalCenter: parent.horizontalCenter

                            layer.enabled: !darkMode
                            layer.effect: MultiEffect {
                                colorization: 1.0
                                colorizationColor: "#333333"
                            }
                        }

                        Text {
                            text: networkPanel.wifiEnabled ? Lang.get("network.wifiOn", uiLanguage) : Lang.get("network.wifiOff", uiLanguage)
                            font.pixelSize: 11
                            color: networkPanel.wifiEnabled ? networkPanel.accentColor : (darkMode ? "#999999" : "#666666")
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }

                    MouseArea {
                        id: wifiButtonMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var newState = !networkPanel.wifiEnabled
                            toggleWifiProc.command = ["bash", "-c", "nmcli radio wifi " + (newState ? "on" : "off")]
                            toggleWifiProc.running = true
                            console.log("Toggle WiFi:", newState)
                        }
                    }
                }

                // Ethernet Button
                Rectangle {
                    width: (parent.width - 10) / 2
                    height: 50
                    radius: 8
                    color: darkMode
                        ? (ethernetButtonMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4))
                        : (ethernetButtonMouseArea.containsMouse ? Qt.rgba(0.85, 0.85, 0.85, 0.8) : Qt.rgba(0.88, 0.88, 0.88, 0.7))
                    border.width: networkPanel.connectionType === "ethernet" ? 2 : 1
                    border.color: networkPanel.connectionType === "ethernet" ? networkPanel.accentColor : (darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8))

                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                    Behavior on border.width { NumberAnimation { duration: 150 } }

                    Column {
                        anchors.centerIn: parent
                        spacing: 4

                        Image {
                            source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/network-idle-symbolic.svg")
                            width: 20
                            height: 20
                            smooth: true
                            anchors.horizontalCenter: parent.horizontalCenter

                            layer.enabled: !darkMode
                            layer.effect: MultiEffect {
                                colorization: 1.0
                                colorizationColor: "#333333"
                            }
                        }

                        Text {
                            text: networkPanel.connectionType === "ethernet" ? "Ethernet" : "Ethernet"
                            font.pixelSize: 11
                            color: networkPanel.connectionType === "ethernet" ? networkPanel.accentColor : (darkMode ? "#999999" : "#666666")
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }

                    MouseArea {
                        id: ethernetButtonMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            console.log("Ethernet status:", networkPanel.connectionType)
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // Current Connection
            Column {
                width: parent.width
                spacing: 10

                Text {
                    text: Lang.get("network.currentConnection", uiLanguage)
                    font.pixelSize: 13
                    color: darkMode ? "#999999" : "#666666"
                }

                Rectangle {
                    width: parent.width
                    height: 60
                    radius: 8
                    color: networkPanel.connectionType !== "none" ? Qt.rgba(networkPanel.accentColor.r, networkPanel.accentColor.g, networkPanel.accentColor.b, 0.2) : "#1f1f1f"
                    border.width: networkPanel.connectionType !== "none" ? 1 : 1
                    border.color: networkPanel.connectionType !== "none" ? networkPanel.accentColor : "#3a3a3a"

                    Behavior on color { ColorAnimation { duration: 150 } }

                    Row {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        Image {
                            source: {
                                if (networkPanel.connectionType === "wifi") {
                                    return Qt.resolvedUrl("../img/Win11-dark/status/symbolic/network-wireless-connected-symbolic.svg")
                                } else if (networkPanel.connectionType === "ethernet") {
                                    return Qt.resolvedUrl("../img/Win11-dark/status/symbolic/network-idle-symbolic.svg")
                                } else {
                                    return Qt.resolvedUrl("../img/Win11-dark/status/symbolic/network-offline-symbolic.svg")
                                }
                            }
                            width: 24
                            height: 24
                            smooth: true
                            anchors.verticalCenter: parent.verticalCenter

                            layer.enabled: !darkMode
                            layer.effect: MultiEffect {
                                colorization: 1.0
                                colorizationColor: "#333333"
                            }
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            width: parent.width - 48

                            Text {
                                text: networkPanel.currentConnection.length > 0 ? networkPanel.currentConnection : Lang.get("network.notConnected", uiLanguage)
                                font.pixelSize: 13
                                color: darkMode ? "#ffffff" : "#000000"
                                elide: Text.ElideRight
                                width: parent.width
                            }

                            Text {
                                text: {
                                    if (networkPanel.connectionType === "wifi") return Lang.get("network.wifiConnected", uiLanguage)
                                    if (networkPanel.connectionType === "ethernet") return Lang.get("network.ethernetConnected", uiLanguage)
                                    return Lang.get("network.noConnection", uiLanguage)
                                }
                                font.pixelSize: 11
                                color: networkPanel.connectionType !== "none" ? networkPanel.accentColor : (darkMode ? "#666666" : "#444444")
                            }
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // Password Dialog
            Column {
                width: parent.width
                spacing: 10
                visible: networkPanel.showPasswordDialog

                Text {
                    text: Lang.get("network.enterPassword", uiLanguage)
                    font.pixelSize: 13
                    color: darkMode ? "#ffffff" : "#000000"
                    font.weight: Font.DemiBold
                    antialiasing: true
                    renderType: Text.NativeRendering
                }

                Rectangle {
                    width: parent.width
                    height: networkPanel.connectionStatus !== "" ? 130 : 100
                    radius: 8
                    color: darkMode ? "#1a1a1a" : "#f0f0f0"
                    border.width: 1
                    border.color: {
                        if (networkPanel.connectionStatus === "success") return "#4CAF50"
                        if (networkPanel.connectionStatus === "failed") return "#F44336"
                        return networkPanel.accentColor
                    }

                    Behavior on height { NumberAnimation { duration: 200 } }
                    Behavior on border.color { ColorAnimation { duration: 200 } }

                    Column {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10

                        Row {
                            width: parent.width
                            spacing: 10

                            Text {
                                text: Lang.get("network.networkLabel", uiLanguage) + " " + networkPanel.selectedNetwork
                                font.pixelSize: 12
                                color: darkMode ? "#999999" : "#666666"
                                elide: Text.ElideRight
                                width: parent.width - statusIndicator.width - 10
                            }

                            // Status Indicator
                            Item {
                                id: statusIndicator
                                width: networkPanel.isConnecting || networkPanel.connectionStatus !== "" ? 20 : 0
                                height: 20
                                visible: width > 0

                                Behavior on width { NumberAnimation { duration: 200 } }

                                // Connecting spinner
                                Rectangle {
                                    visible: networkPanel.isConnecting
                                    width: 16
                                    height: 16
                                    radius: 8
                                    anchors.centerIn: parent
                                    color: "transparent"
                                    border.width: 2
                                    border.color: networkPanel.accentColor

                                    Rectangle {
                                        width: 4
                                        height: 4
                                        radius: 2
                                        color: networkPanel.accentColor
                                        x: 6
                                        y: 0

                                        RotationAnimation on rotation {
                                            loops: Animation.Infinite
                                            from: 0
                                            to: 360
                                            duration: 1000
                                            running: networkPanel.isConnecting
                                        }
                                    }
                                }

                                // Success checkmark
                                Text {
                                    visible: networkPanel.connectionStatus === "success"
                                    text: "✓"
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: "#4CAF50"
                                    anchors.centerIn: parent
                                }

                                // Failed X
                                Text {
                                    visible: networkPanel.connectionStatus === "failed"
                                    text: "✗"
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: "#F44336"
                                    anchors.centerIn: parent
                                }
                            }
                        }

                        // Status Message
                        Text {
                            visible: networkPanel.connectionStatus !== ""
                            text: {
                                if (networkPanel.connectionStatus === "success") return "✓ " + Lang.get("network.connectionSuccess", uiLanguage)
                                if (networkPanel.connectionStatus === "failed") return "✗ " + Lang.get("network.connectionFailed", uiLanguage)
                                return ""
                            }
                            font.pixelSize: 11
                            color: networkPanel.connectionStatus === "success" ? "#4CAF50" : "#F44336"
                            font.bold: true
                            width: parent.width
                        }

                        Rectangle {
                            width: parent.width
                            height: 32
                            radius: 6
                            color: darkMode ? "#2a2a2a" : "#ffffff"
                            border.width: passwordInput.activeFocus ? 1 : 0
                            border.color: networkPanel.accentColor

                            TextInput {
                                id: passwordInput
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                verticalAlignment: TextInput.AlignVCenter
                                font.pixelSize: 12
                                color: darkMode ? "#ffffff" : "#000000"
                                echoMode: TextInput.Password
                                selectByMouse: true

                                Keys.onReturnPressed: {
                                    if (text.length > 0) {
                                        networkPanel.connectWithPassword(text)
                                        text = ""
                                    }
                                }
                                Keys.onEscapePressed: {
                                    networkPanel.showPasswordDialog = false
                                    text = ""
                                }
                            }

                            Text {
                                visible: passwordInput.text.length === 0 && !passwordInput.activeFocus
                                text: Lang.get("network.password", uiLanguage)
                                font.pixelSize: 12
                                color: darkMode ? "#666666" : "#999999"
                                anchors.left: parent.left
                                anchors.leftMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Row {
                            width: parent.width
                            spacing: 8

                            Rectangle {
                                width: (parent.width - 8) / 2
                                height: 28
                                radius: 6
                                color: darkMode
                                    ? (cancelButtonMouseArea.containsMouse ? "#2a2a2a" : "#1f1f1f")
                                    : (cancelButtonMouseArea.containsMouse ? "#c0c0c0" : "#d0d0d0")
                                border.width: 1
                                border.color: darkMode ? "#3a3a3a" : "#a0a0a0"

                                Text {
                                    anchors.centerIn: parent
                                    text: Lang.get("common.cancel", uiLanguage)
                                    font.pixelSize: 11
                                    color: darkMode ? "#cccccc" : "#333333"
                                    antialiasing: true
                                    renderType: Text.NativeRendering
                                }

                                MouseArea {
                                    id: cancelButtonMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        networkPanel.showPasswordDialog = false
                                        passwordInput.text = ""
                                    }
                                }
                            }

                            Rectangle {
                                width: (parent.width - 8) / 2
                                height: 28
                                radius: 6
                                color: connectButtonMouseArea.containsMouse ? Qt.rgba(networkPanel.accentColor.r, networkPanel.accentColor.g, networkPanel.accentColor.b, 0.8) : networkPanel.accentColor
                                border.width: 0

                                Text {
                                    anchors.centerIn: parent
                                    text: Lang.get("network.connect", uiLanguage)
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: "#fff"
                                    antialiasing: true
                                    renderType: Text.NativeRendering
                                }

                                MouseArea {
                                    id: connectButtonMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: passwordInput.text.length > 0
                                    onClicked: {
                                        networkPanel.connectWithPassword(passwordInput.text)
                                        passwordInput.text = ""
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Available Networks
            Column {
                width: parent.width
                spacing: 10

                Text {
                    text: Lang.get("network.availableNetworks", uiLanguage)
                    font.pixelSize: 13
                    color: darkMode ? "#999999" : "#666666"
                }

                Rectangle {
                    width: parent.width
                    height: 130
                    radius: 8
                    color: darkMode ? Qt.rgba(0.1, 0.1, 0.1, 0.5) : Qt.rgba(0.9, 0.9, 0.9, 0.8)
                    border.width: 1
                    border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)
                    clip: true

                    ListView {
                        id: networkListView
                        anchors.fill: parent
                        anchors.margins: 5
                        spacing: 5
                        clip: true

                        model: networkPanel.availableNetworks

                        delegate: Rectangle {
                            width: networkListView.width
                            height: 45
                            radius: 6
                            color: {
                                if (modelData.active) return Qt.rgba(networkPanel.accentColor.r, networkPanel.accentColor.g, networkPanel.accentColor.b, 0.3)
                                return networkMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4)
                            }
                            border.width: modelData.active ? 1 : 0
                            border.color: networkPanel.accentColor

                            Behavior on color { ColorAnimation { duration: 150 } }

                            Item {
                                anchors.fill: parent
                                anchors.margins: 12

                                Row {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 12

                                    Image {
                                        source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/network-wireless-signal-good-symbolic.svg")
                                        width: 18
                                        height: 18
                                        smooth: true
                                        anchors.verticalCenter: parent.verticalCenter

                                        layer.enabled: !darkMode
                                        layer.effect: MultiEffect {
                                            colorization: 1.0
                                            colorizationColor: "#333333"
                                        }
                                    }

                                    Column {
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 2
                                        width: parent.width - 18 - 12 - (modelData.active ? 70 + 12 : (modelData.secured ? 14 + 12 : 0))

                                        Text {
                                            text: modelData.ssid
                                            font.pixelSize: 13
                                            color: modelData.active ? (darkMode ? "#ffffff" : "#000000") : (darkMode ? "#cccccc" : "#333333")
                                            elide: Text.ElideRight
                                            width: parent.width
                                        }

                                        Text {
                                            visible: modelData.active
                                            text: Lang.get("network.connected", uiLanguage)
                                            font.pixelSize: 10
                                            color: networkPanel.accentColor
                                        }
                                    }

                                    Item {
                                        width: modelData.active ? 70 : (modelData.secured ? 14 : 0)
                                        height: 24
                                        anchors.verticalCenter: parent.verticalCenter

                                        // Disconnect button for active connection
                                        Rectangle {
                                            visible: modelData.active
                                            anchors.fill: parent
                                            radius: 4
                                            color: darkMode
                                                ? (disconnectMouseArea.containsMouse ? "#5a5a5a" : "#4a4a4a")
                                                : (disconnectMouseArea.containsMouse ? "#c0c0c0" : "#d0d0d0")

                                            Text {
                                                anchors.centerIn: parent
                                                text: Lang.get("network.disconnect", uiLanguage)
                                                font.pixelSize: 10
                                                color: darkMode ? "#cccccc" : "#333333"
                                                font.bold: true
                                                antialiasing: true
                                                renderType: Text.NativeRendering
                                            }

                                            MouseArea {
                                                id: disconnectMouseArea
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    console.log("Disconnect from:", modelData.ssid)
                                                    networkPanel.disconnectFromWifi(modelData.ssid)
                                                    mouse.accepted = true
                                                }
                                            }
                                        }

                                        // Lock icon for secured networks (only when not active)
                                        Image {
                                            visible: modelData.secured && !modelData.active
                                            source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/channel-secure-symbolic.svg")
                                            width: 14
                                            height: 14
                                            smooth: true
                                            anchors.centerIn: parent

                                            layer.enabled: !darkMode
                                            layer.effect: MultiEffect {
                                                colorization: 1.0
                                                colorizationColor: "#333333"
                                            }
                                        }
                                    }
                                }
                            }

                            MouseArea {
                                id: networkMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: modelData.active ? Qt.ArrowCursor : Qt.PointingHandCursor
                                enabled: !modelData.active
                                onClicked: {
                                    console.log("Connect to:", modelData.ssid, "Secured:", modelData.secured, "Active:", modelData.active)
                                    networkPanel.connectToWifi(modelData.ssid, modelData.secured, modelData.active)
                                }
                            }
                        }
                    }

                    // Placeholder when no networks
                    Text {
                        anchors.centerIn: parent
                        visible: networkPanel.availableNetworks.length === 0
                        text: networkPanel.wifiEnabled ? Lang.get("network.noKnownNetworks", uiLanguage) : Lang.get("network.wifiDisabled", uiLanguage)
                        font.pixelSize: 13
                        color: darkMode ? "#666666" : "#444444"
                    }
                }
            }
        }

        // Settings Button - am unteren Rand verankert
        Rectangle {
            id: settingsButton
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 40
            radius: 8
            color: darkMode
                ? (netSettingsMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4))
                : (netSettingsMouseArea.containsMouse ? Qt.rgba(0.85, 0.85, 0.85, 0.8) : Qt.rgba(0.88, 0.88, 0.88, 0.7))
            border.width: 1
            border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)

            Behavior on color { ColorAnimation { duration: 150 } }

            Row {
                anchors.centerIn: parent
                spacing: 8

                Image {
                    source: Qt.resolvedUrl("../img/Win11-dark/actions/symbolic/settings-symbolic.svg")
                    width: 16
                    height: 16
                    smooth: true
                    anchors.verticalCenter: parent.verticalCenter

                    layer.enabled: !darkMode
                    layer.effect: MultiEffect {
                        colorization: 1.0
                        colorizationColor: "#333333"
                    }
                }

                Text {
                    text: Lang.get("network.settings", uiLanguage)
                    font.pixelSize: 12
                    color: darkMode ? "#cccccc" : "#333333"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: netSettingsMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: openNetworkSettingsProc.startDetached()
            }
        }
    }
}
