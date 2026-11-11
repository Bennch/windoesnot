#!/bin/bash

# Script to generate icon name mapping from .desktop files
# This maps application class names to their correct icon names

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/default"
mkdir -p -- "$CONFIG_DIR" || exit 1
WORK_DIR=$(mktemp -d -- "$CONFIG_DIR/.icon-map.XXXXXXXX") || exit 1
trap 'rm -rf -- "$WORK_DIR"' EXIT
OUTPUT_FILE="$WORK_DIR/icon-map.json"
JS_OUTPUT_FILE="$WORK_DIR/IconMap.js"

echo "Scanning desktop files for icon mappings..."

# Collect all mappings first
declare -A mappings

# Search directories for .desktop files
for dir in /usr/share/applications /var/lib/flatpak/exports/share/applications ~/.local/share/applications; do
    if [ ! -d "$dir" ]; then
        continue
    fi

    find "$dir" -maxdepth 1 -name "*.desktop" 2>/dev/null | while read -r desktop_file; do
        # Extract the base name without .desktop
        basename=$(basename "$desktop_file" .desktop)

        # Extract Icon= line
        icon=$(grep "^Icon=" "$desktop_file" | head -1 | cut -d'=' -f2)

        # Skip if no icon found
        if [ -z "$icon" ]; then
            continue
        fi

        # Skip if icon is a full path (we only want icon names)
        if [[ "$icon" == /* ]]; then
            continue
        fi

        # Create lowercase version for key
        key=$(echo "$basename" | tr '[:upper:]' '[:lower:]')

        # Only add if key and icon differ
        if [ "$key" != "$icon" ]; then
            # Escape quotes and backslashes
            icon_escaped=$(echo "$icon" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
            key_escaped=$(echo "$key" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
            echo "  \"$key_escaped\": \"$icon_escaped\""
        fi
    done
done | sort -u > "$WORK_DIR/mappings.tmp"

# Build proper JSON
echo "{" > "$OUTPUT_FILE"
total_lines=$(wc -l < "$WORK_DIR/mappings.tmp")
line_num=0

while IFS= read -r line; do
    line_num=$((line_num + 1))
    if [ "$line_num" -lt "$total_lines" ]; then
        echo "$line," >> "$OUTPUT_FILE"
    else
        echo "$line" >> "$OUTPUT_FILE"
    fi
done < "$WORK_DIR/mappings.tmp"

echo "}" >> "$OUTPUT_FILE"

rm -f "$WORK_DIR/mappings.tmp"

echo "Icon mapping generated at: $OUTPUT_FILE"
echo "Total mappings: $((total_lines))"

# Generate JS Library file
echo "Generating JavaScript library..."
{
  echo "// Auto-generated icon mapping library"
  echo "// DO NOT EDIT MANUALLY - regenerate with generate-icon-map.sh"
  echo ".pragma library"
  echo ""
  echo "// Icon name mappings (lowercase key -> correct icon name)"
  echo "var MAP = "
  cat "$OUTPUT_FILE"
  echo ";"
  echo ""
  cat <<'EOF'
/**
 * Convert CamelCase to kebab-case
 * @param {string} str - The string to convert
 * @returns {string} - kebab-case version
 */
function camelToKebab(str) {
    return str.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
}

EOF
  cat <<'EOF'
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
EOF
} > "$JS_OUTPUT_FILE"

# Quickshell can import this library while the generator runs. Publish only
# complete files with same-filesystem renames; keep the last good map on failure.
if ! python3 -m json.tool "$OUTPUT_FILE" >/dev/null; then
    echo "Invalid icon map; keeping the previous files" >&2
    exit 1
fi
chmod 600 "$OUTPUT_FILE" "$JS_OUTPUT_FILE" || exit 1
mv -f -- "$OUTPUT_FILE" "$CONFIG_DIR/icon-map.json" || exit 1
mv -f -- "$JS_OUTPUT_FILE" "$CONFIG_DIR/IconMap.js" || exit 1

echo "JavaScript library published at: $CONFIG_DIR/IconMap.js"
