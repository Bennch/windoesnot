import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "i18n/Lang.js" as Lang

FloatingWindow {
    id: root
    property var settingsMenu
    property var panelWindow
    property var entries: []
    title: "quickshell-shortcuts"
    implicitWidth: 650
    implicitHeight: 600
    color: "transparent"
    visible: false
    onVisibleChanged: {
        panelWindow.syncFocusGrab(grab, visible)
        if (visible) { bindings.reload(); Qt.callLater(function() { search.forceActiveFocus() }) }
    }
    Shortcut { sequence: "Escape"; onActivated: root.visible = false }
    HyprlandFocusGrab {
        id: grab
        windows: [root]
        onCleared: root.visible = false
    }
    FileView {
        id: bindings
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/hypr/lua/bindings.lua"
        onLoaded: root.parseBindings(text())
    }
    function parseBindings(source) {
        var result = []
        var lines = source.split("\n")
        for (var i = 0; i < lines.length; ++i) {
            var match = lines[i].match(/^\s*hl\.bind\("([^"]+)",\s*hl\.dsp\.([^\(]+)\((.*)/)
            if (!match) continue
            var key = match[1], action = match[2], detail = match[3]
            var group = "system"
            if (action.indexOf("window.") === 0 || action === "focus" || action === "layout" || key.indexOf("Tab") >= 0 || key.indexOf("TAB") >= 0) group = "windows"
            else if (key.indexOf("PRINT") >= 0 || key.indexOf("Brightness") >= 0) group = "screen"
            else if (action === "exec_cmd" || action === "global") group = "apps"
            var description = action
            var cmd = detail.match(/^"([^\"]*)"/)
            if (cmd) description = cmd[1]
            else {
                var workspace = detail.match(/\["workspace"\]="([^"]+)"/)
                var direction = detail.match(/\["direction"\]="([^"]+)"/)
                if (workspace) description += " " + workspace[1]
                if (direction) description += " " + direction[1]
            }
            var labels = {
                "SUPER + Q": "terminal", "SUPER + C": "closeWindow", "SUPER + M": "logout",
                "SUPER + E": "files", "SUPER + V": "floating", "SUPER + R": "start",
                "CTRL + ALT + Delete": "monitor", "CTRL + SHIFT + Escape": "monitor",
                "SUPER + I": "settings", "SUPER + L": "lock", "SUPER + S": "searchAction",
                "SUPER + H": "desktop", "SUPER + D": "desktop", "SUPER + N": "notifications",
                "SUPER + P": "picker", "SUPER + F": "fullscreen", "SUPER + J": "split",
                "PRINT": "screenshot", "SUPER + PRINT": "screenshot", "SUPER + F12": "gameFix",
                "SUPER + F11": "tileFix", "SUPER + TAB": "overview", "SUPER + Z": "snap",
                "ALT + Tab": "nextWindow", "ALT + SHIFT + Tab": "previousWindow",
                "SUPER + mouse:272": "drag", "SUPER + mouse:273": "resize",
                "SUPER + mouse_down": "nextWorkspace", "SUPER + mouse_up": "previousWorkspace",
                "XF86AudioRaiseVolume": "volumeUp", "XF86AudioLowerVolume": "volumeDown",
                "XF86AudioMute": "mute", "XF86AudioMicMute": "micMute",
                "XF86MonBrightnessUp": "brightnessUp", "XF86MonBrightnessDown": "brightnessDown",
                "XF86AudioNext": "nextTrack", "XF86AudioPrev": "previousTrack",
                "XF86AudioPause": "playPause", "XF86AudioPlay": "playPause", "SUPER + F1": "title"
            }
            if (labels[key]) description = Lang.get("shortcuts." + labels[key], settingsMenu.uiLanguage)
            else if (action === "focus" && workspace) description = Lang.get("shortcuts.workspace", settingsMenu.uiLanguage) + " " + workspace[1]
            else if (action === "window.move" && workspace) description = Lang.get("shortcuts.moveWorkspace", settingsMenu.uiLanguage) + " " + workspace[1]
            else if (action === "focus" && direction) description = Lang.get("shortcuts.focus", settingsMenu.uiLanguage) + " " + Lang.get("shortcuts." + direction[1], settingsMenu.uiLanguage)
            result.push({ keys: key, group: group, description: description })
        }
        root.entries = result
    }
    Rectangle {
        anchors.fill: parent
        radius: root.settingsMenu.borderRadius
        color: root.settingsMenu.darkMode ? "#202020" : "#f3f3f3"
        border.color: root.settingsMenu.darkMode ? "#555555" : "#cccccc"
        Column {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12
            Row {
                width: parent.width
                Text { width: parent.width - closeButton.width; text: Lang.get("shortcuts.title", root.settingsMenu.uiLanguage); color: root.settingsMenu.darkMode ? "white" : "#202020"; font.pixelSize: 22; font.bold: true }
                Button { id: closeButton; text: "×"; Accessible.name: Lang.get("shortcuts.close", root.settingsMenu.uiLanguage); onClicked: root.visible = false }
            }
            TextField {
                id: search
                width: parent.width
                placeholderText: Lang.get("shortcuts.search", root.settingsMenu.uiLanguage)
                Accessible.name: placeholderText
                Keys.onEscapePressed: root.visible = false
            }
            ScrollView {
                width: parent.width
                height: parent.height - y
                clip: true
                contentWidth: availableWidth
                Column {
                    width: parent.width
                    Repeater {
                        model: ["windows", "apps", "system", "screen"]
                        delegate: Column {
                            required property string modelData
                            width: parent.width
                            property var filtered: root.entries.filter(function(e) { var q = search.text.toLowerCase(); return e.group === modelData && (e.keys + " " + e.description + " " + Lang.get("shortcuts." + e.group, root.settingsMenu.uiLanguage)).toLowerCase().indexOf(q) >= 0 })
                            visible: filtered.length > 0
                            Text { text: Lang.get("shortcuts." + parent.modelData, root.settingsMenu.uiLanguage); color: root.settingsMenu.accentColor; font.pixelSize: 16; font.bold: true; topPadding: 12; bottomPadding: 6 }
                            Repeater {
                                model: parent.filtered
                                delegate: Row {
                                    required property var modelData
                                    width: parent.width
                                    spacing: 12
                                    Text { width: 180; text: parent.modelData.keys; color: root.settingsMenu.accentColor; font.bold: true; wrapMode: Text.Wrap }
                                    Text { width: parent.width - 192; text: parent.modelData.description; color: root.settingsMenu.darkMode ? "#eeeeee" : "#222222"; wrapMode: Text.WrapAnywhere }
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: modelData.keys + ": " + modelData.description
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
