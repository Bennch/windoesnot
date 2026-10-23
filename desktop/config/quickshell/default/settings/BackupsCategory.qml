import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Item {
    id: backupsCategory
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"

    width: parent.width
    height: backupsReady ? contentColumn.height : unavailableNotice.implicitHeight
    property bool backupsReady: false
    property bool liveSession: false

    // State
    property bool busy: false
    property string statusText: ""
    property bool confirmDeleteVisible: false
    property string deleteCandidateId: ""
    property string deleteCandidateDate: ""

    // Schedule state
    property bool monthlyEnabled: false
    property int monthlyKeep: 2
    property bool weeklyEnabled: false
    property int weeklyKeep: 3
    property bool dailyEnabled: true
    property int dailyKeep: 5
    property bool hourlyEnabled: false
    property int hourlyKeep: 6

    ListModel { id: snapshotModel }

    property bool customRetention: false
    property bool scheduleLoaded: false
    property bool timelineActive: false
    property bool timelineConfigured: false

    function formatDateTime(value) {
        const date = new Date(value)
        return isNaN(date.getTime()) ? value : date.toLocaleString(Qt.locale(_lang), "dd.MM.yyyy HH:mm")
    }

    function acceptStatus(data, updateSchedule) {
        backupsReady = data.ready === true
        liveSession = data.live === true
        if (!backupsReady) return
        snapshotModel.clear()
        for (const snapshot of data.snapshots)
            snapshotModel.append({snapshotId: snapshot.id, date: formatDateTime(snapshot.date)})
        timelineActive = data.timeline && data.timerActive
        timelineConfigured = data.timeline
        if (updateSchedule) {
            customRetention = false
            for (const period of ["monthly", "weekly", "daily", "hourly"]) {
                const raw = String(data.schedule[period] || "0")
                if (raw.indexOf("-") >= 0) customRetention = true
                const count = parseInt(raw.split("-").pop()) || 0
                if (count > 365) customRetention = true
                backupsCategory[period + "Keep"] = Math.min(365, Math.max(1, count))
                backupsCategory[period + "Enabled"] = data.timeline && count > 0
            }
            scheduleLoaded = true
        }
    }

    function runAction(action, args, updateSchedule) {
        if (busy || liveSession || (action !== "status" && !backupsReady)) return
        busy = true
        statusText = ""
        // Keeps Settings open if the fallback agent needs a separate window.
        if (settingsMenu) settingsMenu.fileDialogOpen = true
        snapshotProcess.operation = action
        snapshotProcess.updateSchedule = updateSchedule
        snapshotProcess.command = ["/usr/bin/pkexec", "--disable-internal-agent",
            "/usr/lib/windoesnot/snapshots.py", action, JSON.stringify(args)]
        snapshotProcess.running = true
    }
    function refreshSnapshots() { runAction("status", {}, true) }
    function createSnapshot() { runAction("create", {}, false) }
    function deleteSnapshotById(number) { runAction("delete", {id: String(number)}, false) }
    function applySchedule() {
        const schedule = {}
        for (const period of ["monthly", "weekly", "daily", "hourly"])
            schedule[period] = backupsCategory[period + "Enabled"] ? backupsCategory[period + "Keep"] : 0
        runAction("schedule", schedule, true)
    }
    Process {
        id: snapshotProcess
        property string operation: ""
        property bool updateSchedule: false
        stdout: StdioCollector { id: snapshotOutput }
        stderr: StdioCollector { id: snapshotError }
        onExited: (code) => {
            busy = false
            if (settingsMenu) settingsMenu.fileDialogOpen = false
            if (code === 0) {
                try { acceptStatus(JSON.parse(snapshotOutput.text), updateSchedule) }
                catch (error) { statusText = Lang.get("backups.error", _lang) + ": " + error }
            } else if (code === 126) {
                statusText = Lang.get("backups.cancelled", _lang)
            } else {
                let detail = snapshotError.text.trim()
                try { detail = JSON.parse(detail).error } catch (error) {}
                statusText = Lang.get("backups.error", _lang) + ": " + detail
            }
        }
    }
    Process {
        running: true
        command: ["sh", "-c", "if [ -f /etc/windoesnot-image-build ]; then exit 10; fi; test -x /usr/lib/windoesnot/snapshots.py"]
        onExited: (code) => {
            liveSession = code === 10
            backupsReady = code === 0
            if (backupsReady) refreshSnapshots()
        }
    }

    Text {
        id: unavailableNotice
        visible: !backupsReady
        width: parent.width
        text: Lang.get(liveSession ? "backups.liveDisabled" : "backups.unavailable", _lang) + (statusText ? "\n" + statusText : "")
        color: settingsMenu.darkMode ? "#aaa" : "#555"
        font.pixelSize: 14
        wrapMode: Text.WordWrap
    }

    Column {
        id: contentColumn
        visible: backupsReady
        enabled: backupsReady
        width: parent.width
        spacing: 25

    // === Header with Create Button ===
    Row {
        width: parent.width
        height: 40
        spacing: 15

        Text {
            text: Lang.get("backups.snapshotsTitle", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
            height: parent.height
            verticalAlignment: Text.AlignVCenter
        }

        Item {
            width: parent.width - 360
            height: parent.height
        }

        Rectangle {
            width: 160
            height: 36
            radius: 6
            color: busy
                ? (settingsMenu.darkMode ? "#444444" : "#cccccc")
                : settingsMenu.accentColor
            opacity: busy ? 0.5 : 1.0

            Row {
                anchors.centerIn: parent
                height: parent.height
                spacing: 6

                BusyIndicator {
                    visible: busy
                    running: visible
                    width: 16
                    height: 16
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: busy ? (_lang === "de" ? "Läuft..." : "Running...") : Lang.get("backups.create", _lang)
                    color: "#fff"
                    font.pixelSize: 13
                    font.bold: true
                    height: parent.height
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: createMouse
                anchors.fill: parent
                enabled: !busy
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: createSnapshot()
            }
        }
    }

    // Error message bar (only when error occurs)
    Rectangle {
        visible: statusText.length > 0
        width: parent.width
        height: 40
        radius: 6
        color: settingsMenu.darkMode ? "#3d2a2a" : "#ffe0e0"
        border.width: 1
        border.color: "#c23838"

        Text {
            anchors.centerIn: parent
            text: statusText
            color: settingsMenu.darkMode ? "#ff9999" : "#c23838"
            font.pixelSize: 12
        }

        MouseArea {
            anchors.fill: parent
            onClicked: statusText = ""
        }
    }

    // === Snapshot List ===
    Rectangle {
        width: parent.width
        height: 400
        radius: settingsMenu.borderRadius
        color: settingsMenu.darkMode ? "#1a1a1a" : "#fff"
        border.width: 1
        border.color: settingsMenu.darkMode ? "#333" : "#ddd"

        Column {
            width: parent.width - 2
            height: parent.height - 2
            x: 1
            y: 1
            spacing: 0

            // Header
            Rectangle {
                width: parent.width
                height: 40
                color: settingsMenu.darkMode ? "#252525" : "#f0f0f0"

                Row {
                    width: parent.width - 40
                    height: parent.height
                    x: 20
                    spacing: 0

                    Text {
                        width: parent.width - 60
                        text: Lang.get("backups.columnDate", _lang)
                        color: settingsMenu.darkMode ? "#bbb" : "#555"
                        font.pixelSize: 11
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        height: parent.height
                    }
                    Text {
                        width: 60
                        text: ""
                        height: parent.height
                    }
                }
            }

            // Separator
            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#333" : "#ddd"
            }

            // List
            ListView {
                id: snapshotList
                width: parent.width
                height: parent.height - 41
                clip: true
                model: snapshotModel

                delegate: Rectangle {
                    width: snapshotList.width
                    height: 48
                    color: index % 2 === 0
                        ? (settingsMenu.darkMode ? "#1e1e1e" : "#fafafa")
                        : (settingsMenu.darkMode ? "#1a1a1a" : "#fff")

                    Row {
                        width: parent.width - 40
                        height: parent.height
                        x: 20
                        spacing: 0

                        Text {
                            width: parent.width - 60
                            text: model.date
                            color: settingsMenu.darkMode ? "#ddd" : "#333"
                            font.pixelSize: 13
                            verticalAlignment: Text.AlignVCenter
                            height: parent.height
                            elide: Text.ElideRight
                        }

                        Item {
                            width: 60
                            height: parent.height

                            Rectangle {
                                width: 36
                                height: 32
                                radius: 6
                                x: (parent.width - width) / 2
                                y: (parent.height - height) / 2
                                color: deleteMouse.containsMouse ? "#d64545" : "#c23838"

                                Text {
                                    anchors.centerIn: parent
                                    text: "✕"
                                    color: "#fff"
                                    font.pixelSize: 16
                                    font.bold: true
                                }

                                MouseArea {
                                    id: deleteMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        deleteCandidateId = model.snapshotId
                                        deleteCandidateDate = model.date
                                        confirmDeleteVisible = true
                                    }
                                }
                            }
                        }
                    }
                }

                ScrollIndicator.vertical: ScrollIndicator {}
            }

            // Empty state
            Item {
                width: parent.width
                height: parent.height - 41
                visible: snapshotModel.count === 0 && !busy

                Text {
                    x: (parent.width - width) / 2
                    y: (parent.height - height) / 2
                    text: Lang.get("backups.noData", _lang)
                    color: settingsMenu.darkMode ? "#666" : "#999"
                    font.pixelSize: 14
                }
            }
        }
    }

    // === Automatic Backups Schedule ===
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("backups.scheduleTitle", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Text {
            width: parent.width
            text: Lang.get("backups.scheduleHint", _lang) + (timelineConfigured && !timelineActive ? "\n" + Lang.get("backups.timerInactive", _lang) : "") + (customRetention ? "\n" + Lang.get("backups.scheduleCustom", _lang) : "")
            wrapMode: Text.WordWrap
            color: settingsMenu.darkMode ? "#aaaaaa" : "#555555"
            font.pixelSize: 12
        }
        // Schedule Table
        Rectangle {
            width: parent.width
            height: scheduleColumn.height + 2
            radius: 6
            color: settingsMenu.darkMode ? "#1a1a1a" : "#fff"
            border.width: 1
            border.color: settingsMenu.darkMode ? "#333" : "#ddd"

            Column {
                id: scheduleColumn
                width: parent.width - 2
                x: 1
                y: 1
                spacing: 0

                // Header
                Rectangle {
                    width: parent.width
                    height: 40
                    color: settingsMenu.darkMode ? "#252525" : "#f0f0f0"

                    Row {
                        width: parent.width - 40
                        height: parent.height
                        x: 20
                        spacing: 10

                        Item { width: 30; height: parent.height }
                        Text {
                            width: 100
                            text: Lang.get("backups.frequency", _lang)
                            color: settingsMenu.darkMode ? "#bbb" : "#555"
                            font.pixelSize: 11
                            font.bold: true
                            verticalAlignment: Text.AlignVCenter
                            height: parent.height
                        }
                        Item {
                            width: parent.width - 140
                            height: parent.height

                            Text {
                                anchors.right: parent.right
                                text: Lang.get("backups.retention", _lang)
                                color: settingsMenu.darkMode ? "#bbb" : "#555"
                                font.pixelSize: 11
                                font.bold: true
                                verticalAlignment: Text.AlignVCenter
                                height: parent.height
                            }
                        }
                    }
                }

                Rectangle { width: parent.width; height: 1; color: settingsMenu.darkMode ? "#333" : "#ddd" }

                // Rows
                Repeater {
                    model: [
                        { nameKey: "backups.monthly", star: true, enabled: monthlyEnabled, keep: monthlyKeep, prop: "monthly" },
                        { nameKey: "backups.weekly", star: true, enabled: weeklyEnabled, keep: weeklyKeep, prop: "weekly" },
                        { nameKey: "backups.daily", star: true, enabled: dailyEnabled, keep: dailyKeep, prop: "daily" },
                        { nameKey: "backups.hourly", star: true, enabled: hourlyEnabled, keep: hourlyKeep, prop: "hourly" },
                    ]

                    delegate: Rectangle {
                        width: scheduleColumn.width
                        height: 50
                        color: index % 2 === 0
                            ? (settingsMenu.darkMode ? "#1e1e1e" : "#f5f5f5")
                            : (settingsMenu.darkMode ? "#1a1a1a" : "#fafafa")

                        Row {
                            width: parent.width - 40
                            height: parent.height
                            x: 20
                            spacing: 10

                            CheckBox {
                                id: checkbox
                                width: 30
                                height: parent.height
                                checked: modelData.enabled
                                onClicked: {
                                    if (modelData.prop === "monthly") backupsCategory.monthlyEnabled = checked
                                    else if (modelData.prop === "weekly") backupsCategory.weeklyEnabled = checked
                                    else if (modelData.prop === "daily") backupsCategory.dailyEnabled = checked
                                    else if (modelData.prop === "hourly") backupsCategory.hourlyEnabled = checked
                                }

                                indicator: Rectangle {
                                    width: 20
                                    height: 20
                                    x: 5
                                    y: (parent.height - height) / 2
                                    radius: 3
                                    border.width: 2
                                    border.color: settingsMenu.accentColor
                                    color: checkbox.checked ? settingsMenu.accentColor : "transparent"

                                    Text {
                                        visible: checkbox.checked
                                        anchors.centerIn: parent
                                        text: "✓"
                                        color: "#fff"
                                        font.pixelSize: 14
                                        font.bold: true
                                    }
                                }
                            }

                            Text {
                                width: 100
                                text: Lang.get(modelData.nameKey, _lang) + (modelData.star ? " *" : "")
                                color: settingsMenu.darkMode ? "#ddd" : "#333"
                                font.pixelSize: 13
                                verticalAlignment: Text.AlignVCenter
                                height: parent.height
                            }

                            Item {
                                width: parent.width - 140
                                height: parent.height

                            SpinBox {
                                id: spinBox
                                width: 110
                                height: 36
                                from: 1
                                to: 365
                                value: modelData.keep
                                editable: true
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.right: parent.right

                                onValueModified: {
                                    if (modelData.prop === "monthly") backupsCategory.monthlyKeep = value
                                    else if (modelData.prop === "weekly") backupsCategory.weeklyKeep = value
                                    else if (modelData.prop === "daily") backupsCategory.dailyKeep = value
                                    else if (modelData.prop === "hourly") backupsCategory.hourlyKeep = value
                                }

                                contentItem: TextInput {
                                    text: spinBox.textFromValue(spinBox.value, spinBox.locale)
                                    font.pixelSize: 12
                                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                    horizontalAlignment: Qt.AlignHCenter
                                    verticalAlignment: Qt.AlignVCenter
                                    readOnly: !spinBox.editable
                                    validator: spinBox.validator
                                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                                }

                                background: Rectangle {
                                    color: "transparent"
                                    border.width: 1
                                    border.color: settingsMenu.darkMode ? "#444" : "#ccc"
                                    radius: 4
                                }

                                up.indicator: Rectangle {
                                    width: 32
                                    height: parent.height / 2
                                    x: parent.width - width
                                    y: 0
                                    color: "transparent"

                                    Text {
                                        anchors.centerIn: parent
                                        text: "+"
                                        color: settingsMenu.darkMode ? "#aaa" : "#666"
                                        font.pixelSize: 18
                                    }
                                }

                                down.indicator: Rectangle {
                                    width: 32
                                    height: parent.height / 2
                                    x: parent.width - width
                                    y: parent.height / 2
                                    color: "transparent"

                                    Text {
                                        anchors.centerIn: parent
                                        text: "−"
                                        color: settingsMenu.darkMode ? "#aaa" : "#666"
                                        font.pixelSize: 18
                                    }
                                }
                            }
                            }  // End Item (SpinBox container)
                        }
                    }
                }
            }
        }

        // Apply Button
        Rectangle {
            width: 140
            height: 36
            radius: 6
            color: busy ? (settingsMenu.darkMode ? "#444444" : "#cccccc") : settingsMenu.accentColor
            opacity: busy ? 0.5 : 1.0

            Text {
                anchors.centerIn: parent
                text: busy ? Lang.get("backups.applying", _lang) : Lang.get("backups.apply", _lang)
                color: "#fff"
                font.pixelSize: 13
                font.bold: true
            }

            MouseArea {
                anchors.fill: parent
                enabled: !busy
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: applySchedule()
            }
        }

        Text {
            width: parent.width
            text: Lang.get("backups.authHint", _lang)
            color: settingsMenu.darkMode ? "#888" : "#777"
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }
    }
    }  // End contentColumn

    // === Confirm Delete Dialog ===
    Rectangle {
        visible: confirmDeleteVisible
        width: parent.width
        height: Math.max(500, parent.height)
        x: 0
        y: 0
        color: "#40000000"
        z: 100

        MouseArea {
            anchors.fill: parent
            onClicked: confirmDeleteVisible = false
        }

        Rectangle {
            width: Math.min(450, parent.width - 24)
            height: dialogContent.height + 40
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            radius: settingsMenu.borderRadius
            color: settingsMenu.darkMode ? "#222" : "#fff"
            border.width: 1
            border.color: settingsMenu.darkMode ? "#444" : "#ccc"

            Column {
                id: dialogContent
                width: parent.width - 40
                x: 20
                y: 20
                spacing: 20

                Text {
                    text: Lang.get("backups.confirmDeleteTitle", _lang)
                    font.pixelSize: 18
                    font.bold: true
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                }

                Text {
                    width: parent.width
                    text: (_lang === "de"
                        ? "Möchten Sie den Snapshot vom "
                        : "Do you want to delete the snapshot from ") + deleteCandidateDate + "?"
                    wrapMode: Text.WordWrap
                    color: settingsMenu.darkMode ? "#ccc" : "#444"
                    font.pixelSize: 13
                }

                Row {
                    spacing: 10

                    Rectangle {
                        width: 140
                        height: 36
                        radius: 6
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#e8e8e8"
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#444444" : "#cccccc"

                        Text {
                            anchors.centerIn: parent
                            text: Lang.get("common.cancel", _lang)
                            color: settingsMenu.darkMode ? "#cccccc" : "#444444"
                            font.pixelSize: 13
                        }

                        MouseArea {
                            id: cancelMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: confirmDeleteVisible = false
                        }
                    }

                    Rectangle {
                        width: 140
                        height: 36
                        radius: 6
                        color: busy ? (settingsMenu.darkMode ? "#444444" : "#cccccc") : "#c23838"
                        border.width: 1
                        border.color: "#e65555"
                        opacity: busy ? 0.5 : 1.0

                        Text {
                            anchors.centerIn: parent
                            text: Lang.get("apps.delete", _lang)
                            color: "#fff"
                            font.pixelSize: 13
                            font.bold: true
                        }

                        MouseArea {
                            id: deleteConfirmMouse
                            anchors.fill: parent
                            enabled: !busy
                            hoverEnabled: true
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                confirmDeleteVisible = false
                                deleteSnapshotById(deleteCandidateId)
                            }
                        }
                    }
                }
            }
        }
    }
}
