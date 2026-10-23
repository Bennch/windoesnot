.pragma library
.import "de.js" as De
.import "en.js" as En

var languages = {
    de: De.strings,
    en: En.strings
}

var current = "de"

function setCurrent(lang) {
    if (languages[lang]) {
        current = lang
    }
}

function getCurrent() {
    return current
}

function get(key, trigger) {
    // trigger parameter forces QML binding re-evaluation when language changes
    var selected = languages[trigger] ? trigger : current
    if (languages[selected] && languages[selected][key]) {
        return languages[selected][key]
    }
    // Fallback to English
    if (languages["en"] && languages["en"][key]) {
        return languages["en"][key]
    }
    // Return key if not found
    return key
}

function getAvailableLanguages() {
    return [
        { code: "de", name: "Deutsch" },
        { code: "en", name: "English" }
    ]
}
