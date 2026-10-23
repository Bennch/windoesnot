import QtQuick
import QtQuick.Controls
import Quickshell.Io
import Qt5Compat.GraphicalEffects

Column {
    property var settingsMenu: null

    width: parent.width
    spacing: 30

    // Window Mode (Tiling/Floating)
    Column {
        width: parent.width
        spacing: 15

        Column {
            width: parent.width
            spacing: 5

            Text {
                text: "Fenster-Modus"
                font.pixelSize: 16
                color: "#aaa"
            }

            Text {
                text: "Bestimmt wie neue Fenster geöffnet werden."
                font.pixelSize: 12
                color: "#666"
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
                        label: "Tiling"
                        icon: "../img/Win11-dark/actions/symbolic/view-grid-symbolic.svg"
                        description: "Fenster werden automatisch gekachelt und füllen den Bildschirm ohne Überlappung"
                    }
                    ListElement {
                        value: "floating"
                        label: "Floating"
                        icon: "../img/Win11-dark/actions/symbolic/window-new-symbolic.svg"
                        description: "Fenster schweben frei und können beliebig positioniert werden (wie Windows)"
                    }
                }

                delegate: Rectangle {
                    width: 275
                    height: 120
                    radius: 8
                    color: settingsMenu.windowMode === value ? settingsMenu.accentColor : "#2a2a2a"
                    border.width: 2
                    border.color: settingsMenu.windowMode === value ? settingsMenu.accentColor : "#3a3a3a"

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
                                layer.enabled: true
                                layer.smooth: true
                            }

                            Text {
                                text: label
                                color: "#fff"
                                font.pixelSize: 16
                                font.bold: true
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            text: description
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





    // Dark/Light Mode
    Row {
        width: parent.width
        spacing: 15

        Column {
            spacing: 5
            width: parent.width - 80

            Text {
                text: "Erscheinungsmodus"
                font.pixelSize: 16
                color: "#aaa"
            }

            Text {
                text: "Wechsel zwischen hellem und dunklem Theme"
                font.pixelSize: 12
                color: "#666"
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
                layer.enabled: true
                layer.smooth: true
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
        color: "#3a3a3a"
    }

    // GTK Theme
    Column {
        width: parent.width
        spacing: 15

        Text {
            text: "GTK-Theme"
            font.pixelSize: 16
            color: "#aaa"
        }

        Text {
            text: "Aktuell aktiv: " + settingsMenu.gtkTheme
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
                        text: "Dark Mode Theme"
                        font.pixelSize: 13
                        color: "#aaa"
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
                        color: gtkThemeDarkCombo.pressed ? "#1a1a1a" : "#2a2a2a"
                        border.color: "#3a3a3a"
                        border.width: 1
                        radius: 6
                    }

                    contentItem: Text {
                        leftPadding: 10
                        rightPadding: gtkThemeDarkCombo.indicator.width + gtkThemeDarkCombo.spacing
                        text: gtkThemeDarkCombo.displayText
                        font.pixelSize: 12
                        color: "#fff"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    indicator: Text {
                        x: gtkThemeDarkCombo.width - width - 10
                        y: gtkThemeDarkCombo.topPadding + (gtkThemeDarkCombo.availableHeight - height) / 2
                        text: "▼"
                        font.pixelSize: 9
                        color: "#999"
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
                            color: "#2a2a2a"
                            border.color: "#3a3a3a"
                            border.width: 1
                            radius: 6
                        }
                    }

                    delegate: ItemDelegate {
                        width: gtkThemeDarkCombo.width - 2
                        contentItem: Text {
                            text: model.name
                            color: "#fff"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: 10
                        }
                        highlighted: gtkThemeDarkCombo.highlightedIndex === index
                        background: Rectangle {
                            color: highlighted ? settingsMenu.accentColor : (parent.hovered ? "#333" : "transparent")
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

                            layer.enabled: !darkMode
                            layer.effect: ColorOverlay {
                                color: "#000000"
                            }
                        }
                    }
                    Text {
                        text: "Light Mode Theme"
                        font.pixelSize: 13
                        color: "#aaa"
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
                        color: gtkThemeLightCombo.pressed ? "#1a1a1a" : "#2a2a2a"
                        border.color: "#3a3a3a"
                        border.width: 1
                        radius: 6
                    }

                    contentItem: Text {
                        leftPadding: 10
                        rightPadding: gtkThemeLightCombo.indicator.width + gtkThemeLightCombo.spacing
                        text: gtkThemeLightCombo.displayText
                        font.pixelSize: 12
                        color: "#fff"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    indicator: Text {
                        x: gtkThemeLightCombo.width - width - 10
                        y: gtkThemeLightCombo.topPadding + (gtkThemeLightCombo.availableHeight - height) / 2
                        text: "▼"
                        font.pixelSize: 9
                        color: "#999"
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
                            color: "#2a2a2a"
                            border.color: "#3a3a3a"
                            border.width: 1
                            radius: 6
                        }
                    }

                    delegate: ItemDelegate {
                        width: gtkThemeLightCombo.width - 2
                        contentItem: Text {
                            text: model.name
                            color: "#fff"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: 10
                        }
                        highlighted: gtkThemeLightCombo.highlightedIndex === index
                        background: Rectangle {
                            color: highlighted ? settingsMenu.accentColor : (parent.hovered ? "#333" : "transparent")
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
                text: "Alle verfügbaren Themes"
                font.pixelSize: 14
                color: "#aaa"
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
                        color: settingsMenu.gtkTheme === model.name ? settingsMenu.accentColor : "#2a2a2a"
                        border.width: 1
                        border.color: "#3a3a3a"

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
                                layer.enabled: true
                                layer.smooth: true
                            }

                            Text {
                                text: model.name
                                font.pixelSize: 13
                                color: "#fff"
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
            text: "💡 Tipp: GTK-Themes werden automatisch gewechselt wenn du zwischen Dark/Light Mode umschaltest"
            font.pixelSize: 11
            color: "#666"
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: "#3a3a3a"
    }

    // Cursor Theme
    Column {
        width: parent.width
        spacing: 15

        Row {
            width: parent.width
            spacing: 0

            Text {
                text: "Mauszeiger-Theme"
                font.pixelSize: 16
                color: "#aaa"
                width: parent.width - 150
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: settingsMenu.cursorTheme
                font.pixelSize: 14
                color: "#999"
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
                    color: settingsMenu.cursorTheme === model.name ? settingsMenu.accentColor : "#2a2a2a"
                    border.width: 1
                    border.color: "#3a3a3a"

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
                            layer.enabled: true
                            layer.smooth: true
                        }

                        Text {
                            text: model.name
                            font.pixelSize: 13
                            color: "#fff"
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
            text: "💡 Tipp: Weitere Cursor-Themes installieren mit: sudo pacman -S bibata-cursor-theme breeze"
            font.pixelSize: 11
            color: "#666"
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: "#3a3a3a"
    }

    // Icon Theme
    Column {
        width: parent.width
        spacing: 15

        Row {
            width: parent.width
            spacing: 0

            Text {
                text: "Symbol-Theme"
                font.pixelSize: 16
                color: "#aaa"
                width: parent.width - 150
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: settingsMenu.iconTheme
                font.pixelSize: 14
                color: "#999"
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
                    color: settingsMenu.iconTheme === model.name ? settingsMenu.accentColor : "#2a2a2a"
                    border.width: 1
                    border.color: "#3a3a3a"

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
                            layer.enabled: true
                            layer.smooth: true
                        }

                        Text {
                            text: model.name
                            font.pixelSize: 13
                            color: "#fff"
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
        color: "#3a3a3a"
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
                    text: "Titelleiste aktivieren"
                    font.pixelSize: 16
                    color: "#aaa"
                }

                Text {
                    text: "Aktiviert/deaktiviert die Titelleiste komplett (setzt bar_height auf 0)"
                    font.pixelSize: 12
                    color: "#666"
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                width: 60
                height: 32
                radius: 16
                color: settingsMenu.hyprbarsPluginEnabled ? settingsMenu.accentColor : "#3a3a3a"
                anchors.verticalCenter: parent.verticalCenter

                Behavior on color { ColorAnimation { duration: 150 } }

                Rectangle {
                    width: 24
                    height: 24
                    radius: 12
                    color: "#fff"
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
        color: "#3a3a3a"
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
                    text: "Titelleisten Buttons"
                    font.pixelSize: 16
                    color: "#aaa"
                }

                Text {
                    text: "Zeige Titelleiste mit Schließen/Maximieren/Minimieren Buttons"
                    font.pixelSize: 12
                    color: "#666"
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                width: 60
                height: 32
                radius: 16
                color: settingsMenu.hyprbarsEnabled ? settingsMenu.accentColor : "#3a3a3a"
                anchors.verticalCenter: parent.verticalCenter

                Behavior on color { ColorAnimation { duration: 150 } }

                Rectangle {
                    width: 24
                    height: 24
                    radius: 12
                    color: "#fff"
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
                color: "#3a3a3a"
            }

            // Individual Button Toggles
            Column {
                width: parent.width
                spacing: 15

                Text {
                    text: "Einzelne Buttons"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#aaa"
                }

                // Close Button Toggle
                Row {
                    width: parent.width
                    spacing: 15

                    Text {
                        text: "Schließen Button (X)"
                        font.pixelSize: 13
                        color: "#aaa"
                        width: parent.width - 80
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Rectangle {
                        width: 50
                        height: 28
                        radius: 14
                        color: (settingsMenu && settingsMenu.hyprbarsCloseButtonEnabled) ? settingsMenu.accentColor : "#3a3a3a"
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Rectangle {
                            width: 20
                            height: 20
                            radius: 10
                            color: "#fff"
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
                        text: "Maximieren Button (□)"
                        font.pixelSize: 13
                        color: "#aaa"
                        width: parent.width - 80
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Rectangle {
                        width: 50
                        height: 28
                        radius: 14
                        color: (settingsMenu && settingsMenu.hyprbarsMaxButtonEnabled) ? settingsMenu.accentColor : "#3a3a3a"
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Rectangle {
                            width: 20
                            height: 20
                            radius: 10
                            color: "#fff"
                            x: (settingsMenu && settingsMenu.hyprbarsMaxButtonEnabled) ? parent.width - width - 4 : 4
                            anchors.verticalCenter: parent.verticalCenter

                            Behavior on x { NumberAnimation { duration: 150 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                settingsMenu.hyprbarsMaxButtonEnabled = !settingsMenu.hyprbarsMaxButtonEnabled
                            }
                        }
                    }
                }

                // Minimize Button Toggle
                Row {
                    width: parent.width
                    spacing: 15

                    Text {
                        text: "Minimieren Button (—)"
                        font.pixelSize: 13
                        color: "#aaa"
                        width: parent.width - 80
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Rectangle {
                        width: 50
                        height: 28
                        radius: 14
                        color: (settingsMenu && settingsMenu.hyprbarsMinButtonEnabled) ? settingsMenu.accentColor : "#3a3a3a"
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on color { ColorAnimation { duration: 150 } }

                        Rectangle {
                            width: 20
                            height: 20
                            radius: 10
                            color: "#fff"
                            x: (settingsMenu && settingsMenu.hyprbarsMinButtonEnabled) ? parent.width - width - 4 : 4
                            anchors.verticalCenter: parent.verticalCenter

                            Behavior on x { NumberAnimation { duration: 150 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                settingsMenu.hyprbarsMinButtonEnabled = !settingsMenu.hyprbarsMinButtonEnabled
                            }
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: "#3a3a3a"
            }

            // Titelleisten-Höhe
            Column {
                width: parent.width
                spacing: 10

                Row {
                    width: parent.width
                    spacing: 0

                    Text {
                        text: "Titelleisten-Höhe"
                        font.pixelSize: 14
                        color: "#aaa"
                        width: parent.width - 50
                    }

                    Text {
                        text: settingsMenu.hyprbarsHeight + "px"
                        font.pixelSize: 14
                        color: "#999"
                        width: 50
                        horizontalAlignment: Text.AlignRight
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 6
                    radius: 3
                    color: "#3a3a3a"

                    Rectangle {
                        width: (settingsMenu ? ((settingsMenu.hyprbarsHeight - 15) / 35) * parent.width : 0)
                        height: parent.height
                        radius: 3
                        color: settingsMenu.accentColor

                        Behavior on width {
                            NumberAnimation {
                                duration: 100
                                easing.type: Easing.OutQuad
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: function(mouse) {
                            settingsMenu.hyprbarsHeight = Math.round(15 + (mouse.x / width) * 35)
                        }
                        onPositionChanged: function(mouse) {
                            if (pressed) {
                                settingsMenu.hyprbarsHeight = Math.round(15 + (mouse.x / width) * 35)
                            }
                        }
                    }
                }

                Text {
                    text: "Min: 15px • Max: 50px"
                    font.pixelSize: 10
                    color: "#666"
                }
            }

            // Button Ausrichtung
            Column {
                width: parent.width
                spacing: 10

                Text {
                    text: "Button-Position"
                    font.pixelSize: 14
                    color: "#aaa"
                }

                Row {
                    spacing: 10

                    Repeater {
                        model: ListModel {
                            ListElement { value: "left"; label: "Links" }
                            ListElement { value: "right"; label: "Rechts" }
                        }

                        delegate: Rectangle {
                            width: 100
                            height: 40
                            radius: 6
                            color: settingsMenu.hyprbarsButtonAlign === value ? settingsMenu.accentColor : "#2a2a2a"
                            border.width: 1
                            border.color: "#3a3a3a"

                            Behavior on color { ColorAnimation { duration: 150 } }

                            Text {
                                anchors.centerIn: parent
                                text: label
                                color: "#fff"
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
                color: "#3a3a3a"
            }

            Column {
                width: parent.width
                spacing: 20

                Text {
                    text: "Bar Design"
                    font.pixelSize: 15
                    font.bold: true
                    color: "#fff"
                }

                // Bar Farbe
                Row {
                    spacing: 15
                    Text {
                        text: "Bar Farbe"
                        font.pixelSize: 14
                        color: "#aaa"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsBarColor
                        border.width: 2
                        border.color: "#fff"
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
                        text: "Bar Blur"
                        font.pixelSize: 14
                        color: "#aaa"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 50
                        height: 30
                        radius: 15
                        color: settingsMenu.hyprbarsBarBlur ? settingsMenu.accentColor : "#3a3a3a"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Rectangle {
                            x: (settingsMenu && settingsMenu.hyprbarsBarBlur) ? parent.width - width - 3 : 3
                            y: 3
                            width: 24
                            height: 24
                            radius: 12
                            color: "#fff"
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
                color: "#3a3a3a"
            }

            Column {
                width: parent.width
                spacing: 20

                Text {
                    text: "Text Styling"
                    font.pixelSize: 15
                    font.bold: true
                    color: "#fff"
                }

                // Text Farbe
                Row {
                    spacing: 15
                    Text {
                        text: "Text Farbe"
                        font.pixelSize: 14
                        color: "#aaa"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 6
                        color: settingsMenu.hyprbarsTextColor
                        border.width: 2
                        border.color: "#fff"
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
                    Row {
                        width: parent.width
                        Text {
                            text: "Text Größe"
                            font.pixelSize: 14
                            color: "#aaa"
                            width: parent.width - 40
                        }
                        Text {
                            text: settingsMenu.hyprbarsTextSize + "px"
                            font.pixelSize: 14
                            color: "#999"
                            width: 40
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                    Rectangle {
                        width: parent.width
                        height: 6
                        radius: 3
                        color: "#3a3a3a"
                        Rectangle {
                            width: (settingsMenu ? ((settingsMenu.hyprbarsTextSize - 8) / 8) * parent.width : 0)
                            height: parent.height
                            radius: 3
                            color: settingsMenu.accentColor
                            Behavior on width { NumberAnimation { duration: 100 } }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onPressed: {
                                settingsMenu.hyprbarsTextSize = Math.round(8 + (mouse.x / width) * 8)
                            }
                            onPositionChanged: {
                                if (pressed) {
                                    settingsMenu.hyprbarsTextSize = Math.round(8 + (mouse.x / width) * 8)
                                }
                            }
                        }
                    }
                }

                // Text Font
                Column {
                    width: parent.width
                    spacing: 10
                    Text {
                        text: "Schriftart"
                        font.pixelSize: 14
                        color: "#aaa"
                    }
                    Rectangle {
                        width: parent.width
                        height: 40
                        radius: 6
                        color: "#2a2a2a"
                        border.width: 1
                        border.color: "#3a3a3a"
                        TextInput {
                            id: fontInput
                            anchors.fill: parent
                            anchors.margins: 10
                            text: settingsMenu.hyprbarsTextFont
                            color: "#fff"
                            font.pixelSize: 13
                            verticalAlignment: TextInput.AlignVCenter
                            onEditingFinished: {
                                settingsMenu.hyprbarsTextFont = text
                            }
                        }
                    }
                }

                // Text Align
                Column {
                    width: parent.width
                    spacing: 10
                    Text {
                        text: "Text Ausrichtung"
                        font.pixelSize: 14
                        color: "#aaa"
                    }
                    Row {
                        spacing: 10
                        Repeater {
                            model: ListModel {
                                ListElement { value: "left"; label: "Links" }
                                ListElement { value: "center"; label: "Mitte" }
                                ListElement { value: "right"; label: "Rechts" }
                            }
                            delegate: Rectangle {
                                width: 80
                                height: 35
                                radius: 6
                                color: settingsMenu.hyprbarsTextAlign === value ? settingsMenu.accentColor : "#2a2a2a"
                                border.width: 1
                                border.color: "#3a3a3a"
                                Behavior on color { ColorAnimation { duration: 150 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: label
                                    color: "#fff"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: settingsMenu.hyprbarsTextAlign = value
                                }
                            }
                        }
                    }
                }

                // Title Enabled
                Row {
                    spacing: 15
                    Text {
                        text: "Titel anzeigen"
                        font.pixelSize: 14
                        color: "#aaa"
                        width: 150
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        width: 50
                        height: 30
                        radius: 15
                        color: settingsMenu.hyprbarsBarTitleEnabled ? settingsMenu.accentColor : "#3a3a3a"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Rectangle {
                            x: (settingsMenu && settingsMenu.hyprbarsBarTitleEnabled) ? parent.width - width - 3 : 3
                            y: 3
                            width: 24
                            height: 24
                            radius: 12
                            color: "#fff"
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
                color: "#3a3a3a"
            }

            Column {
                width: parent.width
                spacing: 20

                Text {
                    text: "Windows 11 Style (Transparente Buttons)"
                    font.pixelSize: 15
                    font.bold: true
                    color: "#fff"
                }

                Text {
                    text: "Im Windows 11 Style haben alle Buttons transparente Hintergründe und zeigen nur beim Hover Farben. Die Button-Text-Farben werden automatisch an den Dark/Light Mode angepasst."
                    font.pixelSize: 11
                    color: "#666"
                    wrapMode: Text.WordWrap
                    width: parent.width
                }

            }
        }
    }

    // === SCHRIFTARTEN ===
    Rectangle {
        width: parent.width
        height: 1
        color: "#3a3a3a"
    }

    Column {
        width: parent.width
        spacing: 20

        Text {
            text: "Schriftarten"
            font.pixelSize: 18
            font.bold: true
            color: "#fff"
        }

        // Interface Font
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: "Oberfläche"
                font.pixelSize: 14
                color: "#aaa"
            }
            Rectangle {
                width: 280
                height: 40
                radius: 6
                color: "#2a2a2a"
                border.width: 1
                border.color: "#3a3a3a"
                TextInput {
                    id: fontInterfaceInput
                    anchors.fill: parent
                    anchors.margins: 10
                    text: settingsMenu.fontInterface
                    color: "#fff"
                    font.pixelSize: 13
                    verticalAlignment: TextInput.AlignVCenter
                    onEditingFinished: {
                        settingsMenu.fontInterface = text
                    }
                }
            }
            Text {
                text: "z.B. Cantarell 11"
                font.pixelSize: 11
                color: "#666"
            }
        }

        // Document Font
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: "Dokumente"
                font.pixelSize: 14
                color: "#aaa"
            }
            Rectangle {
                width: 280
                height: 40
                radius: 6
                color: "#2a2a2a"
                border.width: 1
                border.color: "#3a3a3a"
                TextInput {
                    id: fontDocumentInput
                    anchors.fill: parent
                    anchors.margins: 10
                    text: settingsMenu.fontDocument
                    color: "#fff"
                    font.pixelSize: 13
                    verticalAlignment: TextInput.AlignVCenter
                    onEditingFinished: {
                        settingsMenu.fontDocument = text
                    }
                }
            }
            Text {
                text: "z.B. Sans 11"
                font.pixelSize: 11
                color: "#666"
            }
        }

        // Monospace Font
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: "Konsolentext (Monospace)"
                font.pixelSize: 14
                color: "#aaa"
            }
            Rectangle {
                width: 280
                height: 40
                radius: 6
                color: "#2a2a2a"
                border.width: 1
                border.color: "#3a3a3a"
                TextInput {
                    id: fontMonospaceInput
                    anchors.fill: parent
                    anchors.margins: 10
                    text: settingsMenu.fontMonospace
                    color: "#fff"
                    font.pixelSize: 13
                    verticalAlignment: TextInput.AlignVCenter
                    onEditingFinished: {
                        settingsMenu.fontMonospace = text
                    }
                }
            }
            Text {
                text: "z.B. Monospace 10 (für Terminal/Code)"
                font.pixelSize: 11
                color: "#666"
            }
        }

        // Font Scaling
        Column {
            width: parent.width
            spacing: 10
            Row {
                width: parent.width
                Text {
                    text: "Skalierung"
                    font.pixelSize: 14
                    color: "#aaa"
                    width: parent.width - 50
                }
                Text {
                    text: settingsMenu.fontScaling.toFixed(2)
                    font.pixelSize: 14
                    color: "#999"
                    width: 50
                    horizontalAlignment: Text.AlignRight
                }
            }
            Rectangle {
                width: parent.width
                height: 6
                radius: 3
                color: "#3a3a3a"
                Rectangle {
                    width: (settingsMenu ? ((settingsMenu.fontScaling - 0.5) / 1.5) * parent.width : 0)
                    height: parent.height
                    radius: 3
                    color: settingsMenu.accentColor
                    Behavior on width { NumberAnimation { duration: 100 } }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onPressed: {
                        settingsMenu.fontScaling = 0.5 + (mouse.x / width) * 1.5
                    }
                    onPositionChanged: {
                        if (pressed) {
                            settingsMenu.fontScaling = 0.5 + (mouse.x / width) * 1.5
                        }
                    }
                }
            }
            Text {
                text: "0.5 (klein) bis 2.0 (groß)"
                font.pixelSize: 11
                color: "#666"
            }
        }

        // Hinting
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: "Hinting"
                font.pixelSize: 14
                color: "#aaa"
            }
            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: "none"; label: "Keine" }
                        ListElement { value: "slight"; label: "Leicht" }
                        ListElement { value: "medium"; label: "Mittel" }
                        ListElement { value: "full"; label: "Voll" }
                    }
                    delegate: Rectangle {
                        width: 90
                        height: 35
                        radius: 6
                        color: settingsMenu.fontHinting === value ? settingsMenu.accentColor : "#2a2a2a"
                        border.width: 1
                        border.color: "#3a3a3a"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            anchors.centerIn: parent
                            text: label
                            color: "#fff"
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
                text: "Kantenglättung"
                font.pixelSize: 14
                color: "#aaa"
            }
            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: "none"; label: "Keine" }
                        ListElement { value: "grayscale"; label: "Graustufen" }
                        ListElement { value: "rgba"; label: "RGB" }
                    }
                    delegate: Rectangle {
                        width: 110
                        height: 35
                        radius: 6
                        color: settingsMenu.fontAntialiasing === value ? settingsMenu.accentColor : "#2a2a2a"
                        border.width: 1
                        border.color: "#3a3a3a"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            anchors.centerIn: parent
                            text: label
                            color: "#fff"
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
}
}
