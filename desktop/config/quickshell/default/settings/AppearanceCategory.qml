import "."
import QtQuick
import QtQuick.Controls
import Quickshell.Io
import Qt5Compat.GraphicalEffects
import "../i18n/Lang.js" as Lang

Column {
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"

    width: parent.width
    spacing: 30

    // Dark/Light Mode
    Row {
        width: parent.width
        spacing: 15

        Column {
            spacing: 5
            width: parent.width - 80

            Text {
                text: Lang.get("appearance.mode", _lang)
                font.pixelSize: 18
                font.bold: true
                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
            }

            Text {
                text: Lang.get("appearance.modeDesc", _lang)
                font.pixelSize: 12
                color: settingsMenu.darkMode ? "#666" : "#888"
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            width: 60
            height: 32
            radius: 16
            color: settingsMenu.darkMode ? "#3a3a3a" : settingsMenu.accentColor
            anchors.verticalCenter: parent.verticalCenter

            Behavior on color { ColorAnimation { duration: 150 } }

            Image {
                anchors.centerIn: parent
                source: "../img/Win11-dark/actions/symbolic/dark-mode-symbolic.svg"
                width: 18
                height: 18
                sourceSize.width: 18
                sourceSize.height: 18
                fillMode: Image.PreserveAspectFit
                smooth: true
                antialiasing: true
                mipmap: true
                layer.enabled: !settingsMenu.darkMode
                layer.smooth: true
                layer.effect: ColorOverlay { color: "#000000" }
                opacity: settingsMenu.darkMode ? 1.0 : 0.5
                Behavior on opacity { NumberAnimation { duration: 150 } }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    settingsMenu.darkMode = !settingsMenu.darkMode
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    StartOrbSettings { settingsMenu: parent.settingsMenu }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Window Mode (Tiling/Floating)
    Column {
        width: parent.width
        spacing: 15

        Column {
            width: parent.width
            spacing: 5

            Text {
                text: Lang.get("appearance.windowMode", _lang)
                font.pixelSize: 18
                font.bold: true
                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
            }

            Text {
                text: Lang.get("appearance.windowModeDesc", _lang)
                font.pixelSize: 12
                color: settingsMenu.darkMode ? "#666" : "#888"
                wrapMode: Text.WordWrap
            }
        }

        Row {
            width: parent.width
            spacing: 15

            Repeater {
                model: ListModel {
                    ListElement {
                        value: "tiling"
                        labelKey: "appearance.tiling"
                        icon: "../img/Win11-dark/actions/symbolic/view-grid-symbolic.svg"
                        descKey: "appearance.tilingDesc"
                    }
                    ListElement {
                        value: "floating"
                        labelKey: "appearance.floating"
                        icon: "../img/Win11-dark/actions/symbolic/window-new-symbolic.svg"
                        descKey: "appearance.floatingDesc"
                    }
                }

                delegate: Rectangle {
                    width: 275
                    height: 120
                    radius: 8
                    color: settingsMenu.windowMode === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.width: 2
                    border.color: settingsMenu.windowMode === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")

                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    Column {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 8

                        Row {
                            spacing: 10
                            width: parent.width

                            Image {
                                source: icon
                                width: 28
                                height: 28
                                sourceSize.width: 28
                                sourceSize.height: 28
                                fillMode: Image.PreserveAspectFit
                                anchors.verticalCenter: parent.verticalCenter
                                smooth: true
                                antialiasing: true
                                mipmap: true
                                layer.enabled: !settingsMenu.darkMode
                                layer.smooth: true
                                layer.effect: ColorOverlay { color: "#000000" }
                            }

                            Text {
                                text: Lang.get(labelKey)
                                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                font.pixelSize: 16
                                font.bold: true
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            text: Lang.get(descKey)
                            color: settingsMenu.windowMode === value ? "#fff" : "#999"
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            width: parent.width
                            lineHeight: 1.3
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            settingsMenu.windowMode = value
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // GTK Theme
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: Lang.get("appearance.gtkTheme", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Text {
            text: Lang.get("appearance.currentActive", _lang) + " " + settingsMenu.gtkTheme
            font.pixelSize: 13
            color: settingsMenu.accentColor
            font.bold: true
        }

        // Theme selection dropdowns
        Row {
            width: parent.width
            spacing: 15

            // Dark Mode Theme Dropdown
            Column {
                width: (parent.width - 15) / 2
                spacing: 8

                Row {
                    spacing: 8
                    Image {
                        source: "../img/Win11-dark/actions/symbolic/dark-mode-symbolic.svg"
                        width: 16
                        height: 16
                        sourceSize.width: 16
                        sourceSize.height: 16
                        fillMode: Image.PreserveAspectFit
                        anchors.verticalCenter: parent.verticalCenter
                        smooth: true
                    }
                    Text {
                        text: Lang.get("appearance.darkModeTheme", _lang)
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                ComboBox {
                    id: gtkThemeDarkCombo
                    width: parent.width
                    height: 35
                    model: settingsMenu ? settingsMenu.gtkThemesModel : null
                    textRole: "name"

                    onModelChanged: {
                        if (model && model.count > 0 && settingsMenu) {
                            for (var i = 0; i < model.count; i++) {
                                if (model.get(i).name === settingsMenu.gtkThemeDark) {
                                    currentIndex = i
                                    return
                                }
                            }
                        }
                    }

                    onActivated: {
                        settingsMenu.gtkThemeDark = model.get(currentIndex).name
                    }

                    background: Rectangle {
                        color: gtkThemeDarkCombo.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1
                        radius: 6
                    }

                    contentItem: Text {
                        leftPadding: 10
                        rightPadding: gtkThemeDarkCombo.indicator.width + gtkThemeDarkCombo.spacing
                        text: gtkThemeDarkCombo.displayText
                        font.pixelSize: 12
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    indicator: Text {
                        x: gtkThemeDarkCombo.width - width - 10
                        y: gtkThemeDarkCombo.topPadding + (gtkThemeDarkCombo.availableHeight - height) / 2
                        text: "▼"
                        font.pixelSize: 9
                        color: settingsMenu.darkMode ? "#999" : "#666"
                    }

                    popup: Popup {
                        y: gtkThemeDarkCombo.height + 2
                        width: gtkThemeDarkCombo.width
                        implicitHeight: Math.min(contentItem.implicitHeight, 250)
                        padding: 1

                        contentItem: ListView {
                            clip: true
                            implicitHeight: contentHeight
                            model: gtkThemeDarkCombo.popup.visible ? gtkThemeDarkCombo.delegateModel : null
                            currentIndex: gtkThemeDarkCombo.highlightedIndex
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
                        width: gtkThemeDarkCombo.width - 2
                        contentItem: Text {
                            text: model.name
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: 10
                        }
                        highlighted: gtkThemeDarkCombo.highlightedIndex === index
                        background: Rectangle {
                            color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                            radius: 4
                        }
                    }
                }
            }

            // Light Mode Theme Dropdown
            Column {
                width: (parent.width - 15) / 2
                spacing: 8

                Row {
                    spacing: 8
                    Rectangle {
                        width: 16
                        height: 16
                        color: "transparent"
                        anchors.verticalCenter: parent.verticalCenter

                        Image {
                            anchors.fill: parent
                            source: "../img/Win11-dark/actions/symbolic/weather-clear-symbolic.svg"
                            sourceSize.width: 16
                            sourceSize.height: 16
                            fillMode: Image.PreserveAspectFit
                            smooth: true

                            layer.enabled: !settingsMenu.darkMode
                            layer.effect: ColorOverlay {
                                color: "#000000"
                            }
                        }
                    }
                    Text {
                        text: Lang.get("appearance.lightModeTheme", _lang)
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                ComboBox {
                    id: gtkThemeLightCombo
                    width: parent.width
                    height: 35
                    model: settingsMenu ? settingsMenu.gtkThemesModel : null
                    textRole: "name"

                    onModelChanged: {
                        if (model && model.count > 0 && settingsMenu) {
                            for (var i = 0; i < model.count; i++) {
                                if (model.get(i).name === settingsMenu.gtkThemeLight) {
                                    currentIndex = i
                                    return
                                }
                            }
                        }
                    }

                    onActivated: {
                        settingsMenu.gtkThemeLight = model.get(currentIndex).name
                    }

                    background: Rectangle {
                        color: gtkThemeLightCombo.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        border.width: 1
                        radius: 6
                    }

                    contentItem: Text {
                        leftPadding: 10
                        rightPadding: gtkThemeLightCombo.indicator.width + gtkThemeLightCombo.spacing
                        text: gtkThemeLightCombo.displayText
                        font.pixelSize: 12
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    indicator: Text {
                        x: gtkThemeLightCombo.width - width - 10
                        y: gtkThemeLightCombo.topPadding + (gtkThemeLightCombo.availableHeight - height) / 2
                        text: "▼"
                        font.pixelSize: 9
                        color: settingsMenu.darkMode ? "#999" : "#666"
                    }

                    popup: Popup {
                        y: gtkThemeLightCombo.height + 2
                        width: gtkThemeLightCombo.width
                        implicitHeight: Math.min(contentItem.implicitHeight, 250)
                        padding: 1

                        contentItem: ListView {
                            clip: true
                            implicitHeight: contentHeight
                            model: gtkThemeLightCombo.popup.visible ? gtkThemeLightCombo.delegateModel : null
                            currentIndex: gtkThemeLightCombo.highlightedIndex
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
                        width: gtkThemeLightCombo.width - 2
                        contentItem: Text {
                            text: model.name
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: 10
                        }
                        highlighted: gtkThemeLightCombo.highlightedIndex === index
                        background: Rectangle {
                            color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                            radius: 4
                        }
                    }
                }
            }
        }

        // All available themes grid
        Column {
            width: parent.width
            spacing: 10

            Text {
                text: Lang.get("appearance.allThemes", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            Grid {
                columns: 2
                columnSpacing: 10
                rowSpacing: 10

                Repeater {
                    model: settingsMenu.gtkThemesModel

                    delegate: Rectangle {
                        width: 280
                        height: 50
                        radius: 6
                        color: settingsMenu.gtkTheme === model.name ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Row {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 10

                            Image {
                                source: "../img/Win11-dark/actions/symbolic/color-palette-symbolic.svg"
                                width: 20
                                height: 20
                                sourceSize.width: 20
                                sourceSize.height: 20
                                fillMode: Image.PreserveAspectFit
                                anchors.verticalCenter: parent.verticalCenter
                                smooth: true
                                antialiasing: true
                                mipmap: true
                                layer.enabled: !settingsMenu.darkMode
                                layer.smooth: true
                                layer.effect: ColorOverlay { color: "#000000" }
                            }

                            Text {
                                text: model.name
                                font.pixelSize: 13
                                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                // Set as both dark and light theme, then apply
                                if (settingsMenu.darkMode) {
                                    settingsMenu.gtkThemeDark = model.name
                                } else {
                                    settingsMenu.gtkThemeLight = model.name
                                }
                            }
                        }
                    }
                }
            }
        }

        Text {
            text: Lang.get("common.tip", _lang) + " " + Lang.get("appearance.gtkTip", _lang)
            font.pixelSize: 11
            color: settingsMenu.darkMode ? "#666" : "#888"
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Cursor Theme
    Column {
        width: parent.width
        spacing: 15

        Row {
            width: parent.width
            spacing: 0

            Text {
                text: Lang.get("appearance.cursorTheme", _lang)
                font.pixelSize: 18
                font.bold: true
                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                width: parent.width - 150
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: settingsMenu.cursorTheme
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#999" : "#666"
                width: 150
                horizontalAlignment: Text.AlignRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Grid {
            columns: 2
            columnSpacing: 10
            rowSpacing: 10

            Repeater {
                model: settingsMenu.cursorThemesModel

                delegate: Rectangle {
                    width: 280
                    height: 50
                    radius: 6
                    color: settingsMenu.cursorTheme === model.name ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.width: 1
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    Behavior on color { ColorAnimation { duration: 150 } }

                    Row {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Image {
                            source: "../img/Win11-dark/actions/symbolic/tool-pointer-symbolic.svg"
                            width: 20
                            height: 20
                            sourceSize.width: 20
                            sourceSize.height: 20
                            fillMode: Image.PreserveAspectFit
                            anchors.verticalCenter: parent.verticalCenter
                            smooth: true
                            antialiasing: true
                            mipmap: true
                            layer.enabled: !settingsMenu.darkMode
                            layer.smooth: true
                            layer.effect: ColorOverlay { color: "#000000" }
                        }

                        Text {
                            text: model.name
                            font.pixelSize: 13
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            settingsMenu.cursorTheme = model.name
                        }
                    }
                }
            }
        }

        Text {
            text: Lang.get("common.tip", _lang) + " " + Lang.get("appearance.cursorTip", _lang)
            font.pixelSize: 11
            color: settingsMenu.darkMode ? "#666" : "#888"
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Icon Theme
    Column {
        width: parent.width
        spacing: 15

        Row {
            width: parent.width
            spacing: 0

            Text {
                text: Lang.get("appearance.iconTheme", _lang)
                font.pixelSize: 18
                font.bold: true
                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                width: parent.width - 150
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: settingsMenu.iconTheme
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#999" : "#666"
                width: 150
                horizontalAlignment: Text.AlignRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Grid {
            columns: 2
            columnSpacing: 10
            rowSpacing: 10

            Repeater {
                model: settingsMenu.iconThemesModel

                delegate: Rectangle {
                    width: 280
                    height: 50
                    radius: 6
                    color: settingsMenu.iconTheme === model.name ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.width: 1
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    Behavior on color { ColorAnimation { duration: 150 } }

                    Row {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Image {
                            source: "../img/Win11-dark/actions/symbolic/insert-image-symbolic.svg"
                            width: 20
                            height: 20
                            sourceSize.width: 20
                            sourceSize.height: 20
                            fillMode: Image.PreserveAspectFit
                            anchors.verticalCenter: parent.verticalCenter
                            smooth: true
                            antialiasing: true
                            mipmap: true
                            layer.enabled: !settingsMenu.darkMode
                            layer.smooth: true
                            layer.effect: ColorOverlay { color: "#000000" }
                        }

                        Text {
                            text: model.name
                            font.pixelSize: 13
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            settingsMenu.iconTheme = model.name
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Titlebar (Complete Enable/Disable)
    Column {
        width: parent.width
        spacing: 20

        // Titlebar Toggle
        Row {
            width: parent.width
            spacing: 15

            Column {
                spacing: 5
                width: parent.width - 80

                Text {
                    text: Lang.get("appearance.titlebar", _lang)
                    font.pixelSize: 16
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }

                Text {
                    text: "Aktiviert/deaktiviert die Titelleiste komplett (setzt bar_height auf 0)"
                    font.pixelSize: 12
                    color: settingsMenu.darkMode ? "#666" : "#888"
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                width: 60
                height: 32
                radius: 16
                color: settingsMenu.hyprbarsPluginEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                anchors.verticalCenter: parent.verticalCenter

                Behavior on color { ColorAnimation { duration: 150 } }

                Rectangle {
                    width: 24
                    height: 24
                    radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: (settingsMenu && settingsMenu.hyprbarsPluginEnabled) ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter

                    Behavior on x { NumberAnimation { duration: 150 } }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        settingsMenu.hyprbarsPluginEnabled = !settingsMenu.hyprbarsPluginEnabled
                    }
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // Hyprbars (Window Decoration)
    Column {
        width: parent.width
        spacing: 20
        visible: settingsMenu.hyprbarsPluginEnabled
        opacity: settingsMenu.hyprbarsPluginEnabled ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 200 }
        }

        // Toggle
        Row {
            width: parent.width
            spacing: 15

            Column {
                spacing: 5
                width: parent.width - 80

                Text {
                    text: Lang.get("appearance.titlebarButtons", _lang)
                    font.pixelSize: 16
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }

                Text {
                    text: Lang.get("appearance.titlebarButtonsDesc", _lang)
                    font.pixelSize: 12
                    color: settingsMenu.darkMode ? "#666" : "#888"
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                width: 60
                height: 32
                radius: 16
                color: settingsMenu.hyprbarsEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                anchors.verticalCenter: parent.verticalCenter

                Behavior on color { ColorAnimation { duration: 150 } }

                Rectangle {
                    width: 24
                    height: 24
                    radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: (settingsMenu && settingsMenu.hyprbarsEnabled) ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter

                    Behavior on x { NumberAnimation { duration: 150 } }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        settingsMenu.hyprbarsEnabled = !settingsMenu.hyprbarsEnabled
                    }
                }
            }
        }

        // Hyprbars Optionen (nur wenn aktiviert)
        Column {
            width: parent.width
            spacing: 20
            visible: settingsMenu.hyprbarsEnabled
            opacity: settingsMenu.hyprbarsEnabled ? 1.0 : 0.0

            Behavior on opacity {
                NumberAnimation { duration: 200 }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // Individual Button Toggles
            Column {
                width: parent.width
                spacing: 15

                Text {
                    text: Lang.get("appearance.individualButtons", _lang)
                    font.pixelSize: 14
                    font.bold: true
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }

                // Close Button Toggle
                Row {
                    width: parent.width
                    spacing: 15

                    Text {
                        text: Lang.get("appearance.closeButton", _lang)
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: parent.width - 80
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Rectangle {
                        width: 50
                        height: 28
                        radius: 14
                        color: settingsMenu.hyprbarsCloseButtonEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Rectangle {
                            width: 20
                            height: 20
                            radius: 10
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            x: (settingsMenu && settingsMenu.hyprbarsCloseButtonEnabled) ? parent.width - width - 4 : 4
                            anchors.verticalCenter: parent.verticalCenter

                            Behavior on x { NumberAnimation { duration: 150 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                settingsMenu.hyprbarsCloseButtonEnabled = !settingsMenu.hyprbarsCloseButtonEnabled
                            }
                        }
                    }
                }

                // Maximize Button Toggle
                Row {
                    width: parent.width
                    spacing: 15

                    Text {
                        text: Lang.get("appearance.maxButton", _lang)
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: parent.width - 80
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Rectangle {
                        width: 50
                        height: 28
                        radius: 14
                        color: settingsMenu.hyprbarsMaxButtonEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Rectangle {
                            width: 20
                            height: 20
                            radius: 10
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            x: (settingsMenu && settingsMenu.hyprbarsMaxButtonEnabled) ? parent.width - width - 4 : 4
                            anchors.verticalCenter: parent.verticalCenter

                            Behavior on x { NumberAnimation { duration: 150 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (settingsMenu) settingsMenu.hyprbarsMaxButtonEnabled = !settingsMenu.hyprbarsMaxButtonEnabled
                            }
                        }
                    }
                }

                // Minimize Button Toggle
                Row {
                    width: parent.width
                    spacing: 15

                    Text {
                        text: Lang.get("appearance.minButton", _lang)
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: parent.width - 80
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Rectangle {
                        width: 50
                        height: 28
                        radius: 14
                        color: settingsMenu.hyprbarsMinButtonEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Rectangle {
                            width: 20
                            height: 20
                            radius: 10
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            x: (settingsMenu && settingsMenu.hyprbarsMinButtonEnabled) ? parent.width - width - 4 : 4
                            anchors.verticalCenter: parent.verticalCenter

                            Behavior on x { NumberAnimation { duration: 150 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (settingsMenu) settingsMenu.hyprbarsMinButtonEnabled = !settingsMenu.hyprbarsMinButtonEnabled
                            }
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            // Titelleisten-Höhe
            Column {
                width: parent.width
                spacing: 10

                Text {
                    text: Lang.get("appearance.titlebarHeight", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }

                Row {
                    width: parent.width
                    spacing: 12

                    Slider {
                        id: hyprbarsHeightSlider
                        width: parent.width - 60
                        from: 15; to: 50; stepSize: 1
                        value: settingsMenu ? settingsMenu.hyprbarsHeight : 30
                        background: Rectangle {
                            x: hyprbarsHeightSlider.leftPadding
                            y: hyprbarsHeightSlider.topPadding + hyprbarsHeightSlider.availableHeight / 2 - height / 2
                            implicitWidth: 200; implicitHeight: 4
                            width: hyprbarsHeightSlider.availableWidth; height: implicitHeight
                            radius: 2; color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                            Rectangle {
                                width: hyprbarsHeightSlider.visualPosition * parent.width
                                height: parent.height; radius: 2
                                color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                            }
                        }
                        handle: Rectangle {
                            x: hyprbarsHeightSlider.leftPadding + hyprbarsHeightSlider.visualPosition * (hyprbarsHeightSlider.availableWidth - width)
                            y: hyprbarsHeightSlider.topPadding + hyprbarsHeightSlider.availableHeight / 2 - height / 2
                            implicitWidth: 20; implicitHeight: 20; radius: 10
                            color: hyprbarsHeightSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                            border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 2
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }
                        onMoved: { if (settingsMenu) settingsMenu.hyprbarsHeight = value }
                    }

                    Text {
                        text: (settingsMenu ? settingsMenu.hyprbarsHeight : 30) + "px"
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#999" : "#666"
                        width: 48; horizontalAlignment: Text.AlignRight
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }

            // Button Ausrichtung
            Column {
                width: parent.width
                spacing: 10

                Text {
                    text: Lang.get("appearance.buttonPosition", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }

                Row {
                    spacing: 10

                    Repeater {
                        model: ListModel {
                            ListElement { value: "left"; labelKey: "appearance.left" }
                            ListElement { value: "right"; labelKey: "appearance.right" }
                        }

                        delegate: Rectangle {
                            width: 100
                            height: 40
                            radius: 6
                            color: settingsMenu.hyprbarsButtonAlign === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                            border.width: 1
                            border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                            Behavior on color { ColorAnimation { duration: 150 } }

                            Text {
                                anchors.centerIn: parent
                                text: Lang.get(labelKey)
                                color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                font.pixelSize: 13
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    settingsMenu.hyprbarsButtonAlign = value
                                }
                            }
                        }
                    }
                }
            }

            // === BAR DESIGN ===
            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            Column {
                width: parent.width
                spacing: 20

                Text {
                    text: Lang.get("appearance.barDesign", _lang)
                    font.pixelSize: 15
                    font.bold: true
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                }

                // Bar Farbe
                Row {
                    spacing: 15
                    Text {
                        text: Lang.get("appearance.barColor", _lang)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsBarColor
                        border.width: 2
                        border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var proc = Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["hyprpicker", "-a"]; ' +
                                    'running: true; ' +
                                    'stdout: StdioCollector { onStreamFinished: { ' +
                                    'var color = this.text.trim(); ' +
                                    'if (color.length > 0) settingsMenu.hyprbarsBarColor = color; ' +
                                    '} } }',
                                    settingsMenu
                                )
                            }
                        }
                    }
                }

                // Bar Blur
                Row {
                    spacing: 15
                    Text {
                        text: Lang.get("appearance.barBlur", _lang)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 50
                        height: 30
                        radius: 15
                        color: settingsMenu.hyprbarsBarBlur ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Rectangle {
                            x: (settingsMenu && settingsMenu.hyprbarsBarBlur) ? parent.width - width - 3 : 3
                            y: 3
                            width: 24
                            height: 24
                            radius: 12
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            Behavior on x { NumberAnimation { duration: 150 } }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: settingsMenu.hyprbarsBarBlur = !settingsMenu.hyprbarsBarBlur
                        }
                    }
                }
            }

            // === TEXT STYLING ===
            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            Column {
                width: parent.width
                spacing: 20

                Text {
                    text: Lang.get("appearance.textStyling", _lang)
                    font.pixelSize: 15
                    font.bold: true
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                }

                // Text Farbe
                Row {
                    spacing: 15
                    Text {
                        text: Lang.get("appearance.textColor", _lang)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsTextColor
                        border.width: 2
                        border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var proc = Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["hyprpicker", "-a"]; ' +
                                    'running: true; ' +
                                    'stdout: StdioCollector { onStreamFinished: { ' +
                                    'var color = this.text.trim(); ' +
                                    'if (color.length > 0) settingsMenu.hyprbarsTextColor = color; ' +
                                    '} } }',
                                    settingsMenu
                                )
                            }
                        }
                    }
                }

                // Text Größe
                Column {
                    width: parent.width
                    spacing: 10
                    Text {
                        text: Lang.get("appearance.textSize", _lang)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                    }
                    Row {
                        width: parent.width
                        spacing: 12

                        Slider {
                            id: hyprbarsTextSizeSlider
                            width: parent.width - 60
                            from: 8; to: 16; stepSize: 1
                            value: settingsMenu ? settingsMenu.hyprbarsTextSize : 12
                            background: Rectangle {
                                x: hyprbarsTextSizeSlider.leftPadding
                                y: hyprbarsTextSizeSlider.topPadding + hyprbarsTextSizeSlider.availableHeight / 2 - height / 2
                                implicitWidth: 200; implicitHeight: 4
                                width: hyprbarsTextSizeSlider.availableWidth; height: implicitHeight
                                radius: 2; color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                                Rectangle {
                                    width: hyprbarsTextSizeSlider.visualPosition * parent.width
                                    height: parent.height; radius: 2
                                    color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                                }
                            }
                            handle: Rectangle {
                                x: hyprbarsTextSizeSlider.leftPadding + hyprbarsTextSizeSlider.visualPosition * (hyprbarsTextSizeSlider.availableWidth - width)
                                y: hyprbarsTextSizeSlider.topPadding + hyprbarsTextSizeSlider.availableHeight / 2 - height / 2
                                implicitWidth: 20; implicitHeight: 20; radius: 10
                                color: hyprbarsTextSizeSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                                border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 2
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }
                            onMoved: { if (settingsMenu) settingsMenu.hyprbarsTextSize = value }
                        }

                        Text {
                            text: (settingsMenu ? settingsMenu.hyprbarsTextSize : 12) + "px"
                            font.pixelSize: 14
                            color: settingsMenu.darkMode ? "#999" : "#666"
                            width: 48; horizontalAlignment: Text.AlignRight
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // Text Font
                Column {
                    width: parent.width
                    spacing: 10
                    Text {
                        text: Lang.get("appearance.font", _lang)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                    }
                    ComboBox {
                        id: hyprbarsTextFontBox
                        width: parent.width
                        height: 40
                        model: settingsMenu ? settingsMenu.fontsModel : null
                        textRole: "name"

                        property string targetFamily: settingsMenu ? settingsMenu.hyprbarsTextFont.trim() : ""

                        onCountChanged: {
                            for (var i = 0; i < count; i++) {
                                if (settingsMenu.fontsModel.get(i).name === targetFamily) {
                                    currentIndex = i
                                    break
                                }
                            }
                        }

                        onActivated: {
                            settingsMenu.hyprbarsTextFont = currentText
                        }

                        background: Rectangle {
                            radius: 6
                            color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                            border.width: 1
                            border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        }

                        contentItem: Text {
                            leftPadding: 10
                            text: hyprbarsTextFontBox.displayText
                            font.pixelSize: 13
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }
                    }
                }

                // Text Align
                Column {
                    width: parent.width
                    spacing: 10
                    Text {
                        text: Lang.get("appearance.textAlign", _lang)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                    }
                    Row {
                        spacing: 10
                        Repeater {
                            model: ListModel {
                                ListElement { value: "left"; labelKey: "appearance.left" }
                                ListElement { value: "center"; labelKey: "appearance.center" }
                                ListElement { value: "right"; labelKey: "appearance.right" }
                            }
                            delegate: Rectangle {
                                width: 80
                                height: 35
                                radius: 6
                                color: settingsMenu.hyprbarsTextAlign === model.value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                                border.width: 1
                                border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                                Behavior on color { ColorAnimation { duration: 150 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: Lang.get(model.labelKey)
                                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: settingsMenu.hyprbarsTextAlign = model.value
                                }
                            }
                        }
                    }
                }

                // Title Enabled
                Row {
                    spacing: 15
                    Text {
                        text: Lang.get("appearance.showTitle", _lang)
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 50
                        height: 30
                        radius: 15
                        color: settingsMenu.hyprbarsBarTitleEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Rectangle {
                            x: (settingsMenu && settingsMenu.hyprbarsBarTitleEnabled) ? parent.width - width - 3 : 3
                            y: 3
                            width: 24
                            height: 24
                            radius: 12
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            Behavior on x { NumberAnimation { duration: 150 } }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: settingsMenu.hyprbarsBarTitleEnabled = !settingsMenu.hyprbarsBarTitleEnabled
                        }
                    }
                }
            }

            // === BUTTON COLORS ===
            Rectangle {
                width: parent.width
                height: 1
                color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
            }

            Column {
                width: parent.width
                spacing: 20

                Text {
                    text: Lang.get("appearance.buttonColors", _lang)
                    font.pixelSize: 15
                    font.bold: true
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                }

                // Close Button
                Row {
                    spacing: 15
                    Text {
                        text: "Close (X)"
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsCloseButtonColor
                        border.width: 2
                        border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var proc = Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["hyprpicker", "-a"]; ' +
                                    'running: true; ' +
                                    'stdout: StdioCollector { onStreamFinished: { ' +
                                    'var color = this.text.trim(); ' +
                                    'if (color.length > 0) settingsMenu.hyprbarsCloseButtonColor = color; ' +
                                    '} } }',
                                    settingsMenu
                                )
                            }
                        }
                    }
                }

                // Maximize Button
                Row {
                    spacing: 15
                    Text {
                        text: "Maximize (□)"
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsMaxButtonColor
                        border.width: 2
                        border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var proc = Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["hyprpicker", "-a"]; ' +
                                    'running: true; ' +
                                    'stdout: StdioCollector { onStreamFinished: { ' +
                                    'var color = this.text.trim(); ' +
                                    'if (color.length > 0) settingsMenu.hyprbarsMaxButtonColor = color; ' +
                                    '} } }',
                                    settingsMenu
                                )
                            }
                        }
                    }
                }

                // Minimize Button
                Row {
                    spacing: 15
                    Text {
                        text: "Minimize (—)"
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsMinButtonColor
                        border.width: 2
                        border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var proc = Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["hyprpicker", "-a"]; ' +
                                    'running: true; ' +
                                    'stdout: StdioCollector { onStreamFinished: { ' +
                                    'var color = this.text.trim(); ' +
                                    'if (color.length > 0) settingsMenu.hyprbarsMinButtonColor = color; ' +
                                    '} } }',
                                    settingsMenu
                                )
                            }
                        }
                    }
                }

                // Divider
                Rectangle {
                    width: parent.width
                    height: 1
                    color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                }

                Text {
                    text: Lang.get("appearance.buttonTextColors", _lang)
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                // Close Button Text Color
                Row {
                    spacing: 15
                    Text {
                        text: "Close Text"
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsButtonTextColor
                        border.width: 2
                        border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var proc = Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["hyprpicker", "-a"]; ' +
                                    'running: true; ' +
                                    'stdout: StdioCollector { onStreamFinished: { ' +
                                    'var color = this.text.trim(); ' +
                                    'if (color.length > 0) settingsMenu.hyprbarsButtonTextColor = color; ' +
                                    '} } }',
                                    settingsMenu
                                )
                            }
                        }
                    }
                }

                // Neutral Button Text Color (Max/Min)
                Row {
                    spacing: 15
                    Text {
                        text: "Max/Min Text"
                        font.pixelSize: 14
                        color: settingsMenu.darkMode ? "#aaa" : "#555"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsButtonTextColorNeutral
                        border.width: 2
                        border.color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var proc = Qt.createQmlObject(
                                    'import Quickshell.Io; Process { ' +
                                    'command: ["hyprpicker", "-a"]; ' +
                                    'running: true; ' +
                                    'stdout: StdioCollector { onStreamFinished: { ' +
                                    'var color = this.text.trim(); ' +
                                    'if (color.length > 0) settingsMenu.hyprbarsButtonTextColorNeutral = color; ' +
                                    '} } }',
                                    settingsMenu
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    // === SCHRIFTARTEN ===
    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    Column {
        width: parent.width
        spacing: 20

        Text {
            text: Lang.get("appearance.fonts", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Interface Font
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("appearance.fontInterface", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                spacing: 10

                ComboBox {
                    id: fontInterfaceFamilyBox
                    width: 220
                    height: 40
                    model: settingsMenu ? settingsMenu.fontsModel : null
                    textRole: "name"

                    property string targetFamily: {
                        var val = settingsMenu ? settingsMenu.fontInterface : ""
                        var m = val.match(/^(.*)\s+\d+$/)
                        return m ? m[1].trim() : val.trim()
                    }

                    onCountChanged: {
                        for (var i = 0; i < count; i++) {
                            if (settingsMenu.fontsModel.get(i).name === targetFamily) {
                                currentIndex = i
                                break
                            }
                        }
                    }

                    onActivated: {
                        var size = fontInterfaceSizeInput.text || "11"
                        settingsMenu.fontInterface = currentText + " " + size
                    }

                    background: Rectangle {
                        radius: 6
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    }

                    contentItem: Text {
                        leftPadding: 10
                        text: fontInterfaceFamilyBox.displayText
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }

                Rectangle {
                    width: 60
                    height: 40
                    radius: 6
                    color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 1
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    TextInput {
                        id: fontInterfaceSizeInput
                        anchors.fill: parent
                        anchors.margins: 10
                        text: {
                            var m = settingsMenu ? settingsMenu.fontInterface.match(/(\d+)$/) : null
                            return m ? m[1] : "11"
                        }
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 13
                        verticalAlignment: TextInput.AlignVCenter
                        validator: IntValidator { bottom: 6; top: 72 }
                        onEditingFinished: {
                            var family = fontInterfaceFamilyBox.currentText
                            if (family) settingsMenu.fontInterface = family + " " + text
                        }
                    }
                }

                Text {
                    text: "px"
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#666" : "#888"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // Document Font
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("appearance.fontDocument", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                spacing: 10

                ComboBox {
                    id: fontDocumentFamilyBox
                    width: 220
                    height: 40
                    model: settingsMenu ? settingsMenu.fontsModel : null
                    textRole: "name"

                    property string targetFamily: {
                        var val = settingsMenu ? settingsMenu.fontDocument : ""
                        var m = val.match(/^(.*)\s+\d+$/)
                        return m ? m[1].trim() : val.trim()
                    }

                    onCountChanged: {
                        for (var i = 0; i < count; i++) {
                            if (settingsMenu.fontsModel.get(i).name === targetFamily) {
                                currentIndex = i
                                break
                            }
                        }
                    }

                    onActivated: {
                        var size = fontDocumentSizeInput.text || "11"
                        settingsMenu.fontDocument = currentText + " " + size
                    }

                    background: Rectangle {
                        radius: 6
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    }

                    contentItem: Text {
                        leftPadding: 10
                        text: fontDocumentFamilyBox.displayText
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }

                Rectangle {
                    width: 60
                    height: 40
                    radius: 6
                    color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 1
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    TextInput {
                        id: fontDocumentSizeInput
                        anchors.fill: parent
                        anchors.margins: 10
                        text: {
                            var m = settingsMenu ? settingsMenu.fontDocument.match(/(\d+)$/) : null
                            return m ? m[1] : "11"
                        }
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 13
                        verticalAlignment: TextInput.AlignVCenter
                        validator: IntValidator { bottom: 6; top: 72 }
                        onEditingFinished: {
                            var family = fontDocumentFamilyBox.currentText
                            if (family) settingsMenu.fontDocument = family + " " + text
                        }
                    }
                }

                Text {
                    text: "px"
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#666" : "#888"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // Monospace Font
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("appearance.fontMonospace", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                spacing: 10

                ComboBox {
                    id: fontMonospaceFamilyBox
                    width: 220
                    height: 40
                    model: settingsMenu ? settingsMenu.monospaceFontsModel : null
                    textRole: "name"

                    property string targetFamily: {
                        var val = settingsMenu ? settingsMenu.fontMonospace : ""
                        var m = val.match(/^(.*)\s+\d+$/)
                        return m ? m[1].trim() : val.trim()
                    }

                    onCountChanged: {
                        for (var i = 0; i < count; i++) {
                            if (settingsMenu.monospaceFontsModel.get(i).name === targetFamily) {
                                currentIndex = i
                                break
                            }
                        }
                    }

                    onActivated: {
                        var size = fontMonospaceSizeInput.text || "10"
                        settingsMenu.fontMonospace = currentText + " " + size
                    }

                    background: Rectangle {
                        radius: 6
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    }

                    contentItem: Text {
                        leftPadding: 10
                        text: fontMonospaceFamilyBox.displayText
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }

                Rectangle {
                    width: 60
                    height: 40
                    radius: 6
                    color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 1
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    TextInput {
                        id: fontMonospaceSizeInput
                        anchors.fill: parent
                        anchors.margins: 10
                        text: {
                            var m = settingsMenu ? settingsMenu.fontMonospace.match(/(\d+)$/) : null
                            return m ? m[1] : "10"
                        }
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 13
                        verticalAlignment: TextInput.AlignVCenter
                        validator: IntValidator { bottom: 6; top: 72 }
                        onEditingFinished: {
                            var family = fontMonospaceFamilyBox.currentText
                            if (family) settingsMenu.fontMonospace = family + " " + text
                        }
                    }
                }

                Text {
                    text: "px"
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#666" : "#888"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // Font Scaling
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("appearance.fontScaling", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                width: parent.width
                spacing: 12
                Slider {
                    id: fontScalingSlider
                    width: parent.width - 60
                    from: 0.5; to: 2.0; stepSize: 0.05
                    value: settingsMenu ? settingsMenu.fontScaling : 1.0
                    background: Rectangle {
                        x: fontScalingSlider.leftPadding
                        y: fontScalingSlider.topPadding + fontScalingSlider.availableHeight / 2 - height / 2
                        implicitWidth: 200; implicitHeight: 4
                        width: fontScalingSlider.availableWidth; height: implicitHeight
                        radius: 2; color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Rectangle {
                            width: fontScalingSlider.visualPosition * parent.width
                            height: parent.height; radius: 2
                            color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        }
                    }
                    handle: Rectangle {
                        x: fontScalingSlider.leftPadding + fontScalingSlider.visualPosition * (fontScalingSlider.availableWidth - width)
                        y: fontScalingSlider.topPadding + fontScalingSlider.availableHeight / 2 - height / 2
                        implicitWidth: 20; implicitHeight: 20; radius: 10
                        color: fontScalingSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                        border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 2
                        Behavior on color { ColorAnimation { duration: 100 } }
                    }
                    onMoved: { if (settingsMenu) settingsMenu.fontScaling = value }
                }
                Text {
                    text: (settingsMenu ? settingsMenu.fontScaling.toFixed(2) : "1.00")
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#999" : "#666"
                    width: 48; horizontalAlignment: Text.AlignRight
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Text {
                text: "0.5 (klein) bis 2.0 (groß)"
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Hinting
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("appearance.hinting", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: "none"; labelKey: "appearance.hintingNone" }
                        ListElement { value: "slight"; labelKey: "appearance.hintingSlight" }
                        ListElement { value: "medium"; labelKey: "appearance.hintingMedium" }
                        ListElement { value: "full"; labelKey: "appearance.hintingFull" }
                    }
                    delegate: Rectangle {
                        width: 90
                        height: 35
                        radius: 6
                        color: settingsMenu.fontHinting === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            anchors.centerIn: parent
                            text: Lang.get(labelKey)
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            font.pixelSize: 12
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: settingsMenu.fontHinting = value
                        }
                    }
                }
            }
        }

        // Antialiasing
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("appearance.antialiasing", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: "none"; labelKey: "appearance.antialiasingNone" }
                        ListElement { value: "grayscale"; labelKey: "appearance.antialiasingGrayscale" }
                        ListElement { value: "rgba"; labelKey: "appearance.antialiasingRgb" }
                    }
                    delegate: Rectangle {
                        width: 110
                        height: 35
                        radius: 6
                        color: settingsMenu.fontAntialiasing === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            anchors.centerIn: parent
                            text: Lang.get(labelKey)
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            font.pixelSize: 12
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: settingsMenu.fontAntialiasing = value
                        }
                    }
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
        }

        ColorsCategory {
            width: parent.width
            settingsMenu: settingsMenu
        }
}
}
