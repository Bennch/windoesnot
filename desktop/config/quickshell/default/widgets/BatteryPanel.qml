import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: batteryPanel
    width: 320
    height: 360

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property bool windowVisible: false
    property bool darkMode: true
    property string uiLanguage: "de"

    property bool hasBattery: false
    property string percentage: "0"
    property string state: ""
    property string timeToEmpty: ""
    property string timeToFull: ""
    property var profiles: []
    property string currentProfile: ""
    property bool profilesAvailable: false
    property bool profileBusy: false

    property bool hasBrightness: false
    property int brightness: 0
    // Desktops with no laptop backlight (brightnessctl finds nothing) fall
    // back to DDC/CI on the first detected external monitor.
    property bool usesDdc: false
    property string ddcDisplay: ""
    property bool ddcProbed: false

    // Eye-comfort / blue-light filter. State is just "is hyprsunset running
    // right now" -- no separate persisted setting, so a crashed/restarted
    // Quickshell can't disagree with reality.
    property bool hasNightLight: false
    property bool nightLightEnabled: false

    function tr(key) { return Lang.get(key, uiLanguage) }

    function batteryStateLabel(value) {
        var key = ({charging: "power.stateCharging", discharging: "power.stateDischarging",
            "fully-charged": "power.stateFull", "pending-charge": "power.stateCharging",
            "pending-discharge": "power.stateDischarging"})[value]
        return key ? tr(key) : (value || tr("power.stateUnknown"))
    }

    function refresh() {
        statusProc.running = true
        if (usesDdc) { ddcGetProc.running = true } else { brightnessProc.running = true }
        nightLightStatusProc.running = true
    }

    Component.onCompleted: refresh()
    onVisibleChanged: if (visible) refresh()

    Timer {
        interval: 10000
        running: batteryPanel.windowVisible
        repeat: true
        onTriggered: batteryPanel.refresh()
    }

    Process {
        id: statusProc
        command: ["/usr/bin/python3", "-I", "/usr/lib/windoesnot/system_tools.py", "power-status", "{}"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(this.text)
                    batteryPanel.hasBattery = !!data.battery
                    if (data.battery) {
                        batteryPanel.percentage = data.battery.percentage || "0"
                        batteryPanel.state = data.battery.state || ""
                        batteryPanel.timeToEmpty = data.battery.timeToEmpty || ""
                        batteryPanel.timeToFull = data.battery.timeToFull || ""
                    }
                    batteryPanel.profiles = data.profiles || []
                    batteryPanel.currentProfile = data.currentProfile || ""
                    batteryPanel.profilesAvailable = !!data.profilesAvailable
                } catch (error) {}
            }
        }
    }

    Process {
        id: profileProc
        running: false
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onExited: batteryPanel.refresh()
    }

    function setProfile(name) {
        if (profileBusy) return
        profileBusy = true
        profileProc.command = ["/usr/bin/powerprofilesctl", "set", name]
        profileProc.running = true
        profileBusy = false
    }

    Process {
        id: brightnessProc
        command: ["bash", "-c", "brightnessctl -c backlight -m 2>/dev/null"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var line = this.text.trim()
                var parts = line.split(",")
                if (parts.length >= 4) {
                    batteryPanel.hasBrightness = true
                    batteryPanel.brightness = parseInt(parts[3]) || 0
                } else if (!batteryPanel.ddcProbed) {
                    batteryPanel.ddcProbed = true
                    ddcDetectProc.running = true
                } else {
                    batteryPanel.hasBrightness = false
                }
            }
        }
    }

    // No backlight device (desktop PC, external monitors): try the first
    // DDC/CI-capable display instead. One-off probe, not repeated on every
    // refresh -- ddcutil is slow (seconds, not milliseconds).
    Process {
        id: ddcDetectProc
        command: ["bash", "-c", "command -v ddcutil >/dev/null 2>&1 && ddcutil detect --brief 2>/dev/null | sed -n 's/^Display \\([0-9]\\+\\)/\\1/p' | head -1"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var display = this.text.trim()
                if (display) {
                    batteryPanel.usesDdc = true
                    batteryPanel.ddcDisplay = display
                    ddcGetProc.command = ["bash", "-c", "ddcutil getvcp 10 --display " + display + " 2>/dev/null"]
                    ddcGetProc.running = true
                } else {
                    batteryPanel.hasBrightness = false
                }
            }
        }
    }

    Process {
        id: ddcGetProc
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var match = this.text.match(/current value\s*=\s*(\d+)/)
                if (match) {
                    batteryPanel.hasBrightness = true
                    batteryPanel.brightness = parseInt(match[1])
                } else {
                    batteryPanel.hasBrightness = false
                }
            }
        }
    }

    Process {
        id: setBrightnessProc
        running: false
    }

    // Dragging the slider fires setBrightness continuously; ddcutil's I2C
    // writes take noticeably longer than brightnessctl, so only the DDC path
    // gets debounced -- brightnessctl stays as responsive as before.
    Timer {
        id: ddcWriteDebounce
        interval: 150
        onTriggered: setBrightnessProc.running = true
    }

    function setBrightness(value) {
        brightness = Math.max(1, Math.min(100, value))
        if (usesDdc) {
            setBrightnessProc.command = ["bash", "-c", "ddcutil setvcp 10 " + brightness + " --display " + ddcDisplay + " --noverify 2>/dev/null"]
            ddcWriteDebounce.restart()
        } else {
            setBrightnessProc.command = ["bash", "-c", "brightnessctl -c backlight set " + brightness + "%"]
            setBrightnessProc.running = true
        }
    }

    Process {
        id: nightLightStatusProc
        command: ["bash", "-c", "command -v hyprsunset >/dev/null 2>&1 && echo has; pgrep -x hyprsunset >/dev/null 2>&1 && echo on"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                batteryPanel.hasNightLight = this.text.indexOf("has") !== -1
                batteryPanel.nightLightEnabled = this.text.indexOf("on") !== -1
            }
        }
    }

    Process {
        id: nightLightToggleProc
        running: false
        onExited: nightLightStatusProc.running = true
    }

    function toggleNightLight() {
        nightLightToggleProc.command = nightLightEnabled
            ? ["bash", "-c", "pkill -x hyprsunset"]
            : ["bash", "-c", "setsid hyprsunset -t 4000 >/dev/null 2>&1 &"]
        nightLightToggleProc.running = true
    }

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
            width: parent.width
            spacing: 15

            Text {
                text: Lang.get("nav.power", uiLanguage)
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

            // Battery readout
            Column {
                width: parent.width
                spacing: 4
                visible: batteryPanel.hasBattery

                Text {
                    text: batteryPanel.percentage + "%"
                    font.pixelSize: 26
                    font.bold: true
                    color: darkMode ? "#ffffff" : "#000000"
                }
                Text {
                    text: batteryPanel.batteryStateLabel(batteryPanel.state)
                    font.pixelSize: 13
                    color: darkMode ? "#999999" : "#666666"
                }
                Text {
                    readonly property string remaining: batteryPanel.state === "charging" && batteryPanel.timeToFull
                        ? batteryPanel.tr("power.timeToFull") + " " + batteryPanel.timeToFull
                        : (batteryPanel.timeToEmpty ? batteryPanel.tr("power.timeToEmpty") + " " + batteryPanel.timeToEmpty : "")
                    visible: remaining.length > 0
                    text: remaining
                    font.pixelSize: 12
                    color: darkMode ? "#999999" : "#666666"
                }
            }

            Text {
                visible: !batteryPanel.hasBattery
                width: parent.width
                wrapMode: Text.WordWrap
                text: batteryPanel.tr("power.noBattery")
                font.pixelSize: 13
                color: darkMode ? "#999999" : "#666666"
            }

            // Power profile
            Column {
                width: parent.width
                spacing: 8
                visible: batteryPanel.profilesAvailable

                Text {
                    text: batteryPanel.tr("power.profile")
                    font.pixelSize: 13
                    color: darkMode ? "#999999" : "#666666"
                }

                Row {
                    spacing: 8
                    Repeater {
                        model: batteryPanel.profiles
                        delegate: Rectangle {
                            required property string modelData
                            readonly property bool active: batteryPanel.currentProfile === modelData
                            width: 92
                            height: 30
                            radius: 6
                            color: active ? batteryPanel.accentColor : (darkMode ? "#2a2a2a" : "#f0f0f0")
                            border.width: 1
                            border.color: darkMode ? "#3a3a3a" : "#d0d0d0"
                            Behavior on color { ColorAnimation { duration: 150 } }
                            Text {
                                anchors.centerIn: parent
                                text: batteryPanel.tr("power.profile." + modelData)
                                color: active ? "#ffffff" : (darkMode ? "#ffffff" : "#1a1a1a")
                                font.pixelSize: 11
                                elide: Text.ElideRight
                                width: parent.width - 8
                                horizontalAlignment: Text.AlignHCenter
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: batteryPanel.setProfile(modelData)
                            }
                        }
                    }
                }
            }

            // Brightness
            Column {
                width: parent.width
                spacing: 10
                visible: batteryPanel.hasBrightness

                Row {
                    width: parent.width
                    spacing: 10

                    Image {
                        source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/display-brightness-symbolic.svg")
                        width: 20; height: 20
                        smooth: true
                        layer.enabled: !darkMode
                        layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                    }
                    Text {
                        id: brightnessLabel
                        text: batteryPanel.tr("power.brightness")
                        font.pixelSize: 14
                        color: darkMode ? "#cccccc" : "#333333"
                    }
                    Item { width: parent.width - brightnessLabel.width - brightnessPercent.width - 20 - 30; height: 1 }
                    Text {
                        id: brightnessPercent
                        text: batteryPanel.brightness + "%"
                        font.pixelSize: 13
                        color: darkMode ? "#999999" : "#666666"
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 8
                    radius: 4
                    color: darkMode ? "#2a2a2a" : "#d0d0d0"

                    Rectangle {
                        width: parent.width * (batteryPanel.brightness / 100)
                        height: parent.height
                        radius: 4
                        color: batteryPanel.accentColor
                    }

                    MouseArea {
                        anchors.fill: parent
                        onPositionChanged: function(mouse) {
                            if (pressed) batteryPanel.setBrightness(Math.round((mouse.x / parent.width) * 100))
                        }
                        onClicked: function(mouse) {
                            batteryPanel.setBrightness(Math.round((mouse.x / parent.width) * 100))
                        }
                    }
                }
            }

            // Eye comfort / night light
            Row {
                width: parent.width
                spacing: 10
                visible: batteryPanel.hasNightLight

                Image {
                    source: Qt.resolvedUrl("../img/Win11-dark/status/symbolic/weather-clear-night-symbolic.svg")
                    width: 20; height: 20
                    smooth: true
                    layer.enabled: !darkMode
                    layer.effect: MultiEffect { colorization: 1.0; colorizationColor: "#333333" }
                }
                Text {
                    id: nightLightLabel
                    text: batteryPanel.tr("power.nightLight")
                    font.pixelSize: 14
                    color: darkMode ? "#cccccc" : "#333333"
                    anchors.verticalCenter: parent.verticalCenter
                }
                Item { width: parent.width - nightLightLabel.width - 60 - 20; height: 1 }
                Rectangle {
                    width: 44; height: 24; radius: 12
                    anchors.verticalCenter: parent.verticalCenter
                    color: batteryPanel.nightLightEnabled ? batteryPanel.accentColor : (darkMode ? "#3a3a3a" : "#c0c0c0")
                    Behavior on color { ColorAnimation { duration: 150 } }
                    Rectangle {
                        width: 18; height: 18; radius: 9
                        color: darkMode ? "#fff" : "#1a1a1a"
                        x: batteryPanel.nightLightEnabled ? parent.width - width - 3 : 3
                        anchors.verticalCenter: parent.verticalCenter
                        Behavior on x { NumberAnimation { duration: 150 } }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: batteryPanel.toggleNightLight()
                    }
                }
            }
        }
    }
}
