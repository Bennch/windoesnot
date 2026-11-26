pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Theme of the capture overlay: follows the desktop design scheme.
// Reads accentColor, borderRadius and darkMode from the same settings.txt the shell uses
// (~/.config/quickshell/default/settings.txt); defaults are the shell's own (Settings.qml).
// The overlay is started on demand, so the file is read each time it opens.
Singleton {
    id: root

    readonly property string defaultAccent: "#FE6F2D"   // Settings.qml accentColor
    property color accentColor: defaultAccent
    property int borderRadius: 10                       // Settings.qml borderRadius
    property bool darkMode: true                        // Settings.qml darkMode

    // Derived colours
    readonly property color panel: darkMode ? "#f2252528" : "#f2f6f7f9"
    readonly property color panelBorder: darkMode ? "#4a4a50" : "#c9ccd2"
    readonly property color text: darkMode ? "#f2f2f4" : "#1b1b1f"
    readonly property color mutedText: darkMode ? "#b5b5ba" : "#55555c"
    readonly property color hover: darkMode ? "#26ffffff" : "#1f000000"
    readonly property color separator: darkMode ? "#3cffffff" : "#26000000"
    readonly property color dim: "#99000000"
    readonly property color danger: "#e5484d"
    // Text on top of the accent colour: dark on light accents, white on dark ones.
    readonly property color onAccent: (accentColor.r * 0.299 + accentColor.g * 0.587 + accentColor.b * 0.114) > 0.6 ? "#1b1b1f" : "#ffffff"

    function parseSettings(text) {
        var lines = (text || "").split("\n")
        var accent = defaultAccent
        var dark = true
        var radius = 10
        for (var i = 0; i < lines.length; ++i) {
            var idx = lines[i].indexOf("=")
            if (idx < 0)
                continue
            var key = lines[i].substring(0, idx).trim()
            var value = lines[i].substring(idx + 1).trim()
            if (key === "accentColor" && /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value))
                accent = value
            else if (key === "darkMode")
                dark = value !== "false"
            else if (key === "borderRadius" && /^\d+$/.test(value))
                radius = Math.min(40, parseInt(value))
        }
        root.accentColor = accent
        root.darkMode = dark
        root.borderRadius = radius
        console.log("[capture] theme accent=" + accent + " radius=" + radius + " dark=" + dark)
    }

    FileView {
        id: settingsFile
        path: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/quickshell/default/settings.txt"
        onLoaded: root.parseSettings(text())
        onLoadFailed: root.parseSettings("")
    }
}
