.pragma library

// Where a new floating window goes. The first window stays centred; the next ones step down and to the right (then up and to the
// left) by STEP pixels, so title bars stay visible and windows no longer hide each other exactly.
var STEP = 32
var MAX_STEPS = 5

// usable: {x, y, w, h} area of the monitor; width/height: size of the new window; others: [{x, y}] top-left corners of the floating
// windows already on that monitor and workspace.
function cascadePosition(usable, width, height, others) {
    var cx = usable.x + (usable.w - width) / 2
    var cy = usable.y + (usable.h - height) / 2
    var room = Math.max(0, Math.min((usable.w - width) / 2, (usable.h - height) / 2))
    var steps = Math.min(MAX_STEPS, Math.floor(room / STEP))
    var slots = [0]
    var k
    for (k = 1; k <= steps; k++) slots.push(k)
    for (k = 1; k <= steps; k++) slots.push(-k)
    function free(slot) {
        var x = cx + slot * STEP, y = cy + slot * STEP
        for (var i = 0; i < others.length; i++)
            if (Math.abs(others[i].x - x) < STEP / 2 && Math.abs(others[i].y - y) < STEP / 2) return false
        return true
    }
    var chosen = null
    for (var i = 0; i < slots.length && chosen === null; i++) if (free(slots[i])) chosen = slots[i]
    if (chosen === null) chosen = slots[others.length % slots.length]
    return { x: Math.round(cx + chosen * STEP), y: Math.round(cy + chosen * STEP) }
}

// The windows that count for the cascade: mapped, floating, visible clients on the same monitor and workspace as `client`
// (not the client itself, no shell surfaces, no fullscreen windows).
function neighbours(clients, client) {
    return clients.filter(function(c) {
        return c.address !== client.address && c.mapped !== false && !c.hidden && c.floating && !c.fullscreen
            && c.monitor === client.monitor && c.workspace && client.workspace && c.workspace.id === client.workspace.id
            && String(c.class || "").indexOf("quickshell") < 0 && String(c.title || "").indexOf("quickshell-") !== 0
    }).map(function(c) { return { x: c.at[0], y: c.at[1] } })
}


// Overlap-aware placement: look for a spot where the new window hides as little of the existing windows as possible (beside, above or
// below them, in the corners, in the centre), so windows of different size no longer sit exactly behind each other. If every spot would
// still cover more than half of the window, fall back to the cascade. others: [{x, y, w, h}].
var GAP = 16

function overlapArea(x, y, w, h, o) {
    var dx = Math.min(x + w, o.x + o.w) - Math.max(x, o.x)
    var dy = Math.min(y + h, o.y + o.h) - Math.max(y, o.y)
    return dx > 0 && dy > 0 ? dx * dy : 0
}

function placeWindow(usable, width, height, others) {
    if (!others || others.length === 0) return cascadePosition(usable, width, height, [])
    var minX = usable.x, maxX = usable.x + usable.w - width
    var minY = usable.y, maxY = usable.y + usable.h - height
    if (maxX < minX || maxY < minY) return cascadePosition(usable, width, height, others)
    var cx = usable.x + (usable.w - width) / 2, cy = usable.y + (usable.h - height) / 2
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }
    var xs = [cx, minX + GAP, maxX - GAP], ys = [cy, minY + GAP, maxY - GAP]
    others.forEach(function(o) {
        xs.push(o.x - width - GAP, o.x + o.w + GAP, o.x)
        ys.push(o.y - height - GAP, o.y + o.h + GAP, o.y)
    })
    xs = xs.map(function(v) { return clamp(v, minX, maxX) })
    ys = ys.map(function(v) { return clamp(v, minY, maxY) })
    var best = null, bestScore = Infinity, area = width * height
    xs.forEach(function(x) {
        ys.forEach(function(y) {
            var covered = 0
            others.forEach(function(o) { covered += overlapArea(x, y, width, height, o) })
            // overlap first, then how far from the centre (small tie-breaker)
            var score = covered + Math.hypot(x - cx, y - cy) * 50
            if (score < bestScore) { bestScore = score; best = { x: x, y: y, covered: covered } }
        })
    })
    if (best === null || best.covered > area / 2) return cascadePosition(usable, width, height, others)
    return { x: Math.round(best.x), y: Math.round(best.y) }
}

// Same filter as neighbours(), but with sizes
function neighbourRects(clients, client) {
    return clients.filter(function(c) {
        return c.address !== client.address && c.mapped !== false && !c.hidden && c.floating && !c.fullscreen
            && c.monitor === client.monitor && c.workspace && client.workspace && c.workspace.id === client.workspace.id
            && String(c.class || "").indexOf("quickshell") < 0 && String(c.title || "").indexOf("quickshell-") !== 0
    }).map(function(c) { return { x: c.at[0], y: c.at[1], w: c.size[0], h: c.size[1] } })
}
