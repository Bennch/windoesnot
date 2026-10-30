import QtQuick
import QtQuick.Controls
import "." as Tools
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: settingsMenu ? settingsMenu.darkMode : true
    readonly property color foreground: dark ? "#eeeeee" : "#202020"
    readonly property color secondary: dark ? "#bbbbbb" : "#555555"
    property bool autoLoad: true
    property bool busy: false
    property bool ready: false
    property bool rebootNeeded: false
    property var state: ({kernels: [], repositories: [], scx: {schedulers: []}})
    property string resultKey: ""
    property string resultDetail: ""
    readonly property string resultText: resultKey ? tr(resultKey) : ""
    property bool detailsExpanded: false
    property string logPath: ""
    property string pendingAction: ""
    property var pendingArgs: ({})
    property string pendingDescription: ""
    width: parent ? parent.width : 650
    height: content.height

    function tr(key) { return Lang.get(key, _lang) }
    function graphicsName(profiles) {
        return (profiles || "").split(", ").map(function(profile) {
            if (profile.indexOf("nvidia") === 0) return "NVIDIA"
            const labels = {intel: "Intel", amd: "AMD", qemu: page.tr("kernel.virtualMachine"),
                virtualbox: "VirtualBox", vmware: "VMware", nouveau: "NVIDIA (nouveau)"}
            return labels[profile] || profile || page.tr("kernel.unknown")
        }).join(", ")
    }
    function acceptStatus(data) {
        state = data
        ready = true
        const current = data.scx.schedulers.indexOf(data.scx.defaultScheduler)
        scheduler.currentIndex = Math.max(0, current)
        mode.currentIndex = Math.max(0, ["Auto", "Gaming", "PowerSave", "LowLatency", "Server"].indexOf(data.scx.defaultMode))
        onBoot.checked = data.scx.enabled === true
    }
    function requestAction(action, args, description) {
        if (busy || !ready || state.live) return
        pendingAction = action; pendingArgs = args; pendingDescription = description
        confirmation.open()
    }
    function runAction(action, args) {
        if (busy) return
        busy = true
        worker.operation = action
        if (action !== "kernel-status") {
            resultKey = ""; resultDetail = ""; logPath = ""
        }
        worker.command = (action === "kernel-status" ? ["/usr/bin/python3", "-I"] : ["/usr/bin/pkexec", "--disable-internal-agent"])
            .concat(["/usr/lib/windoesnot/system_tools.py", action, JSON.stringify(args)])
        worker.running = true
    }
    Component.onCompleted: if (autoLoad) runAction("kernel-status", {})
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
                if (operation === "kernel-status") {
                    acceptStatus(data)
                    if (resultKey === "kernel.statusFailed") {
                        resultKey = ""; resultDetail = ""; logPath = ""
                    }
                }
                else {
                    rebootNeeded = rebootNeeded || data.reboot === true
                    logPath = data.log || ""
                    resultKey = "systemTools.done"
                    runAction("kernel-status", {})
                }
            } else {
                logPath = data.log || ""
                resultKey = code === 126 ? "systemTools.cancelled" : (operation === "kernel-status" ? "kernel.statusFailed" : "systemTools.failed")
                resultDetail = code === 126 ? "" : (data.error || errors.text.trim() || output.text.trim())
                    + (data.detail ? "\n" + data.detail : "")
                if (operation !== "kernel-status") runAction("kernel-status", {})
            }
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
    component ActionButton: Tools.SystemToolsButton {
        settingsMenu: page.settingsMenu
        enabled: page.ready && !page.busy && !page.state.live
    }

    Column {
        id: content
        width: parent.width
        spacing: 20
        Note { text: page.tr("kernel.intro") }
        Note { visible: page.state.live === true; text: page.tr("systemTools.live") }
        Note { visible: !page.ready; text: page.busy ? page.tr("systemTools.loading") : page.tr("systemTools.unavailable") }
        BusyIndicator { width: 32; height: 32; running: page.busy; visible: running; palette.highlight: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
        Note { visible: page.resultText.length > 0; text: page.resultText; color: page.foreground }
        Note { visible: page.ready && page.state.catalogAvailable === false; text: page.tr("kernel.catalogMissing") }
        Tools.SystemToolsButton {
            settingsMenu: page.settingsMenu
            text: page.tr(page.detailsExpanded ? "kernel.hideDetails" : "kernel.showDetails")
            onClicked: page.detailsExpanded = !page.detailsExpanded
        }
        Column {
            width: parent.width; spacing: 8; visible: page.detailsExpanded
            Note { visible: page.resultDetail.length > 0; text: page.resultDetail }
            Note { visible: page.logPath.length > 0; text: page.tr("systemTools.log") + " " + page.logPath }
            Note { visible: page.ready; text: page.state.repositories.join(", ") }
        }
        Note { visible: page.rebootNeeded; text: page.tr("kernel.reboot"); color: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
        Heading { text: page.tr("kernel.detected") }
        Rectangle {
            width: parent.width
            height: detectedRows.height + 32
            visible: page.ready
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1
            border.color: page.dark ? "#3a3a3a" : "#d0d0d0"
            Column {
                id: detectedRows
                x: 16; y: 16; width: parent.width - 32; spacing: 16
                Repeater {
                    model: page.ready ? [
                        {label: page.tr("kernel.cpu"), value: page.state.cpuLevel},
                        {label: page.tr("kernel.optimized"), value: page.tr(page.state.repositories.length ? "kernel.optimizationsOn" : "kernel.optimizationsDefault")},
                        {label: page.tr("kernel.running"), value: page.state.release},
                        {label: page.tr("kernel.graphics"), value: page.graphicsName(page.state.drivers)}
                    ] : []
                    delegate: Column {
                        required property var modelData
                        width: detectedRows.width; spacing: 4
                        Note { text: modelData.label }
                        Text { width: parent.width; text: modelData.value; color: page.foreground; font.pixelSize: 14; wrapMode: Text.WordWrap }
                    }
                }
            }
        }
        Heading { text: page.tr("kernel.kernels") }
        Note { text: page.tr("kernel.installHint") }
        Note { visible: page.ready && !page.state.bootloader; text: page.tr("kernel.noLoader") }
        Note { visible: page.ready && !page.state.kernels.length; text: page.tr("kernel.empty") }
        Repeater {
            model: page.state.kernels
            delegate: Rectangle {
                id: kernelRow
                required property var modelData
                width: content.width
                height: kernelContent.height + 32
                radius: settingsMenu ? settingsMenu.borderRadius : 10
                color: page.dark ? "#141414" : "#f5f5f5"
                border.width: 1
                border.color: page.dark ? "#3a3a3a" : "#d0d0d0"
                Column {
                    id: kernelContent
                    x: 16; y: 16; width: parent.width - 32; spacing: 8
                    Text { width: parent.width; text: kernelRow.modelData.selectable ? page.tr("kernel.name." + kernelRow.modelData.name) : kernelRow.modelData.name; color: page.foreground; font.bold: true; font.pixelSize: 14; wrapMode: Text.WordWrap }
                    Note { text: page.tr(kernelRow.modelData.selectable ? "kernel.description." + kernelRow.modelData.name : "kernel.customDescription") }
                    Note {
                        text: (kernelRow.modelData.installed ? page.tr("kernel.installed") + ": " + kernelRow.modelData.installed : page.tr("kernel.notInstalled"))
                            + (kernelRow.modelData.running ? " · " + page.tr("kernel.inUse") : "")
                            + (kernelRow.modelData.available ? "\n" + page.tr("kernel.available") + ": " + kernelRow.modelData.available : "")
                    }
                    Row {
                        spacing: 8
                        ActionButton {
                            visible: !kernelRow.modelData.installed && !!kernelRow.modelData.available && kernelRow.modelData.selectable
                            enabled: page.ready && !page.busy && !page.state.live && !!page.state.bootloader
                            primary: true
                            text: page.tr("kernel.install")
                            onClicked: page.requestAction("kernel-install", {kernel: kernelRow.modelData.name},
                                kernelRow.modelData.name + "\n\n" + page.tr("kernel.confirmInstall"))
                        }
                        ActionButton {
                            visible: !!kernelRow.modelData.installed
                            enabled: page.ready && !page.busy && !page.state.live && !!page.state.bootloader && kernelRow.modelData.removable
                            text: page.tr("kernel.remove")
                            onClicked: page.requestAction("kernel-remove", {kernel: kernelRow.modelData.name},
                                kernelRow.modelData.name + "\n\n" + page.tr("kernel.confirmRemove"))
                        }
                    }
                }
            }
        }
        Heading { text: page.tr("kernel.scheduler") }
        Note { text: page.tr("kernel.schedulerHint") }
        Note { visible: page.ready && !page.state.scx.supported; text: page.tr("kernel.noScx") }
        Column {
            visible: page.ready && page.state.scx.supported === true
            width: parent.width; spacing: 12
            Note { text: page.tr("kernel.schedulerActive") + ": " + (page.state.scx.current || page.state.scx.state || page.tr("kernel.none")) }
            ActionButton {
                visible: !page.state.scx.installed || !page.state.scx.schedulers.length
                text: page.tr("kernel.installScx")
                onClicked: page.requestAction("scx-install", {}, page.tr("kernel.confirmScxInstall"))
            }
            Tools.SystemToolsChoice { settingsMenu: page.settingsMenu; id: scheduler; width: Math.min(320, parent.width); model: page.state.scx.schedulers; enabled: !page.busy && !page.state.live }
            Tools.SystemToolsChoice {
                settingsMenu: page.settingsMenu
                id: mode; objectName: "systemToolsMode"; width: Math.min(320, parent.width)
                model: ["Auto", "Gaming", "PowerSave", "LowLatency", "Server"]
                labelPrefix: "kernel.mode"
                enabled: !page.busy && !page.state.live
            }
            Tools.SystemToolsToggle { settingsMenu: page.settingsMenu; id: onBoot; text: page.tr("kernel.onBoot"); enabled: !page.busy && !page.state.live }
            ActionButton {
                primary: true
                text: page.tr("kernel.applyScheduler")
                enabled: page.ready && !page.busy && !page.state.live && page.state.scx.installed && scheduler.currentText.length > 0
                onClicked: page.requestAction("scx-set", {scheduler: scheduler.currentText,
                    mode: mode.currentText, onBoot: onBoot.checked},
                    scheduler.currentText + " · " + mode.displayText + "\n" + page.tr(onBoot.checked ? "kernel.persist" : "kernel.sessionOnly"))
            }
            ActionButton {
                text: page.tr("kernel.stopScheduler")
                enabled: page.ready && !page.busy && !page.state.live && (page.state.scx.active || page.state.scx.enabled)
                onClicked: page.requestAction("scx-stop", {}, page.tr("kernel.confirmScxStop"))
            }
        }
    }
    Tools.SystemToolsConfirm {
        id: confirmation
        settingsMenu: page.settingsMenu
        title: page.tr("systemTools.confirm")
        description: page.pendingDescription
        destructive: page.pendingAction === "kernel-remove"
        onAccepted: page.runAction(page.pendingAction, page.pendingArgs)
    }
}
