.pragma library
// Public holidays and common observances for the calendar, computed offline (no network, no data files).
// Every entry: { de, en, kind } with kind "public" (public holiday), "regional" (only in part of the country)
// or "observance" (well-known day, not a day off).

function easter(year) {
    // Anonymous Gregorian algorithm
    var a = year % 19, b = Math.floor(year / 100), c = year % 100
    var d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25)
    var g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30
    var i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7
    var m = Math.floor((a + 11 * h + 22 * l) / 451)
    var month = Math.floor((h + l - 7 * m + 114) / 31)
    var day = ((h + l - 7 * m + 114) % 31) + 1
    return new Date(year, month - 1, day)
}

function shift(date, days) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days)
}

// n-th (1-based) weekday (0 = Sunday) of a month; n = -1 means the last one.
function nthWeekday(year, month, weekday, n) {
    if (n > 0) {
        var first = new Date(year, month - 1, 1)
        var offset = (weekday - first.getDay() + 7) % 7
        return new Date(year, month - 1, 1 + offset + (n - 1) * 7)
    }
    var last = new Date(year, month, 0)
    var back = (last.getDay() - weekday + 7) % 7
    return new Date(year, month - 1, last.getDate() - back)
}

function add(map, date, de, en, kind) {
    var key = (date.getMonth() + 1) + "-" + date.getDate()
    var rank = { public: 3, regional: 2, observance: 1 }
    if (map[key] && rank[map[key].kind] >= rank[kind]) return
    map[key] = { de: de, en: en, kind: kind }
}

function fixed(map, month, day, year, de, en, kind) { add(map, new Date(year, month - 1, day), de, en, kind) }

var SUPPORTED = ["DE", "AT", "CH", "US", "GB", "FR"]

// Region from the system locale ("de_DE" -> "DE"); without a known region the UI language decides.
function regionFor(localeName, uiLanguage) {
    var parts = String(localeName || "").split(/[_.@-]/)
    var region = parts.length > 1 ? parts[1].toUpperCase() : ""
    if (SUPPORTED.indexOf(region) >= 0) return region
    if (uiLanguage === "de") return "DE"
    return "GLOBAL"
}

function holidays(year, region) {
    var m = {}
    var e = easter(year)
    var f = function (mo, d, de, en, kind) { fixed(m, mo, d, year, de, en, kind) }
    var rel = function (days, de, en, kind) { add(m, shift(e, days), de, en, kind) }
    var wd = function (mo, w, n, de, en, kind) { add(m, nthWeekday(year, mo, w, n), de, en, kind) }

    if (region === "DE") {
        f(1, 1, "Neujahr", "New Year's Day", "public")
        f(1, 6, "Heilige Drei Könige", "Epiphany", "regional")
        f(3, 8, "Internationaler Frauentag", "International Women's Day", "regional")
        rel(-2, "Karfreitag", "Good Friday", "public")
        rel(0, "Ostersonntag", "Easter Sunday", "observance")
        rel(1, "Ostermontag", "Easter Monday", "public")
        f(5, 1, "Tag der Arbeit", "Labour Day", "public")
        rel(39, "Christi Himmelfahrt", "Ascension Day", "public")
        rel(49, "Pfingstsonntag", "Whit Sunday", "observance")
        rel(50, "Pfingstmontag", "Whit Monday", "public")
        rel(60, "Fronleichnam", "Corpus Christi", "regional")
        f(8, 15, "Mariä Himmelfahrt", "Assumption Day", "regional")
        f(9, 20, "Weltkindertag", "World Children's Day", "regional")
        f(10, 3, "Tag der Deutschen Einheit", "German Unity Day", "public")
        f(10, 31, "Reformationstag", "Reformation Day", "regional")
        f(11, 1, "Allerheiligen", "All Saints' Day", "regional")
        add(m, shift(nthWeekday(year, 11, 3, 4), -7), "Buß- und Bettag", "Day of Repentance and Prayer", "regional")
        f(12, 6, "Nikolaus", "St Nicholas Day", "observance")
        f(12, 24, "Heiligabend", "Christmas Eve", "observance")
        f(12, 25, "1. Weihnachtstag", "Christmas Day", "public")
        f(12, 26, "2. Weihnachtstag", "Boxing Day", "public")
        f(12, 31, "Silvester", "New Year's Eve", "observance")
        f(2, 14, "Valentinstag", "Valentine's Day", "observance")
        wd(5, 0, 2, "Muttertag", "Mother's Day", "observance")
    } else if (region === "AT") {
        f(1, 1, "Neujahr", "New Year's Day", "public")
        f(1, 6, "Heilige Drei Könige", "Epiphany", "public")
        rel(0, "Ostersonntag", "Easter Sunday", "observance")
        rel(1, "Ostermontag", "Easter Monday", "public")
        f(5, 1, "Staatsfeiertag", "State Holiday", "public")
        rel(39, "Christi Himmelfahrt", "Ascension Day", "public")
        rel(50, "Pfingstmontag", "Whit Monday", "public")
        rel(60, "Fronleichnam", "Corpus Christi", "public")
        f(8, 15, "Mariä Himmelfahrt", "Assumption Day", "public")
        f(10, 26, "Nationalfeiertag", "National Day", "public")
        f(11, 1, "Allerheiligen", "All Saints' Day", "public")
        f(12, 8, "Mariä Empfängnis", "Immaculate Conception", "public")
        f(12, 24, "Heiligabend", "Christmas Eve", "observance")
        f(12, 25, "Christtag", "Christmas Day", "public")
        f(12, 26, "Stefanitag", "St Stephen's Day", "public")
        f(12, 31, "Silvester", "New Year's Eve", "observance")
        wd(5, 0, 2, "Muttertag", "Mother's Day", "observance")
    } else if (region === "CH") {
        f(1, 1, "Neujahr", "New Year's Day", "public")
        f(1, 2, "Berchtoldstag", "Berchtold's Day", "regional")
        rel(-2, "Karfreitag", "Good Friday", "regional")
        rel(0, "Ostersonntag", "Easter Sunday", "observance")
        rel(1, "Ostermontag", "Easter Monday", "regional")
        rel(39, "Auffahrt", "Ascension Day", "public")
        rel(50, "Pfingstmontag", "Whit Monday", "regional")
        f(8, 1, "Bundesfeier", "Swiss National Day", "public")
        f(12, 24, "Heiligabend", "Christmas Eve", "observance")
        f(12, 25, "Weihnachten", "Christmas Day", "public")
        f(12, 26, "Stephanstag", "St Stephen's Day", "regional")
        f(12, 31, "Silvester", "New Year's Eve", "observance")
    } else if (region === "US") {
        f(1, 1, "Neujahr", "New Year's Day", "public")
        wd(1, 1, 3, "Martin-Luther-King-Tag", "Martin Luther King Jr. Day", "public")
        f(2, 14, "Valentinstag", "Valentine's Day", "observance")
        wd(2, 1, 3, "Presidents' Day", "Presidents' Day", "public")
        rel(0, "Ostersonntag", "Easter Sunday", "observance")
        wd(5, 0, 2, "Muttertag", "Mother's Day", "observance")
        wd(5, 1, -1, "Memorial Day", "Memorial Day", "public")
        f(6, 19, "Juneteenth", "Juneteenth", "public")
        f(7, 4, "Unabhängigkeitstag", "Independence Day", "public")
        wd(9, 1, 1, "Labor Day", "Labor Day", "public")
        wd(10, 1, 2, "Columbus Day", "Columbus Day", "public")
        f(10, 31, "Halloween", "Halloween", "observance")
        f(11, 11, "Veterans Day", "Veterans Day", "public")
        wd(11, 4, 4, "Thanksgiving", "Thanksgiving", "public")
        f(12, 25, "Weihnachten", "Christmas Day", "public")
    } else if (region === "GB") {
        f(1, 1, "Neujahr", "New Year's Day", "public")
        f(2, 14, "Valentinstag", "Valentine's Day", "observance")
        add(m, shift(e, -21), "Muttertag (Mothering Sunday)", "Mothering Sunday", "observance")
        rel(-2, "Karfreitag", "Good Friday", "public")
        rel(0, "Ostersonntag", "Easter Sunday", "observance")
        rel(1, "Ostermontag", "Easter Monday", "public")
        wd(5, 1, 1, "Early May Bank Holiday", "Early May bank holiday", "public")
        wd(5, 1, -1, "Spring Bank Holiday", "Spring bank holiday", "public")
        wd(8, 1, -1, "Summer Bank Holiday", "Summer bank holiday", "public")
        f(10, 31, "Halloween", "Halloween", "observance")
        f(11, 5, "Bonfire Night", "Bonfire Night", "observance")
        f(11, 11, "Remembrance Day", "Remembrance Day", "observance")
        f(12, 25, "Weihnachtstag", "Christmas Day", "public")
        f(12, 26, "Boxing Day", "Boxing Day", "public")
    } else if (region === "FR") {
        f(1, 1, "Neujahr", "New Year's Day", "public")
        rel(0, "Ostersonntag", "Easter Sunday", "observance")
        rel(1, "Ostermontag", "Easter Monday", "public")
        f(5, 1, "Tag der Arbeit", "Labour Day", "public")
        f(5, 8, "Tag des Sieges 1945", "Victory in Europe Day", "public")
        rel(39, "Christi Himmelfahrt", "Ascension Day", "public")
        rel(50, "Pfingstmontag", "Whit Monday", "public")
        f(7, 14, "Nationalfeiertag (Fête nationale)", "Bastille Day", "public")
        f(8, 15, "Mariä Himmelfahrt", "Assumption Day", "public")
        f(11, 1, "Allerheiligen", "All Saints' Day", "public")
        f(11, 11, "Waffenstillstand 1918", "Armistice Day", "public")
        f(12, 25, "Weihnachten", "Christmas Day", "public")
    } else {
        // Everywhere else: only the days that are widely shared.
        f(1, 1, "Neujahr", "New Year's Day", "public")
        rel(0, "Ostersonntag", "Easter Sunday", "observance")
        f(5, 1, "Internationaler Tag der Arbeit", "International Workers' Day", "observance")
        f(10, 31, "Halloween", "Halloween", "observance")
        f(12, 24, "Heiligabend", "Christmas Eve", "observance")
        f(12, 25, "Weihnachtstag", "Christmas Day", "public")
        f(12, 31, "Silvester", "New Year's Eve", "observance")
    }
    return m
}

// Entry for one date, or null.
function lookup(map, date) {
    var entry = map[(date.getMonth() + 1) + "-" + date.getDate()]
    return entry || null
}
