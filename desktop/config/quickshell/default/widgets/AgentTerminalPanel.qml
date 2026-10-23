import Quickshell
import QtQuick
import Quickshell.Io
import org.kde.syntaxhighlighting
import "."
// Native QML plugin: resolved through QML_IMPORT_PATH (extras/start-quickshell.sh);
// Quickshell serves this directory as qs:@ URLs, from which Qt cannot load plugins.
import LocalTerminal as LocalTerminal
import "../i18n/Lang.js" as Lang

Item {
    id: terminalPanel

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property bool darkMode: true
    property bool windowVisible: false
    property string uiLanguage: "de"
    property bool isPinned: true
    property var switchToChat: null

    property string activeProfile: "claude"
    property string workingDirectory: Quickshell.env("HOME") + "/.config/quickshell/default"
    readonly property string claudeProjectDirectory: Quickshell.env("HOME")
        + "/.claude/projects/" + workingDirectory.replace(/[^a-zA-Z0-9]/g, "-")


    readonly property color bgColor: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.97) : Qt.rgba(0.97, 0.97, 0.97, 0.97)
    readonly property color sidebarColor: darkMode ? Qt.rgba(0.09, 0.09, 0.09, 0.95) : Qt.rgba(0.93, 0.93, 0.93, 0.95)
    readonly property color borderColor: darkMode ? "#2a2a2f" : "#c0c0c0"
    readonly property color surfaceColor: darkMode ? Qt.rgba(0.18, 0.18, 0.18, 1) : Qt.rgba(0.92, 0.92, 0.92, 1)
    readonly property color mutedColor: darkMode ? "#8a8a8f" : "#777777"
    readonly property color textColor: darkMode ? "#e8e8e8" : "#1a1a1a"

    // ── Shared chat state (claude + codex) ───────────────────────────────────
    property string claudeSessionId: ""
    property string codexSessionId: ""
    property bool   claudeRunning: false
    property var    claudeMessages: []   // [{role:"user"|"assistant", text:"..."}]
    property string claudeStreamText: "" // accumulates during streaming
    property int    claudeOutputOffset: 0
    property var    claudeSessions: []   // [{id, title, ts}] — past Claude sessions
    property var    codexSessions:  []   // [{id, title, ts, file}] — past Codex sessions

    property string claudeApiKey: ""
    property string openaiApiKey: ""

    property string activeModel: claudeCodeModels[0]
    property bool   showModelDropdown: false
    property bool   _bubbleMenuVisible: false
    property string _bubbleMenuText: ""
    property bool   showScrollButtons: false
    property string scrollButtonsTarget: ""
    property int _timeNowMs: Date.now()
    property bool usageLimitLoading: false
    property int usageLimitRetryAfter: 0
    property int usageLimitRequestLimit: 0
    property int usageLimitRequestRemaining: 0
    property string usageLimitRequestResetAt: ""
    property int usageLimitTokenLimit: 0
    property int usageLimitTokenRemaining: 0
    property string usageLimitTokenResetAt: ""
    property int usageLimitInputTokenLimit: 0
    property int usageLimitInputTokenRemaining: 0
    property string usageLimitInputTokenResetAt: ""
    property int usageLimitOutputTokenLimit: 0
    property int usageLimitOutputTokenRemaining: 0
    property string usageLimitOutputTokenResetAt: ""
    property string usageLimitError: ""
    property string usageLimitDebugSummary: ""
    property var usageRows: []
    property var lastGoodUsageRows: []
    property var usageCache: ({})
    property int usageRefreshIntervalMs: 5000
    property int lastUsageRefreshAtMs: 0
    property int usageBackoffUntilMs: 0
    property bool usageRefreshPending: false
    property var claudeCodeModels: ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
                                    "claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022"]
    property var codexModels: ["codex-mini-latest", "o4-mini", "o3", "o3-mini", "o1"]

    function profileLabel(p) {
        if (p === "shell")  return "Shell"
        if (p === "codex")  return "Codex"
        if (p === "claude") return "Claude Code"
        return p
    }

    function tr(key) {
        return Lang.get(key, uiLanguage)
    }

    function maxScrollY(flickable) {
        if (!flickable) return 0
        return Math.max(0, flickable.contentHeight - flickable.height)
    }

    function showScrollButtonsFor(target) {
        scrollButtonsTarget = target
        showScrollButtons = true
        scrollButtonTimer.restart()
    }

    function supportsLiveUsageLimits() {
        return activeProfile === "codex" || activeProfile === "claude"
    }

    function currentUsageSessionId() {
        return activeProfile === "codex" ? codexSessionId : claudeSessionId
    }

    function currentUsageCacheKey() {
        if (activeProfile === "claude")
            return "claude:" + activeModel
        if (activeProfile === "codex")
            return "codex:" + currentUsageSessionId() + ":" + activeModel
        return activeProfile + ":" + activeModel
    }

    function currentUsageRefreshIntervalMs() {
        return activeProfile === "claude" ? 60000 : usageRefreshIntervalMs
    }

    function currentUsageBackoffMs() {
        return activeProfile === "claude" ? 5 * 60 * 1000 : currentUsageRefreshIntervalMs()
    }

    function usageCacheEntry() {
        var key = currentUsageCacheKey()
        return usageCache[key] || null
    }

    function applyUsageCache(entry) {
        if (!entry) return false
        usageRows = entry.rows || []
        lastGoodUsageRows = entry.lastGoodRows || entry.rows || []
        usageLimitError = entry.error || ""
        usageLimitDebugSummary = entry.debug || ""
        lastUsageRefreshAtMs = entry.fetchedAtMs || 0
        usageBackoffUntilMs = entry.backoffUntilMs || 0
        return true
    }

    function storeUsageCache(rows, error, debug, backoffUntilMs) {
        var key = currentUsageCacheKey()
        var cache = {}
        for (var existingKey in usageCache)
            cache[existingKey] = usageCache[existingKey]
        cache[key] = {
            rows: rows || [],
            lastGoodRows: (rows && rows.length > 0) ? rows : lastGoodUsageRows,
            error: error || "",
            debug: debug || "",
            fetchedAtMs: Date.now(),
            backoffUntilMs: backoffUntilMs || 0
        }
        usageCache = cache
    }

    function currentLimitApiKey() {
        if (activeProfile === "claude") return claudeApiKey
        if (activeProfile === "codex") return openaiApiKey
        return ""
    }

    function currentLimitProvider() {
        if (activeProfile === "claude") return "claude"
        if (activeProfile === "codex") return "openai"
        return ""
    }

    function resetUsageLimitInfo() {
        usageLimitLoading = false
        usageLimitRetryAfter = 0
        usageLimitRequestLimit = 0
        usageLimitRequestRemaining = 0
        usageLimitRequestResetAt = ""
        usageLimitTokenLimit = 0
        usageLimitTokenRemaining = 0
        usageLimitTokenResetAt = ""
        usageLimitInputTokenLimit = 0
        usageLimitInputTokenRemaining = 0
        usageLimitInputTokenResetAt = ""
        usageLimitOutputTokenLimit = 0
        usageLimitOutputTokenRemaining = 0
        usageLimitOutputTokenResetAt = ""
        usageLimitError = ""
        usageLimitDebugSummary = ""
        usageRows = []
        lastGoodUsageRows = []
        usageBackoffUntilMs = 0
    }

    function parseResetMillis(value) {
        if (!value) return 0
        var raw = String(value).trim()
        if (raw === "") return 0
        if (/^\d+$/.test(raw)) {
            if (raw.length === 13) return parseInt(raw, 10)
            if (raw.length === 10) return parseInt(raw, 10) * 1000
            return 0
        }
        if (/^\d+(?:\.\d+)?[smhd]/.test(raw)) {
            var total = 0
            var re = /(\d+(?:\.\d+)?)(ms|s|m|h|d)/g
            var m
            while ((m = re.exec(raw)) !== null) {
                var n = parseFloat(m[1])
                var unit = m[2]
                if (unit === "ms") total += n
                else if (unit === "s") total += n * 1000
                else if (unit === "m") total += n * 60 * 1000
                else if (unit === "h") total += n * 60 * 60 * 1000
                else if (unit === "d") total += n * 24 * 60 * 60 * 1000
            }
            return _timeNowMs + total
        }
        var ms = Date.parse(raw)
        return isNaN(ms) ? 0 : ms
    }

    function secondsUntil(resetAt) {
        var target = parseResetMillis(resetAt)
        if (target <= 0) return 0
        var deltaMs = target - _timeNowMs
        if (deltaMs <= 0) return 0
        if (deltaMs < 1000) return 1
        var secs = Math.ceil(deltaMs / 1000)
        if (secs > 7 * 24 * 60 * 60) return 0
        return secs
    }

    function formatDurationShort(totalSeconds) {
        var secs = Math.max(0, Math.floor(totalSeconds))
        if (secs < 60) return secs + "s"
        var mins = Math.floor(secs / 60)
        var remSecs = secs % 60
        if (mins < 60) return mins + "m" + (remSecs > 0 ? " " + remSecs + "s" : "")
        var hours = Math.floor(mins / 60)
        var remMins = mins % 60
        if (hours < 24) return hours + "h" + (remMins > 0 ? " " + remMins + "m" : "")
        var days = Math.floor(hours / 24)
        var remHours = hours % 24
        return days + "d" + (remHours > 0 ? " " + remHours + "h" : "")
    }

    function formatCount(value) {
        if (value >= 1000000) return (value / 1000000).toFixed(value >= 10000000 ? 0 : 1) + "M"
        if (value >= 1000) return (value / 1000).toFixed(value >= 10000 ? 0 : 1) + "k"
        return String(value)
    }

    function formatUsageReset(row) {
        if (!row || !row.resetAtMs || row.resetAtMs <= 0)
            return row && row.detail ? row.detail : ""
        var d = new Date(row.resetAtMs)
        var now = new Date(_timeNowMs)
        var hh = d.getHours().toString().padStart(2, "0")
        var mm = d.getMinutes().toString().padStart(2, "0")
        var sameDay = d.getFullYear() === now.getFullYear()
                   && d.getMonth() === now.getMonth()
                   && d.getDate() === now.getDate()
        var prefix = row.detail && row.detail !== "" ? row.detail + " · " : ""
        if (sameDay)
            return prefix + tr("agent.resetAt") + " " + hh + ":" + mm
        return prefix + tr("agent.resetAt") + " " + d.getDate() + "." + (d.getMonth() + 1).toString().padStart(2, "0") + " " + hh + ":" + mm
    }

    function usageRowPercentText(row) {
        if (!row) return ""
        if (row.remainingPercent >= 0)
            return row.remainingPercent + "% " + tr("agent.left")
        return row.stateText || tr("agent.notAvailable")
    }

    function usageRowRatio(row) {
        if (!row || row.remainingPercent < 0) return 0
        return Math.max(0, Math.min(1, (100 - row.remainingPercent) / 100))
    }

    function isApproxContextDetail(detail) {
        var text = String(detail || "")
        return text.indexOf("~") === 0 && text.indexOf("/") > 1
    }

    function formatUsageRowDetail(row) {
        if (!row) return ""
        var detail = String(row.detail || "")
        if (row.label === "Context" && isApproxContextDetail(detail)) {
            var parts = detail.slice(1).split("/")
            if (parts.length === 2)
                return tr("agent.approx") + " " + formatCount(parseInt(parts[0], 10)) + " / " + formatCount(parseInt(parts[1], 10))
        }
        if (detail !== "") return detail
        return formatUsageReset(row)
    }

    function compactUsageLabel(row) {
        if (!row) return ""
        if (row.label === "5h-Limit") return tr("agent.limit5hShort")
        if (row.label === "Woche") return tr("agent.week")
        if (row.label === "Context") return tr("agent.context")
        if (row.label === "Extra") return tr("agent.extra")
        if (row.label === "Heute") return tr("agent.today")
        if (row.label === "Kosten") return tr("agent.cost")
        if (row.label === "Credits") return tr("agent.credits")
        if (row.label === "Requests") return tr("agent.requests")
        if (row.label === "Tokens") return tr("agent.tokens")
        if (row.label === "Input") return tr("agent.input")
        if (row.label === "Output") return tr("agent.output")
        return row.label
    }

    function compactUsageText(row) {
        if (!row) return ""
        var parts = [compactUsageLabel(row)]
        var pct = usageRowPercentText(row)
        if (pct !== "")
            parts.push(pct)
        var detail = formatUsageRowDetail(row)
        if (detail !== "")
            parts.push(detail)
        return parts.join("  ")
    }

    function dominantUsageMetric() {
        var metrics = []
        if (usageLimitRequestLimit > 0) metrics.push({ label: "Requests", remaining: usageLimitRequestRemaining, limit: usageLimitRequestLimit, reset: usageLimitRequestResetAt, remainingRatio: usageLimitRequestRemaining / usageLimitRequestLimit })
        if (usageLimitTokenLimit > 0) metrics.push({ label: "Tokens", remaining: usageLimitTokenRemaining, limit: usageLimitTokenLimit, reset: usageLimitTokenResetAt, remainingRatio: usageLimitTokenRemaining / usageLimitTokenLimit })
        if (usageLimitInputTokenLimit > 0) metrics.push({ label: "Input", remaining: usageLimitInputTokenRemaining, limit: usageLimitInputTokenLimit, reset: usageLimitInputTokenResetAt, remainingRatio: usageLimitInputTokenRemaining / usageLimitInputTokenLimit })
        if (usageLimitOutputTokenLimit > 0) metrics.push({ label: "Output", remaining: usageLimitOutputTokenRemaining, limit: usageLimitOutputTokenLimit, reset: usageLimitOutputTokenResetAt, remainingRatio: usageLimitOutputTokenRemaining / usageLimitOutputTokenLimit })
        if (metrics.length === 0) return null
        metrics.sort(function(a, b) { return a.remainingRatio - b.remainingRatio })
        return metrics[0]
    }

    function hasLiveUsageMetric() {
        return dominantUsageMetric() !== null
    }

    function currentUsageRatio() {
        if (usageLimitRetryAfter > 0) return 1
        var metric = dominantUsageMetric()
        if (metric) return Math.max(0, Math.min(1, metric.remainingRatio))
        return 0
    }

    function usageCardTitle() {
        if (usageLimitRetryAfter > 0) return tr("agent.waitTime")
        if (!usageLimitLoading && !hasLiveUsageMetric()) return tr("agent.apiLimit")
        return tr("agent.apiAvailable")
    }

    function usageCardPercent() {
        if (usageLimitRetryAfter > 0) return "100%"
        if (!usageLimitLoading && !hasLiveUsageMetric()) return tr("agent.notAvailable")
        return Math.round(currentUsageRatio() * 100) + "%"
    }

    function usageCardDetail() {
        if (usageLimitLoading) return tr("agent.loadingCliStatus")
        if (usageLimitRetryAfter > 0) return tr("agent.wait") + " " + formatDurationShort(usageLimitRetryAfter)
        var metric = dominantUsageMetric()
        if (metric) {
            var resetSecs = secondsUntil(metric.reset)
            return compactUsageLabel({ label: metric.label }) + " " + tr("agent.available") + " " + formatCount(metric.remaining) + "/" + formatCount(metric.limit) +
                (resetSecs > 0 ? " · " + tr("agent.resetIn") + " " + formatDurationShort(resetSecs) : "")
        }
        return tr("agent.noLiveHeaders")
    }

    function refreshUsageLimitInfo() {
        if (!supportsLiveUsageLimits() || activeModel === "") {
            resetUsageLimitInfo()
            return
        }
        var nowMs = Date.now()
        var cached = usageCacheEntry()
        if (cached)
            applyUsageCache(cached)
        if (usageBackoffUntilMs > nowMs) {
            usageLimitLoading = false
            return
        }
        if (limitProbeProc.running) {
            usageRefreshPending = activeProfile !== "claude"
            return
        }
        if ((nowMs - lastUsageRefreshAtMs) < currentUsageRefreshIntervalMs()) {
            usageRefreshPending = activeProfile !== "claude"
            if (usageRefreshPending)
                usageRefreshTimer.restart()
            return
        }
        lastUsageRefreshAtMs = nowMs
        usageRefreshPending = false
        usageLimitLoading = true
        usageLimitError = ""
        limitProbeProc.command = ["python3", "-c",
            "import json, subprocess, sys, time\n" +
            "from pathlib import Path\n" +
            "\n" +
            "profile, model, session_id = sys.argv[1:4]\n" +
            "\n" +
            "def mins_label(mins):\n" +
            "    if mins == 300:\n" +
            "        return '5h-Limit'\n" +
            "    if mins == 10080:\n" +
            "        return 'Woche'\n" +
            "    if mins == 1440:\n" +
            "        return 'Tag'\n" +
            "    if mins:\n" +
            "        return f'{mins}m-Limit'\n" +
            "    return 'Limit'\n" +
            "\n" +
            "def latest_codex_window(session_id):\n" +
            "    root = Path.home() / '.codex' / 'sessions'\n" +
            "    candidates = []\n" +
            "    if session_id:\n" +
            "        candidates = sorted(root.rglob(f'*{session_id}*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)\n" +
            "    if not candidates:\n" +
            "        candidates = sorted(root.rglob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)[:12]\n" +
            "    for path in candidates:\n" +
            "        try:\n" +
            "            latest = 0\n" +
            "            for line in path.read_text(encoding='utf-8', errors='replace').splitlines():\n" +
            "                line = line.strip()\n" +
            "                if not line:\n" +
            "                    continue\n" +
            "                obj = json.loads(line)\n" +
            "                payload = obj.get('payload') or {}\n" +
            "                if obj.get('type') == 'event_msg':\n" +
            "                    if payload.get('type') == 'task_started' and payload.get('model_context_window'):\n" +
            "                        latest = int(payload.get('model_context_window') or 0)\n" +
            "                    info = payload.get('info') or {}\n" +
            "                    if info.get('model_context_window'):\n" +
            "                        latest = int(info.get('model_context_window') or 0)\n" +
            "            if latest > 0:\n" +
            "                return latest\n" +
            "        except Exception:\n" +
            "            pass\n" +
            "    return 0\n" +
            "\n" +
            "def codex_context_left(session_id):\n" +
            "    if not session_id:\n" +
            "        return None\n" +
            "    import fcntl, os, pty, re, select, struct, termios\n" +
            "    master, slave = pty.openpty()\n" +
            "    try:\n" +
            "        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))\n" +
            "        env = dict(os.environ)\n" +
            "        env['TERM'] = 'xterm-256color'\n" +
            "        env['COLORTERM'] = 'truecolor'\n" +
            "        proc = subprocess.Popen(['codex', 'resume', session_id, '--no-alt-screen'], stdin=slave, stdout=slave, stderr=slave, close_fds=True, env=env)\n" +
            "    finally:\n" +
            "        os.close(slave)\n" +
            "    buf = b''\n" +
            "    answered_update = False\n" +
            "    end = time.time() + 15\n" +
            "    try:\n" +
            "        while time.time() < end:\n" +
            "            ready, _, _ = select.select([master], [], [], 0.2)\n" +
            "            if not ready:\n" +
            "                continue\n" +
            "            chunk = os.read(master, 8192)\n" +
            "            if not chunk:\n" +
            "                break\n" +
            "            buf += chunk\n" +
            "            if b'\\x1b[6n' in buf:\n" +
            "                os.write(master, b'\\x1b[24;1R')\n" +
            "                buf = buf.replace(b'\\x1b[6n', b'')\n" +
            "            if b'\\x1b[c' in buf:\n" +
            "                os.write(master, b'\\x1b[?62;4;c')\n" +
            "                buf = buf.replace(b'\\x1b[c', b'')\n" +
            "            if b'\\x1b]10;?' in buf:\n" +
            "                os.write(master, b'\\x1b]10;rgb:ffff/ffff/ffff\\x1b\\\\')\n" +
            "                buf = buf.replace(b'\\x1b]10;?', b'')\n" +
            "            if b'\\x1b]11;?' in buf:\n" +
            "                os.write(master, b'\\x1b]11;rgb:0000/0000/0000\\x1b\\\\')\n" +
            "                buf = buf.replace(b'\\x1b]11;?', b'')\n" +
            "            if (not answered_update) and b'Update available' in buf:\n" +
            "                os.write(master, b'2\\r')\n" +
            "                answered_update = True\n" +
            "            if answered_update and b'% left' in buf:\n" +
            "                break\n" +
            "    finally:\n" +
            "        try:\n" +
            "            proc.terminate()\n" +
            "        except Exception:\n" +
            "            pass\n" +
            "        try:\n" +
            "            os.close(master)\n" +
            "        except Exception:\n" +
            "            pass\n" +
            "    text = buf.decode('utf-8', 'replace')\n" +
            "    text = re.sub(r'\\x1b\\[[0-?]*[ -/]*[@-~]', '', text)\n" +
            "    text = re.sub(r'\\x1b\\][^\\x07]*(?:\\x07|\\x1b\\\\)', '', text)\n" +
            "    text = re.sub(r'\\x1b[@-_]', '', text)\n" +
            "    matches = re.findall(r'(\\d+)% left', text)\n" +
            "    if not matches:\n" +
            "        return None\n" +
            "    return int(matches[-1])\n" +
            "\n" +
            "def codex_probe():\n" +
            "    proc = subprocess.Popen(['codex', 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)\n" +
            "    reqs = [\n" +
            "        {'jsonrpc': '2.0', 'id': '1', 'method': 'initialize', 'params': {'clientInfo': {'name': 'quickshell-agent-panel', 'title': 'quickshell-agent-panel', 'version': '1'}, 'capabilities': {'experimentalApi': True}}},\n" +
            "        {'jsonrpc': '2.0', 'id': '2', 'method': 'account/rateLimits/read', 'params': None},\n" +
            "    ]\n" +
            "    for req in reqs:\n" +
            "        proc.stdin.write(json.dumps(req) + '\\n')\n" +
            "        proc.stdin.flush()\n" +
            "    end = time.time() + 8\n" +
            "    payload = None\n" +
            "    errs = []\n" +
            "    while time.time() < end:\n" +
            "        line = proc.stdout.readline()\n" +
            "        if line:\n" +
            "            obj = json.loads(line)\n" +
            "            if obj.get('id') == '2':\n" +
            "                if 'result' in obj:\n" +
            "                    payload = obj['result']\n" +
            "                    break\n" +
            "                raise RuntimeError(obj.get('error', {}).get('message', 'rate limit read failed'))\n" +
            "        if proc.poll() is not None:\n" +
            "            break\n" +
            "    try:\n" +
            "        proc.kill()\n" +
            "    except Exception:\n" +
            "        pass\n" +
            "    if payload is None:\n" +
            "        raise RuntimeError('keine Codex-Rate-Limits erhalten')\n" +
            "    snap = ((payload.get('rateLimitsByLimitId') or {}).get('codex')) or payload.get('rateLimits') or {}\n" +
            "    rows = []\n" +
            "    ctx_left = codex_context_left(session_id)\n" +
            "    ctx_window = latest_codex_window(session_id)\n" +
            "    if ctx_left is not None:\n" +
            "        if ctx_window > 0:\n" +
            "            approx_used = int(round(ctx_window * (100 - int(ctx_left)) / 100.0))\n" +
            "            detail = '~' + str(approx_used) + '/' + str(ctx_window)\n" +
            "        else:\n" +
            "            detail = 'aktueller CLI-Status'\n" +
            "        rows.append({'label': 'Context', 'remainingPercent': max(0, min(100, int(ctx_left))), 'resetAtMs': 0, 'detail': detail, 'stateText': ''})\n" +
            "    for key in ('primary', 'secondary'):\n" +
            "        win = snap.get(key) or {}\n" +
            "        if win.get('usedPercent') is None:\n" +
            "            continue\n" +
            "        used = int(round(float(win.get('usedPercent', 0))))\n" +
            "        rows.append({'label': mins_label(win.get('windowDurationMins')), 'remainingPercent': max(0, 100 - used), 'resetAtMs': int(win.get('resetsAt') or 0) * 1000, 'detail': '', 'stateText': ''})\n" +
            "    credits = snap.get('credits') or {}\n" +
            "    if credits.get('hasCredits') and not credits.get('unlimited'):\n" +
            "        rows.append({'label': 'Credits', 'remainingPercent': -1, 'resetAtMs': 0, 'detail': 'Saldo $' + str(credits.get('balance') or '0'), 'stateText': '$' + str(credits.get('balance') or '0')})\n" +
            "    return {'rows': rows, 'debug': 'source=codex-app-server plan=' + str(snap.get('planType')) + ' rows=' + str(len(rows)) + (' ctx=' + str(ctx_left) + '%' if ctx_left is not None else '') + (' window=' + str(ctx_window) if ctx_window > 0 else '')}\n" +
            "\n" +
            "def find_claude_transcript(session_id):\n" +
            "    root = Path.home() / '.claude' / 'projects'\n" +
            "    if not root.exists():\n" +
            "        return None\n" +
            "    if session_id:\n" +
            "        matches = sorted(root.rglob(session_id + '.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)\n" +
            "        if matches:\n" +
            "            return matches[0]\n" +
            "    candidates = []\n" +
            "    for path in root.rglob('*.jsonl'):\n" +
            "        try:\n" +
            "            if '/subagents/' in str(path):\n" +
            "                continue\n" +
            "            candidates.append(path)\n" +
            "        except Exception:\n" +
            "            pass\n" +
            "    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)\n" +
            "    return candidates[0] if candidates else None\n" +
            "\n" +
            "def load_claude_oauth_token():\n" +
            "    cred_path = Path.home() / '.claude' / '.credentials.json'\n" +
            "    if not cred_path.exists():\n" +
            "        return None\n" +
            "    try:\n" +
            "        data = json.loads(cred_path.read_text(encoding='utf-8', errors='replace'))\n" +
            "        oauth = data.get('claudeAiOauth') or {}\n" +
            "        token = oauth.get('accessToken')\n" +
            "        if not token:\n" +
            "            return None\n" +
            "        expires_at = oauth.get('expiresAt')\n" +
            "        if expires_at and time.time() * 1000 > float(expires_at):\n" +
            "            return None\n" +
            "        return token\n" +
            "    except Exception:\n" +
            "        return None\n" +
            "\n" +
            "def fetch_oauth_usage(token):\n" +
            "    import urllib.request\n" +
            "    cache_path = Path.home() / '.claude' / '.qs-oauth-cache.json'\n" +
            "    try:\n" +
            "        if cache_path.exists():\n" +
            "            cache = json.loads(cache_path.read_text(encoding='utf-8', errors='replace'))\n" +
            "            if time.time() - cache.get('ts', 0) < 300:\n" +
            "                return cache.get('data'), False\n" +
            "    except Exception:\n" +
            "        pass\n" +
            "    req = urllib.request.Request(\n" +
            "        'https://api.anthropic.com/api/oauth/usage',\n" +
            "        headers={\n" +
            "            'Authorization': 'Bearer ' + token,\n" +
            "            'anthropic-beta': 'oauth-2025-04-20',\n" +
            "            'User-Agent': 'claude-code/1.0',\n" +
            "        }\n" +
            "    )\n" +
            "    with urllib.request.urlopen(req, timeout=10) as resp:\n" +
            "        data = json.loads(resp.read().decode('utf-8'))\n" +
            "    try:\n" +
            "        cache_path.write_text(json.dumps({'ts': time.time(), 'data': data}))\n" +
            "    except Exception:\n" +
            "        pass\n" +
            "    return data, True\n" +
            "\n" +
            "def claude_probe():\n" +
            "    path = find_claude_transcript(session_id)\n" +
            "    if path is None:\n" +
            "        raise RuntimeError('keine Claude-Sessiondaten gefunden')\n" +
            "    session_model = model or ''\n" +
            "    last_ctx_tokens = 0\n" +
            "    with open(path, encoding='utf-8', errors='replace') as fp:\n" +
            "        for raw_line in fp:\n" +
            "            line = raw_line.strip()\n" +
            "            if not line:\n" +
            "                continue\n" +
            "            try:\n" +
            "                obj = json.loads(line)\n" +
            "            except Exception:\n" +
            "                continue\n" +
            "            msg = obj.get('message') or {}\n" +
            "            if obj.get('type') == 'assistant' and not session_model:\n" +
            "                session_model = msg.get('model') or session_model\n" +
            "            usage = msg.get('usage') or {}\n" +
            "            inp = int(usage.get('input_tokens') or 0)\n" +
            "            cr  = int(usage.get('cache_read_input_tokens') or 0)\n" +
            "            cc_obj = usage.get('cache_creation') or {}\n" +
            "            cc5m = int(cc_obj.get('ephemeral_5m_input_tokens') or 0)\n" +
            "            cc1h = int(cc_obj.get('ephemeral_1h_input_tokens') or 0)\n" +
            "            cc_leg = int(usage.get('cache_creation_input_tokens') or 0)\n" +
            "            ctx = inp + cr + cc5m + cc1h + cc_leg\n" +
            "            if ctx > 0:\n" +
            "                last_ctx_tokens = ctx\n" +
            "    rows = []\n" +
            "    ctx_window = 200000\n" +
            "    if last_ctx_tokens > 0:\n" +
            "        ctx_left = max(0, min(100, int(round(100 - (last_ctx_tokens / float(ctx_window)) * 100))))\n" +
            "        rows.append({'label': 'Context', 'remainingPercent': ctx_left, 'resetAtMs': 0, 'detail': str(last_ctx_tokens) + '/' + str(ctx_window), 'stateText': ''})\n" +
            "    oauth_source = ''\n" +
            "    token = load_claude_oauth_token()\n" +
            "    if token:\n" +
            "        try:\n" +
            "            oauth_data, from_api = fetch_oauth_usage(token)\n" +
            "            oauth_source = 'live' if from_api else 'cache'\n" +
            "            if oauth_data:\n" +
            "                from datetime import datetime as _datetime\n" +
            "                for key, label in [('five_hour', '5h-Limit'), ('seven_day', 'Woche')]:\n" +
            "                    win = oauth_data.get(key) or {}\n" +
            "                    util = win.get('utilization')\n" +
            "                    if util is None:\n" +
            "                        continue\n" +
            "                    remaining_pct = max(0, min(100, int(round(100 - float(util)))))\n" +
            "                    resets_at_str = win.get('resets_at') or ''\n" +
            "                    reset_ms = 0\n" +
            "                    if resets_at_str:\n" +
            "                        try:\n" +
            "                            d = _datetime.fromisoformat(resets_at_str.replace('Z', '+00:00'))\n" +
            "                            reset_ms = int(d.timestamp() * 1000)\n" +
            "                        except Exception:\n" +
            "                            pass\n" +
            "                    rows.append({'label': label, 'remainingPercent': remaining_pct, 'resetAtMs': reset_ms, 'detail': '', 'stateText': ''})\n" +
            "                extra = oauth_data.get('extra_usage') or {}\n" +
            "                if extra.get('is_enabled') and (extra.get('monthly_limit') or 0) > 0:\n" +
            "                    used = float(extra.get('used_credits') or 0)\n" +
            "                    limit = float(extra.get('monthly_limit') or 0)\n" +
            "                    remaining_pct = max(0, min(100, int(round(100 - (used / limit * 100)))))\n" +
            "                    rows.append({'label': 'Extra', 'remainingPercent': remaining_pct, 'resetAtMs': 0, 'detail': '$' + ('%.2f' % (used/100)) + ' / $' + ('%.0f' % (limit/100)), 'stateText': '$' + ('%.2f' % (used/100))})\n" +
            "        except Exception:\n" +
            "            pass\n" +
            "    return {'rows': rows, 'debug': 'source=claude-local+oauth(' + oauth_source + ') rows=' + str(len(rows)) + ' model=' + str(session_model or model or '') + ' ctx=' + str(last_ctx_tokens) + ' transcript=' + path.name}\n" +
            "\n" +
            "try:\n" +
            "    result = codex_probe() if profile == 'codex' else claude_probe()\n" +
            "    print(json.dumps(result))\n" +
            "except Exception as e:\n" +
            "    print(json.dumps({'rows': [], 'error': str(e)}))\n",
            activeProfile,
            activeModel,
            currentUsageSessionId()
        ]
        limitProbeProc.running = true
    }

    // Parse one NDJSON line from claude --output-format stream-json
    function parseClaudeEvent(line) {
        if (!line) return
        try {
            var obj = JSON.parse(line)
            if (obj.session_id) claudeSessionId = obj.session_id
            // Streamed assistant content blocks
            if (obj.type === "assistant" && obj.message && obj.message.content) {
                for (var i = 0; i < obj.message.content.length; i++) {
                    var b = obj.message.content[i]
                    if (b.type === "text") claudeStreamText += b.text
                }
            }
            // Simple text streaming event
            if (obj.type === "text" && obj.text) claudeStreamText += obj.text
            // Final result — authoritative complete response
            if (obj.type === "result" && obj.subtype === "success" && obj.result) {
                claudeStreamText = obj.result
                if (obj.session_id) claudeSessionId = obj.session_id
            }
        } catch(e) {}
    }

    function sendClaude(message) {
        if (claudeRunning || !message.trim()) return

        // Append user message
        var msgs = claudeMessages.slice()
        msgs.push({role: "user", text: message.trim(), ts: Date.now()})
        claudeMessages = msgs
        claudeStreamText = ""
        claudeOutputOffset = 0

        // Build shell command — single-quote escape the user message
        var escaped = message.replace(/'/g, "'\\''")
        var wdEscaped = workingDirectory.replace(/'/g, "'\\''")
        var cmd = "cd '" + wdEscaped + "' && claude -p '" + escaped + "' --output-format stream-json --verbose"
        if (claudeSessionId) cmd += " --resume '" + claudeSessionId + "'"
        if (activeModel !== "") cmd += " --model '" + activeModel + "'"

        console.log("[Claude] Starting:", cmd)
        claudeProc.command = ["/usr/bin/bash", "-lc", cmd]
        claudeRunning = true
        claudeProc.running = true
    }

    // Parse one NDJSON line from codex exec --json
    function parseCodexEvent(line) {
        if (!line) return
        try {
            var obj = JSON.parse(line)
            if (obj.type === "thread.started" && obj.thread_id)
                codexSessionId = obj.thread_id
            if (obj.type === "item.completed" && obj.item && obj.item.type === "agent_message")
                claudeStreamText += obj.item.text
        } catch(e) {}
    }

    function sendCodex(message) {
        if (claudeRunning || !message.trim()) return

        var msgs = claudeMessages.slice()
        msgs.push({role: "user", text: message.trim(), ts: Date.now()})
        claudeMessages = msgs
        claudeStreamText = ""
        claudeOutputOffset = 0

        var escaped = message.replace(/'/g, "'\\''")
        var wdEscaped = workingDirectory.replace(/'/g, "'\\''")
        var cmd
        var modelFlag = activeModel !== "" ? " --model '" + activeModel + "'" : ""
        if (codexSessionId) {
            cmd = "cd '" + wdEscaped + "' && codex exec resume --json --skip-git-repo-check '" + codexSessionId + "' '" + escaped + "'" + modelFlag
        } else {
            cmd = "cd '" + wdEscaped + "' && codex exec --json --skip-git-repo-check --sandbox danger-full-access" + modelFlag + " -- '" + escaped + "'"
        }

        console.log("[Codex] Starting:", cmd)
        codexProc.command = ["/usr/bin/bash", "-lc", cmd]
        claudeRunning = true
        codexProc.running = true
    }

    function sendMessage(message) {
        if (activeProfile === "codex") sendCodex(message)
        else sendClaude(message)
    }

    // Clear conversation
    function resetClaude() {
        claudeMessages = []
        claudeStreamText = ""
        claudeSessionId = ""
        codexSessionId = ""
        claudeRunning = false
        claudeOutputOffset = 0
    }

    function formatMsgTs(ts) {
        if (!ts) return ""
        var d = new Date(ts)
        var now = new Date()
        var h = d.getHours().toString().padStart(2, "0")
        var m = d.getMinutes().toString().padStart(2, "0")
        var timeStr = uiLanguage === "de" ? h + ":" + m + " Uhr" : h + ":" + m
        var sameDay = d.getFullYear() === now.getFullYear()
                   && d.getMonth()    === now.getMonth()
                   && d.getDate()     === now.getDate()
        if (sameDay) return timeStr
        var deMonths = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
        var enMonths = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        var months = uiLanguage === "de" ? deMonths : enMonths
        var dateStr = uiLanguage === "de"
            ? d.getDate() + ". " + months[d.getMonth()] + ", " + timeStr
            : months[d.getMonth()] + " " + d.getDate() + ", " + timeStr
        return dateStr
    }

    // Format ISO timestamp for display in session list
    function formatTs(ts) {
        if (!ts) return ""
        var d = new Date(ts)
        var today = new Date()
        var h = d.getHours().toString().padStart(2, "0")
        var m = d.getMinutes().toString().padStart(2, "0")
        if (d.toDateString() === today.toDateString())
            return h + ":" + m
        var day = d.getDate().toString().padStart(2, "0")
        var mon = (d.getMonth() + 1).toString().padStart(2, "0")
        return day + "." + mon + " " + h + ":" + m
    }

    // List past Claude sessions from ~/.claude/projects/
    function loadSessions() {
        var script = `import json, sys
from pathlib import Path
project_dir = Path(sys.argv[1])
if not project_dir.exists():
    print("[]")
    exit()
sessions = []
for f in sorted(project_dir.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
    sid = f.stem
    title = None
    ts = None
    model = None
    try:
        with open(f) as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if ts is None and obj.get("timestamp"):
                        ts = obj["timestamp"]
                    if title is None and obj.get("type") == "user":
                        msg = obj.get("message", {})
                        c = msg.get("content", "")
                        if isinstance(c, list):
                            for b in c:
                                if isinstance(b, dict) and b.get("type") == "text":
                                    title = b["text"][:60]
                                    break
                        elif isinstance(c, str):
                            title = c[:60]
                    if model is None and obj.get("type") == "assistant":
                        msg = obj.get("message", {})
                        if isinstance(msg, dict) and msg.get("model"):
                            model = msg.get("model")
                    if title and ts and model:
                        break
                except:
                    pass
    except:
        pass
    sessions.append({"id": sid, "title": title or "Session", "ts": ts or "", "model": model or ""})
print(json.dumps(sessions, ensure_ascii=False))`
        listSessionsProc.command = ["python3", "-c", script, claudeProjectDirectory]
        listSessionsProc.running = true
    }

    // Delete a session file and refresh list
    function deleteSession(sessionId) {
        if (sessionId === claudeSessionId) resetClaude()
        deleteSessionProc.command = ["python3", "-c",
            "import re,sys; from pathlib import Path; sid=sys.argv[2]; "
            + "assert re.fullmatch(r'[a-zA-Z0-9_-]+',sid); "
            + "(Path(sys.argv[1])/(sid+'.jsonl')).unlink(missing_ok=True)",
            claudeProjectDirectory, sessionId]
        deleteSessionProc.running = true
    }

    // Resume a past session: load its messages then set session ID
    function resumeSession(sessionId) {
        var script = `import json, re, sys
from pathlib import Path
sid = sys.argv[2]
assert re.fullmatch(r'[a-zA-Z0-9_-]+', sid)
f = Path(sys.argv[1]) / (sid + ".jsonl")
msgs = []
model = ""
if f.exists():
    with open(f) as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == "user":
                    msg = obj.get("message", {})
                    c = msg.get("content", "")
                    if isinstance(c, list):
                        for b in c:
                            if isinstance(b, dict) and b.get("type") == "text":
                                msgs.append({"role": "user", "text": b["text"]})
                                break
                    elif isinstance(c, str) and c:
                        msgs.append({"role": "user", "text": c})
                elif obj.get("type") == "assistant":
                    msg = obj.get("message", {})
                    if not model and isinstance(msg, dict) and msg.get("model"):
                        model = msg.get("model")
                    c = msg.get("content", [])
                    if isinstance(c, list):
                        t = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                        if t:
                            msgs.append({"role": "assistant", "text": t})
            except:
                pass
print(json.dumps({"messages": msgs, "model": model}, ensure_ascii=False))`
        claudeSessionId = sessionId
        claudeStreamText = ""
        claudeRunning = false
        loadHistoryProc.command = ["python3", "-c", script, claudeProjectDirectory, sessionId]
        loadHistoryProc.running = true
    }

    // ── Codex session management ──────────────────────────────────────────────

    function loadCodexSessions() {
        var script = `import json, re
from pathlib import Path
sessions_dir = Path.home() / ".codex/sessions"
if not sessions_dir.exists():
    print("[]")
    exit()
result = []
for f in sorted(sessions_dir.rglob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
    sid = None
    ts = None
    title = None
    model = None
    try:
        with open(f, 'rb') as fp:
            content = fp.read().decode('utf-8', errors='replace')
        for line in content.split('\\n'):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                payload = obj.get('payload', {})
                if obj.get('type') == 'session_meta':
                    sid = payload.get('id')
                    ts = obj.get('timestamp')
                if model is None and obj.get('type') == 'turn_context':
                    model = payload.get('model') or ""
                if obj.get('type') == 'response_item' and payload.get('role') == 'user':
                    for block in payload.get('content', []):
                        if isinstance(block, dict) and block.get('type') == 'input_text':
                            text = block['text']
                            if text and not text.startswith('<') and not text.startswith('#'):
                                title = text[:60]
                                break
                if sid and title and model:
                    break
            except:
                pass
    except:
        pass
    if sid:
        result.append({"id": sid, "title": title or "Session", "ts": ts or "", "file": str(f), "model": model or ""})
print(json.dumps(result, ensure_ascii=False))`
        listCodexSessionsProc.command = ["python3", "-c", script]
        listCodexSessionsProc.running = true
    }

    function resumeCodexSession(sessionId, filePath) {
        var script = `import json
from pathlib import Path
f = Path("` + filePath + `")
msgs = []
model = ""
if f.exists():
    with open(f, 'rb') as fp:
        content = fp.read().decode('utf-8', errors='replace')
    for line in content.split('\\n'):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            payload = obj.get('payload', {})
            if not model and obj.get('type') == 'turn_context':
                model = payload.get('model') or ""
            if obj.get('type') == 'response_item':
                role = payload.get('role')
                for block in payload.get('content', []):
                    if not isinstance(block, dict):
                        continue
                    if role == 'user' and block.get('type') == 'input_text':
                        text = block['text']
                        if text and not text.startswith('<') and not text.startswith('#'):
                            msgs.append({"role": "user", "text": text})
                            break
                    elif role == 'assistant' and block.get('type') == 'output_text':
                        text = block.get('text', '')
                        if text:
                            msgs.append({"role": "assistant", "text": text})
                            break
        except:
            pass
print(json.dumps({"messages": msgs, "model": model}, ensure_ascii=False))`
        codexSessionId = sessionId
        claudeStreamText = ""
        claudeRunning = false
        loadCodexHistoryProc.command = ["python3", "-c", script]
        loadCodexHistoryProc.running = true
    }

    function deleteCodexSession(sessionId, filePath) {
        if (sessionId === codexSessionId) resetClaude()
        deleteCodexSessionProc.command = ["bash", "-c", "rm -f '" + filePath.replace(/'/g, "'\\''") + "'"]
        deleteCodexSessionProc.running = true
    }

    Process {
        id: limitProbeProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                terminalPanel.usageLimitLoading = false
                try {
                    var result = JSON.parse(text.trim())
                    var backoffUntilMs = 0
                    if ((result.error || "").toLowerCase().indexOf("too many requests") >= 0)
                        backoffUntilMs = Date.now() + terminalPanel.currentUsageBackoffMs()
                    if ((result.rows || []).length > 0) {
                        terminalPanel.usageRows = result.rows || []
                        terminalPanel.lastGoodUsageRows = result.rows || []
                    } else if (result.error && terminalPanel.lastGoodUsageRows.length > 0) {
                        terminalPanel.usageRows = terminalPanel.lastGoodUsageRows
                    } else {
                        terminalPanel.usageRows = result.rows || []
                    }
                    terminalPanel.usageLimitError = result.error || ""
                    terminalPanel.usageLimitDebugSummary = result.debug || ""
                    terminalPanel.usageBackoffUntilMs = backoffUntilMs
                    terminalPanel.storeUsageCache(terminalPanel.usageRows, terminalPanel.usageLimitError, terminalPanel.usageLimitDebugSummary, backoffUntilMs)
                    if (terminalPanel.usageLimitDebugSummary !== "")
                        console.log("[AgentLimitProbe]", terminalPanel.activeProfile, terminalPanel.usageLimitDebugSummary)
                } catch(e) {
                    terminalPanel.resetUsageLimitInfo()
                }
                if (terminalPanel.usageRefreshPending)
                    usageRefreshTimer.restart()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                terminalPanel.usageLimitLoading = false
                if (text.trim() !== "") {
                    console.error("limitProbeProc:", text.trim())
                    var err = text.trim()
                    if (err.toLowerCase().indexOf("too many requests") >= 0)
                        terminalPanel.usageBackoffUntilMs = Date.now() + terminalPanel.currentUsageBackoffMs()
                    terminalPanel.storeUsageCache(terminalPanel.usageRows, terminalPanel.usageLimitError || err, terminalPanel.usageLimitDebugSummary, terminalPanel.usageBackoffUntilMs)
                }
                if (terminalPanel.usageRefreshPending)
                    usageRefreshTimer.restart()
            }
        }
    }

    Timer {
        id: usageRefreshTimer
        interval: terminalPanel.currentUsageRefreshIntervalMs()
        repeat: false
        onTriggered: {
            if (terminalPanel.windowVisible && terminalPanel.supportsLiveUsageLimits() && terminalPanel.activeModel !== "")
                terminalPanel.refreshUsageLimitInfo()
        }
    }

    Timer {
        id: scrollButtonTimer
        interval: 2000
        onTriggered: terminalPanel.showScrollButtons = false
    }

    // ── Claude process ────────────────────────────────────────────────────────
    Process {
        id: claudeProc
        running: false

        stdout: StdioCollector {
            onTextChanged: {
                var fresh = text.slice(terminalPanel.claudeOutputOffset)
                terminalPanel.claudeOutputOffset = text.length
                var lines = fresh.split('\n')
                var limit = fresh.endsWith('\n') ? lines.length : lines.length - 1
                for (var i = 0; i < limit; i++)
                    terminalPanel.parseClaudeEvent(lines[i].trim())
                // Scroll output to bottom in real time
                Qt.callLater(function() {
                    claudeFlick.contentY = Math.max(0, claudeFlick.contentHeight - claudeFlick.height)
                })
            }
            onStreamFinished: {
                // Process any trailing partial line
                var tail = text.slice(terminalPanel.claudeOutputOffset).trim()
                if (tail) terminalPanel.parseClaudeEvent(tail)

                // Commit streamed response to message list
                console.log("[Claude] Stream finished, text length:", terminalPanel.claudeStreamText.length)
                var finalText = terminalPanel.claudeStreamText.trim()
                if (finalText) {
                    var msgs = terminalPanel.claudeMessages.slice()
                    msgs.push({role: "assistant", text: finalText, ts: Date.now()})
                    terminalPanel.claudeMessages = msgs
                }
                terminalPanel.claudeStreamText = ""
                terminalPanel.claudeOutputOffset = 0
                terminalPanel.claudeRunning = false
                Qt.callLater(function() {
                    claudeFlick.contentY = Math.max(0, claudeFlick.contentHeight - claudeFlick.height)
                })
                terminalPanel.refreshUsageLimitInfo()
                // Refresh session list so new session appears in sidebar
                terminalPanel.loadSessions()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                var err = text.trim()
                if (err) {
                    console.log("[Claude] stderr:", err)
                    var msgs = terminalPanel.claudeMessages.slice()
                    msgs.push({role: "error", text: "Claude error: " + err, ts: Date.now()})
                    terminalPanel.claudeMessages = msgs
                    terminalPanel.claudeRunning = false
                }
            }
        }
    }

    // ── Codex process ─────────────────────────────────────────────────────────
    Process {
        id: codexProc
        running: false

        stdout: StdioCollector {
            onTextChanged: {
                var fresh = text.slice(terminalPanel.claudeOutputOffset)
                terminalPanel.claudeOutputOffset = text.length
                var lines = fresh.split('\n')
                var limit = fresh.endsWith('\n') ? lines.length : lines.length - 1
                for (var i = 0; i < limit; i++)
                    terminalPanel.parseCodexEvent(lines[i].trim())
                Qt.callLater(function() {
                    claudeFlick.contentY = Math.max(0, claudeFlick.contentHeight - claudeFlick.height)
                })
            }
            onStreamFinished: {
                var tail = text.slice(terminalPanel.claudeOutputOffset).trim()
                if (tail) terminalPanel.parseCodexEvent(tail)

                console.log("[Codex] Stream finished, text length:", terminalPanel.claudeStreamText.length)
                var finalText = terminalPanel.claudeStreamText.trim()
                if (finalText) {
                    var msgs = terminalPanel.claudeMessages.slice()
                    msgs.push({role: "assistant", text: finalText, ts: Date.now()})
                    terminalPanel.claudeMessages = msgs
                }
                terminalPanel.claudeStreamText = ""
                terminalPanel.claudeOutputOffset = 0
                terminalPanel.claudeRunning = false
                Qt.callLater(function() {
                    claudeFlick.contentY = Math.max(0, claudeFlick.contentHeight - claudeFlick.height)
                })
                terminalPanel.refreshUsageLimitInfo()
                terminalPanel.loadCodexSessions()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                var err = text.trim()
                if (err) {
                    console.log("[Codex] stderr:", err)
                    var msgs = terminalPanel.claudeMessages.slice()
                    msgs.push({role: "error", text: "Codex error: " + err, ts: Date.now()})
                    terminalPanel.claudeMessages = msgs
                    terminalPanel.claudeRunning = false
                }
            }
        }
    }

    // ── Clipboard copy ────────────────────────────────────────────────────────
    property string _clipboardText: ""
    Process {
        id: clipboardCopyProc
        command: ["wl-copy", terminalPanel._clipboardText]
        running: false
    }
    function copyToClipboard(txt) { _clipboardText = txt; clipboardCopyProc.running = true }

    Process {
        id: inputPasteProc
        command: ["wl-paste", "--no-newline"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                if (text.length > 0) {
                    var start = Math.min(claudeInput.selectionStart, claudeInput.selectionEnd)
                    var end   = Math.max(claudeInput.selectionStart, claudeInput.selectionEnd)
                    var cur   = claudeInput.text
                    claudeInput.text = cur.slice(0, start) + text + cur.slice(end)
                    claudeInput.cursorPosition = start + text.length
                }
            }
        }
    }

    // ── (segment parsing moved to ChatMessageView.qml) ───────────────────────
    function splitSegments(text) {
        var segs = []
        var fence = /```(\w*)\n?([\s\S]*?)```/g
        var last = 0, m
        while ((m = fence.exec(text)) !== null) {
            if (m.index > last) segs.push({type: "text", content: text.slice(last, m.index), lang: ""})
            segs.push({type: "code", content: m[2].replace(/\n$/, ""), lang: m[1] || ""})
            last = m.index + m[0].length
        }
        if (last < text.length) segs.push({type: "text", content: text.slice(last), lang: ""})
        if (segs.length === 0) segs.push({type: "text", content: text, lang: ""})
        return segs
    }

    // Map fenced code block language tag → KSyntaxHighlighting definition name
    function kdeLang(lang) {
        var m = ({
            "python": "Python", "py": "Python",
            "javascript": "JavaScript", "js": "JavaScript",
            "typescript": "TypeScript", "ts": "TypeScript",
            "bash": "Bash", "sh": "Bash", "shell": "Bash",
            "zsh": "Bash", "fish": "Fish",
            "cpp": "C++", "c++": "C++", "cxx": "C++",
            "c": "C",
            "java": "Java",
            "rust": "Rust", "rs": "Rust",
            "go": "Go",
            "json": "JSON",
            "yaml": "YAML", "yml": "YAML",
            "toml": "TOML",
            "html": "HTML",
            "css": "CSS",
            "sql": "SQL",
            "xml": "XML",
            "qml": "QML",
            "cmake": "CMake",
            "diff": "Diff",
            "makefile": "Makefile",
        })
        return m[lang.toLowerCase()] || ""
    }

    // ── Terminal session (shell only) ─────────────────────────────────────────
    property string termStartupCommand: ""

    LocalTerminal.EmbeddedTerminal {
        id: terminalSession
        program: "/usr/bin/bash"
        arguments: ["-l"]
        workingDirectory: terminalPanel.workingDirectory
        startupCommand: terminalPanel.termStartupCommand
        fontPixelSize: 13
    }

    Process {
        id: focusProc
        running: false
        command: ["windoesnot-hyprctl", "dispatch", "focuswindow", "title:quickshell-agent-terminal"]
    }

    // Lists past Claude sessions
    Process {
        id: listSessionsProc
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try { terminalPanel.claudeSessions = JSON.parse(text) } catch(e) {}
            }
        }
    }

    // Loads message history of a specific Claude session
    Process {
        id: loadHistoryProc
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var result = JSON.parse(text)
                    terminalPanel.claudeMessages = result.messages || []
                    if (result.model)
                        terminalPanel.activeModel = result.model
                    for (var i = 0; i < terminalPanel.claudeMessages.length; i++)
                    Qt.callLater(function() {
                        claudeFlick.contentY = Math.max(0, claudeFlick.contentHeight - claudeFlick.height)
                    })
                } catch(e) {}
            }
        }
    }

    // Deletes a Claude session file and refreshes the list
    Process {
        id: deleteSessionProc
        running: false
        onExited: terminalPanel.loadSessions()
    }

    // Lists past Codex sessions
    Process {
        id: listCodexSessionsProc
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try { terminalPanel.codexSessions = JSON.parse(text) } catch(e) {}
            }
        }
    }

    // Loads message history of a specific Codex session
    Process {
        id: loadCodexHistoryProc
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var result = JSON.parse(text)
                    terminalPanel.claudeMessages = result.messages || []
                    if (result.model)
                        terminalPanel.activeModel = result.model
                    for (var i = 0; i < terminalPanel.claudeMessages.length; i++)
                    Qt.callLater(function() {
                        claudeFlick.contentY = Math.max(0, claudeFlick.contentHeight - claudeFlick.height)
                    })
                } catch(e) {}
            }
        }
    }

    // Deletes a Codex session file and refreshes the list
    Process {
        id: deleteCodexSessionProc
        running: false
        onExited: terminalPanel.loadCodexSessions()
    }

    Process {
        id: agentClipProc
        command: ["wl-copy", terminalPanel._bubbleMenuText]
        running: false
    }

    // Fetch available models from Claude / OpenAI APIs
    Process {
        id: fetchAgentModelsProc
        property string _provider: ""
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var result = JSON.parse(text.trim())
                    if (result.models.length === 0) return
                    if (result.provider === "claude") {
                        terminalPanel.claudeCodeModels = result.models
                        if (terminalPanel.activeProfile === "claude" &&
                                result.models.indexOf(terminalPanel.activeModel) < 0)
                            terminalPanel.activeModel = result.models[0]
                    } else if (result.provider === "openai") {
                        terminalPanel.codexModels = result.models
                        if (terminalPanel.activeProfile === "codex" &&
                                result.models.indexOf(terminalPanel.activeModel) < 0)
                            terminalPanel.activeModel = result.models[0]
                    }
                } catch(e) {}
            }
        }
    }

    function fetchAgentModels(provider, apiKey) {
        if (apiKey === "") return
        fetchAgentModelsProc.command = ["python3", "-c",
            "import sys, json, urllib.request\n" +
            "provider = sys.argv[1]\n" +
            "api_key  = sys.argv[2]\n" +
            "try:\n" +
            "    if provider == 'claude':\n" +
            "        url = 'https://api.anthropic.com/v1/models'\n" +
            "        req = urllib.request.Request(url, headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01'})\n" +
            "        with urllib.request.urlopen(req) as r: raw = json.load(r)\n" +
            "        ids = [m['id'] for m in raw.get('data',[]) if 'claude' in m.get('id','')]\n" +
            "    else:\n" +
            "        url = 'https://api.openai.com/v1/models'\n" +
            "        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + api_key})\n" +
            "        with urllib.request.urlopen(req) as r: raw = json.load(r)\n" +
            "        EXCLUDE = ('realtime', 'audio', 'tts', 'whisper', 'embedding', 'instruct', 'moderation')\n" +
            "        def ok(mid): return mid.startswith(('codex-', 'o1', 'o3', 'o4')) and not any(x in mid for x in EXCLUDE)\n" +
            "        ids = sorted([m['id'] for m in raw.get('data',[]) if ok(m.get('id',''))], reverse=True)\n" +
            "    print(json.dumps({'provider': provider, 'models': ids}))\n" +
            "except Exception as e:\n" +
            "    print(json.dumps({'provider': provider, 'models': [], 'error': str(e)}))\n" +
            "sys.stdout.flush()\n",
            provider, apiKey
        ]
        fetchAgentModelsProc.running = true
    }

    onClaudeApiKeyChanged: {
        if (claudeApiKey !== "") fetchAgentModels("claude", claudeApiKey)
        if (activeProfile === "claude" && windowVisible && usageRows.length === 0)
            refreshUsageLimitInfo()
    }
    onOpenaiApiKeyChanged: {
        if (openaiApiKey !== "") fetchAgentModels("openai", openaiApiKey)
        if (activeProfile === "codex") refreshUsageLimitInfo()
    }
    onActiveModelChanged: {
        if (activeProfile === "codex") {
            refreshUsageLimitInfo()
            return
        }
        if (activeProfile === "claude") {
            applyUsageCache(usageCacheEntry())
            if (windowVisible && usageRows.length === 0)
                refreshUsageLimitInfo()
        }
    }
    onCodexSessionIdChanged: {
        if (activeProfile === "codex" && windowVisible)
            refreshUsageLimitInfo()
    }
    onClaudeSessionIdChanged: {
        if (activeProfile === "claude" && windowVisible)
            refreshUsageLimitInfo()
    }

    Connections {
        target: terminalSession
        function onReceivedData(text) {
            if (shellOutputText.text.length > 8000)
                shellOutputText.text = shellOutputText.text.slice(-4000)
            shellOutputText.text += text
            Qt.callLater(function() {
                shellFlick.contentY = Math.max(0, shellFlick.contentHeight - shellFlick.height)
            })
        }
    }

    Timer {
        id: startDelay
        interval: 150; repeat: false
        onTriggered: {
            if (terminalPanel.activeProfile === "shell" && !terminalSession.running)
                terminalSession.start()
        }
    }

    onWindowVisibleChanged: {
        if (windowVisible) {
            if (activeProfile === "shell") startDelay.start()
            if (activeProfile === "claude") loadSessions()
            if (activeProfile === "codex") loadCodexSessions()
            if (activeProfile === "claude") {
                applyUsageCache(usageCacheEntry())
                if (usageRows.length === 0)
                    refreshUsageLimitInfo()
            } else {
                refreshUsageLimitInfo()
            }
        } else {
            startDelay.stop()
            if (terminalSession.running) terminalSession.stop()
        }
    }

    onActiveProfileChanged: {
        // Reset shared chat state when switching between providers
        if (activeProfile === "shell") {
            if (terminalSession.running) { shellOutputText.text = ""; terminalSession.restart() }
            else if (windowVisible) { shellOutputText.text = ""; terminalSession.start() }
        } else {
            if (terminalSession.running) terminalSession.stop()
        }
        // Clear chat when switching provider so sessions don't bleed across tabs
        resetClaude()
        activeModel = activeProfile === "codex" ? codexModels[0] : claudeCodeModels[0]
        showModelDropdown = false
        resetUsageLimitInfo()
        if (activeProfile === "claude") loadSessions()
        if (activeProfile === "codex") loadCodexSessions()
        if (activeProfile === "claude") {
            applyUsageCache(usageCacheEntry())
            if (windowVisible && usageRows.length === 0)
                refreshUsageLimitInfo()
        } else {
            refreshUsageLimitInfo()
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: terminalPanel.windowVisible && terminalPanel.supportsLiveUsageLimits()
        onTriggered: {
            terminalPanel._timeNowMs = Date.now()
            if (terminalPanel.usageLimitRetryAfter > 0)
                terminalPanel.usageLimitRetryAfter = Math.max(0, terminalPanel.usageLimitRetryAfter - 1)
        }
    }

    // ── Background ────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: terminalPanel.bgColor
        border.width: 1
        border.color: terminalPanel.borderColor
        topLeftRadius: terminalPanel.borderRadius
        topRightRadius: terminalPanel.borderRadius
        bottomLeftRadius: 0
        bottomRightRadius: 0
    }

    // ── Header ────────────────────────────────────────────────────────────────
    Item {
        id: headerBar
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: 62

        Row {
            anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
            spacing: 6
            Repeater {
                model: ["codex", "claude"]
                delegate: Rectangle {
                    property bool isActive: terminalPanel.activeProfile === modelData
                    width: tabLabel.implicitWidth + 20; height: 34; radius: 8
                    color: isActive
                        ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18)
                        : tabMouse.containsMouse ? Qt.rgba(0.35, 0.35, 0.35, 0.18) : "transparent"
                    border.width: isActive ? 1 : 0
                    border.color: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.4)
                    Text {
                        id: tabLabel; anchors.centerIn: parent
                        text: terminalPanel.profileLabel(modelData)
                        color: isActive ? terminalPanel.accentColor : terminalPanel.mutedColor
                        font.pixelSize: 13
                        font.weight: isActive ? Font.DemiBold : Font.Normal
                    }
                    MouseArea {
                        id: tabMouse; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: terminalPanel.activeProfile = modelData
                    }
                }
            }
        }

        Row {
            anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
            spacing: 6

            // ← Chat
            Rectangle {
                visible: terminalPanel.switchToChat !== null
                width: chatBackLabel.implicitWidth + 20; height: 36; radius: 8
                color: chatBackMouse.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.45) : "transparent"
                border.width: 1
                border.color: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.3)
                Text { id: chatBackLabel; anchors.centerIn: parent; text: "← Chat"; color: terminalPanel.textColor; font.pixelSize: 12 }
                MouseArea { id: chatBackMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: terminalPanel.switchToChat() }
            }

            // >_ focus terminal (only for shell/codex with running terminal)
            Rectangle {
                visible: terminalPanel.activeProfile === "shell" && terminalSession.running
                width: 36; height: 36; radius: 8
                color: focusWinMouse.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.45) : "transparent"
                border.width: 1; border.color: terminalPanel.borderColor
                Text { anchors.centerIn: parent; text: ">_"; color: terminalPanel.mutedColor; font.pixelSize: 12; font.family: "monospace" }
                MouseArea { id: focusWinMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: focusProc.running = true }
            }

            // Reload / New session
            Rectangle {
                width: 36; height: 36; radius: 8
                color: actionMouse.containsMouse
                    ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.16)
                    : "transparent"
                border.width: 1
                border.color: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.3)
                Image {
                    anchors.centerIn: parent
                    source: Qt.resolvedUrl("../img/Win11-dark/actions/24/reload.svg")
                    width: 18; height: 18
                    sourceSize.width: 36; sourceSize.height: 36
                    smooth: true; mipmap: true
                }
                MouseArea {
                    id: actionMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: terminalPanel.resetClaude()
                }
            }
        }

        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 1
            color: terminalPanel.borderColor
        }
    }

    // ── Content ───────────────────────────────────────────────────────────────
    Item {
        id: agentCtxParent
        anchors { top: headerBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12 }

        // Global dismiss for context menu
        MouseArea {
            anchors.fill: parent
            visible: agentCtxMenu.visible || terminalPanel._bubbleMenuVisible
            z: 298
            onClicked: { agentCtxMenu.visible = false; terminalPanel._bubbleMenuVisible = false }
        }

        // Bubble context menu — copy only
        Rectangle {
            id: agentBubbleCtxMenu
            visible: terminalPanel._bubbleMenuVisible
            z: 300
            width: 150; height: agentBubbleCtxCol.implicitHeight + 8; radius: 6
            color: terminalPanel.darkMode ? Qt.rgba(0.13, 0.13, 0.13, 0.98) : Qt.rgba(0.96, 0.96, 0.96, 0.98)
            border.width: 1; border.color: terminalPanel.borderColor

            Column {
                id: agentBubbleCtxCol
                anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 4 }

                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: agentBubbleCopyMA.containsMouse
                        ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18)
                        : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.copy"); font.pixelSize: 13; color: terminalPanel.textColor }
                    MouseArea {
                        id: agentBubbleCopyMA; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            terminalPanel._bubbleMenuVisible = false
                            agentClipProc.running = true
                        }
                    }
                }
            }
        }

        // Context menu (input area)
        Rectangle {
            id: agentCtxMenu
            visible: false
            z: 300
            width: 150
            height: agentCtxCol.implicitHeight + 8
            radius: 6
            color: terminalPanel.darkMode ? Qt.rgba(0.13, 0.13, 0.13, 0.98) : Qt.rgba(0.96, 0.96, 0.96, 0.98)
            border.width: 1; border.color: terminalPanel.borderColor

            Column {
                id: agentCtxCol
                anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 4; bottomMargin: 4 }

                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ama1.containsMouse ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.cut"); font.pixelSize: 13; color: terminalPanel.textColor }
                    MouseArea { id: ama1; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            agentCtxMenu.visible = false
                            var sel = claudeInput.selectedText
                            if (sel.length > 0) {
                                terminalPanel._clipboardText = sel
                                clipboardCopyProc.running = true
                                var s = Math.min(claudeInput.selectionStart, claudeInput.selectionEnd)
                                var e = Math.max(claudeInput.selectionStart, claudeInput.selectionEnd)
                                claudeInput.text = claudeInput.text.slice(0, s) + claudeInput.text.slice(e)
                                claudeInput.cursorPosition = s
                            }
                        } }
                }
                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ama2.containsMouse ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.copy"); font.pixelSize: 13; color: terminalPanel.textColor }
                    MouseArea { id: ama2; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            agentCtxMenu.visible = false
                            var sel = claudeInput.selectedText
                            terminalPanel._clipboardText = sel.length > 0 ? sel : claudeInput.text
                            clipboardCopyProc.running = true
                        } }
                }
                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ama3.containsMouse ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.paste"); font.pixelSize: 13; color: terminalPanel.textColor }
                    MouseArea { id: ama3; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: { agentCtxMenu.visible = false; inputPasteProc.running = true } }
                }
                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ama4.containsMouse ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.selectAll"); font.pixelSize: 13; color: terminalPanel.textColor }
                    MouseArea { id: ama4; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            agentCtxMenu.visible = false
                            claudeInput.selectAll()
                        } }
                }
            }
        }

        // ── Claude / Codex mode: clean chat UI ───────────────────────────────
        Item {
            anchors.fill: parent
            visible: terminalPanel.activeProfile === "claude" || terminalPanel.activeProfile === "codex"

            // ── Session sidebar (Claude + Codex) ─────────────────────────────
            Rectangle {
                id: sessionSidebar
                visible: terminalPanel.activeProfile === "claude" || terminalPanel.activeProfile === "codex"
                width: visible ? 260 : 0
                anchors { top: parent.top; left: parent.left; bottom: parent.bottom }
                color: terminalPanel.sidebarColor
                radius: 8
                border.width: 1
                border.color: terminalPanel.borderColor
                clip: true

                // "New session" button
                // Sidebar header: title + "+" button
                Item {
                    id: sidebarHeader
                    anchors { top: parent.top; left: parent.left; right: parent.right }
                    height: 44

                    Text {
                        anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                        text: terminalPanel.tr("agent.sessions")
                        color: terminalPanel.textColor; font.pixelSize: 13; font.weight: Font.Medium
                    }

                    Rectangle {
                        anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                        width: 26; height: 26; radius: 6
                        color: newSessionHover.containsMouse ? Qt.rgba(0.5, 0.5, 0.5, 0.2) : "transparent"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text { anchors.centerIn: parent; text: "+"; font.pixelSize: 18; color: terminalPanel.mutedColor }
                        MouseArea {
                            id: newSessionHover
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: terminalPanel.resetClaude()
                        }
                    }

                    Rectangle {
                        anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                        height: 1; color: terminalPanel.borderColor
                    }
                }

                // Session list
                Flickable {
                    anchors { top: sidebarHeader.bottom; left: parent.left; right: parent.right; bottom: parent.bottom; topMargin: 8; leftMargin: 6; rightMargin: 6; bottomMargin: 6 }
                    contentWidth: width
                    contentHeight: sessionsColumn.implicitHeight
                    clip: true; boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: sessionsColumn
                        width: parent.width
                        spacing: 4

                        Repeater {
                            model: terminalPanel.activeProfile === "codex"
                                ? terminalPanel.codexSessions
                                : terminalPanel.claudeSessions
                            delegate: Rectangle {
                                property bool isCodex: terminalPanel.activeProfile === "codex"
                                property bool isCurrent: modelData.id === (isCodex ? terminalPanel.codexSessionId : terminalPanel.claudeSessionId)
                                property bool hovered: sessionItemMouse.containsMouse
                                width: sessionsColumn.width; height: 60; radius: 8
                                color: isCurrent
                                    ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18)
                                    : hovered ? Qt.rgba(0.5, 0.5, 0.5, 0.12) : "transparent"
                                Behavior on color { ColorAnimation { duration: 100 } }

                                // Background MouseArea first so delete button sits above it
                                MouseArea {
                                    id: sessionItemMouse
                                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (isCodex) terminalPanel.resumeCodexSession(modelData.id, modelData.file)
                                        else terminalPanel.resumeSession(modelData.id)
                                    }
                                }

                                Column {
                                    anchors { left: parent.left; leftMargin: 10; right: sessionDelBtn.left; rightMargin: 4; verticalCenter: parent.verticalCenter }
                                    spacing: 3
                                    Text {
                                        width: parent.width
                                        text: modelData.title
                                        color: isCurrent ? terminalPanel.accentColor : terminalPanel.textColor
                                        font.pixelSize: 13; font.weight: isCurrent ? Font.Medium : Font.Normal
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.model && modelData.model !== ""
                                            ? modelData.model + "  " + "\u00b7" + "  " + terminalPanel.formatTs(modelData.ts)
                                            : terminalPanel.formatTs(modelData.ts)
                                        color: terminalPanel.mutedColor; font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                }

                                Text {
                                    id: sessionDelBtn
                                    anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                                    text: "✕"; font.pixelSize: 10; color: terminalPanel.mutedColor
                                    visible: hovered || isCurrent
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            mouse.accepted = true
                                            if (isCodex) terminalPanel.deleteCodexSession(modelData.id, modelData.file)
                                            else terminalPanel.deleteSession(modelData.id)
                                        }
                                    }
                                }
                            }
                        }

                        Item {
                            visible: (terminalPanel.activeProfile === "codex" ? terminalPanel.codexSessions.length : terminalPanel.claudeSessions.length) === 0
                            width: sessionsColumn.width; height: 60
                            Text {
                                anchors.centerIn: parent
                                text: terminalPanel.tr("agent.noSessions")
                                color: terminalPanel.mutedColor; font.pixelSize: 11
                            }
                        }
                    }
                }
            }

            // ── Main chat area ───────────────────────────────────────────────
            Item {
                anchors {
                    top: parent.top
                    left: parent.left
                    leftMargin: (terminalPanel.activeProfile === "claude" || terminalPanel.activeProfile === "codex") ? 268 : 0
                    right: parent.right
                    bottom: parent.bottom
                }

                // Message list
                Rectangle {
                    anchors { top: parent.top; left: parent.left; right: parent.right; bottom: agentComposerArea.top; bottomMargin: 8 }
                    color: terminalPanel.bgColor; radius: 8; border.width: 1; border.color: terminalPanel.borderColor; clip: true

                    Flickable {
                        id: claudeFlick
                        anchors { fill: parent; topMargin: 14; bottomMargin: 8; leftMargin: 20; rightMargin: 20 }
                        contentWidth: width
                        contentHeight: claudeColumn.implicitHeight
                        clip: true; boundsBehavior: Flickable.StopAtBounds
                        onMovementStarted: terminalPanel.showScrollButtonsFor("agent")

                        WheelHandler {
                            onWheel: function(event) {
                                claudeFlick.contentY = Math.max(0, Math.min(
                                    claudeFlick.contentHeight - claudeFlick.height,
                                    claudeFlick.contentY - event.angleDelta.y * 0.5
                                ))
                                terminalPanel.showScrollButtonsFor("agent")
                            }
                        }

                        Column {
                            id: claudeColumn
                            width: claudeFlick.width
                            spacing: 10

                            // Existing messages
                            Repeater {
                                model: terminalPanel.claudeMessages
                                delegate: Item {
                                    width: claudeColumn.width
                                    height: msgBubble.height + (claudeActionRow.visible ? claudeActionRow.height + 4 : 0) + 4

                                    readonly property bool isUser: modelData.role === "user"
                                    readonly property bool isError: modelData.role === "error"
                                    HoverHandler { id: msgHover }

                                    Rectangle {
                                        id: msgBubble
                                        width: isUser ? Math.min(userText.implicitWidth + 24, claudeColumn.width * 0.85)
                                                      : claudeColumn.width
                                        x: isUser ? claudeColumn.width - width : 0
                                        height: (isUser || isError)
                                            ? userText.contentHeight + 20
                                            : msgContent.implicitHeight + 16
                                        radius: 8
                                        color: isError
                                            ? Qt.rgba(0.8, 0.2, 0.2, 0.2)
                                            : isUser
                                                ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.18)
                                                : terminalPanel.surfaceColor
                                        border.width: 1
                                        border.color: isError
                                            ? Qt.rgba(0.8, 0.2, 0.2, 0.4)
                                            : isUser
                                                ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.35)
                                                : terminalPanel.borderColor

                                        // User / error: plain text
                                        TextEdit {
                                            id: userText
                                            visible: isUser || isError
                                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                                            text: (isUser || isError) ? modelData.text : ""
                                            color: isError ? "#ff8080" : terminalPanel.textColor
                                            font.pixelSize: 13
                                            wrapMode: TextEdit.Wrap
                                            textFormat: TextEdit.PlainText
                                            readOnly: true
                                            selectByMouse: true
                                            persistentSelection: true
                                            activeFocusOnPress: false  // Don't steal focus on click
                                            selectedTextColor: terminalPanel.textColor
                                            selectionColor: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.4)
                                        }

                                        // Assistant: markdown + syntax-highlighted code
                                        ChatMessageView {
                                            id: msgContent
                                            visible: !isUser && !isError
                                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
                                            messageText: (!isUser && !isError) ? modelData.text : ""
                                            darkMode:    terminalPanel.darkMode
                                            textColor:   terminalPanel.textColor
                                            mutedColor:  terminalPanel.mutedColor
                                            accentColor: terminalPanel.accentColor
                                        }

                                        // Timestamp inside user bubble (bottom-right, fade on hover)
                                        Text {
                                            visible: isUser
                                            anchors { right: parent.right; bottom: parent.bottom; margins: 7 }
                                            text: terminalPanel.formatMsgTs(modelData.ts || 0)
                                            color: terminalPanel.mutedColor
                                            font.pixelSize: 10
                                            opacity: msgHover.hovered ? 0.85 : 0.0
                                            Behavior on opacity { NumberAnimation { duration: 150 } }
                                        }

                                        // Right-click context menu
                                        MouseArea {
                                            anchors.fill: parent
                                            acceptedButtons: Qt.RightButton
                                            z: 50  // Above content

                                            onPressed: function(mouse) {
                                                // Read selected text IMMEDIATELY in onPressed before it can be cleared
                                                var selectedText = (isUser && userText.visible) ? userText.selectedText : ""
                                                console.log("[AgentBubbleCtx] onPressed - isUser:", isUser, "selected:", selectedText.length, "chars")
                                                console.log("[AgentBubbleCtx] Selected text:", selectedText.substring(0, 50))

                                                terminalPanel._bubbleMenuText = selectedText.length > 0 ? selectedText : modelData.text
                                                console.log("[AgentBubbleCtx] Will copy:", terminalPanel._bubbleMenuText.substring(0, 50))
                                                var g = mapToGlobal(mouse.x, mouse.y)
                                                var pos = agentCtxParent.mapFromGlobal(g.x, g.y)
                                                agentBubbleCtxMenu.x = Math.min(pos.x, agentCtxParent.width - agentBubbleCtxMenu.width - 4)
                                                agentBubbleCtxMenu.y = Math.max(4, pos.y - agentBubbleCtxMenu.height - 4)
                                                terminalPanel._bubbleMenuVisible = true
                                                mouse.accepted = true
                                            }
                                        }
                                    }


                                    // Action row below assistant bubble
                                    Row {
                                        id: claudeActionRow
                                        visible: !isUser && !isError
                                        anchors { top: msgBubble.bottom; left: msgBubble.left; topMargin: 4 }
                                        spacing: 4
                                        height: visible ? 26 : 0

                                        Rectangle {
                                            width: 26; height: 26; radius: 6
                                            color: claudeCopyMouse.containsMouse
                                                ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.2)
                                                : "transparent"
                                            Behavior on color { ColorAnimation { duration: 100 } }
                                            Image {
                                                anchors.centerIn: parent
                                                width: 16; height: 16
                                                source: "../img/Win11-dark/actions/16/spray-mode-copy.svg"
                                                sourceSize: Qt.size(16, 16)
                                                smooth: true; antialiasing: true
                                                opacity: claudeCopyMouse.containsMouse ? 1.0 : 0.5
                                                Behavior on opacity { NumberAnimation { duration: 100 } }
                                            }
                                            MouseArea {
                                                id: claudeCopyMouse
                                                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                onClicked: terminalPanel.copyToClipboard(modelData.text)
                                            }
                                        }
                                        // Timestamp next to copy button (fade on hover)
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            leftPadding: 2
                                            text: terminalPanel.formatMsgTs(modelData.ts || 0)
                                            color: terminalPanel.mutedColor
                                            font.pixelSize: 11
                                            opacity: msgHover.hovered ? 0.75 : 0.0
                                            Behavior on opacity { NumberAnimation { duration: 150 } }
                                        }
                                    }
                                }
                            }

                            // Streaming / thinking indicator
                            Item {
                                width: claudeColumn.width
                                height: visible ? streamBubble.height + 4 : 0
                                visible: terminalPanel.claudeRunning || terminalPanel.claudeStreamText !== ""

                                Rectangle {
                                    id: streamBubble
                                    anchors.left: parent.left
                                    width: Math.min(streamText.implicitWidth + 20, claudeColumn.width * 0.85)
                                    height: streamText.implicitHeight + 16
                                    radius: 8
                                    color: terminalPanel.surfaceColor
                                    border.width: 1; border.color: terminalPanel.borderColor

                                    Text {
                                        id: streamText
                                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                                        text: terminalPanel.claudeStreamText !== "" ? terminalPanel.claudeStreamText : "●●●"
                                        color: terminalPanel.claudeStreamText !== "" ? terminalPanel.textColor : terminalPanel.mutedColor
                                        font.pixelSize: 13
                                        wrapMode: Text.Wrap
                                        textFormat: Text.PlainText
                                    }
                                }
                            }

                            // Empty state
                            Item {
                                width: claudeColumn.width
                                height: 120
                                visible: terminalPanel.claudeMessages.length === 0 && !terminalPanel.claudeRunning

                                Column {
                                    anchors.centerIn: parent; spacing: 8
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: terminalPanel.activeProfile; color: terminalPanel.accentColor; font.pixelSize: 28; font.weight: Font.Bold; font.family: "monospace" }
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: terminalPanel.tr("agent.messageHint"); color: terminalPanel.mutedColor; font.pixelSize: 12 }
                                }
                            }
                        }
                    }
                }

                // Model dropdown dismiss
                MouseArea {
                    anchors.fill: parent
                    visible: terminalPanel.showModelDropdown
                    z: 99
                    onClicked: terminalPanel.showModelDropdown = false
                }

                // Model dropdown (above input bar)
                Rectangle {
                    id: agentModelDropdown
                    visible: terminalPanel.showModelDropdown
                    z: 100
                    anchors { bottom: agentComposerArea.top; bottomMargin: 6; right: parent.right; rightMargin: 0 }
                    width: 260
                    height: Math.min(agentDropdownCol.implicitHeight + 16, 280)
                    radius: 8
                    color: terminalPanel.darkMode ? Qt.rgba(0.13, 0.13, 0.13, 0.98) : Qt.rgba(0.95, 0.95, 0.95, 0.98)
                    border.color: terminalPanel.borderColor; border.width: 1
                    layer.enabled: true

                    Flickable {
                        anchors { fill: parent; margins: 8 }
                        contentHeight: agentDropdownCol.implicitHeight
                        clip: true

                        Column {
                            id: agentDropdownCol
                            width: parent.width
                            spacing: 2

                            Repeater {
                                model: terminalPanel.activeProfile === "codex"
                                    ? terminalPanel.codexModels
                                    : terminalPanel.claudeCodeModels
                                delegate: Rectangle {
                                    property bool isActive: terminalPanel.activeModel === modelData
                                    property bool hov: agentDropItemMA.containsMouse
                                    width: agentDropdownCol.width; height: 36; radius: 6
                                    color: isActive
                                        ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.22)
                                        : hov ? Qt.rgba(0.3, 0.3, 0.3, 0.15) : "transparent"
                                    Behavior on color { ColorAnimation { duration: 80 } }

                                    Text {
                                        anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                                        text: modelData
                                        color: isActive ? terminalPanel.accentColor : terminalPanel.textColor
                                        font.pixelSize: 13; font.weight: isActive ? Font.DemiBold : Font.Normal
                                    }

                                    MouseArea {
                                        id: agentDropItemMA; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            terminalPanel.activeModel = modelData
                                            terminalPanel.showModelDropdown = false
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item {
                    id: agentComposerArea
                    z: 100
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: claudeInputBar.height + ((agentUsagePanel.visible ? agentUsagePanel.height + 6 : 0))

                    // Claude input bar
                    Rectangle {
                        id: claudeInputBar
                        anchors { left: parent.left; right: parent.right; top: parent.top }
                        height: Math.min(Math.max(40, claudeInput.implicitHeight + 20), 120); radius: 8
                        color: terminalPanel.surfaceColor
                        border.width: 1
                        border.color: claudeInput.activeFocus
                            ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.6)
                            : terminalPanel.borderColor

                        // Status indicator
                        Text {
                            id: claudeStatusDot
                            anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                            text: terminalPanel.claudeRunning ? "●" : ">"
                            color: terminalPanel.accentColor; font.pixelSize: 14; font.weight: Font.Bold; font.family: "monospace"
                        }

                        // Model picker pill
                        Rectangle {
                            id: agentModelPickerBtn
                            anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                            height: 26; radius: 13
                            width: agentModelPickerRow.implicitWidth + 14
                            color: terminalPanel.showModelDropdown
                                ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.2)
                                : agentModelPickerHover.containsMouse
                                    ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.12)
                                    : Qt.rgba(0.3, 0.3, 0.3, 0.25)
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                id: agentModelPickerRow
                                anchors.centerIn: parent
                                spacing: 4
                                Text {
                                    text: terminalPanel.activeModel !== ""
                                        ? terminalPanel.activeModel.split(":")[0]
                                        : terminalPanel.tr("agent.chooseModel")
                                    color: terminalPanel.activeModel !== "" ? terminalPanel.textColor : terminalPanel.mutedColor
                                    font.pixelSize: 12
                                }
                                Text {
                                    text: terminalPanel.showModelDropdown ? "▴" : "▾"
                                    color: terminalPanel.mutedColor; font.pixelSize: 8
                                }
                            }

                            MouseArea {
                                id: agentModelPickerHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: terminalPanel.showModelDropdown = !terminalPanel.showModelDropdown
                            }
                        }

                        // Text input (multi-line: Shift+Enter = newline, Enter = send)
                        TextEdit {
                            id: claudeInput
                            anchors {
                                left: claudeStatusDot.right; leftMargin: 8
                                right: agentModelPickerBtn.left; rightMargin: 8
                                top: parent.top; topMargin: 10
                            }
                            color: terminalPanel.claudeRunning ? terminalPanel.mutedColor : terminalPanel.textColor
                            font.family: "monospace"; font.pixelSize: 13
                            selectionColor: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.35)
                            selectedTextColor: terminalPanel.textColor
                            readOnly: terminalPanel.claudeRunning
                            wrapMode: TextEdit.Wrap

                            Keys.onPressed: function(event) {
                                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                    if (event.modifiers & Qt.ShiftModifier) {
                                        insert(cursorPosition, "\n")
                                    } else if (!terminalPanel.claudeRunning && text.trim().length > 0) {
                                        var msg = text.trim()
                                        text = ""
                                        terminalPanel.sendMessage(msg)
                                    }
                                    event.accepted = true
                                }
                            }
                        }

                        // Right-click: context menu
                        MouseArea {
                            anchors { left: claudeInput.left; right: claudeInput.right; top: parent.top; bottom: parent.bottom }
                            acceptedButtons: Qt.RightButton
                            onClicked: function(mouse) {
                                var g = mapToGlobal(mouse.x, mouse.y)
                                var pos = agentCtxParent.mapFromGlobal(g.x, g.y)
                                agentCtxMenu.x = Math.min(pos.x, agentCtxParent.width - agentCtxMenu.width - 4)
                                agentCtxMenu.y = Math.max(4, pos.y - agentCtxMenu.height - 4)
                                agentCtxMenu.visible = true
                            }
                        }
                    }

                    Rectangle {
                        id: agentUsagePanel
                        anchors { left: parent.left; right: parent.right; top: claudeInputBar.bottom; topMargin: 8 }
                        height: 24
                        radius: 0
                        color: "transparent"
                        border.width: 0
                        visible: terminalPanel.supportsLiveUsageLimits() && terminalPanel.activeModel !== ""
                        clip: false

                        Row {
                            anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                            spacing: 6

                            Repeater {
                                model: terminalPanel.usageLimitLoading
                                    ? [{ label: "Limits", remainingPercent: -1, resetAtMs: 0, detail: terminalPanel.tr("agent.loadingCliStatus"), stateText: "…" }]
                                    : (terminalPanel.usageRows.length > 0
                                        ? terminalPanel.usageRows
                                        : [{ label: "Limits", remainingPercent: -1, resetAtMs: 0, detail: terminalPanel.usageLimitError !== "" ? terminalPanel.usageLimitError : terminalPanel.tr("agent.noCliStatus"), stateText: terminalPanel.tr("agent.notAvailable") }])

                                Rectangle {
                                    required property var modelData
                                    anchors.verticalCenter: parent.verticalCenter
                                    height: 16
                                    radius: 8
                                    width: usageChipText.implicitWidth + 16
                                    color: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b,
                                                   modelData.remainingPercent >= 0 ? 0.10 + (0.20 * terminalPanel.usageRowRatio(modelData)) : 0.08)
                                    border.width: 1
                                    border.color: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.16)

                                    Text {
                                        id: usageChipText
                                        anchors.centerIn: parent
                                        text: terminalPanel.compactUsageText(modelData)
                                        color: modelData.remainingPercent >= 0 ? terminalPanel.textColor : terminalPanel.mutedColor
                                        font.pixelSize: 10
                                        font.weight: modelData.remainingPercent >= 0 ? Font.DemiBold : Font.Normal
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    anchors { right: parent.right; rightMargin: 12; top: parent.top; topMargin: 16 }
                    width: 32; height: 32; radius: 16
                    color: Qt.rgba(terminalPanel.surfaceColor.r, terminalPanel.surfaceColor.g, terminalPanel.surfaceColor.b, 0.95)
                    border.width: 1
                    border.color: terminalPanel.borderColor
                    visible: terminalPanel.showScrollButtons
                        && terminalPanel.scrollButtonsTarget === "agent"
                        && claudeFlick.contentHeight > claudeFlick.height
                        && claudeFlick.contentY > 50
                    opacity: visible ? 1.0 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 200 } }
                    z: 101

                    Text {
                        anchors.centerIn: parent
                        text: "↑"
                        font.pixelSize: 18
                        color: terminalPanel.textColor
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: claudeFlick.contentY = 0
                    }
                }

                Rectangle {
                    anchors { right: parent.right; rightMargin: 12; bottom: agentComposerArea.top; bottomMargin: 12 }
                    width: 32; height: 32; radius: 16
                    color: Qt.rgba(terminalPanel.surfaceColor.r, terminalPanel.surfaceColor.g, terminalPanel.surfaceColor.b, 0.95)
                    border.width: 1
                    border.color: terminalPanel.borderColor
                    visible: terminalPanel.showScrollButtons
                        && terminalPanel.scrollButtonsTarget === "agent"
                        && claudeFlick.contentHeight > claudeFlick.height
                        && claudeFlick.contentY < terminalPanel.maxScrollY(claudeFlick) - 10
                    opacity: visible ? 1.0 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 200 } }
                    z: 101

                    Text {
                        anchors.centerIn: parent
                        text: "↓"
                        font.pixelSize: 18
                        color: terminalPanel.textColor
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: claudeFlick.contentY = terminalPanel.maxScrollY(claudeFlick)
                    }
                }
            }
        }

        // ── Shell mode: terminal output ───────────────────────────────────────
        Item {
            anchors.fill: parent
            visible: terminalPanel.activeProfile === "shell"

            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right; bottom: shellInputBar.top; bottomMargin: terminalSession.running ? 8 : 0 }
                color: terminalPanel.surfaceColor; radius: 8; border.width: 1; border.color: terminalPanel.borderColor; clip: true

                Flickable {
                    id: shellFlick
                    anchors.fill: parent; anchors.margins: 10
                    contentWidth: width; contentHeight: shellOutputText.implicitHeight
                    clip: true; boundsBehavior: Flickable.StopAtBounds
                    onMovementStarted: terminalPanel.showScrollButtonsFor("shell")

                    WheelHandler {
                        onWheel: function(event) {
                            shellFlick.contentY = Math.max(0, Math.min(
                                shellFlick.contentHeight - shellFlick.height,
                                shellFlick.contentY - event.angleDelta.y * 0.5
                            ))
                            terminalPanel.showScrollButtonsFor("shell")
                        }
                    }

                    TextEdit {
                        id: shellOutputText
                        width: shellFlick.width
                        color: terminalPanel.textColor; font.family: "monospace"; font.pixelSize: 13
                        wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                        readOnly: true; selectByMouse: true
                        selectedTextColor: terminalPanel.textColor
                        selectionColor: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.4)
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: !terminalSession.running
                    text: "Terminal session is not running."
                    color: terminalPanel.mutedColor; font.pixelSize: 13
                }
            }

            Rectangle {
                id: shellInputBar
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: terminalSession.running ? 40 : 0; visible: terminalSession.running
                color: terminalPanel.surfaceColor; radius: 8
                border.width: 1
                border.color: shellInput.activeFocus
                    ? Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.6)
                    : terminalPanel.borderColor

                Row {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                    spacing: 8
                    Text { anchors.verticalCenter: parent.verticalCenter; text: ">"; color: terminalPanel.accentColor; font.pixelSize: 14; font.weight: Font.Bold; font.family: "monospace" }
                    TextInput {
                        id: shellInput
                        anchors.verticalCenter: parent.verticalCenter; width: parent.width - 30
                        color: terminalPanel.textColor; font.family: "monospace"; font.pixelSize: 13
                        selectionColor: Qt.rgba(terminalPanel.accentColor.r, terminalPanel.accentColor.g, terminalPanel.accentColor.b, 0.35)
                        selectedTextColor: terminalPanel.textColor
                        Keys.onReturnPressed: { if (text.length > 0) { terminalSession.sendText(text + "\r"); text = "" } }
                    }
                }
            }

            Rectangle {
                anchors { right: parent.right; rightMargin: 12; top: parent.top; topMargin: 16 }
                width: 32; height: 32; radius: 16
                color: Qt.rgba(terminalPanel.surfaceColor.r, terminalPanel.surfaceColor.g, terminalPanel.surfaceColor.b, 0.95)
                border.width: 1
                border.color: terminalPanel.borderColor
                visible: terminalPanel.showScrollButtons
                    && terminalPanel.scrollButtonsTarget === "shell"
                    && shellFlick.contentHeight > shellFlick.height
                    && shellFlick.contentY > 50
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 200 } }
                z: 101

                Text {
                    anchors.centerIn: parent
                    text: "↑"
                    font.pixelSize: 18
                    color: terminalPanel.textColor
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shellFlick.contentY = 0
                }
            }

            Rectangle {
                anchors { right: parent.right; rightMargin: 12; bottom: shellInputBar.top; bottomMargin: 12 }
                width: 32; height: 32; radius: 16
                color: Qt.rgba(terminalPanel.surfaceColor.r, terminalPanel.surfaceColor.g, terminalPanel.surfaceColor.b, 0.95)
                border.width: 1
                border.color: terminalPanel.borderColor
                visible: terminalPanel.showScrollButtons
                    && terminalPanel.scrollButtonsTarget === "shell"
                    && shellFlick.contentHeight > shellFlick.height
                    && shellFlick.contentY < terminalPanel.maxScrollY(shellFlick) - 10
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 200 } }
                z: 101

                Text {
                    anchors.centerIn: parent
                    text: "↓"
                    font.pixelSize: 18
                    color: terminalPanel.textColor
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shellFlick.contentY = terminalPanel.maxScrollY(shellFlick)
                }
            }
        }
    }
}
