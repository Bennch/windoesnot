import QtQuick
import Quickshell
import Quickshell.Io

// Icon component with intelligent fallback handling
Image {
    id: root

    property string iconName: ""
    property bool isCustomIcon: false
    property string fallbackIcon: appReplace ? appReplace.fallbackIcon : "img/console.svg"
    property int fallbackAttempt: 0
    property var iconCandidates: []

    // List of known broken/generic icon names that should use fallback
    property var brokenIconNames: [
        "network-wired",
        "preferences-desktop-theme",
        "/usr/share/icons/Humanity/devices/48/printer.svg",
        "printer",
        "protontricks.png",
        "utilities-terminal",
        "network-server",
        "preferences-system-network",
        "preferences-system-network-server-share",
        "avahi",
        "applications-system",
        "applications-system-symbolic"
    ]

    // Apps whose .desktop icon ships in no installed theme: use a close stand-in
    property var iconAliases: ({
        "eog": ["org.gnome.Loupe", "image-x-generic"],
        "org.gnome.eog": ["org.gnome.Loupe", "image-x-generic"],
        "hwloc": ["cpu", "computer"],
        "lstopo": ["cpu", "computer"]
    })

    // First candidate the icon theme really has; the "icon" provider would
    // otherwise answer with a magenta placeholder instead of an error.
    function resolveIcon(name) {
        var candidates = generateCandidates(name).concat(iconAliases[name] || []);
        for (var i = 0; i < candidates.length; i++) {
            var found = Quickshell.iconPath(candidates[i], true);
            if (found !== "")
                return found;
        }
        return "";
    }

    // Generate fallback candidates for an icon name
    function generateCandidates(name) {
        var candidates = [name];

        // For dotted names (org.foo.Bar), try variations
        if (name.indexOf(".") > -1) {
            var parts = name.split(".");
            var lastPart = parts[parts.length - 1];
            candidates.push(lastPart);  // org.foo.Bar -> Bar
            candidates.push(lastPart.toLowerCase());  // org.foo.Bar -> bar

            // Try without first segment: com.foo.bar -> foo.bar
            if (parts.length > 2) {
                candidates.push(parts.slice(1).join("."));
            }
        }

        return candidates;
    }

    source: {
        if (isCustomIcon) {
            return iconName
        }

        // Check if in broken icons list
        for (var i = 0; i < brokenIconNames.length; i++) {
            if (iconName === brokenIconNames[i]) {
                return fallbackIcon
            }
        }

        if (iconName.startsWith("img/") || iconName.startsWith("/")) {
            return iconName
        }

        // Try primary icon name first, with fallback candidates
        iconCandidates = generateCandidates(iconName);
        fallbackAttempt = 0;

        var resolved = resolveIcon(iconName);
        return resolved !== "" ? resolved : fallbackIcon
    }

    // When image fails to load, try next candidate
    onStatusChanged: {
        // Try next candidate if available
        if (status === Image.Error && fallbackAttempt < iconCandidates.length - 1) {
            fallbackAttempt++;
            source = "image://icon/" + iconCandidates[fallbackAttempt];
        }
        // All candidates failed or status is Null/Error - use fallback
        else if ((status === Image.Error || status === Image.Null) && fallbackAttempt >= iconCandidates.length - 1) {
            if (!source.toString().startsWith("img/") && !source.toString().startsWith("/")) {
                source = fallbackIcon;
            }
        }
    }

    // Request appropriate icon size (64x64 should be available in most themes)
    sourceSize: Qt.size(64, 64)

    asynchronous: true
    smooth: true
    antialiasing: true
    mipmap: true
    fillMode: Image.PreserveAspectFit
    layer.enabled: true
    layer.smooth: true
}
