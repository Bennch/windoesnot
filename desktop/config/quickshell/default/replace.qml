import QtQuick

QtObject {
    // App Overrides - Definiert Überschreibungen für Icons und Commands
    // Format: Key ist der App-Name aus der .desktop-Datei
    //         Value ist ein Objekt mit optionalen Eigenschaften: icon, cmd, customIcon

    // Fallback Icon für fehlende/fehlerhafte Icons
    // Wird automatisch von AppIcon.qml verwendet wenn ein Icon nicht geladen werden kann
    property string fallbackIcon: "img/console.svg"

    property var overrides: ({
        // Ghostty Console - Fixes GTK single-instance error und custom icon
        "Ghostty": {
            icon: "img/console.svg",
            cmd: "ghostty",
            customIcon: true
        },
        "Betterbird": {
            icon: "img/scalable/thunderbird.svg",
            cmd: "betterbird",
            customIcon: true
        },
        "Files": {
            icon: "img/folder.svg",
            cmd: "nautilus",
            customIcon: true
        },
        "Text Editor": {
            icon: "img/kate.svg",
            cmd: "gnome-text-editor",
            customIcon: true
        }
// Weitere Overrides können hier hinzugefügt werden:
        // "AppName": {
        //     icon: "img/custom-icon.svg",  // optional
        //     cmd: "custom-command",         // optional
        //     customIcon: true               // optional (default: false)
        // }
    })

    // Hilfsfunktion: Prüft ob eine App überschrieben werden soll
    function hasOverride(appName) {
        return overrides.hasOwnProperty(appName)
    }

    // Hilfsfunktion: Gibt die Überschreibungs-Daten zurück
    function getOverride(appName) {
        return overrides[appName] || null
    }

    // Hilfsfunktion: Wendet Override auf App-Daten an
    function applyOverride(appData) {
        var result = {
            name: appData.name,
            cmd: appData.cmd,
            icon: appData.icon,
            pinned: appData.pinned !== undefined ? appData.pinned : false,
            temporary: appData.temporary !== undefined ? appData.temporary : false,
            customIcon: appData.customIcon
        }

        // Explizite Overrides anwenden
        if (hasOverride(appData.name)) {
            var override = getOverride(appData.name)
            result.cmd = override.cmd !== undefined ? override.cmd : result.cmd
            result.icon = override.icon !== undefined ? override.icon : result.icon
            result.customIcon = override.customIcon !== undefined ? override.customIcon : result.customIcon
        }

        return result
    }
}
