import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as Dialogs
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

// Own account only: password and profile picture. Every write runs through the pkexec helper.
Item {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color foreground: dark ? "#ffffff" : "#1a1a1a"
    readonly property color secondary: dark ? "#aaaaaa" : "#555555"
    readonly property color lineColor: dark ? "#3a3a3a" : "#d0d0d0"
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    property bool busy: false
    property string resultKey: ""
    property string errorText: ""
    property string logPath: ""
    readonly property bool passwordReady: !busy && currentField.text.length > 0
        && newField.text.length >= 8 && newField.text === repeatField.text
    width: parent ? parent.width : 650
    height: content.height

    function tr(key) { return Lang.get(key, _lang) }
    function finish(code, output, errors, pending) {
        busy = false
        let data = {}
        try { data = JSON.parse(output) } catch (error) {}
        logPath = data.log || ""
        if (code === 0 && !data.error) {
            resultKey = pending; errorText = ""
        } else {
            resultKey = code === 126 ? "systemTools.cancelled" : "systemTools.failed"
            errorText = code === 126 ? "" : (data.error || errors.trim() || output.trim())
        }
    }

    component Note: Text {
        width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText
        color: page.secondary; font.pixelSize: 13
    }
    component AccountField: TextField {
        width: parent.width; height: 36
        echoMode: TextInput.Password
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
        color: page.foreground
        placeholderTextColor: page.dark ? "#666" : "#999"
        font.pixelSize: 13
        leftPadding: 10; rightPadding: 10
        background: Rectangle {
            radius: 6
            color: page.dark ? "#2a2a2a" : "#f0f0f0"
            border.color: parent.activeFocus ? page.accent : page.lineColor
            border.width: 1
        }
    }

    // Password: the payload goes to the helper on stdin. It never appears in argv or in the log.
    Process {
        id: passwordWorker
        stdinEnabled: true
        command: ["/usr/bin/pkexec", "--disable-internal-agent", "/usr/lib/windoesnot/system_tools.py", "password-change", "{}"]
        onStarted: {
            write(JSON.stringify({current: currentField.text, password: newField.text}) + "\n")
            currentField.text = ""; newField.text = ""; repeatField.text = ""
        }
        stdout: StdioCollector { id: passwordOutput }
        stderr: StdioCollector { id: passwordErrors }
        onExited: (code) => page.finish(code, passwordOutput.text, passwordErrors.text, "account.passwordDone")
    }

    // Profile picture: ImageMagick makes a 96x96 PNG on stdout, the helper validates and installs it.
    Process {
        id: avatarWorker
        command: ["/usr/bin/bash", "-c", "/usr/bin/magick \"$1[0]\" -auto-orient -strip -resize 96x96^ -gravity center -extent 96x96 PNG:- | /usr/bin/pkexec --disable-internal-agent /usr/lib/windoesnot/system_tools.py avatar-set '{}'", "avatar"]
        stdout: StdioCollector { id: avatarOutput }
        stderr: StdioCollector { id: avatarErrors }
        onExited: (code) => page.finish(code, avatarOutput.text, avatarErrors.text, "account.avatarDone")
    }

    Dialogs.FileDialog {
        id: avatarPicker
        title: page.tr("account.avatarChoose")
        nameFilters: [page.tr("account.imageFilter") + " (*.png *.jpg *.jpeg *.webp)"]
        onAccepted: {
            page.settingsMenu.fileDialogOpen = false
            page.busy = true; page.resultKey = ""; page.errorText = ""; page.logPath = ""
            avatarWorker.command = ["/usr/bin/bash", "-c", avatarWorker.command[2], "avatar",
                decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""))]
            avatarWorker.running = true
        }
        onRejected: page.settingsMenu.fileDialogOpen = false
    }

    Column {
        id: content
        width: parent.width; spacing: 20
        Note { text: page.tr("account.hint") }

        Rectangle {
            visible: page.resultKey.length > 0 || page.errorText.length > 0
            width: parent.width; height: resultColumn.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: resultColumn; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Note { visible: page.resultKey.length > 0; text: page.tr(page.resultKey); color: page.foreground }
                Note { visible: page.errorText.length > 0; text: page.errorText; color: "#e65555" }
                Note { visible: page.logPath.length > 0; text: page.tr("systemTools.log") + " " + page.logPath; font.pixelSize: 11 }
            }
        }

        // Card pattern from the maintenance page: same radius, colors, padding and buttons.
        Rectangle {
            id: passwordCard
            width: content.width; height: passwordContent.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: passwordContent; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Text { width: parent.width; text: page.tr("account.passwordTitle"); color: page.foreground; font.pixelSize: 15; font.bold: true; wrapMode: Text.WordWrap }
                Note { text: page.tr("account.passwordHint") }
                AccountField { id: currentField; placeholderText: page.tr("account.currentPassword"); enabled: !page.busy }
                AccountField { id: newField; placeholderText: page.tr("account.newPassword"); enabled: !page.busy }
                AccountField { id: repeatField; placeholderText: page.tr("account.repeatPassword"); enabled: !page.busy }
                Note { visible: newField.text.length > 0 && newField.text.length < 8; text: page.tr("account.passwordRule"); color: "#e8a020" }
                Note { visible: repeatField.text.length > 0 && newField.text !== repeatField.text; text: page.tr("account.passwordMismatch"); color: "#e8a020" }
                Tools.SystemToolsButton {
                    settingsMenu: page.settingsMenu
                    enabled: page.passwordReady
                    primary: true
                    text: page.tr("account.passwordAction")
                    onClicked: {
                        page.busy = true; page.resultKey = ""; page.errorText = ""; page.logPath = ""
                        passwordWorker.running = true
                    }
                }
            }
        }

        Rectangle {
            id: avatarCard
            width: content.width; height: avatarContent.implicitHeight + 32
            radius: settingsMenu ? settingsMenu.borderRadius : 10
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.lineColor
            Column {
                id: avatarContent; x: 16; y: 16; width: parent.width - 32; spacing: 10
                Text { width: parent.width; text: page.tr("account.avatarTitle"); color: page.foreground; font.pixelSize: 15; font.bold: true; wrapMode: Text.WordWrap }
                Note { text: page.tr("account.avatarHint") }
                Tools.SystemToolsButton {
                    settingsMenu: page.settingsMenu
                    enabled: !page.busy
                    primary: true
                    text: page.tr("account.avatarAction")
                    onClicked: {
                        page.settingsMenu.fileDialogOpen = true
                        avatarPicker.open()
                    }
                }
            }
        }

        BusyIndicator { width: 32; height: 32; running: page.busy; visible: running; palette.highlight: page.accent }
    }
}
