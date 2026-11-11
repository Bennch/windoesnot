import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell
import "../i18n/Lang.js" as Lang

Rectangle {
    id: card
    property var flow: null
    property var settingsMenu: null
    property bool taskActive: false
    property bool taskBusy: false
    property string taskTitle: ""
    property string taskText: ""
    property int taskStep: 0
    property int taskTotal: 0
    property bool taskError: false
    property string taskDetail: ""
    signal dismissTask()
    readonly property bool dark: !settingsMenu || settingsMenu.darkMode
    readonly property string language: settingsMenu ? settingsMenu.uiLanguage : "de"
    readonly property color accent: settingsMenu ? settingsMenu.accentColor : "#fe6f2d"
    readonly property color foreground: dark ? "#eeeeee" : "#222222"
    readonly property color fieldColor: dark ? "#1a1a1a" : "#ffffff"
    readonly property bool responding: flow !== null && flow.isResponseRequired
    implicitHeight: content.implicitHeight + 40
    color: dark ? "#222222" : "#f6f6f6"
    radius: settingsMenu ? settingsMenu.borderRadius : 10
    border.color: dark ? "#444444" : "#cccccc"
    border.width: 1
    onFlowChanged: { response.clear(); focusResponse.restart() }
    onRespondingChanged: { response.clear(); if (responding) focusResponse.restart() }
    Component.onDestruction: response.clear()

    function submit() {
        if (!responding) return
        flow.submit(response.text)
        response.clear()
    }
    function cancel() {
        response.clear()
        if (flow) flow.cancelAuthenticationRequest()
        else if (taskActive && !taskBusy) dismissTask()
    }
    Timer { id: focusResponse; interval: 60; onTriggered: response.forceActiveFocus() }
    Keys.onEscapePressed: (event) => { cancel(); event.accepted = true }
    Column {
        id: content
        x: 20; y: 20; width: parent.width - 40
        spacing: 14
        Row {
            spacing: 12
            Image {
                width: 28; height: 28
                source: "../img/Win11-dark/actions/32/system-lock-screen.svg"
                fillMode: Image.PreserveAspectFit
                layer.enabled: true
                layer.effect: MultiEffect { colorization: 1; colorizationColor: card.foreground }
            }
            Text {
                text: card.taskActive ? card.taskTitle : Lang.get("auth.title", card.language)
                color: card.foreground; font.pixelSize: 18; font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Text {
            width: parent.width
            visible: card.flow !== null
            text: !card.flow ? "" : card.flow.actionId === "org.windoesnot.snapshots.create"
                ? Lang.get("auth.createPoint", card.language)
                : card.flow.actionId === "org.windoesnot.snapshots.delete"
                    ? Lang.get("auth.deletePoint", card.language)
                    : card.flow.actionId === "org.windoesnot.snapshots.schedule"
                        ? Lang.get("auth.schedulePoints", card.language) : card.flow.message
            color: card.foreground; wrapMode: Text.WordWrap; font.pixelSize: 13
            textFormat: Text.PlainText
        }
        ComboBox {
            id: identityChooser
            width: parent.width
            height: 40
            leftPadding: 12
            rightPadding: 32
            topPadding: 0
            bottomPadding: 0
            visible: card.responding && count > 1
            model: card.flow ? card.flow.identities : []
            textRole: "displayName"
            onActivated: if (card.flow) card.flow.selectedIdentity = card.flow.identities[currentIndex]
            contentItem: Text {
                text: identityChooser.displayText
                color: card.foreground
                font.pixelSize: 13
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            delegate: ItemDelegate {
                width: identityChooser.width
                height: 40
                contentItem: Text {
                    text: modelData.displayName
                    font.pixelSize: 13
                    color: card.foreground
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    color: highlighted ? (card.dark ? "#3a3a3a" : "#dddddd") : card.fieldColor
                }
                highlighted: identityChooser.highlightedIndex === index
            }
            popup: Popup {
                y: identityChooser.height + 4
                width: identityChooser.width
                implicitHeight: Math.min(240, identityList.contentHeight + 2)
                padding: 1
                contentItem: ListView {
                    id: identityList
                    clip: true
                    implicitHeight: contentHeight
                    model: identityChooser.popup.visible ? identityChooser.delegateModel : null
                    currentIndex: identityChooser.highlightedIndex
                }
                background: Rectangle {
                    color: card.fieldColor; radius: 6
                    border.color: card.dark ? "#444444" : "#cccccc"
                }
            }
            background: Rectangle { color: card.fieldColor; radius: 6; border.color: card.dark ? "#444" : "#ccc" }
        }
        Text {
            width: parent.width
            visible: card.responding && text.length > 0
            text: card.flow && card.flow.selectedIdentity ? card.flow.selectedIdentity.displayName : ""
            color: card.foreground; font.pixelSize: 12
        }
        TextField {
            id: response
            objectName: "authenticationResponse"
            width: parent.width; height: 40
            enabled: card.responding
            visible: !card.taskActive || card.responding
            placeholderText: !card.responding ? Lang.get("auth.wait", card.language)
                : (!card.flow.responseVisible || /^password\s*:/i.test(card.flow.inputPrompt))
                    ? Lang.get("auth.passwordPlaceholder", card.language) : card.flow.inputPrompt
            echoMode: card.flow && card.flow.responseVisible ? TextInput.Normal : TextInput.Password
            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
            selectByMouse: false
            color: card.foreground
            placeholderTextColor: card.dark ? "#aaaaaa" : "#666666"
            background: Rectangle {
                color: card.fieldColor; radius: 6
                border.color: response.activeFocus ? card.accent : (card.dark ? "#444444" : "#cccccc")
            }
            onAccepted: card.submit()
        }
        Text {
            width: parent.width
            visible: text.length > 0
            text: card.flow ? card.flow.supplementaryMessage : ""
            color: card.flow && card.flow.supplementaryIsError ? "#e66c59" : card.foreground
            textFormat: Text.PlainText; wrapMode: Text.WordWrap; font.pixelSize: 12
        }
        Column {
            width: parent.width
            spacing: 10
            visible: card.taskActive
            Text {
                width: parent.width
                text: card.taskText + (card.taskBusy && card.taskStep > 0 && card.taskTotal > 0
                    ? " (" + card.taskStep + "/" + card.taskTotal + ")" : "")
                color: card.taskError ? "#e66c59" : card.foreground
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            ProgressBar {
                objectName: "authenticationTaskProgress"
                width: parent.width
                from: 0; to: 1
                value: card.taskBusy || card.taskError ? 0 : 1
                indeterminate: card.taskBusy
                palette.highlight: card.accent
                palette.base: card.fieldColor
            }
            Text {
                width: parent.width
                visible: card.taskError && card.taskDetail.length > 0
                text: card.taskDetail
                color: card.foreground; font.pixelSize: 12
                wrapMode: Text.WordWrap; textFormat: Text.PlainText
            }
            Rectangle {
                visible: !card.taskBusy
                width: parent.width; height: 36; radius: 6
                color: card.accent
                Text { anchors.centerIn: parent; text: Lang.get("shell.close", card.language); color: "white"; font.pixelSize: 13 }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: card.dismissTask() }
            }
        }
        Row {
            visible: !card.taskActive || card.responding
            spacing: 10
            Repeater {
                model: ["common.cancel", "auth.confirm"]
                delegate: Rectangle {
                    required property string modelData
                    required property int index
                    width: (content.width - 10) / 2; height: 36; radius: 6
                    color: index === 1 ? card.accent : (card.dark ? "#303030" : "#e6e6e6")
                    opacity: index === 1 && !card.responding ? 0.5 : 1
                    Text {
                        anchors.centerIn: parent
                        text: Lang.get(modelData, card.language)
                        color: index === 1 ? "#ffffff" : card.foreground; font.pixelSize: 13
                    }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        enabled: index === 0 || card.responding
                        onClicked: index === 0 ? card.cancel() : card.submit()
                    }
                }
            }
        }
    }
}
