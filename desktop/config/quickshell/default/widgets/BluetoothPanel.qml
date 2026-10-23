import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: bluetoothPanel
    width: 320
    height: 400

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12  // Default value, wird von shell.qml gebunden
    property bool windowVisible: false
    property bool darkMode: true  // Wird von shell.qml gesetzt
    property string uiLanguage: "de"  // Bound from shell.qml
    property bool bluetoothEnabled: false
    property var allDevices: []  // Combined list of paired and available devices
    property bool isScanning: false

    property bool initialized: false

    Component.onCompleted: {
        // Load initial data once at startup
        updateBluetoothState()
        initialized = true
    }

    // Update when panel becomes visible
    onVisibleChanged: {
        if (visible) {
            updateBluetoothState()
        }
    }

    Timer {
        interval: 3000
        running: bluetoothPanel.windowVisible  // Only run when panel is visible
        repeat: true
        onTriggered: updateBluetoothState()
    }

    function updateBluetoothState() {
        getBluetoothPowerProc.running = true
        getAllDevicesProc.running = true
    }

    // Get Bluetooth power status
    Process {
        id: getBluetoothPowerProc
        command: ["bash", "-c", "bluetoothctl show | grep 'Powered:' | awk '{print $2}'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                bluetoothPanel.bluetoothEnabled = (this.text.trim() === "yes")
            }
        }
    }

    // Toggle Bluetooth power
    Process {
        id: toggleBluetoothProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                Qt.callLater(function() {
                    getBluetoothPowerProc.running = true
                })
            }
        }
    }

    // Get all devices (paired and discovered) with connection status
    Process {
        id: getAllDevicesProc
        command: ["bash", "-c", "bluetoothctl devices | while read -r line; do mac=$(echo \"$line\" | awk '{print $2}'); name=$(echo \"$line\" | cut -d' ' -f3-); [ -z \"$mac\" ] && continue; info=$(bluetoothctl info \"$mac\" 2>/dev/null); paired=$(echo \"$info\" | grep 'Paired:' | awk '{print $2}'); connected=$(echo \"$info\" | grep 'Connected:' | awk '{print $2}'); battery_line=$(echo \"$info\" | grep 'Battery Percentage:'); battery=''; if [ -n \"$battery_line\" ]; then battery=$(echo \"$battery_line\" | grep -oP '\\(\\K\\d+(?=\\))'); fi; icon=$(echo \"$info\" | grep 'Icon:' | awk '{print $2}'); class=$(echo \"$info\" | grep 'Class:' | awk '{print $2}'); echo \"$mac|$name|$paired|$connected|$battery|$icon|$class\"; done"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.trim().split('\n')
                var devices = []
                var deviceNames = {}  // Track names to avoid duplicates

                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].length > 0) {
                        var parts = lines[i].split('|')
                        if (parts.length >= 4) {
                            var deviceMac = parts[0].trim()
                            var deviceName = parts[1].trim()
                            var isPaired = parts[2].trim() === "yes"
                            var isConnected = parts[3].trim() === "yes"
                            var battery = parts.length > 4 && parts[4].trim().length > 0 ? parseInt(parts[4].trim()) : -1
                            var deviceIcon = "img/Win11-dark/devices/symbolic/audio-headphones-symbolic.svg"
                            var iconType = parts.length > 5 ? parts[5].trim() : ""
                            var deviceClass = parts.length > 6 ? parts[6].trim() : ""

                            console.log("Raw:", deviceMac, "|", deviceName, "| Paired:", isPaired, "| Connected:", isConnected, "| Icon:", iconType)

                            // Filter: Skip entries without valid MAC address
                            if (!deviceMac || deviceMac.length < 10 || deviceMac.indexOf(':') === -1) {
                                console.log("Skipping invalid MAC:", deviceMac, deviceName)
                                continue
                            }

                            // Filter: Skip entries where name looks like an icon type
                            if (deviceName === "audio-headset" || deviceName === "audio-card" ||
                                deviceName === "input-keyboard" || deviceName === "input-mouse" ||
                                deviceName === "input-gaming" || deviceName.indexOf("audio-") === 0 ||
                                deviceName.indexOf("input-") === 0) {
                                console.log("Skipping icon-as-name entry:", deviceName)
                                continue
                            }

                            // Filter: Skip empty names
                            if (!deviceName || deviceName.length === 0) {
                                console.log("Skipping empty name")
                                continue
                            }

                            // Check for duplicate names
                            var nameLower = deviceName.toLowerCase()
                            if (deviceNames[nameLower]) {
                                console.log("Skipping duplicate:", deviceName)
                                continue
                            }
                            deviceNames[nameLower] = true

                            // Icon basierend auf Gerätetyp
                            if (iconType === "audio-headset" || iconType === "audio-headphones") {
                                deviceIcon = "img/Win11-dark/devices/symbolic/audio-headphones-symbolic.svg"
                            } else if (iconType === "audio-card" || iconType === "audio-speaker") {
                                deviceIcon = "img/Win11-dark/status/symbolic/audio-volume-high-symbolic.svg"
                            } else if (iconType === "input-keyboard") {
                                deviceIcon = "img/Win11-dark/devices/symbolic/input-keyboard-symbolic.svg"
                            } else if (iconType === "input-mouse") {
                                deviceIcon = "img/Win11-dark/devices/symbolic/input-mouse-symbolic.svg"
                            } else if (iconType === "input-gaming") {
                                deviceIcon = "img/Win11-dark/devices/symbolic/input-gaming-symbolic.svg"
                            } else if (iconType === "phone" || iconType === "smartphone" || iconType === "modem") {
                                deviceIcon = "img/Win11-dark/devices/symbolic/phone-symbolic.svg"
                            } else if (iconType === "computer") {
                                deviceIcon = "img/Win11-dark/devices/symbolic/computer-symbolic.svg"
                            } else {
                                // Fallback: versuche anhand der Device Class zu erkennen
                                // Class Format: 0x<major><minor>
                                // Major class 0x05 = Peripheral (Keyboard, Mouse, Gamepad)
                                // Major class 0x04 = Audio/Video
                                if (deviceClass.indexOf("0x0508") >= 0 || deviceClass.indexOf("0x0540") >= 0) {
                                    // Gamepad/Joystick
                                    deviceIcon = "img/Win11-dark/devices/symbolic/input-gaming-symbolic.svg"
                                } else if (deviceClass.indexOf("0x0580") >= 0) {
                                    // Keyboard
                                    deviceIcon = "img/Win11-dark/devices/symbolic/input-keyboard-symbolic.svg"
                                } else if (deviceClass.indexOf("0x05c0") >= 0) {
                                    // Mouse
                                    deviceIcon = "img/Win11-dark/devices/symbolic/input-mouse-symbolic.svg"
                                } else if (deviceClass.indexOf("0x04") === 2) {
                                    // Audio device
                                    deviceIcon = "img/Win11-dark/devices/symbolic/audio-headphones-symbolic.svg"
                                }
                            }

                            devices.push({
                                mac: deviceMac,
                                name: deviceName,
                                paired: isPaired,
                                connected: isConnected,
                                battery: battery,
                                icon: deviceIcon
                            })
                        }
                    }
                }

                // Sort: Paired & connected first, then paired, then available
                devices.sort(function(a, b) {
                    if (a.paired && a.connected && !(b.paired && b.connected)) return -1
                    if (!(a.paired && a.connected) && b.paired && b.connected) return 1
                    if (a.paired && !b.paired) return -1
                    if (!a.paired && b.paired) return 1
                    return 0
                })

                bluetoothPanel.allDevices = devices
                console.log("Bluetooth devices loaded:", devices.length, "(paired + available)")
            }
        }
    }

    // Connect/Disconnect device
    Process {
        id: toggleDeviceConnectionProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                Qt.callLater(function() {
                    getAllDevicesProc.running = true
                })
                // Start timer to auto-close blueman notifications
                closeBluemanTimer.restart()
            }
        }
    }

    // Timer to auto-close blueman notification windows
    Timer {
        id: closeBluemanTimer
        interval: 3000
        running: false
        repeat: false
        onTriggered: {
            closeBluemanProc.running = true
        }
    }

    // Close blueman notification windows
    Process {
        id: closeBluemanProc
        command: ["bash", "-c", "windoesnot-hyprctl clients -j | jq -r '.[] | select(.class==\"blueman-applet\" or .class==\"blueman-manager\" or .class==\"Blueman-manager\" or (.title | contains(\"Bluetooth\"))) | .address' | while read addr; do windoesnot-hyprctl dispatch closewindow address:$addr; done"]
        running: false
    }

    // Start Python scan script that properly handles bluetoothctl
    Process {
        id: startScanProc
        command: ["python3", Qt.resolvedUrl("../bt_scan.py").toString().replace("file://", "")]
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                // Process all output at the end
                var lines = this.text.trim().split('\n')
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim()
                    if (line.startsWith('FOUND|')) {
                        // Format: FOUND|MAC|NAME
                        var parts = line.split('|')
                        if (parts.length >= 3) {
                            var mac = parts[1]
                            var name = parts[2]
                            addScannedDevice(mac, name)
                        }
                    }
                }
                console.log("Scan completed, processed", lines.length, "lines")
            }
        }

        onRunningChanged: {
            if (running) {
                bluetoothPanel.isScanning = true
                console.log("Python scan script started")
            } else {
                bluetoothPanel.isScanning = false
                console.log("Python scan script finished")
            }
        }
    }

    function addScannedDevice(mac, name) {
        // Check if device already exists
        for (var i = 0; i < bluetoothPanel.allDevices.length; i++) {
            if (bluetoothPanel.allDevices[i].mac === mac) {
                return // Already have this device
            }
        }

        // Add new device
        var newDevice = {
            mac: mac,
            name: name || mac,
            paired: false,
            connected: false,
            battery: -1,
            icon: "img/Win11-dark/devices/symbolic/bluetooth-symbolic.svg"
        }

        var updated = bluetoothPanel.allDevices.slice()
        updated.push(newDevice)
        bluetoothPanel.allDevices = updated

        console.log("Added scanned device:", name, "-", mac)
    }

    // Timer to periodically refresh device list during scan
    Timer {
        id: scanTimer
        interval: 5000
        running: bluetoothPanel.isScanning
        repeat: true
        onTriggered: {
            console.log("Refreshing device list during scan...")
            // Refresh known devices to check if any scanned devices have been paired
            getAllDevicesProc.running = true
        }
    }


    // Pair with device
    Process {
        id: pairDeviceProc
        command: ["bash", "-c", ""]
        running: false
        onRunningChanged: {
            if (!running) {
                Qt.callLater(function() {
                    getAllDevicesProc.running = true
                })
                // Start timer to auto-close blueman notifications
                closeBluemanTimer.restart()
            }
        }
    }

    // Stop scan process
    Process {
        id: stopScanProc
        command: ["bash", "-c", "pkill -f 'python3.*bt_scan.py'; bluetoothctl scan off"]
        running: false
        onRunningChanged: {
            if (!running) {
                bluetoothPanel.isScanning = false
                console.log("Scan stopped")
            }
        }
    }

    function startScan() {
        if (!bluetoothPanel.isScanning) {
            console.log("Starting scan...")
            startScanProc.running = true
        }
    }

    function stopScan() {
        if (bluetoothPanel.isScanning) {
            console.log("Stopping scan...")
            stopScanProc.running = true
        }
    }

    function pairDevice(mac) {
        console.log("Pairing with device:", mac)
        pairDeviceProc.command = ["bash", "-c", "bluetoothctl pair " + mac + " && bluetoothctl trust " + mac + " && bluetoothctl connect " + mac]
        pairDeviceProc.running = true
    }

    // Open blueman-manager
    Process {
        id: openBluemanProc
        command: ["bash", "-c", "blueman-manager & disown"]
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
            anchors.bottom: quickActionsRow.top
            anchors.bottomMargin: 15
            spacing: 15

            // Header
            Item {
                width: parent.width
                height: 30

                Text {
                    text: Lang.get("bluetooth.title", uiLanguage)
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: darkMode ? "#ffffff" : "#000000"
                    antialiasing: true
                    renderType: Text.NativeRendering
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                }

                // Bluetooth Toggle
                Rectangle {
                    width: 50
                    height: 28
                    radius: 14
                    color: bluetoothPanel.bluetoothEnabled ? bluetoothPanel.accentColor : "#3a3a3a"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter

                    Behavior on color { ColorAnimation { duration: 150 } }

                    Rectangle {
                        width: 22
                        height: 22
                        radius: 11
                        color: "#fff"
                        x: bluetoothPanel.bluetoothEnabled ? (parent.width - width - 3) : 3
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on x { NumberAnimation { duration: 150 } }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var newState = !bluetoothPanel.bluetoothEnabled
                            toggleBluetoothProc.command = ["bash", "-c", "bluetoothctl power " + (newState ? "on" : "off")]
                            toggleBluetoothProc.running = true
                            console.log("Toggle Bluetooth:", newState)
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // All Devices (Paired + Available)
            Column {
                width: parent.width
                spacing: 10

                Text {
                    text: Lang.get("bluetooth.devices", uiLanguage)
                    font.pixelSize: 13
                    color: darkMode ? "#999999" : "#666666"
                }

                Rectangle {
                    width: parent.width
                    height: 280
                    radius: 8
                    color: darkMode ? Qt.rgba(0.1, 0.1, 0.1, 0.5) : Qt.rgba(0.9, 0.9, 0.9, 0.8)
                    border.width: 1
                    border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)
                    clip: true

                    ListView {
                        id: deviceListView
                        anchors.fill: parent
                        anchors.margins: 5
                        spacing: 5
                        clip: true

                        model: bluetoothPanel.allDevices

                        delegate: Rectangle {
                            width: deviceListView.width
                            height: 60
                            radius: 6
                            color: {
                                if (modelData.connected) return Qt.rgba(bluetoothPanel.accentColor.r, bluetoothPanel.accentColor.g, bluetoothPanel.accentColor.b, 0.3)
                                return deviceMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4)
                            }
                            border.width: modelData.connected ? 1 : 0
                            border.color: bluetoothPanel.accentColor

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
                                        source: Qt.resolvedUrl("../" + modelData.icon)
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
                                        width: parent.width - 24 - 12 - 80 - 12

                                        Text {
                                            text: modelData.name
                                            font.pixelSize: 13
                                            color: modelData.connected ? (darkMode ? "#ffffff" : "#000000") : (darkMode ? "#cccccc" : "#333333")
                                            elide: Text.ElideRight
                                            width: parent.width
                                        }

                                        Text {
                                            text: {
                                                if (modelData.connected) {
                                                    if (modelData.battery >= 0) {
                                                        return Lang.get("bluetooth.connected", uiLanguage) + " • " + modelData.battery + "%"
                                                    }
                                                    return Lang.get("bluetooth.connected", uiLanguage)
                                                }
                                                if (modelData.paired) {
                                                    return Lang.get("bluetooth.paired", uiLanguage)
                                                }
                                                return Lang.get("bluetooth.available", uiLanguage)
                                            }
                                            font.pixelSize: 11
                                            color: modelData.connected ? bluetoothPanel.accentColor : (modelData.paired ? (darkMode ? "#999999" : "#666666") : (darkMode ? "#444444" : "#666666"))
                                        }
                                    }

                                    Item {
                                        width: 80
                                        height: 24
                                        anchors.verticalCenter: parent.verticalCenter

                                        // Disconnect button for connected device
                                        Rectangle {
                                            visible: modelData.connected
                                            anchors.fill: parent
                                            radius: 4
                                            color: darkMode
                                                ? (disconnectMouseArea.containsMouse ? "#5a5a5a" : "#4a4a4a")
                                                : (disconnectMouseArea.containsMouse ? "#c0c0c0" : "#d0d0d0")

                                            Text {
                                                anchors.centerIn: parent
                                                text: Lang.get("bluetooth.disconnect", uiLanguage)
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
                                                    console.log("Disconnect device:", modelData.mac)
                                                    toggleDeviceConnectionProc.command = ["bash", "-c", "bluetoothctl disconnect " + modelData.mac]
                                                    toggleDeviceConnectionProc.running = true
                                                    mouse.accepted = true
                                                }
                                            }
                                        }

                                        // Connect button for paired but disconnected device
                                        Rectangle {
                                            visible: modelData.paired && !modelData.connected
                                            anchors.fill: parent
                                            radius: 4
                                            color: connectMouseArea.containsMouse ? Qt.rgba(bluetoothPanel.accentColor.r, bluetoothPanel.accentColor.g, bluetoothPanel.accentColor.b, 0.8) : bluetoothPanel.accentColor

                                            Text {
                                                anchors.centerIn: parent
                                                text: Lang.get("bluetooth.connect", uiLanguage)
                                                font.pixelSize: 10
                                                color: "#fff"
                                                font.bold: true
                                                antialiasing: true
                                                renderType: Text.NativeRendering
                                            }

                                            MouseArea {
                                                id: connectMouseArea
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    console.log("Connect device:", modelData.mac)
                                                    toggleDeviceConnectionProc.command = ["bash", "-c", "bluetoothctl connect " + modelData.mac]
                                                    toggleDeviceConnectionProc.running = true
                                                    mouse.accepted = true
                                                }
                                            }
                                        }

                                        // Pair button for available (not paired) device
                                        Rectangle {
                                            visible: !modelData.paired
                                            anchors.fill: parent
                                            radius: 4
                                            color: pairButtonMouseArea.containsMouse ? Qt.rgba(bluetoothPanel.accentColor.r, bluetoothPanel.accentColor.g, bluetoothPanel.accentColor.b, 0.8) : bluetoothPanel.accentColor

                                            Text {
                                                anchors.centerIn: parent
                                                text: Lang.get("bluetooth.pair", uiLanguage)
                                                font.pixelSize: 10
                                                color: "#fff"
                                                font.bold: true
                                                antialiasing: true
                                                renderType: Text.NativeRendering
                                            }

                                            MouseArea {
                                                id: pairButtonMouseArea
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    bluetoothPanel.pairDevice(modelData.mac)
                                                    mouse.accepted = true
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            MouseArea {
                                id: deviceMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.ArrowCursor
                                enabled: false
                            }
                        }
                    }

                    // Placeholder when no devices
                    Text {
                        anchors.centerIn: parent
                        visible: bluetoothPanel.allDevices.length === 0
                        text: Lang.get("bluetooth.noDevices", uiLanguage)
                        font.pixelSize: 13
                        color: darkMode ? "#666666" : "#444444"
                    }
                }
            }

        }

        // Quick Actions - am unteren Rand verankert
        Row {
            id: quickActionsRow
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: 10

            // Scan Button
            Rectangle {
                width: (parent.width - 10) / 2
                height: 40
                radius: 8
                color: {
                    if (bluetoothPanel.isScanning) {
                        return scanButtonMouseArea.containsMouse ? Qt.rgba(bluetoothPanel.accentColor.r, bluetoothPanel.accentColor.g, bluetoothPanel.accentColor.b, 0.8) : bluetoothPanel.accentColor
                    } else {
                        return darkMode
                            ? (scanButtonMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4))
                            : (scanButtonMouseArea.containsMouse ? Qt.rgba(0.85, 0.85, 0.85, 0.8) : Qt.rgba(0.88, 0.88, 0.88, 0.7))
                    }
                }
                border.width: bluetoothPanel.isScanning ? 0 : 1
                border.color: darkMode ? Qt.rgba(0.23, 0.23, 0.23, 0.5) : Qt.rgba(0.7, 0.7, 0.7, 0.8)

                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on border.width { NumberAnimation { duration: 150 } }

                Row {
                    anchors.centerIn: parent
                    spacing: 8

                    Image {
                        source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/blueberry-tray-symbolic.svg")
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
                        text: bluetoothPanel.isScanning ? Lang.get("bluetooth.stopScan", uiLanguage) : Lang.get("bluetooth.searchDevices", uiLanguage)
                        font.pixelSize: 12
                        font.bold: bluetoothPanel.isScanning
                        color: bluetoothPanel.isScanning ? (darkMode ? "#ffffff" : "#000000") : (darkMode ? "#cccccc" : "#333333")
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: scanButtonMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (bluetoothPanel.isScanning) {
                            bluetoothPanel.stopScan()
                        } else {
                            bluetoothPanel.startScan()
                        }
                    }
                }
            }

            // Settings Button
            Rectangle {
                width: (parent.width - 10) / 2
                height: 40
                radius: 8
                color: darkMode
                    ? (settingsMouseArea.containsMouse ? Qt.rgba(0.16, 0.16, 0.16, 0.6) : Qt.rgba(0.12, 0.12, 0.12, 0.4))
                    : (settingsMouseArea.containsMouse ? Qt.rgba(0.85, 0.85, 0.85, 0.8) : Qt.rgba(0.88, 0.88, 0.88, 0.7))
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
                        text: Lang.get("common.settings", uiLanguage)
                        font.pixelSize: 12
                        color: darkMode ? "#cccccc" : "#333333"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: settingsMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: openBluemanProc.running = true
                }
            }
        }
    }
}
