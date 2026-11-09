pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io

// WinDoesNot branding: follows the desktop design scheme live.
// Reads accentColor, darkMode and borderRadius from the same settings.txt the
// rest of the shell uses (~/.config/quickshell/default/settings.txt). The file
// is watched (inotify) and additionally re-read by a slow timer as a safety
// net, because Settings may replace the file instead of writing it in place.
Singleton {
    id: root

    // Defaults (used until/unless the file provides a valid value)
    readonly property string defaultAccent: "#FE6F2D"

    property color accentColor: defaultAccent
    property bool darkMode: true
    property int borderRadius: 6
    property color inactiveBorderColor: "#3a3a3a"
    property bool loaded: false

    function parseSettings(text) {
        const lines = (text || "").split("\n");
        let accent = defaultAccent;
        let dark = true;
        let radius = 6;
        let inactive = "#3a3a3a";
        for (const raw of lines) {
            const idx = raw.indexOf("=");
            if (idx < 0)
                continue;
            const key = raw.substring(0, idx).trim();
            const value = raw.substring(idx + 1).trim();
            if (key === "accentColor" && /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value))
                accent = value;
            else if (key === "darkMode")
                dark = value !== "false";
            else if (key === "borderRadius" && /^\d+$/.test(value))
                radius = Math.min(40, parseInt(value));
            else if (key === "inactiveBorderColor" && /^#[0-9a-fA-F]{6}$/.test(value))
                inactive = value;
        }
        // property setters only notify on real changes
        root.accentColor = accent;
        root.darkMode = dark;
        root.borderRadius = radius;
        root.inactiveBorderColor = inactive;
        root.loaded = true;
    }

    FileView {
        id: settingsFile
        path: `${Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")}/quickshell/default/settings.txt`
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.parseSettings(text())
        onLoadFailed: root.parseSettings("")
    }

    Timer {
        interval: 2000
        running: true
        repeat: true
        onTriggered: settingsFile.reload()
    }
}
