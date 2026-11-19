import "../i18n/Lang.js" as Lang
import QtQuick
import QtQuick.Controls
import Quickshell.Io
import "LookData.js" as Presets

Column {
    id: root

    property var settingsMenu
    property string lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    property var pendingLook: null
    property bool restoring: false
    property string errorText: ""
    // Looks saved by the user (name, dark/light, accent colour, corner radius, wallpaper).
    property var userLooks: []
    property string newName: ""

    function helperPath() {
        return Qt.resolvedUrl("theme-presets.py").toString().replace(/^file:\/\//, "");
    }

    function applyLook(look) {
        pendingLook = look;
        restoring = false;
        errorText = "";
        var old = {
            "darkMode": settingsMenu.darkMode,
            "accentColor": settingsMenu.accentColor.toString(),
            "borderRadius": settingsMenu.borderRadius
        };
        presetProcess.command = ["python3", helperPath(), "apply", JSON.stringify(old), look.wallpaperPath !== undefined ? look.wallpaperPath : "/usr/share/backgrounds/windoesnot/" + look.wallpaper];
        presetProcess.running = true;
    }

    function saveCurrent() {
        var name = newName.trim();
        if (name === "" || libraryProcess.running) return;
        errorText = "";
        libraryProcess.command = ["python3", helperPath(), "save", name, JSON.stringify({
            "darkMode": settingsMenu.darkMode,
            "accentColor": settingsMenu.accentColor.toString(),
            "borderRadius": settingsMenu.borderRadius
        })];
        libraryProcess.running = true;
        newName = "";
    }

    function applyValues(values) {
        // Batch persistence; then run the same live updates as the individual controls.
        settingsMenu.isLoadingSettings = true;
        settingsMenu.darkMode = values.darkMode;
        settingsMenu.accentColor = values.accentColor;
        settingsMenu.borderRadius = values.borderRadius;
        settingsMenu.isLoadingSettings = false;
        settingsMenu.saveSettings();
        settingsMenu.updateHyprlandBorders();
        settingsMenu.updateHyprlandAppearance();
        settingsMenu.updateGtkAccentCss();
        settingsMenu.gtkTheme = values.darkMode ? settingsMenu.gtkThemeDark : settingsMenu.gtkThemeLight;
        settingsMenu.updateGtkColorScheme();
        settingsMenu.updateGtkSettingsIni();
        settingsMenu.updateGhosttyColors();
        settingsMenu.updateHyprbarsColors();
        settingsMenu.updateSwayncStyle();
        settingsMenu.updateSnappySwitcherTheme();
        settingsMenu.reloadPresetWallpapers();
    }

    width: parent.width
    spacing: 12

    Text {
        text: Lang.get("looks.title", root.lang)
        color: settingsMenu.darkMode ? "#fff" : "#1a1a1a"
        font.pixelSize: 18
        font.bold: true
    }

    Flow {
        width: parent.width
        spacing: 10

        Repeater {
            model: Presets.looks.concat(root.userLooks)

            delegate: Rectangle {
                width: 125
                height: 86
                radius: 8
                color: modelData.darkMode ? "#25252b" : "#f0f0f0"
                border.color: modelData.accentColor
                border.width: 2

                Rectangle {
                    x: 10
                    y: 10
                    width: 105
                    height: 28
                    radius: Math.min(modelData.borderRadius, 14)
                    color: modelData.accentColor
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 10
                    width: parent.width - 16
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: modelData.name !== undefined ? modelData.name : (root.lang === "de" ? modelData.nameDe : modelData.nameEn)
                    color: modelData.darkMode ? "#fff" : "#1a1a1a"
                    font.pixelSize: 12
                }

                // Own looks can be removed again.
                Text {
                    visible: modelData.name !== undefined
                    anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 6
                    text: "✕"; color: modelData.darkMode ? "#cccccc" : "#444444"; font.pixelSize: 12
                    MouseArea {
                        anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                        onClicked: { libraryProcess.command = ["python3", root.helperPath(), "delete", modelData.name]; libraryProcess.running = true }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !presetProcess.running && !settingsMenu.isLoadingSettings
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.applyLook(modelData)
                }

            }

        }

    }

    // Save what is set right now as a look of your own.
    Row {
        spacing: 8
        TextField {
            width: 220; height: 36; maximumLength: 40; selectByMouse: true
            placeholderText: Lang.get("looks.namePlaceholder", root.lang)
            text: root.newName
            onTextEdited: root.newName = text
            onAccepted: root.saveCurrent()
            color: settingsMenu.darkMode ? "#ffffff" : "#1a1a1a"; font.pixelSize: 13
            background: Rectangle { radius: 6; color: settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0"; border.width: 1; border.color: parent.activeFocus ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#3a3a3a" : "#d0d0d0") }
        }
        Rectangle {
            width: saveText.width + 28; height: 36; radius: 6
            color: root.newName.trim() !== "" ? settingsMenu.accentColor : (settingsMenu.darkMode ? "#2a2a2a" : "#f0f0f0")
            opacity: root.newName.trim() !== "" ? 1 : 0.6
            Text { id: saveText; anchors.centerIn: parent; text: Lang.get("looks.saveCurrent", root.lang); font.pixelSize: 13; color: root.newName.trim() !== "" ? "#ffffff" : (settingsMenu.darkMode ? "#aaaaaa" : "#666666") }
            MouseArea { anchors.fill: parent; enabled: root.newName.trim() !== ""; cursorShape: Qt.PointingHandCursor; onClicked: root.saveCurrent() }
        }
    }
    Text {
        width: parent.width; wrapMode: Text.WordWrap
        text: Lang.get("looks.saveHint", root.lang)
        color: settingsMenu.darkMode ? "#888888" : "#777777"; font.pixelSize: 12
    }

    Text {
        text: Lang.get("looks.restore", root.lang)
        color: settingsMenu.accentColor
        font.pixelSize: 13
        opacity: presetProcess.running ? 0.5 : 1

        MouseArea {
            anchors.fill: parent
            enabled: !presetProcess.running && !settingsMenu.isLoadingSettings
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                root.restoring = true;
                root.errorText = "";
                presetProcess.command = ["python3", root.helperPath(), "restore"];
                presetProcess.running = true;
            }
        }

    }

    Text {
        visible: root.errorText !== ""
        text: root.errorText
        color: "#d05050"
        font.pixelSize: 12
    }

    // Reads the saved looks when the page opens; save and delete answer with the new list.
    Process {
        id: libraryProcess
        command: ["python3", root.helperPath(), "list"]
        running: true
        stdout: StdioCollector {
            id: libraryOutput
            onStreamFinished: { try { root.userLooks = JSON.parse(libraryOutput.text) } catch (e) {} }
        }
    }

    Process {
        id: presetProcess

        onExited: function(code) {
            if (code !== 0) {
                root.errorText = Lang.get("looks.error", root.lang);
                console.warn("Theme preset:", presetError.text);
                return ;
            }
            try {
                root.applyValues(root.restoring ? JSON.parse(presetOutput.text) : root.pendingLook);
            } catch (e) {
                root.errorText = Lang.get("looks.error", root.lang);
                console.warn("Theme preset:", e);
            }
        }

        stdout: StdioCollector {
            id: presetOutput
        }

        stderr: StdioCollector {
            id: presetError
        }

    }

}
