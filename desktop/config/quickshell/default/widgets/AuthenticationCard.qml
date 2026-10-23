import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell
import "../i18n/Lang.js" as Lang

Rectangle {
    id: card
    property var flow: null
    property var settingsMenu: null
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
                text: Lang.get("auth.title", card.language)
                color: card.foreground; font.pixelSize: 18; font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Text {
            width: parent.width
            text: card.flow ? card.flow.message : ""
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
            visible: count > 1
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
            visible: text.length > 0
            text: card.flow && card.flow.selectedIdentity ? card.flow.selectedIdentity.displayName : ""
            color: card.foreground; font.pixelSize: 12
        }
        TextField {
            id: response
            objectName: "authenticationResponse"
            width: parent.width; height: 40
            enabled: card.responding
            placeholderText: card.flow ? card.flow.inputPrompt : Lang.get("auth.wait", card.language)
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
        Row {
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
