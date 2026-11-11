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
    property string logPath: ""
    property string pendingAction: ""
    property var pendingArgs: ({})
    property string pendingDescription: ""
    // Desired install state per package. Entries are only kept when changed.
    property var selectedKernelStates: ({})
    property var queuedKernelActions: []
    width: parent ? parent.width : 650
    height: content.height

    function tr(key) { return Lang.get(key, _lang) }
    function kernelCategory(name) {
        if (name.indexOf("-lts") >= 0) return tr("kernel.longterm")
        if (name.indexOf("-rt-") >= 0) return tr("kernel.realtime")
        if (name.indexOf("-server") >= 0) return tr("kernel.server")
        return tr("kernel.stable")
    }
    function acceptStatus(data) {
        state = data
        selectedKernelStates = ({})
        ready = true
        const current = data.scx.schedulers.indexOf(data.scx.defaultScheduler)
        scheduler.currentIndex = Math.max(0, current)
        mode.currentIndex = Math.max(0, ["Auto", "Gaming", "PowerSave", "LowLatency", "Server"].indexOf(data.scx.defaultMode))
        onBoot.checked = data.scx.enabled === true
    }
    function desiredInstalled(kernel) {
        return Object.prototype.hasOwnProperty.call(selectedKernelStates, kernel.name)
            ? selectedKernelStates[kernel.name] : !!kernel.installed
    }
    function setDesiredInstalled(kernel, desired) {
        if (!kernel.selectable || (kernel.running && !desired)) return
        const next = ({})
        for (const name in selectedKernelStates) next[name] = selectedKernelStates[name]
        if (desired === !!kernel.installed) delete next[kernel.name]
        else next[kernel.name] = desired
        selectedKernelStates = next
    }
    function kernelChanges() {
        return state.kernels.filter(function(kernel) {
            return kernel.selectable && desiredInstalled(kernel) !== !!kernel.installed
        }).map(function(kernel) {
            return {action: desiredInstalled(kernel) ? "kernel-install" : "kernel-remove", name: kernel.name}
        })
    }
    function requestKernelChanges() {
        const changes = kernelChanges()
        if (!changes.length || busy || !ready || state.live) return
        queuedKernelActions = changes
        pendingAction = "kernel-batch"
        pendingArgs = ({})
        pendingDescription = changes.map(function(change) {
            return (change.action === "kernel-install" ? "+ " : "− ") + change.name
        }).join("\n") + "\n\n" + tr("kernel.confirmBatch")
        confirmation.open()
    }
    function runNextKernelAction() {
        if (!queuedKernelActions.length) {
            runAction("kernel-status", {})
            return
        }
        const change = queuedKernelActions.shift()
        runAction(change.action, {kernel: change.name})
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
                    if ((operation === "kernel-install" || operation === "kernel-remove") && queuedKernelActions.length)
                        runNextKernelAction()
                    else
                        runAction("kernel-status", {})
                }
            } else {
                logPath = data.log || ""
                resultKey = code === 126 ? "systemTools.cancelled" : (operation === "kernel-status" ? "kernel.statusFailed" : "systemTools.failed")
                resultDetail = code === 126 ? "" : (data.error || errors.text.trim() || output.text.trim())
                    + (data.detail ? "\n" + data.detail : "")
                queuedKernelActions = []
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
        Note { visible: page.resultDetail.length > 0; text: page.resultDetail }
        Note { visible: page.logPath.length > 0; text: page.tr("systemTools.log") + " " + page.logPath }
        Note { visible: page.rebootNeeded; text: page.tr("kernel.reboot"); color: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
        Heading { text: page.tr("kernel.kernels") }
        Note { text: page.tr("kernel.installHint") }
        Note { visible: page.ready && !page.state.bootloader; text: page.tr("kernel.noLoader") }
        Note { visible: page.ready && !page.state.kernels.length; text: page.tr("kernel.empty") }
        Rectangle {
            id: kernelTable
            width: content.width
            height: tableContent.implicitHeight + 2
            radius: settingsMenu ? settingsMenu.borderRadius : 8
            clip: true
            color: page.dark ? "#17191b" : "#f7f7f7"
            border.width: 1
            border.color: page.dark ? "#454a4d" : "#c8c8c8"
            readonly property real chooseWidth: 58
            readonly property real packageWidth: Math.max(180, width * 0.46)
            readonly property real versionWidth: Math.max(104, width * 0.22)
            readonly property real categoryWidth: width - chooseWidth - packageWidth - versionWidth
            Column {
                id: tableContent
                width: parent.width
                spacing: 0
                Rectangle {
                    width: parent.width; height: 38
                    color: page.dark ? "#2c3034" : "#e7e7e7"
                    Row {
                        anchors.fill: parent
                        Text { width: kernelTable.chooseWidth; text: page.tr("kernel.choose"); color: page.foreground; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter }
                        Text { width: kernelTable.packageWidth; text: page.tr("kernel.package"); color: page.foreground; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 8 }
                        Text { width: kernelTable.versionWidth; text: page.tr("kernel.version"); color: page.foreground; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 8 }
                        Text { width: kernelTable.categoryWidth; text: page.tr("kernel.category"); color: page.foreground; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 8 }
                    }
                }
                Repeater {
                    model: page.state.kernels
                    delegate: Rectangle {
                        id: kernelRow
                        required property var modelData
                        width: kernelTable.width; height: 42
                        color: modelData.running ? (page.dark ? "#2c2521" : "#fff0e8") : "transparent"
                        border.width: 0
                        Row {
                            anchors.fill: parent
                            CheckBox {
                                id: chooseBox
                                objectName: "kernelChoice-" + modelData.name
                                width: kernelTable.chooseWidth; height: parent.height
                                enabled: page.ready && !page.busy && !page.state.live && !!page.state.bootloader && modelData.selectable
                                    && !modelData.running
                                checked: page.desiredInstalled(modelData)
                                onToggled: page.setDesiredInstalled(modelData, checked)
                                indicator: Rectangle {
                                    x: (parent.width - width) / 2; y: (parent.height - height) / 2
                                    width: 16; height: 16; radius: 4
                                    color: chooseBox.checked ? (settingsMenu ? settingsMenu.accentColor : "#fe6f2d") : (page.dark ? "#30353a" : "#ffffff")
                                    border.width: 1; border.color: page.dark ? "#6a7176" : "#929292"
                                    Text { anchors.centerIn: parent; visible: chooseBox.checked; text: "✓"; color: "white"; font.bold: true; font.pixelSize: 12 }
                                }
                            }
                            Text { width: kernelTable.packageWidth; height: parent.height; text: "cachyos/" + modelData.name; color: page.foreground; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 8; elide: Text.ElideRight }
                            Text { width: kernelTable.versionWidth; height: parent.height; text: modelData.installed || modelData.available || "—"; color: page.foreground; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 8; elide: Text.ElideRight }
                            Text { width: kernelTable.categoryWidth; height: parent.height; text: modelData.running ? page.tr("kernel.current") : page.kernelCategory(modelData.name); color: modelData.running ? (settingsMenu ? settingsMenu.accentColor : "#fe6f2d") : page.secondary; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 8; elide: Text.ElideRight }
                        }
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: page.dark ? "#303438" : "#dddddd" }
                    }
                }
            }
        }
        Row {
            width: parent.width
            spacing: 12
            Item {
                width: parent.width - executeChanges.width - parent.spacing
                height: executeChanges.height
                Note { anchors.verticalCenter: parent.verticalCenter; text: page.kernelChanges().length ? page.tr("kernel.changesPending") : page.tr("kernel.tableHint") }
            }
            ActionButton {
                id: executeChanges
                primary: true
                visible: page.kernelChanges().length > 0
                text: page.tr("kernel.execute")
                onClicked: page.requestKernelChanges()
            }
        }
        Heading { text: page.tr("kernel.scheduler") }
        Note { text: page.tr("kernel.schedulerHint") }
        Note { visible: page.ready && !page.state.scx.supported; text: page.tr("kernel.noScx") }
        Column {
            visible: page.ready && page.state.scx.supported === true
            width: parent.width; spacing: 12
            Row {
                width: parent.width; spacing: 12
                Note { width: parent.width - schedulerState.width - parent.spacing; text: page.tr("kernel.schedulerActive") }
                Text {
                    id: schedulerState
                    width: Math.min(220, implicitWidth)
                    text: page.state.scx.current || page.state.scx.state || page.tr("kernel.none")
                    color: page.foreground; font.pixelSize: 13; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight
                }
            }
            ActionButton {
                visible: !page.state.scx.installed || !page.state.scx.schedulers.length
                text: page.tr("kernel.installScx")
                onClicked: page.requestAction("scx-install", {}, page.tr("kernel.confirmScxInstall"))
            }
            Row {
                width: parent.width; spacing: 12
                Note { width: parent.width - scheduler.width - parent.spacing; text: page.tr("kernel.schedulerChoice") }
                Tools.SystemToolsChoice { settingsMenu: page.settingsMenu; id: scheduler; width: Math.min(220, parent.width); model: page.state.scx.schedulers; enabled: !page.busy && !page.state.live }
            }
            Row {
                width: parent.width; spacing: 12
                Note { width: parent.width - mode.width - parent.spacing; text: page.tr("kernel.modeChoice") }
                Tools.SystemToolsChoice {
                    settingsMenu: page.settingsMenu
                    id: mode; objectName: "systemToolsMode"; width: Math.min(220, parent.width)
                    model: ["Auto", "Gaming", "PowerSave", "LowLatency", "Server"]
                    labelPrefix: "kernel.mode"
                    enabled: !page.busy && !page.state.live
                }
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
        onAccepted: {
            if (page.pendingAction === "kernel-batch") page.runNextKernelAction()
            else page.runAction(page.pendingAction, page.pendingArgs)
        }
    }
}
