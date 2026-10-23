import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Polkit
import QtQuick

Scope {
    id: authentication
    property var settingsMenu: null
    property bool testing: false
    readonly property var flow: agent.item ? agent.item.flow : null
    readonly property bool active: flow !== null && !flow.isCompleted
    readonly property bool embedded: active && settingsMenu && settingsMenu.visible
        && settingsMenu.currentCategory === "backups"
        && flow.actionId.indexOf("org.windoesnot.snapshots.") === 0
    readonly property bool registered: agent.item !== null && agent.item.isRegistered
    property string guardPath: "/usr/bin/windoesnot-auth-guard"

    IpcHandler {
        target: "authentication"
        function status(): string {
            return JSON.stringify({registered: authentication.registered,
                active: authentication.active, embedded: authentication.embedded})
        }
    }

    // The detached guard restores GNOME if this process exits or stops replying.
    Timer { running: !authentication.testing; interval: 2500; onTriggered: acquire.running = true }
    Process {
        id: acquire
        command: [authentication.guardPath, "acquire", String(Quickshell.processId)]
        onExited: (code) => { if (code === 0) { agent.active = true; registrationDeadline.restart() } }
    }
    Loader {
        id: agent
        active: false
        sourceComponent: Component { PolkitAgent {} }
    }
    Timer {
        id: registrationDeadline
        interval: 8000
        onTriggered: if (!authentication.registered) { agent.active = false; fallback.running = true }
    }
    Timer {
        interval: 3000; repeat: true; running: authentication.registered
        onTriggered: if (!heartbeat.running) heartbeat.running = true
    }
    Process {
        id: heartbeat
        command: [authentication.guardPath, "heartbeat", String(Quickshell.processId)]
        onExited: (code) => { if (code !== 0) { agent.active = false; fallback.running = true } }
    }
    Process {
        id: fallback
        command: [authentication.guardPath, "restore", String(Quickshell.processId)]
    }
    // A separate layer surface is only used for requests outside Backup Settings.
    PanelWindow {
        visible: authentication.active && !authentication.embedded
        screen: authentication.settingsMenu ? authentication.settingsMenu.screen : null
        implicitWidth: 460
        implicitHeight: dialog.implicitHeight
        color: "transparent"
        exclusiveZone: 0
        WlrLayershell.namespace: "windoesnot-authentication"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
        AuthenticationCard {
            id: dialog
            anchors.fill: parent
            flow: authentication.embedded ? null : authentication.flow
            settingsMenu: authentication.settingsMenu
        }
    }
}
