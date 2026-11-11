import QtQuick
import QtQuick.Controls
import "." as Tools
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color foreground: dark ? "#eeeeee" : "#202020"
    readonly property color secondary: dark ? "#bbbbbb" : "#555555"
    property bool autoLoad: true
    property bool busy: false
    property bool ready: false
    property var state: ({battery: null, profiles: [], currentProfile: "", profilesAvailable: false})
    property string profileError: ""
    width: parent ? parent.width : 650
    height: content.height

    function tr(key) { return Lang.get(key, _lang) }
    function acceptStatus(data) { state = data; ready = true }
    function refresh() {
        busy = true
        statusWorker.command = ["/usr/bin/python3", "-I", "/usr/lib/windoesnot/system_tools.py", "power-status", "{}"]
        statusWorker.running = true
    }
    Component.onCompleted: if (autoLoad) refresh()

    function batteryStateLabel(value) {
        const key = {charging: "power.stateCharging", discharging: "power.stateDischarging",
            "fully-charged": "power.stateFull", "pending-charge": "power.stateCharging",
            "pending-discharge": "power.stateDischarging"}[value]
        return key ? page.tr(key) : (value || page.tr("power.stateUnknown"))
    }

    function setProfile(name) {
        if (page.busy || profileWorker.running) return
        profileWorker.command = ["/usr/bin/powerprofilesctl", "set", name]
        profileWorker.running = true
    }

    Process {
        id: statusWorker
        stdout: StdioCollector { id: statusOutput }
        onExited: (code) => {
            busy = false
            if (code === 0) {
                try { page.acceptStatus(JSON.parse(statusOutput.text)) } catch (error) {}
            }
        }
    }

    Process {
        id: profileWorker
        stdout: StdioCollector { id: profileOutput }
        stderr: StdioCollector { id: profileErrors }
        onExited: (code) => {
            page.profileError = code === 0 ? "" : (profileErrors.text || profileOutput.text || page.tr("power.profileFailed")).trim()
            page.refresh()
        }
    }

    component Note: Text {
        width: parent.width
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        color: page.secondary
        font.pixelSize: 13
    }
    component Heading: Text {
        width: parent.width
        wrapMode: Text.WordWrap
        color: page.foreground
        font.pixelSize: 18
        font.bold: true
    }

    Column {
        id: content
        width: parent.width
        spacing: 20

        Note { text: page.tr("power.intro") }
        BusyIndicator { width: 32; height: 32; running: page.busy; visible: running; palette.highlight: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }

        Tools.SystemToolsToggle {
            settingsMenu: page.settingsMenu
            text: page.tr("power.trayToggle")
            checked: page.settingsMenu ? page.settingsMenu.showBatteryTray : false
            onToggled: if (page.settingsMenu) page.settingsMenu.showBatteryTray = checked
        }
        Note { text: page.tr("apps.batteryTrayDesc") }

        Heading { text: page.tr("power.battery") }
        Note { visible: !page.ready && page.busy; text: page.tr("systemTools.loading") }
        Note { visible: page.ready && !page.state.battery; text: page.tr("power.noBattery") }
        Rectangle {
            visible: page.ready && !!page.state.battery
            width: parent.width
            height: batteryRows.height + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1
            border.color: page.dark ? "#3a3a3a" : "#d0d0d0"
            Column {
                id: batteryRows
                x: 16; y: 16; width: parent.width - 32; spacing: 8
                Text {
                    text: (page.state.battery ? page.state.battery.percentage : "0") + "%"
                    color: page.foreground
                    font.pixelSize: 28
                    font.bold: true
                }
                Note { text: page.state.battery ? page.batteryStateLabel(page.state.battery.state) : "" }
                Note {
                    readonly property string remaining: page.state.battery && page.state.battery.state === "charging" && page.state.battery.timeToFull
                        ? page.tr("power.timeToFull") + " " + page.state.battery.timeToFull
                        : (page.state.battery && page.state.battery.timeToEmpty ? page.tr("power.timeToEmpty") + " " + page.state.battery.timeToEmpty : "")
                    visible: remaining.length > 0
                    text: remaining
                }
            }
        }

        Heading { text: page.tr("power.profile") }
        Note { text: page.tr("power.profileHint") }
        Note { visible: page.ready && !page.state.profilesAvailable; text: page.tr("power.profileUnavailable") }
        Row {
            spacing: 10
            visible: page.ready && page.state.profilesAvailable
            Repeater {
                model: page.state.profiles
                delegate: Rectangle {
                    required property string modelData
                    readonly property bool active: page.state.currentProfile === modelData
                    width: 140
                    height: 35
                    radius: 6
                    color: active ? (settingsMenu ? settingsMenu.accentColor : "#fe6f2d") : (page.dark ? "#2a2a2a" : "#f0f0f0")
                    border.width: 1
                    border.color: page.dark ? "#3a3a3a" : "#d0d0d0"
                    opacity: profileWorker.running ? 0.5 : 1
                    Behavior on color { ColorAnimation { duration: 150 } }
                    Text {
                        anchors.centerIn: parent
                        text: page.tr("power.profile." + modelData)
                        color: active ? "#ffffff" : (page.dark ? "#ffffff" : "#1a1a1a")
                        font.pixelSize: 12
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: !profileWorker.running
                        cursorShape: Qt.PointingHandCursor
                        onClicked: page.setProfile(modelData)
                    }
                }
            }
        }
        Note { visible: page.profileError.length > 0; text: page.profileError; color: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
    }
}
