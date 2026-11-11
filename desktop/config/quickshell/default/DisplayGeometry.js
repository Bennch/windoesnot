.pragma library

// Hyprland reports physical modes; window/cursor coordinates use logical pixels.
// reserved is [left, top, right, bottom], already in logical pixels.
function normalize(monitor) {
    var m = Object.assign({}, monitor)
    var rotated = (Number(m.transform || 0) % 2) !== 0
    var scale = Math.max(0.25, Number(m.scale || 1))
    m.width = Math.round((rotated ? monitor.height : monitor.width) / scale)
    m.height = Math.round((rotated ? monitor.width : monitor.height) / scale)
    m.transform = 0
    m.scale = 1
    return m
}
