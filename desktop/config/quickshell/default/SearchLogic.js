.pragma library

// Logic of the search window, kept free of UI code so it can be tested with node:
//  - ranking of apps (name match quality + how often and how recently an app was started)
//  - calculator (own parser, no eval) with percentages, functions and unit conversion

function normalize(text) {
    return String(text || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
}

function words(name) { return name.split(/[^a-z0-9]+/).filter(function(w) { return w.length > 0 }) }

// How well does `query` match an app? -1 = not at all. Higher is better.
function matchScore(name, command, query) {
    var n = normalize(name), q = normalize(query).trim()
    if (q.length === 0) return -1
    var parts = words(n)
    if (n === q) return 1000
    if (n.indexOf(q) === 0) return 800 - Math.min(n.length - q.length, 50)
    for (var i = 0; i < parts.length; i++) if (parts[i].indexOf(q) === 0) return 600 - Math.min(i * 20, 100)
    var initials = parts.map(function(w) { return w[0] }).join("")
    if (q.length >= 2 && initials.indexOf(q) === 0) return 500
    var at = n.indexOf(q)
    if (at > 0) return 400 - Math.min(at, 100)
    // Letters in order, but not next to each other ("ffx" finds Firefox); only for longer queries.
    if (q.length >= 3) {
        var pos = 0
        for (var k = 0; k < q.length; k++) {
            pos = n.indexOf(q[k], pos)
            if (pos < 0) break
            pos++
        }
        if (pos >= 0) return 200
    }
    var cmd = normalize(command).split(/[\s\/]+/).filter(function(w) { return w.length > 0 && w[0] !== "-" && w[0] !== "@" })
    for (var c = 0; c < cmd.length; c++) if (cmd[c].indexOf(q) === 0) return 150
    return -1
}

// usage: { "<app name>": {c: starts, t: last start in ms} }
function usageBonus(entry, now) {
    if (!entry) return 0
    var bonus = Math.min(entry.c || 0, 20) * 8
    var age = (now - (entry.t || 0)) / 86400000
    if (age < 1) bonus += 60
    else if (age < 7) bonus += 30
    else if (age < 30) bonus += 10
    return bonus
}

// apps: [{name, cmd, icon, customIcon}] -> best `limit` matches, best first
function rankApps(apps, query, usage, limit, now) {
    var scored = []
    for (var i = 0; i < apps.length; i++) {
        var base = matchScore(apps[i].name, apps[i].cmd, query)
        if (base < 0) continue
        scored.push({app: apps[i], score: base + usageBonus(usage[apps[i].name], now), order: i})
    }
    scored.sort(function(a, b) { return b.score - a.score || a.order - b.order })
    return scored.slice(0, limit).map(function(s) { return s.app })
}

// The most used apps, for the empty search field.
function recentApps(apps, usage, limit, now) {
    var scored = []
    for (var i = 0; i < apps.length; i++) {
        var entry = usage[apps[i].name]
        if (entry) scored.push({app: apps[i], score: usageBonus(entry, now), order: i})
    }
    scored.sort(function(a, b) { return b.score - a.score || a.order - b.order })
    return scored.slice(0, limit).map(function(s) { return s.app })
}

function recordUse(usage, name, now) {
    var copy = {}
    for (var key in usage) copy[key] = usage[key]
    var entry = copy[name] || {c: 0, t: 0}
    copy[name] = {c: (entry.c || 0) + 1, t: now}
    // Keep the file small: drop the least used entries beyond 200.
    var names = Object.keys(copy)
    if (names.length > 200) {
        names.sort(function(a, b) { return usageBonus(copy[b], now) - usageBonus(copy[a], now) })
        var kept = {}
        names.slice(0, 200).forEach(function(k) { kept[k] = copy[k] })
        return kept
    }
    return copy
}

// ---- calculator ------------------------------------------------------------------------------------

var FUNCTIONS = {
    sqrt: Math.sqrt, sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
    log: Math.log10, log10: Math.log10, ln: Math.log, exp: Math.exp, abs: Math.abs, round: Math.round,
    floor: Math.floor, ceil: Math.ceil, min: Math.min, max: Math.max, pow: Math.pow
}
var CONSTANTS = {pi: Math.PI, e: Math.E}

function tokenize(text) {
    // With a function in the text a comma separates arguments (max(3,9)); otherwise it is a decimal comma (1,5*2).
    var decimalComma = !/[a-zA-Z]{2,}\s*\(/.test(text)
    var tokens = [], i = 0
    while (i < text.length) {
        var ch = text[i]
        if (/\s/.test(ch)) { i++; continue }
        var number = (decimalComma ? /^(\d+([.,]\d+)?|[.,]\d+)([eE][+-]?\d+)?/ : /^(\d+(\.\d+)?|\.\d+)([eE][+-]?\d+)?/).exec(text.slice(i))
        if (number) { tokens.push({t: "num", v: parseFloat(number[0].replace(",", "."))}); i += number[0].length; continue }
        var word = /^[a-zA-Z]+/.exec(text.slice(i))
        if (word) { tokens.push({t: "id", v: word[0].toLowerCase()}); i += word[0].length; continue }
        if ("+-*/^%(),×÷·".indexOf(ch) >= 0) { tokens.push({t: "op", v: ch === "×" || ch === "·" ? "*" : ch === "÷" ? "/" : ch}); i++; continue }
        return null
    }
    return tokens
}

// Recursive descent: expr = term (+|- term)*; term = power (*|/ power)*; power = unary (^ power)?;
// unary = -unary | postfix; postfix = atom (%)*; atom = number | constant | function(args) | (expr).
// Every rule returns {v, pct}; pct marks a bare percentage so "100 + 10%" means 10% of 100.
function parseExpression(tokens) {
    var pos = 0
    function isOp(v) { return pos < tokens.length && tokens[pos].t === "op" && tokens[pos].v === v }
    function fail() { throw new Error("syntax") }
    function expr() {
        var left = term()
        while (isOp("+") || isOp("-")) {
            var plus = tokens[pos++].v === "+"
            var right = term()
            var amount = right.pct ? left.v * right.v : right.v
            left = {v: plus ? left.v + amount : left.v - amount, pct: false}
        }
        return left
    }
    function term() {
        var left = power()
        while (isOp("*") || isOp("/")) {
            var multiply = tokens[pos++].v === "*"
            var right = power()
            left = {v: multiply ? left.v * right.v : left.v / right.v, pct: false}
        }
        return left
    }
    function power() {
        var base = unary()
        if (isOp("^")) { pos++; var exponent = power(); return {v: Math.pow(base.v, exponent.v), pct: false} }
        return base
    }
    function unary() {
        if (isOp("-")) { pos++; return {v: -unary().v, pct: false} }
        if (isOp("+")) { pos++; return unary() }
        return postfix()
    }
    function postfix() {
        var value = atom(), pct = false
        while (isOp("%")) { pos++; value = value / 100; pct = true }
        return {v: value, pct: pct}
    }
    function atom() {
        var token = tokens[pos]
        if (!token) fail()
        if (token.t === "num") { pos++; return token.v }
        if (token.t === "id") {
            pos++
            if (CONSTANTS.hasOwnProperty(token.v)) return CONSTANTS[token.v]
            if (!FUNCTIONS.hasOwnProperty(token.v) || !isOp("(")) fail()
            pos++
            var args = []
            if (!isOp(")")) {
                args.push(expr().v)
                while (isOp(",")) { pos++; args.push(expr().v) }
            }
            if (!isOp(")")) fail()
            pos++
            return FUNCTIONS[token.v].apply(null, args)
        }
        if (isOp("(")) { pos++; var inner = expr().v; if (!isOp(")")) fail(); pos++; return inner }
        fail()
    }
    var result = expr()
    if (pos !== tokens.length) fail()
    return result.v
}

function format(value) {
    if (typeof value !== "number" || !isFinite(value)) return ""
    var rounded = Math.round(value * 1e10) / 1e10
    var text = String(rounded)
    if (/e/.test(text)) text = rounded.toPrecision(10).replace(/\.?0+(e|$)/, "$1")
    return text
}

// "20% of 150" -> 30
function percentOf(text) {
    var match = /^\s*([\d.,]+)\s*%\s*(?:of|von)\s*([\d.,]+)\s*$/i.exec(text)
    if (!match) return null
    return parseFloat(match[1].replace(",", ".")) / 100 * parseFloat(match[2].replace(",", "."))
}

function evaluate(text) {
    var direct = percentOf(text)
    if (direct !== null) return format(direct)
    var tokens = tokenize(text)
    if (!tokens || tokens.length === 0) return ""
    // A bare number is not worth an answer line.
    if (tokens.length === 1 && tokens[0].t === "num") return ""
    try {
        return format(parseExpression(tokens))
    } catch (error) {
        return ""
    }
}

// ---- unit conversion -------------------------------------------------------------------------------

var UNITS = {
    length: {m: 1, meter: 1, km: 1000, kilometer: 1000, cm: 0.01, mm: 0.001, mi: 1609.344, mile: 1609.344, meilen: 1609.344, meile: 1609.344,
             ft: 0.3048, feet: 0.3048, fuss: 0.3048, "in": 0.0254, inch: 0.0254, zoll: 0.0254, yd: 0.9144},
    mass: {kg: 1, g: 0.001, mg: 0.000001, t: 1000, lb: 0.45359237, lbs: 0.45359237, pfund: 0.5, oz: 0.028349523125},
    data: {b: 1, kb: 1000, mb: 1e6, gb: 1e9, tb: 1e12, kib: 1024, mib: 1048576, gib: 1073741824, tib: 1099511627776},
    time: {s: 1, sek: 1, min: 60, h: 3600, std: 3600, d: 86400, tage: 86400, tag: 86400, w: 604800},
    speed: {"km/h": 1 / 3.6, kmh: 1 / 3.6, "m/s": 1, mph: 0.44704, kn: 0.514444},
    volume: {l: 1, liter: 1, ml: 0.001, gal: 3.785411784, cl: 0.01}
}

function convertUnits(text) {
    var match = /^\s*(-?[\d.,]+)\s*([a-zA-Z\/°]+)\s*(?:in|to|zu|nach|->|→)\s*([a-zA-Z\/°]+)\s*$/i.exec(text)
    if (!match) return ""
    var amount = parseFloat(match[1].replace(",", ".")), from = match[2].toLowerCase(), to = match[3].toLowerCase()
    var temperature = {"c": "c", "°c": "c", "f": "f", "°f": "f", "k": "k", "celsius": "c", "fahrenheit": "f", "kelvin": "k"}
    if (temperature[from] && temperature[to]) {
        var celsius = temperature[from] === "c" ? amount : temperature[from] === "f" ? (amount - 32) * 5 / 9 : amount - 273.15
        var out = temperature[to] === "c" ? celsius : temperature[to] === "f" ? celsius * 9 / 5 + 32 : celsius + 273.15
        return format(out) + " " + (temperature[to] === "k" ? "K" : "°" + temperature[to].toUpperCase())
    }
    for (var kind in UNITS) {
        var table = UNITS[kind]
        if (table.hasOwnProperty(from) && table.hasOwnProperty(to))
            return format(amount * table[from] / table[to]) + " " + match[3]
    }
    return ""
}

// What to show on the answer line for this query ("" = nothing)
function answer(query) {
    var unit = convertUnits(query)
    if (unit) return unit
    return evaluate(query)
}

// ---- filters and highlighting ----------------------------------------------------------------------

// "/pdf rechnung" -> {kind: "pdf", text: "rechnung"}; text without a known filter is returned unchanged.
var FILTERS = {
    apps: "apps", app: "apps", programme: "apps",
    files: "files", dateien: "files", datei: "files",
    pdf: "pdf", bilder: "images", images: "images", img: "images",
    docs: "docs", dokumente: "docs", doc: "docs",
    video: "video", videos: "video", musik: "audio", audio: "audio"
}
var EXTENSIONS = {
    pdf: ["pdf"], images: ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "avif", "heic"],
    docs: ["odt", "ods", "odp", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"],
    video: ["mp4", "mkv", "avi", "mov", "webm"], audio: ["mp3", "flac", "ogg", "wav", "opus", "m4a"]
}

function parseFilter(query) {
    var match = /^\/([a-zA-ZäöüÄÖÜ]+)(?:\s+(.*))?$/.exec(query)
    if (!match) return {kind: "", text: query}
    var kind = FILTERS[match[1].toLowerCase()]
    if (!kind) return {kind: "", text: query}
    return {kind: kind, text: (match[2] || "").trim()}
}

function extensionsFor(kind) { return EXTENSIONS[kind] || [] }

function escapeHtml(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

// Name as StyledText with the typed letters in the accent colour (first occurrence; plain when it matched otherwise).
function highlight(name, query, color) {
    var q = String(query || "").trim().toLowerCase(), n = String(name)
    var at = q.length > 0 ? n.toLowerCase().indexOf(q) : -1
    if (at < 0) return escapeHtml(n)
    return escapeHtml(n.slice(0, at)) + "<font color=\"" + color + "\"><b>" + escapeHtml(n.slice(at, at + q.length)) + "</b></font>" + escapeHtml(n.slice(at + q.length))
}

// ---- files and folders ------------------------------------------------------------------------------

// Raw output lines "<mtime>|<type>|<path>" (type: "directory"/"d" for folders) -> [{path, isDir, mtime}]
function parseFileLines(text) {
    var entries = []
    String(text).split("\n").forEach(function(line) {
        var first = line.indexOf("|"), second = first < 0 ? -1 : line.indexOf("|", first + 1)
        if (second < 0) return
        var path = line.slice(second + 1)
        if (path.length === 0 || path[0] !== "/") return
        var kind = line.slice(first + 1, second)
        entries.push({path: path, isDir: kind === "directory" || kind === "d", mtime: parseFloat(line.slice(0, first)) * 1000 || 0})
    })
    return entries
}

var FAVOURITE_FOLDERS = ["Dokumente", "Documents", "Schreibtisch", "Desktop", "Downloads", "Bilder", "Pictures", "Projekte", "Musik", "Videos"]

// Best matches first: name quality, then where the file lives (your own folders), how recently it changed and how deep it sits.
function rankFiles(entries, query, home, limit, now) {
    var q = normalize(query).trim()
    var scored = []
    entries.forEach(function(entry) {
        var parts = entry.path.split("/").filter(function(x) { return x.length > 0 })
        var name = parts[parts.length - 1] || ""
        var stem = entry.isDir ? name : name.replace(/\.[^.]*$/, "")
        var quality = Math.max(matchScore(stem, "", q), matchScore(name, "", q), 100)
        var score = quality
        var relative = home && entry.path.indexOf(home + "/") === 0 ? entry.path.slice(home.length + 1).split("/") : parts
        if (FAVOURITE_FOLDERS.indexOf(relative[0]) >= 0) score += 30
        if (relative.some(function(part) { return part.length > 1 && part[0] === "." })) score -= 120
        score -= Math.max(0, relative.length - 4) * 6
        var age = (now - entry.mtime) / 86400000
        if (entry.mtime > 0) score += age < 1 ? 80 : age < 7 ? 50 : age < 30 ? 25 : age < 365 ? 10 : 0
        if (entry.isDir && quality >= 800) score += 25   // a folder named like the search is usually the target
        scored.push({entry: entry, score: score})
    })
    scored.sort(function(a, b) { return b.score - a.score || a.entry.path.length - b.entry.path.length })
    return scored.slice(0, limit).map(function(item) { return item.entry })
}
