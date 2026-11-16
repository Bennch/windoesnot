import "../i18n/Lang.js" as Lang
import QtQuick
import Quickshell.Io
import "LookData.js" as Presets

Column {
    id: root

    property var settingsMenu
    property string lang: settingsMenu ? settingsMenu.uiLanguage : "de"
    property var pendingLook: null
    property bool restoring: false
    property string errorText: ""

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
        presetProcess.command = ["python3", helperPath(), "apply", JSON.stringify(old), "/usr/share/backgrounds/windoesnot/" + look.wallpaper];
        presetProcess.running = true;
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
            model: Presets.looks

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
                    text: root.lang === "de" ? modelData.nameDe : modelData.nameEn
                    color: modelData.darkMode ? "#fff" : "#1a1a1a"
                    font.pixelSize: 12
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
