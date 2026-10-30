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
    readonly property color foreground: dark ? "#ffffff" : "#1a1a1a"
    readonly property color secondary: dark ? "#aaaaaa" : "#555555"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d0d0d0"
    property bool autoLoad: true
    property bool busy: false
    property bool ready: false
    property bool showOrphans: false
    property bool showFailed: false
    property bool showDetails: false
    property bool rebootNeeded: false
    property var state: ({tools: {}, orphans: [], failedServices: [], packageProcesses: []})
    property string resultKey: ""
    property real freedBytes: -1
    readonly property string resultText: resultKey ? tr(resultKey) + (freedBytes >= 0 ? " " + tr("maintenance.freed").replace("%1", sizeText(freedBytes)) : "") : ""
    property string detailText: ""
    property string logPath: ""
    property string pendingAction: ""
    property var pendingArgs: ({})
    property string pendingDescription: ""
    width: parent ? parent.width : 650
    height: content.height

    function tr(key) { return Lang.get(key, _lang) }
    function sizeText(bytes) {
        if (bytes === null || bytes === undefined) return tr("maintenance.sizeUnknown")
        const gib = bytes / (1024 * 1024 * 1024)
        return gib >= 1 ? gib.toFixed(1) + " GiB" : (bytes / (1024 * 1024)).toFixed(1) + " MiB"
    }
    function acceptStatus(data) { state = data; ready = true }
    function requestAction(action, args, description) {
        if (!ready || busy || state.live) return
        pendingAction = action; pendingArgs = args; pendingDescription = description
        confirmation.open()
    }
    function runAction(action, args) {
        if (busy) return
        busy = true; worker.operation = action
        if (action !== "maintenance-status") {
            resultKey = ""; freedBytes = -1; detailText = ""; showDetails = false; logPath = ""
        }
        worker.command = (action === "maintenance-status" ? ["/usr/bin/python3", "-I"] : ["/usr/bin/pkexec", "--disable-internal-agent"])
            .concat(["/usr/lib/windoesnot/system_tools.py", action, JSON.stringify(args)])
        worker.running = true
    }
    Component.onCompleted: if (autoLoad) runAction("maintenance-status", {})
    Process {
        id: worker
        property string operation: ""
        stdout: StdioCollector { id: output }
        stderr: StdioCollector { id: errors }
        onExited: (code) => {
            busy = false
            let data = {}
            try { data = JSON.parse(output.text) } catch (error) {}
            if (code === 0 && !data.error) {
                if (operation === "maintenance-status") acceptStatus(data)
                else {
                    rebootNeeded = rebootNeeded || data.reboot === true
                    logPath = data.log || ""
                    resultKey = "maintenance.done." + operation
                    freedBytes = data.freedBytes !== undefined ? data.freedBytes : -1
                    runAction("maintenance-status", {})
                }
            } else {
                logPath = data.log || ""
                resultKey = code === 126 ? "systemTools.cancelled" : "systemTools.failed"
                detailText = code === 126 ? "" : (data.error || errors.text.trim() || output.text.trim()) + (data.detail ? "\n" + data.detail : "")
                if (operation !== "maintenance-status") runAction("maintenance-status", {})
            }
        }
    }

    component Note: Text {
        width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText
        color: page.secondary; font.pixelSize: 13
    }
    component ActionButton: Tools.SystemToolsButton {
        settingsMenu: page.settingsMenu
        enabled: page.ready && !page.busy && !page.state.live
    }

    Column {
        id: content
        width: parent.width; spacing: 20
        Note { text: page.tr("maintenance.intro") }
        Note { visible: page.state.live === true; text: page.tr("systemTools.live") }
        Note { visible: !page.ready; text: page.busy ? page.tr("systemTools.loading") : page.tr("systemTools.unavailable") }
        Row {
            spacing: 12
            ActionButton { text: page.tr("systemTools.refresh"); enabled: !page.busy; onClicked: page.runAction("maintenance-status", {}) }
            BusyIndicator { width: 32; height: 32; running: page.busy; visible: running; palette.highlight: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
        }
        Rectangle {
            visible: page.resultText.length > 0 || page.rebootNeeded
            width: parent.width; height: resultColumn.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: resultColumn; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Note { visible: page.resultText.length > 0; text: page.resultText; color: page.foreground }
                Note { visible: page.rebootNeeded; text: page.tr("systemTools.reboot"); color: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
                Note { visible: page.logPath.length > 0; text: page.tr("systemTools.log") + " " + page.logPath; font.pixelSize: 11 }
                Tools.SystemToolsButton { settingsMenu: page.settingsMenu; visible: page.detailText.length > 0; text: page.tr("systemTools.details"); onClicked: page.showDetails = !page.showDetails }
                Note { visible: page.showDetails; text: page.detailText; font.pixelSize: 12 }
            }
        }
        Note {
            visible: page.ready && page.state.setup !== null && page.state.setup.drivers === "pending"
            text: page.tr("maintenance.driversPending"); color: "#e8a020"
        }
        Repeater {
            model: [
                {action: "mirrors-rank", title: "maintenance.mirrors", hint: "maintenance.mirrorsHint", tool: "cachyos-rate-mirrors", confirmation: "maintenance.confirmMirrors"},
                {action: "cache-clean", title: "maintenance.cache", hint: "maintenance.cacheHint", tool: "paccache", confirmation: "maintenance.confirmCache"},
                {action: "keyring-repair", title: "maintenance.keyring", hint: "maintenance.keyringHint", tool: "pacman-key", confirmation: "maintenance.confirmKeyring"},
                {action: "lock-remove", title: "maintenance.lock", hint: "maintenance.lockHint", tool: "", confirmation: "maintenance.confirmLock"},
                {action: "orphans", title: "maintenance.orphans", hint: "maintenance.orphansHint", tool: "", confirmation: ""},
                {action: "failed", title: "maintenance.failed", hint: "maintenance.failedHint", tool: "", confirmation: ""},
                {action: "drivers-configure", title: "maintenance.drivers", hint: "maintenance.driversHint", tool: "chwd", confirmation: "maintenance.confirmDrivers"}
            ]
            delegate: Rectangle {
                id: card
                required property var modelData
                readonly property bool readOnlyAction: modelData.action === "orphans" || modelData.action === "failed"
                readonly property bool toolAvailable: !modelData.tool || page.state.tools[modelData.tool] === true
                readonly property bool mayRun: page.ready && !page.busy && toolAvailable
                    && (readOnlyAction || !page.state.live)
                    && (modelData.action !== "lock-remove" || (page.state.lockExists && page.state.processesVisible && !page.state.packageProcesses.length))
                width: content.width; height: cardContent.implicitHeight + 32
                radius: settingsMenu ? settingsMenu.borderRadius : 10
                color: page.dark ? "#141414" : "#f5f5f5"
                border.width: 1; border.color: page.lineColor
                Column {
                    id: cardContent; x: 16; y: 16; width: parent.width - 32; spacing: 10
                    Text { width: parent.width; text: page.tr(card.modelData.title); color: page.foreground; font.pixelSize: 15; font.bold: true; wrapMode: Text.WordWrap }
                    Note { text: page.tr(card.modelData.hint) }
                    Note {
                        visible: card.modelData.action === "cache-clean" && page.ready
                        text: page.tr("maintenance.cacheSize").replace("%1", page.sizeText(page.state.cacheBytes))
                    }
                    Note {
                        visible: card.modelData.action === "mirrors-rank" && page.ready
                        text: page.tr(page.state.mirrorsRanked ? "maintenance.mirrorsDone" : "maintenance.mirrorsNotDone")
                    }
                    Note {
                        visible: card.modelData.action === "lock-remove" && page.ready
                        text: page.tr(!page.state.processesVisible ? "maintenance.lockUnknown"
                            : page.state.packageProcesses.length ? "maintenance.lockBusy"
                            : page.state.lockExists ? "maintenance.lockFound" : "maintenance.lockNone")
                    }
                    Note { visible: page.ready && !card.toolAvailable; text: page.tr("maintenance.toolMissing").replace("%1", card.modelData.tool === "paccache" ? "pacman-contrib" : card.modelData.tool) }
                    ActionButton {
                        enabled: card.mayRun
                        primary: !card.readOnlyAction && card.modelData.action !== "lock-remove"
                        text: page.tr(card.readOnlyAction ? "maintenance.show" : "maintenance.run")
                        onClicked: {
                            if (card.modelData.action === "orphans") page.showOrphans = !page.showOrphans
                            else if (card.modelData.action === "failed") page.showFailed = !page.showFailed
                            else page.requestAction(card.modelData.action, {}, page.tr(card.modelData.confirmation))
                        }
                    }
                    Note {
                        visible: card.modelData.action === "orphans" && page.showOrphans
                        text: page.state.orphans.length ? page.state.orphans.join("\n") : page.tr("maintenance.noOrphans")
                    }
                    ActionButton {
                        visible: card.modelData.action === "orphans" && page.showOrphans && page.state.orphans.length > 0
                        destructive: true
                        text: page.tr("maintenance.removeOrphans")
                        onClicked: page.requestAction("orphans-remove", {packages: page.state.orphans.slice()},
                            page.tr("maintenance.confirmOrphans") + "\n\n" + page.state.orphans.join("\n"))
                    }
                    Note {
                        visible: card.modelData.action === "failed" && page.showFailed
                        text: page.state.failedServices.length ? page.state.failedServices.join("\n") : page.tr("maintenance.noFailed")
                    }
                }
            }
        }
    }
    Tools.SystemToolsConfirm {
        id: confirmation
        settingsMenu: page.settingsMenu
        title: page.tr("systemTools.confirm")
        description: page.pendingDescription
        destructive: page.pendingAction === "orphans-remove"
        onAccepted: page.runAction(page.pendingAction, page.pendingArgs)
    }
}
