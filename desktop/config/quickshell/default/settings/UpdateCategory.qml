import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

// System updates: real status from the WinDoesNot Store (`--status-json`),
// which reads a user-owned copy of the package databases and never changes
// the system. Installing always happens in the Store as one full upgrade.
Column {
    id: updatesPage
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    property color accent: settingsMenu ? settingsMenu.accentColor : "#0078d4"
    readonly property color textColor: settingsMenu.darkMode ? "#ffffff" : "#1a1a1a"
    readonly property color subColor: settingsMenu.darkMode ? "#aaaaaa" : "#555555"
    readonly property color cardColor: settingsMenu.darkMode ? Qt.rgba(0.08, 0.08, 0.08, 1) : Qt.rgba(0.96, 0.96, 0.96, 1)
    readonly property color warnColor: "#e8a020"

    property var status: null
    property bool checking: false
    property bool settingAur: false
    property bool aurEnabled: false
    property bool aurAvailable: false
    property string actionError: ""
    property bool pendingCheck: false
    property bool acceptStatusResult: true

    function setAur(enabled) {
        if (settingAur) return
        settingAur = true
        actionError = ""
        // Let an in-flight check finish, but discard its outdated AUR state.
        acceptStatusResult = false
        aurSetProc.command = ["sh", "-c", 'command -v windoesnot-store >/dev/null || exit 127; exec windoesnot-store --set-aur "$1"', "sh", enabled ? "true" : "false"]
        aurSetProc.running = true
    }

    function readAurStatus() {
        if (!aurReadProc.running && !settingAur) aurReadProc.running = true
    }

    property bool storeMissing: false
    readonly property int updateCount: status ? status.updates.length : 0
    readonly property bool needsAttention: status && (updateCount > 0 || status.reboot || status.relogin)
    // Kernel, drivers and core libraries need a restart after their update.
    readonly property var restartPackages: status ? status.updates.filter(function(u) {
        return /^(linux|nvidia|mesa|systemd|glibc|hyprland|aquamarine)/.test(u.name)
    }) : []

    width: parent.width
    spacing: 20

    function check(refresh) {
        if (checking || settingAur) { pendingCheck = true; return }
        acceptStatusResult = true
        checking = true
        // Via sh: a missing store binary then ends with 127 instead of never
        // reporting an exit.
        statusProc.command = ["sh", "-c", 'command -v windoesnot-store >/dev/null || exit 127; exec windoesnot-store --status-json "$@"',
                              "sh"].concat(refresh ? ["--refresh"] : [])
        statusProc.running = true
    }

    function timeText(seconds) {
        var date = new Date(seconds * 1000)
        return Qt.formatTime(date, "HH:mm")
    }

    Component.onCompleted: { readAurStatus(); check(false) }
    Timer {
        interval: 3000
        repeat: true
        running: updatesPage.visible && (!settingsMenu || settingsMenu.visible)
        onTriggered: updatesPage.readAurStatus()
    }
    Process {
        id: aurReadProc
        command: ["sh", "-c", "command -v windoesnot-store >/dev/null || exit 127; exec windoesnot-store --aur-status-json"]
        stdout: StdioCollector { id: aurReadOutput }
        onExited: (code) => {
            if (code !== 0 || settingAur) return
            try {
                const data = JSON.parse(aurReadOutput.text)
                const changed = aurEnabled !== data.aur_enabled
                aurEnabled = data.aur_enabled
                aurAvailable = data.aur_available
                if (changed && status) {
                    acceptStatusResult = false
                    check(false)
                }
            } catch (error) { actionError = Lang.get("updates.aurReadFailed", _lang) }
        }
    }
    Process {
        id: aurSetProc
        stdout: StdioCollector { id: aurSetOutput }
        stderr: StdioCollector { id: aurSetError }
        onExited: (code) => {
            settingAur = false
            if (code === 0) {
                try { aurEnabled = JSON.parse(aurSetOutput.text).aur_enabled }
                catch (error) { actionError = Lang.get("updates.aurSaveFailed", _lang) }
            } else { actionError = Lang.get("updates.aurSaveFailed", _lang) + " " + aurSetError.text.trim() }
            readAurStatus()
            check(false)
        }
    }


    Process {
        id: statusProc
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    if (!updatesPage.acceptStatusResult) return
                    updatesPage.status = JSON.parse(text)
                    updatesPage.aurEnabled = updatesPage.status.aur_enabled === true
                    updatesPage.aurAvailable = updatesPage.status.aur_available === true
                    updatesPage.storeMissing = false
                } catch (e) {
                    console.log("[Updates] no status:", e)
                }
            }
        }
        onExited: function(code) {
            updatesPage.checking = false
            if (code !== 0 && !updatesPage.status) updatesPage.storeMissing = true
            if (pendingCheck && !settingAur) { pendingCheck = false; Qt.callLater(function() { check(false) }) }
        }
    }

    Process {
        id: openStoreProc
        command: ["windoesnot-store", "--updates"]
    }

    // === WinDoesNot itself (desktop, dotfiles, components) ===
    Rectangle {
        readonly property var wdn: status ? status.windoesnot : null
        visible: wdn !== null && wdn !== undefined
        width: parent.width
        height: wdnColumn.implicitHeight + 32
        radius: settingsMenu.borderRadius
        color: cardColor
        border.color: wdn && wdn.update ? warnColor : accent
        border.width: 1

        Column {
            id: wdnColumn
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
            spacing: 6

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: !parent.parent.wdn ? ""
                    : !parent.parent.wdn.installed ? Lang.get("updates.wdnDev", _lang)
                    : parent.parent.wdn.update ? Lang.get("updates.wdnAvailable", _lang).replace("{}", parent.parent.wdn.available)
                    : Lang.get("updates.wdnCurrent", _lang).replace("{}", parent.parent.wdn.installed)
                font.pixelSize: 15; font.bold: true
                color: textColor
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: !parent.parent.wdn ? ""
                    : !parent.parent.wdn.installed ? Lang.get("updates.wdnDevHint", _lang)
                    : parent.parent.wdn.update ? Lang.get("updates.wdnWhatsNew", _lang)
                    : Lang.get("updates.wdnInstalledNew", _lang)
                font.pixelSize: 12
                color: subColor
            }
            Repeater {
                // One line per change, newest release first, in the UI language.
                model: {
                    var wdn = parent.parent.wdn
                    if (!wdn) return []
                    var lines = []
                    for (var i = 0; i < wdn.changes.length; i++) {
                        var entries = (_lang === "de" ? wdn.changes[i].de : wdn.changes[i].en) || []
                        for (var j = 0; j < entries.length; j++) lines.push(entries[j])
                    }
                    return lines
                }
                delegate: Text {
                    required property var modelData
                    width: wdnColumn.width
                    wrapMode: Text.WordWrap
                    text: "•  " + modelData
                    font.pixelSize: 13
                    color: textColor
                }
            }
        }
    }

    // Same switch and spacing as the optional-app controls in AppsCategory.
    Rectangle {
        width: parent.width
        height: aurContent.implicitHeight + 32
        radius: settingsMenu.borderRadius
        color: cardColor
        border.width: 1
        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
        Row {
            id: aurContent
            x: 16; y: 16; width: parent.width - 32
            spacing: 15
            Column {
                width: parent.width - 75
                spacing: 6
                Text { text: Lang.get("updates.aurTitle", _lang); color: textColor; font.pixelSize: 14; font.bold: true }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: Lang.get("updates.aurHint", _lang)
                    color: subColor; font.pixelSize: 12
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    visible: aurEnabled && !aurAvailable
                    text: Lang.get("updates.aurNoHelper", _lang)
                    color: warnColor; font.pixelSize: 12
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    visible: actionError.length > 0 || (status && !!status.aur_error)
                    text: actionError || Lang.get("updates.aurCheckFailed", _lang)
                    color: warnColor; font.pixelSize: 12
                }
            }
            Rectangle {
                objectName: "aurSwitch"
                width: 60; height: 32; radius: 16
                anchors.verticalCenter: parent.verticalCenter
                color: aurEnabled ? accent : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                opacity: settingAur || storeMissing ? 0.5 : 1
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: aurEnabled ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on x { NumberAnimation { duration: 150 } }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: !settingAur && !storeMissing
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: setAur(!aurEnabled)
                }
            }
        }
    }

    // === Status card ===
    Rectangle {
        width: parent.width
        height: statusRow.implicitHeight + 32
        radius: settingsMenu.borderRadius
        color: cardColor
        border.color: needsAttention ? warnColor : accent
        border.width: 1

        Row {
            id: statusRow
            anchors { left: parent.left; right: parent.right; margins: 16 }
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14

            Rectangle {
                width: 44; height: 44; radius: 22
                color: needsAttention ? warnColor : accent
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    anchors.centerIn: parent
                    text: checking ? "…" : (needsAttention ? "↓" : "✓")
                    font.pixelSize: 18; font.bold: true
                    color: "#ffffff"
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 58
                spacing: 4

                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: storeMissing ? Lang.get("updates.storeMissing", _lang)
                        : !status ? Lang.get("updates.checking", _lang)
                        : updateCount > 0 ? Lang.get("updates.available", _lang).replace("{}", updateCount)
                        : status && status.aur_error ? Lang.get("updates.aurCheckFailed", _lang) : Lang.get("updates.upToDate", _lang)
                    font.pixelSize: 15; font.bold: true
                    color: textColor
                }
                Text {
                    visible: status !== null
                    text: status ? Lang.get("updates.lastChecked", _lang).replace("{}", timeText(status.checked)) : ""
                    font.pixelSize: 12
                    color: subColor
                }
                Text {
                    visible: status !== null && (status.reboot || restartPackages.length > 0)
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: status && status.reboot ? Lang.get("updates.rebootNow", _lang) : Lang.get("updates.rebootAfter", _lang)
                    font.pixelSize: 12
                    color: warnColor
                }
                Text {
                    visible: status !== null && status.relogin
                    text: Lang.get("updates.relogin", _lang)
                    font.pixelSize: 12
                    color: warnColor
                }
            }
        }
    }

    // === Actions ===
    Row {
        spacing: 10

        Rectangle {
            width: checkLabel.implicitWidth + 28; height: 34
            radius: settingsMenu.borderRadius
            color: checking ? (settingsMenu.darkMode ? "#3a3a3a" : "#c8c8c8") : accent
            Text {
                id: checkLabel
                anchors.centerIn: parent
                text: checking ? Lang.get("updates.checkingShort", _lang) : Lang.get("updates.check", _lang)
                font.pixelSize: 13
                color: "#ffffff"
            }
            MouseArea {
                anchors.fill: parent
                enabled: !checking && !storeMissing
                cursorShape: Qt.PointingHandCursor
                onClicked: updatesPage.check(true)
            }
        }

        Rectangle {
            visible: updateCount > 0
            width: storeLabel.implicitWidth + 28; height: 34
            radius: settingsMenu.borderRadius
            color: "transparent"
            border.color: accent; border.width: 1
            Text {
                id: storeLabel
                anchors.centerIn: parent
                text: Lang.get("updates.openStore", _lang)
                font.pixelSize: 13
                color: textColor
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: openStoreProc.running = true
            }
        }
    }

    // === Pending packages ===
    Column {
        visible: updateCount > 0
        width: parent.width
        spacing: 6

        Text {
            text: Lang.get("updates.packages", _lang)
            font.pixelSize: 14; font.bold: true
            color: textColor
        }
        Repeater {
            model: status ? status.updates.slice(0, 10) : []
            delegate: Text {
                required property var modelData
                width: updatesPage.width
                elide: Text.ElideRight
                text: modelData.name + (modelData.source === "aur" ? " (AUR)" : "") + "   " + modelData.old + " → " + modelData.new
                font.pixelSize: 12
                font.family: "monospace"
                color: subColor
            }
        }
        Text {
            visible: updateCount > 10
            text: Lang.get("updates.more", _lang).replace("{}", updateCount - 10)
            font.pixelSize: 12
            color: subColor
        }
    }

    Rectangle {
        width: parent.width; height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // === Arch news (Arch asks to read them before upgrading) ===
    Column {
        width: parent.width
        spacing: 8

        Text {
            text: Lang.get("updates.news", _lang)
            font.pixelSize: 14; font.bold: true
            color: textColor
        }
        Text {
            visible: status !== null && status.news.length === 0
            width: parent.width
            wrapMode: Text.WordWrap
            text: status && status.news_unavailable ? Lang.get("updates.newsOffline", _lang) : Lang.get("updates.newsNone", _lang)
            font.pixelSize: 12
            color: subColor
        }
        Repeater {
            model: status ? status.news : []
            delegate: Rectangle {
                required property var modelData
                width: updatesPage.width
                height: newsText.implicitHeight + 20
                radius: settingsMenu.borderRadius
                color: cardColor
                border.color: modelData.intervention ? warnColor : "transparent"
                border.width: 1
                Column {
                    id: newsText
                    anchors { left: parent.left; right: parent.right; margins: 12; verticalCenter: parent.verticalCenter }
                    spacing: 3
                    Text {
                        visible: modelData.intervention
                        text: "⚠ " + Lang.get("updates.intervention", _lang)
                        font.pixelSize: 11; font.bold: true
                        color: warnColor
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: modelData.title
                        font.pixelSize: 13
                        color: textColor
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Qt.openUrlExternally(modelData.link)
                }
            }
        }
    }
}
