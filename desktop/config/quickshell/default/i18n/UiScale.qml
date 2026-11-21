pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Text size of the desktop itself (Settings > Accessibility > Text size). Every font.pixelSize literal goes through px().
// The value comes from ~/.config/windoesnot/accessibility.json (written by windoesnot-accessibility); the file is watched, so
// a change from the settings page, the command line or another session shows at once. The settings page also sets `factor` directly.
Singleton {
    id: root
    property real factor: 1.0
    readonly property real maxFactor: 1.5   // fixed-size popups and the taskbar have room for this much
    function px(n) { return Math.round(n * Math.min(Math.max(factor, 1.0), maxFactor)) }

    function parse(text) {
        try { var f = Number(JSON.parse(text).textScale); if (f >= 1.0 && f <= 2.0) root.factor = f } catch (e) {}
    }

    // The file does not exist before the first choice is saved; FileView cannot watch a missing file, so look again until it appears.
    property bool fileKnown: false
    Timer { interval: 2000; repeat: true; running: !root.fileKnown; onTriggered: file.reload() }

    FileView {
        id: file
        path: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/windoesnot/accessibility.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: { root.fileKnown = true; root.parse(text()) }
        onLoadFailed: root.fileKnown = false
    }
}
