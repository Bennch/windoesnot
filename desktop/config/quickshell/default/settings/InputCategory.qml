import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"

    width: parent.width
    spacing: 30

    Process {
        id: filemanagerRestart
        onExited: {}
    }

    function restartFileManager() {
        filemanagerRestart.command = ["/usr/bin/killall", "-9", "nautilus", "dolphin", "nemo", "thunar"]
        filemanagerRestart.running = true
    }

    // === SYSTEMSPRACHE ===
    Column {
        width: parent.width
        spacing: 20

        Text {
            text: Lang.get("input.languageTitle", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Column {
            width: parent.width
            spacing: 10

            Row {
                spacing: 15
                Text {
                    text: Lang.get("input.currentLanguage", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                    width: 150
                }
                Text {
                    text: settingsMenu.systemLocale
                    font.pixelSize: 14
                    color: settingsMenu.accentColor
                    font.bold: true
                }
            }

            Text {
                text: Lang.get("input.language", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: localeComboBox
                width: 350
                height: 40

                model: settingsMenu ? settingsMenu.systemLocalesModel : null

                textRole: "text"

                currentIndex: {
                    if (!model || !settingsMenu) return -1
                    for (var i = 0; i < model.count; i++) {
                        if (model.get(i).value === settingsMenu.systemLocale) return i
                    }
                    return -1
                }
                displayText: currentIndex >= 0 ? model.get(currentIndex).text : settingsMenu.systemLocale
                enabled: !settingsMenu.localeChangeBusy
                onActivated: {
                    settingsMenu.selectLanguage(model.get(currentIndex).value)
                    restartFileManager()
                }

                background: Rectangle {
                    color: localeComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: localeComboBox.indicator.width + localeComboBox.spacing
                    text: localeComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: localeComboBox.width - width - 12
                    y: localeComboBox.topPadding + (localeComboBox.availableHeight - height) / 2
                    text: "\u25BC"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: localeComboBox.height + 2
                    width: localeComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: localeComboBox.popup.visible ? localeComboBox.delegateModel : null
                        currentIndex: localeComboBox.highlightedIndex

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
                    width: localeComboBox.width - 2
                    contentItem: Text {
                        text: model.text
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: localeComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: settingsMenu.systemLocale.split(/[_ .@-]/)[0] !== "de"
                    && settingsMenu.systemLocale.split(/[_ .@-]/)[0] !== "en"
                text: Lang.get("input.languageFallback", _lang)
                font.pixelSize: 13
                color: settingsMenu.darkMode ? "#bbb" : "#555"
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: settingsMenu.localeChangeFailed
                text: Lang.get("input.languageFailed", _lang)
                font.pixelSize: 13
                color: settingsMenu.darkMode ? "#bbb" : "#555"
            }

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: Lang.get("input.languageEffect", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#999" : "#666"
                font.italic: true
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // === DATUM & UHRZEIT ===
    Column {
        width: parent.width
        spacing: 20

        Text {
            text: Lang.get("input.dateTime", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Timezone
        Column {
            width: parent.width
            spacing: 10

            Row {
                spacing: 15
                Text {
                    text: Lang.get("input.currentTimezone", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                    width: 150
                }
                Text {
                    text: settingsMenu.timeZone
                    font.pixelSize: 14
                    color: settingsMenu.accentColor
                    font.bold: true
                }
            }

            Text {
                text: Lang.get("input.timezone", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: timezoneComboBox
                width: 350
                height: 40

                model: settingsMenu ? settingsMenu.timezonesModel : null

                textRole: "text"

                onModelChanged: {
                    if (model && model.count > 0 && settingsMenu) {
                        for (var i = 0; i < model.count; i++) {
                            if (model.get(i).value === settingsMenu.timeZone) {
                                currentIndex = i
                                return
                            }
                        }
                    }
                }

                onActivated: {
                    settingsMenu.timeZone = model.get(currentIndex).value
                }

                background: Rectangle {
                    color: timezoneComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: timezoneComboBox.indicator.width + timezoneComboBox.spacing
                    text: timezoneComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: timezoneComboBox.width - width - 12
                    y: timezoneComboBox.topPadding + (timezoneComboBox.availableHeight - height) / 2
                    text: "\u25BC"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: timezoneComboBox.height + 2
                    width: timezoneComboBox.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 300)
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: timezoneComboBox.popup.visible ? timezoneComboBox.delegateModel : null
                        currentIndex: timezoneComboBox.highlightedIndex

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
                    width: timezoneComboBox.width - 2
                    contentItem: Text {
                        text: model.text
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: timezoneComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }
        }

        // Time Format
        Row {
            spacing: 15
            Text {
                text: Lang.get("input.24hourFormat", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 250
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                width: 50
                height: 30
                radius: 15
                color: settingsMenu.use24HourFormat ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    x: (settingsMenu && settingsMenu.use24HourFormat) ? parent.width - width - 3 : 3
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
                    onClicked: settingsMenu.use24HourFormat = !settingsMenu.use24HourFormat
                }
            }
        }

        // NTP Synchronization
        Row {
            spacing: 15
            Text {
                text: Lang.get("input.ntpSync", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 250
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                width: 50
                height: 30
                radius: 15
                color: settingsMenu.ntpEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    x: (settingsMenu && settingsMenu.ntpEnabled) ? parent.width - width - 3 : 3
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
                    onClicked: settingsMenu.ntpEnabled = !settingsMenu.ntpEnabled
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // === MAUS ===
    Column {
        width: parent.width
        spacing: 20

        Text {
            text: Lang.get("input.mouse", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Mouse Sensitivity Slider
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("input.sensitivity", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                width: parent.width
                spacing: 12
                Slider {
                    id: sensitivitySlider
                    width: parent.width - 60
                    from: -1.0; to: 1.0; stepSize: 0.01
                    value: settingsMenu ? settingsMenu.mouseSensitivity : 0.0
                    background: Rectangle {
                        x: sensitivitySlider.leftPadding
                        y: sensitivitySlider.topPadding + sensitivitySlider.availableHeight / 2 - height / 2
                        implicitWidth: 200; implicitHeight: 4
                        width: sensitivitySlider.availableWidth; height: implicitHeight
                        radius: 2; color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Rectangle {
                            width: sensitivitySlider.visualPosition * parent.width
                            height: parent.height; radius: 2
                            color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        }
                    }
                    handle: Rectangle {
                        x: sensitivitySlider.leftPadding + sensitivitySlider.visualPosition * (sensitivitySlider.availableWidth - width)
                        y: sensitivitySlider.topPadding + sensitivitySlider.availableHeight / 2 - height / 2
                        implicitWidth: 20; implicitHeight: 20; radius: 10
                        color: sensitivitySlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                        border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 2
                        Behavior on color { ColorAnimation { duration: 100 } }
                    }
                    onMoved: { if (settingsMenu) settingsMenu.mouseSensitivity = value }
                }
                Text {
                    text: (settingsMenu ? settingsMenu.mouseSensitivity.toFixed(2) : "0.00")
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#999" : "#666"
                    width: 48; horizontalAlignment: Text.AlignRight
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Text {
                text: Lang.get("input.sensitivityHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Mouse Acceleration Profile
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("input.accelProfile", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: "flat"; labelKey: "input.flat" }
                        ListElement { value: "adaptive"; labelKey: "input.adaptive" }
                    }
                    delegate: Rectangle {
                        width: 140
                        height: 40
                        radius: 6
                        color: settingsMenu.mouseAccelProfile === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
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
                            onClicked: settingsMenu.mouseAccelProfile = value
                        }
                    }
                }
            }
        }

        // Follow Mouse
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("input.followMouse", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: 0; labelKey: "input.off" }
                        ListElement { value: 1; labelKey: "input.move" }
                        ListElement { value: 2; labelKey: "input.moveFocus" }
                        ListElement { value: 3; labelKey: "input.focus" }
                    }
                    delegate: Rectangle {
                        width: 120
                        height: 40
                        radius: 6
                        color: settingsMenu.followMouse === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            anchors.centerIn: parent
                            text: Lang.get(labelKey)
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            font.pixelSize: 11
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: settingsMenu.followMouse = value
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

    // === TASTATUR ===
    Column {
        width: parent.width
        spacing: 20

        Text {
            text: Lang.get("input.keyboard", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Keyboard Layout
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("input.layout", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            ComboBox {
                id: layoutComboBox
                width: 280
                height: 40

                model: settingsMenu ? settingsMenu.keyboardLayoutsModel : null

                textRole: "text"

                onModelChanged: {
                    if (model && model.count > 0 && settingsMenu) {
                        for (var i = 0; i < model.count; i++) {
                            if (model.get(i).value === settingsMenu.keyboardLayout) {
                                currentIndex = i
                                return
                            }
                        }
                    }
                }

                onActivated: {
                    settingsMenu.keyboardLayout = model.get(currentIndex).value
                }

                // Custom styling
                background: Rectangle {
                    color: layoutComboBox.pressed ? (settingsMenu.darkMode ? "#1a1a1a" : "#e0e0e0") : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                    border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 12
                    rightPadding: layoutComboBox.indicator.width + layoutComboBox.spacing
                    text: layoutComboBox.displayText
                    font.pixelSize: 13
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: layoutComboBox.width - width - 12
                    y: layoutComboBox.topPadding + (layoutComboBox.availableHeight - height) / 2
                    text: "\u25BC"
                    font.pixelSize: 10
                    color: settingsMenu.darkMode ? "#999" : "#666"
                }

                popup: Popup {
                    y: layoutComboBox.height + 2
                    width: layoutComboBox.width
                    implicitHeight: contentItem.implicitHeight
                    padding: 1

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: layoutComboBox.popup.visible ? layoutComboBox.delegateModel : null
                        currentIndex: layoutComboBox.highlightedIndex

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
                    width: layoutComboBox.width - 2
                    contentItem: Text {
                        text: model.text
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 12
                    }
                    highlighted: layoutComboBox.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? settingsMenu.accentColor : (parent.hovered ? (settingsMenu.darkMode ? "#333" : "#e5e5e5") : "transparent")
                        radius: 4
                    }
                }
            }
        }

        // Repeat Rate
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("input.repeatRate", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                width: parent.width
                spacing: 12
                Slider {
                    id: repeatRateSlider
                    width: parent.width - 60
                    from: 10; to: 50; stepSize: 1
                    value: settingsMenu ? settingsMenu.repeatRate : 25
                    background: Rectangle {
                        x: repeatRateSlider.leftPadding
                        y: repeatRateSlider.topPadding + repeatRateSlider.availableHeight / 2 - height / 2
                        implicitWidth: 200; implicitHeight: 4
                        width: repeatRateSlider.availableWidth; height: implicitHeight
                        radius: 2; color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Rectangle {
                            width: repeatRateSlider.visualPosition * parent.width
                            height: parent.height; radius: 2
                            color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        }
                    }
                    handle: Rectangle {
                        x: repeatRateSlider.leftPadding + repeatRateSlider.visualPosition * (repeatRateSlider.availableWidth - width)
                        y: repeatRateSlider.topPadding + repeatRateSlider.availableHeight / 2 - height / 2
                        implicitWidth: 20; implicitHeight: 20; radius: 10
                        color: repeatRateSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                        border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 2
                        Behavior on color { ColorAnimation { duration: 100 } }
                    }
                    onMoved: { if (settingsMenu) settingsMenu.repeatRate = value }
                }
                Text {
                    text: (settingsMenu ? settingsMenu.repeatRate : 25) + "/s"
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#999" : "#666"
                    width: 48; horizontalAlignment: Text.AlignRight
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Text {
                text: Lang.get("input.repeatRateHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Repeat Delay
        Column {
            width: parent.width
            spacing: 10
            Text {
                text: Lang.get("input.repeatDelay", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }
            Row {
                width: parent.width
                spacing: 12
                Slider {
                    id: repeatDelaySlider
                    width: parent.width - 60
                    from: 200; to: 1000; stepSize: 10
                    value: settingsMenu ? settingsMenu.repeatDelay : 400
                    background: Rectangle {
                        x: repeatDelaySlider.leftPadding
                        y: repeatDelaySlider.topPadding + repeatDelaySlider.availableHeight / 2 - height / 2
                        implicitWidth: 200; implicitHeight: 4
                        width: repeatDelaySlider.availableWidth; height: implicitHeight
                        radius: 2; color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Rectangle {
                            width: repeatDelaySlider.visualPosition * parent.width
                            height: parent.height; radius: 2
                            color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        }
                    }
                    handle: Rectangle {
                        x: repeatDelaySlider.leftPadding + repeatDelaySlider.visualPosition * (repeatDelaySlider.availableWidth - width)
                        y: repeatDelaySlider.topPadding + repeatDelaySlider.availableHeight / 2 - height / 2
                        implicitWidth: 20; implicitHeight: 20; radius: 10
                        color: repeatDelaySlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                        border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 2
                        Behavior on color { ColorAnimation { duration: 100 } }
                    }
                    onMoved: { if (settingsMenu) settingsMenu.repeatDelay = value }
                }
                Text {
                    text: (settingsMenu ? settingsMenu.repeatDelay : 400) + "ms"
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#999" : "#666"
                    width: 48; horizontalAlignment: Text.AlignRight
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Text {
                text: Lang.get("input.repeatDelayHint", _lang)
                font.pixelSize: 11
                color: settingsMenu.darkMode ? "#666" : "#888"
            }
        }

        // Numlock by Default
        Row {
            spacing: 15
            Text {
                text: Lang.get("input.numlock", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 250
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                width: 50
                height: 30
                radius: 15
                color: settingsMenu.numlockByDefault ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    x: (settingsMenu && settingsMenu.numlockByDefault) ? parent.width - width - 3 : 3
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
                    onClicked: settingsMenu.numlockByDefault = !settingsMenu.numlockByDefault
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: 1
        color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
    }

    // === TOUCHPAD ===
    Column {
        width: parent.width
        spacing: 20

        Text {
            text: Lang.get("input.touchpad", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Natural Scroll
        Row {
            spacing: 15
            Text {
                text: Lang.get("input.naturalScroll", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 250
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                width: 50
                height: 30
                radius: 15
                color: settingsMenu.touchpadNaturalScroll ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    x: (settingsMenu && settingsMenu.touchpadNaturalScroll) ? parent.width - width - 3 : 3
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
                    onClicked: settingsMenu.touchpadNaturalScroll = !settingsMenu.touchpadNaturalScroll
                }
            }
        }

        // Disable while typing
        Row {
            spacing: 15
            Text {
                text: Lang.get("input.disableWhileTyping", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 250
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                width: 50
                height: 30
                radius: 15
                color: settingsMenu.touchpadDisableWhileTyping ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    x: (settingsMenu && settingsMenu.touchpadDisableWhileTyping) ? parent.width - width - 3 : 3
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
                    onClicked: settingsMenu.touchpadDisableWhileTyping = !settingsMenu.touchpadDisableWhileTyping
                }
            }
        }

        // Tap to Click
        Row {
            spacing: 15
            Text {
                text: Lang.get("input.tapToClick", _lang)
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 250
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                width: 50
                height: 30
                radius: 15
                color: settingsMenu.touchpadTapToClick ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    x: (settingsMenu && settingsMenu.touchpadTapToClick) ? parent.width - width - 3 : 3
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
                    onClicked: settingsMenu.touchpadTapToClick = !settingsMenu.touchpadTapToClick
                }
            }
        }
}
}
