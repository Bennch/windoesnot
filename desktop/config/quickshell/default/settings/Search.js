.pragma library
.import "../i18n/Lang.js" as Lang
.import "SearchIndex.js" as Index

var cache = {}

// Lower case, no accents: "Größe" matches "groesse" and "grosse".
function fold(text) {
    return (text || "").toLowerCase().replace(/ß/g, "ss").replace(/ä/g, "a").replace(/ö/g, "o").replace(/ü/g, "u")
        .normalize("NFD").replace(/[̀-ͯ]/g, "")
}

// Texts of one setting in every language, so a query in any language finds it.
function allLanguages(key, extra) {
    var languages = Lang.getAvailableLanguages(), all = []
    for (var i = 0; i < languages.length; i++) all.push(Lang.get(key, languages[i].code))
    return fold(all.join(" ") + " " + (extra || ""))
}

function entriesFor(lang) {
    if (cache[lang]) return cache[lang]
    var list = [], seen = {}
    function add(page, text, isTitle, extra, key) {
        if (!text || text.length > 400) return
        var id = page + "|" + text
        if (seen[id]) return
        seen[id] = true
        var pageLabel = Lang.get("nav." + page, lang)
        list.push({ page: page, pageLabel: pageLabel, text: text,
                    hay: (key ? allLanguages(key, extra) : fold(text) + " " + fold(extra)) + " " + allLanguages("nav." + page),
                    isCategory: key === "nav." + page, words: fold(text).split(/[^a-z0-9]+/),
                    title: isTitle || text.length <= 48 })
    }
    for (var i = 0; i < Index.PAGES.length; i++) {
        var page = Index.PAGES[i]
        add(page.page, Lang.get("nav." + page.page, lang), true, "", "nav." + page.page)
        for (var k = 0; k < page.keys.length; k++) add(page.page, Lang.get(page.keys[k], lang), false, page.extra[page.keys[k]], page.keys[k])
        for (var t = 0; t < page.texts.length; t++) add(page.page, page.texts[t], false)
    }
    cache[lang] = list
    return list
}

// Every word of the query must occur; words starting a word and short titles rank first.
function search(query, lang, limit) {
    var tokens = fold(query).split(/\s+/).filter(function (w) { return w.length > 0 })
    if (tokens.length === 0) return []
    var list = entriesFor(lang), hits = []
    for (var i = 0; i < list.length; i++) {
        var entry = list[i], score = 0, ok = true
        for (var j = 0; j < tokens.length && ok; j++) {
            if (entry.hay.indexOf(tokens[j]) < 0) { ok = false; break }
            var starts = false
            for (var w = 0; w < entry.words.length; w++)
                if (entry.words[w].indexOf(tokens[j]) === 0) { starts = true; break }
            score += starts ? 3 : 1
        }
        if (!ok) continue
        if (entry.title) score += 4
        hits.push({ entry: entry, score: score - entry.text.length / 400 })
    }
    hits.sort(function (a, b) { return b.score - a.score })
    return hits.slice(0, limit || 30).map(function (h) {
        return { page: h.entry.page, pageLabel: h.entry.pageLabel, text: h.entry.text, isCategory: h.entry.isCategory }
    })
}
