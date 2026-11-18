import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Controls
import "../settings" as Tools
import "../i18n/Lang.js" as Lang

// Share a folder in the network (Samba usershare), Windows-style: name, read/write, address to copy.
// Backend: windoesnot-share (status, setup, add, remove, set-password). Opened with `qs ipc call windoesnot-share open <path>`.
FloatingWindow {
    id: dialog
    property var settingsMenu: null
    property string folderPath: ""
    property var status: ({installed: true, configured: true, password: false, hostname: "", shares: []})
    property string shareName: ""
    property bool writable: false
    property bool guest: false
    property string passwordText: ""
    property string passwordRepeat: ""
    property string message: ""
    property bool failure: false
    property bool busy: false
    property string resultUnc: ""
    readonly property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    readonly property color textColor: dark ? "#ffffff" : "#1a1a1a"
    readonly property color mutedColor: dark ? "#aaaaaa" : "#666666"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d0d0d0"
    readonly property var existing: {
        for (var i = 0; i < status.shares.length; i++) if (status.shares[i].path === folderPath) return status.shares[i]
        return null
    }
    readonly property bool needsPassword: !guest && !status.password
    visible: false
    implicitWidth: 500
    implicitHeight: content.implicitHeight + 48
    color: dark ? "#1b1b1b" : "#fafafa"
    title: "quickshell-sharedialog"

    function tr(key) { return Lang.get("share." + key, _lang) }
    function baseName(path) { var parts = path.split("/").filter(function(p) { return p !== "" }); return parts.length ? parts[parts.length - 1] : "" }
    function openFor(path) {
        folderPath = path; message = ""; failure = false; resultUnc = ""; passwordText = ""; passwordRepeat = ""
        shareName = baseName(path); writable = false; guest = false
        visible = true
        refresh()
    }
    function refresh() { statusProc.running = true }
    function call(args, stdin) {
        busy = true
        runner.stdinText = stdin || ""
        runner.command = ["windoesnot-share"].concat(args)
        runner.running = true
    }
    function errorText(code) { var k = "error." + code; var v = tr(k); return v === "share." + k ? tr("error.failed") : v }

    Process {
        id: statusProc
        command: ["windoesnot-share", "status"]
        stdout: StdioCollector { id: statusOut }
        onExited: {
            try {
                dialog.status = JSON.parse(statusOut.text)
                if (dialog.existing) { dialog.shareName = dialog.existing.name; dialog.writable = dialog.existing.access === "write"; dialog.guest = dialog.existing.guest; dialog.resultUnc = dialog.existing.unc }
            } catch (e) { dialog.failure = true; dialog.message = dialog.tr("error.failed") }
        }
    }
    Process {
        id: runner
        property string stdinText: ""
        stdinEnabled: true
        stdout: StdioCollector { id: runOut }
        onStarted: { if (stdinText !== "") { write(stdinText + "\n"); stdinEnabled = false } }
        onExited: {
            dialog.busy = false
            var d = {}
            try { d = JSON.parse(runOut.text) } catch (e) { d = {ok: false, error: "failed"} }
            dialog.failure = !d.ok
            if (!d.ok) {
                dialog.message = dialog.errorText(d.error)
                if (d.error === "not-configured") dialog.message = dialog.tr("needsSetup")
            } else {
                dialog.message = dialog.lastDone
                if (d.unc) dialog.resultUnc = d.unc
                dialog.refresh()
            }
            runner.stdinEnabled = true
        }
    }
    property string lastDone: ""

    function share() {
        if (needsPassword) {
            if (passwordText.length < 4) { failure = true; message = tr("passwordShort"); return }
            if (passwordText !== passwordRepeat) { failure = true; message = tr("passwordMismatch"); return }
        }
        stepper.start()
    }
    // Steps: setup (once) -> password (if needed) -> add. Each step waits for the previous one.
    property int step: 0
    Timer {
        id: stepper
        interval: 50; repeat: true
        onTriggered: {
            if (dialog.busy) return
            if (dialog.failure && dialog.step > 0) { stop(); dialog.step = 0; return }
            if (dialog.step === 0 && !dialog.status.configured) { dialog.step = 1; dialog.lastDone = ""; dialog.call(["setup"]); return }
            if (dialog.step <= 1 && dialog.needsPassword) { dialog.step = 2; dialog.lastDone = ""; dialog.call(["set-password"], dialog.passwordText); return }
            if (dialog.step <= 2) {
                dialog.step = 3; dialog.lastDone = dialog.tr("shared")
                var args = ["add", "--path", dialog.folderPath, "--name", dialog.shareName, "--access", dialog.writable ? "write" : "read"]
                if (dialog.guest) args.push("--guest")
                dialog.call(args)
                return
            }
            stop(); dialog.step = 0
        }
    }
    Timer { id: restatus; interval: 100; running: false }
    function stopSharing() { lastDone = tr("stopped"); call(["remove", existing ? existing.name : shareName]); resultUnc = "" }

    Process { id: copyProc; command: ["wl-copy", dialog.resultUnc || ("\\\\" + dialog.status.hostname + "\\" + dialog.shareName)] }
    readonly property string unc: resultUnc !== "" ? resultUnc : ("\\\\" + (status.hostname || "pc") + "\\" + shareName)

    Column {
        id: content
        x: 24; y: 24; width: parent.width - 48; spacing: 14

        Text { text: dialog.existing ? dialog.tr("titleEdit") : dialog.tr("title"); font.pixelSize: 18; font.bold: true; color: dialog.textColor }
        Rectangle {
            width: parent.width; height: 44; radius: 8; color: dialog.dark ? "#262626" : "#eeeeee"; border.color: dialog.lineColor; border.width: 1
            Row {
                anchors.fill: parent; anchors.leftMargin: 12; spacing: 10
                Text { anchors.verticalCenter: parent.verticalCenter; text: "📁"; font.pixelSize: 18 }
                Text { anchors.verticalCenter: parent.verticalCenter; width: parent.width - 50; text: dialog.folderPath; elide: Text.ElideMiddle; font.pixelSize: 13; color: dialog.mutedColor }
            }
        }

        Text { visible: !dialog.status.installed; width: parent.width; wrapMode: Text.WordWrap; text: dialog.tr("notInstalled"); color: "#cc4444"; font.pixelSize: 13 }

        Column {
            width: parent.width; spacing: 6
            Text { text: dialog.tr("name"); font.pixelSize: 13; color: dialog.mutedColor }
            TextField {
                width: parent.width; height: 40; text: dialog.shareName; enabled: !dialog.existing
                maximumLength: 40; selectByMouse: true
                onTextEdited: dialog.shareName = text
                color: dialog.textColor; font.pixelSize: 14
                background: Rectangle { radius: 6; color: dialog.dark ? "#2a2a2a" : "#f0f0f0"; border.width: 1; border.color: parent.activeFocus ? dialog.accent : dialog.lineColor }
            }
        }

        Column {
            width: parent.width; spacing: 6
            Text { text: dialog.tr("access"); font.pixelSize: 13; color: dialog.mutedColor }
            Row {
                spacing: 8
                Repeater {
                    model: [{w: false, key: "readOnly"}, {w: true, key: "readWrite"}]
                    Tools.SystemToolsButton {
                        required property var modelData
                        settingsMenu: dialog.settingsMenu
                        enabled: !dialog.existing
                        width: (dialog.width - 48 - 8) / 2
                        primary: dialog.writable === modelData.w
                        text: dialog.tr(modelData.key)
                        onClicked: { dialog.writable = modelData.w; if (modelData.w) dialog.guest = false }
                    }
                }
            }
        }

        Tools.SystemToolsToggle {
            settingsMenu: dialog.settingsMenu
            enabled: !dialog.existing && !dialog.writable
            text: dialog.tr("guest")
            checked: dialog.guest
            onToggled: dialog.guest = checked
        }
        Text { visible: dialog.guest; width: parent.width; wrapMode: Text.WordWrap; text: dialog.tr("guestWarning"); font.pixelSize: 12; color: "#e8a020" }

        // Password for network access (needed once, unless everyone may read without signing in)
        Column {
            visible: dialog.needsPassword && !dialog.existing
            width: parent.width; spacing: 8
            Text { width: parent.width; wrapMode: Text.WordWrap; text: dialog.tr("passwordIntro"); font.pixelSize: 12; color: dialog.mutedColor }
            Row {
                spacing: 8
                Repeater {
                    model: ["password", "passwordRepeat"]
                    TextField {
                        required property string modelData
                        width: (dialog.width - 48 - 8) / 2; height: 40; echoMode: TextInput.Password; placeholderText: dialog.tr(modelData)
                        onTextEdited: { if (modelData === "password") dialog.passwordText = text; else dialog.passwordRepeat = text }
                        color: dialog.textColor; font.pixelSize: 14
                        background: Rectangle { radius: 6; color: dialog.dark ? "#2a2a2a" : "#f0f0f0"; border.width: 1; border.color: parent.activeFocus ? dialog.accent : dialog.lineColor }
                    }
                }
            }
        }

        // The address other computers use
        Rectangle {
            width: parent.width; height: 56; radius: 8; color: dialog.dark ? "#202020" : "#f3f3f3"; border.color: dialog.lineColor; border.width: 1
            Column {
                anchors.verticalCenter: parent.verticalCenter; x: 12; width: parent.width - 120; spacing: 2
                Text { text: dialog.tr("address"); font.pixelSize: 11; color: dialog.mutedColor }
                Text { width: parent.width; text: dialog.unc; elide: Text.ElideMiddle; font.pixelSize: 14; font.family: "monospace"; color: dialog.textColor }
            }
            Tools.SystemToolsButton {
                anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                settingsMenu: dialog.settingsMenu; text: dialog.tr("copy"); onClicked: copyProc.running = true
            }
        }
        Text { width: parent.width; wrapMode: Text.WordWrap; text: dialog.tr("howTo"); font.pixelSize: 12; color: dialog.mutedColor }

        Text { visible: dialog.message !== ""; width: parent.width; wrapMode: Text.WordWrap; text: dialog.message; font.pixelSize: 13; font.bold: true; color: dialog.failure ? "#cc4444" : "#3aa655" }

        Row {
            spacing: 10; layoutDirection: Qt.RightToLeft; width: parent.width
            Tools.SystemToolsButton {
                settingsMenu: dialog.settingsMenu; primary: true
                visible: !dialog.existing
                enabled: !dialog.busy && dialog.status.installed && dialog.shareName.trim() !== ""
                text: dialog.busy ? dialog.tr("working") : dialog.tr("share")
                onClicked: dialog.share()
            }
            Tools.SystemToolsButton { settingsMenu: dialog.settingsMenu; visible: dialog.existing !== null; destructive: true; enabled: !dialog.busy; text: dialog.tr("stop"); onClicked: dialog.stopSharing() }
            Tools.SystemToolsButton { settingsMenu: dialog.settingsMenu; text: dialog.existing || dialog.resultUnc !== "" ? dialog.tr("close") : dialog.tr("cancel"); onClicked: dialog.visible = false }
        }
    }
}
