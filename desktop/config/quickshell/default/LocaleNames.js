.pragma library

function normalize(value) {
    return String(value || "").trim().replace(/\.utf-?8/i, ".UTF-8");
}

function isLanguageLocale(value) {
    var name = normalize(value);
    return name.length > 0 && !/^(C|POSIX)(?:[.@_-]|$)/i.test(name);
}
