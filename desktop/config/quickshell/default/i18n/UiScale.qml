pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Text size of the desktop itself (Settings > Accessibility > Text size). Every font.pixelSize literal goes through px().
// The choice comes from windoesnot-accessibility; the settings page sets `factor` directly so a change shows at once.
Singleton {
    id: root
    property real factor: 1.0
    readonly property real maxFactor: 1.5   // fixed-size popups and the taskbar have room for this much
    function px(n) { return Math.round(n * Math.min(Math.max(factor, 1.0), maxFactor)) }

    Process {
        id: readProc
        command: ["windoesnot-accessibility", "get"]
        running: true
        stdout: StdioCollector { id: readOut }
        onExited: function(code) {
            try { var f = Number(JSON.parse(readOut.text).textScale); if (f >= 1.0 && f <= 2.0) root.factor = f } catch (e) {}
        }
    }
}
