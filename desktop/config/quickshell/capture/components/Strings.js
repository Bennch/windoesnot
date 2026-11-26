.pragma library

// German / English strings of the capture overlay (the shell's i18n/Lang.js lives in another config).
// The language comes from the locale, like the shell's uiLanguage.
var de = {
    "tab.screenshot": "Bildschirmfoto",
    "tab.record": "Aufnahme",
    "mode.region": "Bereich",
    "mode.window": "Fenster",
    "mode.screen": "Ganzer Bildschirm",
    "delay.none": "Keine Verzögerung",
    "delay.seconds": "%1 s",
    "options": "Optionen",
    "opt.copy": "In die Zwischenablage kopieren",
    "opt.pointer": "Mauszeiger anzeigen",
    "opt.audio": "Ton aufnehmen",
    "capture": "Aufnehmen",
    "startRecording": "Aufnahme starten",
    "close": "Schließen",
    "hint.region": "Ziehen, um einen Bereich zu wählen · Leertaste verschiebt ihn · Eingabe: %1 · Esc: abbrechen",
    "hint.window": "Fenster anklicken · Eingabe: %1 · Esc: abbrechen",
    "hint.screen": "Bildschirm anklicken · Eingabe nimmt den aktiven auf · Esc: abbrechen",
    "verb.capture": "aufnehmen",
    "verb.record": "Aufnahme starten",
    "stop": "Stopp",
    "startsIn": "Start in %1 s",
    "cancel": "Abbrechen",
    "recording": "Aufnahme läuft"
}

var en = {
    "tab.screenshot": "Screenshot",
    "tab.record": "Record",
    "mode.region": "Region",
    "mode.window": "Window",
    "mode.screen": "Full screen",
    "delay.none": "No delay",
    "delay.seconds": "%1 s",
    "options": "Options",
    "opt.copy": "Copy to clipboard",
    "opt.pointer": "Show pointer",
    "opt.audio": "Record audio",
    "capture": "Capture",
    "startRecording": "Start recording",
    "close": "Close",
    "hint.region": "Drag to pick an area · Space to move it · Enter to %1 · Esc to cancel",
    "hint.window": "Click a window · Enter to %1 · Esc to cancel",
    "hint.screen": "Click a screen · Enter captures the focused one · Esc to cancel",
    "verb.capture": "capture",
    "verb.record": "start recording",
    "stop": "Stop",
    "startsIn": "Starting in %1 s",
    "cancel": "Cancel",
    "recording": "Recording"
}

function t(key, lang, arg) {
    var table = lang === "de" ? de : en
    var text = table[key] !== undefined ? table[key] : (en[key] !== undefined ? en[key] : key)
    return arg === undefined ? text : text.replace("%1", arg)
}
