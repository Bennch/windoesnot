import QtQuick
import "widgets"
import QtQuick.Controls
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import "i18n/Lang.js" as Lang
import "SearchLogic.js" as Logic
import "EmojiData.js" as EmojiDb
import "SpecialChars.js" as SpecialDb

FloatingWindow {
    id: root
    visible: false
    implicitWidth: Math.min(640, screen ? Math.max(1, screen.width - 16) : 640)
    implicitHeight: Math.min(480, screen ? Math.max(1, screen.height - 61) : 480)
    color: "transparent"
    title: "quickshell-search"

    // Props from shell.qml
    property var    appsModel:    null
    property bool   darkMode:     true
    property int    borderRadius: 8
    property string accentColor:  "#FE6F2D"
    property string uiLanguage:   "de"

    // Colors
    readonly property color bg:       darkMode ? Qt.rgba(0.09, 0.09, 0.10, 0.97) : Qt.rgba(0.97, 0.97, 0.98, 0.97)
    readonly property color fg:       darkMode ? "#f0f0f0" : "#1a1a1a"
    readonly property color fgSub:    darkMode ? "#888888" : "#777777"
    readonly property color hover:    darkMode ? "#2e2e32" : "#e4e4e8"
    readonly property color secHdr:   darkMode ? "#555555" : "#aaaaaa"
    readonly property color sep:      darkMode ? Qt.rgba(1,1,1,0.08) : Qt.rgba(0,0,0,0.08)
    readonly property color ac:       Qt.color(accentColor)
    readonly property color acBorder: Qt.rgba(ac.r, ac.g, ac.b, 0.45)
    readonly property color acSel:    Qt.rgba(ac.r, ac.g, ac.b, 0.28)

    // State
    property string query:       ""
    property var    appResults:  []
    property var    fileResults: []
    property var    clipResults: []
    property string calcResult:  ""
    property bool   calcError:   false
    property int    selIdx:      -1   // index into flatModel (-1 = none)
    property bool   showClip:    false // user explicitly opened clipboard
    // How often and when each app was started from here: ranks results, fills the empty search field.
    property var    usage:       ({})
    readonly property string usageFile: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/windoesnot/search-usage.json"

    // Derived modes
    readonly property bool modeEmoji: query.startsWith(":")
    readonly property bool modeRun:   query.startsWith(">")
    readonly property bool showHints: query.length === 0 && !showClip && activeChip === 0
    // "/pdf bill" narrows the search to one kind; searchText is what is searched for.
    readonly property var    parsed:     Logic.parseFilter(query)
    // Type filter chips under the results (Left/Right choose, live while searching); "" = everything.
    readonly property var    chipKinds:  ["", "apps", "folders", "docs", "images", "pdf", "video", "audio"]
    property int             chipIndex:  0
    readonly property string filterKind: chipIndex > 0 ? chipKinds[chipIndex] : parsed.kind
    readonly property int    activeChip: Math.max(0, chipKinds.indexOf(filterKind))
    // The symbol in the search bar shows what is searched for.
    readonly property var    chipIcons: ["actions/symbolic/edit-find-symbolic.svg", "actions/symbolic/view-app-grid-symbolic.svg",
                                         "places/symbolic/folder-symbolic.svg", "mimes/symbolic/x-office-document-symbolic.svg",
                                         "mimes/symbolic/image-x-generic-symbolic.svg", "mimes/symbolic/text-x-generic-symbolic.svg",
                                         "mimes/symbolic/media-video-symbolic.svg", "mimes/symbolic/audio-x-generic-symbolic.svg"]
    readonly property string searchText: parsed.text
    // An answer line is shown whenever the text is a calculation or a unit conversion (see SearchLogic.js).
    readonly property bool modeMath: calcResult.length > 0

    // ── Emoji data ───────────────────────────────────────────────────────────
    // Extra search words for the most common emoji (the full list below only knows the official names).
    readonly property var emojiHints: [
        {e:"😀",n:"grinning",k:["smile","happy","grin"]},
        {e:"😂",n:"joy",k:["laugh","lol","funny","tears"]},
        {e:"😍",n:"heart eyes",k:["love","cute"]},
        {e:"🥰",n:"smiling hearts",k:["love","affection"]},
        {e:"😊",n:"smiling",k:["smile","happy","blush"]},
        {e:"🤔",n:"thinking",k:["think","hmm"]},
        {e:"😎",n:"sunglasses",k:["cool"]},
        {e:"🥳",n:"partying",k:["party","celebrate","birthday"]},
        {e:"😅",n:"sweat smile",k:["nervous","phew"]},
        {e:"😭",n:"crying",k:["sob","sad","tears"]},
        {e:"😤",n:"steam",k:["angry","frustrated"]},
        {e:"🤣",n:"rofl",k:["laugh","funny","floor"]},
        {e:"😴",n:"sleeping",k:["tired","zzz"]},
        {e:"🤗",n:"hugging",k:["hug"]},
        {e:"🙄",n:"eye roll",k:["whatever","bored"]},
        {e:"😇",n:"angel",k:["innocent","halo"]},
        {e:"🤯",n:"mind blown",k:["shocked","explode"]},
        {e:"🥺",n:"pleading",k:["please","puppy"]},
        {e:"😱",n:"screaming",k:["scared","shocked"]},
        {e:"🤩",n:"star struck",k:["excited","wow","star"]},
        {e:"😬",n:"grimacing",k:["awkward","nervous"]},
        {e:"🤫",n:"shushing",k:["quiet","secret","shhh"]},
        {e:"🫡",n:"salute",k:["respect","yes sir"]},
        {e:"🥹",n:"holding back tears",k:["touched","grateful"]},
        {e:"👍",n:"thumbs up",k:["like","good","yes","approve"]},
        {e:"👎",n:"thumbs down",k:["dislike","bad","no"]},
        {e:"👋",n:"wave",k:["hello","hi","bye"]},
        {e:"🙌",n:"raised hands",k:["celebrate","praise"]},
        {e:"👏",n:"clapping",k:["applause","bravo"]},
        {e:"🤝",n:"handshake",k:["deal","agreement"]},
        {e:"✌️",n:"peace",k:["victory","v"]},
        {e:"🤞",n:"crossed fingers",k:["luck","hope"]},
        {e:"👆",n:"point up",k:["up","point"]},
        {e:"👇",n:"point down",k:["down","point"]},
        {e:"💪",n:"muscle",k:["strong","flex","workout"]},
        {e:"🙏",n:"pray",k:["please","thanks","namaste","folded"]},
        {e:"🤦",n:"facepalm",k:["fail","frustrated"]},
        {e:"🤷",n:"shrug",k:["dunno","whatever"]},
        {e:"❤️",n:"red heart",k:["heart","love"]},
        {e:"🧡",n:"orange heart",k:["heart","orange"]},
        {e:"💛",n:"yellow heart",k:["heart","yellow"]},
        {e:"💚",n:"green heart",k:["heart","green"]},
        {e:"💙",n:"blue heart",k:["heart","blue"]},
        {e:"💜",n:"purple heart",k:["heart","purple"]},
        {e:"🖤",n:"black heart",k:["heart","dark"]},
        {e:"💔",n:"broken heart",k:["heartbreak","sad"]},
        {e:"💯",n:"hundred",k:["100","perfect","score"]},
        {e:"🔥",n:"fire",k:["hot","flame","lit"]},
        {e:"⭐",n:"star",k:["favorite"]},
        {e:"✨",n:"sparkles",k:["shine","magic","glitter"]},
        {e:"🎉",n:"party",k:["celebrate","tada"]},
        {e:"🎊",n:"confetti",k:["party","celebrate"]},
        {e:"🎈",n:"balloon",k:["party","birthday"]},
        {e:"🎁",n:"gift",k:["present","birthday"]},
        {e:"🏆",n:"trophy",k:["win","award","champion"]},
        {e:"🥇",n:"gold medal",k:["first","win","gold"]},
        {e:"⚡",n:"lightning",k:["electric","fast","zap"]},
        {e:"🌈",n:"rainbow",k:["colorful","pride"]},
        {e:"☀️",n:"sun",k:["sunny","weather"]},
        {e:"🌙",n:"moon",k:["night","crescent"]},
        {e:"❄️",n:"snowflake",k:["cold","ice","winter"]},
        {e:"🌊",n:"wave",k:["ocean","water","sea"]},
        {e:"🌸",n:"cherry blossom",k:["flower","spring","pink"]},
        {e:"🍕",n:"pizza",k:["food","italian"]},
        {e:"🍔",n:"burger",k:["food","fast food"]},
        {e:"🍣",n:"sushi",k:["food","japanese"]},
        {e:"🍜",n:"noodles",k:["ramen","food"]},
        {e:"🍰",n:"cake",k:["dessert","birthday","sweet"]},
        {e:"☕",n:"coffee",k:["tea","hot","drink"]},
        {e:"🍺",n:"beer",k:["drink","cheers"]},
        {e:"🐶",n:"dog",k:["puppy","pet","animal"]},
        {e:"🐱",n:"cat",k:["kitten","pet","animal"]},
        {e:"🐧",n:"penguin",k:["linux","bird"]},
        {e:"🦊",n:"fox",k:["animal"]},
        {e:"🦋",n:"butterfly",k:["insect","spring"]},
        {e:"🌍",n:"earth",k:["world","globe"]},
        {e:"🚀",n:"rocket",k:["space","launch","fast"]},
        {e:"✈️",n:"airplane",k:["plane","travel"]},
        {e:"🚗",n:"car",k:["vehicle","drive"]},
        {e:"🎮",n:"game controller",k:["gaming","video game"]},
        {e:"💻",n:"laptop",k:["computer","work","tech"]},
        {e:"📱",n:"phone",k:["mobile","smartphone"]},
        {e:"📷",n:"camera",k:["photo","picture"]},
        {e:"🎵",n:"music note",k:["song","audio"]},
        {e:"📚",n:"books",k:["study","read","learn"]},
        {e:"💡",n:"idea",k:["light","bulb","tip"]},
        {e:"🔑",n:"key",k:["lock","access"]},
        {e:"💰",n:"money",k:["cash","rich","bag"]},
        {e:"💎",n:"diamond",k:["gem","jewel","precious"]},
        {e:"🎯",n:"target",k:["bullseye","goal"]},
        {e:"✅",n:"check",k:["done","ok","yes","tick"]},
        {e:"❌",n:"cross",k:["no","wrong","error","x"]},
        {e:"⚠️",n:"warning",k:["alert","caution"]},
        {e:"🔒",n:"locked",k:["secure","private"]},
        {e:"🔔",n:"bell",k:["notification","alert"]},
        {e:"📌",n:"pin",k:["location","important"]},
        {e:"🗑️",n:"trash",k:["delete","bin"]},
        {e:"🛠️",n:"tools",k:["fix","build","settings","wrench"]},
        {e:"📊",n:"chart",k:["graph","data","statistics"]},
        {e:"🏠",n:"home",k:["house","building"]},
        {e:"🌐",n:"globe",k:["internet","web","network"]},
        {e:"👤",n:"user",k:["person","profile","account"]},
        {e:"💬",n:"chat",k:["message","speech","talk"]},
        {e:"📧",n:"email",k:["mail","message"]},
        {e:"🧠",n:"brain",k:["mind","think","smart"]},
        {e:"👀",n:"eyes",k:["look","watch","see"]},
        {e:"🎓",n:"graduation",k:["education","study","degree"]},
        {e:"📝",n:"memo",k:["note","write","edit"]},
        {e:"🔧",n:"wrench",k:["tool","fix","repair"]},
        {e:"🔗",n:"link",k:["chain","url"]},
        {e:"🏃",n:"running",k:["run","fast","exercise"]},
    ]

    // All emoji and the special characters, parsed once from EmojiData.js / SpecialChars.js ("symbol<TAB>English<TAB>German").
    function parseSymbols(lines, hints) {
        var extra = {}
        if (hints) for (var h = 0; h < hints.length; h++) extra[hints[h].e] = hints[h].n + " " + hints[h].k.join(" ")
        var list = []
        for (var i = 0; i < lines.length; i++) {
            var parts = lines[i].split("\t")
            var words = (parts[1] + " " + (parts[2] || "") + " " + (extra[parts[0]] || "")).toLowerCase()
            list.push({e: parts[0], n: parts[1], w: Logic.normalize(words)})
        }
        return list
    }
    readonly property var emojiAll:   parseSymbols(EmojiDb.emoji, emojiHints)
    readonly property var specialAll: parseSymbols(SpecialDb.chars, null)
    // 0 = emoji, 1 = special characters (Tab switches while ":" is active)
    property int emojiTab: 0

    readonly property var filteredEmoji: {
        if (!modeEmoji) return []
        var list = emojiTab === 0 ? emojiAll : specialAll
        var q = Logic.normalize(query.substring(1)).trim()
        if (q.length === 0) return list
        var starts = [], contains = []
        for (var i = 0; i < list.length; i++) {
            var at = list[i].w.indexOf(q)
            if (at === 0 || list[i].w.indexOf(" " + q) >= 0) starts.push(list[i])
            else if (at > 0) contains.push(list[i])
        }
        return starts.concat(contains)
    }

    // ── Flat model for ListView ───────────────────────────────────────────────
    ListModel { id: flatModel }

    function rebuildModel() {
        flatModel.clear()

        // ─ Hint screen (empty, no clipboard mode) ─
        if (showHints) {
            var recents = Logic.recentApps(allApps(), usage, 5, Date.now())
            if (recents.length > 0) {
                flatModel.append({type:"header", label:Lang.get("search.recent", uiLanguage), hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
                for (var r = 0; r < recents.length; r++)
                    flatModel.append({type:"app", label:"", hintKey:"", filePath:"", clipText:"",
                        appName:recents[r].name, appCmd:recents[r].cmd, appIcon:recents[r].icon, appCustomIcon:recents[r].customIcon, value:""})
            }
            flatModel.append({type:"hint", hintKey:"calc",  label:"= "   + Lang.get("search.hintCalc",  uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            flatModel.append({type:"hint", hintKey:"emoji", label: Lang.get("search.hintEmoji", uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            flatModel.append({type:"hint", hintKey:"clip",  label: Lang.get("search.hintClip",  uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            flatModel.append({type:"hint", hintKey:"run",   label:"> "   + Lang.get("search.hintRun",   uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            selIdx = recents.length > 0 ? 1 : -1   // the most used app is ready: Enter starts it
            return
        }

        if (modeEmoji) { selIdx = -1; return }  // handled by GridView

        // ─ Run command mode ─
        if (modeRun) {
            var cmd = query.substring(1).trim()
            if (cmd.length > 0) {
                flatModel.append({type:"run", label:cmd, hintKey:"", filePath:"", clipText:"", appName:"", appCmd:cmd, appIcon:"", appCustomIcon:false, value:""})
                flatModel.append({type:"term", label:cmd, hintKey:"", filePath:"", clipText:"", appName:"", appCmd:cmd, appIcon:"", appCustomIcon:false, value:""})
            }
            selIdx = flatModel.count > 0 ? 0 : -1
            return
        }

        // ─ Clipboard mode (with optional filter by query) ─
        if (showClip) {
            var clipFiltered = clipResults
            if (query.length > 0) {
                var qLow = query.toLowerCase()
                clipFiltered = clipResults.filter(function(c) {
                    var t = c.indexOf("\t") >= 0 ? c.substring(c.indexOf("\t") + 1) : c
                    return t.toLowerCase().indexOf(qLow) >= 0
                })
            }
            var clipLabel = Lang.get("search.clipboard", uiLanguage)
            if (query.length > 0) clipLabel += "  (" + clipFiltered.length + ")"
            flatModel.append({type:"header", label:clipLabel, hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            for (var kk = 0; kk < clipFiltered.length; kk++) {
                flatModel.append({type:"clip", label:"", hintKey:"", filePath:"", clipText:clipFiltered[kk], appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            }
            if (clipFiltered.length === 0) {
                flatModel.append({type:"empty", label:"", hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            }
            selIdx = flatModel.count > 1 ? 1 : -1  // skip header
            return
        }

        // ─ Normal search mode ─
        // Calculator
        if (calcResult.length > 0 && !calcError) {
            flatModel.append({type:"calc", label:"", hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:calcResult})
        }

        function addFiles() {
            if (fileResults.length === 0) return
            flatModel.append({type:"header", label:Lang.get("search.files", uiLanguage), hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            for (var j = 0; j < fileResults.length; j++) {
                flatModel.append({type:"file", label:"", hintKey:"", filePath:fileResults[j].path, clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:fileResults[j].isDir ? "dir" : ""})
            }
        }
        function addApps() {
        if (appResults.length > 0) {
            flatModel.append({type:"header", label:Lang.get("search.apps", uiLanguage), hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            for (var i = 0; i < appResults.length; i++) {
                var a = appResults[i]
                flatModel.append({type:"app", label:"", hintKey:"", filePath:"", clipText:"",
                    appName:a.name, appCmd:a.cmd, appIcon:a.icon, appCustomIcon:a.customIcon, value:""})
            }
        }
        }
        // Files and folders come first; only an app whose name starts like the search (you typed "firefox") goes ahead of them.
        var appFirst = appResults.length > 0 && Logic.matchScore(appResults[0].name, appResults[0].cmd, searchText) >= 800
        if (appFirst || fileResults.length === 0) { addApps(); addFiles() } else { addFiles(); addApps() }

        // Web search (always shown when query >= 2 chars)
        if (query.length >= 2 && filterKind === "") {
            flatModel.append({type:"webSearch", label:query, hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            flatModel.append({type:"term", label:query, hintKey:"", filePath:"", clipText:"", appName:"", appCmd:query, appIcon:"", appCustomIcon:false, value:""})
        }

        // Empty state
        var hasResults = calcResult.length > 0 || appResults.length > 0 || fileResults.length > 0
        if (!hasResults && query.length >= 2) {
            flatModel.append({type:"empty", label:"", hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
        }

        // Auto-select first selectable
        selIdx = -1
        for (var m = 0; m < flatModel.count; m++) {
            if (flatModel.get(m).type !== "header") { selIdx = m; break }
        }
    }

    // Rebuild triggers
    onShowHintsChanged:   Qt.callLater(rebuildModel)
    onShowClipChanged:    Qt.callLater(rebuildModel)
    onModeEmojiChanged:   Qt.callLater(rebuildModel)
    onModeRunChanged:     Qt.callLater(rebuildModel)
    onCalcResultChanged:  Qt.callLater(rebuildModel)
    onCalcErrorChanged:   Qt.callLater(rebuildModel)
    onAppResultsChanged:  Qt.callLater(rebuildModel)
    onFileResultsChanged: Qt.callLater(rebuildModel)
    onClipResultsChanged: Qt.callLater(rebuildModel)
    onUiLanguageChanged:  Qt.callLater(rebuildModel)
    onUsageChanged:       Qt.callLater(function() { updateApps(); rebuildModel() })
    onChipIndexChanged:   { updateApps(); updateCalc(); debounce.restart(); Qt.callLater(rebuildModel) }
    // Clipboard filter: rebuild when query changes in clip mode
    onQueryChanged: {
        if (showClip) { Qt.callLater(rebuildModel); return }
        // Everything computed here answers at once on every key; only the file search waits a moment.
        updateApps()
        updateCalc()
    }

    // ── Keyboard nav ─────────────────────────────────────────────────────────
    function selectFirst() {
        for (var i = 0; i < flatModel.count; i++) if (flatModel.get(i).type !== "header" && flatModel.get(i).type !== "empty") { selIdx = i; return }
    }
    function selectLast() {
        for (var i = flatModel.count - 1; i >= 0; i--) if (flatModel.get(i).type !== "header" && flatModel.get(i).type !== "empty") { selIdx = i; return }
    }

    // Up on the first row jumps to the last one ("Search the web", "Run in terminal"); Down on the last row to the first.
    function navUp() {
        var next = selIdx - 1
        while (next >= 0 && flatModel.get(next).type === "header") next--
        if (next >= 0) selIdx = next
        else selectLast()
    }

    // Tab / Shift+Tab: the next / previous search type (or emoji <-> special characters while ":" is active).
    function cycleChip(delta) {
        if (modeEmoji) { emojiTab = (emojiTab + 1) % 2; emojiGrid.currentIndex = 0; return }
        if (showClip || modeRun) return
        var next = (activeChip + (delta || 1) + chipKinds.length) % chipKinds.length
        if (parsed.kind !== "") searchField.text = parsed.text
        chipIndex = next
    }

    function navDown() {
        var next = selIdx + 1
        while (next < flatModel.count && flatModel.get(next).type === "header") next++
        if (next < flatModel.count) selIdx = next
        else selectFirst()
    }

    // ── Actions ───────────────────────────────────────────────────────────────
    function launchSelected() {
        if (modeEmoji) {
            if (emojiGrid.currentIndex >= 0 && emojiGrid.currentIndex < filteredEmoji.length)
                activateEmoji(filteredEmoji[emojiGrid.currentIndex])
            return
        }
        if (selIdx < 0 || selIdx >= flatModel.count) return
        var item = flatModel.get(selIdx)
        if (item.type === "calc")      { copyText(item.value); closeSearch(); return }
        if (item.type === "app")       { activateAppItem(item); return }
        if (item.type === "file")      { activateFile(item.filePath); return }
        if (item.type === "clip")      { activateClipText(item.clipText); return }
        if (item.type === "hint")      { activateHint(item.hintKey); return }
        if (item.type === "run")       { activateRunCmd(item.appCmd); return }
        if (item.type === "term")      { activateRunTerminal(item.appCmd); return }
        if (item.type === "webSearch") { activateWebSearch(item.label); return }
    }

    // Ctrl+Enter on a file: show it in its folder instead of opening it.
    function revealSelected() {
        if (selIdx < 0 || selIdx >= flatModel.count) return false
        var item = flatModel.get(selIdx)
        if (item.type !== "file") return false
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        var uri = "file://" + item.filePath.split("/").map(encodeURIComponent).join("/").replace(/'/g, "%27")
        p.command = ["gdbus", "call", "--session", "--dest", "org.freedesktop.FileManager1", "--object-path",
                     "/org/freedesktop/FileManager1", "--method", "org.freedesktop.FileManager1.ShowItems", "['" + uri + "']", ""]
        p.running = true
        return true
    }

    function activateHint(key) {
        if (key === "emoji") {
            searchField.text = ":"
            searchField.forceActiveFocus()
        } else if (key === "clip") {
            showClip = true
            clipProc.running = false
            clipProc.running = true
        } else if (key === "run") {
            searchField.text = "> "
            searchField.cursorPosition = searchField.text.length
            searchField.forceActiveFocus()
        }
        // "calc": no action, user starts typing math
    }

    function activateAppItem(item) {
        usage = Logic.recordUse(usage, item.appName, Date.now())
        usageSave.stdinText = JSON.stringify(usage)
        usageSave.running = true
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", item.appCmd + " & disown"]
        p.running = true
    }

    function activateFile(path) {
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", "xdg-open " + JSON.stringify(path) + " & disown"]
        p.running = true
    }

    function activateClipText(clipLine) {
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", "printf '%s\\n' " + JSON.stringify(clipLine) + " | cliphist decode | wl-copy"]
        p.running = true
    }

    // Types the emoji into the window that had the focus before the search (wtype) and also keeps it in the clipboard.
    function activateEmoji(em) {
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", 'printf %s "$1" | wl-copy; sleep 0.3; command -v wtype >/dev/null 2>&1 && wtype -- "$1"', "emoji", em.e]
        p.running = true
    }

    function activateRunCmd(cmd) {
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", cmd + " & disown"]
        p.running = true
    }

    // Runs the text in a terminal window that stays open afterwards.
    function activateRunTerminal(cmd) {
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", 'T=ghostty; command -v "$T" >/dev/null 2>&1 || T=foot; setsid "$T" -e bash -lc "$1; exec bash" >/dev/null 2>&1 &', "terminal", cmd]
        p.running = true
    }

    function activateWebSearch(q) {
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", "xdg-open 'https://duckduckgo.com/?q=" + encodeURIComponent(q) + "' & disown"]
        p.running = true
    }

    function copyText(text) {
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", "printf '%s' " + JSON.stringify(text) + " | wl-copy"]
        p.running = true
    }

    function effectiveKind() { return chipIndex > 0 ? chipKinds[chipIndex] : Logic.parseFilter(query).kind }

    // Left/Right: another type filter. A typed "/pdf" prefix is removed from the field: the chip takes over from it.
    function stepChip(delta) {
        var next = Math.max(0, Math.min(chipKinds.length - 1, activeChip + delta))
        if (next === activeChip) return
        if (parsed.kind !== "") searchField.text = parsed.text
        chipIndex = next
    }

    function allApps() {
        var list = []
        if (!appsModel) return list
        for (var i = 0; i < appsModel.count; i++) {
            var a = appsModel.get(i)
            list.push({name:a.name, cmd:a.cmd, icon:a.icon, customIcon:a.customIcon})
        }
        return list
    }

    // The handlers below run from onQueryChanged, before the bindings that derive from `query` have updated:
    // they parse the text themselves.
    function updateApps() {
        var f = Logic.parseFilter(query)
        var kind = effectiveKind()
        if (!appsModel || query.length === 0 || modeEmoji || modeRun || showClip) { appResults = []; return }
        if (kind !== "" && kind !== "apps") { appResults = []; return }
        if (f.text.length === 0) {
            appResults = kind === "apps" ? Logic.recentApps(allApps(), usage, 8, Date.now()) : []
            return
        }
        appResults = Logic.rankApps(allApps(), f.text, usage, 6, Date.now())
    }

    function updateCalc() {
        if (modeEmoji || modeRun || showClip || effectiveKind() !== "" || query.length < 2) { calcResult = ""; calcError = false; return }
        calcResult = Logic.answer(query)
        calcError = false
    }

    // ── Public API ────────────────────────────────────────────────────────────
    function openSearch() {
        query = ""; chipIndex = 0; emojiTab = 0; selIdx = -1; calcResult = ""; calcError = false
        fileResults = []; appResults = []; clipResults = []; showClip = false
        searchField.text = ""
        usageLoad.running = false
        usageLoad.running = true
        visible = true
        Qt.callLater(function() { searchField.forceActiveFocus() })
    }

    function closeSearch() { visible = false }

    // ── Helpers ───────────────────────────────────────────────────────────────
    function fileIcon(path) {
        var ext = path.split(".").pop().toLowerCase()
        if (["png","jpg","jpeg","gif","webp","svg","bmp","avif","heic"].indexOf(ext) >= 0) return "display"
        if (["mp4","mkv","avi","mov","webm"].indexOf(ext) >= 0) return "display"
        if (["mp3","flac","ogg","wav","opus","m4a"].indexOf(ext) >= 0) return "audio"
        if (["pdf"].indexOf(ext) >= 0) return "info"
        if (["zip","tar","gz","bz2","xz","7z","rar"].indexOf(ext) >= 0) return "info"
        if (["js","ts","py","qml","cpp","c","h","rs","go","sh","fish","bash"].indexOf(ext) >= 0) return "display"
        if (["md","txt","csv","log"].indexOf(ext) >= 0) return "info"
        return "info"
    }

    function basename(path) { return path.split("/").pop() }
    function dirpart(path) {
        var parts = path.split("/"); parts.pop()
        return parts.join("/").replace(/^\/home\/[^/]+/, "~")
    }

    // ── Processes ─────────────────────────────────────────────────────────────
    HyprlandFocusGrab {
        id: searchGrab
        windows: [root]
        onCleared: root.closeSearch()
    }

    // Quickshell clears a grab's `active` itself once it was dismissed, which breaks a plain
    // `active: root.visible` binding for good: from the second opening on, a click outside no longer closed
    // the search. Switch the grab on explicitly at every opening (same fix as the other popups).
    onVisibleChanged: {
        if (visible) Qt.callLater(function() { searchGrab.active = true })
        else searchGrab.active = false
    }

    Process {
        id: fileProc
        stdout: StdioCollector {
            onStreamFinished: root.fileResults = Logic.rankFiles(Logic.parseFileLines(text), root.searchText,
                                                                 Quickshell.env("HOME"), 8, Date.now())
        }
        stderr: StdioCollector {}
    }

    Process {
        id: usageLoad
        command: ["bash", "-c", "cat \"$1\" 2>/dev/null", "usage", root.usageFile]
        stdout: StdioCollector {
            onStreamFinished: { try { var data = JSON.parse(text); if (data && typeof data === "object") root.usage = data } catch (e) {} }
        }
    }

    Process {
        id: usageSave
        property string stdinText: ""
        command: ["bash", "-c", "mkdir -p \"$(dirname \"$1\")\" && cat > \"$1.tmp\" && mv \"$1.tmp\" \"$1\"", "usage", root.usageFile]
        stdinEnabled: true
        onStarted: { write(stdinText + "\n"); stdinEnabled = false }
        onExited: stdinEnabled = true
    }

    Process {
        id: clipProc
        command: ["bash", "-c", "cliphist list 2>/dev/null | head -50"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: root.clipResults = text.trim().split("\n").filter(function(l){ return l.length > 0 })
        }
    }

    // Only the file search waits for a pause in typing (it starts a program); apps and answers update on every key.
    Timer {
        id: debounce
        interval: 150
        onTriggered: {
            var q = root.searchText
            var extensions = Logic.extensionsFor(root.filterKind).map(function(e) { return "-e " + e }).join(" ")
            var fileChip = root.filterKind !== "" && root.filterKind !== "apps"
            if ((q.length >= (extensions || root.filterKind === "folders" ? 1 : 2) || (fileChip && q.length === 0))
                    && root.filterKind !== "apps" && !root.modeEmoji && !root.modeRun && !root.showClip) {
                // No text yet but a type chosen: the newest items of that type.
                var recent = q.length === 0 ? "--changed-within 120d " : ""
                if (q.length === 0) q = "."
                fileProc.running = false
                fileProc.command = ["bash", "-c",
                    "if command -v fd >/dev/null 2>&1; then fd --max-results 80 " + recent + (root.filterKind === "folders" ? "--type d " : extensions ? "--type f " : "--type f --type d ") + "--ignore-case " + extensions + " --exclude .cache --exclude node_modules --exclude .git --exclude .local/share -0 -- " + JSON.stringify(q) + " \"$HOME\" 2>/dev/null | xargs -0 -r stat -c '%Y|%F|%n' 2>/dev/null; else " +
                    "find \"$HOME\" -maxdepth 6 \\( -type f -o -type d \\) -iname " + JSON.stringify("*" + q + "*") + " -not -path '*/.cache/*' -not -path '*/node_modules/*' -printf '%T@|%y|%p\\n' 2>/dev/null | head -80; fi"]
                fileProc.running = true
            } else {
                root.fileResults = []
            }
        }
    }

    // ── UI ────────────────────────────────────────────────────────────────────
    Item {
        anchors.fill: parent

        Rectangle {
            anchors.fill: parent
            radius: root.borderRadius
            color: root.bg
        }

        // ── Search bar ───────────────────────────────────────────────────────
        Item {
            id: searchBar
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
            }
            height: 54

            // Mode icon (SVG for normal/emoji/clip, text for math/run)
            Item {
                id: modeIcon
                width: 22; height: 22
                anchors {
                    left: parent.left
                    leftMargin: 16
                    verticalCenter: parent.verticalCenter
                }

                // SVG icon (normal, emoji, clip modes)
                Image {
                    anchors.fill: parent
                    source: "img/Win11-dark/" + root.chipIcons[root.activeChip]
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                    visible: !root.modeMath && !root.modeRun
                    opacity: 0.75
                }

                // Math mode: "=" text
                Text {
                    anchors.centerIn: parent
                    text: "="
                    font.pixelSize: 20; font.bold: true
                    color: root.accentColor
                    visible: root.modeMath
                }

                // Run mode: "▶" text
                Text {
                    anchors.centerIn: parent
                    text: "▶"
                    font.pixelSize: 16; font.bold: true
                    color: root.accentColor
                    visible: root.modeRun && !root.modeMath
                }
            }

            TextInput {
                id: searchField
                anchors {
                    left: modeIcon.right
                    leftMargin: 12
                    right: parent.right
                    rightMargin: 16
                    verticalCenter: parent.verticalCenter
                }
                color: root.fg
                font.pixelSize: 16
                selectionColor: root.acSel
                selectedTextColor: root.fg
                selectByMouse: true
                clip: true

                Keys.onEscapePressed: {
                    if (root.showClip) root.showClip = false
                    else root.closeSearch()
                }
                Keys.onReturnPressed: function(event) {
                    if ((event.modifiers & Qt.ControlModifier) && root.revealSelected()) return
                    root.launchSelected()
                }
                Keys.onTabPressed:    root.cycleChip(1)
                Keys.onBacktabPressed: root.cycleChip(-1)
                Keys.onUpPressed: {
                    if (root.modeEmoji) emojiGrid.moveCurrentIndexUp()
                    else root.navUp()
                }
                Keys.onDownPressed: {
                    if (root.modeEmoji) emojiGrid.moveCurrentIndexDown()
                    else root.navDown()
                }
                Keys.onLeftPressed:  function(event) { if (root.modeEmoji) emojiGrid.moveCurrentIndexLeft(); else event.accepted = false }
                Keys.onRightPressed: function(event) { if (root.modeEmoji) emojiGrid.moveCurrentIndexRight(); else event.accepted = false }

                onTextChanged: {
                    root.query = text
                    if (!root.showClip) {
                        if (text.length === 0) {
                            root.fileResults = []; root.calcResult = ""; root.calcError = false
                        }
                        debounce.restart()   // files only; apps and answers follow in onQueryChanged
                    }
                    // In clip mode: rebuild model to filter (onQueryChanged handles this)
                }
            }

            // Placeholder text
            Text {
                anchors {
                    left: searchField.left
                    verticalCenter: parent.verticalCenter
                }
                text: root.showClip  ? Lang.get("search.clipPlaceholder",  root.uiLanguage)
                    : root.modeEmoji ? Lang.get("search.emojiPlaceholder", root.uiLanguage)
                    : root.modeRun   ? Lang.get("search.runPlaceholder",   root.uiLanguage)
                    : root.activeChip > 0 ? Lang.get("search.placeholder." + root.chipKinds[root.activeChip], root.uiLanguage)
                    :                  Lang.get("search.placeholder",       root.uiLanguage)
                color: root.fgSub
                font.pixelSize: 16
                visible: searchField.text.length === 0
                opacity: 0.5
            }

            // Mode badge
            Rectangle {
                visible: root.showClip || root.modeRun || root.modeEmoji
                anchors {
                    right: parent.right
                    rightMargin: 14
                    verticalCenter: parent.verticalCenter
                }
                height: 20
                width: modeBadgeText.implicitWidth + 12
                radius: 4
                color: Qt.rgba(root.ac.r, root.ac.g, root.ac.b, 0.18)

                Text {
                    id: modeBadgeText
                    anchors.centerIn: parent
                    text: root.modeEmoji ? "emoji"
                        : root.modeRun   ? "run"
                        : root.showClip  ? (Lang.get("search.clipBadge", root.uiLanguage))
                        : ""
                    color: root.accentColor
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            Rectangle {
                anchors {
                    bottom: parent.bottom
                    left: parent.left
                    right: parent.right
                    leftMargin: 12
                    rightMargin: 12
                }
                height: 1
                color: root.sep
            }
        }

        // ── Emoji GridView ───────────────────────────────────────────────────
        GridView {
            id: emojiGrid
            anchors {
                top: emojiTabs.bottom
                left: parent.left
                right: parent.right
                bottom: keyBar.top
                margins: 6
            }
            visible: root.modeEmoji
            clip: true
            cellWidth: 48
            cellHeight: 48
            model: root.filteredEmoji
            currentIndex: 0
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 6 }

            delegate: Rectangle {
                width: 44; height: 44
                radius: 6
                color: GridView.isCurrentItem ? root.acSel
                     : emDelegMouse.containsMouse ? root.hover : "transparent"
                Text { anchors.centerIn: parent; text: modelData.e; font.pixelSize: 26 }
                ToolTip.visible: emDelegMouse.containsMouse
                ToolTip.text: modelData.n
                ToolTip.delay: 600
                MouseArea {
                    id: emDelegMouse
                    anchors.fill: parent; hoverEnabled: true
                    onEntered: emojiGrid.currentIndex = index
                    onClicked: root.activateEmoji(modelData)
                }
            }
        }

        // ── Emoji / special characters tabs (Tab switches) ─────────────────────
        Item {
            id: emojiTabs
            visible: root.modeEmoji
            anchors { top: searchBar.bottom; left: parent.left; right: parent.right }
            height: visible ? 38 : 0
            Row {
                anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                spacing: 6
                Repeater {
                    model: ["emoji", "special"]
                    delegate: Rectangle {
                        required property string modelData
                        required property int index
                        readonly property bool active: root.emojiTab === index
                        height: 26; width: tabText.implicitWidth + 24; radius: 13
                        color: active ? root.acSel : (tabMouse.containsMouse ? root.hover : "transparent")
                        border.width: 1; border.color: active ? root.accentColor : root.sep
                        Text {
                            id: tabText
                            anchors.centerIn: parent
                            text: Lang.get("search.tab." + parent.modelData, root.uiLanguage)
                            color: parent.active ? root.fg : root.fgSub
                            font.pixelSize: 12; font.bold: parent.active
                        }
                        MouseArea {
                            id: tabMouse
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { root.emojiTab = index; emojiGrid.currentIndex = 0; searchField.forceActiveFocus() }
                        }
                    }
                }
            }
        }

        // ── Type filter chips ────────────────────────────────────────────────
        Item {
            id: chipBar
            visible: !root.modeEmoji && !root.showClip && !root.modeRun
            anchors { left: parent.left; right: parent.right; bottom: keyBar.top }
            height: visible ? 38 : 0
            Row {
                anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                spacing: 6
                Repeater {
                    model: root.chipKinds
                    delegate: Rectangle {
                        required property string modelData
                        required property int index
                        readonly property bool active: root.activeChip === index
                        height: 26; width: chipText.implicitWidth + 22; radius: 13
                        color: active ? root.acSel : (chipMouse.containsMouse ? root.hover : "transparent")
                        border.width: 1
                        border.color: active ? root.accentColor : root.sep
                        Text {
                            id: chipText
                            anchors.centerIn: parent
                            text: Lang.get("search.chip." + (parent.modelData === "" ? "all" : parent.modelData), root.uiLanguage)
                            color: parent.active ? root.fg : root.fgSub
                            font.pixelSize: 12; font.bold: parent.active
                        }
                        MouseArea {
                            id: chipMouse
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (index === 0 && root.parsed.kind !== "") searchField.text = root.parsed.text
                                root.chipIndex = index
                                searchField.forceActiveFocus()
                            }
                        }
                    }
                }
            }
        }

        // ── Key hints ────────────────────────────────────────────────────────
        Item {
            id: keyBar
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 30
            Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 12; rightMargin: 12 } height: 1; color: root.sep }
            Text {
                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 16; right: parent.right; rightMargin: 16 }
                elide: Text.ElideRight
                text: root.modeEmoji ? Lang.get("search.keysEmoji", root.uiLanguage) : Lang.get("search.keys", root.uiLanguage)
                color: root.fgSub; font.pixelSize: 11
            }
        }

        // ── Results ListView ─────────────────────────────────────────────────
        ListView {
            id: resultsList
            anchors {
                top: searchBar.bottom
                left: parent.left
                right: parent.right
                bottom: chipBar.top
                topMargin: 4
            }
            visible: !root.modeEmoji
            clip: true
            model: flatModel
            currentIndex: root.selIdx
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 6 }

            onCurrentIndexChanged: {
                if (currentIndex >= 0)
                    positionViewAtIndex(currentIndex, ListView.Contain)
            }

            delegate: Item {
                id: delegItem
                width: resultsList.width
                height: model.type === "header"    ? 28
                      : model.type === "calc"      ? 66
                      : model.type === "file"      ? 54
                      : model.type === "empty"     ? 110
                      : model.type === "webSearch" ? 44
                      : model.type === "app"       ? 50
                      : 46  // hint, clip, run

                // ── HEADER ─────────────────────────────────────────────────
                Text {
                    visible: model.type === "header"
                    anchors {
                        left: parent.left
                        leftMargin: 10
                        verticalCenter: parent.verticalCenter
                    }
                    text: model.label || ""
                    color: root.secHdr
                    font.pixelSize: 11
                    font.bold: true
                    font.letterSpacing: 0.8
                }

                // ── HINT ───────────────────────────────────────────────────
                Rectangle {
                    visible: model.type === "hint"
                    anchors {
                        fill: parent
                        leftMargin: 6; rightMargin: 6; topMargin: 3; bottomMargin: 3
                    }
                    radius: root.borderRadius
                    color: root.selIdx === index ? root.acSel
                         : hintMouse.containsMouse ? root.hover : "transparent"

                    Text {
                        anchors {
                            left: parent.left; leftMargin: 14
                            verticalCenter: parent.verticalCenter
                        }
                        text: model.label || ""
                        color: root.fg
                        font.pixelSize: 14
                    }

                    Text {
                        anchors {
                            right: parent.right; rightMargin: 14
                            verticalCenter: parent.verticalCenter
                        }
                        text: Lang.get("search.hint", root.uiLanguage)
                        color: root.fgSub
                        font.pixelSize: 11
                    }

                    MouseArea {
                        id: hintMouse
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: root.selIdx = index
                        onClicked: root.activateHint(model.hintKey || "")
                    }
                }

                // ── CALC ───────────────────────────────────────────────────
                Rectangle {
                    visible: model.type === "calc"
                    anchors { fill: parent; margins: 4 }
                    radius: root.borderRadius
                    color: root.selIdx === index ? root.acSel
                         : calcMouse.containsMouse ? root.hover
                         : Qt.rgba(root.ac.r, root.ac.g, root.ac.b, 0.06)
                    border.width: 1
                    border.color: Qt.rgba(root.ac.r, root.ac.g, root.ac.b, 0.25)

                    Row {
                        anchors {
                            left: parent.left; leftMargin: 14
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 14
                        Text {
                            text: "="
                            color: root.accentColor
                            font.pixelSize: 22; font.bold: true
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2
                            Text { text: root.query; color: root.fgSub; font.pixelSize: 11 }
                            Text { text: model.value || ""; color: root.fg; font.pixelSize: 20; font.bold: true }
                        }
                    }
                    Text {
                        anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                        text: Lang.get("search.copy", root.uiLanguage)
                        color: root.fgSub; font.pixelSize: 12
                    }
                    MouseArea {
                        id: calcMouse
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: root.selIdx = index
                        onClicked: { root.copyText(model.value || ""); root.closeSearch() }
                    }
                }

                // ── APP ────────────────────────────────────────────────────
                Rectangle {
                    visible: model.type === "app"
                    anchors {
                        fill: parent
                        leftMargin: 4; rightMargin: 8; topMargin: 3; bottomMargin: 3
                    }
                    radius: root.borderRadius
                    color: root.selIdx === index ? root.acSel
                         : appMouse.containsMouse ? root.hover : "transparent"

                    Row {
                        anchors {
                            left: parent.left; leftMargin: 12
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 12
                        Image {
                            width: 28; height: 28
                            sourceSize.width: 56; sourceSize.height: 56
                            anchors.verticalCenter: parent.verticalCenter
                            source: model.type === "app"
                                ? (model.appCustomIcon
                                    ? "img/" + (model.appIcon || "") + ".svg"
                                    : "image://icon/" + (model.appIcon || ""))
                                : ""
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                        Text {
                            textFormat: Text.StyledText
                            text: Logic.highlight(model.appName || "", root.searchText, root.accentColor)
                            color: root.fg; font.pixelSize: 15
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    // The row Enter would start gets a small key hint.
                    Text {
                        visible: root.selIdx === index
                        anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                        text: "↵  " + Lang.get("search.open", root.uiLanguage)
                        color: root.fgSub; font.pixelSize: 11
                    }
                    MouseArea {
                        id: appMouse
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: root.selIdx = index
                        onClicked: root.activateAppItem(model)
                    }
                }

                // ── FILE ───────────────────────────────────────────────────
                Rectangle {
                    visible: model.type === "file"
                    anchors {
                        fill: parent
                        leftMargin: 4; rightMargin: 8; topMargin: 3; bottomMargin: 3
                    }
                    radius: root.borderRadius
                    color: root.selIdx === index ? root.acSel
                         : fileMouse.containsMouse ? root.hover : "transparent"

                    Item {
                        id: fileEmoIcon
                        width: 34; height: 34
                        anchors {
                            left: parent.left; leftMargin: 12
                            verticalCenter: parent.verticalCenter
                        }
                        readonly property bool isDir: model.type === "file" && model.value === "dir"
                        readonly property bool isImage: model.type === "file" && !isDir && Logic.extensionsFor("images").indexOf((model.filePath || "").split(".").pop().toLowerCase()) >= 0
                        // Pictures show a small preview of themselves.
                        Image {
                            anchors.fill: parent
                            visible: fileEmoIcon.isImage && status === Image.Ready
                            source: fileEmoIcon.isImage ? "file://" + model.filePath : ""
                            sourceSize.width: 68; sourceSize.height: 68
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            layer.enabled: true
                        }
                        Image {
                            anchors.centerIn: parent
                            width: 30; height: 30
                            visible: fileEmoIcon.isDir
                            source: Qt.resolvedUrl("img/folder.svg")
                            sourceSize.width: 60; sourceSize.height: 60
                            fillMode: Image.PreserveAspectFit
                        }
                        ProjectIcon {
                            anchors.centerIn: parent
                            visible: !fileEmoIcon.isImage && !fileEmoIcon.isDir
                            name: model.type === "file" ? root.fileIcon(model.filePath || "") : "info"
                            font.pixelSize: 20
                        }
                    }
                    Column {
                        anchors {
                            left: fileEmoIcon.right; leftMargin: 10
                            right: parent.right; rightMargin: 12
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 2
                        Text {
                            textFormat: Text.StyledText
                            text: model.type === "file" ? Logic.highlight(root.basename(model.filePath || ""), root.searchText, root.accentColor) : ""
                            color: root.fg; font.pixelSize: 14
                            elide: Text.ElideRight; width: parent.width
                        }
                        Text {
                            text: model.type === "file" ? root.dirpart(model.filePath || "") : ""
                            color: root.fgSub; font.pixelSize: 11
                            elide: Text.ElideRight; width: parent.width
                        }
                    }
                    MouseArea {
                        id: fileMouse
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: root.selIdx = index
                        onClicked: root.activateFile(model.filePath || "")
                    }
                }

                // ── CLIP ───────────────────────────────────────────────────
                Rectangle {
                    visible: model.type === "clip"
                    anchors {
                        fill: parent
                        leftMargin: 4; rightMargin: 8; topMargin: 3; bottomMargin: 3
                    }
                    radius: root.borderRadius
                    color: root.selIdx === index ? root.acSel
                         : clipMouse.containsMouse ? root.hover : "transparent"

                    ProjectIcon {
                        id: clipIcon
                        anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                        name: "info"; font.pixelSize: 16
                    }
                    Text {
                        anchors {
                            left: clipIcon.right; leftMargin: 10
                            right: parent.right; rightMargin: 12
                            verticalCenter: parent.verticalCenter
                        }
                        text: {
                            var t = model.clipText || ""
                            var ti = t.indexOf("\t")
                            if (ti >= 0) t = t.substring(ti + 1)
                            return t.replace(/\n/g, " ")
                        }
                        color: root.fg; font.pixelSize: 13
                        elide: Text.ElideRight
                    }
                    MouseArea {
                        id: clipMouse
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: root.selIdx = index
                        onClicked: root.activateClipText(model.clipText || "")
                    }
                }

                // ── RUN ────────────────────────────────────────────────────
                Rectangle {
                    visible: model.type === "run" || model.type === "term"
                    anchors {
                        fill: parent
                        leftMargin: 4; rightMargin: 8; topMargin: 3; bottomMargin: 3
                    }
                    radius: root.borderRadius
                    color: root.selIdx === index ? root.acSel
                         : runMouse.containsMouse ? root.hover
                         : Qt.rgba(root.ac.r, root.ac.g, root.ac.b, 0.04)
                    border.width: 1
                    border.color: Qt.rgba(root.ac.r, root.ac.g, root.ac.b, 0.18)

                    Row {
                        anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                        spacing: 10
                        Text {
                            text: model.type === "term" ? ">_" : "▶"
                            color: root.accentColor; font.pixelSize: 14; font.bold: true
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter; spacing: 2
                            Text {
                                text: Lang.get(model.type === "term" ? "search.runInTerminal" : "search.runCommand", root.uiLanguage)
                                color: root.fgSub; font.pixelSize: 11
                            }
                            Text {
                                text: model.label || ""
                                color: root.fg; font.pixelSize: 14; font.bold: true
                            }
                        }
                    }
                    Text {
                        anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                        text: "↵"
                        color: root.fgSub; font.pixelSize: 16
                    }
                    MouseArea {
                        id: runMouse
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: root.selIdx = index
                        onClicked: model.type === "term" ? root.activateRunTerminal(model.appCmd || "") : root.activateRunCmd(model.appCmd || "")
                    }
                }

                // ── WEB SEARCH ─────────────────────────────────────────────
                Rectangle {
                    visible: model.type === "webSearch"
                    anchors {
                        fill: parent
                        leftMargin: 4; rightMargin: 8; topMargin: 3; bottomMargin: 3
                    }
                    radius: root.borderRadius
                    color: root.selIdx === index ? root.acSel
                         : webMouse.containsMouse ? root.hover : "transparent"

                    Row {
                        anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                        spacing: 10
                        ProjectIcon {
                            name: "network"
                            font.pixelSize: 18
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter; spacing: 2
                            Text {
                                text: Lang.get("search.webSearch", root.uiLanguage)
                                color: root.fgSub; font.pixelSize: 11
                            }
                            Text {
                                text: model.label || ""
                                color: root.fg; font.pixelSize: 13
                            }
                        }
                    }
                    MouseArea {
                        id: webMouse
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: root.selIdx = index
                        onClicked: root.activateWebSearch(model.label || "")
                    }
                }

                // ── EMPTY ──────────────────────────────────────────────────
                Column {
                    visible: model.type === "empty"
                    anchors.centerIn: parent
                    spacing: 8
                    ProjectIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        name: "search"; font.pixelSize: 28
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: Lang.get("search.noResults", root.uiLanguage)
                        color: root.fgSub; font.pixelSize: 14
                    }
                }

            } // delegate
        } // ListView
    } // Item
}
