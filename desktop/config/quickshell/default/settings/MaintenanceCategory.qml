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
    property string selectedGroup: "downloads"
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
    function groupFor(action) {
        if (action === "mirrors-rank" || action === "cache-clean") return "downloads"
        if (action === "drivers-configure") return "devices"
        return "repair"
    }
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
        Row {
            width: parent.width; spacing: 8
            Repeater {
                model: [
                    {key: "downloads", label: page.tr("maintenance.groupDownloads")},
                    {key: "repair", label: page.tr("maintenance.groupRepair")},
                    {key: "devices", label: page.tr("maintenance.groupDevices")}
                ]
                delegate: Tools.SystemToolsButton {
                    required property var modelData
                    width: (content.width - 16) / 3
                    settingsMenu: page.settingsMenu
                    text: modelData.label
                    primary: page.selectedGroup === modelData.key
                    onClicked: page.selectedGroup = modelData.key
                }
            }
        }
        Note { visible: page.state.live === true; text: page.tr("systemTools.live") }
        Note { visible: !page.ready; text: page.busy ? page.tr("systemTools.loading") : page.tr("systemTools.unavailable") }
        BusyIndicator { width: 32; height: 32; running: page.busy; visible: running; palette.highlight: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
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
                visible: page.selectedGroup === page.groupFor(modelData.action)
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
        Rectangle {
            id: firewallCard
            visible: page.selectedGroup === "devices"
            width: content.width; height: firewallContent.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: firewallContent; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Text { width: parent.width; text: page.tr("maintenance.firewall"); color: page.foreground; font.pixelSize: 15; font.bold: true; wrapMode: Text.WordWrap }
                Note { text: page.tr("maintenance.firewallHint") }
                Tools.SystemToolsToggle {
                    settingsMenu: page.settingsMenu
                    text: page.tr("maintenance.firewallOn")
                    enabled: page.ready && !page.busy && !page.state.live && page.state.firewall !== null && page.state.firewall !== undefined
                    checked: page.state.firewall ? page.state.firewall.enabled === true : false
                    onToggled: {
                        page.requestAction("firewall-set", {enabled: checked},
                            page.tr(checked ? "maintenance.confirmFirewallOn" : "maintenance.confirmFirewallOff"))
                        // Show the confirmed state only after the next status read.
                        checked = Qt.binding(function() { return page.state.firewall ? page.state.firewall.enabled === true : false })
                    }
                }
                Note { visible: page.ready && (page.state.firewall === null || page.state.firewall === undefined); text: page.tr("maintenance.firewallUnavailable") }
            }
        }
        Rectangle {
            id: printerCard
            visible: page.selectedGroup === "devices"
            // Older installed helpers and the initial empty state may omit printers.
            readonly property var printerState: page.state.printers || null
            width: content.width; height: printerContent.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: printerContent; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Text { width: parent.width; text: page.tr("maintenance.printers"); color: page.foreground; font.pixelSize: 15; font.bold: true; wrapMode: Text.WordWrap }
                Note { text: page.tr("maintenance.printersHint") }
                Note { visible: page.ready && printerCard.printerState === null; text: page.tr("maintenance.printersUnavailable") }
                Note { visible: printerCard.printerState !== null && printerCard.printerState.cupsActive === false; text: page.tr("maintenance.printersCupsOff") }
                ActionButton {
                    visible: printerCard.printerState !== null && printerCard.printerState.cupsActive === false
                    primary: true
                    text: page.tr("maintenance.printerSearch")
                    onClicked: page.requestAction("printer-service-start", {}, page.tr("maintenance.confirmPrinterService"))
                }
                Note { visible: printerCard.printerState !== null && printerCard.printerState.cupsActive === true && printerCard.printerState.printers.length === 0; text: page.tr("maintenance.printerNone") }
                Repeater {
                    model: printerCard.printerState !== null && printerCard.printerState.cupsActive === true ? printerCard.printerState.printers : []
                    delegate: Column {
                        id: printerRow
                        required property var modelData
                        width: printerContent.width; spacing: 6
                        Text { width: parent.width; text: printerRow.modelData.name + (printerRow.modelData.name === printerCard.printerState.default ? "  (" + page.tr("maintenance.printerIsDefault") + ")" : ""); color: page.foreground; font.pixelSize: 13; wrapMode: Text.WordWrap }
                        Note { text: printerRow.modelData.uri; font.pixelSize: 11 }
                        ActionButton {
                            visible: printerRow.modelData.name !== printerCard.printerState.default
                            text: page.tr("maintenance.printerMakeDefault")
                            onClicked: page.requestAction("printer-default", {name: printerRow.modelData.name},
                                page.tr("maintenance.confirmPrinterDefault"))
                        }
                    }
                }
                Note { visible: printerCard.printerState !== null && printerCard.printerState.cupsActive === true; text: page.tr("maintenance.printerFound") }
                Note {
                    visible: printerCard.printerState !== null && printerCard.printerState.cupsActive === true && printerCard.printerState.candidates.length === 0
                    text: page.tr("maintenance.printerNoneFound")
                }
                Repeater {
                    model: printerCard.printerState !== null && printerCard.printerState.cupsActive === true ? printerCard.printerState.candidates : []
                    delegate: Column {
                        id: candidateRow
                        required property var modelData
                        required property int index
                        readonly property string printerName: {
                            const host = String(modelData).replace(/^[^:]+:\/\//, "").split(/[\/?]/)[0].replace(/[^A-Za-z0-9-]+/g, "-").slice(0, 40)
                            return host.length ? host : "Drucker-" + (index + 1)
                        }
                        width: printerContent.width; spacing: 6
                        Note { text: candidateRow.modelData; font.pixelSize: 11 }
                        ActionButton {
                            enabled: page.ready && !page.busy && !page.state.live
                                && !(printerCard.printerState.printers.some(function(p) { return p.name === candidateRow.printerName }))
                            text: page.tr("maintenance.printerAdd")
                            onClicked: page.requestAction("printer-add", {uri: candidateRow.modelData, name: candidateRow.printerName},
                                page.tr("maintenance.confirmPrinterAdd"))
                        }
                    }
                }
            }
        }
        Rectangle {
            id: firmwareCard
            visible: page.selectedGroup === "devices"
            readonly property var updates: page.state.firmware
            width: content.width; height: firmwareContent.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: firmwareContent; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Text { width: parent.width; text: page.tr("maintenance.firmware"); color: page.foreground; font.pixelSize: 15; font.bold: true; wrapMode: Text.WordWrap }
                Note { text: page.tr("maintenance.firmwareHint") }
                Note { visible: page.ready && firmwareCard.updates === null; text: page.tr("maintenance.firmwareUnknown") }
                Note { visible: page.ready && firmwareCard.updates !== null && firmwareCard.updates.length === 0; text: page.tr("maintenance.firmwareNone") }
                Note {
                    visible: firmwareCard.updates !== null && firmwareCard.updates !== undefined && firmwareCard.updates.length > 0
                    color: page.foreground
                    text: firmwareCard.updates ? firmwareCard.updates.map(function(u) { return u.device + ": " + u.version }).join("\n") : ""
                }
                ActionButton {
                    visible: firmwareCard.updates !== null && firmwareCard.updates !== undefined && firmwareCard.updates.length > 0
                    enabled: page.ready && !page.busy && !page.state.live
                    primary: true
                    text: page.tr("maintenance.firmwareApply")
                    onClicked: page.requestAction("firmware-apply", {}, page.tr("maintenance.confirmFirmware"))
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
