import QtQuick
import QtQuick.Controls
import "." as Tools
import Quickshell.Io
import "../i18n/Lang.js" as Lang
import "../i18n" as UiI

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
    property string desktopErrors: ""
    property var desktopPlugins: ({})
    property bool desktopStateReady: false
    property var pacnewFiles: []
    property string selectedPacnewPath: ""
    property string pacnewError: ""
    property var hwReport: null
    property bool hwBusy: false
    property string hwCopyResult: ""
    width: parent ? parent.width : 650
    height: content.height

    function tr(key) { return Lang.get(key, _lang) }
    function groupFor(action) {
        if (action === "mirrors-rank" || action === "cache-clean") return "downloads"
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
    Component.onCompleted: {
        if (autoLoad) runAction("maintenance-status", {})
        desktopStateProc.running = true
        hwProc.running = true
        if (autoLoad) { busyPacnew = true; pacnewProc.running = true }
    }
    Process {
        id: hwProc
        command: ["/usr/bin/python3", "-I", "/usr/lib/windoesnot/hwcheck.py"]
        stdout: StdioCollector { id: hwOutput }
        onExited: (code) => {
            page.hwBusy = false
            if (code !== 0) { page.hwReport = null; return }
            try { page.hwReport = JSON.parse(hwOutput.text) } catch (error) { page.hwReport = null }
        }
        Component.onCompleted: page.hwBusy = true
    }
    Process { id: hwCopyProc; onExited: (code) => page.hwCopyResult = code === 0 ? "maintenance.hwCopied" : "maintenance.hwCopyFailed" }
    Process {
        id: pacnewProc
        command: ["/usr/bin/python3", "-I", "/usr/lib/windoesnot/pacnew.py"]
        stdout: StdioCollector { id: pacnewOutput }
        stderr: StdioCollector { id: pacnewErrors }
        onExited: (code) => {
            page.busyPacnew = false
            if (code !== 0) { page.pacnewError = pacnewErrors.text.trim(); return }
            try {
                const data = JSON.parse(pacnewOutput.text)
                page.pacnewFiles = data.files || []
                if (!page.pacnewFiles.some(item => item.path === page.selectedPacnewPath))
                    page.selectedPacnewPath = page.pacnewFiles.length ? page.pacnewFiles[0].path : ""
                page.pacnewError = ""
            } catch (error) { page.pacnewError = String(error) }
        }
    }
    property bool busyPacnew: false
    function refreshPacnew() { if (busyPacnew) return; busyPacnew = true; pacnewProc.running = true }
    readonly property var selectedPacnew: pacnewFiles.find(item => item.path === selectedPacnewPath) || null
    Process {
        id: desktopStateProc
        command: ["windoesnot-bounded", "8", "sh", "-c", "command -v windoesnot-hyprctl >/dev/null || exit 127; printf '%s\\n' '---CONFIG---'; windoesnot-hyprctl configerrors 2>&1 || true; printf '%s\\n' '---PLUGINS---'; windoesnot-hyprctl plugin list 2>&1 || true"]
        stdout: StdioCollector { id: desktopStateOutput }
        onExited: (code) => {
            const parts = desktopStateOutput.text.split("---PLUGINS---")
            const configPart = parts[0].replace("---CONFIG---", "").trim()
            const pluginPart = parts.length > 1 ? parts.slice(1).join("---PLUGINS---") : ""
            page.desktopErrors = configPart
            page.desktopPlugins = ({
                hyprbars: /hyprbars/i.test(pluginPart),
                hyprdrag: /hyprdrag/i.test(pluginPart)
            })
            page.desktopStateReady = code === 0
        }
    }
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

    property var mediaReport: null
    property bool mediaFailed: false
    Process {
        id: mediaProc
        command: ["/usr/bin/python3", "-I", "/usr/lib/windoesnot/media_check.py"]
        stdout: StdioCollector { id: mediaOutput }
        onExited: (code) => {
            page.mediaFailed = code !== 0
            if (code === 0) {
                try { page.mediaReport = JSON.parse(mediaOutput.text) }
                catch (error) { page.mediaFailed = true }
            }
        }
    }

    component Note: Text {
        width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText
        color: page.secondary; font.pixelSize: UiI.UiScale.px(13)
    }
    component ActionButton: Tools.SystemToolsButton {
        settingsMenu: page.settingsMenu
        enabled: page.ready && !page.busy && !page.state.live
    }

    Column {
        id: content
        width: parent.width; spacing: 20
        Note { text: page.tr("maintenance.intro") }
        Rectangle {
            objectName: "mediaCard"
            width: parent.width; height: mediaColumn.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: mediaColumn; x: 16; y: 16; width: parent.width - 32; spacing: 8
                Text { text: page.tr("media.title"); color: page.foreground; font.bold: true; font.pixelSize: UiI.UiScale.px(15) }
                Note { text: page.tr("media.hint") }
                Tools.SystemToolsButton {
                    settingsMenu: page.settingsMenu; text: page.tr("media.check"); enabled: !mediaProc.running
                    onClicked: { page.mediaFailed = false; page.mediaReport = null; mediaProc.running = true }
                }
                Note {
                    visible: page.mediaFailed || page.mediaReport !== null
                    text: page.mediaFailed ? page.tr("media.failed") : page.mediaReport ? Object.keys(page.mediaReport).map(function (name) {
                        const item = page.mediaReport[name]
                        return name + ": FFmpeg " + page.tr(item.ffmpeg ? "media.present" : "media.missing") + ", GStreamer " + page.tr(item.gstreamer ? "media.present" : "media.missing")
                    }).join("\n") : ""
                }
            }
        }
        Rectangle {
            objectName: "hardwareCard"
            width: parent.width; height: hardwareColumn.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: hardwareColumn; x: 16; y: 16; width: parent.width - 32; spacing: 8
                Text { text: page.tr("hwcheck.title"); color: page.foreground; font.bold: true; font.pixelSize: UiI.UiScale.px(15) }
                Note { visible: page.hwReport === null; text: page.hwBusy ? page.tr("systemTools.loading") : page.tr("systemTools.unavailable") }
                Note {
                    visible: page.hwReport !== null
                    text: page.hwReport ? page.tr("hwcheck.cpu") + ": " + page.hwReport.cpu.model + " (" + page.hwReport.cpu.cores + ")\n"
                        + page.tr("hwcheck.missingInstructions") + ": " + (page.hwReport.cpu.missing_instruction_sets.length ? page.hwReport.cpu.missing_instruction_sets.join(", ") : page.tr("hwcheck.noneMissing")) + "\n"
                        + page.tr("hwcheck.memory") + ": " + page.sizeText(page.hwReport.memory_bytes) + " · " + page.tr("hwcheck.swap") + ": " + page.sizeText(page.hwReport.swap_bytes) + "\n"
                        + page.tr("hwcheck.graphics") + ": " + (page.hwReport.gpus.length ? page.hwReport.gpus.map(g => g.name + (g.driver ? " — " + g.driver : "")).join(", ") : page.tr("hwcheck.unknown")) + "\n"
                        + page.tr("hwcheck.renderer") + ": " + (page.hwReport.renderer || page.tr("hwcheck.hardwareRenderer")) + "\n"
                        + page.tr("hwcheck.disks") + ": " + (page.hwReport.disks.map(d => page.tr("hwcheck." + d.kind)).join(", ") || page.tr("hwcheck.unknown")) + "\n"
                        + page.tr("hwcheck.devices") + ": " + page.tr("hwcheck.battery") + " " + (page.hwReport.battery ? page.tr("hwcheck.present") : page.tr("hwcheck.absent")) + ", Wi-Fi " + (page.hwReport.controllers.wifi ? page.tr("hwcheck.present") : page.tr("hwcheck.absent")) + ", Bluetooth " + (page.hwReport.controllers.bluetooth ? page.tr("hwcheck.present") : page.tr("hwcheck.absent")) + "\n"
                        + page.tr("hwcheck.recommendations") + ": " + (page.hwReport.recommendations.map(r => page.tr("hwcheck.recommendation." + r.id) + " — " + r.reasons.map(reason => page.tr("hwcheck.reason." + reason)).join(", ")).join("; ") || page.tr("hwcheck.none")) : ""
                }
                Tools.SystemToolsButton {
                    objectName: "hwLiteEnableButton"
                    visible: page.hwReport !== null && page.hwReport.recommendations.some(r => r.id === "lite_mode") && !page.state.liteMode
                    settingsMenu: page.settingsMenu; text: page.tr("maintenance.liteModeEnable")
                    enabled: page.ready && !page.busy && !page.state.live
                    onClicked: page.requestAction("lite-mode-set", {enabled: true}, page.tr("maintenance.confirmLiteMode"))
                }
                Row {
                    spacing: 8
                    Tools.SystemToolsButton {
                        objectName: "hwReportCopyButton"
                        visible: page.hwReport !== null; settingsMenu: page.settingsMenu
                        text: page.tr("hwcheck.copy"); enabled: !hwCopyProc.running
                        onClicked: {
                            page.hwCopyResult = ""
                            const safe = JSON.stringify(page.hwReport, null, 2)
                            hwCopyProc.command = ["bash", "-c", "printf '%s' \"$1\" | wl-copy", "--", safe]
                            hwCopyProc.running = true
                        }
                    }
                    Note { visible: page.hwCopyResult.length > 0; text: page.tr(page.hwCopyResult) }
                }
            }
        }
        Rectangle {
            width: parent.width; height: liteColumn.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: liteColumn; x: 16; y: 16; width: parent.width - 32; spacing: 8
                Text { text: page.tr("maintenance.liteMode"); color: page.foreground; font.bold: true; font.pixelSize: UiI.UiScale.px(15) }
                Note { text: page.tr("maintenance.liteModeHint") }
                Tools.SystemToolsButton {
                    settingsMenu: page.settingsMenu
                    enabled: page.ready && !page.busy && !page.state.live
                    text: page.tr(page.state.liteMode ? "maintenance.liteModeDisable" : "maintenance.liteModeEnable")
                    onClicked: page.requestAction("lite-mode-set", {enabled: !page.state.liteMode}, page.tr("maintenance.confirmLiteMode"))
                }
            }
        }
        Rectangle {
            objectName: "removeOldCard"
            width: parent.width; height: removeOldColumn.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: removeOldColumn; x: 16; y: 16; width: parent.width - 32; spacing: 8
                Text { text: page.tr("maintenance.removeOld"); color: page.foreground; font.bold: true; font.pixelSize: UiI.UiScale.px(15) }
                Note { text: page.tr("maintenance.removeOldHint") }
                Tools.SystemToolsButton {
                    settingsMenu: page.settingsMenu
                    enabled: !page.state.live
                    text: page.tr("maintenance.removeOldOpen")
                    onClicked: removeOldProcess.running = true
                }
                Process { id: removeOldProcess; command: ["setsid", "--fork", "windoesnot-remove-old-os"] }
            }
        }
        Rectangle {
            objectName: "pacnewCard"
            width: parent.width; height: pacnewContent.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: pacnewContent; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Text { text: page.tr("pacnew.title"); color: page.foreground; font.pixelSize: UiI.UiScale.px(15); font.bold: true }
                Note { text: page.tr("pacnew.hint") }
                Row {
                    width: parent.width; spacing: 10
                    Tools.SystemToolsButton { settingsMenu: page.settingsMenu; text: page.tr("pacnew.refresh"); enabled: !page.busyPacnew; onClicked: page.refreshPacnew() }
                    BusyIndicator { width: 28; height: 28; running: page.busyPacnew; visible: running; palette.highlight: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
                }
                Note { visible: page.pacnewError.length > 0; text: page.tr("pacnew.failed") + " " + page.pacnewError }
                Note { visible: !page.busyPacnew && !page.pacnewFiles.length && !page.pacnewError; text: page.tr("pacnew.empty") }
                Repeater {
                    model: page.pacnewFiles
                    delegate: Tools.SystemToolsButton {
                        required property var modelData
                        width: pacnewContent.width
                        settingsMenu: page.settingsMenu
                        primary: page.selectedPacnewPath === modelData.path
                        text: modelData.path + "  ·  " + modelData.kind + "  ·  " + modelData.package
                        onClicked: page.selectedPacnewPath = modelData.path
                    }
                }
                Note {
                    visible: page.selectedPacnew !== null
                    text: page.selectedPacnew ? page.tr("pacnew.metadata").replace("%1", page.selectedPacnew.date).replace("%2", page.selectedPacnew.size).replace("%3", page.selectedPacnew.package || page.tr("pacnew.unknown")).replace("%4", page.tr(page.selectedPacnew.locally_modified === true ? "pacnew.modifiedYes" : page.selectedPacnew.locally_modified === false ? "pacnew.modifiedNo" : "pacnew.modifiedUnknown")) : ""
                }
                Note {
                    visible: page.selectedPacnew !== null
                    text: page.selectedPacnew ? page.tr("pacnew.diff." + page.selectedPacnew.diff_status) : ""
                }
                ScrollView {
                    visible: page.selectedPacnew && page.selectedPacnew.diff_status === "ok"
                    width: pacnewContent.width; height: 260; clip: true
                    TextArea {
                        readOnly: true; selectByMouse: true; wrapMode: TextEdit.NoWrap
                        text: page.selectedPacnew ? page.selectedPacnew.diff : ""
                        color: page.foreground; font.family: "monospace"; font.pixelSize: UiI.UiScale.px(12)
                        background: Rectangle { color: page.dark ? "#101010" : "#ffffff"; border.color: page.lineColor; radius: 6 }
                    }
                }
            }
        }
        Rectangle {
            width: parent.width; height: desktopStateColumn.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: desktopStateColumn; x: 16; y: 16; width: parent.width - 32; spacing: 8
                Text { text: page.tr("desktopState.title"); color: page.foreground; font.bold: true; font.pixelSize: UiI.UiScale.px(15) }
                Note {
                    text: !page.desktopStateReady ? page.tr("desktopState.unavailable")
                        : (page.desktopErrors.length ? page.desktopErrors : page.tr("desktopState.noErrors"))
                    color: page.desktopErrors.length ? "#e8a020" : page.secondary
                }
                Note {
                    visible: page.desktopStateReady
                    text: page.tr("desktopState.plugins") + " — hyprbars: " + (page.desktopPlugins.hyprbars ? page.tr("desktopState.loaded") : page.tr("desktopState.missing"))
                        + ", hyprdrag: " + (page.desktopPlugins.hyprdrag ? page.tr("desktopState.loaded") : page.tr("desktopState.missing"))
                    color: page.desktopPlugins.hyprbars && page.desktopPlugins.hyprdrag ? page.secondary : "#e8a020"
                }
            }
        }
        Row {
            width: parent.width; spacing: 8
            Repeater {
                model: [
                    {key: "downloads", label: page.tr("maintenance.groupDownloads")},
                    {key: "repair", label: page.tr("maintenance.groupRepair")}
                ]
                delegate: Tools.SystemToolsButton {
                    required property var modelData
                    width: (content.width - 8) / 2
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
                Note { visible: page.logPath.length > 0; text: page.tr("systemTools.log") + " " + page.logPath; font.pixelSize: UiI.UiScale.px(11) }
                Tools.SystemToolsButton { settingsMenu: page.settingsMenu; visible: page.detailText.length > 0; text: page.tr("systemTools.details"); onClicked: page.showDetails = !page.showDetails }
                Note { visible: page.showDetails; text: page.detailText; font.pixelSize: UiI.UiScale.px(12) }
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
                {action: "failed", title: "maintenance.failed", hint: "maintenance.failedHint", tool: "", confirmation: ""}
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
                    Text { width: parent.width; text: page.tr(card.modelData.title); color: page.foreground; font.pixelSize: UiI.UiScale.px(15); font.bold: true; wrapMode: Text.WordWrap }
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
