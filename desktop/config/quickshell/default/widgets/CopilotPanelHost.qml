import QtQuick
import Quickshell.Io

Item {
    id: panelHost

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property bool darkMode: true
    property bool windowVisible: false
    property string uiLanguage: "de"

    property string panelMode: "chat"       // "chat" | "terminal"
    property string terminalProfile: "claude"

    property bool terminalModuleAvailable: false
    property bool availabilityResolved: false
    property bool _agentFailed: false

    property string claudeApiKey: ""
    property string openaiApiKey: ""

    // Always pinned — window stays open until explicitly closed (no FocusGrab auto-close)
    property bool isPinned: true

    signal closeAndReopenWindow(bool newPinState)

    // Checks the same QML_IMPORT_PATH the engine uses to import LocalTerminal.
    Process {
        id: moduleCheckProc
        command: ["bash", "-c",
            "IFS=:; for dir in $QML_IMPORT_PATH; do " +
            "if [ -f \"$dir/LocalTerminal/qmldir\" ] && ls \"$dir/LocalTerminal\"/*.so >/dev/null 2>&1; then echo 1; exit 0; fi; " +
            "done; echo 0"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                panelHost.terminalModuleAvailable = text.trim() === "1"
                panelHost.availabilityResolved = true
            }
        }
    }

    Component.onCompleted: moduleCheckProc.running = true

    // Chat panel – always loaded
    Loader {
        id: chatLoader
        anchors.fill: parent
        source: "CopilotPanel.qml"
        visible: panelHost.panelMode === "chat"

        onLoaded: {
            item.accentColor = Qt.binding(function() { return panelHost.accentColor })
            item.borderRadius = Qt.binding(function() { return panelHost.borderRadius })
            item.darkMode = Qt.binding(function() { return panelHost.darkMode })
            item.windowVisible = Qt.binding(function() { return panelHost.windowVisible && panelHost.panelMode === "chat" })
            item.uiLanguage = Qt.binding(function() { return panelHost.uiLanguage })
            // Set isPinned directly, not as binding - otherwise signal loops
            item.isPinned = panelHost.isPinned
            console.log("[CopilotHost] chatLoader loaded, set item.isPinned to:", panelHost.isPinned)
            // Expose API keys to the host so the terminal panel can use them
            panelHost.claudeApiKey = Qt.binding(function() { return item.claudeApiKey })
            panelHost.openaiApiKey = Qt.binding(function() { return item.openaiApiKey })
            item.switchToTerminal = function(profile) {
                console.log("[CopilotHost] switchToTerminal called, profile:", profile,
                    "moduleAvail:", panelHost.terminalModuleAvailable,
                    "agentFailed:", panelHost._agentFailed,
                    "termLoader.status:", termLoader.status,
                    "termLoader.item:", termLoader.item)
                if (!panelHost.terminalModuleAvailable || panelHost._agentFailed) return
                panelHost.terminalProfile = profile
                panelHost.panelMode = "terminal"
                console.log("[CopilotHost] panelMode set to terminal")
            }
            // Forward pin state change signal
            item.requestWindowReopen.connect(function(newPinState) {
                console.log("[CopilotHost] ========================================")
                console.log("[CopilotHost] requestWindowReopen received!")
                console.log("[CopilotHost] newPinState:", newPinState)
                console.log("[CopilotHost] Setting panelHost.isPinned to:", newPinState)
                panelHost.isPinned = newPinState
                console.log("[CopilotHost] Emitting closeAndReopenWindow signal...")
                console.log("[CopilotHost] ========================================")
                panelHost.closeAndReopenWindow(newPinState)
            })
        }
    }

    // Terminal panel – loaded once module check succeeds
    Loader {
        id: termLoader
        anchors.fill: parent
        source: panelHost.availabilityResolved && panelHost.terminalModuleAvailable && !panelHost._agentFailed
            ? "AgentTerminalPanel.qml"
            : ""
        visible: panelHost.panelMode === "terminal"

        onStatusChanged: {
            console.log("[CopilotHost] termLoader status:", status, "source:", source)
            if (status === Loader.Error && panelHost.terminalModuleAvailable && !panelHost._agentFailed) {
                console.log("[CopilotHost] AgentTerminalPanel failed to load!")
                Qt.callLater(function() {
                    panelHost._agentFailed = true
                    if (panelHost.panelMode === "terminal") panelHost.panelMode = "chat"
                })
            }
        }

        onLoaded: {
            item.accentColor = Qt.binding(function() { return panelHost.accentColor })
            item.borderRadius = Qt.binding(function() { return panelHost.borderRadius })
            item.darkMode = Qt.binding(function() { return panelHost.darkMode })
            item.windowVisible = Qt.binding(function() { return panelHost.windowVisible && panelHost.panelMode === "terminal" })
            item.isPinned = true
            item.switchToChat = function() { panelHost.panelMode = "chat" }
            item.claudeApiKey = Qt.binding(function() { return panelHost.claudeApiKey })
            item.openaiApiKey = Qt.binding(function() { return panelHost.openaiApiKey })

            // apply the requested profile when terminal becomes visible
            item.activeProfile = Qt.binding(function() { return panelHost.terminalProfile })
        }
    }
}
