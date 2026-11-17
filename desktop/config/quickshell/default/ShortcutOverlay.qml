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
        if (visible) { bindings.reload(); markViewed.running = true; Qt.callLater(function() { search.forceActiveFocus() }) }
    }
    // opening the overlay ticks "look at the shortcuts" in the welcome checklist
    Process { id: markViewed; command: ["windoesnot-welcome-state", "view", "true"] }
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
    // "SUPER + Q" becomes [Win, Q]: one key cap per key, readable names instead of raw Hyprland identifiers
    function keycaps(raw) {
        var german = root.settingsMenu.uiLanguage === "de"
        var names = {
            "SUPER": "Win", "CTRL": german ? "Strg" : "Ctrl", "ALT": "Alt", "SHIFT": german ? "Umschalt" : "Shift",
            "PRINT": german ? "Druck" : "Print", "Escape": "Esc", "Delete": german ? "Entf" : "Del", "Return": german ? "Eingabe" : "Enter",
            "mouse:272": german ? "Linke Maustaste" : "Left button", "mouse:273": german ? "Rechte Maustaste" : "Right button",
            "mouse_down": german ? "Mausrad ↓" : "Wheel ↓", "mouse_up": german ? "Mausrad ↑" : "Wheel ↑",
            "XF86AudioRaiseVolume": german ? "Lauter" : "Volume up", "XF86AudioLowerVolume": german ? "Leiser" : "Volume down",
            "XF86AudioMute": german ? "Stumm" : "Mute", "XF86AudioMicMute": german ? "Mikro aus" : "Mic mute",
            "XF86MonBrightnessUp": german ? "Heller" : "Brighter", "XF86MonBrightnessDown": german ? "Dunkler" : "Darker",
            "XF86AudioNext": german ? "Nächster Titel" : "Next track", "XF86AudioPrev": german ? "Vorheriger Titel" : "Previous track",
            "XF86AudioPause": german ? "Pause" : "Pause", "XF86AudioPlay": german ? "Wiedergabe" : "Play"
        }
        return String(raw).split(" + ").map(function(part) {
            var key = part.trim()
            if (names[key]) return names[key]
            return key.length === 1 ? key.toUpperCase() : key
        })
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
                Item {
                    id: closeButton
                    width: 32; height: 32
                    Accessible.role: Accessible.Button
                    Accessible.name: Lang.get("shortcuts.close", root.settingsMenu.uiLanguage)
                    Rectangle {
                        anchors.fill: parent; radius: 8
                        color: closeArea.containsMouse ? (root.settingsMenu.darkMode ? "#3a3e42" : "#e2e2e2") : "transparent"
                    }
                    // two strokes instead of a text glyph: crisp at every scale and centred
                    Rectangle { anchors.centerIn: parent; width: 14; height: 2; radius: 1; rotation: 45; color: root.settingsMenu.darkMode ? "#d8d8d8" : "#333333" }
                    Rectangle { anchors.centerIn: parent; width: 14; height: 2; radius: 1; rotation: -45; color: root.settingsMenu.darkMode ? "#d8d8d8" : "#333333" }
                    MouseArea { id: closeArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.visible = false }
                }
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
                                    bottomPadding: 6
                                    Flow {
                                        width: 230; spacing: 5
                                        Repeater {
                                            model: root.keycaps(parent.parent.modelData.keys)
                                            delegate: Row {
                                                required property int index
                                                required property string modelData
                                                spacing: 5
                                                Text { visible: index > 0; text: "+"; color: root.settingsMenu.darkMode ? "#8a8f94" : "#8a8a8a"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                                Item {
                                                    width: capLabel.implicitWidth + 18; height: 26
                                                    // darker underlay offset by 2 px gives the key its raised edge
                                                    Rectangle { x: 0; y: 2; width: parent.width; height: 24; radius: 6; color: root.settingsMenu.darkMode ? "#101214" : "#bdbdbd" }
                                                    Rectangle {
                                                        x: 0; y: 0; width: parent.width; height: 24; radius: 6
                                                        color: root.settingsMenu.darkMode ? "#33373b" : "#ffffff"
                                                        border.width: 1; border.color: root.settingsMenu.darkMode ? "#4b5157" : "#d2d2d2"
                                                        Text { id: capLabel; anchors.centerIn: parent; text: modelData; font.pixelSize: 12; font.bold: true; color: root.settingsMenu.darkMode ? "#f1f1f1" : "#202020" }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    Text { width: parent.width - 242; anchors.verticalCenter: undefined; text: parent.modelData.description; color: root.settingsMenu.darkMode ? "#eeeeee" : "#222222"; wrapMode: Text.WrapAnywhere; topPadding: 4 }
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
