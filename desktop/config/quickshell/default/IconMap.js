// Neutral bootstrap; generate-icon-map.sh fills this user-owned runtime cache.
.pragma library
var MAP = {};

/**
 * Convert CamelCase to kebab-case
 * @param {string} str - The string to convert
 * @returns {string} - kebab-case version
 */
function camelToKebab(str) {
    return str.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
}

/**
 * Fix icon name using the mapping table
 * @param {string} name - The icon/class name to fix
 * @returns {string} - The corrected icon name or original if no mapping exists
 */
function fix(name) {
    if (!name || typeof name !== "string")
        return "";
    var key = name.toLowerCase();
    return MAP[key] || name;   // Fallback: original name
}

/**
 * Smart fix that also tries capitalization heuristics
 * @param {string} name - The icon/class name to fix
 * @returns {string} - The corrected icon name
 */
function smartFix(name) {
    if (!name || typeof name !== "string")
        return "";

    var out = fix(name);
    if (out !== name) return out;

    // Try CamelCase to kebab-case conversion (balenaEtcher -> balena-etcher)
    var kebab = camelToKebab(name);
    if (kebab !== name.toLowerCase()) {
        var kebabFixed = fix(kebab);
        if (kebabFixed !== kebab) return kebabFixed;
        // Try to find the icon directly
        return kebab;
    }

    // If name is just a single capitalized word (like "Audacity"), use lowercase
    if (name !== name.toLowerCase() && name.indexOf(".") === -1 && name.indexOf("-") === -1 && name.indexOf("_") === -1) {
        var lower = name.toLowerCase();
        var lowerFixed = fix(lower);
        if (lowerFixed !== lower) return lowerFixed;
        return lower;
    }

    // Try underscore to dash conversion (some_app -> some-app)
    var dashed = name.replace(/_/g, '-');
    if (dashed !== name) {
        var dashedFixed = fix(dashed);
        if (dashedFixed !== dashed) return dashedFixed;
    }

    // Heuristic: capitalize last segment (foo.bar.baz -> foo.bar.Baz)
    var parts = name.split(".");
    if (parts.length > 1) {
        var last = parts.pop();
        if (last.length > 0) {
            var guess = parts.join(".") + "." + last[0].toUpperCase() + last.slice(1);
            // Check if this guess exists in MAP (lowercase key)
            var m2 = MAP[guess.toLowerCase()];
            if (m2 && m2 !== guess) return m2;

            // Also try PascalCase for kebab-case last segment (system-monitor -> SystemMonitor)
            if (last.indexOf("-") !== -1) {
                var pascal = last.split("-").map(function(w) {
                    return w.length > 0 ? w[0].toUpperCase() + w.slice(1) : "";
                }).join("");
                var guessPascal = parts.join(".") + "." + pascal;
                var m3 = MAP[guessPascal.toLowerCase()];
                if (m3) return m3;
                return guessPascal;  // Trust the theme to find it (e.g. org.gnome.SystemMonitor)
            }
        }
        // Keep the original dotted name (Qt with gtk3 platform theme can find it)
        return name;
    }
    return name.toLowerCase();
}
