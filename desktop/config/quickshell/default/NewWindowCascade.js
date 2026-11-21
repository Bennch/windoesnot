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
