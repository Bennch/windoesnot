import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang
import "../i18n" as UiI

// File backup (windoesnot-filebackup): status, target, schedule, sources, browse and restore.
Item {
    id: card
    objectName: "fileBackupCard"
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    readonly property int radius: settingsMenu ? settingsMenu.borderRadius : 10
    property bool autoLoad: true
    readonly property string cli: "windoesnot-filebackup"

    width: parent ? parent.width : 600
    height: column.height

    // State
    property var info: ({})
    property var config: ({})
    property var drives: []
    property var points: []
    property var entries: []
    property string errorText: ""
    property string resultText: ""
    property bool smbOpen: false
    property string smbMessage: ""
    property bool browsing: false
    property string pointId: ""
    property string browsePath: ""
    property string restoreRel: ""
    readonly property var status: info.status || ({})
    readonly property bool running: status.state === "running" || runProcess.running || systemProcess.running
    readonly property bool available: info.available === true
    readonly property var quickFolders: ["Documents", "Pictures", "Music", "Videos", "Desktop", "Downloads"]

    readonly property string systemRestoreCommand: "pkexec /usr/lib/windoesnot/snapshot_export.py restore '{\"dir\":\"<WinDoesNot-Backup/" + tr("systemHostPlaceholder") + "/system>\",\"id\":<" + tr("systemNumberPlaceholder") + ">,\"into\":\"<" + tr("systemIntoPlaceholder") + ">\"}'"
    function tr(key) { return Lang.get("filebackup." + key, _lang) }
    function parse(text) {
        try { return JSON.parse(text) } catch (e) { return null }
    }
    function formatSize(bytes) {
        const n = Number(bytes || 0)
        if (n < 1024 * 1024) return Math.round(n / 1024) + " KiB"
        if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MiB"
        return (n / (1024 * 1024 * 1024)).toFixed(1) + " GiB"
    }
    function relativeTime(seconds) {
        const diff = Math.max(0, Date.now() / 1000 - seconds)
        if (diff < 90) return tr("ago.now")
        if (diff < 5400) return tr("ago.min").replace("%1", Math.round(diff / 60))
        if (diff < 129600) return tr("ago.hour").replace("%1", Math.round(diff / 3600))
        return tr("ago.day").replace("%1", Math.round(diff / 86400))
    }
    function absoluteTime(seconds) {
        return new Date(seconds * 1000).toLocaleString(Qt.locale(_lang), "dd.MM.yyyy HH:mm")
    }
    function errorMessage(code) {
        const text = String(code || "")
        return text === "unavailable" ? tr("offline") : text
    }
    function targetLabel() {
        const target = config.target
        if (!target) return tr("targetNone")
        if (target.kind === "smb") return target.address
        return target.label || target.uuid
    }
    readonly property string statusLine: {
        if (running && status.message === "system") return tr("systemRunning")
        if (running) return tr("running").replace("%1", Math.round(Number(status.percent || 0)))
        if (!config.target) return tr("targetNone")
        if (!available) return tr("offline")
        if (status.state === "error" && status.error) return tr("failed") + " " + errorMessage(status.error)
        const last = Number(status.last_success || 0)
        const when = last > 0 ? tr("last").replace("%1", relativeTime(last)).replace("%2", absoluteTime(last)) : tr("never")
        return when + " - " + tr("points").replace("%1", Number(info.points || 0))
            + (info.systemAvailable && config.system ? " - " + tr("systemPoints").replace("%1", Number(info.systemPoints || 0)) : "")
    }

    // Data acceptance (also used by tests)
    function acceptStatus(data) {
        if (!data || data.error) { errorText = data ? errorMessage(data.error) : ""; return }
        errorText = ""
        info = data
        config = data.config || ({})
    }
    function acceptDrives(list) { drives = Array.isArray(list) ? list : [] }
    function acceptPoints(list) {
        if (Array.isArray(list)) { points = list; errorText = "" }
        else if (list && list.error) { points = []; errorText = errorMessage(list.error) }
    }
    function acceptBrowse(list) {
        if (Array.isArray(list)) { entries = list; errorText = "" }
        else if (list && list.error) { entries = []; errorText = errorMessage(list.error) }
    }

    // Commands
    function refresh() {
        if (!statusProcess.running) statusProcess.running = true
        if (!drivesProcess.running) drivesProcess.running = true
    }
    function saveConfig(patch) {
        if (configProcess.running) return
        configProcess.command = [cli, "config", JSON.stringify(patch)]
        configProcess.running = true
    }
    function chooseDrive(drive) {
        saveConfig({target: {kind: "drive", uuid: drive.uuid, label: drive.label, folder: ""}})
    }
    function connectSmb() {
        const address = smbAddress.text.trim()
        if (address.indexOf("smb://") !== 0 || mountProcess.running) { smbMessage = tr("smbFailed"); return }
        smbMessage = tr("smbConnecting")
        mountProcess.command = ["pkexec", "/usr/bin/windoesnot-filebackup-mount", "connect", address, smbUser.text.trim()]
        mountProcess.running = true
    }
    function startBackup() {
        if (runProcess.running || !available) return
        resultText = ""
        runProcess.running = true
        pollTimer.start()
    }
    function startSystemExport() {
        if (systemProcess.running || runProcess.running || !available) return
        resultText = ""
        systemProcess.running = true
    }
    function toggleSource(path, on) {
        const current = (config.sources || ["~"]).slice()
        let next = current.filter(s => s !== path)
        if (on) next.push(path)
        if (next.length === 0) return
        saveConfig({sources: next})
    }
    function hasSource(path) { return (config.sources || []).indexOf(path) >= 0 }
    function openBrowser() {
        browsing = true; pointId = ""; browsePath = ""; entries = []; resultText = ""
        listProcess.running = true
    }
    function openPoint(id) { pointId = id; browsePath = ""; loadFolder() }
    function loadFolder() {
        browseProcess.command = browsePath ? [cli, "browse", pointId, browsePath] : [cli, "browse", pointId]
        browseProcess.running = true
    }
    function enter(name) { browsePath = browsePath ? browsePath + "/" + name : name; loadFolder() }
    function up() {
        const parts = browsePath.split("/"); parts.pop(); browsePath = parts.join("/"); loadFolder()
    }
    function askRestore(name) {
        restoreRel = browsePath ? browsePath + "/" + name : name
        restorePrompt.open()
    }
    function pointTitle(point) {
        if (point.kind === "mirror") return tr("pointLatest")
        return absoluteTime(new Date(point.time).getTime() / 1000)
    }

    Component.onCompleted: if (autoLoad) refresh()
    onVisibleChanged: if (visible && autoLoad) refresh()

    Timer {
        id: pollTimer
        interval: 2000; repeat: true
        running: card.running
        onTriggered: if (!statusProcess.running) statusProcess.running = true
    }

    Process {
        id: statusProcess
        command: [card.cli, "status"]
        stdout: StdioCollector { onStreamFinished: card.acceptStatus(card.parse(text)) }
    }
    Process {
        id: drivesProcess
        command: [card.cli, "drives"]
        stdout: StdioCollector { onStreamFinished: card.acceptDrives(card.parse(text)) }
    }
    Process {
        id: configProcess
        stdout: StdioCollector { onStreamFinished: { const data = card.parse(text); if (data && data.error) card.errorText = data.error; card.refresh() } }
    }
    Process {
        id: runProcess
        command: [card.cli, "run"]
        stdout: StdioCollector { onStreamFinished: { const data = card.parse(text); if (data && data.error) card.errorText = card.errorMessage(data.error); card.refresh() } }
        onExited: card.refresh()
    }
    Process {
        id: systemProcess
        command: [card.cli, "system-export"]
        stdout: StdioCollector { onStreamFinished: { const data = card.parse(text); if (data && data.error) card.errorText = card.errorMessage(data.error); card.refresh() } }
        onExited: card.refresh()
    }
    Process {
        id: listProcess
        command: [card.cli, "list"]
        stdout: StdioCollector { onStreamFinished: card.acceptPoints(card.parse(text)) }
    }
    Process {
        id: browseProcess
        stdout: StdioCollector { onStreamFinished: card.acceptBrowse(card.parse(text)) }
    }
    Process {
        id: restoreProcess
        stdout: StdioCollector {
            onStreamFinished: {
                const data = card.parse(text)
                if (data && data.restored) card.resultText = card.tr("restored").replace("%1", data.restored)
                else card.errorText = data && data.error ? card.errorMessage(data.error) : card.tr("restoreFailed")
            }
        }
    }
    Process {
        id: mountProcess
        stdinEnabled: true
        onStarted: { write(smbPassword.text + "\n"); smbPassword.text = "" }
        onExited: (code) => {
            if (code === 0) {
                card.smbMessage = card.tr("smbConnected")
                card.saveConfig({target: {kind: "smb", address: smbAddress.text.trim(), folder: ""}})
            } else card.smbMessage = card.tr("smbFailed")
        }
    }

    Tools.SystemToolsConfirm {
        id: restorePrompt
        settingsMenu: card.settingsMenu
        title: card.tr("restoreConfirm")
        description: card.tr("restoreHint") + "\n\n" + card.restoreRel
        confirmText: card.tr("restore")
        destructive: true
        onAccepted: {
            restoreProcess.command = [card.cli, "restore", card.pointId, card.restoreRel]
            restoreProcess.running = true
        }
    }

    // Reusable pieces
    component Heading: Text {
        width: parent ? parent.width : 100
        font.pixelSize: UiI.UiScale.px(14); font.bold: true; wrapMode: Text.WordWrap
        color: card.dark ? "#ffffff" : "#1a1a1a"
    }
    component Note: Text {
        width: parent ? parent.width : 100
        font.pixelSize: UiI.UiScale.px(12); wrapMode: Text.WordWrap
        color: card.dark ? "#aaaaaa" : "#555555"
    }
    component Field: TextField {
        width: parent ? parent.width : 100
        implicitHeight: 36; font.pixelSize: UiI.UiScale.px(13)
        color: card.dark ? "#ffffff" : "#1a1a1a"
        placeholderTextColor: card.dark ? "#777777" : "#999999"
        background: Rectangle {
            radius: 6; color: card.dark ? "#1a1a1a" : "#ffffff"
            border.width: 1; border.color: parent.activeFocus ? card.accent : (card.dark ? "#444444" : "#cccccc")
        }
    }
    component Box: Rectangle {
        width: parent ? parent.width : 100
        radius: card.radius
        color: card.dark ? "#1a1a1a" : "#ffffff"
        border.width: 1; border.color: card.dark ? "#333333" : "#dddddd"
    }

    Column {
        id: column
        width: parent.width
        spacing: 14

        Heading { text: card.tr("title"); font.pixelSize: UiI.UiScale.px(18) }

        // Status
        Box {
            height: statusColumn.height + 28
            Column {
                id: statusColumn
                x: 16; y: 14; width: parent.width - 32; spacing: 8
                Text {
                    objectName: "fileBackupStatus"
                    width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(13)
                    color: card.dark ? "#eeeeee" : "#222222"
                    text: card.statusLine
                }
                Text {
                    visible: card.config.target !== null && card.config.target !== undefined
                    width: parent.width; font.pixelSize: UiI.UiScale.px(12); wrapMode: Text.WordWrap
                    color: card.dark ? "#aaaaaa" : "#555555"
                    text: card.tr("targetIs").replace("%1", card.targetLabel())
                }
                Rectangle {
                    visible: card.running
                    width: parent.width; height: 6; radius: 3
                    color: card.dark ? "#333333" : "#dddddd"
                    Rectangle { width: parent.width * Math.min(1, Number(card.status.percent || 0) / 100); height: parent.height; radius: 3; color: card.accent }
                }
                Text {
                    objectName: "fileBackupError"
                    visible: card.errorText !== ""
                    width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(12)
                    color: card.dark ? "#ff9999" : "#c23838"
                    text: card.errorText
                }
                Text {
                    visible: card.resultText !== ""
                    width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: UiI.UiScale.px(12)
                    color: card.accent
                    text: card.resultText
                }
                Tools.SystemToolsButton {
                    objectName: "fileBackupRunButton"
                    settingsMenu: card.settingsMenu; primary: true
                    text: card.running ? card.tr("runningShort") : card.tr("runNow")
                    enabled: card.available && !card.running
                    onClicked: card.startBackup()
                }
            }
        }

        // Target
        Heading { text: card.tr("target") }
        Box {
            height: targetColumn.height + 28
            Column {
                id: targetColumn
                x: 16; y: 14; width: parent.width - 32; spacing: 8
                Note { visible: card.drives.length === 0; text: card.tr("noDrives") }
                Repeater {
                    model: card.drives
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        objectName: "fileBackupDrive-" + index
                        readonly property bool chosen: card.config.target && card.config.target.kind === "drive" && card.config.target.uuid === modelData.uuid
                        width: targetColumn.width; height: 48; radius: 6
                        color: chosen ? Qt.alpha(card.accent, 0.2) : (card.dark ? "#222222" : "#f5f5f5")
                        border.width: 1; border.color: chosen ? card.accent : (card.dark ? "#333333" : "#dddddd")
                        Column {
                            x: 12; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 130
                            Text { width: parent.width; elide: Text.ElideRight; font.pixelSize: UiI.UiScale.px(13); font.bold: true; color: card.dark ? "#eeeeee" : "#222222"; text: modelData.label }
                            Text { width: parent.width; elide: Text.ElideRight; font.pixelSize: UiI.UiScale.px(11); color: card.dark ? "#aaaaaa" : "#555555"; text: card.formatSize(modelData.size) + " - " + modelData.filesystem }
                        }
                        Tools.SystemToolsButton {
                            anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                            settingsMenu: card.settingsMenu
                            text: parent.chosen ? card.tr("selected") : card.tr("use")
                            enabled: !parent.chosen
                            onClicked: card.chooseDrive(modelData)
                        }
                    }
                }
                Row {
                    spacing: 8
                    Tools.SystemToolsButton { settingsMenu: card.settingsMenu; text: card.tr("rescan"); onClicked: card.refresh() }
                    Tools.SystemToolsButton { objectName: "fileBackupSmbToggle"; settingsMenu: card.settingsMenu; text: card.tr("smbTitle"); onClicked: card.smbOpen = !card.smbOpen }
                }
                Column {
                    visible: card.smbOpen
                    width: parent.width; spacing: 8
                    Field { id: smbAddress; objectName: "fileBackupSmbAddress"; placeholderText: card.tr("smbAddress") }
                    Field { id: smbUser; objectName: "fileBackupSmbUser"; placeholderText: card.tr("smbUser") }
                    Field { id: smbPassword; objectName: "fileBackupSmbPassword"; placeholderText: card.tr("smbPassword"); echoMode: TextInput.Password }
                    Row {
                        spacing: 10
                        Tools.SystemToolsButton { objectName: "fileBackupSmbConnect"; settingsMenu: card.settingsMenu; primary: true; text: card.tr("smbConnect"); enabled: !mountProcess.running; onClicked: card.connectSmb() }
                        Text { anchors.verticalCenter: parent.verticalCenter; font.pixelSize: UiI.UiScale.px(12); color: card.dark ? "#cccccc" : "#444444"; text: card.smbMessage }
                    }
                }
            }
        }

        // Automatic backup, schedule, sources
        Heading { text: card.tr("automatic") }
        Box {
            height: autoColumn.height + 28
            Column {
                id: autoColumn
                x: 16; y: 14; width: parent.width - 32; spacing: 8
                Tools.SystemToolsToggle {
                    objectName: "fileBackupEnabled"
                    settingsMenu: card.settingsMenu
                    text: card.tr("enabled")
                    checked: card.config.enabled === true
                    onToggled: card.saveConfig({enabled: checked})
                }
                Text { font.pixelSize: UiI.UiScale.px(12); color: card.dark ? "#aaaaaa" : "#555555"; text: card.tr("schedule") }
                Flow {
                    width: parent.width; spacing: 8
                    Repeater {
                        model: ["hourly", "daily", "weekly", "manual"]
                        delegate: Tools.SystemToolsButton {
                            required property string modelData
                            objectName: "fileBackupSchedule-" + modelData
                            settingsMenu: card.settingsMenu
                            primary: card.config.schedule === modelData
                            text: card.tr("sched." + modelData)
                            onClicked: card.saveConfig({schedule: modelData})
                        }
                    }
                }
                Tools.SystemToolsToggle {
                    objectName: "fileBackupSystem"
                    visible: card.info.systemAvailable === true
                    settingsMenu: card.settingsMenu
                    text: card.tr("systemEnable")
                    checked: card.config.system === true
                    onToggled: card.saveConfig({system: checked})
                }
                Note { objectName: "fileBackupSystemHint"; visible: card.info.systemAvailable === true; text: card.tr("systemHint") }
                Tools.SystemToolsButton {
                    objectName: "fileBackupSystemNow"
                    visible: card.info.systemAvailable === true
                    settingsMenu: card.settingsMenu
                    text: card.tr("systemNow")
                    enabled: card.available && !card.running
                    onClicked: card.startSystemExport()
                }
                Text { font.pixelSize: UiI.UiScale.px(12); color: card.dark ? "#aaaaaa" : "#555555"; text: card.tr("what") }
                CheckBox {
                    objectName: "fileBackupHome"
                    text: card.tr("home")
                    checked: card.hasSource("~")
                    onClicked: card.toggleSource("~", checked)
                    contentItem: Text { leftPadding: 28; text: parent.text; font.pixelSize: UiI.UiScale.px(13); color: card.dark ? "#eeeeee" : "#222222"; verticalAlignment: Text.AlignVCenter }
                }
                Flow {
                    width: parent.width; spacing: 4
                    Repeater {
                        model: card.quickFolders
                        delegate: CheckBox {
                            required property string modelData
                            objectName: "fileBackupFolder-" + modelData
                            enabled: !card.hasSource("~")
                            text: card.tr("folder." + modelData)
                            checked: card.hasSource("~/" + modelData)
                            onClicked: card.toggleSource("~/" + modelData, checked)
                            contentItem: Text { leftPadding: 28; rightPadding: 12; text: parent.text; font.pixelSize: UiI.UiScale.px(13); color: card.dark ? "#eeeeee" : "#222222"; verticalAlignment: Text.AlignVCenter; opacity: parent.enabled ? 1 : 0.5 }
                        }
                    }
                }
            }
        }

        // Browse and restore
        Heading { text: card.tr("browseTitle") }
        Box {
            height: browseColumn.height + 28
            Column {
                id: browseColumn
                x: 16; y: 14; width: parent.width - 32; spacing: 8
                Tools.SystemToolsButton {
                    objectName: "fileBackupBrowse"
                    settingsMenu: card.settingsMenu
                    visible: !card.browsing
                    text: card.tr("browseOpen")
                    enabled: card.available
                    onClicked: card.openBrowser()
                }
                Column {
                    visible: card.browsing
                    width: parent.width; spacing: 8
                    Row {
                        spacing: 8
                        Tools.SystemToolsButton { settingsMenu: card.settingsMenu; text: card.tr("close"); onClicked: card.browsing = false }
                        Tools.SystemToolsButton { settingsMenu: card.settingsMenu; visible: card.pointId !== ""; text: card.tr("up"); onClicked: card.browsePath ? card.up() : (card.pointId = "") }
                    }
                    Note { visible: card.pointId === "" && card.points.length === 0; text: card.tr("noPoints") }
                    Note { visible: card.pointId !== ""; text: "/" + card.browsePath }
                    Note { visible: card.pointId !== "" && card.entries.length === 0; text: card.tr("emptyFolder") }
                    ListView {
                        objectName: "fileBackupList"
                        width: parent.width
                        height: Math.min(300, count * 40)
                        clip: true
                        model: card.pointId === "" ? card.points : card.entries
                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: ListView.view.width; height: 40
                            color: index % 2 === 0 ? (card.dark ? "#1e1e1e" : "#fafafa") : (card.dark ? "#1a1a1a" : "#ffffff")
                            readonly property bool isPoint: card.pointId === ""
                            Text {
                                x: 8; width: parent.width - 150; height: parent.height
                                verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; font.pixelSize: UiI.UiScale.px(13)
                                color: card.dark ? "#eeeeee" : "#222222"
                                text: isPoint ? card.pointTitle(modelData) : (modelData.dir ? "[ ] " : "") + modelData.name
                            }
                            MouseArea {
                                anchors.fill: parent; anchors.rightMargin: 100
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (parent.isPoint) card.openPoint(modelData.id)
                                    else if (modelData.dir) card.enter(modelData.name)
                                }
                            }
                            Tools.SystemToolsButton {
                                visible: !parent.isPoint
                                anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
                                settingsMenu: card.settingsMenu
                                text: card.tr("restore")
                                onClicked: card.askRestore(modelData.name)
                            }
                        }
                    }
                }
            }
        }

        // Honest notes
        Note { objectName: "fileBackupHints"; text: card.tr("hintEncrypt") + "\n" + card.tr("hintFat") + "\n" + card.tr("hintSystem")
            + (card.info.systemAvailable === true ? "\n" + card.tr("systemRestoreHint") + "\n" + card.systemRestoreCommand : "") }
    }
}
