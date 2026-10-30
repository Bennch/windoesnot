import "../widgets"
import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell.Io
import "../i18n/Lang.js" as Lang

Column {
    id: alignmentRoot
    property var settingsMenu: null
    property string _lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    property bool geocodeRunning: false

    ListModel { id: suggestionsModel }

    Timer {
        id: geocodeDebounce
        interval: 400
        repeat: false
        onTriggered: {
            var city = cityTextField.text.trim()
            if (city.length >= 2) {
                geocodeSuggestProc.command = ["bash", "-c",
                    "curl -s --max-time 8 -H 'User-Agent: QuickshellDesktop/1.0' 'https://nominatim.openstreetmap.org/search?q=" + encodeURIComponent(city) + "&format=json&limit=5&addressdetails=1'"
                ]
                geocodeSuggestProc.running = true
            } else {
                suggestionsModel.clear()
            }
        }
    }

    Process {
        id: geocodeSuggestProc
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var d = JSON.parse(text)
                    suggestionsModel.clear()
                    for (var i = 0; i < Math.min(d.length, 5); i++) {
                        var item = d[i]
                        var addr = item.address || {}
                        var name = addr.city || addr.town || addr.village || addr.municipality || item.display_name.split(",")[0].trim()
                        var country = addr.country || ""
                        var state = addr.state || ""
                        var zip = addr.postcode || ""
                        var displayText = name
                        if (zip) displayText += " (" + zip + ")"
                        if (state && state !== name) displayText += ", " + state
                        if (country) displayText += ", " + country
                        suggestionsModel.append({displayText: displayText, lat: parseFloat(item.lat), lon: parseFloat(item.lon), cityName: name})
                    }
                } catch(e) { suggestionsModel.clear() }
            }
        }
    }

    Process {
        id: geocodeConfirmProc
        stdout: StdioCollector {
            onStreamFinished: {
                geocodeRunning = false
                try {
                    var d = JSON.parse(text)
                    if (d.length > 0) {
                        var r = d[0]
                        var addr = r.address || {}
                        var name = addr.city || addr.town || addr.village || addr.municipality || r.display_name.split(",")[0].trim()
                        settingsMenu.weatherCity = name
                        settingsMenu.weatherLatitude = parseFloat(r.lat)
                        settingsMenu.weatherLongitude = parseFloat(r.lon)
                        geocodeStatus.text = "✓ " + name + (addr.country ? ", " + addr.country : "")
                        geocodeStatus.color = "#4caf50"
                        suggestionsModel.clear()
                    } else {
                        geocodeStatus.text = "Kein Ergebnis gefunden"
                        geocodeStatus.color = "#e53935"
                    }
                } catch(e) {
                    geocodeStatus.text = "Fehler beim Abrufen"
                    geocodeStatus.color = "#e53935"
                }
            }
        }
    }

    function geocodeCity() {
        var city = cityTextField.text.trim()
        if (city.length === 0) return
        if (suggestionsModel.count > 0) {
            var first = suggestionsModel.get(0)
            settingsMenu.weatherCity = first.cityName
            settingsMenu.weatherLatitude = first.lat
            settingsMenu.weatherLongitude = first.lon
            cityTextField.text = first.cityName
            geocodeStatus.text = "✓ " + first.displayText
            geocodeStatus.color = "#4caf50"
            suggestionsModel.clear()
            return
        }
        geocodeRunning = true
        geocodeStatus.color = settingsMenu.darkMode ? "#888" : "#666"
        geocodeStatus.text = "Suche läuft…"
        suggestionsModel.clear()
        geocodeConfirmProc.command = ["bash", "-c",
            "curl -s --max-time 8 -H 'User-Agent: QuickshellDesktop/1.0' 'https://nominatim.openstreetmap.org/search?q=" + encodeURIComponent(city) + "&format=json&limit=1&addressdetails=1'"
        ]
        geocodeConfirmProc.running = true
    }

    width: parent.width
    spacing: 30

    // Taskbar Ausrichtung
    Column {
        width: parent.width
        spacing: 10

        Text {
            text: Lang.get("alignment.taskbar", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Row {
            spacing: 10

            Repeater {
                model: ListModel {
                    ListElement { value: "left"; labelKey: "appearance.left" }
                    ListElement { value: "center"; labelKey: "alignment.centered" }
                }

                delegate: Rectangle {
                    width: 100
                    height: 40
                    radius: 6
                    color: settingsMenu.taskbarAlignmentSetting === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
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
                            console.log("=== Alignment button clicked:", value)
                            console.log("=== Current setting:", settingsMenu.taskbarAlignmentSetting)
                            console.log("=== Current taskbar:", panelWindow.taskbarAlignment)
                            settingsMenu.taskbarAlignmentSetting = value
                            panelWindow.taskbarAlignment = value
                            console.log("=== After change - setting:", settingsMenu.taskbarAlignmentSetting)
                            console.log("=== After change - taskbar:", panelWindow.taskbarAlignment)
                        }
                    }
                }
            }
        }
    }

    // Border Radius Slider
    Column {
        width: parent.width
        spacing: 10

        Text {
            text: Lang.get("alignment.borderRadius", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Row {
            width: parent.width
            spacing: 12

            Slider {
                id: borderRadiusSlider
                width: parent.width - 60
                from: 0
                to: 30
                stepSize: 1
                value: settingsMenu ? settingsMenu.borderRadius : 0

                background: Rectangle {
                    x: borderRadiusSlider.leftPadding
                    y: borderRadiusSlider.topPadding + borderRadiusSlider.availableHeight / 2 - height / 2
                    implicitWidth: 200
                    implicitHeight: 4
                    width: borderRadiusSlider.availableWidth
                    height: implicitHeight
                    radius: 2
                    color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    Rectangle {
                        width: borderRadiusSlider.visualPosition * parent.width
                        height: parent.height
                        color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        radius: 2
                    }
                }

                handle: Rectangle {
                    x: borderRadiusSlider.leftPadding + borderRadiusSlider.visualPosition * (borderRadiusSlider.availableWidth - width)
                    y: borderRadiusSlider.topPadding + borderRadiusSlider.availableHeight / 2 - height / 2
                    implicitWidth: 20
                    implicitHeight: 20
                    radius: 10
                    color: borderRadiusSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                    border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 2
                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                onMoved: {
                    if (settingsMenu) settingsMenu.borderRadius = value
                }
            }

            Text {
                text: (settingsMenu ? settingsMenu.borderRadius : 0) + "px"
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 48
                horizontalAlignment: Text.AlignRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // Window Gaps Slider
    Column {
        width: parent.width
        spacing: 10

        Text {
            text: Lang.get("alignment.windowGaps", _lang)
            font.pixelSize: 18
            font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        Row {
            width: parent.width
            spacing: 12

            Slider {
                id: windowGapsSlider
                width: parent.width - 60
                from: 0
                to: 20
                stepSize: 1
                value: settingsMenu ? settingsMenu.windowGaps : 0

                background: Rectangle {
                    x: windowGapsSlider.leftPadding
                    y: windowGapsSlider.topPadding + windowGapsSlider.availableHeight / 2 - height / 2
                    implicitWidth: 200
                    implicitHeight: 4
                    width: windowGapsSlider.availableWidth
                    height: implicitHeight
                    radius: 2
                    color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"

                    Rectangle {
                        width: windowGapsSlider.visualPosition * parent.width
                        height: parent.height
                        color: settingsMenu ? settingsMenu.accentColor : "#FE6F2D"
                        radius: 2
                    }
                }

                handle: Rectangle {
                    x: windowGapsSlider.leftPadding + windowGapsSlider.visualPosition * (windowGapsSlider.availableWidth - width)
                    y: windowGapsSlider.topPadding + windowGapsSlider.availableHeight / 2 - height / 2
                    implicitWidth: 20
                    implicitHeight: 20
                    radius: 10
                    color: windowGapsSlider.pressed ? Qt.darker(settingsMenu ? settingsMenu.accentColor : "#FE6F2D", 1.2) : (settingsMenu ? settingsMenu.accentColor : "#FE6F2D")
                    border.color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                    border.width: 2
                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                onMoved: {
                    if (settingsMenu) settingsMenu.windowGaps = value
                }
            }

            Text {
                text: (settingsMenu ? settingsMenu.windowGaps : 0) + "px"
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
                width: 48
                horizontalAlignment: Text.AlignRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // Taskbar Icon Toggles section
    Column {
        width: parent.width
        spacing: 14

        Text {
            text: Lang.get("alignment.taskbarIcons", _lang)
            font.pixelSize: 18; font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Workspace Toggle
        Row {
            width: parent.width
            spacing: 15

            Column {
                spacing: 5
                width: parent.width - 80

                Text {
                    text: Lang.get("alignment.workspaceToggle", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }
                Text {
                    text: Lang.get("alignment.workspaceToggleDesc", _lang)
                    font.pixelSize: 12; color: settingsMenu.darkMode ? "#666" : "#888"
                    wrapMode: Text.WordWrap; width: parent.width
                }
            }

            Rectangle {
                width: 60; height: 32; radius: 16
                color: settingsMenu.workspaceToggleEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                anchors.verticalCenter: parent.verticalCenter
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: settingsMenu.workspaceToggleEnabled ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on x { NumberAnimation { duration: 150 } }
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        settingsMenu.workspaceToggleEnabled = !settingsMenu.workspaceToggleEnabled
                        workspaceContainer.visible = settingsMenu.workspaceToggleEnabled
                    }
                }
            }
        }

        // Search Button Toggle
        Row {
            width: parent.width
            spacing: 15

            Column {
                spacing: 5
                width: parent.width - 80
                Text {
                    text: Lang.get("alignment.searchButton", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }
                Text {
                    text: Lang.get("alignment.searchButtonDesc", _lang)
                    font.pixelSize: 12; color: settingsMenu.darkMode ? "#666" : "#888"
                    wrapMode: Text.WordWrap; width: parent.width
                }
            }

            Rectangle {
                width: 60; height: 32; radius: 16
                color: settingsMenu.showSearchButton ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                anchors.verticalCenter: parent.verticalCenter
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: settingsMenu.showSearchButton ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on x { NumberAnimation { duration: 150 } }
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: settingsMenu.showSearchButton = !settingsMenu.showSearchButton
                }
            }
        }

        // Store Button Toggle
        Row {
            width: parent.width
            spacing: 15

            Column {
                spacing: 5
                width: parent.width - 80
                Text {
                    text: Lang.get("alignment.storeButton", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }
                Text {
                    text: Lang.get("alignment.storeButtonDesc", _lang)
                    font.pixelSize: 12; color: settingsMenu.darkMode ? "#666" : "#888"
                    wrapMode: Text.WordWrap; width: parent.width
                }
            }

            Rectangle {
                width: 60; height: 32; radius: 16
                color: settingsMenu.showStoreButton ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                anchors.verticalCenter: parent.verticalCenter
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: settingsMenu.showStoreButton ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on x { NumberAnimation { duration: 150 } }
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: settingsMenu.showStoreButton = !settingsMenu.showStoreButton
                }
            }
        }

        // Settings Button Toggle
        Row {
            width: parent.width
            spacing: 15

            Column {
                spacing: 5
                width: parent.width - 80
                Text {
                    text: Lang.get("alignment.settingsButton", _lang)
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }
                Text {
                    text: Lang.get("alignment.settingsButtonDesc", _lang)
                    font.pixelSize: 12; color: settingsMenu.darkMode ? "#666" : "#888"
                    wrapMode: Text.WordWrap; width: parent.width
                }
            }

            Rectangle {
                width: 60; height: 32; radius: 16
                color: settingsMenu.showSettingsButton ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                anchors.verticalCenter: parent.verticalCenter
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: settingsMenu.showSettingsButton ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on x { NumberAnimation { duration: 150 } }
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: settingsMenu.showSettingsButton = !settingsMenu.showSettingsButton
                }
            }
        }
    }

    // Wetter
    Column {
        width: parent.width
        spacing: 14

        Text {
            text: "Wetter"
            font.pixelSize: 18; font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Enable toggle
        Row {
            width: parent.width
            spacing: 15
            Column {
                spacing: 5
                width: parent.width - 80
                Text {
                    text: "Wetter-Widget aktivieren"
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                }
                Text {
                    text: "Zeigt das aktuelle Wetter an"
                    font.pixelSize: 12; color: settingsMenu.darkMode ? "#666" : "#888"
                    wrapMode: Text.WordWrap; width: parent.width
                }
            }
            Rectangle {
                readonly property bool hasLocation: settingsMenu.weatherLatitude !== 0 || settingsMenu.weatherLongitude !== 0
                width: 60; height: 32; radius: 16
                opacity: hasLocation ? 1 : 0.5
                color: settingsMenu.weatherEnabled ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                anchors.verticalCenter: parent.verticalCenter
                Behavior on color { ColorAnimation { duration: 150 } }
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    x: settingsMenu.weatherEnabled ? parent.width - width - 4 : 4
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on x { NumberAnimation { duration: 150 } }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: parent.hasLocation ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: {
                        // A location (PLZ/city search above) is required before the
                        // widget can be turned on; otherwise it ends up enabled with
                        // no data and no icon.
                        if (parent.hasLocation) settingsMenu.weatherEnabled = !settingsMenu.weatherEnabled
                        else geocodeStatus.text = "⚠ " + geocodeStatus.text
                    }
                }
            }
        }

        // Location toggle
        Column {
            width: parent.width
            spacing: 8

            Text {
                text: "Anzeige-Position"
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: "tray";    label: "Systembereich" }
                        ListElement { value: "taskbar"; label: "Taskleiste" }
                    }
                    delegate: Rectangle {
                        width: 120; height: 36; radius: 6
                        color: settingsMenu.weatherLocation === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
                        border.width: 1
                        border.color: settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            anchors.centerIn: parent
                            text: label
                            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                            font.pixelSize: 13
                        }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: settingsMenu.weatherLocation = value
                        }
                    }
                }
            }
        }

        // City search
        Column {
            width: parent.width
            spacing: 8

            Text {
                text: "Standort"
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            Row {
                width: parent.width
                spacing: 8

                TextField {
                    id: cityTextField
                    width: parent.width - 100
                    height: 36
                    text: settingsMenu.weatherCity
                    placeholderText: "Stadt oder PLZ eingeben…"
                    color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    placeholderTextColor: settingsMenu.darkMode ? "#666" : "#999"
                    font.pixelSize: 13
                    background: Rectangle {
                        radius: 6
                        color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"
                        border.color: cityTextField.activeFocus ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0")
                        border.width: 1
                    }
                    leftPadding: 10; rightPadding: 10
                    Keys.onReturnPressed: geocodeCity()
                    onTextChanged: {
                        suggestionsModel.clear()
                        if (text.trim().length >= 2) geocodeDebounce.restart()
                        else geocodeDebounce.stop()
                    }
                }

                Rectangle {
                    width: 88; height: 36; radius: 6
                    color: geocodeMouse.containsMouse ? settingsMenu.accentColor
                                                     : (settingsMenu.darkMode ? "#2a2a2a" : "#e0e0e0")
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        anchors.centerIn: parent
                        text: geocodeRunning ? "…" : "Suchen"
                        font.pixelSize: 13
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                    }
                    MouseArea {
                        id: geocodeMouse
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: geocodeCity()
                    }
                }
            }

            // Autocomplete suggestions
            ListView {
                id: suggestionsList
                width: parent.width
                height: suggestionsModel.count > 0 ? Math.min(suggestionsModel.count * 40, 200) : 0
                clip: true
                model: suggestionsModel
                delegate: Rectangle {
                    width: suggestionsList.width
                    height: 40
                    color: suggestMa.containsMouse ? settingsMenu.accentColor
                                                   : (settingsMenu.darkMode ? "#222" : "#e8e8e8")
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        text: displayText
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 10
                        anchors.right: parent.right; anchors.rightMargin: 10
                        color: suggestMa.containsMouse ? "#fff" : (settingsMenu.darkMode ? "#ddd" : "#1a1a1a")
                        font.pixelSize: 13
                        elide: Text.ElideRight
                    }
                    MouseArea {
                        id: suggestMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            settingsMenu.weatherCity = cityName
                            settingsMenu.weatherLatitude = lat
                            settingsMenu.weatherLongitude = lon
                            cityTextField.text = cityName
                            geocodeStatus.text = "✓ " + displayText
                            geocodeStatus.color = "#4caf50"
                            suggestionsModel.clear()
                        }
                    }
                }
            }

            // Status text
            ProjectIcon { name: "location"; color: settingsMenu.darkMode ? "#aaa" : "#555" }
            Text {
                id: geocodeStatus
                width: parent.width
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                color: settingsMenu.darkMode ? "#888" : "#666"
                text: settingsMenu.weatherLatitude !== 0
                    ? settingsMenu.weatherCity + "  (" + settingsMenu.weatherLatitude.toFixed(2) + "°, " + settingsMenu.weatherLongitude.toFixed(2) + "°)"
                    : "Noch kein Standort gesetzt"
            }
        }
    }

    // Startmenü Sidebar
    Column {
        width: parent.width
        spacing: 14

        Text {
            text: "Startmenü Sidebar"
            font.pixelSize: 18; font.bold: true
            color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        }

        // Sidebar Position
        Column {
            width: parent.width
            spacing: 8

            Text {
                text: "Position"
                font.pixelSize: 14
                color: settingsMenu.darkMode ? "#aaa" : "#555"
            }

            Row {
                spacing: 10
                Repeater {
                    model: ListModel {
                        ListElement { value: "left";   labelKey: "appearance.left" }
                        ListElement { value: "right";  labelKey: "appearance.right" }
                        ListElement { value: "hidden"; labelKey: "common.off" }
                    }
                    delegate: Rectangle {
                        width: 100; height: 40; radius: 6
                        color: settingsMenu.startMenuSidebarPosition === value ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
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
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: settingsMenu.startMenuSidebarPosition = value
                        }
                    }
                }
            }
        }

        // Sidebar item toggles
        Text {
            text: "Sichtbare Links"
            font.pixelSize: 14
            color: settingsMenu.darkMode ? "#aaa" : "#555"
        }

        Repeater {
            model: ListModel {
                ListElement { label: "Alle Apps";     propName: "startMenuShowAllApps" }
                ListElement { label: "Personalisiert"; propName: "startMenuShowPersonalized" }
                ListElement { label: "Desktop";        propName: "startMenuShowDesktop" }
                ListElement { label: "Dokumente";      propName: "startMenuShowDocuments" }
                ListElement { label: "Downloads";      propName: "startMenuShowDownloads" }
                ListElement { label: "Bilder";         propName: "startMenuShowPictures" }
                ListElement { label: "Musik";          propName: "startMenuShowMusic" }
                ListElement { label: "Videos";         propName: "startMenuShowVideos" }
            }
            delegate: Row {
                width: parent.width
                spacing: 15

                Text {
                    text: label
                    font.pixelSize: 14
                    color: settingsMenu.darkMode ? "#aaa" : "#555"
                    width: parent.width - 80
                    anchors.verticalCenter: parent.verticalCenter
                }

                Rectangle {
                    property bool isOn: settingsMenu[propName]
                    width: 60; height: 32; radius: 16
                    color: isOn ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#c0c0c0")
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 150 } }
                    Rectangle {
                        width: 24; height: 24; radius: 12
                        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
                        x: parent.isOn ? parent.width - width - 4 : 4
                        anchors.verticalCenter: parent.verticalCenter
                        Behavior on x { NumberAnimation { duration: 150 } }
                    }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: settingsMenu[propName] = !settingsMenu[propName]
                    }
                }
            }
        }
    }

}
