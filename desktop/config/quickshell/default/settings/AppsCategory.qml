import "../widgets"
import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"

    width: parent.width
    spacing: 30

    ShellSettings { width: parent.width; settingsMenu: parent.settingsMenu }

    Text {
        text: Lang.get("apps.optionalTools", _lang)
        font.pixelSize: 18
        font.bold: true
        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
    }

    Repeater {
        model: [
            { "propertyName": "showDockerTray", "title": "Docker", "description": "apps.dockerTrayDesc" },
            { "propertyName": "showOllamaTray", "title": "Ollama", "description": "apps.ollamaTrayDesc" },
            { "propertyName": "showNearbyTray", "title": Lang.get("nearby.title", _lang), "description": "apps.nearbyTrayDesc" }
        ]
        delegate: Row {
            required property var modelData
            width: parent.width
            spacing: 15
            Column {
                width: parent.width - 80
                spacing: 5
                Text {
                    text: modelData.title
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }
                Text {
                    text: Lang.get(modelData.description, _lang)
                    font.pixelSize: 12
                    color: settingsMenu.darkMode ? "#888" : "#666"
                    wrapMode: Text.WordWrap
                    width: parent.width
                }
            }
            Rectangle {
                property bool isOn: settingsMenu[modelData.propertyName]
                width: 60; height: 32; radius: 16
                anchors.verticalCenter: parent.verticalCenter
                color: isOn ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: parent.isOn ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on x { NumberAnimation { duration: 150 } }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: settingsMenu[modelData.propertyName] = !settingsMenu[modelData.propertyName]
                }
            }
        }
    }

    // Standard-Anwendungen
    Text {
        text: Lang.get("apps.defaultApps", _lang)
        font.pixelSize: 18
        font.bold: true
        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
    }

    Column {
        width: parent.width
        spacing: 20

        // File Manager
        Column {
            width: parent.width
            spacing: 10

            Text {
                text: Lang.get("apps.fileManager", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: fileManagerComboBox
                width: 400
                height: 40

                model: settingsMenu ? settingsMenu.fileManagerAppsModel : null
                textRole: "name"

                function syncIndex(desktopFile) {
                    if (!model || !desktopFile) return
                    for (var i = 0; i < model.count; i++) {
                        if (model.get(i).desktopFile === desktopFile) { currentIndex = i; return }
                    }
                }

                onModelChanged: { if (settingsMenu) syncIndex(settingsMenu.defaultFileManager) }

                Connections {
                    target: settingsMenu
                    function onDefaultFileManagerChanged() { fileManagerComboBox.syncIndex(settingsMenu.defaultFileManager) }
                }

                onActivated: {
                    if (settingsMenu && index >= 0) {
                        settingsMenu.defaultFileManager = model.get(index).desktopFile
                    }
                }

                background: Rectangle {
                    color: fileManagerComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: fileManagerComboBox.indicator.width + fileManagerComboBox.spacing
                    text: fileManagerComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: fileManagerComboBox.width - width - 12
                    y: fileManagerComboBox.topPadding + (fileManagerComboBox.availableHeight - height) / 2
                    text: "▼"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: fileManagerComboBox.height + 2
                    width: fileManagerComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: fileManagerComboBox.popup.visible ? fileManagerComboBox.delegateModel : null
                        currentIndex: fileManagerComboBox.highlightedIndex

                        ScrollIndicator.vertical: ScrollIndicator { }
                    }

                    background: Rectangle {
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1
                        radius: 6
                    }
                }

                delegate: ItemDelegate {
                    width: fileManagerComboBox.width - 2
                    contentItem: Text {
                        text: model.name
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: fileManagerComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }

            Text {
                text: Lang.get("apps.fileManagerHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Text Editor
        Column {
            width: parent.width
            spacing: 10

            Text {
                text: Lang.get("apps.textEditor", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: textEditorComboBox
                width: 400
                height: 40

                model: settingsMenu ? settingsMenu.textEditorAppsModel : null
                textRole: "name"

                function syncIndex(desktopFile) {
                    if (!model || !desktopFile) return
                    for (var i = 0; i < model.count; i++) {
                        if (model.get(i).desktopFile === desktopFile) { currentIndex = i; return }
                    }
                }

                onModelChanged: { if (settingsMenu) syncIndex(settingsMenu.defaultTextEditor) }

                Connections {
                    target: settingsMenu
                    function onDefaultTextEditorChanged() { textEditorComboBox.syncIndex(settingsMenu.defaultTextEditor) }
                }

                onActivated: {
                    if (settingsMenu && index >= 0) {
                        settingsMenu.defaultTextEditor = model.get(index).desktopFile
                    }
                }

                background: Rectangle {
                    color: textEditorComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: textEditorComboBox.indicator.width + textEditorComboBox.spacing
                    text: textEditorComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: textEditorComboBox.width - width - 12
                    y: textEditorComboBox.topPadding + (textEditorComboBox.availableHeight - height) / 2
                    text: "▼"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: textEditorComboBox.height + 2
                    width: textEditorComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: textEditorComboBox.popup.visible ? textEditorComboBox.delegateModel : null
                        currentIndex: textEditorComboBox.highlightedIndex

                        ScrollIndicator.vertical: ScrollIndicator { }
                    }

                    background: Rectangle {
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1
                        radius: 6
                    }
                }

                delegate: ItemDelegate {
                    width: textEditorComboBox.width - 2
                    contentItem: Text {
                        text: model.name
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: textEditorComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }

            Text {
                text: Lang.get("apps.textEditorHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Image Viewer
        Column {
            width: parent.width
            spacing: 10

            Text {
                text: Lang.get("apps.imageViewer", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: imageViewerComboBox
                width: 400
                height: 40

                model: settingsMenu ? settingsMenu.imageViewerAppsModel : null
                textRole: "name"

                function syncIndex(desktopFile) {
                    if (!model || !desktopFile) return
                    for (var i = 0; i < model.count; i++) {
                        if (model.get(i).desktopFile === desktopFile) { currentIndex = i; return }
                    }
                }

                onModelChanged: { if (settingsMenu) syncIndex(settingsMenu.defaultImageViewer) }

                Connections {
                    target: settingsMenu
                    function onDefaultImageViewerChanged() { imageViewerComboBox.syncIndex(settingsMenu.defaultImageViewer) }
                }

                onActivated: {
                    if (settingsMenu && index >= 0) {
                        settingsMenu.defaultImageViewer = model.get(index).desktopFile
                    }
                }

                background: Rectangle {
                    color: imageViewerComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: imageViewerComboBox.indicator.width + imageViewerComboBox.spacing
                    text: imageViewerComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: imageViewerComboBox.width - width - 12
                    y: imageViewerComboBox.topPadding + (imageViewerComboBox.availableHeight - height) / 2
                    text: "▼"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: imageViewerComboBox.height + 2
                    width: imageViewerComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: imageViewerComboBox.popup.visible ? imageViewerComboBox.delegateModel : null
                        currentIndex: imageViewerComboBox.highlightedIndex

                        ScrollIndicator.vertical: ScrollIndicator { }
                    }

                    background: Rectangle {
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1
                        radius: 6
                    }
                }

                delegate: ItemDelegate {
                    width: imageViewerComboBox.width - 2
                    contentItem: Text {
                        text: model.name
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: imageViewerComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }

            Text {
                text: Lang.get("apps.imageViewerHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // PDF Viewer
        Column {
            width: parent.width
            spacing: 10

            Text {
                text: Lang.get("apps.pdfViewer", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: pdfViewerComboBox
                width: 400
                height: 40

                model: settingsMenu ? settingsMenu.pdfViewerAppsModel : null
                textRole: "name"

                function syncIndex(desktopFile) {
                    if (!model || !desktopFile) return
                    for (var i = 0; i < model.count; i++) {
                        if (model.get(i).desktopFile === desktopFile) { currentIndex = i; return }
                    }
                }

                onModelChanged: { if (settingsMenu) syncIndex(settingsMenu.defaultPdfViewer) }

                Connections {
                    target: settingsMenu
                    function onDefaultPdfViewerChanged() { pdfViewerComboBox.syncIndex(settingsMenu.defaultPdfViewer) }
                }

                onActivated: {
                    if (settingsMenu && index >= 0) {
                        settingsMenu.defaultPdfViewer = model.get(index).desktopFile
                    }
                }

                background: Rectangle {
                    color: pdfViewerComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: pdfViewerComboBox.indicator.width + pdfViewerComboBox.spacing
                    text: pdfViewerComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: pdfViewerComboBox.width - width - 12
                    y: pdfViewerComboBox.topPadding + (pdfViewerComboBox.availableHeight - height) / 2
                    text: "▼"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: pdfViewerComboBox.height + 2
                    width: pdfViewerComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: pdfViewerComboBox.popup.visible ? pdfViewerComboBox.delegateModel : null
                        currentIndex: pdfViewerComboBox.highlightedIndex

                        ScrollIndicator.vertical: ScrollIndicator { }
                    }

                    background: Rectangle {
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1
                        radius: 6
                    }
                }

                delegate: ItemDelegate {
                    width: pdfViewerComboBox.width - 2
                    contentItem: Text {
                        text: model.name
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: pdfViewerComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }

            Text {
                text: Lang.get("apps.pdfViewerHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Web Browser
        Column {
            width: parent.width
            spacing: 10

            Text {
                text: Lang.get("apps.webBrowser", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: webBrowserComboBox
                width: 400
                height: 40

                model: settingsMenu ? settingsMenu.webBrowserAppsModel : null
                textRole: "name"

                function syncIndex(desktopFile) {
                    if (!model || !desktopFile) return
                    for (var i = 0; i < model.count; i++) {
                        if (model.get(i).desktopFile === desktopFile) { currentIndex = i; return }
                    }
                }

                onModelChanged: { if (settingsMenu) syncIndex(settingsMenu.defaultWebBrowser) }

                Connections {
                    target: settingsMenu
                    function onDefaultWebBrowserChanged() { webBrowserComboBox.syncIndex(settingsMenu.defaultWebBrowser) }
                }

                onActivated: {
                    if (settingsMenu && index >= 0) {
                        settingsMenu.defaultWebBrowser = model.get(index).desktopFile
                    }
                }

                background: Rectangle {
                    color: webBrowserComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: webBrowserComboBox.indicator.width + webBrowserComboBox.spacing
                    text: webBrowserComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: webBrowserComboBox.width - width - 12
                    y: webBrowserComboBox.topPadding + (webBrowserComboBox.availableHeight - height) / 2
                    text: "▼"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: webBrowserComboBox.height + 2
                    width: webBrowserComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: webBrowserComboBox.popup.visible ? webBrowserComboBox.delegateModel : null
                        currentIndex: webBrowserComboBox.highlightedIndex

                        ScrollIndicator.vertical: ScrollIndicator { }
                    }

                    background: Rectangle {
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1
                        radius: 6
                    }
                }

                delegate: ItemDelegate {
                    width: webBrowserComboBox.width - 2
                    contentItem: Text {
                        text: model.name
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: webBrowserComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }

            Text {
                text: Lang.get("apps.webBrowserHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Terminal
        Column {
            width: parent.width
            spacing: 10

            Text {
                text: Lang.get("apps.terminal", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: terminalComboBox
                width: 400
                height: 40
                model: settingsMenu ? settingsMenu.terminalAppsModel : null
                textRole: "name"

                function syncIndex(execCmd) {
                    if (!model || !execCmd) return
                    for (var i = 0; i < model.count; i++) {
                        if (model.get(i).desktopFile === execCmd) { currentIndex = i; return }
                    }
                }

                onModelChanged: { if (settingsMenu) syncIndex(settingsMenu.defaultTerminal) }

                Connections {
                    target: settingsMenu
                    function onDefaultTerminalChanged() { terminalComboBox.syncIndex(settingsMenu.defaultTerminal) }
                }

                onActivated: {
                    if (settingsMenu && index >= 0)
                        settingsMenu.defaultTerminal = model.get(index).desktopFile
                }

                background: Rectangle {
                    color: terminalComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1; radius: 6
                }
                contentItem: Text {
                    leftPadding: 12
                    rightPadding: terminalComboBox.indicator.width + terminalComboBox.spacing
                    text: terminalComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                }
                indicator: Text {
                    x: terminalComboBox.width - width - 12
                    y: terminalComboBox.topPadding + (terminalComboBox.availableHeight - height) / 2
                    text: "▼"; font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }
                popup: Popup {
                    y: terminalComboBox.height + 2
                    width: terminalComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1
                    contentItem: ListView {
                        clip: true; implicitHeight: contentHeight
                        model: terminalComboBox.popup.visible ? terminalComboBox.delegateModel : null
                        currentIndex: terminalComboBox.highlightedIndex
                        ScrollIndicator.vertical: ScrollIndicator { }
                    }
                    background: Rectangle {
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1; radius: 6
                    }
                }
                delegate: ItemDelegate {
                    width: terminalComboBox.width - 2
                    contentItem: Text {
                        text: model.name
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12; elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter; leftPadding: 12
                    }
                    highlighted: terminalComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }

            Text {
                text: Lang.get("apps.terminalHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }
    }

    // Trennlinie
    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Icon-Überschreibungen
    Text {
        text: Lang.get("apps.iconOverrides", _lang)
        font.pixelSize: 18
        font.bold: true
        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
    }

    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("apps.iconOverridesDesc", _lang)
            font.pixelSize: 12
            color: settingsMenu.darkMode ? "#666" : "#888"
            wrapMode: Text.WordWrap
            width: parent.width
        }

        // Suchfeld
        Row {
            spacing: 10

            Rectangle {
                width: 300
                height: 36
                radius: 6
                color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                border.width: 1
                border.color: overrideSearchInput.activeFocus ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")

                TextInput {
                    id: overrideSearchInput
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    verticalAlignment: TextInput.AlignVCenter
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    selectionColor: settingsMenu.accentColor
                    selectByMouse: true
                    clip: true

                    Text {
                        visible: parent.text.length === 0
                        text: Lang.get("apps.searchApp", _lang)
                        color: settingsMenu.darkMode ? "#666" : "#888"
                        font.pixelSize: 13
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }

            Text {
                id: appCountText
                text: "0 " + Lang.get("apps.appsCount", _lang)
                font.pixelSize: 12
                color: settingsMenu.darkMode ? "#666" : "#888"
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // App-Liste mit Overrides
        Rectangle {
            id: overrideListContainer
            width: parent.width
            height: 400
            radius: 8
            color: settingsMenu.darkMode ? "#1a1a1a" : "#e5e5e5"
            border.width: 1
            border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

            property var overridesMap: ({})

            function loadOverrides() {
                console.log("=== Loading overrides from replace.qml...")
                var configDir = Qt.resolvedUrl("..").toString().replace("file://", "")
                console.log("=== Config dir:", configDir)
                var proc = Qt.createQmlObject(
                    'import Quickshell.Io; Process { command: ["python3", "read_overrides.py"]; running: true; workingDirectory: "' +
                    configDir + '"; }',
                    overrideListContainer
                )
                proc.stdout = Qt.createQmlObject('import Quickshell.Io; StdioCollector { }', proc)
                proc.stderr = Qt.createQmlObject('import Quickshell.Io; StdioCollector { }', proc)

                proc.stdout.streamFinished.connect(function() {
                    try {
                        var jsonText = proc.stdout.text.trim()
                        console.log("=== Override JSON:", jsonText)
                        overridesMap = JSON.parse(jsonText)
                        console.log("=== Loaded overrides:", Object.keys(overridesMap))
                        updateFilteredApps()
                    } catch (e) {
                        console.error("=== Error parsing overrides:", e)
                        overridesMap = {}
                        updateFilteredApps()
                    }
                })

                proc.stderr.streamFinished.connect(function() {
                    if (proc.stderr.text.trim().length > 0) {
                        console.error("=== Error loading overrides:", proc.stderr.text)
                    }
                })
            }

            Component.onCompleted: loadOverrides()

            function updateFilteredApps() {
                if (!settingsMenu || !settingsMenu.desktopAppsModel) {
                    overrideListView.model = []
                    appCountText.text = "0 Apps"
                    return
                }

                console.log("=== updateFilteredApps called, desktopAppsModel.count:", settingsMenu.desktopAppsModel.count)
                console.log("=== overridesMap keys:", Object.keys(overridesMap))

                // Debug: zeige die ersten 10 App-Namen
                for (var j = 0; j < Math.min(10, settingsMenu.desktopAppsModel.count); j++) {
                    var debugApp = settingsMenu.desktopAppsModel.get(j)
                    console.log("=== App", j, ":", debugApp.name)
                }

                var apps = []
                var search = overrideSearchInput.text.toLowerCase()
                var isSearching = search.length > 0

                for (var i = 0; i < settingsMenu.desktopAppsModel.count; i++) {
                    var app = settingsMenu.desktopAppsModel.get(i)
                    var appName = app.name || ""

                    // Flexibles Matching für Overrides
                    var hasOverride = false
                    var matchedOverrideName = ""

                    // Entferne .desktop Endung für Vergleich
                    var cleanAppName = appName.replace(/\.desktop$/, "")

                    // Prüfe gegen alle Override-Namen
                    for (var overrideName in overridesMap) {
                        // Exakte Übereinstimmung
                        if (appName === overrideName || cleanAppName === overrideName) {
                            hasOverride = true
                            matchedOverrideName = overrideName
                            break
                        }

                        // Normalisierte Namen für besseres Matching
                        var normalizedAppName = cleanAppName.toLowerCase().replace(/[-_\.]/g, "").replace(/\s+/g, "")
                        var normalizedOverrideName = overrideName.toLowerCase().replace(/[-_\.]/g, "").replace(/\s+/g, "")

                        // Teilübereinstimmung (case-insensitive, ohne Bindestriche/Leerzeichen)
                        if (normalizedAppName.indexOf(normalizedOverrideName) !== -1 ||
                            normalizedOverrideName.indexOf(normalizedAppName) !== -1) {
                            hasOverride = true
                            matchedOverrideName = overrideName
                            break
                        }

                        // Spezielle Mappings für bekannte Fälle
                        if ((overrideName === "Files" && (cleanAppName.toLowerCase() === "org.gnome.nautilus" || cleanAppName.toLowerCase() === "nautilus")) ||
                            (overrideName === "Text Editor" && cleanAppName.toLowerCase().indexOf("texteditor") !== -1)) {
                            hasOverride = true
                            matchedOverrideName = overrideName
                            break
                        }
                    }

                    if (hasOverride) {
                        console.log("=== Found app with override:", appName, "->", matchedOverrideName)
                    }

                    // Wenn keine Suche: nur Apps mit Overrides zeigen
                    // Wenn Suche: alle passenden Apps zeigen
                    var shouldShow = isSearching ? appName.toLowerCase().indexOf(search) !== -1 : hasOverride

                    if (shouldShow) {
                        apps.push({
                            name: appName,
                            icon: app.icon || "application-x-executable",
                            cmd: app.cmd || "",
                            customIcon: app.customIcon || false,
                            overrideName: matchedOverrideName  // Name in replace.qml
                        })
                    }
                }

                console.log("=== Found", apps.length, "apps to show")
                overrideListView.model = apps

                if (isSearching) {
                    appCountText.text = apps.length + " " + Lang.get("apps.appsFound", _lang)
                } else {
                    appCountText.text = apps.length + " " + Lang.get("apps.overrides", _lang)
                }
            }

            Connections {
                target: overrideSearchInput
                function onTextChanged() {
                    overrideListContainer.updateFilteredApps()
                }
            }

            Connections {
                target: settingsMenu
                function onOverridesListChanged() {
                    console.log("=== Reloading overrides list...")
                    overrideListContainer.loadOverrides()
                }
            }

            ListView {
                id: overrideListView
                anchors.fill: parent
                anchors.margins: 1
                clip: true
                spacing: 2

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    width: 8
                    contentItem: Rectangle {
                        radius: 4
                        color: parent.pressed ? "#666" : (parent.hovered ? "#555" : "#444")
                    }
                }

                delegate: Rectangle {
                    width: overrideListView.width - 10
                    height: expanded ? 220 : 50
                    color: delegateMouseArea.containsMouse ? (settingsMenu.darkMode ? "#2a2a2a" : "#e0e0e0") : (settingsMenu.darkMode ? "#1f1f1f" : "#f0f0f0")
                    radius: 4

                    MouseArea {
                        id: delegateMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: expanded = !expanded
                        z: -1
                    }

                    property bool expanded: false
                    property var appData: modelData
                    property bool hasOverride: appData && appData.overrideName && appData.overrideName.length > 0

                    function loadValues() {
                        if (!appData || !appData.name) return

                        // Verwende overrideName wenn vorhanden, sonst appData Werte
                        var override = appData.overrideName ? overrideListContainer.overridesMap[appData.overrideName] : null

                        if (override) {
                            iconInput.text = override.icon || ""
                            cmdInput.text = override.cmd || ""
                            customIconCheckbox.checked = override.customIcon || false
                        } else {
                            iconInput.text = appData.icon || ""
                            cmdInput.text = appData.cmd || ""
                            customIconCheckbox.checked = appData.customIcon || false
                        }
                    }

                    onExpandedChanged: {
                        if (expanded) {
                            loadValues()
                        }
                    }

                    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        // Kopfzeile
                        Row {
                            width: parent.width
                            spacing: 12

                            // Icon-Vorschau
                            Rectangle {
                                width: 32
                                height: 32
                                radius: 4
                                color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                                anchors.verticalCenter: parent.verticalCenter

                                Image {
                                    anchors.centerIn: parent
                                    width: 24
                                    height: 24
                                    source: {
                                        if (!appData || !appData.name) return "image://icon/application-x-executable"

                                        var override = appData.overrideName ? overrideListContainer.overridesMap[appData.overrideName] : null
                                        if (override && override.icon) {
                                            // Korrigiere Pfad für Custom-Icons (von settings/ zurück zum Hauptverzeichnis)
                                            return override.customIcon ? ("../" + override.icon) : "image://icon/" + override.icon
                                        }

                                        return (appData.customIcon || false) ? appData.icon : "image://icon/" + (appData.icon || "application-x-executable")
                                    }
                                    fillMode: Image.PreserveAspectFit
                                    cache: false

                                    onStatusChanged: {
                                        if (status === Image.Error) {
                                            source = "image://icon/application-x-executable"
                                        }
                                    }
                                }
                            }

                            // App-Info
                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2

                                Text {
                                    text: appData.name
                                    font.pixelSize: 14
                                    font.bold: hasOverride
                                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                }

                                Text {
                                    text: hasOverride ? ("✓ " + Lang.get("apps.overridden", _lang)) : Lang.get("apps.standard", _lang)
                                    font.pixelSize: 11
                                    color: hasOverride ? settingsMenu.accentColor : "#666"
                                }
                            }
                        }

                        // Erweiterte Einstellungen
                        Column {
                            visible: expanded
                            width: parent.width
                            spacing: 12
                            opacity: expanded ? 1 : 0

                            Behavior on opacity { NumberAnimation { duration: 150 } }

                            // Icon Override
                            Column {
                                width: parent.width
                                spacing: 6

                                Text {
                                    text: Lang.get("apps.iconPath", _lang)
                                    font.pixelSize: 12
                                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                                }

                                Row {
                                    spacing: 8

                                    Rectangle {
                                        width: 300
                                        height: 32
                                        radius: 4
                                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                                        border.width: 1
                                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                                        TextInput {
                                            id: iconInput
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            verticalAlignment: TextInput.AlignVCenter
                                            font.pixelSize: 12
                                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                            selectionColor: settingsMenu.accentColor
                                            selectByMouse: true
                                            clip: true

                                            Text {
                                                visible: parent.text.length === 0
                                                text: "z.B. img/myicon.svg oder app-name"
                                                color: "#555"
                                                font.pixelSize: 11
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }
                                    }

                                    CheckBox {
                                        id: customIconCheckbox
                                        anchors.verticalCenter: parent.verticalCenter

                                        contentItem: Text {
                                            text: Lang.get("apps.customIcon", _lang)
                                            font.pixelSize: 11
                                            color: settingsMenu.darkMode ? "#aaa" : "#555"
                                            leftPadding: customIconCheckbox.indicator.width + 8
                                            verticalAlignment: Text.AlignVCenter
                                        }

                                        indicator: Rectangle {
                                            width: 18
                                            height: 18
                                            radius: 3
                                            color: customIconCheckbox.checked ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                                            border.width: 1
                                            border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                                            Text {
                                                visible: customIconCheckbox.checked
                                                anchors.centerIn: parent
                                                text: "✓"
                                                font.pixelSize: 12
                                                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                            }
                                        }
                                    }
                                }
                            }

                            // Command Override
                            Column {
                                width: parent.width
                                spacing: 6

                                Text {
                                    text: Lang.get("apps.command", _lang)
                                    font.pixelSize: 12
                                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                                }

                                Rectangle {
                                    width: 450
                                    height: 32
                                    radius: 4
                                    color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                                    border.width: 1
                                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                                    TextInput {
                                        id: cmdInput
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 8
                                        verticalAlignment: TextInput.AlignVCenter
                                        font.pixelSize: 12
                                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                        selectionColor: settingsMenu.accentColor
                                        selectByMouse: true
                                        clip: true

                                        Text {
                                            visible: parent.text.length === 0
                                            text: "z.B. my-custom-app --flag"
                                            color: "#555"
                                            font.pixelSize: 11
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }
                            }

                            // Aktionsbuttons
                            Row {
                                spacing: 10

                                // Speichern Button
                                Rectangle {
                                    width: 100
                                    height: 32
                                    radius: 4
                                    color: saveButtonMouseArea.containsMouse ? Qt.lighter(settingsMenu.accentColor, 1.2) : settingsMenu.accentColor
                                    border.width: 0

                                    Text {
                                        anchors.centerIn: parent
                                        text: Lang.get("apps.save", _lang)
                                        font.pixelSize: 12
                                        font.bold: true
                                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                    }

                                    MouseArea {
                                        id: saveButtonMouseArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (settingsMenu && settingsMenu.saveAppOverride) {
                                                settingsMenu.saveAppOverride(
                                                    appData.name,
                                                    iconInput.text,
                                                    cmdInput.text,
                                                    customIconCheckbox.checked
                                                )
                                            }
                                        }
                                    }
                                }

                                // Löschen Button
                                Rectangle {
                                    visible: hasOverride
                                    width: 100
                                    height: 32
                                    radius: 4
                                    color: deleteButtonMouseArea.containsMouse ? "#cc0000" : "#aa0000"
                                    border.width: 0

                                    Text {
                                        anchors.centerIn: parent
                                        text: Lang.get("apps.delete", _lang)
                                        font.pixelSize: 12
                                        font.bold: true
                                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                    }

                                    MouseArea {
                                        id: deleteButtonMouseArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (settingsMenu && settingsMenu.deleteAppOverride) {
                                                settingsMenu.deleteAppOverride(appData.name)
                                            }
                                        }
                                    }
                                }

                                // Standard wiederherstellen
                                Rectangle {
                                    width: 140
                                    height: 32
                                    radius: 4
                                    color: resetButtonMouseArea.containsMouse ? (settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                                    border.width: 1
                                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                                    Text {
                                        anchors.centerIn: parent
                                        text: "Standard"
                                        font.pixelSize: 12
                                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                    }

                                    MouseArea {
                                        id: resetButtonMouseArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (appData) {
                                                iconInput.text = appData.icon
                                                cmdInput.text = appData.cmd
                                                customIconCheckbox.checked = appData.customIcon
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Trennlinie
    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    Text {
        text: Lang.get("apps.systemApps", _lang)
        font.pixelSize: 18
        font.bold: true
        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
    }

    Grid {
        columns: 3
        columnSpacing: 15
        rowSpacing: 15

        Repeater {
            model: ListModel {
                ListElement { name: "Displays"; targetCategory: "monitors"; cmd: ""; icon: "display" }
                ListElement { name: "Bluetooth"; targetCategory: ""; cmd: "blueman-manager"; icon: "bluetooth" }
                ListElement { name: "Audio"; targetCategory: ""; cmd: "pavucontrol"; icon: "audio" }
                ListElement { name: "Network"; targetCategory: ""; cmd: "nm-connection-editor"; icon: "network" }
                ListElement { name: "System Monitor"; targetCategory: ""; cmd: "gnome-system-monitor"; icon: "chart" }
                ListElement { name: "GTK-Themes"; targetCategory: "appearance"; cmd: ""; icon: "palette" }
            }

            delegate: Rectangle {
                width: 180
                height: 70
                radius: 8
                color: appMouseArea.containsMouse ? (settingsMenu.darkMode ? "#2a2a2a" : "#e0e0e0") : (settingsMenu.darkMode ? "#1f1f1f" : "#f0f0f0")
                border.width: 1
                border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                Behavior on color { ColorAnimation { duration: 150 } }

                Row {
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 12

                    ProjectIcon {
                        name: model.icon
                        color: settingsMenu.darkMode ? "#cccccc" : "#444444"
                        font.pixelSize: 32
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4

                        Text {
                            text: targetCategory ? Lang.get("nav." + targetCategory, _lang) : name
                            font.pixelSize: 14
                            font.bold: true
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        }

                        Text {
                            text: targetCategory ? "WinDoesNot" : cmd
                            font.pixelSize: 11
                            color: settingsMenu.darkMode ? "#666" : "#888"
                        }
                    }
                }

                Process {
                    id: systemAppProc
                    command: ["sh", "-c", "setsid " + cmd + " >/dev/null 2>&1 &"]
                    running: false

                    stdout: StdioCollector {
                        onStreamFinished: {
                            if (this.text.trim().length > 0) {
                                console.log("=== System app stdout:", this.text.trim())
                            }
                        }
                    }
                    stderr: StdioCollector {
                        onStreamFinished: {
                            if (this.text.trim().length > 0) {
                                console.log("=== System app stderr:", this.text.trim())
                            }
                        }
                    }
                }

                MouseArea {
                    id: appMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (targetCategory) {
                            settingsMenu.currentCategory = targetCategory
                        } else {
                            systemAppProc.running = true
                            settingsMenu.visible = false
                        }
                    }
                }
            }
        }
    }
}
