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
        onExited: (code) => {
            page.finish(code, avatarOutput.text, avatarErrors.text, "account.avatarDone")
            if (code === 0) avatarStatus.running = true
        }
    }

    // Current picture for the preview, same lookup order as the start menu. Prints the
    // path (empty when none is set) and the user name for the placeholder letter.
    property string avatarSource: ""
    property string userName: ""
    Process {
        id: avatarStatus
        command: ["bash", "-c", "p=''; for c in \"$HOME/.face\" \"$HOME/.face.icon\" \"/var/lib/AccountsService/icons/$USER\"; do if [ -f \"$c\" ]; then p=\"$c\"; break; fi; done; printf '%s\\n%s' \"$p\" \"$USER\""]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.split("\n")
                page.avatarSource = lines[0] ? "file://" + lines[0] : ""
                page.userName = lines.length > 1 ? lines[1] : ""
            }
        }
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
                Loader { width: parent.width; sourceComponent: avatarContentComponent }
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

        Component {
            id: avatarContentComponent
            Row {
                width: parent.width; spacing: 12
                // Current picture; without one, a neutral tile with the initial of the user.
                Rectangle {
                        width: 64; height: 64
                        radius: settingsMenu ? settingsMenu.borderRadius : 10
                        clip: true
                        color: page.dark ? "#2a2a2a" : "#e0e0e0"
                        border.width: 1; border.color: page.lineColor
                        Image {
                            id: avatarPreview
                            anchors.fill: parent
                            source: page.avatarSource
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: false
                            visible: status === Image.Ready
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: avatarPreview.status !== Image.Ready
                            text: page.userName.length > 0 ? page.userName.charAt(0).toUpperCase() : "?"
                            font.pixelSize: 24; font.bold: true
                            color: page.foreground
                        }
                }
                Column {
                    width: parent.width - 76; spacing: 5
                    Text { width: parent.width; text: page.tr("account.avatarTitle"); color: page.foreground; font.pixelSize: 14; font.bold: true; elide: Text.ElideRight }
                    Note { text: page.tr("account.avatarHint"); font.pixelSize: 12 }
                    Tools.SystemToolsButton {
                        settingsMenu: page.settingsMenu
                        enabled: !page.busy
                        text: page.tr("account.avatarAction")
                        onClicked: {
                            page.settingsMenu.fileDialogOpen = true
                            avatarPicker.open()
                        }
                    }
                }
            }
        }

        BusyIndicator { width: 32; height: 32; running: page.busy; visible: running; palette.highlight: page.accent }
    }
}
