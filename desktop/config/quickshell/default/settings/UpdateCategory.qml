import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import "../i18n/Lang.js" as Lang

// Updates in plain language: one status card with one button, then what the
// update brings — WinDoesNot, programs, system — and technical details last.
// Data comes from the WinDoesNot Store (`--status-json`), which reads a
// user-owned copy of the package databases and never changes the system.
// Installing is always one full upgrade, reviewed in the Store (`--upgrade`).
Column {
    id: updatesPage
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    property color accent: settingsMenu ? settingsMenu.accentColor : "#0078d4"
    readonly property color textColor: settingsMenu.darkMode ? "#ffffff" : "#1a1a1a"
    readonly property color subColor: settingsMenu.darkMode ? "#aaaaaa" : "#555555"
    readonly property color cardColor: settingsMenu.darkMode ? Qt.rgba(0.08, 0.08, 0.08, 1) : Qt.rgba(0.96, 0.96, 0.96, 1)
    readonly property color lineColor: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    readonly property color warnColor: "#e8a020"

    property var status: null
    property bool checking: false
    property bool settingAur: false
    property bool aurEnabled: false
    property bool aurAvailable: false
    property string actionError: ""
    property bool pendingCheck: false
    property bool acceptStatusResult: true
    property bool showAdvanced: false

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
    readonly property var updates: status ? status.updates : []
    readonly property int updateCount: updates.length
    // Without any downloaded package database, "no updates" means "not checked".
    readonly property bool neverChecked: status !== null && !status.databases_checked
    readonly property bool needsReboot: updates.some(function(u) { return u.restart === "reboot" })
    readonly property bool needsRelogin: updates.some(function(u) { return u.restart === "relogin" })
    readonly property var apps: updates.filter(function(u) { return u.category === "app" })
    readonly property var interventions: status ? status.news.filter(function(n) { return n.intervention }) : []
    readonly property var groupOrder: ["kernel", "drivers", "desktop", "sound", "network", "other"]
    readonly property var systemGroups: {
        var groups = []
        for (var i = 0; i < groupOrder.length; i++) {
            var key = groupOrder[i]
            var items = updates.filter(function(u) { return u.category === "system" && u.group === key })
            if (items.length === 0) continue
            var restart = items.some(function(u) { return u.restart === "reboot" }) ? "reboot"
                : items.some(function(u) { return u.restart === "relogin" }) ? "relogin" : ""
            groups.push({ key: key, items: items, restart: restart })
        }
        return groups
    }

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

    function countText(n) {
        return n === 1 ? Lang.get("updates.countOne", _lang) : Lang.get("updates.countMany", _lang).replace("{}", n)
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
        id: upgradeProc
        command: ["windoesnot-store", "--upgrade"]
    }

    // === Status: one sentence, one button ===
    Rectangle {
        width: parent.width
        height: heroColumn.implicitHeight + 40
        radius: settingsMenu.borderRadius
        color: cardColor
        border.color: updateCount > 0 || neverChecked ? warnColor : accent
        border.width: 1

        Row {
            id: heroRow
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 20 }
            spacing: 16

            Rectangle {
                width: 48; height: 48; radius: 24
                color: updateCount > 0 || neverChecked ? warnColor : accent
                Text {
                    anchors.centerIn: parent
                    text: checking ? "…" : (updateCount > 0 ? "↓" : neverChecked ? "?" : "✓")
                    font.pixelSize: 20; font.bold: true
                    color: "#ffffff"
                }
            }

            Column {
                id: heroColumn
                width: parent.width - 64
                spacing: 6

                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: storeMissing ? Lang.get("updates.storeMissing", _lang)
                        : !status ? Lang.get("updates.checking", _lang)
                        : updateCount === 1 ? Lang.get("updates.heroAvailableOne", _lang)
                        : updateCount > 1 ? Lang.get("updates.heroAvailable", _lang).replace("{}", updateCount)
                        : neverChecked ? Lang.get("updates.heroNever", _lang)
                        : status.aur_error ? Lang.get("updates.aurCheckFailed", _lang)
                        : Lang.get("updates.heroCurrent", _lang)
                    font.pixelSize: 17; font.bold: true
                    color: textColor
                }
                Text {
                    visible: neverChecked && updateCount === 0
                    width: parent.width; wrapMode: Text.WordWrap
                    text: Lang.get("updates.heroNeverHint", _lang)
                    font.pixelSize: 12; color: subColor
                }
                Text {
                    visible: status !== null && !!status.databases_checked
                    text: status && status.databases_checked ? Lang.get("updates.lastChecked", _lang).replace("{}", timeText(status.databases_checked)) : ""
                    font.pixelSize: 12; color: subColor
                }
                Text {
                    visible: updateCount > 0 && (needsReboot || needsRelogin)
                    width: parent.width; wrapMode: Text.WordWrap
                    text: needsReboot ? Lang.get("updates.afterReboot", _lang) : Lang.get("updates.afterRelogin", _lang)
                    font.pixelSize: 12; color: warnColor
                }
                Text {
                    visible: status !== null && (status.reboot || status.relogin)
                    width: parent.width; wrapMode: Text.WordWrap
                    text: status && status.reboot ? Lang.get("updates.rebootNow", _lang) : Lang.get("updates.relogin", _lang)
                    font.pixelSize: 12; color: warnColor
                }

                Item { width: 1; height: 6 }
                Row {
                    spacing: 10
                    Rectangle {
                        visible: updateCount > 0
                        width: updateLabel.implicitWidth + 32; height: 36
                        radius: settingsMenu.borderRadius
                        color: accent
                        Text {
                            id: updateLabel
                            anchors.centerIn: parent
                            text: Lang.get("updates.updateNow", _lang)
                            font.pixelSize: 13; font.bold: true
                            color: "#ffffff"
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                upgradeProc.running = true
                                // The Store's review dialog takes over; don't cover it.
                                settingsMenu.visible = false
                            }
                        }
                    }
                    Rectangle {
                        readonly property bool active: !checking && !storeMissing
                        readonly property bool primary: updateCount === 0
                        width: checkLabel.implicitWidth + 32; height: 36
                        radius: settingsMenu.borderRadius
                        color: !active ? (settingsMenu.darkMode ? "#3a3a3a" : "#c8c8c8") : (primary ? accent : "transparent")
                        border.color: accent
                        border.width: primary || !active ? 0 : 1
                        Text {
                            id: checkLabel
                            anchors.centerIn: parent
                            text: checking ? Lang.get("updates.checkingShort", _lang) : Lang.get("updates.check", _lang)
                            font.pixelSize: 13; font.bold: parent.primary
                            color: parent.primary || !parent.active ? "#ffffff" : textColor
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: parent.active
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: updatesPage.check(true)
                        }
                    }
                }
                Text {
                    visible: updateCount > 0
                    width: parent.width; wrapMode: Text.WordWrap
                    text: Lang.get("updates.oneStep", _lang)
                    font.pixelSize: 11; color: subColor
                }
            }
        }
    }

    // === Arch news that need action before upgrading ===
    Rectangle {
        visible: interventions.length > 0
        width: parent.width
        height: visible ? interventionColumn.implicitHeight + 28 : 0
        radius: settingsMenu.borderRadius
        color: Qt.rgba(0.91, 0.63, 0.13, 0.10)
        border.color: warnColor; border.width: 1
        Column {
            id: interventionColumn
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 8
            Text { text: "⚠  " + Lang.get(updateCount > 0 ? "updates.importantTitle" : "updates.importantNews", _lang); font.pixelSize: 14; font.bold: true; color: warnColor }
            Repeater {
                model: interventions
                delegate: Row {
                    required property var modelData
                    width: interventionColumn.width
                    spacing: 10
                    Text {
                        width: parent.width - readLink.width - 10
                        wrapMode: Text.WordWrap
                        text: modelData.title
                        font.pixelSize: 13; color: textColor
                    }
                    Text {
                        id: readLink
                        text: Lang.get("updates.read", _lang) + " ›"
                        font.pixelSize: 13; color: accent
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally(modelData.link) }
                    }
                }
            }
        }
    }

    // === WinDoesNot itself ===
    Rectangle {
        readonly property var wdn: status ? status.windoesnot : null
        visible: wdn !== null && wdn !== undefined
        width: parent.width
        height: wdnColumn.implicitHeight + 32
        radius: settingsMenu.borderRadius
        color: cardColor
        border.color: wdn && wdn.update ? warnColor : lineColor
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

    // === Programs, as named in the start menu ===
    Column {
        visible: apps.length > 0
        width: parent.width
        spacing: 8
        Text { text: Lang.get("updates.sectionApps", _lang) + "  ·  " + apps.length; font.pixelSize: 15; font.bold: true; color: textColor }
        Rectangle {
            width: parent.width
            height: appList.implicitHeight
            radius: settingsMenu.borderRadius
            color: cardColor
            Column {
                id: appList
                width: parent.width
                Repeater {
                    model: apps
                    delegate: Item {
                        required property var modelData
                        required property int index
                        width: appList.width; height: 52
                        Rectangle {
                            visible: index > 0
                            width: parent.width - 32; height: 1; x: 16
                            color: lineColor
                        }
                        Image {
                            id: appIcon
                            x: 16; anchors.verticalCenter: parent.verticalCenter
                            width: 28; height: 28
                            sourceSize: Qt.size(28, 28)
                            // iconPath(…, true) is empty for icons the theme lacks; the
                            // image provider would draw its checkerboard instead.
                            source: Quickshell.iconPath(modelData.icon || "", true) || Quickshell.iconPath("application-x-executable")
                        }
                        Column {
                            anchors { left: appIcon.right; leftMargin: 12; right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                            spacing: 2
                            Text {
                                width: parent.width; elide: Text.ElideRight
                                text: modelData.app_name + (modelData.source === "aur" ? "  · AUR" : "")
                                font.pixelSize: 13; color: textColor
                            }
                            Text {
                                width: parent.width; elide: Text.ElideRight
                                text: modelData.old + "  →  " + modelData.new
                                font.pixelSize: 11; color: subColor
                            }
                        }
                    }
                }
            }
        }
    }

    // === System, in a few plain groups ===
    Column {
        visible: systemGroups.length > 0
        width: parent.width
        spacing: 8
        Text { text: Lang.get("updates.sectionSystem", _lang) + "  ·  " + countText(updates.filter(function(u) { return u.category === "system" }).length); font.pixelSize: 15; font.bold: true; color: textColor }
        Rectangle {
            width: parent.width
            height: groupList.implicitHeight
            radius: settingsMenu.borderRadius
            color: cardColor
            Column {
                id: groupList
                width: parent.width
                Repeater {
                    model: systemGroups
                    delegate: Column {
                        id: groupRow
                        required property var modelData
                        required property int index
                        property bool expanded: false
                        width: groupList.width
                        Rectangle {
                            visible: groupRow.index > 0
                            width: parent.width - 32; height: 1; x: 16
                            color: lineColor
                        }
                        Item {
                            width: parent.width; height: 46
                            Text {
                                id: chevron
                                x: 16; anchors.verticalCenter: parent.verticalCenter
                                text: groupRow.expanded ? "▾" : "▸"
                                font.pixelSize: 12; color: subColor
                            }
                            Text {
                                anchors { left: chevron.right; leftMargin: 10; verticalCenter: parent.verticalCenter }
                                text: Lang.get("updates.group." + groupRow.modelData.key, _lang)
                                font.pixelSize: 13; color: textColor
                            }
                            Row {
                                anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                                spacing: 10
                                Rectangle {
                                    visible: groupRow.modelData.restart !== ""
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: tagText.implicitWidth + 14; height: 20
                                    radius: 10
                                    color: Qt.rgba(0.91, 0.63, 0.13, 0.18)
                                    Text {
                                        id: tagText
                                        anchors.centerIn: parent
                                        text: groupRow.modelData.restart === "reboot" ? Lang.get("updates.tagReboot", _lang) : Lang.get("updates.tagRelogin", _lang)
                                        font.pixelSize: 11; color: warnColor
                                    }
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: countText(groupRow.modelData.items.length)
                                    font.pixelSize: 12; color: subColor
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: groupRow.expanded = !groupRow.expanded
                            }
                        }
                        Column {
                            visible: groupRow.expanded
                            x: 38; width: parent.width - 54
                            bottomPadding: 10
                            Repeater {
                                model: groupRow.expanded ? groupRow.modelData.items : []
                                delegate: Text {
                                    required property var modelData
                                    width: parent.width; elide: Text.ElideRight
                                    text: modelData.name + "   " + modelData.old + " → " + modelData.new
                                    font.pixelSize: 11; font.family: "monospace"; color: subColor
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // === Advanced: AUR switch, all Arch news, raw package list ===
    Item {
        width: parent.width; height: 34
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Text { text: showAdvanced ? "▾" : "▸"; font.pixelSize: 12; color: subColor; anchors.verticalCenter: parent.verticalCenter }
            Text { text: Lang.get("updates.advanced", _lang); font.pixelSize: 14; font.bold: true; color: subColor }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: showAdvanced = !showAdvanced }
    }

    Column {
        visible: showAdvanced
        width: parent.width
        spacing: 16

        // Same switch and spacing as the optional-app controls in AppsCategory.
        Rectangle {
            width: parent.width
            height: aurContent.implicitHeight + 32
            radius: settingsMenu.borderRadius
            color: cardColor
            border.width: 1
            border.color: lineColor
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

        // Arch asks to read the news before upgrading.
        Column {
            width: parent.width
            spacing: 8
            Text { text: Lang.get("updates.news", _lang); font.pixelSize: 14; font.bold: true; color: textColor }
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

        Column {
            visible: updateCount > 0
            width: parent.width
            spacing: 4
            Text { text: Lang.get("updates.allPackages", _lang) + " (" + updateCount + ")"; font.pixelSize: 14; font.bold: true; color: textColor }
            Repeater {
                model: showAdvanced ? updates : []
                delegate: Text {
                    required property var modelData
                    width: updatesPage.width
                    elide: Text.ElideRight
                    text: modelData.name + (modelData.source === "aur" ? " (AUR)" : "") + "   " + modelData.old + " → " + modelData.new
                    font.pixelSize: 11
                    font.family: "monospace"
                    color: subColor
                }
            }
        }
    }
}
