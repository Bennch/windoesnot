import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "." as Tools
import "../i18n/Lang.js" as Lang

Column {
    id: page
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property color foreground: dark ? "#ffffff" : "#1a1a1a"
    readonly property color secondary: dark ? "#aaaaaa" : "#555555"
    property bool busy: false
    property bool ready: false
    property var printerState: null
    property string pendingAction: ""
    property var pendingArgs: ({})
    property string pendingDescription: ""
    property string result: ""

    width: parent.width
    spacing: 12

    function tr(key) { return Lang.get(key, _lang) }
    function refresh() {
        if (!busy) runAction("maintenance-status", {})
    }
    function requestAction(action, args, description) {
        if (!ready || busy) return
        pendingAction = action; pendingArgs = args; pendingDescription = description
        confirmation.open()
    }
    function runAction(action, args) {
        busy = true; worker.operation = action
        worker.command = (action === "maintenance-status" ? ["/usr/bin/python3", "-I"] : ["/usr/bin/pkexec", "--disable-internal-agent"])
            .concat(["/usr/lib/windoesnot/system_tools.py", action, JSON.stringify(args)])
        worker.running = true
    }

    Component.onCompleted: refresh()

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
                if (operation === "maintenance-status") {
                    printerState = data.printers || null
                    ready = true
                    result = ""
                } else {
                    result = page.tr("systemTools.done")
                    refresh()
                }
            } else {
                result = code === 126 ? page.tr("systemTools.cancelled")
                    : (data.error || errors.text.trim() || output.text.trim() || page.tr("systemTools.failed"))
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
    component ActionButton: Tools.SystemToolsButton {
        settingsMenu: page.settingsMenu
        enabled: page.ready && !page.busy
    }

    Text { text: page.tr("maintenance.printers"); color: page.foreground; font.pixelSize: 18; font.bold: true }
    Note { text: page.tr("maintenance.printersHint") }
    Note { visible: !page.ready; text: page.busy ? page.tr("systemTools.loading") : page.tr("systemTools.unavailable") }
    BusyIndicator { width: 28; height: 28; running: page.busy; visible: running; palette.highlight: settingsMenu ? settingsMenu.accentColor : "#fe6f2d" }
    Note { visible: page.result.length > 0; text: page.result; color: page.foreground }
    Note { visible: page.ready && page.printerState === null; text: page.tr("maintenance.printersUnavailable") }
    Note { visible: page.printerState !== null && page.printerState.cupsActive === false; text: page.tr("maintenance.printersCupsOff") }
    ActionButton {
        visible: page.printerState !== null && page.printerState.cupsActive === false
        primary: true
        text: page.tr("maintenance.printerSearch")
        onClicked: page.requestAction("printer-service-start", {}, page.tr("maintenance.confirmPrinterService"))
    }
    Note { visible: page.printerState !== null && page.printerState.cupsActive === true && page.printerState.printers.length === 0; text: page.tr("maintenance.printerNone") }
    Repeater {
        model: page.printerState !== null && page.printerState.cupsActive === true ? page.printerState.printers : []
        delegate: Rectangle {
            required property var modelData
            width: page.width; height: printerRow.implicitHeight + 20
            radius: settingsMenu ? settingsMenu.borderRadius : 8
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.dark ? "#3a3a3a" : "#d0d0d0"
            Column {
                id: printerRow
                x: 12; y: 10; width: parent.width - 24; spacing: 5
                Text { width: parent.width; text: modelData.name + (modelData.name === page.printerState.default ? "  (" + page.tr("maintenance.printerIsDefault") + ")" : ""); color: page.foreground; font.pixelSize: 13; font.bold: true; wrapMode: Text.WordWrap }
                Note { text: modelData.uri; font.pixelSize: 11 }
                ActionButton {
                    visible: modelData.name !== page.printerState.default
                    text: page.tr("maintenance.printerMakeDefault")
                    onClicked: page.requestAction("printer-default", {name: modelData.name}, page.tr("maintenance.confirmPrinterDefault"))
                }
            }
        }
    }
    Note { visible: page.printerState !== null && page.printerState.cupsActive === true; text: page.tr("maintenance.printerFound") }
    Note { visible: page.printerState !== null && page.printerState.cupsActive === true && page.printerState.candidates.length === 0; text: page.tr("maintenance.printerNoneFound") }
    Repeater {
        model: page.printerState !== null && page.printerState.cupsActive === true ? page.printerState.candidates : []
        delegate: Rectangle {
            id: candidateCard
            required property var modelData
            required property int index
            readonly property string printerName: {
                const host = String(modelData).replace(/^[^:]+:\/\//, "").split(/[\/?]/)[0].replace(/[^A-Za-z0-9-]+/g, "-").slice(0, 40)
                return host.length ? host : "Drucker-" + (index + 1)
            }
            width: page.width; height: candidateContent.implicitHeight + 20
            radius: settingsMenu ? settingsMenu.borderRadius : 8
            color: page.dark ? "#141414" : "#f5f5f5"
            border.width: 1; border.color: page.dark ? "#3a3a3a" : "#d0d0d0"
            Column {
                id: candidateContent
                x: 12; y: 10; width: parent.width - 24; spacing: 6
                Note { text: modelData; font.pixelSize: 11 }
                ActionButton {
                    enabled: page.ready && !page.busy && !(page.printerState.printers.some(function(p) { return p.name === candidateCard.printerName }))
                    text: page.tr("maintenance.printerAdd")
                    onClicked: page.requestAction("printer-add", {uri: candidateCard.modelData, name: candidateCard.printerName}, page.tr("maintenance.confirmPrinterAdd"))
                }
            }
        }
    }

    Tools.SystemToolsConfirm {
        id: confirmation
        settingsMenu: page.settingsMenu
        title: page.tr("systemTools.confirm")
        description: page.pendingDescription
        onAccepted: page.runAction(page.pendingAction, page.pendingArgs)
    }
}
