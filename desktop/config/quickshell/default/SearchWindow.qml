import QtQuick
import "widgets"
import QtQuick.Controls
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import "i18n/Lang.js" as Lang

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

    // Derived modes
    readonly property bool modeEmoji: query.startsWith(":")
    readonly property bool modeRun:   query.startsWith(">")
    readonly property bool showHints: query.length === 0 && !showClip
    readonly property bool modeMath: {
        if (modeEmoji || modeRun || query.length < 2) return false
        var q = query.replace(/\b(sqrt|sin|cos|tan|log|ln|pi|abs|pow|round|floor|ceil|exp)\b/g, "0")
        return /^[\d\s\+\-\*\/\.\(\)\^%eE]+$/.test(q)
    }

    // ── Emoji data ───────────────────────────────────────────────────────────
    readonly property var emojiData: [
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

    readonly property var filteredEmoji: {
        if (!modeEmoji) return []
        var q = query.substring(1).toLowerCase().trim()
        if (q.length === 0) return emojiData.slice(0, 40)
        var res = []
        for (var i = 0; i < emojiData.length; i++) {
            var em = emojiData[i]
            if (res.length >= 60) break
            if (em.n.indexOf(q) !== -1) { res.push(em); continue }
            for (var j = 0; j < em.k.length; j++) {
                if (em.k[j].indexOf(q) !== -1) { res.push(em); break }
            }
        }
        return res
    }

    // ── Flat model for ListView ───────────────────────────────────────────────
    ListModel { id: flatModel }

    function rebuildModel() {
        flatModel.clear()

        // ─ Hint screen (empty, no clipboard mode) ─
        if (showHints) {
            flatModel.append({type:"hint", hintKey:"calc",  label:"= "   + Lang.get("search.hintCalc",  uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            flatModel.append({type:"hint", hintKey:"emoji", label: Lang.get("search.hintEmoji", uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            flatModel.append({type:"hint", hintKey:"clip",  label: Lang.get("search.hintClip",  uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            flatModel.append({type:"hint", hintKey:"run",   label:"> "   + Lang.get("search.hintRun",   uiLanguage), filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            selIdx = -1
            return
        }

        if (modeEmoji) { selIdx = -1; return }  // handled by GridView

        // ─ Run command mode ─
        if (modeRun) {
            var cmd = query.substring(1).trim()
            if (cmd.length > 0) {
                flatModel.append({type:"run", label:cmd, hintKey:"", filePath:"", clipText:"", appName:"", appCmd:cmd, appIcon:"", appCustomIcon:false, value:""})
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

        // Apps
        if (appResults.length > 0) {
            flatModel.append({type:"header", label:Lang.get("search.apps", uiLanguage), hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            for (var i = 0; i < appResults.length; i++) {
                var a = appResults[i]
                flatModel.append({type:"app", label:"", hintKey:"", filePath:"", clipText:"",
                    appName:a.name, appCmd:a.cmd, appIcon:a.icon, appCustomIcon:a.customIcon, value:""})
            }
        }

        // Files
        if (fileResults.length > 0) {
            flatModel.append({type:"header", label:Lang.get("search.files", uiLanguage), hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            for (var j = 0; j < fileResults.length; j++) {
                flatModel.append({type:"file", label:"", hintKey:"", filePath:fileResults[j], clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
            }
        }

        // Web search (always shown when query >= 2 chars)
        if (query.length >= 2) {
            flatModel.append({type:"webSearch", label:query, hintKey:"", filePath:"", clipText:"", appName:"", appCmd:"", appIcon:"", appCustomIcon:false, value:""})
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
    // Clipboard filter: rebuild when query changes in clip mode
    onQueryChanged: { if (showClip) Qt.callLater(rebuildModel) }

    // ── Keyboard nav ─────────────────────────────────────────────────────────
    function navUp() {
        var next = selIdx - 1
        while (next >= 0 && flatModel.get(next).type === "header") next--
        if (next >= 0) selIdx = next
    }

    function navDown() {
        var next = selIdx + 1
        while (next < flatModel.count && flatModel.get(next).type === "header") next++
        if (next < flatModel.count) selIdx = next
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
        if (item.type === "webSearch") { activateWebSearch(item.label); return }
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

    function activateEmoji(em) {
        closeSearch()
        copyText(em.e)
    }

    function activateRunCmd(cmd) {
        closeSearch()
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root)
        p.command = ["bash", "-c", cmd + " & disown"]
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

    function updateApps() {
        if (!appsModel || query.length === 0 || modeEmoji || modeRun || showClip) { appResults = []; return }
        var q = query.toLowerCase()
        var res = []
        for (var i = 0; i < appsModel.count && res.length < 5; i++) {
            var a = appsModel.get(i)
            if (a.name.toLowerCase().indexOf(q) !== -1 || (a.cmd && a.cmd.toLowerCase().indexOf(q) !== -1))
                res.push({name:a.name, cmd:a.cmd, icon:a.icon, customIcon:a.customIcon})
        }
        appResults = res
    }

    // ── Public API ────────────────────────────────────────────────────────────
    function openSearch() {
        query = ""; selIdx = -1; calcResult = ""; calcError = false
        fileResults = []; appResults = []; clipResults = []; showClip = false
        searchField.text = ""
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
        windows: [root]
        active: root.visible
        onCleared: root.closeSearch()
    }

    Process {
        id: fileProc
        stdout: StdioCollector {
            onStreamFinished: root.fileResults = text.trim().split("\n").filter(function(l){ return l.length > 0 })
        }
        stderr: StdioCollector {}
    }

    Process {
        id: calcProc
        stdout: StdioCollector {
            onStreamFinished: {
                var r = text.trim()
                if (r.length > 0) { root.calcResult = r; root.calcError = false }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim().length > 0) { root.calcError = true; root.calcResult = "" }
            }
        }
    }

    Process {
        id: clipProc
        command: ["bash", "-c", "cliphist list 2>/dev/null | head -50"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: root.clipResults = text.trim().split("\n").filter(function(l){ return l.length > 0 })
        }
    }

    Timer {
        id: debounce
        interval: 200
        onTriggered: {
            root.updateApps()
            var q = root.query
            if (q.length >= 2 && !root.modeEmoji && !root.modeRun && !root.showClip) {
                fileProc.running = false
                fileProc.command = ["bash", "-c",
                    "(fd --max-results 8 --type f --ignore-case -- " + JSON.stringify(q) + " \"$HOME\" 2>/dev/null || " +
                    "find \"$HOME\" -maxdepth 5 -iname " + JSON.stringify("*" + q + "*") + " -type f 2>/dev/null | head -8) | head -8"]
                fileProc.running = true
            } else {
                root.fileResults = []
            }
            if (root.modeMath) {
                var expr = q.replace(/\^/g, "**").replace(/\bln\b/g, "log")
                calcProc.running = false
                calcProc.command = ["python3", "-c",
                    "import math\ntry:\n" +
                    " r=eval('" + expr.replace(/\\/g, "\\\\").replace(/'/g, "\\'") + "',{'__builtins__':{}},{k:getattr(math,k) for k in dir(math) if not k.startswith('_')})\n" +
                    " print(round(r,10) if isinstance(r,float) else r)\n" +
                    "except: pass"]
                calcProc.running = true
            } else {
                root.calcResult = ""
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
                    source: "img/Win11-dark/actions/symbolic/edit-find-symbolic.svg"
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
                Keys.onReturnPressed: root.launchSelected()
                Keys.onTabPressed:    root.launchSelected()
                Keys.onUpPressed: {
                    if (root.modeEmoji) emojiGrid.moveCurrentIndexUp()
                    else root.navUp()
                }
                Keys.onDownPressed: {
                    if (root.modeEmoji) emojiGrid.moveCurrentIndexDown()
                    else root.navDown()
                }
                Keys.onLeftPressed:  { if (root.modeEmoji) emojiGrid.moveCurrentIndexLeft() }
                Keys.onRightPressed: { if (root.modeEmoji) emojiGrid.moveCurrentIndexRight() }

                onTextChanged: {
                    root.query = text
                    if (!root.showClip) {
                        if (text.length === 0) {
                            root.fileResults = []; root.calcResult = ""; root.calcError = false
                        }
                        debounce.restart()
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
                top: searchBar.bottom
                left: parent.left
                right: parent.right
                bottom: parent.bottom
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

        // ── Results ListView ─────────────────────────────────────────────────
        ListView {
            id: resultsList
            anchors {
                top: searchBar.bottom
                left: parent.left
                right: parent.right
                bottom: parent.bottom
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
                      : model.type === "file"      ? 50
                      : model.type === "empty"     ? 110
                      : model.type === "webSearch" ? 44
                      : 46  // hint, app, clip, run

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
                        spacing: 10
                        Image {
                            width: 22; height: 22
                            anchors.verticalCenter: parent.verticalCenter
                            source: model.type === "app"
                                ? (model.appCustomIcon
                                    ? "img/" + (model.appIcon || "") + ".svg"
                                    : "image://icon/" + (model.appIcon || ""))
                                : ""
                            fillMode: Image.PreserveAspectFit
                        }
                        Text {
                            text: model.appName || ""
                            color: root.fg; font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
                        }
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

                    ProjectIcon {
                        id: fileEmoIcon
                        anchors {
                            left: parent.left; leftMargin: 12
                            verticalCenter: parent.verticalCenter
                        }
                        name: model.type === "file" ? root.fileIcon(model.filePath || "") : "info"
                        font.pixelSize: 20
                    }
                    Column {
                        anchors {
                            left: fileEmoIcon.right; leftMargin: 10
                            right: parent.right; rightMargin: 12
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 2
                        Text {
                            text: model.type === "file" ? root.basename(model.filePath || "") : ""
                            color: root.fg; font.pixelSize: 13
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
                    visible: model.type === "run"
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
                            text: "▶"
                            color: root.accentColor; font.pixelSize: 14; font.bold: true
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter; spacing: 2
                            Text {
                                text: Lang.get("search.runCommand", root.uiLanguage)
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
                        onClicked: root.activateRunCmd(model.appCmd || "")
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
