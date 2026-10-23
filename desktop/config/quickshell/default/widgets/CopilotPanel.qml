import Quickshell
import QtQuick
import QtQuick.Effects
import Quickshell.Io
import org.kde.syntaxhighlighting
import "."
import "../i18n/Lang.js" as Lang

Item {
    id: copilotPanel

    property color accentColor: "#FE6F2D"
    property int borderRadius: 12
    property bool darkMode: true
    property bool windowVisible: false
    property string uiLanguage: "de"
    property bool isPinned: true

    signal requestWindowReopen(bool newPinState)

    onIsPinnedChanged: {
        console.log("[CopilotPanel] ========================================")
        console.log("[CopilotPanel] isPinned changed to:", isPinned)
        console.log("[CopilotPanel] Emitting requestWindowReopen signal...")
        console.log("[CopilotPanel] ========================================")
        requestWindowReopen(isPinned)
    }


    // ── Terminal mode callback (set by CopilotPanelHost) ──────────────────
    property var switchToTerminal: null

    // ── Provider / Model ──────────────────────────────────────────────────
    property string activeProvider: "ollama"
    property string activeModel: ""
    property var ollamaModels: []       // just names for selector
    property var ollamaModelDetails: []  // [{name, size, family, url}]
    property var ollamaUrlStatuses: []   // [{url, status, count}]
    property var claudeModels: ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
                                "claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
    property var openaiModels: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o4-mini", "o3", "o3-mini", "o1"]
    property var perplexityModels: ["sonar-pro", "sonar", "sonar-reasoning-pro", "sonar-reasoning",
                                    "sonar-deep-research"]
    property var geminiModels: ["gemini-2.5-pro-preview-05-06", "gemini-2.0-flash", "gemini-2.0-flash-lite",
                                "gemini-1.5-pro", "gemini-1.5-flash"]
    property var nvidiaModels: []
    property var ollamaUrls: ["http://localhost:11434"]
    property var openclawUrls: []
    property bool configLoaded: false

    // Save URLs when changed (after initial load)
    onOllamaUrlsChanged: {
        if (configLoaded) {
            saveConfig()
        }
    }
    onOpenclawUrlsChanged: {
        if (configLoaded) {
            saveConfig()
        }
    }

    function saveConfig() {
        // Filter out empty/invalid URLs before saving (but keep "http://" for editing)
        var cleaned = ollamaUrls.filter(function(u) {
            var trimmed = u.trim()
            return trimmed !== "" && trimmed !== "https://"  // Keep "http://" for editing
        })
        var cleanedOc = openclawUrls.filter(function(u) {
            var trimmed = u.trim()
            return trimmed !== "" && trimmed !== "wss://"  // Keep "ws://" for editing
        })

        saveConfigProc.command = ["python3", "-c",
            "import json, os, sys\n" +
            "cfg = (__import__('os').path.expanduser('~/.config/quickshell/copilot/config.json'))\n" +
            "os.makedirs(os.path.dirname(cfg), exist_ok=True)\n" +
            "data = json.loads(sys.argv[1])\n" +
            "with open(cfg, 'w', encoding='utf-8') as f:\n" +
            "    json.dump(data, f, indent=2)\n" +
            "print('ok')\n",
            JSON.stringify({ollamaUrls: cleaned, openclawUrls: cleanedOc})
        ]
        saveConfigProc.running = true
    }
    property var openclawModels: []
    property var openclawModelDetails: []
    property var openclawUrlStatuses: []
    property string openclawHealthState: "idle"   // idle | checking | ok | error
    property string openclawHealthMessage: ""
    property string openclawToken: ""
    property string claudeApiKey: ""
    property string openaiApiKey: ""
    property string perplexityApiKey: ""
    property string geminiApiKey: ""
    property string nvidiaApiKey: ""
    property var _apiTestedOk: ({"claude": false, "openai": false, "perplexity": false, "gemini": false, "nvidia": false})

    // ── Session state ──────────────────────────────────────────────────────
    property var sessions: []
    property string activeSessionId: ""
    property var currentMessages: []
    readonly property var filteredSessions: sessions.filter(function(s) { return s.provider === activeProvider })

    // ── Streaming ──────────────────────────────────────────────────────────
    property bool isStreaming: false
    property int streamLastLen: 0
    property string streamAccumulated: ""

    // ── UI state ───────────────────────────────────────────────────────────
    property bool showSettings: false
    property bool showOllamaModels: false
    property bool scanningOllama: false
    property bool scanningOpenclaw: false
    property var foundOllamaInstances: []
    property var foundOpenclawInstances: []
    property var openclawPairingStatus: ({})  // {url: {status: "pending|approved|failed", requestId: "", message: ""}}
    property bool showModelDropdown: false
    property string modelSearchQuery: ""
    onShowModelDropdownChanged: { if (!showModelDropdown) modelSearchQuery = "" }
    property string statusMessage: ""
    property bool userScrolled: false
    property bool showScrollButtons: false
    property bool _loadingSession: false
    property string _editingProvider: ""
    property string _clipboardText: ""
    property bool   _bubbleMenuVisible: false
    property string _bubbleMenuText: ""
    property int    _hoveredBubbleIndex: -1
    property string _hoveredBubbleSelectedText: ""
    property int ollamaContextWindow: 0
    property bool ollamaContextLoading: false
    property int localContextFallback: 4096
    property int _timeNowMs: Date.now()

    // ── Agent Mode (Tool-Use) ──────────────────────────────────────────
    property bool toolsEnabled: false
    property var executedToolCalls: []  // [{turn, tool, arguments, result}] - final list
    property var liveToolCalls: []  // Live tool calls during streaming
    property bool showToolDetails: true  // Toggle for tool call visibility in messages
    property int currentToolTurn: 0  // Current LLM turn

    // NVIDIA tool-capable models (still need hardcoding as NVIDIA API doesn't auto-detect)
    readonly property var nvidiaToolModels: [
        "kimi",                               // Moonshot AI Kimi
        "llama-3.1", "llama-3.2", "llama-3.3", // Meta Llama 3.1+
        "mistral-nemo", "mistral-small",      // Mistral
        "qwen2.5", "qwen3.5"                  // Alibaba Qwen
    ]

    function modelSupportsTools() {
        if (!activeModel) return false

        // Ollama: Enable for ALL models - let the model/API decide if it actually works
        // If a model doesn't support tools, it will simply ignore them or error gracefully
        if (activeProvider === "ollama") {
            return true  // No more hardcoding!
        }

        // NVIDIA provider: check against known tool-capable models
        if (activeProvider === "nvidia") {
            var modelLower = activeModel.toLowerCase()
            for (var i = 0; i < nvidiaToolModels.length; i++) {
                if (modelLower.indexOf(nvidiaToolModels[i]) >= 0) {
                    return true
                }
            }
            return false
        }

        // Other providers: assume tools supported (Claude, OpenAI, etc.)
        // They all support function calling natively
        return activeProvider === "claude" || activeProvider === "openai" || activeProvider === "gemini"
    }
    property bool usageLimitLoading: false
    property int usageLimitStatusCode: 0
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


    function copyToClipboard(txt) {
        _clipboardText = txt
        clipboardCopyProc.running = true
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

    function parseMessageSegments(content) {
        var segments = []
        var regex = /```(\w*)\n?([\s\S]*?)```/g
        var lastIndex = 0
        var match
        while ((match = regex.exec(content)) !== null) {
            if (match.index > lastIndex) {
                var before = content.substring(lastIndex, match.index).replace(/^\n+|\n+$/g, "")
                if (before.length > 0)
                    segments.push({ type: "text", content: before })
            }
            segments.push({ type: "code", lang: match[1] || "", content: match[2].replace(/\n$/, "") })
            lastIndex = match.index + match[0].length
        }
        if (lastIndex < content.length) {
            var after = content.substring(lastIndex).replace(/^\n+|\n+$/g, "")
            if (after.length > 0)
                segments.push({ type: "text", content: after })
        }
        return segments.length > 0 ? segments : [{ type: "text", content: content }]
    }

    // ── Derived colours ────────────────────────────────────────────────────
    readonly property color bgColor: darkMode ? Qt.rgba(0.125, 0.125, 0.125, 0.97) : Qt.rgba(0.97, 0.97, 0.97, 0.97)
    readonly property color sidebarColor: darkMode ? Qt.rgba(0.09, 0.09, 0.09, 0.95) : Qt.rgba(0.93, 0.93, 0.93, 0.95)
    readonly property color borderColor: darkMode ? "#2a2a2f" : "#c0c0c0"
    readonly property color surfaceColor: darkMode ? Qt.rgba(0.18, 0.18, 0.18, 1) : Qt.rgba(0.92, 0.92, 0.92, 1)
    readonly property color textColor: darkMode ? "#e8e8e8" : "#1a1a1a"
    readonly property color subtextColor: darkMode ? "#888" : "#777"

    // ── Helpers ───────────────────────────────────────────────────────────
    function providerLabel(p) {
        if (p === "ollama")      return "Ollama"
        if (p === "openclaw")    return "OpenClaw"
        if (p === "claude")      return "Claude"
        if (p === "openai")      return "OpenAI"
        if (p === "perplexity")  return "Perplexity"
        if (p === "gemini")      return "Gemini"
        if (p === "nvidia")      return "NVIDIA"
        return p
    }

    function currentApiKey() {
        if (activeProvider === "claude")     return claudeApiKey
        if (activeProvider === "openai")     return openaiApiKey
        if (activeProvider === "perplexity") return perplexityApiKey
        if (activeProvider === "gemini")     return geminiApiKey
        if (activeProvider === "nvidia")     return nvidiaApiKey
        return ""
    }

    function currentModelList() {
        if (activeProvider === "ollama")     return ollamaModels
        if (activeProvider === "openclaw")   return openclawModels
        if (activeProvider === "claude")     return claudeModels
        if (activeProvider === "openai")     return openaiModels
        if (activeProvider === "perplexity") return perplexityModels
        if (activeProvider === "gemini")     return geminiModels
        if (activeProvider === "nvidia")     return nvidiaModels
        return []
    }

    function filteredModelList() {
        var models = currentModelList()
        if (modelSearchQuery.trim() === "") return models
        var q = modelSearchQuery.toLowerCase()
        return models.filter(function(m) {
            return m.toLowerCase().indexOf(q) >= 0
        })
    }

    function estimateTokens(text) {
        if (!text) return 0
        return Math.max(1, Math.ceil(text.length / 4))
    }

    function estimateConversationTokens() {
        var total = 0
        // Count user/assistant messages
        for (var i = 0; i < currentMessages.length; i++) {
            var msg = currentMessages[i]
            if (!msg || !msg.content) continue
            total += estimateTokens(msg.content) + 12
        }
        // Add streaming content
        if (isStreaming && streamAccumulated !== "")
            total += estimateTokens(streamAccumulated)
        // Add tool call overhead (arguments + results)
        if (toolsEnabled && executedToolCalls.length > 0) {
            for (var j = 0; j < executedToolCalls.length; j++) {
                var tc = executedToolCalls[j]
                // Tool name + arguments
                if (tc.arguments) {
                    total += estimateTokens(JSON.stringify(tc.arguments)) + 20
                }
                // Tool result (can be large for file reads!)
                if (tc.result) {
                    total += estimateTokens(tc.result) + 20
                }
            }
        }
        return total
    }

    function formatTokenCount(value) {
        if (value >= 1000000) return (value / 1000000).toFixed(value >= 10000000 ? 0 : 1) + "M"
        if (value >= 1000) return (value / 1000).toFixed(value >= 10000 ? 0 : 1) + "k"
        return String(value)
    }

    function progressRatio(used, max) {
        if (max <= 0) return 0
        return Math.max(0, Math.min(1, used / max))
    }

    function supportsLiveUsageLimits() {
        return activeProvider === "claude" || activeProvider === "openai"
    }

    function resetUsageLimitInfo() {
        usageLimitLoading = false
        usageLimitStatusCode = 0
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
        var ms = Date.parse(value)
        return isNaN(ms) ? 0 : ms
    }

    function secondsUntil(resetAt) {
        var target = parseResetMillis(resetAt)
        if (target <= 0) return 0
        var deltaMs = target - _timeNowMs
        if (deltaMs < 1000) return 0
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

    function activeUsageLive() {
        return supportsLiveUsageLimits() && (usageLimitLoading || usageLimitRequestLimit > 0 || usageLimitTokenLimit > 0 || usageLimitRetryAfter > 0)
    }

    function currentUsageRatio() {
        if (supportsLiveUsageLimits()) {
            if (usageLimitRetryAfter > 0) return 1
            var metric = dominantUsageMetric()
            if (metric) return Math.max(0, Math.min(1, metric.remainingRatio))
            if (usageLimitLoading) return 0
        }
        return usageBudgetRatio
    }

    function dominantUsageMetric() {
        var metrics = []
        if (usageLimitRequestLimit > 0)
            metrics.push({
                kind: "requests",
                remaining: usageLimitRequestRemaining,
                limit: usageLimitRequestLimit,
                reset: usageLimitRequestResetAt,
                remainingRatio: usageLimitRequestRemaining / usageLimitRequestLimit,
                label: "Requests"
            })
        if (usageLimitTokenLimit > 0)
            metrics.push({
                kind: "tokens",
                remaining: usageLimitTokenRemaining,
                limit: usageLimitTokenLimit,
                reset: usageLimitTokenResetAt,
                remainingRatio: usageLimitTokenRemaining / usageLimitTokenLimit,
                label: "Tokens"
            })
        if (usageLimitInputTokenLimit > 0)
            metrics.push({
                kind: "input_tokens",
                remaining: usageLimitInputTokenRemaining,
                limit: usageLimitInputTokenLimit,
                reset: usageLimitInputTokenResetAt,
                remainingRatio: usageLimitInputTokenRemaining / usageLimitInputTokenLimit,
                label: "Input"
            })
        if (usageLimitOutputTokenLimit > 0)
            metrics.push({
                kind: "output_tokens",
                remaining: usageLimitOutputTokenRemaining,
                limit: usageLimitOutputTokenLimit,
                reset: usageLimitOutputTokenResetAt,
                remainingRatio: usageLimitOutputTokenRemaining / usageLimitOutputTokenLimit,
                label: "Output"
            })
        if (metrics.length === 0) return null
        metrics.sort(function(a, b) { return a.remainingRatio - b.remainingRatio })
        return metrics[0]
    }

    function hasLiveUsageMetric() {
        return dominantUsageMetric() !== null
    }

    function usageCardTitle() {
        if (supportsLiveUsageLimits() && usageLimitRetryAfter > 0) return Lang.get("copilot.waitTime", uiLanguage)
        if (supportsLiveUsageLimits() && !usageLimitLoading && !hasLiveUsageMetric())
            return Lang.get("copilot.apiLimit", uiLanguage)
        return supportsLiveUsageLimits() ? Lang.get("copilot.apiAvailable", uiLanguage) : Lang.get("copilot.usage", uiLanguage)
    }

    function usageCardPercent() {
        if (supportsLiveUsageLimits() && usageLimitRetryAfter > 0) return "100%"
        if (supportsLiveUsageLimits() && !usageLimitLoading && !hasLiveUsageMetric())
            return Lang.get("copilot.notAvailable", uiLanguage)
        return Math.round(currentUsageRatio() * 100) + "%"
    }

    function usageCardDetail() {
        if (supportsLiveUsageLimits()) {
            if (usageLimitLoading) return Lang.get("copilot.loadingLiveLimit", uiLanguage)
            if (usageLimitRetryAfter > 0) return Lang.get("copilot.wait", uiLanguage) + " " + formatDurationShort(usageLimitRetryAfter)
            var metric = dominantUsageMetric()
            if (metric) {
                var resetSecs = secondsUntil(metric.reset)
                return metric.label + " " + Lang.get("copilot.available", uiLanguage) + " " + formatTokenCount(metric.remaining) + "/" + formatTokenCount(metric.limit) +
                    (resetSecs > 0 ? " · " + Lang.get("copilot.resetIn", uiLanguage) + " " + formatDurationShort(resetSecs) : "")
            }
            return usageLimitError !== "" ? usageLimitError : Lang.get("copilot.noLiveHeaders", uiLanguage)
        }
        return formatTokenCount(estimatedConversationTokens) + " / " + formatTokenCount(activeUsageBudget)
    }

    function modelContextWindow() {
        if (activeProvider === "ollama" || activeProvider === "openclaw")
            return ollamaContextWindow > 0 ? ollamaContextWindow : localContextFallback
        if (activeProvider === "claude")
            return 200000
        if (activeProvider === "openai") {
            if (activeModel === "gpt-4o" || activeModel === "gpt-4o-mini" || activeModel === "gpt-4-turbo")
                return 128000
            if (activeModel === "o1" || activeModel === "o3" || activeModel === "o3-mini" || activeModel === "o4-mini")
                return 200000
            return 128000
        }
        if (activeProvider === "perplexity")
            return 127000
        if (activeProvider === "gemini") {
            if (activeModel.indexOf("1.5-pro") >= 0) return 2000000
            if (activeModel.indexOf("1.5-flash") >= 0) return 1000000
            if (activeModel.indexOf("2.0-flash") >= 0) return 1000000
            if (activeModel.indexOf("2.5-pro") >= 0) return 1000000
            return 1000000
        }
        if (activeProvider === "nvidia") {
            if (activeModel.indexOf("llama-3.3-nemotron-super") >= 0) return 1000000
            if (activeModel.indexOf("llama-3.1-nemotron-ultra") >= 0) return 1000000
            if (activeModel.indexOf("llama-3.3-70b") >= 0) return 128000
            return 32000
        }
        return 0
    }

    function usageBudgetTokens() {
        if (activeProvider === "ollama" || activeProvider === "openclaw") return 0
        if (activeProvider === "claude") return 500000
        if (activeProvider === "openai") return 400000
        if (activeProvider === "perplexity") return 250000
        if (activeProvider === "gemini") return 1000000
        if (activeProvider === "nvidia") return 0
        return 0
    }

    readonly property int estimatedConversationTokens: estimateConversationTokens()
    readonly property int activeContextWindow: modelContextWindow()
    readonly property int activeUsageBudget: usageBudgetTokens()
    readonly property real contextUsageRatio: progressRatio(estimatedConversationTokens, activeContextWindow)
    readonly property real usageBudgetRatio: progressRatio(estimatedConversationTokens, activeUsageBudget)

    function sessionFilePath(id) {
        return Quickshell.env("HOME") + "/.config/quickshell/copilot/chats/" + id + ".json"
    }

    function refreshModelContextInfo() {
        if ((activeProvider !== "ollama" && activeProvider !== "openclaw") || activeModel === "") {
            ollamaContextLoading = false
            return
        }
        var detail = activeProvider === "ollama"
            ? ollamaModelDetails.find(function(m) { return m.name === activeModel })
            : openclawModelDetails.find(function(m) { return m.name === activeModel })
        var baseUrl = detail ? detail.url
            : (activeProvider === "ollama"
                ? (ollamaUrls.length > 0 ? ollamaUrls[0] : "http://localhost:11434")
                : (openclawUrls.length > 0 ? openclawUrls[0] : "http://localhost:8080"))
        ollamaContextLoading = true
        loadOllamaContextProc.command = ["python3", "-c",
            "import json, subprocess, sys\n" +
            "url = sys.argv[1].rstrip('/') + '/api/show'\n" +
            "model = sys.argv[2]\n" +
            "payload = json.dumps({'model': model})\n" +
            "ctx = 0\n" +
            "try:\n" +
            "    raw = subprocess.check_output(['curl', '-sf', '--max-time', '4', '-X', 'POST', url, '-H', 'Content-Type: application/json', '-d', payload], stderr=subprocess.DEVNULL)\n" +
            "    data = json.loads(raw.decode('utf-8', 'replace'))\n" +
            "    info = data.get('model_info', {}) or {}\n" +
            "    for key, value in info.items():\n" +
            "        lk = str(key).lower()\n" +
            "        if 'context_length' in lk or 'n_ctx_train' in lk or lk.endswith('.context_length'):\n" +
            "            try:\n" +
            "                ctx = int(value)\n" +
            "                if ctx > 0: break\n" +
            "            except:\n" +
            "                pass\n" +
            "    if not ctx:\n" +
            "        opts = data.get('parameters', '') or ''\n" +
            "        for part in str(opts).split('\\n'):\n" +
            "            if 'num_ctx' in part:\n" +
            "                digits = ''.join(ch for ch in part if ch.isdigit())\n" +
            "                if digits:\n" +
            "                    ctx = int(digits)\n" +
            "                    break\n" +
            "except:\n" +
            "    pass\n" +
            "print(json.dumps({'context': ctx}))\n",
            baseUrl,
            activeModel
        ]
        loadOllamaContextProc.running = true
    }

    function refreshUsageLimitInfo() {
        if (!supportsLiveUsageLimits() || activeModel === "" || currentApiKey() === "") {
            resetUsageLimitInfo()
            return
        }
        usageLimitLoading = true
        usageLimitError = ""
        limitProbeProc.command = ["python3", "-c",
            "import json, subprocess, sys, tempfile, os\n" +
            "provider, model, api_key = sys.argv[1:4]\n" +
            "if provider == 'claude':\n" +
            "    url = 'https://api.anthropic.com/v1/messages'\n" +
            "    headers = [('content-type','application/json'), ('x-api-key', api_key), ('anthropic-version','2023-06-01')]\n" +
            "    body = {'model': model, 'max_tokens': 1, 'messages': [{'role':'user','content':'ping'}]}\n" +
            "elif provider == 'openai':\n" +
            "    headers = [('content-type','application/json'), ('authorization', 'Bearer ' + api_key)]\n" +
            "    if model.startswith('gpt-'):\n" +
            "        url = 'https://api.openai.com/v1/chat/completions'\n" +
            "        body = {'model': model, 'messages': [{'role': 'user', 'content': 'ping'}], 'max_completion_tokens': 16}\n" +
            "    else:\n" +
            "        url = 'https://api.openai.com/v1/responses'\n" +
            "        body = {'model': model, 'input': 'ping', 'max_output_tokens': 64}\n" +
            "        if 'deep-research' in model:\n" +
            "            body['background'] = True\n" +
            "            body['tools'] = [{'type': 'web_search_preview'}]\n" +
            "            body['max_tool_calls'] = 1\n" +
            "elif provider == 'nvidia':\n" +
            "    url = 'https://integrate.api.nvidia.com/v1/chat/completions'\n" +
            "    headers = [('content-type','application/json'), ('authorization', 'Bearer ' + api_key)]\n" +
            "    body = {'model': model, 'messages': [{'role': 'user', 'content': 'ping'}], 'max_tokens': 16}\n" +
            "else:\n" +
            "    print(json.dumps({}))\n" +
            "    sys.exit(0)\n" +
            "tf = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)\n" +
            "json.dump(body, tf)\n" +
            "tf.close()\n" +
            "body_path = tf.name + '.out'\n" +
            "cmd = ['curl', '-sS', '-D', '-', '-o', body_path, '-X', 'POST', url, '--max-time', '12']\n" +
            "for k, v in headers:\n" +
            "    cmd += ['-H', f'{k}: {v}']\n" +
            "cmd += ['--data-binary', '@' + tf.name, '-w', '\\nSTATUS:%{http_code}']\n" +
            "result = {'status': 0}\n" +
            "try:\n" +
            "    raw = subprocess.run(cmd, capture_output=True, text=True)\n" +
            "    text = (raw.stdout or '')\n" +
            "    header_block = text.split('STATUS:', 1)[0]\n" +
            "    status_str = text.split('STATUS:', 1)[1].strip() if 'STATUS:' in text else '0'\n" +
            "    result['status'] = int(status_str) if status_str.isdigit() else 0\n" +
            "    try:\n" +
            "        result['body'] = open(body_path, 'r', encoding='utf-8', errors='replace').read().strip()[:300]\n" +
            "    except:\n" +
            "        result['body'] = ''\n" +
            "    headers_out = {}\n" +
            "    for line in header_block.splitlines():\n" +
            "        if ':' not in line:\n" +
            "            continue\n" +
            "        k, v = line.split(':', 1)\n" +
            "        headers_out[k.strip().lower()] = v.strip()\n" +
            "    result['retry_after'] = int(headers_out.get('retry-after', '0') or '0') if (headers_out.get('retry-after', '0') or '0').isdigit() else 0\n" +
            "    def resolve_reset(raw):\n" +
            "        import re as _re, time as _t\n" +
            "        if not raw: return ''\n" +
            "        raw = raw.strip()\n" +
            "        if _re.match(r'^\\d{10}$', raw): return str(int(raw)*1000)\n" +
            "        if _re.match(r'^\\d{13}$', raw): return raw\n" +
            "        if 'T' in raw or (len(raw) > 8 and '-' in raw): return raw\n" +
            "        total_ms = 0\n" +
            "        for m in _re.finditer(r'(\\d+(?:\\.\\d+)?)(ms|s|m|h|d)', raw):\n" +
            "            n, u = float(m.group(1)), m.group(2)\n" +
            "            total_ms += n if u=='ms' else n*1000 if u=='s' else n*60000 if u=='m' else n*3600000 if u=='h' else n*86400000\n" +
            "        return str(int(_t.time()*1000 + total_ms)) if total_ms > 0 else raw\n" +
            "    if provider == 'claude':\n" +
            "        result['request_limit'] = int(headers_out.get('anthropic-ratelimit-requests-limit', '0') or '0')\n" +
            "        result['request_remaining'] = int(headers_out.get('anthropic-ratelimit-requests-remaining', '0') or '0')\n" +
            "        result['request_reset'] = headers_out.get('anthropic-ratelimit-requests-reset', '')\n" +
            "        result['token_limit'] = int(headers_out.get('anthropic-ratelimit-tokens-limit', '0') or '0')\n" +
            "        result['token_remaining'] = int(headers_out.get('anthropic-ratelimit-tokens-remaining', '0') or '0')\n" +
            "        result['token_reset'] = headers_out.get('anthropic-ratelimit-tokens-reset', '')\n" +
            "        result['input_token_limit'] = int(headers_out.get('anthropic-ratelimit-input-tokens-limit', '0') or '0')\n" +
            "        result['input_token_remaining'] = int(headers_out.get('anthropic-ratelimit-input-tokens-remaining', '0') or '0')\n" +
            "        result['input_token_reset'] = headers_out.get('anthropic-ratelimit-input-tokens-reset', '')\n" +
            "        result['output_token_limit'] = int(headers_out.get('anthropic-ratelimit-output-tokens-limit', '0') or '0')\n" +
            "        result['output_token_remaining'] = int(headers_out.get('anthropic-ratelimit-output-tokens-remaining', '0') or '0')\n" +
            "        result['output_token_reset'] = headers_out.get('anthropic-ratelimit-output-tokens-reset', '')\n" +
            "        result['debug'] = 'provider=' + provider + ' model=' + model + ' status=' + str(result['status']) + ' retry=' + str(result['retry_after']) + ' | req=' + headers_out.get('anthropic-ratelimit-requests-remaining', '?') + '/' + headers_out.get('anthropic-ratelimit-requests-limit', '?') + ' reset=' + headers_out.get('anthropic-ratelimit-requests-reset', '') + ' | tok=' + headers_out.get('anthropic-ratelimit-tokens-remaining', '?') + '/' + headers_out.get('anthropic-ratelimit-tokens-limit', '?') + ' reset=' + headers_out.get('anthropic-ratelimit-tokens-reset', '') + ' | in=' + headers_out.get('anthropic-ratelimit-input-tokens-remaining', '?') + '/' + headers_out.get('anthropic-ratelimit-input-tokens-limit', '?') + ' reset=' + headers_out.get('anthropic-ratelimit-input-tokens-reset', '') + ' | out=' + headers_out.get('anthropic-ratelimit-output-tokens-remaining', '?') + '/' + headers_out.get('anthropic-ratelimit-output-tokens-limit', '?') + ' reset=' + headers_out.get('anthropic-ratelimit-output-tokens-reset', '')\n" +
            "    elif provider == 'openai':\n" +
            "        result['request_limit'] = int(headers_out.get('x-ratelimit-limit-requests', '0') or '0')\n" +
            "        result['request_remaining'] = int(headers_out.get('x-ratelimit-remaining-requests', '0') or '0')\n" +
            "        result['request_reset'] = resolve_reset(headers_out.get('x-ratelimit-reset-requests', ''))\n" +
            "        result['token_limit'] = int(headers_out.get('x-ratelimit-limit-tokens', '0') or '0')\n" +
            "        result['token_remaining'] = int(headers_out.get('x-ratelimit-remaining-tokens', '0') or '0')\n" +
            "        result['token_reset'] = resolve_reset(headers_out.get('x-ratelimit-reset-tokens', ''))\n" +
            "        result['debug'] = 'provider=' + provider + ' model=' + model + ' status=' + str(result['status']) + ' retry=' + str(result['retry_after']) + ' | req=' + headers_out.get('x-ratelimit-remaining-requests', '?') + '/' + headers_out.get('x-ratelimit-limit-requests', '?') + ' reset=' + headers_out.get('x-ratelimit-reset-requests', '') + ' | tok=' + headers_out.get('x-ratelimit-remaining-tokens', '?') + '/' + headers_out.get('x-ratelimit-limit-tokens', '?') + ' reset=' + headers_out.get('x-ratelimit-reset-tokens', '') + (' | body=' + result.get('body', '') if result['status'] >= 400 else '')\n" +
            "    print(json.dumps(result))\n" +
            "except Exception as e:\n" +
            "    print(json.dumps({'status': 0, 'error': str(e)}))\n" +
            "finally:\n" +
            "    try:\n" +
            "        os.unlink(tf.name)\n" +
            "    except:\n" +
            "        pass\n" +
            "    try:\n" +
            "        os.unlink(body_path)\n" +
            "    except:\n" +
            "        pass\n",
            activeProvider,
            activeModel,
            currentApiKey()
        ]
        limitProbeProc.running = true
    }

    function scrollToBottom(force) {
        if (force || !userScrolled) {
            copilotPanel.userScrolled = false
            Qt.callLater(function() {
                chatFlick.contentY = Math.max(0, chatFlick.contentHeight - chatFlick.height)
            })
        }
    }

    function createNewSession() {
        var id = Date.now().toString(36) + Math.random().toString(36).substr(2, 6)
        var session = { id: id, title: "", provider: activeProvider, model: activeModel }
        sessions = [session].concat(sessions)
        activeSessionId = id
        currentMessages = []
        console.log("Created new session:", id)
    }

    function switchToSession(id) {
        if (id === activeSessionId) return

        // Stop any active streaming
        if (isStreaming) {
            stopStreaming()
        }

        _loadingSession = true
        activeSessionId = id
        currentMessages = []
        liveToolCalls = []
        currentToolTurn = 0
        _sessionLoadId = id
        loadSessionProc.running = true
    }

    function deleteSession(id) {
        var remaining = sessions.filter(function(s) { return s.id !== id })
        sessions = remaining
        _deleteSessionId = id
        deleteSessionProc.running = true
        if (activeSessionId === id) {
            var sameProvider = remaining.filter(function(s) { return s.provider === activeProvider })
            if (sameProvider.length > 0) switchToSession(sameProvider[0].id)
            else { activeSessionId = ""; currentMessages = [] }
        }
    }

    function sendMessage(userText) {
        if (userText.trim() === "") return
        if (isStreaming) return
        if (activeModel === "") { statusMessage = "Kein Modell ausgewählt"; return }
        if (activeProvider !== "ollama" && activeProvider !== "openclaw" && currentApiKey() === "") {
            statusMessage = "API-Key fehlt — bitte in den Einstellungen (⚙) eingeben"
            return
        }

        // Ensure a session exists
        if (activeSessionId === "") createNewSession()

        // Append user message + empty assistant placeholder
        var _now = Date.now()
        var newMessages = currentMessages.concat([
            { role: "user", content: userText, ts: _now },
            { role: "assistant", content: "", ts: _now }
        ])
        currentMessages = newMessages
        isStreaming = true
        streamLastLen = 0
        streamAccumulated = ""
        statusMessage = ""
        scrollToBottom(true)

        // Determine URL and key
        var url = ""
        var key = ""
        if (activeProvider === "ollama") {
            var detail = ollamaModelDetails.find(function(m) { return m.name === activeModel })
            url = detail ? detail.url : (ollamaUrls.length > 0 ? ollamaUrls[0] : "http://localhost:11434")
            url = url.replace(/\/$/, "") + "/api/chat"
        } else if (activeProvider === "openclaw") {
            var detail = openclawModelDetails.find(function(m) { return m.name === activeModel })
            url = detail ? detail.url : (openclawUrls.length > 0 ? openclawUrls[0] : "http://localhost:8080")
            url = url.replace(/\/$/, "") + "/api/chat"
        } else if (activeProvider === "claude") {
            url = "https://api.anthropic.com/v1/messages"
            key = claudeApiKey
        } else if (activeProvider === "openai") {
            url = "https://api.openai.com/v1/chat/completions"
            key = openaiApiKey
        } else if (activeProvider === "perplexity") {
            url = "https://api.perplexity.ai/chat/completions"
            key = perplexityApiKey
        } else if (activeProvider === "gemini") {
            // Gemini key goes in the URL as a query param
            url = "https://generativelanguage.googleapis.com/v1beta/models/" +
                  activeModel + ":streamGenerateContent?alt=sse&key=" + geminiApiKey
            key = ""
        } else if (activeProvider === "nvidia") {
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            key = nvidiaApiKey
        }

        _chatProvider = activeProvider
        _chatModel    = activeModel
        _chatApiKey   = key
        _chatMessagesJson = JSON.stringify(currentMessages.slice(0, -1))  // exclude the empty assistant placeholder
        _chatUserMessage = userText

        // Use tool executor if tools are enabled
        if (toolsEnabled && (activeProvider === "ollama" || activeProvider === "nvidia" || activeProvider === "claude" || activeProvider === "openai")) {
            executedToolCalls = []

            if (activeProvider === "ollama") {
                // Ollama uses OpenAI-compatible REST API for tools
                var baseUrl = url.replace("/api/chat", "")
                _chatUrl = baseUrl + "/v1/chat/completions"
                agentToolProc.running = true
            } else if (activeProvider === "claude") {
                // Claude uses Anthropic API with tool support
                _chatUrl = url
                agentToolProc.running = true
            } else if (activeProvider === "openai") {
                // OpenAI uses standard API with tool support
                _chatUrl = url
                agentToolProc.running = true
            } else {
                // NVIDIA
                _chatUrl = url
                agentToolProc.running = true
            }
        } else {
            _chatUrl = url
            // Use dedicated OpenClaw chat process for OpenClaw provider
            if (activeProvider === "openclaw") {
                openclawChatProc.running = true
            } else {
                chatProc.running = true
            }
        }
    }

    function stopStreaming() {
        chatProc.running = false
        openclawChatProc.running = false
        openclawAgentProc.running = false
        agentToolProc.running = false
        isStreaming = false
        // Strip cursor from last message
        if (currentMessages.length > 0) {
            var msgs = currentMessages.slice(0, -1)
            var _last = currentMessages[currentMessages.length - 1]
            msgs.push({ role: "assistant", content: streamAccumulated, ts: _last.ts || Date.now() })
            currentMessages = msgs
        }
        streamLastLen = 0
        streamAccumulated = ""
    }

    function saveCurrentSession() {
        if (activeSessionId === "" || currentMessages.length === 0) return
        // Auto-title from first user message
        var title = ""
        var s = sessions.find(function(x) { return x.id === activeSessionId })
        if (s) title = s.title
        if (title === "") {
            var firstUser = currentMessages.find(function(m) { return m.role === "user" })
            if (firstUser) title = firstUser.content.substring(0, 50).replace(/\n/g, " ")
        }
        // Update title in sessions list
        sessions = sessions.map(function(x) {
            return x.id === activeSessionId ? { id: x.id, title: title, provider: activeProvider, model: activeModel } : x
        })
        _sessionSaveJson = JSON.stringify({
            id: activeSessionId, title: title,
            provider: activeProvider, model: activeModel,
            messages: currentMessages
        })
        saveSessionProc.running = true
    }

    // ── Processes ──────────────────────────────────────────────────────────
    Process {
        id: loadModelsProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var result = JSON.parse(text.trim())
                    copilotPanel.ollamaModelDetails = result.models || []
                    copilotPanel.ollamaModels = (result.models || []).map(function(m) { return m.name })
                    copilotPanel.ollamaUrlStatuses = result.results || []
                    if (copilotPanel.activeProvider === "ollama" && copilotPanel.activeModel === "" &&
                            copilotPanel.ollamaModelDetails.length > 0)
                        copilotPanel.activeModel = copilotPanel.ollamaModelDetails[0].name
                } catch(e) { console.error("loadModelsProc parse error:", e) }
            }
        }
    }

    Process {
        id: loadOllamaContextProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                copilotPanel.ollamaContextLoading = false
                try {
                    var result = JSON.parse(text.trim())
                    copilotPanel.ollamaContextWindow = result.context || 0
                } catch(e) {
                    copilotPanel.ollamaContextWindow = 0
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                copilotPanel.ollamaContextLoading = false
                if (text.trim() !== "")
                    console.error("loadOllamaContextProc:", text.trim())
            }
        }
    }

    Process {
        id: limitProbeProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                copilotPanel.usageLimitLoading = false
                try {
                    var result = JSON.parse(text.trim())
                    copilotPanel.usageLimitStatusCode = result.status || 0
                    copilotPanel.usageLimitRetryAfter = result.retry_after || 0
                    copilotPanel.usageLimitRequestLimit = result.request_limit || 0
                    copilotPanel.usageLimitRequestRemaining = result.request_remaining || 0
                    copilotPanel.usageLimitRequestResetAt = result.request_reset || ""
                    copilotPanel.usageLimitTokenLimit = result.token_limit || 0
                    copilotPanel.usageLimitTokenRemaining = result.token_remaining || 0
                    copilotPanel.usageLimitTokenResetAt = result.token_reset || ""
                    copilotPanel.usageLimitInputTokenLimit = result.input_token_limit || 0
                    copilotPanel.usageLimitInputTokenRemaining = result.input_token_remaining || 0
                    copilotPanel.usageLimitInputTokenResetAt = result.input_token_reset || ""
                    copilotPanel.usageLimitOutputTokenLimit = result.output_token_limit || 0
                    copilotPanel.usageLimitOutputTokenRemaining = result.output_token_remaining || 0
                    copilotPanel.usageLimitOutputTokenResetAt = result.output_token_reset || ""
                    copilotPanel.usageLimitError = result.error || ""
                    copilotPanel.usageLimitDebugSummary = result.debug || ""
                    if (copilotPanel.usageLimitDebugSummary !== "")
                        console.log("[CopilotLimitProbe]", copilotPanel.usageLimitDebugSummary)
                } catch(e) {
                    copilotPanel.usageLimitError = "Probe fehlgeschlagen"
                    copilotPanel.usageLimitDebugSummary = ""
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                copilotPanel.usageLimitLoading = false
                if (text.trim() !== "")
                    console.error("limitProbeProc:", text.trim())
            }
        }
    }

    // ── Ollama Network Scan ────────────────────────────────────────────────
    Process {
        id: scanOllamaProc
        command: ["python3", "-c",
            "import socket, subprocess, json, concurrent.futures, sys\n" +
            "# Scan for Ollama servers only\n" +
            "def scan_ollama(ip, port=11434):\n" +
            "    try:\n" +
            "        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n" +
            "        sock.settimeout(0.3)\n" +
            "        result = sock.connect_ex((ip, port))\n" +
            "        sock.close()\n" +
            "        if result == 0:\n" +
            "            try:\n" +
            "                r = subprocess.check_output(['curl', '-sf', '--max-time', '1', f'http://{ip}:{port}/api/tags'], stderr=subprocess.DEVNULL)\n" +
            "                data = json.loads(r)\n" +
            "                model_count = len(data.get('models', []))\n" +
            "                version = data.get('version', '')\n" +
            "                return {'url': f'http://{ip}:{port}', 'ip': ip, 'port': port, 'version': f'{model_count} models' + (f' • {version}' if version else '')}\n" +
            "            except: pass\n" +
            "        return None\n" +
            "    except: return None\n" +
            "\n" +
            "# Get local subnet\n" +
            "def get_local_subnet():\n" +
            "    try:\n" +
            "        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n" +
            "        s.connect(('8.8.8.8', 80))\n" +
            "        local_ip = s.getsockname()[0]\n" +
            "        s.close()\n" +
            "        return '.'.join(local_ip.split('.')[:3])\n" +
            "    except:\n" +
            "        try:\n" +
            "            result = subprocess.check_output(['ip', 'addr', 'show'], text=True)\n" +
            "            for line in result.split('\\n'):\n" +
            "                if 'inet ' in line and '127.0.0.1' not in line:\n" +
            "                    ip = line.split()[1].split('/')[0]\n" +
            "                    return '.'.join(ip.split('.')[:3])\n" +
            "        except: pass\n" +
            "        return '192.168.1'\n" +
            "\n" +
            "base = get_local_subnet()\n" +
            "print(f'Scanning {base}.0/24 for Ollama servers...', file=sys.stderr)\n" +
            "\n" +
            "# Get all local IPs\n" +
            "local_ips = ['127.0.0.1']\n" +
            "try:\n" +
            "    result = subprocess.check_output(['ip', 'addr', 'show'], text=True)\n" +
            "    for line in result.split('\\n'):\n" +
            "        if 'inet ' in line and '127.0.0.1' not in line:\n" +
            "            ip = line.split()[1].split('/')[0]\n" +
            "            local_ips.append(ip)\n" +
            "except: pass\n" +
            "\n" +
            "found = []\n" +
            "# Priority IPs first\n" +
            "priority = [1, 2] + list(range(100, 111)) + list(range(200, 221)) + list(range(170, 191))\n" +
            "other = [i for i in range(1, 255) if i not in priority]\n" +
            "all_ips = priority + other\n" +
            "\n" +
            "with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:\n" +
            "    futures = {executor.submit(scan_ollama, f'{base}.{i}'): i for i in all_ips}\n" +
            "    for future in concurrent.futures.as_completed(futures):\n" +
            "        result = future.result()\n" +
            "        if result:\n" +
            "            found.append(result)\n" +
            "            print(f\"Found Ollama: {result['url']} - {result.get('version', '')}\", file=sys.stderr)\n" +
            "            if len(found) >= 10: break\n" +
            "\n" +
            "print(json.dumps({'found': found, 'localIps': local_ips}))\n"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                copilotPanel.scanningOllama = false
                console.log("[Ollama] Scan output:", text.trim())
                try {
                    var result = JSON.parse(text.trim())
                    var found = result.found || []
                    var localIps = result.localIps || []  // Get local machine IPs from scan

                    // Filter out already added instances
                    found = found.filter(function(instance) {
                        var foundIp = instance.ip
                        var foundPort = String(instance.port)

                        for (var i = 0; i < copilotPanel.ollamaUrls.length; i++) {
                            var existing = copilotPanel.ollamaUrls[i]
                            var existingIp = existing.replace(/^https?:\/\//, '').split(':')[0]
                            var existingPort = existing.split(':').pop()

                            // Both refer to localhost?
                            var existingIsLocal = (existingIp === 'localhost' || existingIp === '127.0.0.1' || localIps.indexOf(existingIp) !== -1)
                            var foundIsLocal = (foundIp === '127.0.0.1' || localIps.indexOf(foundIp) !== -1)

                            if (existingIsLocal && foundIsLocal && existingPort === foundPort)
                                return false  // Both localhost, same port = duplicate

                            // Exact IP:port match
                            if (existingIp === foundIp && existingPort === foundPort)
                                return false
                        }
                        return true
                    })
                    console.log("[Ollama] Found instances:", found.length, "(after filtering)")
                    copilotPanel.foundOllamaInstances = found
                } catch(e) {
                    console.error("[Ollama] Scan parse error:", e)
                    copilotPanel.foundOllamaInstances = []
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "")
                    console.log("[Ollama] Scan info:", text.trim())
            }
        }
    }

    // ── OpenClaw Processes ─────────────────────────────────────────────────
    Process {
        id: loadOpenclawModelsProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                console.log("[OpenClaw] Load models output:", text.trim().substring(0, 200))
                try {
                    var result = JSON.parse(text.trim())
                    copilotPanel.openclawModelDetails = result.models || []
                    copilotPanel.openclawModels = (result.models || []).map(function(m) { return m.name })
                    copilotPanel.openclawUrlStatuses = result.results || []
                    var okCount = 0
                    var errCount = 0
                    for (var i = 0; i < copilotPanel.openclawUrlStatuses.length; i++) {
                        if ((copilotPanel.openclawUrlStatuses[i].status || "") === "ok")
                            okCount++
                        else
                            errCount++
                    }
                    if (copilotPanel.openclawUrlStatuses.length === 0) {
                        copilotPanel.openclawHealthState = "error"
                        copilotPanel.openclawHealthMessage = "No OpenClaw URL configured"
                    } else if (errCount === 0) {
                        copilotPanel.openclawHealthState = "ok"
                        copilotPanel.openclawHealthMessage = "Health check passed (" + okCount + " URL" + (okCount === 1 ? "" : "s") + ")"
                    } else {
                        copilotPanel.openclawHealthState = "error"
                        copilotPanel.openclawHealthMessage = "Health check failed (" + errCount + " error" + (errCount === 1 ? "" : "s") + ")"
                    }
                    console.log("[OpenClaw] Loaded", copilotPanel.openclawModels.length, "models")
                    if (copilotPanel.activeProvider === "openclaw" && copilotPanel.activeModel === "" &&
                            copilotPanel.openclawModelDetails.length > 0)
                        copilotPanel.activeModel = copilotPanel.openclawModelDetails[0].name
                } catch(e) {
                    copilotPanel.openclawHealthState = "error"
                    copilotPanel.openclawHealthMessage = "Health check parse error"
                    console.error("[OpenClaw] loadOpenclawModelsProc parse error:", e, "- raw:", text)
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "")
                    console.error("[OpenClaw] loadOpenclawModelsProc stderr:", text.trim())
            }
        }
    }

    Process {
        id: pairProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onTextChanged: {
                var lines = text.trim().split('\n')
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim()
                    if (line === "") continue
                    try {
                        var result = JSON.parse(line)
                        if (result.status === "success") {
                            console.log("[OpenClaw] ✓", result.message)
                            if (result.token) {
                                console.log("[OpenClaw] Token received, saving...")
                                copilotPanel.openclawToken = result.token
                                copilotPanel._saveKeyName = "openclaw-token"
                                copilotPanel._saveKeyValue = result.token
                                saveKeyProc.running = true
                            }
                        } else if (result.status === "pairing_required") {
                            console.log("[OpenClaw] ⏳", result.message)
                            console.log("[OpenClaw] Device ID:", result.deviceId)
                        } else if (result.status === "sent") {
                            console.log("[OpenClaw] →", result.message)
                        } else if (result.status === "timeout") {
                            console.error("[OpenClaw] ⏱", result.message)
                        } else if (result.status === "error") {
                            console.error("[OpenClaw] ✗", result.message, result.code || "")
                        }
                    } catch(e) {}
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "")
                    console.error("[OpenClaw] Pairing error:", text.trim())
            }
        }
    }

    /* Process {
        id: pairOpenclawProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onTextChanged: {
                // Handle streaming status updates
                var lines = text.trim().split('\n')
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim()
                    if (line === "") continue
                    try {
                        var result = JSON.parse(line)
                        if (result.status === "success") {
                            console.log("[OpenClaw] ✓", result.message)
                            if (result.token) {
                                console.log("[OpenClaw] Token received, saving...")
                                copilotPanel.openclawToken = result.token
                                copilotPanel._saveKeyName = "openclaw-token"
                                copilotPanel._saveKeyValue = result.token
                                saveKeyProc.running = true
                            }
                        } else if (result.status === "pairing_required") {
                            console.log("[OpenClaw] ⏳", result.message)
                            console.log("[OpenClaw] Device ID:", result.deviceId)
                        } else if (result.status === "sent") {
                            console.log("[OpenClaw] →", result.message)
                        } else if (result.status === "timeout") {
                            console.error("[OpenClaw] ⏱", result.message)
                        } else if (result.status === "error") {
                            console.error("[OpenClaw] ✗", result.message, result.code || "")
                        }
                    } catch(e) {
                        // Ignore non-JSON lines
                    }
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "")
                    console.error("[OpenClaw] pairOpenclawProc stderr:", text.trim())
            }
        }
    } */

    // Scan for OpenClaw Gateways via HTTP port scan (port 18789)
    Process {
        id: scanOpenclawProc
        command: ["python3", "-c",
            "import socket, subprocess, json, concurrent.futures, sys\n" +
            "# Scan for OpenClaw Gateways (port 18789)\n" +
            "def scan_openclaw(ip, port=18789):\n" +
            "    try:\n" +
            "        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n" +
            "        sock.settimeout(0.3)\n" +
            "        result = sock.connect_ex((ip, port))\n" +
            "        sock.close()\n" +
            "        if result == 0:\n" +
            "            # Port is open - assume it's OpenClaw Gateway\n" +
            "            return {\n" +
            "                'url': f'ws://{ip}:{port}',\n" +
            "                'ip': ip,\n" +
            "                'port': port,\n" +
            "                'hostname': ip,\n" +
            "                'displayName': f'OpenClaw Gateway ({ip})',\n" +
            "                'version': 'Gateway'\n" +
            "            }\n" +
            "        return None\n" +
            "    except: return None\n" +
            "\n" +
            "# Get local subnet\n" +
            "def get_local_subnet():\n" +
            "    try:\n" +
            "        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n" +
            "        s.connect(('8.8.8.8', 80))\n" +
            "        local_ip = s.getsockname()[0]\n" +
            "        s.close()\n" +
            "        return '.'.join(local_ip.split('.')[:3])\n" +
            "    except:\n" +
            "        try:\n" +
            "            result = subprocess.check_output(['ip', 'addr', 'show'], text=True)\n" +
            "            for line in result.split('\\n'):\n" +
            "                if 'inet ' in line and '127.0.0.1' not in line:\n" +
            "                    ip = line.split()[1].split('/')[0]\n" +
            "                    return '.'.join(ip.split('.')[:3])\n" +
            "        except: pass\n" +
            "        return '192.168.1'\n" +
            "\n" +
            "base = get_local_subnet()\n" +
            "print(f'Scanning {base}.0/24 for OpenClaw Gateways (port 18789)...', file=sys.stderr)\n" +
            "\n" +
            "found = []\n" +
            "# Priority IPs\n" +
            "priority = [1, 2] + list(range(100, 111)) + list(range(200, 221)) + list(range(170, 191))\n" +
            "other = [i for i in range(1, 255) if i not in priority]\n" +
            "all_ips = priority + other\n" +
            "\n" +
            "found_ips = set()\n" +
            "with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:\n" +
            "    futures = {executor.submit(scan_openclaw, f'{base}.{i}'): i for i in all_ips}\n" +
            "    for future in concurrent.futures.as_completed(futures):\n" +
            "        result = future.result()\n" +
            "        if result:\n" +
            "            # Prevent duplicates\n" +
            "            ip_key = result['ip'] + ':' + str(result['port'])\n" +
            "            if ip_key not in found_ips:\n" +
            "                found_ips.add(ip_key)\n" +
            "                found.append(result)\n" +
            "                print(f\"Found OpenClaw Gateway: {result['ip']}:{result['port']}\", file=sys.stderr)\n" +
            "            if len(found) >= 10: break\n" +
            "\n" +
            "print(json.dumps({'found': found}))\n"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                copilotPanel.scanningOpenclaw = false
                console.log("[OpenClaw] Scan output:", text.trim())
                try {
                    var result = JSON.parse(text.trim())
                    var found = result.found || []
                    // Filter out already added instances
                    found = found.filter(function(instance) {
                        // Check exact match
                        if (copilotPanel.openclawUrls.indexOf(instance.url) !== -1) return false
                        // Check if same IP already added
                        for (var i = 0; i < copilotPanel.openclawUrls.length; i++) {
                            var existing = copilotPanel.openclawUrls[i]
                            var existingIp = existing.replace(/^wss?:\/\//, '').split(':')[0]
                            if (existingIp === instance.ip) return false
                        }
                        return true
                    })
                    console.log("[OpenClaw] Found gateways:", found.length, "(after filtering)")
                    copilotPanel.foundOpenclawInstances = found
                } catch(e) {
                    console.error("[OpenClaw] Scan parse error:", e)
                    copilotPanel.foundOpenclawInstances = []
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "")
                    console.log("[OpenClaw] Scan info:", text.trim())
            }
        }
    }

    // WebSocket pairing process
    Process {
        id: pairOpenclawProc
        command: []
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                console.log("[OpenClaw] Pairing result:", text.trim())
                try {
                    var result = JSON.parse(text.trim())
                    var url = result.url
                    var status = copilotPanel.openclawPairingStatus

                    if (result.status === "success") {
                        // Save token
                        copilotPanel.openclawToken = result.token
                        copilotPanel._saveKeyName = "openclaw-token"
                        copilotPanel._saveKeyValue = result.token
                        saveKeyProc.running = true

                        // Add URL to list
                        if (copilotPanel.openclawUrls.indexOf(url) === -1) {
                            var urls = copilotPanel.openclawUrls.slice()
                            urls.push(url)
                            copilotPanel.openclawUrls = urls
                        }

                        // Remove from found list
                        copilotPanel.foundOpenclawInstances = copilotPanel.foundOpenclawInstances.filter(function(i) {
                            return i.url !== url
                        })

                        status[url] = {status: "success", message: "Paired successfully"}
                    } else {
                        status[url] = {status: "error", message: result.error || "Pairing failed"}
                    }
                    copilotPanel.openclawPairingStatus = status
                } catch(e) {
                    console.error("[OpenClaw] Pairing parse error:", e)
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "")
                    console.log("[OpenClaw] Pairing info:", text.trim())
            }
        }
    }

    function startOpenclawPairing(url) {
        var status = copilotPanel.openclawPairingStatus
        status[url] = {status: "pending", message: "Waiting for approval..."}
        copilotPanel.openclawPairingStatus = status

        pairOpenclawProc.command = ["python3", "-c",
            "import asyncio, websockets, json, sys, uuid, socket\n" +
            "async def pair():\n" +
            "    url = '" + url + "'\n" +
            "    try:\n" +
            "        print(f'Connecting to {url}...', file=sys.stderr)\n" +
            "        async with await asyncio.wait_for(websockets.connect(url), timeout=10) as ws:\n" +
            "            # Get challenge\n" +
            "            response = await asyncio.wait_for(ws.recv(), timeout=10)\n" +
            "            data = json.loads(response)\n" +
            "            print(f'Received challenge: {data}', file=sys.stderr)\n" +
            "            \n" +
            "            if data.get('type') == 'event' and data.get('event') == 'connect.challenge':\n" +
            "                nonce = data.get('payload', {}).get('nonce')\n" +
            "                device_id = str(uuid.uuid4())\n" +
            "                \n" +
            "                # Step 1: Send connect request (handshake)\n" +
            "                connect_id = str(uuid.uuid4())\n" +
            "                connect_msg = {\n" +
            "                    'type': 'req',\n" +
            "                    'id': connect_id,\n" +
            "                    'method': 'connect',\n" +
            "                    'params': {\n" +
            "                        'minProtocol': 1,\n" +
            "                        'maxProtocol': 1,\n" +
            "                        'role': 'node',\n" +
            "                        'device': {\n" +
            "                            'id': device_id,\n" +
            "                            'name': 'QuickShell',\n" +
            "                            'platform': 'linux',\n" +
            "                            'hostname': socket.gethostname()\n" +
            "                        }\n" +
            "                    }\n" +
            "                }\n" +
            "                await ws.send(json.dumps(connect_msg))\n" +
            "                print('Sent connect request...', file=sys.stderr)\n" +
            "                \n" +
            "                # Get connect response\n" +
            "                response = await asyncio.wait_for(ws.recv(), timeout=10)\n" +
            "                data = json.loads(response)\n" +
            "                print(f'Connect response: {data}', file=sys.stderr)\n" +
            "                \n" +
            "                if data.get('type') == 'res' and data.get('id') == connect_id and data.get('ok'):\n" +
            "                    # Step 2: Send pairing request\n" +
            "                    pair_id = str(uuid.uuid4())\n" +
            "                    pair_msg = {\n" +
            "                        'type': 'req',\n" +
            "                        'id': pair_id,\n" +
            "                        'method': 'node.pair.request',\n" +
            "                        'params': {}\n" +
            "                    }\n" +
            "                    await ws.send(json.dumps(pair_msg))\n" +
            "                    print('Sent pairing request, waiting for approval...', file=sys.stderr)\n" +
            "                    \n" +
            "                    # Wait for pairing response and events\n" +
            "                    while True:\n" +
            "                        response = await asyncio.wait_for(ws.recv(), timeout=300)\n" +
            "                        data = json.loads(response)\n" +
            "                        print(f'Received: {data}', file=sys.stderr)\n" +
            "                        \n" +
            "                        if data.get('type') == 'res' and data.get('id') == pair_id:\n" +
            "                            if data.get('ok'):\n" +
            "                                print('Pairing request accepted, waiting for approval...', file=sys.stderr)\n" +
            "                            else:\n" +
            "                                error = str(data.get('error', 'Request failed'))\n" +
            "                                print(json.dumps({'url': url, 'status': 'error', 'error': error}))\n" +
            "                                break\n" +
            "                        \n" +
            "                        elif data.get('type') == 'event':\n" +
            "                            event = data.get('event')\n" +
            "                            payload = data.get('payload', {})\n" +
            "                            \n" +
            "                            if event == 'node.pair.resolved' and payload.get('approved'):\n" +
            "                                token = payload.get('token')\n" +
            "                                if token:\n" +
            "                                    print(json.dumps({'url': url, 'status': 'success', 'token': token}))\n" +
            "                                    break\n" +
            "                            elif event == 'node.pair.resolved' and not payload.get('approved'):\n" +
            "                                print(json.dumps({'url': url, 'status': 'error', 'error': 'Pairing rejected by user'}))\n" +
            "                                break\n" +
            "                else:\n" +
            "                    error = str(data.get('error', 'Connect failed'))\n" +
            "                    print(json.dumps({'url': url, 'status': 'error', 'error': error}))\n" +
            "            else:\n" +
            "                print(json.dumps({'url': url, 'status': 'error', 'error': 'No challenge received'}))\n" +
            "    except asyncio.TimeoutError:\n" +
            "        print(json.dumps({'url': url, 'status': 'error', 'error': 'Timeout - no approval within 5 minutes'}))\n" +
            "    except Exception as e:\n" +
            "        print(json.dumps({'url': url, 'status': 'error', 'error': str(e)}))\n" +
            "\n" +
            "asyncio.run(pair())\n"
        ]
        pairOpenclawProc.running = true
    }

    function startLoadOpenclawModels() {
        var urls = copilotPanel.openclawUrls.filter(function(u) { return u.trim() !== "" })
        if (urls.length === 0) return
        var token = copilotPanel.openclawToken
        // Set all to checking
        copilotPanel.openclawUrlStatuses = urls.map(function(u) { return {url: u, status: "checking"} })
        loadOpenclawModelsProc.command = [
            "python3",
            Quickshell.env("HOME") + "/.config/quickshell/copilot/openclaw_models_multi.py",
            JSON.stringify(urls),
            token
        ]
        loadOpenclawModelsProc.running = true
    }

    function pairOpenclawDevice(url) {
        console.log("[OpenClaw] Starting pairing for:", url)
        var token = copilotPanel.openclawToken || ""
        pairProc.command = ["python3", Quickshell.env("HOME") + "/.config/quickshell/copilot/openclaw_pair.py", url, token]
        pairProc.running = true
    }

    function startLoadModels() {
        var urls = copilotPanel.ollamaUrls.filter(function(u) { return u.trim() !== "" })
        if (urls.length === 0) return
        // Set all to checking
        copilotPanel.ollamaUrlStatuses = urls.map(function(u) { return {url: u, status: "checking"} })
        loadModelsProc.command = ["python3", "-c",
            "import json, subprocess, sys\n" +
            "urls = " + JSON.stringify(urls) + "\n" +
            "all_models = []\n" +
            "results = []\n" +
            "for url in urls:\n" +
            "    try:\n" +
            "        # Normalize URL - strip whitespace and ensure http://\n" +
            "        url = url.strip()\n" +
            "        if not url.startswith('http://') and not url.startswith('https://'):\n" +
            "            url = 'http://' + url\n" +
            "        # Ensure port is present\n" +
            "        if ':' not in url.split('//')[1]:\n" +
            "            url = url + ':11434'\n" +
            "        full_url = url.rstrip('/') + '/api/tags'\n" +
            "        print(f'Checking {full_url}', file=sys.stderr)\n" +
            "        r = subprocess.check_output(['curl', '-sf', '--max-time', '4', full_url], stderr=subprocess.DEVNULL)\n" +
            "        models = json.loads(r).get('models', [])\n" +
            "        for m in models:\n" +
            "            sz = m.get('size', 0)\n" +
            "            sz_gb = round(sz / 1e9, 1) if sz > 1e8 else round(sz / 1e6)\n" +
            "            sz_str = str(sz_gb) + ' GB' if sz > 1e8 else str(sz_gb) + ' MB'\n" +
            "            fam = m.get('details', {}).get('family', '')\n" +
            "            all_models.append({'name': m['name'], 'size': sz_str, 'family': fam, 'url': url})\n" +
            "        results.append({'url': url, 'status': 'ok', 'count': len(models)})\n" +
            "    except Exception as e:\n" +
            "        print(f'Error checking {url}: {e}', file=sys.stderr)\n" +
            "        results.append({'url': url, 'status': 'error'})\n" +
            "print(json.dumps({'models': all_models, 'results': results}))\n"
        ]
        loadModelsProc.running = true
    }

    Process {
        id: listSessionsProc
        command: ["python3", "-c",
            "import json, os, glob\n" +
            "d = (__import__('os').path.expanduser('~/.config/quickshell/copilot/chats'))\n" +
            "result = []\n" +
            "for p in sorted(glob.glob(d + '/*.json'), key=os.path.getmtime, reverse=True):\n" +
            "    try:\n" +
            "        s = json.load(open(p, encoding='utf-8'))\n" +
            "        result.append({'id': s['id'], 'title': s.get('title',''), 'provider': s.get('provider','ollama'), 'model': s.get('model','')})\n" +
            "    except: pass\n" +
            "print(json.dumps(result))\n"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var loaded = JSON.parse(text.trim())
                    if (Array.isArray(loaded)) {
                        copilotPanel.sessions = loaded
                    }
                } catch(e) {}
            }
        }
    }

    // ── Chat binding slots ──────────────────────────────────────────────────
    property string _chatProvider: ""
    property string _chatModel: ""
    property string _chatApiKey: ""
    property string _chatUrl: ""
    property string _chatMessagesJson: "[]"
    property string _chatUserMessage: ""
    property string _sessionSaveJson: "{}"
    property string _sessionLoadId: ""
    property string _deleteSessionId: ""
    property string _fetchProvider: ""
    property string _fetchApiKey: ""

    // Streaming via curl -N (no buffering) + subprocess for true real-time output
    Process {
        id: chatProc
        command: ["python3", "-c",
            "import sys, json, os, subprocess, tempfile\n" +
            "provider = sys.argv[1]\n" +
            "model    = sys.argv[2]\n" +
            "api_key  = sys.argv[3]\n" +
            "url      = sys.argv[4]\n" +
            "messages = json.loads(sys.argv[5])\n" +
            "msgs = [{'role': m['role'], 'content': m.get('content', '')} for m in messages]\n" +
            "if provider == 'ollama':\n" +
            "    body = {'model': model, 'stream': True, 'messages': msgs}\n" +
            "    hdrs = [('Content-Type', 'application/json')]\n" +
            "elif provider == 'claude':\n" +
            "    body = {'model': model, 'max_tokens': 4096, 'stream': True, 'messages': msgs}\n" +
            "    hdrs = [('Content-Type','application/json'),('x-api-key',api_key),('anthropic-version','2023-06-01')]\n" +
            "elif provider == 'gemini':\n" +
            "    contents = []\n" +
            "    for m in messages:\n" +
            "        role = 'model' if m['role'] == 'assistant' else 'user'\n" +
            "        contents.append({'role': role, 'parts': [{'text': m['content']}]})\n" +
            "    body = {'contents': contents, 'generationConfig': {'maxOutputTokens': 4096}}\n" +
            "    hdrs = [('Content-Type','application/json')]\n" +
            "else:\n" +
            "    body = {'model': model, 'stream': True, 'messages': msgs}\n" +
            "    hdrs = [('Content-Type','application/json'),('Authorization','Bearer '+api_key)]\n" +
            "tf = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)\n" +
            "json.dump(body, tf); tf.close()\n" +
            "hdr_args = [a for h in hdrs for a in ['-H', h[0]+': '+h[1]]]\n" +
            "cmd = ['curl','-sS','-N','-X','POST',url]+hdr_args+['--data-binary','@'+tf.name]\n" +
            "print('DEBUG: provider='+provider+' model='+model+' url='+url, file=sys.stderr, flush=True)\n" +
            "err_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.err', delete=False)\n" +
            "err_path = err_file.name; err_file.close()\n" +
            "try:\n" +
            "    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=open(err_path,'w'), bufsize=1)\n" +
            "    for raw in proc.stdout:\n" +
            "        line = raw.decode('utf-8','replace').rstrip('\\r\\n')\n" +
            "        if provider == 'ollama':\n" +
            "            if not line: continue\n" +
            "            try:\n" +
            "                c = json.loads(line)\n" +
            "                t = c.get('message',{}).get('content','')\n" +
            "                if t: sys.stdout.write(t); sys.stdout.flush()\n" +
            "                if c.get('done'): break\n" +
            "            except: pass\n" +
            "        elif provider == 'claude':\n" +
            "            if not line.startswith('data:'): continue\n" +
            "            try:\n" +
            "                c = json.loads(line[5:])\n" +
            "                if c.get('type')=='content_block_delta' and c['delta'].get('type')=='text_delta':\n" +
            "                    sys.stdout.write(c['delta']['text']); sys.stdout.flush()\n" +
            "            except: pass\n" +
            "        elif provider == 'gemini':\n" +
            "            if not line.startswith('data:'): continue\n" +
            "            p = line[5:].strip()\n" +
            "            if not p: continue\n" +
            "            try:\n" +
            "                c = json.loads(p)\n" +
            "                parts = c.get('candidates',[{}])[0].get('content',{}).get('parts',[])\n" +
            "                for part in parts:\n" +
            "                    t = part.get('text','')\n" +
            "                    if t: sys.stdout.write(t); sys.stdout.flush()\n" +
            "            except: pass\n" +
            "        else:\n" +
            "            if not line.startswith('data:'): continue\n" +
            "            p = line[5:].strip()\n" +
            "            if p=='[DONE]': break\n" +
            "            if not p: continue\n" +
            "            try:\n" +
            "                c = json.loads(p)\n" +
            "                if 'error' in c:\n" +
            "                    print('API_ERROR: '+str(c['error']), file=sys.stderr, flush=True)\n" +
            "                    break\n" +
            "                t = c['choices'][0]['delta'].get('content')\n" +
            "                if t: sys.stdout.write(t); sys.stdout.flush()\n" +
            "            except Exception as ex:\n" +
            "                print('PARSE_ERROR: '+str(ex)+' | line='+p[:100], file=sys.stderr, flush=True)\n" +
            "    proc.wait()\n" +
            "    if proc.returncode != 0:\n" +
            "        try:\n" +
            "            curl_err = open(err_path).read()\n" +
            "            print('CURL_ERROR (rc='+str(proc.returncode)+'): '+curl_err[:500], file=sys.stderr, flush=True)\n" +
            "        except: pass\n" +
            "except Exception as e:\n" +
            "    print('FEHLER: '+str(e), file=sys.stderr, flush=True)\n" +
            "finally:\n" +
            "    try: os.unlink(tf.name)\n" +
            "    except: pass\n" +
            "    try: os.unlink(err_path)\n" +
            "    except: pass\n",
            copilotPanel._chatProvider,
            copilotPanel._chatModel,
            copilotPanel._chatApiKey,
            copilotPanel._chatUrl,
            copilotPanel._chatMessagesJson
        ]
        running: false

        stdout: StdioCollector {
            onTextChanged: {
                if (!copilotPanel.isStreaming) return
                var chunk = text.substring(copilotPanel.streamLastLen)
                copilotPanel.streamLastLen = text.length
                if (chunk === "") return
                copilotPanel.streamAccumulated += chunk
                var _ph = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                var msgs = copilotPanel.currentMessages.slice(0, -1)
                msgs.push({ role: "assistant", content: copilotPanel.streamAccumulated + "▋", ts: _ph ? _ph.ts : Date.now() })
                copilotPanel.currentMessages = msgs
                copilotPanel.scrollToBottom(true)
            }
            onStreamFinished: {
                if (copilotPanel.currentMessages.length > 0) {
                    var _ph = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                    var msgs = copilotPanel.currentMessages.slice(0, -1)
                    msgs.push({ role: "assistant", content: copilotPanel.streamAccumulated, ts: _ph ? (_ph.ts || Date.now()) : Date.now() })
                    copilotPanel.currentMessages = msgs
                }
                copilotPanel.isStreaming = false
                copilotPanel.streamLastLen = 0
                copilotPanel.streamAccumulated = ""
                copilotPanel.saveCurrentSession()
                copilotPanel.scrollToBottom(true)
                copilotPanel.refreshUsageLimitInfo()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "") {
                    var errMsg = text.trim()
                    copilotPanel.statusMessage = errMsg.replace(/^(FEHLER|DEBUG|CURL_ERROR|API_ERROR|PARSE_ERROR):\s*/, "")
                    copilotPanel.isStreaming = false
                    // Replace empty assistant placeholder with error message
                    if (copilotPanel.currentMessages.length > 0) {
                        var last = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                        if (last.role === "assistant" && last.content === "") {
                            var msgs = copilotPanel.currentMessages.slice(0, -1)
                            var errorContent = "❌ **Fehler:**\n\n" + copilotPanel.statusMessage + "\n\nModell: " + copilotPanel.activeModel + "\nProvider: " + copilotPanel.activeProvider
                            msgs.push({ role: "assistant", content: errorContent, ts: last.ts || Date.now() })
                            copilotPanel.currentMessages = msgs
                            copilotPanel.saveCurrentSession()
                        }
                    }
                    copilotPanel.refreshUsageLimitInfo()
                }
            }
        }
    }

    // OpenClaw Chat Process (uses external openclaw_chat.py script)
    Process {
        id: openclawChatProc
        property var fullMessages: {
            try {
                var msgs = JSON.parse(copilotPanel._chatMessagesJson || "[]")
                msgs.push({"role": "user", "content": copilotPanel._chatUserMessage || ""})
                return msgs
            } catch(e) {
                return [{"role": "user", "content": copilotPanel._chatUserMessage || ""}]
            }
        }
        command: [
            "python3",
            Quickshell.env("HOME") + "/.config/quickshell/copilot/openclaw_chat.py",
            copilotPanel._chatModel,
            JSON.stringify(fullMessages),
            copilotPanel._chatUrl.replace("/api/chat", ""),  // Remove /api/chat suffix if present
            ""  // Token will be loaded from file by script
        ]
        running: false

        stdout: StdioCollector {
            onTextChanged: {
                if (!copilotPanel.isStreaming) return
                var chunk = text.substring(copilotPanel.streamLastLen)
                copilotPanel.streamLastLen = text.length
                if (chunk === "") return
                copilotPanel.streamAccumulated += chunk
                var _ph = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                var msgs = copilotPanel.currentMessages.slice(0, -1)
                msgs.push({ role: "assistant", content: copilotPanel.streamAccumulated + "▋", ts: _ph ? _ph.ts : Date.now() })
                copilotPanel.currentMessages = msgs
                copilotPanel.scrollToBottom(true)
            }
            onStreamFinished: {
                if (copilotPanel.currentMessages.length > 0) {
                    var _ph = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                    var msgs = copilotPanel.currentMessages.slice(0, -1)
                    msgs.push({ role: "assistant", content: copilotPanel.streamAccumulated, ts: _ph ? (_ph.ts || Date.now()) : Date.now() })
                    copilotPanel.currentMessages = msgs
                }
                copilotPanel.isStreaming = false
                copilotPanel.streamLastLen = 0
                copilotPanel.streamAccumulated = ""
                copilotPanel.saveCurrentSession()
                copilotPanel.scrollToBottom(true)
                copilotPanel.refreshUsageLimitInfo()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "") {
                    var errMsg = text.trim()
                    copilotPanel.statusMessage = errMsg.replace(/^(ERROR|FEHLER|DEBUG):\s*/, "")
                    copilotPanel.isStreaming = false
                    if (copilotPanel.currentMessages.length > 0) {
                        var last = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                        if (last.role === "assistant" && last.content === "") {
                            var msgs = copilotPanel.currentMessages.slice(0, -1)
                            var errorContent = "❌ **Fehler:**\n\n" + copilotPanel.statusMessage + "\n\nModell: " + copilotPanel.activeModel + "\nProvider: " + copilotPanel.activeProvider
                            msgs.push({ role: "assistant", content: errorContent, ts: last.ts || Date.now() })
                            copilotPanel.currentMessages = msgs
                            copilotPanel.saveCurrentSession()
                        }
                    }
                    copilotPanel.refreshUsageLimitInfo()
                }
            }
        }
    }

    // OpenClaw Agent Process (with built-in tool support)
    Process {
        id: openclawAgentProc
        property var fullMessages: {
            try {
                var msgs = JSON.parse(copilotPanel._chatMessagesJson || "[]")
                msgs.push({"role": "user", "content": copilotPanel._chatUserMessage || ""})
                return msgs
            } catch(e) {
                return [{"role": "user", "content": copilotPanel._chatUserMessage || ""}]
            }
        }
        command: [
            "python3",
            Quickshell.env("HOME") + "/.config/quickshell/copilot/openclaw_agent_chat.py",
            copilotPanel._chatModel,
            JSON.stringify(fullMessages),
            copilotPanel._chatUrl,
            "",  // Token loaded from file
            "coding"  // Tool profile (coding gives file + exec tools)
        ]
        running: false

        stdout: StdioCollector {
            onTextChanged: {
                if (!copilotPanel.isStreaming) return
                var chunk = text.substring(copilotPanel.streamLastLen)
                copilotPanel.streamLastLen = text.length
                if (chunk === "") return
                copilotPanel.streamAccumulated += chunk
                var _ph = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                var msgs = copilotPanel.currentMessages.slice(0, -1)
                msgs.push({ role: "assistant", content: copilotPanel.streamAccumulated + "▋", ts: _ph ? _ph.ts : Date.now() })
                copilotPanel.currentMessages = msgs
                copilotPanel.scrollToBottom(true)
            }
            onStreamFinished: {
                if (copilotPanel.currentMessages.length > 0) {
                    var _ph = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                    var msgs = copilotPanel.currentMessages.slice(0, -1)
                    msgs.push({ role: "assistant", content: copilotPanel.streamAccumulated, ts: _ph ? (_ph.ts || Date.now()) : Date.now() })
                    copilotPanel.currentMessages = msgs
                }
                copilotPanel.isStreaming = false
                copilotPanel.streamLastLen = 0
                copilotPanel.streamAccumulated = ""
                copilotPanel.saveCurrentSession()
                copilotPanel.scrollToBottom(true)
                copilotPanel.refreshUsageLimitInfo()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "") {
                    var errMsg = text.trim()
                    copilotPanel.statusMessage = errMsg.replace(/^(ERROR|FEHLER|DEBUG):\s*/, "")
                    copilotPanel.isStreaming = false
                    if (copilotPanel.currentMessages.length > 0) {
                        var last = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                        if (last.role === "assistant" && last.content === "") {
                            var msgs = copilotPanel.currentMessages.slice(0, -1)
                            var errorContent = "❌ **Fehler:**\n\n" + copilotPanel.statusMessage + "\n\nModell: " + copilotPanel.activeModel + "\nProvider: " + copilotPanel.activeProvider
                            msgs.push({ role: "assistant", content: errorContent, ts: last.ts || Date.now() })
                            copilotPanel.currentMessages = msgs
                            copilotPanel.saveCurrentSession()
                        }
                    }
                    copilotPanel.refreshUsageLimitInfo()
                }
            }
        }
    }

    // Agent Tool Executor (for Ollama/NVIDIA with tool use)
    Process {
        id: agentToolProc
        command: ["python3", "-c",
            "import sys, json, traceback\n" +
            "try:\n" +
            "    sys.path.insert(0, (__import__('os').path.expanduser('~/.config/quickshell/default/tools')))\n" +
            "    from ollama_tool_executor import OllamaToolExecutor\n" +
            "    model = sys.argv[1]\n" +
            "    messages = json.loads(sys.argv[2])\n" +
            "    api_url = sys.argv[3]\n" +
            "    api_key = sys.argv[4]\n" +
            "    language = sys.argv[5]\n" +
            "    executor = OllamaToolExecutor(model=model, api_url=api_url, api_key=api_key)\n" +
            "    result = executor.run(messages=messages, language=language)\n" +
            "    print(json.dumps(result, ensure_ascii=False))\n" +
            "except Exception as e:\n" +
            "    error_result = {'success': False, 'error': str(e), 'traceback': traceback.format_exc()}\n" +
            "    print(json.dumps(error_result, ensure_ascii=False))\n",
            copilotPanel._chatModel,
            copilotPanel._chatMessagesJson,
            copilotPanel._chatUrl,
            copilotPanel._chatApiKey,
            copilotPanel.uiLanguage
        ]
        running: false

        stdout: StdioCollector {
            property int lastProcessedPos: 0

            onTextChanged: {
                if (!copilotPanel.isStreaming) {
                    console.log("[Agent] onTextChanged but not streaming - ignoring")
                    return
                }
                if (text.length <= lastProcessedPos) return

                console.log("[Agent] Processing new text, length:", text.length, "lastPos:", lastProcessedPos)

                // Process new lines
                var newText = text.substring(lastProcessedPos)
                var lines = newText.split('\n')

                // Process complete lines (all except last, which might be incomplete)
                for (var i = 0; i < lines.length - 1; i++) {
                    var line = lines[i].trim()
                    if (line === "") continue

                    console.log("[Agent] Parsing line:", line.substring(0, 100))
                    try {
                        var update = JSON.parse(line)
                        console.log("[Agent] Parsed update type:", update.type)

                        if (update.type === "llm_start") {
                            copilotPanel.currentToolTurn = update.turn || 0
                        }
                        else if (update.type === "tool_start") {
                            // Add to live list
                            console.log("[Agent] Tool started:", update.tool)
                            var liveTools = copilotPanel.liveToolCalls.slice()
                            liveTools.push({
                                tool: update.tool,
                                arguments: update.arguments,
                                result: null,
                                status: "running"
                            })
                            copilotPanel.liveToolCalls = liveTools
                            console.log("[Agent] liveToolCalls.length:", copilotPanel.liveToolCalls.length)
                        }
                        else if (update.type === "tool_result") {
                            // Update last tool with result
                            var liveTools2 = copilotPanel.liveToolCalls.slice()
                            for (var j = liveTools2.length - 1; j >= 0; j--) {
                                if (liveTools2[j].tool === update.tool && liveTools2[j].status === "running") {
                                    liveTools2[j].result = update.result
                                    liveTools2[j].status = "done"
                                    break
                                }
                            }
                            copilotPanel.liveToolCalls = liveTools2
                        }
                        else if (update.type === "final") {
                            // Process final response (same as before)
                            handleFinalResult(update)
                        }

                    } catch (e) {
                        console.log("[Agent] Parse error on line:", line, "Error:", e)
                    }
                }

                lastProcessedPos = text.length - lines[lines.length - 1].length
            }

            onStreamFinished: {
                if (!copilotPanel.isStreaming) return

                // Process all complete lines in the full text (in case we missed some)
                var allLines = text.split('\n')
                for (var i = 0; i < allLines.length; i++) {
                    var line = allLines[i].trim()
                    if (line === "") continue

                    try {
                        var update = JSON.parse(line)
                        if (update.type === "final") {
                            handleFinalResult(update)
                            lastProcessedPos = 0
                            return
                        }
                    } catch (e) {
                        // Incomplete/truncated JSON - ignore
                        console.log("[Agent] Skipping incomplete line:", line.substring(0, 100))
                    }
                }

                // If we get here, no valid "final" message was found
                console.log("[Agent] Warning: No final message received")
                copilotPanel.isStreaming = false
                copilotPanel.liveToolCalls = []
                copilotPanel.currentToolTurn = 0
                lastProcessedPos = 0
            }

            function handleFinalResult(result) {
                // Update tool calls history
                if (result.conversation_log) {
                    copilotPanel.executedToolCalls = []
                    for (var i = 0; i < result.conversation_log.length; i++) {
                        var turn = result.conversation_log[i]
                        if (turn.tool_calls) {
                            for (var j = 0; j < turn.tool_calls.length; j++) {
                                copilotPanel.executedToolCalls.push(turn.tool_calls[j])
                            }
                        }
                    }
                    // User manually toggles showToolDetails via button (no auto-enable)
                }

                // Update final message
                if (copilotPanel.currentMessages.length > 0 && result.response !== undefined) {
                    var msgs = copilotPanel.currentMessages.slice(0, -1)
                    var _ph = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]

                    // Build response with tool info (only if showToolDetails is enabled)
                    var content = result.response || ""

                    // If response is empty but we used tools, show error
                    if (content.trim() === "" && copilotPanel.executedToolCalls.length > 0) {
                        var noResponseMsg = copilotPanel.uiLanguage === "de"
                            ? "⚠️ Das Modell hat Tools verwendet, aber keine Antwort gegeben."
                            : "⚠️ Model used tools but provided no response."
                        content = noResponseMsg
                    }

                    if (copilotPanel.showToolDetails && copilotPanel.executedToolCalls.length > 0) {
                        var toolHeader = copilotPanel.uiLanguage === "de" ? "⚙ Tools verwendet:" : "⚙ Tools used:"
                        content += "\n\n---\n**" + toolHeader + "**\n"
                        for (var k = 0; k < copilotPanel.executedToolCalls.length; k++) {
                            var tc = copilotPanel.executedToolCalls[k]
                            content += "\n• **" + tc.tool + "**"
                            if (tc.arguments) {
                                var argStr = JSON.stringify(tc.arguments, null, 0)
                                if (argStr.length > 80) argStr = argStr.substring(0, 77) + "..."
                                content += ": `" + argStr + "`"
                            }
                            // Show tool result
                            if (tc.result) {
                                var resultStr = tc.result.toString()
                                // Truncate long results
                                if (resultStr.length > 300) {
                                    resultStr = resultStr.substring(0, 297) + "..."
                                }
                                content += "\n  → " + resultStr.replace(/\n/g, "\n  ")
                            }
                        }
                    }

                    msgs.push({ role: "assistant", content: content, ts: _ph ? _ph.ts : Date.now() })
                    copilotPanel.currentMessages = msgs
                    copilotPanel.saveCurrentSession()
                    copilotPanel.scrollToBottom(true)
                }

                copilotPanel.isStreaming = false
                copilotPanel.liveToolCalls = []
                copilotPanel.currentToolTurn = 0
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "") {
                    var errMsg = text.trim()
                    copilotPanel.statusMessage = "Agent Error: " + errMsg
                    copilotPanel.isStreaming = false

                    // Replace empty assistant message with error
                    if (copilotPanel.currentMessages.length > 0) {
                        var last = copilotPanel.currentMessages[copilotPanel.currentMessages.length - 1]
                        if (last.role === "assistant" && (last.content === "" || last.content === "▋")) {
                            var msgs = copilotPanel.currentMessages.slice(0, -1)
                            msgs.push({
                                role: "assistant",
                                content: "❌ **Agent Fehler (stderr):**\n\n" + errMsg,
                                ts: last.ts || Date.now()
                            })
                            copilotPanel.currentMessages = msgs
                            copilotPanel.saveCurrentSession()
                        }
                    }
                }
            }
        }
    }

    // Session save (binding on _sessionSaveJson)
    Process {
        id: saveSessionProc
        command: ["python3", "-c",
            "import sys, json, os\n" +
            "data = json.loads(sys.argv[1])\n" +
            "path = (__import__('os').path.expanduser('~/.config/quickshell/copilot/chats/')) + data['id'] + '.json'\n" +
            "os.makedirs(os.path.dirname(path), exist_ok=True)\n" +
            "open(path, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False))\n",
            copilotPanel._sessionSaveJson
        ]
        running: false
    }

    // Session load (binding on _sessionLoadId)
    Process {
        id: loadSessionProc
        command: ["python3", "-c",
            "import sys, json\n" +
            "path = (__import__('os').path.expanduser('~/.config/quickshell/copilot/chats/')) + sys.argv[1] + '.json'\n" +
            "try:\n" +
            "    data = json.load(open(path, encoding='utf-8'))\n" +
            "    print(json.dumps(data))\n" +
            "except Exception as e:\n" +
            "    print(json.dumps({'messages': [], 'error': str(e)}))\n" +
            "sys.stdout.flush()\n",
            copilotPanel._sessionLoadId
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(text.trim())
                    if (data.provider) copilotPanel.activeProvider = data.provider
                    if (data.model) copilotPanel.activeModel = data.model
                    copilotPanel.currentMessages = data.messages || []
                    copilotPanel._loadingSession = false
                    copilotPanel.scrollToBottom()
                } catch(e) {
                    copilotPanel.currentMessages = []
                    copilotPanel._loadingSession = false
                }
            }
        }
    }

    Process {
        id: deleteSessionProc
        command: ["python3", "-c",
            "import sys, os\n" +
            "path = (__import__('os').path.expanduser('~/.config/quickshell/copilot/chats/')) + sys.argv[1] + '.json'\n" +
            "try: os.remove(path)\n" +
            "except: pass\n",
            copilotPanel._deleteSessionId
        ]
        running: false
    }

    Process {
        id: clipboardCopyProc
        command: ["wl-copy", copilotPanel._clipboardText]
        running: false
    }

    property var _pasteTarget: null

    Process {
        id: clipboardPasteProc
        command: ["wl-paste", "--no-newline"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                if (text.length > 0) {
                    var target = copilotPanel._pasteTarget || inputEdit
                    target.remove(target.selectionStart, target.selectionEnd)
                    target.insert(target.cursorPosition, text)
                    copilotPanel._pasteTarget = null
                }
            }
        }
    }

    // Fetch available models from Claude / OpenAI APIs
    Process {
        id: fetchApiModelsProc
        command: ["python3", "-c",
            "import sys, json, urllib.request\n" +
            "provider = sys.argv[1]\n" +
            "api_key  = sys.argv[2]\n" +
            "if provider == 'claude':\n" +
            "    url = 'https://api.anthropic.com/v1/models'\n" +
            "    req = urllib.request.Request(url, headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01'})\n" +
            "elif provider == 'openai':\n" +
            "    url = 'https://api.openai.com/v1/models'\n" +
            "    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + api_key})\n" +
            "elif provider == 'gemini':\n" +
            "    url = 'https://generativelanguage.googleapis.com/v1beta/models?key=' + api_key\n" +
            "    req = urllib.request.Request(url)\n" +
            "elif provider == 'nvidia':\n" +
            "    url = 'https://integrate.api.nvidia.com/v1/models'\n" +
            "    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + api_key})\n" +
            "else:\n" +
            "    print(json.dumps({'provider': provider, 'models': []})); sys.exit(0)\n" +
            "try:\n" +
            "    with urllib.request.urlopen(req) as r:\n" +
            "        raw = json.load(r)\n" +
            "    EXCLUDE = ('realtime', 'audio', 'tts', 'whisper', 'dall-e', 'embedding', 'instruct', 'moderation', 'search')\n" +
            "    if provider == 'claude':\n" +
            "        ids = [m['id'] for m in raw.get('data',[]) if 'claude' in m.get('id','')]\n" +
            "    elif provider == 'openai':\n" +
            "        def ok(mid):\n" +
            "            if any(x in mid for x in EXCLUDE): return False\n" +
            "            return mid.startswith(('gpt-4', 'gpt-3.5', 'o1', 'o3', 'o4'))\n" +
            "        ids = sorted([m['id'] for m in raw.get('data',[]) if ok(m.get('id',''))], reverse=True)[:12]\n" +
            "    elif provider == 'gemini':\n" +
            "        ids = [m['name'].replace('models/','') for m in raw.get('models',[]) if 'generateContent' in m.get('supportedGenerationMethods',[])]\n" +
            "        ids = [i for i in ids if 'gemini' in i and 'exp' not in i][:8]\n" +
            "    elif provider == 'nvidia':\n" +
            "        all_ids = [m['id'] for m in raw.get('data',[])]\n" +
            "        print(json.dumps({'debug': 'nvidia_total_models', 'count': len(all_ids)}), file=sys.stderr)\n" +
            "        EXCLUDE_KW = ['embedding', 'vision', 'nv-embed', 'rerank', 'sd3', 'flux', 'stable-diffusion']\n" +
            "        PRIORITY = ['llama', 'nemotron', 'mistral', 'deepseek', 'gemma', 'qwen', 'phi', 'kimi', 'minimax', 'glm']\n" +
            "        def ok(mid):\n" +
            "            ml = mid.lower()\n" +
            "            if any(x in ml for x in EXCLUDE_KW): return False\n" +
            "            return True\n" +
            "        def sort_key(mid):\n" +
            "            for idx, kw in enumerate(PRIORITY):\n" +
            "                if kw in mid.lower(): return (idx, mid)\n" +
            "            return (99, mid)\n" +
            "        filtered = [i for i in all_ids if ok(i)]\n" +
            "        ids = sorted(filtered, key=sort_key)\n" +
            "        print(json.dumps({'debug': 'nvidia_filtered', 'count': len(ids), 'samples': ids[:5]+['...']+ids[-3:] if len(ids)>8 else ids}), file=sys.stderr)\n" +
            "    else:\n" +
            "        ids = []\n" +
            "    print(json.dumps({'provider': provider, 'models': ids}))\n" +
            "except Exception as e:\n" +
            "    print(json.dumps({'provider': provider, 'models': [], 'error': str(e)}))\n" +
            "sys.stdout.flush()\n",
            copilotPanel._fetchProvider,
            copilotPanel._fetchApiKey
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var result = JSON.parse(text.trim())
                    if (result.models.length === 0) return
                    var p = result.provider
                    if (p === "claude")      copilotPanel.claudeModels  = result.models
                    else if (p === "gemini") copilotPanel.geminiModels  = result.models
                    else if (p === "openai") copilotPanel.openaiModels  = result.models
                    else if (p === "nvidia") copilotPanel.nvidiaModels = result.models
                    // If active provider matches and selected model not in new list, pick first
                    if (copilotPanel.activeProvider === p &&
                            result.models.indexOf(copilotPanel.activeModel) < 0)
                        copilotPanel.activeModel = result.models[0]
                } catch(e) {}
            }
        }
    }

    function selectDefaultModel() {
        var list = currentModelList()
        if (list.length > 0) activeModel = list[0]
    }

    // Auto-fetch models when provider + key are available
    onActiveProviderChanged: {
        activeModel = ""
        showModelDropdown = false
        ollamaContextWindow = 0
        ollamaContextLoading = false
        resetUsageLimitInfo()

        // Clear messages if current session is from a different provider
        if (activeSessionId !== "") {
            var currentSession = sessions.find(function(s) { return s.id === activeSessionId })
            if (currentSession && currentSession.provider !== activeProvider) {
                // Session belongs to different provider - clear it
                currentMessages = []
                activeSessionId = ""
            }
        }

        if (activeProvider === "claude" && claudeApiKey !== "") {
            _fetchProvider = "claude"; _fetchApiKey = claudeApiKey; fetchApiModelsProc.running = true
        } else if (activeProvider === "openai" && openaiApiKey !== "") {
            _fetchProvider = "openai"; _fetchApiKey = openaiApiKey; fetchApiModelsProc.running = true
        } else if (activeProvider === "gemini" && geminiApiKey !== "") {
            _fetchProvider = "gemini"; _fetchApiKey = geminiApiKey; fetchApiModelsProc.running = true
        } else if (activeProvider === "nvidia" && nvidiaApiKey !== "") {
            _fetchProvider = "nvidia"; _fetchApiKey = nvidiaApiKey; fetchApiModelsProc.running = true
        } else if (activeProvider === "ollama") {
            if (ollamaModelDetails.length > 0) {
                activeModel = ollamaModelDetails[0].name
            } else {
                startLoadModels()
            }
            return  // model set above or via onOllamaModelDetailsChanged
        } else if (activeProvider === "openclaw") {
            if (openclawModelDetails.length > 0) {
                activeModel = openclawModelDetails[0].name
            } else {
                startLoadOpenclawModels()
            }
            return  // model set above or via onOpenclawModelDetailsChanged
        }
        selectDefaultModel()
    }

    onOllamaModelDetailsChanged: {
        if (activeProvider === "ollama" && activeModel === "" && ollamaModelDetails.length > 0)
            activeModel = ollamaModelDetails[0].name
    }
    onOpenclawModelDetailsChanged: {
        if (activeProvider === "openclaw" && openclawModelDetails.length > 0) {
            // Auto-select first model if none selected or current model not in list
            var modelInList = openclawModelDetails.find(function(m) { return m.name === activeModel })
            if (activeModel === "" || !modelInList) {
                activeModel = openclawModelDetails[0].name
            }
        }
    }
    onActiveModelChanged: {
        if (activeProvider === "ollama" || activeProvider === "openclaw") refreshModelContextInfo()
        else refreshUsageLimitInfo()
        // Auto-disable agent mode if model doesn't support tools
        if (!modelSupportsTools()) toolsEnabled = false
    }
    onClaudeApiKeyChanged: {
        if (activeProvider === "claude" && claudeApiKey !== "") {
            _fetchProvider = "claude"; _fetchApiKey = claudeApiKey; fetchApiModelsProc.running = true
        }
        if (activeProvider === "claude") refreshUsageLimitInfo()
        var m = Object.assign({}, _apiTestedOk); m["claude"] = false; _apiTestedOk = m
    }
    onOpenaiApiKeyChanged: {
        if (activeProvider === "openai" && openaiApiKey !== "") {
            _fetchProvider = "openai"; _fetchApiKey = openaiApiKey; fetchApiModelsProc.running = true
        }
        if (activeProvider === "openai") refreshUsageLimitInfo()
        var m = Object.assign({}, _apiTestedOk); m["openai"] = false; _apiTestedOk = m
    }
    onPerplexityApiKeyChanged: {
        var m = Object.assign({}, _apiTestedOk); m["perplexity"] = false; _apiTestedOk = m
    }
    onGeminiApiKeyChanged: {
        if (activeProvider === "gemini" && geminiApiKey !== "") {
            _fetchProvider = "gemini"; _fetchApiKey = geminiApiKey; fetchApiModelsProc.running = true
        }
        var m = Object.assign({}, _apiTestedOk); m["gemini"] = false; _apiTestedOk = m
    }
    onNvidiaApiKeyChanged: {
        if (nvidiaApiKey !== "") {
            _fetchProvider = "nvidia"; _fetchApiKey = nvidiaApiKey; fetchApiModelsProc.running = true
        }
        var m = Object.assign({}, _apiTestedOk); m["nvidia"] = false; _apiTestedOk = m
    }

    // ── Key storage: ~/.config/quickshell/copilot/keys.json (chmod 600) ──
    // Binding-based command slots — set these props, then set running=true
    property string _saveKeyName: "claude-api-key"
    property string _saveKeyValue: ""
    property string _testApiUrl: ""
    property string _testApiHeader: ""
    property string _testApiExtra: ""
    property string _testApiBody: ""

    // lastSaveResult / lastTestResult keyed by provider ("claude"|"openai"|"")
    property string lastSaveResult: ""   // "saving" | "ok" | "error:…" | ""
    property string lastSaveProvider: ""
    property string lastTestResult: ""   // "testing" | "ok" | "error:…" | ""
    property string lastTestProvider: ""

    Process {
        id: loadKeysProc
        command: ["python3", "-c",
            "import subprocess, os, json, sys\n" +
            "def dbus_env():\n" +
            "    e = os.environ.copy()\n" +
            "    if not e.get('DBUS_SESSION_BUS_ADDRESS'):\n" +
            "        p = '/run/user/' + str(os.getuid()) + '/bus'\n" +
            "        if os.path.exists(p): e['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=' + p\n" +
            "    return e\n" +
            "env = dbus_env()\n" +
            "def store(key_name, val):\n" +
            "    p = subprocess.Popen(['secret-tool','store','--label','Copilot '+key_name,\n" +
            "        'service','copilot-panel','key',key_name],\n" +
            "        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)\n" +
            "    p.communicate(input=val)\n" +
            "def lookup(key_name):\n" +
            "    r = subprocess.run(['secret-tool','lookup','service','copilot-panel','key',key_name],\n" +
            "        capture_output=True, text=True, env=env)\n" +
            "    return r.stdout.strip() if r.returncode == 0 else ''\n" +
            "# One-time migration from legacy JSON file\n" +
            "legacy = (__import__('os').path.expanduser('~/.config/quickshell/copilot/keys.json'))\n" +
            "if os.path.exists(legacy):\n" +
            "    try:\n" +
            "        d = json.load(open(legacy))\n" +
            "        for k,v in d.items():\n" +
            "            if v and not lookup(k): store(k, v)\n" +
            "        os.rename(legacy, legacy + '.migrated')\n" +
            "    except: pass\n" +
            "print(json.dumps({\n" +
            "    'claude':     lookup('claude-api-key'),\n" +
            "    'openai':     lookup('openai-api-key'),\n" +
            "    'perplexity': lookup('perplexity-api-key'),\n" +
            "    'gemini':     lookup('gemini-api-key'),\n" +
            "    'nvidia':     lookup('nvidia-api-key'),\n" +
            "    'openclaw':   lookup('openclaw-token'),\n" +
            "}))\n" +
            "sys.stdout.flush()\n"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var keys = JSON.parse(text.trim())
                    copilotPanel.claudeApiKey     = keys.claude     || ""
                    copilotPanel.openaiApiKey     = keys.openai     || ""
                    copilotPanel.perplexityApiKey = keys.perplexity || ""
                    copilotPanel.geminiApiKey     = keys.gemini     || ""
                    copilotPanel.nvidiaApiKey     = keys.nvidia     || ""
                    copilotPanel.openclawToken    = keys.openclaw   || ""

                    // Load OpenClaw models AFTER token is loaded
                    if (copilotPanel.openclawUrls.length > 0 && copilotPanel.openclawToken) {
                        copilotPanel.startLoadOpenclawModels()
                    }
                } catch(e) { console.error("loadKeysProc parse error:", text.trim()) }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: { if (text.trim() !== "") console.error("loadKeysProc:", text.trim()) }
        }
    }

    // ── URL Persistierung ──────────────────────────────────────────────────
    Process {
        id: loadConfigProc
        command: ["python3", "-c",
            "import json, os\n" +
            "cfg = (__import__('os').path.expanduser('~/.config/quickshell/copilot/config.json'))\n" +
            "if os.path.exists(cfg):\n" +
            "    d = json.load(open(cfg, encoding='utf-8'))\n" +
            "    print(json.dumps(d))\n" +
            "else:\n" +
            "    print(json.dumps({'ollamaUrls': ['http://localhost:11434'], 'openclawUrls': []}))\n"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var cfg = JSON.parse(text.trim())
                    console.log("[Config] Loaded - Ollama:", (cfg.ollamaUrls || []).length, "OpenClaw:", (cfg.openclawUrls || []).length)
                    copilotPanel.ollamaUrls = cfg.ollamaUrls || ["http://localhost:11434"]
                    copilotPanel.openclawUrls = cfg.openclawUrls || []
                    copilotPanel.configLoaded = true  // Enable auto-save
                } catch(e) { console.error("[Config] Load parse error:", text.trim()) }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: { if (text.trim() !== "") console.error("[Config] Load error:", text.trim()) }
        }
    }

    Component.onCompleted: {
        // Load config immediately on component creation
        loadConfigProc.running = true
    }

    Process {
        id: saveConfigProc
        command: []
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                if (text.trim() === "ok") {
                    console.log("[Config] Saved URLs - Ollama:", copilotPanel.ollamaUrls.length, "OpenClaw:", copilotPanel.openclawUrls.length)
                } else {
                    console.error("[Config] Save failed:", text.trim())
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: { if (text.trim() !== "") console.error("[Config] Save error:", text.trim()) }
        }
    }

    // Command uses bound properties → updates reactively when _saveKeyName/_saveKeyValue change
    Process {
        id: saveKeyProc
        command: ["python3", "-c",
            "import subprocess, os, sys\n" +
            "key_name  = sys.argv[1]\n" +
            "key_value = sys.argv[2]\n" +
            "e = os.environ.copy()\n" +
            "if not e.get('DBUS_SESSION_BUS_ADDRESS'):\n" +
            "    p = '/run/user/' + str(os.getuid()) + '/bus'\n" +
            "    if os.path.exists(p): e['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=' + p\n" +
            "proc = subprocess.Popen(\n" +
            "    ['secret-tool', 'store', '--label', 'Copilot ' + key_name,\n" +
            "     'service', 'copilot-panel', 'key', key_name],\n" +
            "    stdin=subprocess.PIPE, stdout=subprocess.PIPE,\n" +
            "    stderr=subprocess.PIPE, text=True, env=e)\n" +
            "out, err = proc.communicate(input=key_value)\n" +
            "if proc.returncode == 0:\n" +
            "    print('ok')\n" +
            "else:\n" +
            "    print('error:' + (err.strip() or 'secret-tool fehlgeschlagen'))\n" +
            "sys.stdout.flush()\n",
            copilotPanel._saveKeyName,
            copilotPanel._saveKeyValue
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var r = text.trim()
                copilotPanel.lastSaveResult = r === "ok" ? "ok" : ("error:" + r)
                loadKeysProc.running = true
                saveStatusResetTimer.restart()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "") {
                    console.error("saveKeyProc stderr:", text.trim())
                    if (copilotPanel.lastSaveResult === "saving")
                        copilotPanel.lastSaveResult = "error:" + text.trim().split("\n")[0]
                }
            }
        }
    }

    // Command uses bound _testApiUrl / _testApiHeader / _testApiBody
    Process {
        id: testKeyProc
        command: ["python3", "-c",
            "import sys, subprocess, json\n" +
            "url    = sys.argv[1]\n" +
            "header = sys.argv[2]\n" +
            "extra  = sys.argv[3]\n" +
            "body   = sys.argv[4]\n" +
            "def err_msg(raw):\n" +
            "    try: return json.loads(raw).get('error',{}).get('message', raw)\n" +
            "    except: return (raw or 'HTTP-Fehler')[:120]\n" +
            "if body:\n" +
            "    cmd = ['curl', '-s', '--max-time', '8', '-w', '\\n%{http_code}', '-X', 'POST', url]\n" +
            "    if header: cmd += ['-H', header]\n" +
            "    if extra:  cmd += ['-H', extra]\n" +
            "    cmd += ['-H', 'Content-Type: application/json', '-d', body]\n" +
            "    r = subprocess.run(cmd, capture_output=True, text=True)\n" +
            "    parts = r.stdout.strip().rsplit('\\n', 1)\n" +
            "    status = int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else 0\n" +
            "    if status in (401, 403):\n" +
            "        print('error:' + err_msg(parts[0] if parts else ''))\n" +
            "    else:\n" +
            "        print('ok')\n" +
            "else:\n" +
            "    cmd = ['curl', '-sf', '--max-time', '8', url]\n" +
            "    if header: cmd += ['-H', header]\n" +
            "    if extra:  cmd += ['-H', extra]\n" +
            "    r = subprocess.run(cmd, capture_output=True, text=True)\n" +
            "    if r.returncode == 0:\n" +
            "        print('ok')\n" +
            "    else:\n" +
            "        print('error:' + err_msg(r.stderr.strip() or r.stdout.strip()))\n" +
            "sys.stdout.flush()\n",
            copilotPanel._testApiUrl,
            copilotPanel._testApiHeader,
            copilotPanel._testApiExtra,
            copilotPanel._testApiBody
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                var r = text.trim()
                copilotPanel.lastTestResult = r.startsWith("ok") ? "ok" : r
                if (r.startsWith("ok")) {
                    var m = Object.assign({}, copilotPanel._apiTestedOk)
                    m[copilotPanel.lastTestProvider] = true
                    copilotPanel._apiTestedOk = m
                }
                testStatusResetTimer.restart()
            }
        }
        stderr: StdioCollector {
            onStreamFinished: {
                if (text.trim() !== "") console.error("testKeyProc stderr:", text.trim())
            }
        }
    }

    Timer {
        id: saveStatusResetTimer
        interval: 4000; repeat: false
        onTriggered: { copilotPanel.lastSaveResult = ""; copilotPanel.lastSaveProvider = "" }
    }
    Timer {
        id: testStatusResetTimer
        interval: 8000; repeat: false
        onTriggered: { copilotPanel.lastTestResult = ""; copilotPanel.lastTestProvider = "" }
    }

    Timer {
        interval: 5000
        repeat: false
        running: copilotPanel.statusMessage !== ""
        onTriggered: copilotPanel.statusMessage = ""
    }

    Timer {
        interval: 1000
        repeat: true
        running: copilotPanel.windowVisible && copilotPanel.supportsLiveUsageLimits()
        onTriggered: {
            copilotPanel._timeNowMs = Date.now()
            if (copilotPanel.usageLimitRetryAfter > 0)
                copilotPanel.usageLimitRetryAfter = Math.max(0, copilotPanel.usageLimitRetryAfter - 1)
        }
    }

    // Auto-close when unpinned
    onWindowVisibleChanged: {
        if (windowVisible) {
            console.log("CopilotPanel window visible, starting loads...")
            listSessionsProc.running = true
            startLoadModels()
            // OpenClaw models will be loaded after keys are loaded (see loadKeysProc)
            loadKeysProc.running = true
            refreshUsageLimitInfo()
            // Apply pin state after window is mapped by compositor
            applyPinStateTimer.start()
        } else {
            showModelDropdown = false
        }
    }

    Timer {
        id: applyPinStateTimer
        interval: 300
        repeat: false
        onTriggered: {
            console.log("[CopilotPanel] Applying pin state after window map...")

            // Build command based on current state
            var baseCmd = "addr=$(windoesnot-hyprctl clients -j | jq -r '.[] | select(.title | test(\"^quickshell-(does|copilot)\")) | .address'); " +
                "[[ -z \"$addr\" ]] && { echo \"Window not found, waiting...\"; sleep 0.2; addr=$(windoesnot-hyprctl clients -j | jq -r '.[] | select(.title | test(\"^quickshell-(does|copilot)\")) | .address'); }; " +
                "echo \"Window address: $addr\"; "

            if (isPinned) {
                // Pinned mode: hide hyprbars, set position if first open
                var cmd = "echo \"Applying PINNED mode\"; " +
                    "isFloating=$(windoesnot-hyprctl clients -j | jq -r \".[] | select(.address == \\\"$addr\\\") | .floating\"); " +
                    "[[ \"$isFloating\" == \"false\" ]] && { windoesnot-hyprctl dispatch togglefloating address:$addr; echo \"Made floating\"; }; " +
                    "windoesnot-hyprctl dispatch resizewindowpixel exact 1100 760,address:$addr; " +
                    "isPinned=$(windoesnot-hyprctl clients -j | jq -r \".[] | select(.address == \\\"$addr\\\") | .pinned\"); " +
                    "[[ \"$isPinned\" == \"false\" ]] && windoesnot-hyprctl dispatch pin address:$addr; " +
                    "windoesnot-hyprctl dispatch setprop address:$addr stay_focused 1; " +
                    "echo \"Done: pinned popup mode (position set by posProc or kept from previous state)\""

                applyPinStateProc.command = ["bash", "-c", baseCmd + cmd]
            } else {
                // Unpinned mode: show hyprbars + make tiled
                var cmd = "echo \"Applying UNPINNED mode\"; " +
                    "echo \"Enabling hyprbars...\"; " +
                    "windoesnot-hyprctl dispatch setprop address:$addr decorate unset; " +
                    "isPinned=$(windoesnot-hyprctl clients -j | jq -r \".[] | select(.address == \\\"$addr\\\") | .pinned\"); " +
                    "[[ \"$isPinned\" == \"true\" ]] && windoesnot-hyprctl dispatch pin address:$addr; " +
                    "echo \"Removing nodecorate rule...\"; " +
                    "windoesnot-hyprctl dispatch setprop address:$addr stay_focused unset; " +
                    "isFloating=$(windoesnot-hyprctl clients -j | jq -r \".[] | select(.address == \\\"$addr\\\") | .floating\"); " +
                    "[[ \"$isFloating\" == \"true\" ]] && windoesnot-hyprctl dispatch togglefloating address:$addr; " +
                    "workspace=$(windoesnot-hyprctl activeworkspace -j | jq -r '.id'); " +
                    "windoesnot-hyprctl dispatch movetoworkspacesilent $workspace,address:$addr; " +
                    "echo \"Done: tiled window mode with hyprbars visible\""

                applyPinStateProc.command = ["bash", "-c", baseCmd + cmd]
            }

            applyPinStateProc.running = true
        }
    }

    Process {
        id: applyPinStateProc
        command: ["bash", "-c", ""]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                console.log("[CopilotPanel] Applied pin state:\n" + text.trim())
            }
        }
    }


    // ── Background ─────────────────────────────────────────────────────────
    Rectangle {
        id: panelRoot
        anchors.fill: parent
        color: copilotPanel.bgColor
        border.color: copilotPanel.borderColor
        border.width: 1
        topLeftRadius: copilotPanel.borderRadius
        topRightRadius: copilotPanel.borderRadius
        bottomLeftRadius: 0
        bottomRightRadius: 0
        clip: true

        // Global dismiss for input context menu
        MouseArea {
            anchors.fill: parent
            visible: ctxMenu.visible
            z: 298
            onClicked: ctxMenu.visible = false
        }

        // Input context menu — at panelRoot level (z:400) so it sits above the dismiss MA (z:298)
        Rectangle {
            id: ctxMenu
            visible: false
            z: 400
            width: 150
            height: ctxCol.implicitHeight + 8
            radius: 6
            color: copilotPanel.darkMode ? Qt.rgba(0.13, 0.13, 0.13, 0.98) : Qt.rgba(0.96, 0.96, 0.96, 0.98)
            border.width: 1; border.color: copilotPanel.borderColor

            property var targetInput: null

            Column {
                id: ctxCol
                anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 4; bottomMargin: 4 }

                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ma1.containsMouse ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.cut"); font.pixelSize: 13; color: copilotPanel.textColor }
                    MouseArea { id: ma1; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            ctxMenu.visible = false
                            var target = ctxMenu.targetInput || inputEdit
                            var sel = target.selectedText
                            if (sel.length > 0) {
                                copilotPanel._clipboardText = sel
                                clipboardCopyProc.running = true
                                target.remove(target.selectionStart, target.selectionEnd)
                            }
                        } }
                }
                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ma2.containsMouse ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.copy"); font.pixelSize: 13; color: copilotPanel.textColor }
                    MouseArea { id: ma2; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            ctxMenu.visible = false
                            var target = ctxMenu.targetInput || inputEdit
                            var sel = target.selectedText
                            copilotPanel._clipboardText = sel.length > 0 ? sel : target.text
                            clipboardCopyProc.running = true
                        } }
                }
                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ma3.containsMouse ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.paste"); font.pixelSize: 13; color: copilotPanel.textColor }
                    MouseArea { id: ma3; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            ctxMenu.visible = false
                            copilotPanel._pasteTarget = ctxMenu.targetInput
                            clipboardPasteProc.running = true
                        } }
                }
                Rectangle {
                    width: parent.width; height: 28; radius: 4
                    color: ma4.containsMouse ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18) : "transparent"
                    Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: Lang.get("common.selectAll"); font.pixelSize: 13; color: copilotPanel.textColor }
                    MouseArea { id: ma4; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: { ctxMenu.visible = false; var target = ctxMenu.targetInput || inputEdit; target.selectAll() } }
                }
            }
        }

        // ── SIDEBAR (260px) ────────────────────────────────────────────────
        Rectangle {
            id: sidebar
            anchors { top: parent.top; left: parent.left; bottom: parent.bottom }
            width: 260
            color: copilotPanel.sidebarColor
            topLeftRadius: copilotPanel.borderRadius

            Column {
                anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 14 }
                spacing: 0

                // Sidebar header
                Item {
                    width: parent.width; height: 52
                    Row {
                        anchors { left: parent.left; leftMargin: 14; top: parent.top; topMargin: 5 }
                        spacing: 9
                        Image {
                            source: Qt.resolvedUrl("../img/does.svg")
                            width: 32; height: 32; sourceSize.width: 64; sourceSize.height: 64
                            smooth: true; mipmap: true
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Does"
                            font.pixelSize: 15; font.weight: Font.DemiBold
                            color: "#fff"
                        }
                    }
                    Rectangle {
                        anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                        width: 26; height: 26; radius: 6
                        color: newChatHover.containsMouse ? Qt.rgba(0.35, 0.35, 0.35, 0.5) : "transparent"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text { anchors.centerIn: parent; text: "+"; font.pixelSize: 18; color: copilotPanel.subtextColor }
                        MouseArea { id: newChatHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: copilotPanel.createNewSession() }
                    }
                }

                // Divider
                Rectangle { width: parent.width; height: 1; color: copilotPanel.borderColor; opacity: 0.5 }

                // Section label
                Text {
                    leftPadding: 14; topPadding: 10; bottomPadding: 4
                    text: Lang.get("copilot.chats")
                    font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.8
                    color: copilotPanel.subtextColor
                    renderType: Text.NativeRendering
                }
            }

            // Session list
            ListView {
                id: sessionList
                anchors { top: parent.top; topMargin: 96; left: parent.left; right: parent.right; bottom: parent.bottom }
                anchors.leftMargin: 6; anchors.rightMargin: 6; anchors.bottomMargin: 6
                model: copilotPanel.filteredSessions
                spacing: 2; clip: true

                delegate: Rectangle {
                    property bool isActive: modelData.id === copilotPanel.activeSessionId
                    property bool hovered: sessionArea.containsMouse
                    width: parent.width; height: 52; radius: 8
                    color: isActive
                        ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                        : hovered ? Qt.rgba(0.3, 0.3, 0.3, 0.15) : "transparent"
                    Behavior on color { ColorAnimation { duration: 100 } }

                    // Background MouseArea first so delete button sits above it
                    MouseArea { id: sessionArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: copilotPanel.switchToSession(modelData.id) }

                    Column {
                        anchors { left: parent.left; leftMargin: 10; right: delBtn.left; rightMargin: 4; verticalCenter: parent.verticalCenter }
                        spacing: 3
                        Text {
                            text: modelData.title !== "" ? modelData.title : Lang.get("copilot.newChat")
                            font.pixelSize: 13; font.weight: isActive ? Font.Medium : Font.Normal
                            color: isActive ? copilotPanel.accentColor : copilotPanel.textColor
                            elide: Text.ElideRight; width: parent.width
                            renderType: Text.NativeRendering
                        }
                        Text {
                            text: copilotPanel.providerLabel(modelData.provider) + (modelData.model ? " · " + modelData.model.split(":")[0] : "")
                            font.pixelSize: 11; color: copilotPanel.subtextColor
                            elide: Text.ElideRight; width: parent.width
                            renderType: Text.NativeRendering
                        }
                    }

                    Text {
                        id: delBtn
                        anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        text: "✕"; font.pixelSize: 10; color: copilotPanel.subtextColor
                        visible: hovered || isActive
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: function(mouse) { mouse.accepted = true; copilotPanel.deleteSession(modelData.id) } }
                    }
                }

                // Empty sessions state
                Text {
                    anchors.centerIn: parent
                    visible: copilotPanel.filteredSessions.length === 0
                    text: Lang.get("copilot.noChats")
                    font.pixelSize: 12; color: copilotPanel.subtextColor
                    horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; width: 200
                }
            }
        }

        // Sidebar border
        Rectangle {
            anchors { top: parent.top; left: sidebar.right; bottom: parent.bottom }
            width: 1; color: copilotPanel.borderColor
        }

        // ── MAIN CONTENT ──────────────────────────────────────────────────
        Item {
            anchors { top: parent.top; left: sidebar.right; leftMargin: 1; right: parent.right; bottom: parent.bottom }

            // ── HEADER BAR ────────────────────────────────────────────────
            Item {
                id: headerBar
                anchors { top: parent.top; left: parent.left; right: parent.right }
                height: 56

                // Provider tabs
                Row {
                    id: providerTabs
                    anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
                    spacing: 4

                    // Ollama — always visible
                    Rectangle {
                        property bool isActive: copilotPanel.activeProvider === "ollama"
                        width: ollamaLabel.implicitWidth + 20; height: 32; radius: 6
                        color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                            : ollamaHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                        border.width: 1
                        border.color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        Text {
                            id: ollamaLabel
                            anchors.centerIn: parent
                            text: "Ollama"
                            font.pixelSize: 13; font.weight: parent.isActive ? Font.DemiBold : Font.Normal
                            color: parent.isActive ? copilotPanel.accentColor : copilotPanel.subtextColor
                        }
                        MouseArea { id: ollamaHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { copilotPanel.activeProvider = "ollama"; copilotPanel.activeModel = ""; copilotPanel.showModelDropdown = false }
                        }
                    }

                    // OpenClaw — visible only if URLs configured
                    Rectangle {
                        visible: copilotPanel.openclawUrls.length > 0
                        property bool isActive: copilotPanel.activeProvider === "openclaw"
                        width: openclawLabel.implicitWidth + 20; height: 32; radius: 6
                        color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                            : openclawHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                        border.width: 1
                        border.color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        Text {
                            id: openclawLabel
                            anchors.centerIn: parent
                            text: "OpenClaw"
                            font.pixelSize: 13; font.weight: parent.isActive ? Font.DemiBold : Font.Normal
                            color: parent.isActive ? copilotPanel.accentColor : copilotPanel.subtextColor
                        }
                        MouseArea { id: openclawHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { copilotPanel.activeProvider = "openclaw"; copilotPanel.activeModel = ""; copilotPanel.showModelDropdown = false }
                        }
                    }

                    // NVIDIA — visible only if API key set
                    Rectangle {
                        visible: copilotPanel.nvidiaApiKey !== ""
                        property bool isActive: copilotPanel.activeProvider === "nvidia"
                        width: nvidiaLabel.implicitWidth + 20; height: 32; radius: 6
                        color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                            : nvidiaHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                        border.width: 1
                        border.color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        Text {
                            id: nvidiaLabel
                            anchors.centerIn: parent
                            text: "NVIDIA"
                            font.pixelSize: 13; font.weight: parent.isActive ? Font.DemiBold : Font.Normal
                            color: parent.isActive ? copilotPanel.accentColor : copilotPanel.subtextColor
                        }
                        MouseArea { id: nvidiaHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { copilotPanel.activeProvider = "nvidia"; copilotPanel.activeModel = ""; copilotPanel.showModelDropdown = false }
                        }
                    }

                    // Claude + Code pill — visible only if claude API key set
                    Rectangle {
                        visible: copilotPanel.claudeApiKey !== ""
                        height: 32; radius: 6; clip: true; color: "transparent"
                        width: claudeCodeRow.implicitWidth
                        border.width: 1
                        border.color: copilotPanel.activeProvider === "claude"
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        Row {
                            id: claudeCodeRow
                            spacing: 0; height: parent.height

                            Rectangle {
                                property bool isActive: copilotPanel.activeProvider === "claude"
                                width: claudeLabel.implicitWidth + 20; height: 32; radius: 0
                                color: isActive
                                    ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                                    : claudeHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text {
                                    id: claudeLabel
                                    anchors.centerIn: parent
                                    text: "Claude"
                                    font.pixelSize: 13; font.weight: parent.isActive ? Font.DemiBold : Font.Normal
                                    color: parent.isActive ? copilotPanel.accentColor : copilotPanel.subtextColor
                                }
                                MouseArea { id: claudeHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: { copilotPanel.activeProvider = "claude"; copilotPanel.activeModel = ""; copilotPanel.showModelDropdown = false }
                                }
                            }

                            Rectangle {
                                visible: copilotPanel.switchToTerminal !== null
                                width: 1; height: 32
                                color: Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                            }

                            Rectangle {
                                visible: copilotPanel.switchToTerminal !== null
                                width: codeLabel.implicitWidth + 16; height: 32; radius: 0
                                color: codeHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text {
                                    id: codeLabel
                                    anchors.centerIn: parent
                                    text: ">_ Code"
                                    font.pixelSize: 12
                                    color: copilotPanel.subtextColor
                                }
                                MouseArea { id: codeHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: copilotPanel.switchToTerminal("claude")
                                }
                            }
                        }
                    }

                    // ChatGPT + Codex pill — visible only if openai API key set
                    Rectangle {
                        visible: copilotPanel.openaiApiKey !== ""
                        height: 32; radius: 6; clip: true; color: "transparent"
                        width: chatgptCodexRow.implicitWidth
                        border.width: 1
                        border.color: copilotPanel.activeProvider === "openai"
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        Row {
                            id: chatgptCodexRow
                            spacing: 0; height: parent.height

                            Rectangle {
                                property bool isActive: copilotPanel.activeProvider === "openai"
                                width: openaiLabel.implicitWidth + 20; height: 32; radius: 0
                                color: isActive
                                    ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                                    : openaiHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text {
                                    id: openaiLabel
                                    anchors.centerIn: parent
                                    text: "ChatGPT"
                                    font.pixelSize: 13; font.weight: parent.isActive ? Font.DemiBold : Font.Normal
                                    color: parent.isActive ? copilotPanel.accentColor : copilotPanel.subtextColor
                                }
                                MouseArea { id: openaiHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: { copilotPanel.activeProvider = "openai"; copilotPanel.activeModel = ""; copilotPanel.showModelDropdown = false }
                                }
                            }

                            Rectangle {
                                visible: copilotPanel.switchToTerminal !== null
                                width: 1; height: 32
                                color: Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                            }

                            Rectangle {
                                visible: copilotPanel.switchToTerminal !== null
                                width: codexLabel.implicitWidth + 16; height: 32; radius: 0
                                color: codexHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text {
                                    id: codexLabel
                                    anchors.centerIn: parent
                                    text: ">_ Codex"
                                    font.pixelSize: 12
                                    color: copilotPanel.subtextColor
                                }
                                MouseArea { id: codexHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: copilotPanel.switchToTerminal("codex")
                                }
                            }
                        }
                    }

                    // Perplexity — visible only if API key set
                    Rectangle {
                        visible: copilotPanel.perplexityApiKey !== ""
                        property bool isActive: copilotPanel.activeProvider === "perplexity"
                        width: perplexityLabel.implicitWidth + 20; height: 32; radius: 6
                        color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                            : perplexityHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                        border.width: 1
                        border.color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        Text {
                            id: perplexityLabel
                            anchors.centerIn: parent
                            text: "Perplexity"
                            font.pixelSize: 13; font.weight: parent.isActive ? Font.DemiBold : Font.Normal
                            color: parent.isActive ? copilotPanel.accentColor : copilotPanel.subtextColor
                        }
                        MouseArea { id: perplexityHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { copilotPanel.activeProvider = "perplexity"; copilotPanel.activeModel = ""; copilotPanel.showModelDropdown = false }
                        }
                    }

                    // Gemini — visible only if API key set
                    Rectangle {
                        visible: copilotPanel.geminiApiKey !== ""
                        property bool isActive: copilotPanel.activeProvider === "gemini"
                        width: geminiLabel.implicitWidth + 20; height: 32; radius: 6
                        color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                            : geminiHover.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.2) : "transparent"
                        border.width: 1
                        border.color: isActive
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.25)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        Text {
                            id: geminiLabel
                            anchors.centerIn: parent
                            text: "Gemini"
                            font.pixelSize: 13; font.weight: parent.isActive ? Font.DemiBold : Font.Normal
                            color: parent.isActive ? copilotPanel.accentColor : copilotPanel.subtextColor
                        }
                        MouseArea { id: geminiHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { copilotPanel.activeProvider = "gemini"; copilotPanel.activeModel = ""; copilotPanel.showModelDropdown = false }
                        }
                    }
                }

                // Right controls: Pin + Settings
                Row {
                    anchors { right: parent.right; rightMargin: 12; verticalCenter: providerTabs.verticalCenter }
                    spacing: 4

                    // Pin/Unpin button
                    Rectangle {
                        width: 36; height: 36; radius: 8
                        color: pinBtnHover.containsMouse
                            ? Qt.rgba(0.3, 0.3, 0.3, 0.5)
                            : "transparent"
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Item {
                            anchors.centerIn: parent
                            width: 20; height: 20

                            Image {
                                id: pinIcon
                                anchors.fill: parent
                                source: copilotPanel.isPinned
                                    ? "../img/Win11-dark/actions/24/window_fullscreen.svg"
                                    : "../img/Win11-dark/actions/24/window-pin.svg"
                                sourceSize: Qt.size(20, 20)
                                visible: false
                            }

                            MultiEffect {
                                source: pinIcon
                                anchors.fill: pinIcon
                                colorization: 1.0
                                colorizationColor: copilotPanel.subtextColor
                            }
                        }

                        MouseArea {
                            id: pinBtnHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: copilotPanel.isPinned = !copilotPanel.isPinned
                        }
                    }

                    // Settings button
                    Rectangle {
                        width: 36; height: 36; radius: 8
                        color: settingsBtnHover.containsMouse
                            ? Qt.rgba(0.3, 0.3, 0.3, 0.5)
                            : copilotPanel.showSettings
                                ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.15)
                                : "transparent"
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text { anchors.centerIn: parent; text: "⚙"; font.pixelSize: 18; font.weight: Font.Bold
                            color: copilotPanel.showSettings ? copilotPanel.accentColor : copilotPanel.subtextColor }
                        MouseArea { id: settingsBtnHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: copilotPanel.showSettings = !copilotPanel.showSettings }
                    }
                }

                // Bottom divider
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: copilotPanel.borderColor }
            }

            // ── CHAT VIEW ─────────────────────────────────────────────────
            Item {
                id: chatArea
                anchors { top: headerBar.bottom; left: parent.left; right: parent.right; bottom: composerArea.top }
                visible: !copilotPanel.showSettings

                // Right-click anywhere in chat
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                    z: 1
                    onClicked: function(mouse) {
                        // Find which message was clicked (simplified - could iterate through children)
                        // For now, just skip this feature with Flickable
                        // TODO: Implement message detection for right-click menu
                    }
                }

                // Bubble context menu dismiss
                MouseArea {
                    anchors.fill: parent; z: 299
                    visible: copilotPanel._bubbleMenuVisible
                    onClicked: copilotPanel._bubbleMenuVisible = false
                }

                // Right-click overlay ABOVE Flickable to intercept right-clicks
                MouseArea {
                    id: rightClickOverlay
                    anchors.fill: chatFlick  // Match the Flickable exactly
                    z: 200
                    acceptedButtons: Qt.RightButton
                    hoverEnabled: false

                    // CRITICAL: Capture selected text in onPressed BEFORE it gets cleared
                    property string capturedSelectedText: ""

                    onPressed: function(mouse) {
                        console.log("[RightClickOverlay] onPressed - capturing selection NOW")
                        // Capture selected text immediately before it gets cleared
                        capturedSelectedText = copilotPanel._hoveredBubbleSelectedText
                        console.log("[RightClickOverlay] Captured selected text:", capturedSelectedText.length, "chars")
                    }

                    onClicked: function(mouse) {
                        console.log("[RightClickOverlay] Right-click at", mouse.x, mouse.y, "hoveredIndex:", copilotPanel._hoveredBubbleIndex)

                        // Check if we're hovering over a bubble
                        if (copilotPanel._hoveredBubbleIndex >= 0 && copilotPanel._hoveredBubbleIndex < copilotPanel.currentMessages.length) {
                            var msg = copilotPanel.currentMessages[copilotPanel._hoveredBubbleIndex]

                            // Use the captured selected text from onPressed
                            var selectedText = capturedSelectedText
                            copilotPanel._bubbleMenuText = selectedText.length > 0 ? selectedText : (msg.content || "")
                            console.log("[RightClickOverlay] Using bubble", copilotPanel._hoveredBubbleIndex)
                            console.log("[RightClickOverlay] Captured text length:", selectedText.length, "text:", selectedText.substring(0, 50))
                            console.log("[RightClickOverlay] Will copy:", copilotPanel._bubbleMenuText.substring(0, 50))

                            // Map from this MouseArea to global, then to bubbleCtxMenu's parent
                            var g = mapToGlobal(mouse.x, mouse.y)
                            var pos = bubbleCtxMenu.parent.mapFromGlobal(g.x, g.y)

                            bubbleCtxMenu.x = Math.min(pos.x, bubbleCtxMenu.parent.width - bubbleCtxMenu.width - 4)
                            bubbleCtxMenu.y = Math.max(4, pos.y - bubbleCtxMenu.height - 4)
                            copilotPanel._bubbleMenuVisible = true
                            console.log("[RightClickOverlay] Menu at", bubbleCtxMenu.x, bubbleCtxMenu.y, "parent:", bubbleCtxMenu.parent, "from global", g.x, g.y)
                        }
                        mouse.accepted = true
                    }
                }

                // Bubble context menu — copy only (read-only bubbles)
                Rectangle {
                    id: bubbleCtxMenu
                    visible: copilotPanel._bubbleMenuVisible
                    z: 300
                    width: 150; height: bubbleCtxCol.implicitHeight + 8; radius: 6
                    color: copilotPanel.darkMode ? Qt.rgba(0.13, 0.13, 0.13, 0.98) : Qt.rgba(0.96, 0.96, 0.96, 0.98)
                    border.width: 1; border.color: copilotPanel.borderColor

                    Column {
                        id: bubbleCtxCol
                        anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 4 }

                        Rectangle {
                            width: parent.width; height: 28; radius: 4
                            color: bubbleCtxCopyMA.containsMouse
                                ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.18)
                                : "transparent"
                            Text { anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                                   text: Lang.get("common.copy"); font.pixelSize: 13; color: copilotPanel.textColor }
                            MouseArea {
                                id: bubbleCtxCopyMA; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    copilotPanel._bubbleMenuVisible = false
                                    copilotPanel._clipboardText = copilotPanel._bubbleMenuText
                                    clipboardCopyProc.running = true
                                }
                            }
                        }
                    }
                }

                // Empty state
                Column {
                    anchors.centerIn: parent; spacing: 14
                    visible: copilotPanel.currentMessages.length === 0

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: Lang.get("copilot.emptyHint")
                        font.pixelSize: 14; color: copilotPanel.subtextColor
                        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; width: 340
                    }
                }

                // Timer for scroll buttons (in chatArea, not in ListView)
                Timer {
                    id: scrollButtonTimer
                    interval: 2000
                    onTriggered: copilotPanel.showScrollButtons = false
                }

                Flickable {
                    id: chatFlick
                    anchors { fill: parent; topMargin: 14; bottomMargin: 8; leftMargin: 20; rightMargin: 20 }
                    contentWidth: width
                    contentHeight: chatColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    visible: copilotPanel.currentMessages.length > 0

                    // CRITICAL: Allow child MouseAreas to receive right-clicks
                    pressDelay: 0
                    interactive: true

                    onMovementStarted: {
                        copilotPanel.userScrolled = true
                        copilotPanel.showScrollButtons = true
                        scrollButtonTimer.restart()
                    }

                    Column {
                        id: chatColumn
                        width: parent.width
                        spacing: 10

                        Repeater {
                            model: copilotPanel.currentMessages

                            delegate: Item {
                        property bool isUser: modelData.role === "user"
                        property bool isLoading: !isUser && modelData.content === "" && copilotPanel.isStreaming
                        width: chatColumn.width
                        height: bubbleRect.height + (actionRow.visible ? actionRow.height + 4 : 0) + (isUser && !isLoading ? 22 : 0) + 2
                        HoverHandler {
                            id: bubbleHover
                            onHoveredChanged: {
                                if (hovered) {
                                    copilotPanel._hoveredBubbleIndex = index
                                    // Track selected text from TextEdit if it exists
                                    if (isUser && bubbleText.visible) {
                                        copilotPanel._hoveredBubbleSelectedText = bubbleText.selectedText
                                    } else {
                                        copilotPanel._hoveredBubbleSelectedText = ""
                                    }
                                } else if (copilotPanel._hoveredBubbleIndex === index) {
                                    copilotPanel._hoveredBubbleIndex = -1
                                    copilotPanel._hoveredBubbleSelectedText = ""
                                }
                            }
                        }

                        Rectangle {
                            id: bubbleRect
                            anchors {
                                right: isUser ? parent.right : undefined
                                left: isUser ? undefined : parent.left
                            }
                            width: isLoading
                                ? (copilotPanel.toolsEnabled && copilotPanel.liveToolCalls.length > 0
                                    ? chatColumn.width  // Wide for tool details
                                    : 76)  // Small for simple spinner
                                : isUser ? Math.min(bubbleText.implicitWidth + 28, chatColumn.width * 0.78)
                                : chatColumn.width
                            height: isLoading
                                ? (copilotPanel.toolsEnabled && copilotPanel.liveToolCalls.length > 0
                                    ? thinkingContent.implicitHeight + 28
                                    : 40)  // Small for simple spinner
                                : isUser ? (bubbleText.contentHeight + 28)
                                : (bubbleContent.implicitHeight + 28)
                            radius: 10
                            color: isUser
                                ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.22)
                                : copilotPanel.surfaceColor
                            border.width: 1
                            border.color: isUser
                                ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.4)
                                : copilotPanel.borderColor

                            // 3-dot loading spinner (waiting for first token) - simple mode
                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                visible: isLoading && !(copilotPanel.toolsEnabled && copilotPanel.liveToolCalls.length > 0)
                                Repeater {
                                    model: 3
                                    Rectangle {
                                        width: 7; height: 7; radius: 4
                                        color: copilotPanel.subtextColor
                                        SequentialAnimation on opacity {
                                            running: isLoading; loops: Animation.Infinite
                                            PauseAnimation { duration: index * 180 }
                                            NumberAnimation { to: 1.0; duration: 260; easing.type: Easing.InOutSine }
                                            NumberAnimation { to: 0.25; duration: 260; easing.type: Easing.InOutSine }
                                            PauseAnimation { duration: (2 - index) * 180 }
                                        }
                                    }
                                }
                            }

                            // Agent Thinking - Live Tool-Call Display
                            Column {
                                id: thinkingContent
                                visible: isLoading && copilotPanel.toolsEnabled && copilotPanel.liveToolCalls.length > 0
                                anchors { top: parent.top; left: parent.left; right: parent.right; margins: 10 }
                                spacing: 8

                                Component.onCompleted: console.log("[ThinkingContent] Created")
                                onVisibleChanged: console.log("[ThinkingContent] visible:", visible, "isLoading:", isLoading, "toolsEnabled:", copilotPanel.toolsEnabled, "toolCalls:", copilotPanel.liveToolCalls.length)

                                // Thinking header
                                Row {
                                    spacing: 6
                                    Text {
                                        text: "⏳"
                                        font.pixelSize: 14
                                        color: copilotPanel.accentColor
                                    }
                                    Text {
                                        text: copilotPanel.uiLanguage === "de"
                                            ? "Denke nach" + (copilotPanel.currentToolTurn > 0 ? " (Runde " + copilotPanel.currentToolTurn + ")" : "") + "..."
                                            : "Thinking" + (copilotPanel.currentToolTurn > 0 ? " (turn " + copilotPanel.currentToolTurn + ")" : "") + "..."
                                        font.pixelSize: 13
                                        color: copilotPanel.textColor
                                        font.weight: Font.DemiBold
                                    }
                                }

                                // Tool calls list
                                Repeater {
                                    model: copilotPanel.liveToolCalls

                                    delegate: Column {
                                        width: parent.width
                                        spacing: 2

                                        Row {
                                            spacing: 6
                                            width: parent.width

                                            // Status icon
                                            ProjectIcon {
                                                name: modelData.status === "done" ? "check" : "wrench"
                                                font.pixelSize: 13
                                                color: modelData.status === "done"
                                                    ? Qt.rgba(0.3, 0.8, 0.3, 1.0)  // Green
                                                    : copilotPanel.accentColor
                                                anchors.verticalCenter: parent.verticalCenter
                                            }

                                            // Tool name
                                            Text {
                                                text: modelData.tool
                                                font.pixelSize: 12
                                                color: copilotPanel.textColor
                                                font.weight: Font.DemiBold
                                                anchors.verticalCenter: parent.verticalCenter
                                            }

                                            // Arguments (truncated)
                                            Text {
                                                text: {
                                                    if (!modelData.arguments) return ""
                                                    var argStr = JSON.stringify(modelData.arguments, null, 0)
                                                    if (argStr.length > 40) return "(" + argStr.substring(0, 37) + "...)"
                                                    return "(" + argStr + ")"
                                                }
                                                font.pixelSize: 11
                                                color: copilotPanel.subtextColor
                                                font.family: "monospace"
                                                anchors.verticalCenter: parent.verticalCenter
                                                elide: Text.ElideRight
                                            }
                                        }

                                        // Result preview (if done)
                                        Text {
                                            visible: modelData.status === "done" && modelData.result
                                            text: modelData.result ? "  ↳ " + modelData.result.substring(0, 100).replace(/\n/g, " ") + (modelData.result.length > 100 ? "..." : "") : ""
                                            font.pixelSize: 10
                                            color: copilotPanel.subtextColor
                                            wrapMode: Text.Wrap
                                            width: parent.width
                                            leftPadding: 20
                                        }
                                    }
                                }
                            }

                            // User messages: plain TextEdit (for implicitWidth calc)
                            TextEdit {
                                id: bubbleText
                                visible: isUser && !isLoading
                                anchors { top: parent.top; left: parent.left; right: parent.right; margins: 14 }
                                text: isUser ? modelData.content : ""
                                textFormat: TextEdit.PlainText
                                wrapMode: TextEdit.Wrap
                                font.pixelSize: 15
                                color: copilotPanel.textColor
                                readOnly: true
                                selectByMouse: true
                                persistentSelection: true
                                activeFocusOnPress: false  // Don't steal focus on click
                                selectedTextColor: copilotPanel.textColor
                                selectionColor: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.4)

                                // Track selected text for context menu - update immediately
                                onSelectedTextChanged: {
                                    if (copilotPanel._hoveredBubbleIndex === index) {
                                        copilotPanel._hoveredBubbleSelectedText = selectedText
                                        console.log("[BubbleText] Selection changed for index", index, "length:", selectedText.length)
                                    }
                                }

                                // Also update when this becomes the hovered bubble
                                Connections {
                                    target: copilotPanel
                                    function on_HoveredBubbleIndexChanged() {
                                        if (copilotPanel._hoveredBubbleIndex === index) {
                                            copilotPanel._hoveredBubbleSelectedText = bubbleText.selectedText
                                            console.log("[BubbleText] Bubble became hovered, selected:", bubbleText.selectedText.length)
                                        }
                                    }
                                }
                            }

                            // Assistant messages: markdown + syntax highlighting
                            ChatMessageView {
                                id: bubbleContent
                                visible: !isUser && !isLoading
                                anchors { top: parent.top; left: parent.left; right: parent.right; margins: 14 }
                                messageText: (!isUser && !isLoading) ? modelData.content : ""
                                darkMode:    copilotPanel.darkMode
                                textColor:   copilotPanel.textColor
                                mutedColor:  copilotPanel.subtextColor
                                accentColor: copilotPanel.accentColor
                                textPixelSize: 15
                            }

                            // Right-click context menu - READ selection from TextEdit in onPressed
                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.RightButton
                                z: 50  // Above TextEdit/ChatMessageView
                                onPressed: function(mouse) {
                                    // Read selected text IMMEDIATELY before it can be cleared
                                    var selectedText = isUser && bubbleText.visible ? bubbleText.selectedText : ""
                                    console.log("[BubbleCtxInside] onPressed - isUser:", isUser, "selected:", selectedText.length, "chars")
                                    console.log("[BubbleCtxInside] Selected text:", selectedText.substring(0, 50))
                                    // Check if there's selected text in user bubble

                                    copilotPanel._bubbleMenuText = selectedText.length > 0 ? selectedText : modelData.content

                                    var g = mapToGlobal(mouse.x, mouse.y)
                                    var pos = bubbleCtxMenu.parent.mapFromGlobal(g.x, g.y)
                                    bubbleCtxMenu.x = Math.min(pos.x, bubbleCtxMenu.parent.width - bubbleCtxMenu.width - 4)
                                    bubbleCtxMenu.y = Math.max(4, pos.y - bubbleCtxMenu.height - 4)
                                    copilotPanel._bubbleMenuVisible = true
                                    console.log("[BubbleCtxInside] Will copy:", copilotPanel._bubbleMenuText.substring(0, 50))
                                    mouse.accepted = true
                                }
                            }

                        }

                        // Timestamp below user bubble (right-aligned, fade on hover)
                        Text {
                            visible: isUser && !isLoading
                            anchors { right: bubbleRect.right; top: bubbleRect.bottom; topMargin: 4 }
                            text: copilotPanel.formatMsgTs(modelData.ts || 0)
                            color: copilotPanel.subtextColor
                            font.pixelSize: 11
                            opacity: bubbleHover.hovered ? 0.8 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        // Copy button + timestamp below assistant bubble
                        Row {
                            id: actionRow
                            visible: !isUser && !isLoading
                            anchors { top: bubbleRect.bottom; left: bubbleRect.left; topMargin: 4 }
                            spacing: 4
                            height: visible ? 26 : 0
                            Rectangle {
                                width: 26; height: 26; radius: 6
                                color: copyBtnMouse.containsMouse
                                    ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.2)
                                    : "transparent"
                                Behavior on color { ColorAnimation { duration: 100 } }
                                Image {
                                    anchors.centerIn: parent; width: 16; height: 16
                                    source: "../img/Win11-dark/actions/16/spray-mode-copy.svg"
                                    sourceSize: Qt.size(16, 16); smooth: true; antialiasing: true
                                    opacity: copyBtnMouse.containsMouse ? 1.0 : 0.5
                                    Behavior on opacity { NumberAnimation { duration: 100 } }
                                }
                                MouseArea {
                                    id: copyBtnMouse
                                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: copilotPanel.copyToClipboard(modelData.content)
                                }
                            }
                            // Timestamp next to copy button (fade on hover)
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                leftPadding: 2
                                text: copilotPanel.formatMsgTs(modelData.ts || 0)
                                color: copilotPanel.subtextColor
                                font.pixelSize: 11
                                opacity: bubbleHover.hovered ? 0.75 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 150 } }
                            }
                        }
                    }
                            }
                        }
                    }
                }

            // ── MODEL DROPDOWN (anchored above input bar) ──────────────────
            MouseArea {
                anchors.fill: parent
                visible: copilotPanel.showModelDropdown
                z: 99
                onClicked: copilotPanel.showModelDropdown = false
            }

            Rectangle {
                id: modelDropdown
                visible: copilotPanel.showModelDropdown && !copilotPanel.showSettings
                z: 100
                anchors {
                    bottom: composerArea.top; bottomMargin: 6
                    right: composerArea.right; rightMargin: 54
                }
                width: 300
                height: Math.min(dropdownCol.implicitHeight + 16, 320)
                radius: 8
                color: copilotPanel.darkMode ? Qt.rgba(0.13, 0.13, 0.13, 0.98) : Qt.rgba(0.95, 0.95, 0.95, 0.98)
                border.color: copilotPanel.borderColor; border.width: 1
                layer.enabled: true

                Column {
                    anchors.fill: parent
                    spacing: 0

                    // Search input
                    Rectangle {
                        width: parent.width; height: 44
                        color: "transparent"
                        visible: copilotPanel.activeProvider !== "ollama" && copilotPanel.currentModelList().length > 5

                        Rectangle {
                            anchors { fill: parent; margins: 8 }
                            radius: 6; color: copilotPanel.surfaceColor
                            border.width: searchInput.activeFocus ? 1 : 0
                            border.color: copilotPanel.accentColor

                            TextInput {
                                id: searchInput
                                anchors { fill: parent; leftMargin: 10; rightMargin: 30 }
                                verticalAlignment: TextInput.AlignVCenter
                                color: copilotPanel.textColor
                                font.pixelSize: 13
                                selectByMouse: true
                                text: copilotPanel.modelSearchQuery
                                onTextChanged: copilotPanel.modelSearchQuery = text
                                Component.onCompleted: {
                                    if (visible) Qt.callLater(function() { forceActiveFocus() })
                                }
                            }

                            Text {
                                anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                                visible: searchInput.text === ""
                                text: "Modell suchen..."
                                color: copilotPanel.subtextColor
                                font.pixelSize: 13
                            }

                            ProjectIcon {
                                anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                                name: "search"
                                font.pixelSize: 14
                                color: copilotPanel.subtextColor
                            }
                        }
                    }

                    Flickable {
                        width: parent.width
                        height: parent.height - (searchInputRow.visible ? 44 : 0)
                        contentHeight: dropdownCol.implicitHeight
                        clip: true
                        anchors.margins: 8

                        property Item searchInputRow: parent.children[0]

                        Column {
                            id: dropdownCol
                            width: parent.width
                            spacing: 2
                            topPadding: 8

                            // Ollama / OpenClaw: rich model rows with family + size
                            Repeater {
                                model: copilotPanel.activeProvider === "ollama" ? copilotPanel.ollamaModelDetails
                                     : copilotPanel.activeProvider === "openclaw" ? copilotPanel.openclawModelDetails
                                     : []
                            delegate: Rectangle {
                                property bool isActive: copilotPanel.activeModel === modelData.name
                                property bool hov: dropItemMA.containsMouse
                                width: dropdownCol.width; height: 46; radius: 6
                                color: isActive
                                    ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.22)
                                    : hov ? Qt.rgba(0.3, 0.3, 0.3, 0.15) : "transparent"
                                Behavior on color { ColorAnimation { duration: 80 } }

                                Column {
                                    anchors { left: parent.left; leftMargin: 14; right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                                    spacing: 2
                                    Text {
                                        text: modelData.name; width: parent.width
                                        color: isActive ? copilotPanel.accentColor : copilotPanel.textColor
                                        font.pixelSize: 13; font.weight: isActive ? Font.DemiBold : Font.Normal
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: {
                                            // Ollama: show family + size
                                            if (modelData.family && modelData.size) {
                                                return (modelData.family !== "" ? modelData.family + "  ·  " : "") + modelData.size
                                            }
                                            // OpenClaw: show provider + context window
                                            if (modelData.provider) {
                                                var parts = []
                                                if (modelData.provider) parts.push(modelData.provider)
                                                if (modelData.contextWindow > 0) {
                                                    var ctx = Math.round(modelData.contextWindow / 1024)
                                                    parts.push(ctx + "k")
                                                }
                                                return parts.join("  ·  ")
                                            }
                                            return ""
                                        }
                                        color: copilotPanel.subtextColor; font.pixelSize: 11
                                    }
                                }

                                MouseArea {
                                    id: dropItemMA; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        copilotPanel.activeModel = modelData.name
                                        // Keep current provider (ollama or openclaw)
                                        copilotPanel.showModelDropdown = false
                                    }
                                }
                            }
                        }

                        // Claude / OpenAI / NVIDIA: simple list (filtered)
                        Repeater {
                            model: (copilotPanel.activeProvider !== "ollama" && copilotPanel.activeProvider !== "openclaw") ? copilotPanel.filteredModelList() : []
                            delegate: Rectangle {
                                property bool isActive: copilotPanel.activeModel === modelData
                                property bool hov: simpleItemMA.containsMouse
                                width: dropdownCol.width; height: 36; radius: 6
                                color: isActive
                                    ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.22)
                                    : hov ? Qt.rgba(0.3, 0.3, 0.3, 0.15) : "transparent"
                                Behavior on color { ColorAnimation { duration: 80 } }

                                Text {
                                    anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
                                    text: modelData
                                    color: isActive ? copilotPanel.accentColor : copilotPanel.textColor
                                    font.pixelSize: 13; font.weight: isActive ? Font.DemiBold : Font.Normal
                                }

                                MouseArea {
                                    id: simpleItemMA; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        copilotPanel.activeModel = modelData
                                        copilotPanel.showModelDropdown = false
                                    }
                                }
                            }
                        }

                        // Empty state
                        Text {
                            visible: (copilotPanel.activeProvider === "ollama" && copilotPanel.ollamaModelDetails.length === 0) ||
                                     (copilotPanel.activeProvider === "openclaw" && copilotPanel.openclawModelDetails.length === 0) ||
                                     (copilotPanel.activeProvider !== "ollama" && copilotPanel.activeProvider !== "openclaw" && copilotPanel.filteredModelList().length === 0)
                            width: dropdownCol.width
                            text: copilotPanel.modelSearchQuery !== ""
                                ? "Keine Modelle gefunden für '" + copilotPanel.modelSearchQuery + "'"
                                : (copilotPanel.activeProvider === "ollama"
                                    ? "Keine Modelle gefunden.\nOllama-URLs in den Einstellungen prüfen."
                                    : copilotPanel.activeProvider === "openclaw"
                                    ? "Keine Modelle gefunden.\nOpenClaw-URLs in den Einstellungen prüfen oder im Netz suchen."
                                    : "Keine Modelle verfügbar.")
                            color: copilotPanel.subtextColor; font.pixelSize: 12
                            wrapMode: Text.Wrap; leftPadding: 10; topPadding: 4; bottomPadding: 4
                        }
                        }
                    }
                }

            }

            Item {
                id: composerArea
                z: 100
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right; bottomMargin: 14; leftMargin: 16; rightMargin: 16 }
                height: inputArea.height + ((usageBelowInput.visible ? usageBelowInput.height + 6 : 0))
                visible: !copilotPanel.showSettings

                // ── INPUT BAR ──────────────────────────────────────────────────
                Item {
                    id: inputArea
                    anchors { top: parent.top; left: parent.left; right: parent.right }
                    height: Math.max(52, inputEdit.implicitHeight + 20)

                    Rectangle {
                        anchors.fill: parent; radius: 12
                        color: copilotPanel.surfaceColor
                        border.width: 1
                        border.color: inputEdit.activeFocus
                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.55)
                            : copilotPanel.borderColor
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        TextEdit {
                            id: inputEdit
                            anchors {
                                left: parent.left
                                right: toolDetailsToggle.visible ? toolDetailsToggle.left
                                       : toolsEnabledToggle.visible ? toolsEnabledToggle.left
                                       : modelPickerBtn.left
                                top: parent.top
                                bottom: parent.bottom
                                leftMargin: 14
                                rightMargin: 8
                                topMargin: 10
                                bottomMargin: 10
                            }
                            verticalAlignment: TextEdit.AlignVCenter
                            font.pixelSize: 15; color: copilotPanel.textColor
                            wrapMode: TextEdit.Wrap; selectByMouse: true
                            renderType: Text.NativeRendering

                            // Placeholder
                            Text {
                                anchors.fill: parent; verticalAlignment: Text.AlignVCenter
                                text: Lang.get("copilot.inputHint") + " …"
                                font.pixelSize: 15; color: copilotPanel.darkMode ? "#444" : "#bbb"
                                visible: inputEdit.text === ""
                                renderType: Text.NativeRendering
                            }

                            Keys.onPressed: function(e) {
                                if (e.key === Qt.Key_Return && !(e.modifiers & Qt.ShiftModifier)) {
                                    e.accepted = true
                                    var t = inputEdit.text
                                    inputEdit.text = ""
                                    copilotPanel.sendMessage(t)
                                }
                            }
                        }

                        // Right-click: show context menu — maps to panelRoot since ctxMenu lives there at z:400
                        MouseArea {
                            anchors { left: inputEdit.left; right: inputEdit.right; top: parent.top; bottom: parent.bottom }
                            acceptedButtons: Qt.RightButton
                            propagateComposedEvents: true
                            onClicked: function(mouse) {
                                var g = mapToGlobal(mouse.x, mouse.y)
                                var pos = panelRoot.mapFromGlobal(g.x, g.y)
                                ctxMenu.targetInput = null
                                ctxMenu.x = Math.min(pos.x, panelRoot.width - ctxMenu.width - 4)
                                ctxMenu.y = Math.max(4, pos.y - ctxMenu.height - 4)
                                ctxMenu.visible = true
                            }
                        }

                        // Model picker pill (e.g. "gemma3:27b ▾")
                        // Tool Details Toggle (only visible when agent has used tools)
                        Rectangle {
                            id: toolDetailsToggle
                            visible: copilotPanel.toolsEnabled && copilotPanel.executedToolCalls.length > 0
                            anchors { right: toolsEnabledToggle.visible ? toolsEnabledToggle.left : modelPickerBtn.left; rightMargin: 6; verticalCenter: parent.verticalCenter }
                            height: 28; width: 28; radius: 14
                            color: copilotPanel.showToolDetails
                                ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.25)
                                : toolDetailsHover.containsMouse
                                    ? Qt.rgba(0.3, 0.3, 0.3, 0.25)
                                    : Qt.rgba(0.2, 0.2, 0.2, 0.25)
                            border.width: 1
                            border.color: copilotPanel.showToolDetails
                                ? copilotPanel.accentColor
                                : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.3)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Image {
                                source: Qt.resolvedUrl("../img/mdi--tools.svg")
                                width: 14; height: 14
                                sourceSize.width: 28; sourceSize.height: 28
                                smooth: true; antialiasing: true; mipmap: true
                                anchors.centerIn: parent
                                layer.enabled: true
                                layer.effect: MultiEffect {
                                    colorization: 1.0
                                    colorizationColor: copilotPanel.showToolDetails ? copilotPanel.accentColor : copilotPanel.subtextColor
                                }
                            }

                            MouseArea {
                                id: toolDetailsHover
                                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: copilotPanel.showToolDetails = !copilotPanel.showToolDetails
                            }
                        }

                        // Tools Enable/Disable Toggle (for tool-capable models)
                        Rectangle {
                            id: toolsEnabledToggle
                            visible: copilotPanel.modelSupportsTools()
                            anchors { right: modelPickerBtn.left; rightMargin: 6; verticalCenter: parent.verticalCenter }
                            height: 28; radius: 14
                            width: toolsEnabledRow.implicitWidth + 16
                            color: copilotPanel.toolsEnabled
                                ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.25)
                                : toolsEnabledHover.containsMouse
                                    ? Qt.rgba(0.3, 0.3, 0.3, 0.25)
                                    : Qt.rgba(0.2, 0.2, 0.2, 0.25)
                            border.width: 1
                            border.color: copilotPanel.toolsEnabled
                                ? copilotPanel.accentColor
                                : Qt.rgba(copilotPanel.subtextColor.r, copilotPanel.subtextColor.g, copilotPanel.subtextColor.b, 0.3)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Row {
                                id: toolsEnabledRow
                                anchors.centerIn: parent
                                spacing: 4
                                Image {
                                    source: Qt.resolvedUrl("../img/mdi--tools.svg")
                                    width: 14; height: 14
                                    sourceSize.width: 28; sourceSize.height: 28
                                    smooth: true; antialiasing: true; mipmap: true
                                    anchors.verticalCenter: parent.verticalCenter
                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        colorization: 1.0
                                        colorizationColor: copilotPanel.toolsEnabled ? copilotPanel.accentColor : copilotPanel.subtextColor
                                    }
                                }
                                Text {
                                    text: "Tools"
                                    color: copilotPanel.toolsEnabled ? copilotPanel.accentColor : copilotPanel.subtextColor
                                    font.pixelSize: 11
                                    font.weight: copilotPanel.toolsEnabled ? Font.DemiBold : Font.Normal
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            MouseArea {
                                id: toolsEnabledHover
                                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: copilotPanel.toolsEnabled = !copilotPanel.toolsEnabled
                            }
                        }

                        Rectangle {
                            id: modelPickerBtn
                            anchors { right: sendBtn.left; rightMargin: 6; verticalCenter: parent.verticalCenter }
                            height: 28; radius: 14
                            width: modelPickerRow.implicitWidth + 24
                            color: copilotPanel.showModelDropdown
                                ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.2)
                                : modelPickerHover.containsMouse
                                    ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.12)
                                    : Qt.rgba(0.3, 0.3, 0.3, 0.25)
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                id: modelPickerRow
                                anchors.centerIn: parent
                                spacing: 4
                                Text {
                                    text: copilotPanel.activeModel !== ""
                                        ? copilotPanel.activeModel.split(":")[0]
                                        : copilotPanel.providerLabel(copilotPanel.activeProvider) + " – wählen"
                                    color: copilotPanel.activeModel !== "" ? copilotPanel.textColor : copilotPanel.subtextColor
                                    font.pixelSize: 12
                                }
                                Text {
                                    text: copilotPanel.showModelDropdown ? "▴" : "▾"
                                    color: copilotPanel.subtextColor; font.pixelSize: 8
                                }
                            }

                            MouseArea {
                                id: modelPickerHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (copilotPanel.activeProvider === "ollama" && copilotPanel.ollamaModelDetails.length === 0)
                                        copilotPanel.startLoadModels()
                                    if (copilotPanel.activeProvider === "openclaw" && copilotPanel.openclawModelDetails.length === 0)
                                        copilotPanel.startLoadOpenclawModels()
                                    copilotPanel.showModelDropdown = !copilotPanel.showModelDropdown
                                }
                            }
                        }

                        Rectangle {
                            id: sendBtn
                            anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                            width: 34; height: 34; radius: 8
                            color: copilotPanel.isStreaming
                                ? "#c0392b"
                                : inputEdit.text.trim() !== "" ? copilotPanel.accentColor : Qt.rgba(0.3, 0.3, 0.3, 0.4)
                            Behavior on color { ColorAnimation { duration: 150 } }
                            Text {
                                anchors.centerIn: parent
                                text: copilotPanel.isStreaming ? "⏹" : "↑"
                                font.pixelSize: copilotPanel.isStreaming ? 12 : 16; font.weight: Font.Bold; color: "#fff"
                            }
                            MouseArea {
                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (copilotPanel.isStreaming) {
                                        copilotPanel.stopStreaming()
                                    } else {
                                        var t = inputEdit.text
                                        inputEdit.text = ""
                                        copilotPanel.sendMessage(t)
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: usageBelowInput
                    anchors { top: inputArea.bottom; topMargin: 8; left: parent.left; right: parent.right }
                    height: 24
                    radius: 0
                    color: "transparent"
                    border.width: 0
                    visible: activeModel !== "" && !copilotPanel.showSettings
                    clip: false

                    Row {
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                        spacing: 6

                        Rectangle {
                            height: 16
                            anchors.verticalCenter: parent.verticalCenter
                            width: contextUsageText.implicitWidth + 16
                            radius: 8
                            color: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b,
                                           0.10 + (0.20 * copilotPanel.contextUsageRatio))
                            border.width: 1
                            border.color: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.16)

                            Text {
                                id: contextUsageText
                                anchors.centerIn: parent
                                text: Lang.get("copilot.context", copilotPanel.uiLanguage) + "  " + Math.max(0, 100 - Math.round(copilotPanel.contextUsageRatio * 100)) + "% " + Lang.get("copilot.left", copilotPanel.uiLanguage) + "  " +
                                      copilotPanel.formatTokenCount(copilotPanel.estimatedConversationTokens) + " / " +
                                      (copilotPanel.ollamaContextLoading ? "…" : copilotPanel.formatTokenCount(copilotPanel.activeContextWindow))
                                color: copilotPanel.textColor
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                            }
                        }

                        Rectangle {
                            visible: copilotPanel.supportsLiveUsageLimits() || copilotPanel.activeUsageBudget > 0
                            height: 16
                            anchors.verticalCenter: parent.verticalCenter
                            width: usageInlineText.implicitWidth + 16
                            radius: 8
                            color: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b,
                                           0.08 + (0.22 * copilotPanel.currentUsageRatio()))
                            border.width: 1
                            border.color: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.16)

                            Text {
                                id: usageInlineText
                                anchors.centerIn: parent
                                text: copilotPanel.usageCardTitle() + "  " + copilotPanel.usageCardPercent() + "  " + copilotPanel.usageCardDetail()
                                color: copilotPanel.textColor
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }

            // ── SETTINGS OVERLAY ──────────────────────────────────────────
            Rectangle {
                anchors { top: headerBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
                visible: copilotPanel.showSettings
                color: copilotPanel.bgColor

                Flickable {
                    anchors { fill: parent; margins: 20 }
                    contentHeight: settingsCol.implicitHeight
                    clip: true

                    Column {
                        id: settingsCol
                        width: parent.width
                        spacing: 28

                        // ── OLLAMA ────────────────────────────────────────────
                        Column {
                            width: parent.width; spacing: 10

                            // Header row: title + scan + check buttons
                            Item {
                                width: parent.width; height: 28

                                Text {
                                    id: ollamaTitle
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Lang.get("copilot.ollamaSection")
                                    color: copilotPanel.accentColor
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                }

                                Row {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 8

                                    Rectangle {
                                        width: ollamaScanBtnContent.implicitWidth + 20; height: 28; radius: 6
                                        color: copilotPanel.scanningOllama
                                            ? Qt.rgba(0.3, 0.6, 0.9, 0.25)
                                            : Qt.rgba(0.3, 0.6, 0.9, 0.15)
                                        border.color: "#4a9eff"; border.width: 1

                                        Row {
                                            id: ollamaScanBtnContent
                                            anchors.centerIn: parent
                                            spacing: 6

                                            // Spinner - bigger and more visible
                                            Rectangle {
                                                visible: copilotPanel.scanningOllama
                                                width: 14; height: 14
                                                radius: 7
                                                anchors.verticalCenter: parent.verticalCenter
                                                color: "transparent"
                                                border.width: 2
                                                border.color: "#4a9eff"

                                                Rectangle {
                                                    width: 6; height: 3; radius: 1.5
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    anchors.top: parent.top
                                                    color: "#4a9eff"
                                                    transformOrigin: Item.Bottom

                                                    RotationAnimation on rotation {
                                                        running: copilotPanel.scanningOllama
                                                        loops: Animation.Infinite
                                                        from: 0; to: 360
                                                        duration: 800
                                                    }
                                                }
                                            }

                                            Text {
                                                text: copilotPanel.scanningOllama ? Lang.get("copilot.scanning") : Lang.get("copilot.scanNetwork")
                                                color: "#4a9eff"
                                                font.pixelSize: 11
                                                font.weight: Font.DemiBold
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            enabled: !copilotPanel.scanningOllama
                                            onClicked: {
                                                console.log("[Ollama] Starting network scan...")
                                                copilotPanel.scanningOllama = true
                                                copilotPanel.foundOllamaInstances = []
                                                scanOllamaProc.running = true
                                            }
                                        }
                                    }

                                    Rectangle {
                                        width: ollamaCheckText.implicitWidth + 20; height: 28; radius: 6
                                        color: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.15)
                                        border.color: copilotPanel.accentColor; border.width: 1
                                        Text {
                                            id: ollamaCheckText
                                            anchors.centerIn: parent
                                            text: Lang.get("copilot.checkAll")
                                            color: copilotPanel.accentColor
                                            font.pixelSize: 12
                                        }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                // Clear focus to commit any pending TextInput edits
                                                copilotPanel.focus = true
                                                copilotPanel.startLoadModels()
                                            }
                                        }
                                    }
                                }
                            }

                            // Found Ollama instances
                            Column {
                                width: parent.width
                                spacing: 6
                                visible: copilotPanel.foundOllamaInstances.length > 0

                                Text {
                                    text: Lang.get("copilot.foundInstances")
                                    color: copilotPanel.subtextColor
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    topPadding: 4
                                    bottomPadding: 4
                                }

                                Repeater {
                                    model: copilotPanel.foundOllamaInstances
                                    Rectangle {
                                        width: parent.width; height: 52; radius: 6
                                        color: Qt.rgba(0.18, 0.75, 0.38, 0.1)
                                        border.color: "#4ade80"; border.width: 1

                                        Row {
                                            anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                                            spacing: 12

                                            Column {
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: parent.width - 90

                                                Text {
                                                    text: modelData.url
                                                    color: copilotPanel.textColor
                                                    font.pixelSize: 13
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideMiddle
                                                    width: parent.width
                                                }
                                                Text {
                                                    text: modelData.version || modelData.ip
                                                    color: copilotPanel.subtextColor
                                                    font.pixelSize: 11
                                                }
                                            }

                                            Rectangle {
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 78; height: 28; radius: 5
                                                color: copilotPanel.accentColor
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: Lang.get("copilot.addInstance")
                                                    color: "#ffffff"
                                                    font.pixelSize: 12
                                                    font.weight: Font.DemiBold
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        var url = modelData.url
                                                        // Check if not already in list
                                                        if (copilotPanel.ollamaUrls.indexOf(url) === -1) {
                                                            var urls = copilotPanel.ollamaUrls.slice()
                                                            urls.push(url)
                                                            copilotPanel.ollamaUrls = urls
                                                            console.log("[Ollama] Added instance:", url)
                                                        }
                                                        // Remove from found list
                                                        var found = copilotPanel.foundOllamaInstances.slice()
                                                        found.splice(index, 1)
                                                        copilotPanel.foundOllamaInstances = found
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // URL list
                            Repeater {
                                model: copilotPanel.ollamaUrls
                                delegate: Item {
                                    id: ollamaUrlDelegate
                                    required property int index
                                    required property string modelData
                                    width: parent.width
                                    height: ollamaUrlCol.height

                                    property var _panel: copilotPanel  // Capture reference

                                    Column {
                                        id: ollamaUrlCol
                                        width: parent.width; spacing: 4

                                    Row {
                                        width: parent.width; spacing: 8

                                        // Status indicator
                                        Rectangle {
                                            width: 28; height: 36; radius: 6
                                            color: {
                                                var s = ollamaUrlDelegate._panel.ollamaUrlStatuses[ollamaUrlDelegate.index]
                                                if (!s) return ollamaUrlDelegate._panel.surfaceColor
                                                if (s.status === "ok") return Qt.rgba(0.18, 0.75, 0.38, 0.2)
                                                if (s.status === "error") return Qt.rgba(0.94, 0.27, 0.27, 0.2)
                                                return Qt.rgba(0.9, 0.7, 0.1, 0.2)  // checking
                                            }
                                            Text {
                                                anchors.centerIn: parent; font.pixelSize: 14
                                                text: {
                                                    var s = ollamaUrlDelegate._panel.ollamaUrlStatuses[ollamaUrlDelegate.index]
                                                    if (!s) return "○"
                                                    if (s.status === "ok") return "✓"
                                                    if (s.status === "error") return "✗"
                                                    return "…"
                                                }
                                                color: {
                                                    var s = ollamaUrlDelegate._panel.ollamaUrlStatuses[ollamaUrlDelegate.index]
                                                    if (!s) return ollamaUrlDelegate._panel.subtextColor
                                                    if (s.status === "ok") return "#4ade80"
                                                    if (s.status === "error") return "#f87171"
                                                    return "#fbbf24"
                                                }
                                            }
                                        }

                                        // URL input
                                        Rectangle {
                                            width: parent.width - 28 - 28 - 16; height: 36; radius: 6
                                            color: ollamaUrlDelegate._panel.surfaceColor; border.color: ollamaUrlDelegate._panel.borderColor; border.width: 1
                                            TextInput {
                                                anchors { fill: parent; leftMargin: 10; rightMargin: 10; topMargin: 8; bottomMargin: 8 }
                                                text: ollamaUrlDelegate.modelData
                                                color: ollamaUrlDelegate._panel.textColor; font.pixelSize: 13; selectByMouse: true
                                                onEditingFinished: {
                                                    var trimmed = text.trim()
                                                    var idx = ollamaUrlDelegate.index
                                                    if (trimmed !== ollamaUrlDelegate.modelData) {
                                                        var urls = ollamaUrlDelegate._panel.ollamaUrls.slice()
                                                        urls[idx] = trimmed
                                                        ollamaUrlDelegate._panel.ollamaUrls = urls
                                                        text = trimmed
                                                    }
                                                }
                                            }
                                        }

                                        // Remove button
                                        Rectangle {
                                            width: 28; height: 36; radius: 6
                                            color: ollamaUrlDelegate._panel.surfaceColor; border.color: ollamaUrlDelegate._panel.borderColor; border.width: 1
                                            visible: ollamaUrlDelegate._panel.ollamaUrls.length > 0
                                            Text { anchors.centerIn: parent; text: "✕"; color: "#f87171"; font.pixelSize: 13 }
                                            MouseArea {
                                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    var idx = ollamaUrlDelegate.index
                                                    var urls = ollamaUrlDelegate._panel.ollamaUrls.slice()
                                                    urls.splice(idx, 1)
                                                    ollamaUrlDelegate._panel.ollamaUrls = urls
                                                    var statuses = ollamaUrlDelegate._panel.ollamaUrlStatuses.slice()
                                                    statuses.splice(idx, 1)
                                                    ollamaUrlDelegate._panel.ollamaUrlStatuses = statuses
                                                }
                                            }
                                        }
                                    }

                                    // Model count per endpoint
                                    Text {
                                        leftPadding: 36
                                        visible: {
                                            var s = ollamaUrlDelegate._panel.ollamaUrlStatuses[ollamaUrlDelegate.index]
                                            return !!(s && s.status === "ok")
                                        }
                                        text: {
                                            var s = ollamaUrlDelegate._panel.ollamaUrlStatuses[ollamaUrlDelegate.index]
                                            return s ? (s.count || 0) + " " + Lang.get("copilot.modelsAvailable") : ""
                                        }
                                        color: "#4ade80"; font.pixelSize: 11
                                    }
                                    Text {
                                        leftPadding: 36
                                        visible: {
                                            var s = ollamaUrlDelegate._panel.ollamaUrlStatuses[ollamaUrlDelegate.index]
                                            return !!(s && s.status === "error")
                                        }
                                        text: Lang.get("copilot.notReachable")
                                        color: "#f87171"; font.pixelSize: 11
                                    }
                                    }
                                }
                            }

                            // No instances found message
                            Text {
                                visible: !copilotPanel.scanningOllama &&
                                         copilotPanel.foundOllamaInstances.length === 0 &&
                                         copilotPanel.ollamaUrls.length === 1  // Only show if just localhost
                                width: parent.width
                                text: Lang.get("copilot.noInstancesFound")
                                color: copilotPanel.subtextColor
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                horizontalAlignment: Text.AlignHCenter
                                topPadding: 4
                                bottomPadding: 4
                            }

                            // Add endpoint button
                            Rectangle {
                                width: parent.width; height: 36; radius: 6
                                color: copilotPanel.surfaceColor; border.color: copilotPanel.borderColor; border.width: 1
                                Row {
                                    anchors.centerIn: parent; spacing: 6
                                    Text { text: "+"; color: copilotPanel.accentColor; font.pixelSize: 16; font.weight: Font.Bold }
                                    Text { text: Lang.get("copilot.addEndpoint"); color: copilotPanel.accentColor; font.pixelSize: 13 }
                                }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: {
                                    var urls = copilotPanel.ollamaUrls.slice()
                                    urls.push("http://")
                                    copilotPanel.ollamaUrls = urls
                                }}
                            }

                            // Model details list
                            Column {
                                width: parent.width; spacing: 4
                                visible: copilotPanel.ollamaModelDetails.length > 0

                                Row {
                                    width: parent.width
                                    spacing: 6
                                    Text {
                                        text: copilotPanel.ollamaModelDetails.length + " " + Lang.get("copilot.modelsFound")
                                        color: copilotPanel.subtextColor; font.pixelSize: 12
                                        bottomPadding: 4
                                    }
                                    Text {
                                        text: copilotPanel.showOllamaModels ? "▲" : "▼"
                                        color: copilotPanel.subtextColor; font.pixelSize: 9
                                        MouseArea {
                                            anchors.fill: parent
                                            anchors.margins: -4
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: copilotPanel.showOllamaModels = !copilotPanel.showOllamaModels
                                        }
                                    }
                                }

                                Repeater {
                                    model: copilotPanel.showOllamaModels ? copilotPanel.ollamaModelDetails : []
                                    Rectangle {
                                        width: parent.width; height: 46; radius: 6
                                        color: copilotPanel.surfaceColor
                                        border.color: copilotPanel.activeModel === modelData.name
                                            ? copilotPanel.accentColor : "transparent"
                                        border.width: 1

                                        Row {
                                            anchors { fill: parent; leftMargin: 12; rightMargin: 12; topMargin: 8; bottomMargin: 8 }
                                            spacing: 8

                                            Column {
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: parent.width - 28
                                                Text {
                                                    text: modelData.name
                                                    color: copilotPanel.activeModel === modelData.name ? copilotPanel.accentColor : copilotPanel.textColor
                                                    font.pixelSize: 13; font.weight: copilotPanel.activeModel === modelData.name ? Font.DemiBold : Font.Normal
                                                    elide: Text.ElideRight; width: parent.width
                                                }
                                                Text {
                                                    text: {
                                                        var parts = []
                                                        if (modelData.family !== "") parts.push(modelData.family)
                                                        parts.push(modelData.size)
                                                        // Extract hostname from URL
                                                        if (modelData.url) {
                                                            var hostname = modelData.url.replace(/^https?:\/\//, '').split(':')[0]
                                                            if (hostname === 'localhost' || hostname === '127.0.0.1') hostname = 'local'
                                                            parts.push(hostname)
                                                        }
                                                        return parts.join("  ·  ")
                                                    }
                                                    color: copilotPanel.subtextColor; font.pixelSize: 11
                                                }
                                            }

                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: "✓"
                                                color: copilotPanel.accentColor; font.pixelSize: 14; font.weight: Font.Bold
                                                visible: copilotPanel.activeModel === modelData.name
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── OPENCLAW ──────────────────────────────────────────
                        Column {
                            width: parent.width; spacing: 10

                            // Header row: title + scan + check buttons
                            Item {
                                width: parent.width; height: 28

                                Text {
                                    id: openclawTitle
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Lang.get("copilot.openclawSection")
                                    color: copilotPanel.accentColor
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                }

                                Row {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 8

                                    Rectangle {
                                        width: openclawScanBtnContent.implicitWidth + 20; height: 28; radius: 6
                                        color: copilotPanel.scanningOpenclaw
                                            ? Qt.rgba(0.3, 0.6, 0.9, 0.25)
                                            : Qt.rgba(0.3, 0.6, 0.9, 0.15)
                                        border.color: "#4a9eff"; border.width: 1

                                        Row {
                                            id: openclawScanBtnContent
                                            anchors.centerIn: parent
                                            spacing: 6

                                            Rectangle {
                                                visible: copilotPanel.scanningOpenclaw
                                                width: 14; height: 14
                                                radius: 7
                                                anchors.verticalCenter: parent.verticalCenter
                                                color: "transparent"
                                                border.width: 2
                                                border.color: "#4a9eff"

                                                Rectangle {
                                                    width: 6; height: 3; radius: 1.5
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    anchors.top: parent.top
                                                    color: "#4a9eff"
                                                    transformOrigin: Item.Bottom

                                                    RotationAnimation on rotation {
                                                        running: copilotPanel.scanningOpenclaw
                                                        loops: Animation.Infinite
                                                        from: 0; to: 360
                                                        duration: 800
                                                    }
                                                }
                                            }

                                            Text {
                                                text: copilotPanel.scanningOpenclaw ? Lang.get("copilot.scanning") : Lang.get("copilot.scanNetwork")
                                                color: "#4a9eff"
                                                font.pixelSize: 11
                                                font.weight: Font.DemiBold
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            enabled: !copilotPanel.scanningOpenclaw
                                            onClicked: {
                                                console.log("[OpenClaw] Starting gateway scan...")
                                                copilotPanel.scanningOpenclaw = true
                                                copilotPanel.foundOpenclawInstances = []
                                                scanOpenclawProc.running = true
                                            }
                                        }
                                    }

                                    Rectangle {
                                        width: openclawCheckText.implicitWidth + 20; height: 28; radius: 6
                                        color: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.15)
                                        border.color: copilotPanel.accentColor; border.width: 1

                                        Text {
                                            id: openclawCheckText
                                            anchors.centerIn: parent
                                            text: Lang.get("copilot.checkAll")
                                            color: copilotPanel.accentColor
                                            font.pixelSize: 12
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                copilotPanel.focus = true
                                                copilotPanel.openclawHealthState = "checking"
                                                copilotPanel.openclawHealthMessage = "Running health check..."
                                                copilotPanel.startLoadOpenclawModels()
                                            }
                                        }
                                    }
                                }
                            }

                            // Found OpenClaw gateways
                            Column {
                                width: parent.width
                                spacing: 6
                                visible: copilotPanel.foundOpenclawInstances.length > 0

                                Text {
                                    text: Lang.get("copilot.foundInstances")
                                    color: copilotPanel.subtextColor
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    topPadding: 4
                                    bottomPadding: 4
                                }

                                Repeater {
                                    model: copilotPanel.foundOpenclawInstances
                                    Rectangle {
                                        width: parent.width; height: 52; radius: 6
                                        color: Qt.rgba(0.3, 0.6, 0.9, 0.15)
                                        border.color: "#4a9eff"; border.width: 1

                                        Item {
                                            anchors { fill: parent; margins: 12 }

                                            Column {
                                                id: infoCol
                                                anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                                                width: 140

                                                Text {
                                                    text: (modelData.displayName || modelData.hostname || modelData.ip)
                                                    color: copilotPanel.textColor
                                                    font.pixelSize: 11
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideMiddle
                                                    width: parent.width
                                                }
                                                Text {
                                                    text: modelData.ip + ":" + modelData.port
                                                    color: copilotPanel.subtextColor
                                                    font.pixelSize: 10
                                                }
                                            }

                                            Rectangle {
                                                id: addBtn
                                                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                                                width: 88
                                                height: 28
                                                radius: 5
                                                color: "#4a9eff"

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: Lang.get("copilot.addInstance")
                                                    color: "#ffffff"
                                                    font.pixelSize: 11
                                                    font.weight: Font.DemiBold
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        var url = modelData.url
                                                        var token = foundTokenInput.text.trim()

                                                        if (token === "") {
                                                            console.error("[OpenClaw] Token required")
                                                            return
                                                        }

                                                        // Add URL
                                                        if (copilotPanel.openclawUrls.indexOf(url) === -1) {
                                                            var urls = copilotPanel.openclawUrls.slice()
                                                            urls.push(url)
                                                            copilotPanel.openclawUrls = urls
                                                        }

                                                        // Save token
                                                        copilotPanel.openclawToken = token
                                                        copilotPanel._saveKeyName = "openclaw-token"
                                                        copilotPanel._saveKeyValue = token
                                                        saveKeyProc.running = true

                                                        // Remove from found list
                                                        copilotPanel.foundOpenclawInstances = copilotPanel.foundOpenclawInstances.filter(function(i) {
                                                            return i.url !== url
                                                        })

                                                        console.log("[OpenClaw] Gateway added:", url)
                                                    }
                                                }
                                            }

                                            Rectangle {
                                                anchors {
                                                    left: infoCol.right
                                                    right: addBtn.left
                                                    verticalCenter: parent.verticalCenter
                                                    leftMargin: 8
                                                    rightMargin: 8
                                                }
                                                height: 28
                                                radius: 5
                                                color: copilotPanel.surfaceColor
                                                border.color: foundTokenInput.activeFocus
                                                    ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.5)
                                                    : copilotPanel.borderColor
                                                border.width: 1

                                                TextInput {
                                                    id: foundTokenInput
                                                    anchors { fill: parent; leftMargin: 8; rightMargin: 28; topMargin: 5; bottomMargin: 5 }
                                                    text: ""
                                                    echoMode: foundTokenInput.showToken ? TextInput.Normal : TextInput.Password
                                                    property bool showToken: false
                                                    color: copilotPanel.textColor
                                                    font.pixelSize: 11
                                                    selectByMouse: true

                                                    Text {
                                                        visible: parent.text === ""
                                                        text: "Token"
                                                        color: copilotPanel.subtextColor
                                                        font.pixelSize: 11
                                                        opacity: 0.5
                                                    }
                                                }

                                                Text {
                                                    anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                                                    text: foundTokenInput.showToken ? "◉" : "○"
                                                    font.pixelSize: 13
                                                    color: copilotPanel.subtextColor
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: foundTokenInput.showToken = !foundTokenInput.showToken
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // No instances found message
                            Text {
                                visible: !copilotPanel.scanningOpenclaw &&
                                         copilotPanel.foundOpenclawInstances.length === 0 &&
                                         copilotPanel.openclawUrls.length === 0
                                width: parent.width
                                text: Lang.get("copilot.noInstancesFound")
                                color: copilotPanel.subtextColor
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                horizontalAlignment: Text.AlignHCenter
                                topPadding: 4
                                bottomPadding: 4
                            }

                            // URL list
                            Repeater {
                                model: copilotPanel.openclawUrls
                                delegate: Item {
                                    id: openclawUrlDelegate
                                    required property int index
                                    required property string modelData
                                    width: parent.width
                                    height: openclawUrlCol.height

                                    property var _panel: copilotPanel

                                    Column {
                                        id: openclawUrlCol
                                        width: parent.width; spacing: 4

                                    Row {
                                        width: parent.width; spacing: 8

                                        // Status indicator
                                        Rectangle {
                                            width: 28; height: 36; radius: 6
                                            color: {
                                                var s = openclawUrlDelegate._panel.openclawUrlStatuses[openclawUrlDelegate.index]
                                                if (!s) return openclawUrlDelegate._panel.surfaceColor
                                                if (s.status === "ok") return Qt.rgba(0.18, 0.75, 0.38, 0.2)
                                                if (s.status === "error") return Qt.rgba(0.94, 0.27, 0.27, 0.2)
                                                return Qt.rgba(0.9, 0.7, 0.1, 0.2)  // checking
                                            }
                                            Text {
                                                anchors.centerIn: parent; font.pixelSize: 14
                                                text: {
                                                    var s = openclawUrlDelegate._panel.openclawUrlStatuses[openclawUrlDelegate.index]
                                                    if (!s) return "○"
                                                    if (s.status === "ok") return "✓"
                                                    if (s.status === "error") return "✗"
                                                    return "…"
                                                }
                                                color: {
                                                    var s = openclawUrlDelegate._panel.openclawUrlStatuses[openclawUrlDelegate.index]
                                                    if (!s) return openclawUrlDelegate._panel.subtextColor
                                                    if (s.status === "ok") return "#4ade80"
                                                    if (s.status === "error") return "#f87171"
                                                    return "#fbbf24"
                                                }
                                            }
                                        }

                                        // URL input
                                        Rectangle {
                                            width: (parent.width - 28 - 28 - 28 - 32) / 2; height: 36; radius: 6
                                            color: openclawUrlDelegate._panel.surfaceColor; border.color: openclawUrlDelegate._panel.borderColor; border.width: 1
                                            clip: true
                                            TextInput {
                                                anchors { fill: parent; leftMargin: 10; rightMargin: 10; topMargin: 8; bottomMargin: 8 }
                                                text: openclawUrlDelegate.modelData
                                                color: openclawUrlDelegate._panel.textColor; font.pixelSize: 12; selectByMouse: true
                                                onEditingFinished: {
                                                    var trimmed = text.trim()
                                                    var idx = openclawUrlDelegate.index
                                                    if (trimmed !== openclawUrlDelegate.modelData) {
                                                        var urls = openclawUrlDelegate._panel.openclawUrls.slice()
                                                        urls[idx] = trimmed
                                                        openclawUrlDelegate._panel.openclawUrls = urls
                                                        text = trimmed
                                                    }
                                                }
                                            }
                                        }

                                        // Token input
                                        Rectangle {
                                            width: (parent.width - 28 - 28 - 28 - 32) / 2; height: 36; radius: 6
                                            color: openclawUrlDelegate._panel.surfaceColor; border.color: openclawUrlDelegate._panel.borderColor; border.width: 1
                                            clip: true

                                            TextInput {
                                                id: urlTokenInput
                                                anchors { fill: parent; leftMargin: 10; rightMargin: 30; topMargin: 8; bottomMargin: 8 }
                                                text: openclawUrlDelegate._panel.openclawToken
                                                echoMode: urlTokenInput.showToken ? TextInput.Normal : TextInput.Password
                                                property bool showToken: false
                                                color: openclawUrlDelegate._panel.textColor
                                                font.pixelSize: 12
                                                selectByMouse: true
                                                onEditingFinished: {
                                                    var trimmed = text.trim()
                                                    if (trimmed !== "") {
                                                        openclawUrlDelegate._panel.openclawToken = trimmed
                                                        openclawUrlDelegate._panel._saveKeyName = "openclaw-token"
                                                        openclawUrlDelegate._panel._saveKeyValue = trimmed
                                                        saveKeyProc.running = true
                                                    }
                                                }
                                            }

                                            Text {
                                                anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                                                text: urlTokenInput.showToken ? "◉" : "○"
                                                font.pixelSize: 13
                                                color: openclawUrlDelegate._panel.subtextColor
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: urlTokenInput.showToken = !urlTokenInput.showToken
                                                }
                                            }
                                        }

                                        // Pair button
                                        Rectangle {
                                            width: 28; height: 36; radius: 6
                                            color: openclawUrlDelegate._panel.surfaceColor
                                            border.color: openclawUrlDelegate._panel.borderColor
                                            border.width: 1
                                            ProjectIcon {
                                                anchors.centerIn: parent
                                                name: "link"
                                                font.pixelSize: 14
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    var url = openclawUrlDelegate.modelData.trim()
                                                    if (url !== "") {
                                                        openclawUrlDelegate._panel.pairOpenclawDevice(url)
                                                    }
                                                }
                                            }
                                        }

                                        // Remove button
                                        Rectangle {
                                            width: 28; height: 36; radius: 6
                                            color: openclawUrlDelegate._panel.surfaceColor; border.color: openclawUrlDelegate._panel.borderColor; border.width: 1
                                            visible: openclawUrlDelegate._panel.openclawUrls.length > 0
                                            Text { anchors.centerIn: parent; text: "✕"; color: "#f87171"; font.pixelSize: 13 }
                                            MouseArea {
                                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    var idx = openclawUrlDelegate.index
                                                    var urls = openclawUrlDelegate._panel.openclawUrls.slice()
                                                    urls.splice(idx, 1)
                                                    openclawUrlDelegate._panel.openclawUrls = urls
                                                    var statuses = openclawUrlDelegate._panel.openclawUrlStatuses.slice()
                                                    statuses.splice(idx, 1)
                                                    openclawUrlDelegate._panel.openclawUrlStatuses = statuses
                                                }
                                            }
                                        }
                                    }

                                    // Model count per endpoint
                                    Text {
                                        leftPadding: 36
                                        visible: {
                                            var s = openclawUrlDelegate._panel.openclawUrlStatuses[openclawUrlDelegate.index]
                                            return !!(s && s.status === "ok")
                                        }
                                        text: {
                                            var s = openclawUrlDelegate._panel.openclawUrlStatuses[openclawUrlDelegate.index]
                                            return s ? (s.count || 0) + " " + Lang.get("copilot.modelsAvailable") : ""
                                        }
                                        color: "#4ade80"; font.pixelSize: 11
                                    }
                                    }
                                }
                            }

                            // Add endpoint button
                            Rectangle {
                                width: parent.width; height: 36; radius: 6
                                color: copilotPanel.surfaceColor; border.color: copilotPanel.borderColor; border.width: 1
                                Row {
                                    anchors.centerIn: parent; spacing: 6
                                    Text { text: "+"; color: copilotPanel.accentColor; font.pixelSize: 16; font.weight: Font.Bold }
                                    Text { text: Lang.get("copilot.addEndpoint"); color: copilotPanel.accentColor; font.pixelSize: 13 }
                                }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: {
                                    var urls = copilotPanel.openclawUrls.slice()
                                    urls.push("ws://")
                                    copilotPanel.openclawUrls = urls
                                }}
                            }

                            // Model details list (not toggleable for OpenClaw - always collapsed by default)
                            Column {
                                width: parent.width; spacing: 4
                                visible: copilotPanel.openclawModelDetails.length > 0

                                Text {
                                    text: copilotPanel.openclawModelDetails.length + " " + Lang.get("copilot.modelsFound")
                                    color: copilotPanel.subtextColor; font.pixelSize: 12
                                    bottomPadding: 4
                                }

                                Repeater {
                                    model: copilotPanel.openclawModelDetails
                                    Rectangle {
                                        width: parent.width; height: 46; radius: 6
                                        color: copilotPanel.surfaceColor
                                        border.color: copilotPanel.activeModel === modelData.name && copilotPanel.activeProvider === "openclaw"
                                            ? copilotPanel.accentColor : "transparent"
                                        border.width: 1

                                        Row {
                                            anchors { fill: parent; leftMargin: 12; rightMargin: 12; topMargin: 8; bottomMargin: 8 }
                                            spacing: 8

                                            Column {
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: parent.width - 28
                                                Text {
                                                    text: modelData.name
                                                    color: (copilotPanel.activeModel === modelData.name && copilotPanel.activeProvider === "openclaw") ? copilotPanel.accentColor : copilotPanel.textColor
                                                    font.pixelSize: 13; font.weight: (copilotPanel.activeModel === modelData.name && copilotPanel.activeProvider === "openclaw") ? Font.DemiBold : Font.Normal
                                                    elide: Text.ElideRight; width: parent.width
                                                }
                                                Text {
                                                    text: {
                                                        // Ollama: show family + size
                                                        if (modelData.family && modelData.size) {
                                                            return (modelData.family !== "" ? modelData.family + "  ·  " : "") + modelData.size
                                                        }
                                                        // OpenClaw: show provider + context window
                                                        if (modelData.provider) {
                                                            var parts = []
                                                            if (modelData.provider) parts.push(modelData.provider)
                                                            if (modelData.contextWindow > 0) {
                                                                var ctx = Math.round(modelData.contextWindow / 1024)
                                                                parts.push(ctx + "k")
                                                            }
                                                            return parts.join("  ·  ")
                                                        }
                                                        return ""
                                                    }
                                                    color: copilotPanel.subtextColor; font.pixelSize: 11
                                                }
                                            }

                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: "✓"
                                                color: copilotPanel.accentColor; font.pixelSize: 14; font.weight: Font.Bold
                                                visible: copilotPanel.activeModel === modelData.name && copilotPanel.activeProvider === "openclaw"
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── API KEYS (compact collapsible list) ───────────────
                        Column {
                            width: parent.width; spacing: 0

                            Text {
                                text: "API Keys"
                                color: copilotPanel.accentColor; font.pixelSize: 13; font.weight: Font.Bold
                                bottomPadding: 10
                            }

                            // Top border
                            Rectangle { width: parent.width; height: 1; color: copilotPanel.borderColor; opacity: 0.5 }

                            Repeater {
                                model: [
                                    { label: "Claude (Anthropic)", keyProp: "claudeApiKey",     storeKey: "claude-api-key",     provId: "claude",
                                      testUrl: "https://api.anthropic.com/v1/models",
                                      testHeader: "x-api-key: KEY", testExtra: "anthropic-version: 2023-06-01", testBody: "" },
                                    { label: "ChatGPT (OpenAI)",   keyProp: "openaiApiKey",     storeKey: "openai-api-key",     provId: "openai",
                                      testUrl: "https://api.openai.com/v1/models",
                                      testHeader: "Authorization: Bearer KEY", testExtra: "", testBody: "" },
                                    { label: "Perplexity",         keyProp: "perplexityApiKey", storeKey: "perplexity-api-key", provId: "perplexity",
                                      testUrl: "https://api.perplexity.ai/chat/completions",
                                      testHeader: "Authorization: Bearer KEY", testExtra: "",
                                      testBody: '{"model":"sonar","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' },
                                    { label: "Gemini (Google)",    keyProp: "geminiApiKey",     storeKey: "gemini-api-key",     provId: "gemini",
                                      testUrl: "https://generativelanguage.googleapis.com/v1beta/models?key=KEY",
                                      testHeader: "", testExtra: "", testBody: "" },
                                    { label: "NVIDIA Build",       keyProp: "nvidiaApiKey",     storeKey: "nvidia-api-key",     provId: "nvidia",
                                      testUrl: "https://integrate.api.nvidia.com/v1/models",
                                      testHeader: "Authorization: Bearer KEY", testExtra: "", testBody: "" }
                                ]

                                Column {
                                    width: parent.width; spacing: 0

                                    // ── Compact summary row ──────────────────────
                                    Rectangle {
                                        width: parent.width; height: 44
                                        color: copilotPanel._editingProvider === modelData.provId
                                            ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.08)
                                            : keyRowMa.containsMouse ? Qt.rgba(0.3, 0.3, 0.3, 0.08) : "transparent"
                                        Behavior on color { ColorAnimation { duration: 100 } }

                                        // Status dot
                                        Rectangle {
                                            anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                                            width: 8; height: 8; radius: 4
                                            color: copilotPanel[modelData.keyProp] !== ""
                                                ? (copilotPanel._apiTestedOk[modelData.provId] ? "#4ade80" : "#fbbf24")
                                                : copilotPanel.borderColor
                                        }

                                        // Provider label
                                        Text {
                                            anchors { left: parent.left; leftMargin: 28; verticalCenter: parent.verticalCenter }
                                            text: modelData.label
                                            font.pixelSize: 13; color: copilotPanel.textColor
                                        }

                                        // Status text
                                        Text {
                                            anchors { right: keyToggleIcon.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
                                            font.pixelSize: 11
                                            text: {
                                                var p = modelData.provId
                                                if (copilotPanel.lastSaveProvider === p && copilotPanel.lastSaveResult === "saving") return "Speichern…"
                                                if (copilotPanel.lastTestProvider === p && copilotPanel.lastTestResult === "testing") return "Testen…"
                                                if (copilotPanel._apiTestedOk[p]) return "✓ verifiziert"
                                                return copilotPanel[modelData.keyProp] !== "" ? "✓ gesetzt" : "○ kein Key"
                                            }
                                            color: {
                                                var p = modelData.provId
                                                if (copilotPanel.lastSaveProvider === p && copilotPanel.lastSaveResult === "saving") return copilotPanel.subtextColor
                                                if (copilotPanel.lastTestProvider === p && copilotPanel.lastTestResult === "testing") return copilotPanel.subtextColor
                                                if (copilotPanel._apiTestedOk[p]) return "#4ade80"
                                                return copilotPanel[modelData.keyProp] !== "" ? "#fbbf24" : copilotPanel.subtextColor
                                            }
                                        }

                                        // Expand icon
                                        Text {
                                            id: keyToggleIcon
                                            anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                                            text: copilotPanel._editingProvider === modelData.provId ? "▲" : "▼"
                                            font.pixelSize: 9; color: copilotPanel.subtextColor
                                        }

                                        MouseArea {
                                            id: keyRowMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: copilotPanel._editingProvider =
                                                (copilotPanel._editingProvider === modelData.provId ? "" : modelData.provId)
                                        }
                                    }

                                    // ── Expanded edit panel ──────────────────────
                                    Rectangle {
                                        width: parent.width
                                        height: visible ? keyEditCol.implicitHeight + 20 : 0
                                        visible: copilotPanel._editingProvider === modelData.provId
                                        color: copilotPanel.darkMode ? Qt.rgba(0.1, 0.1, 0.1, 0.6) : Qt.rgba(0.88, 0.88, 0.88, 0.6)
                                        clip: true

                                        Column {
                                            id: keyEditCol
                                            anchors { left: parent.left; right: parent.right; top: parent.top
                                                      margins: 12; topMargin: 10 }
                                            spacing: 10

                                            // Key input row
                                            Row {
                                                spacing: 8; width: parent.width

                                                Rectangle {
                                                    width: parent.width - 92 - 8; height: 36; radius: 6
                                                    clip: true
                                                    color: copilotPanel.surfaceColor
                                                    border.color: keyEditInput.activeFocus
                                                        ? Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.5)
                                                        : copilotPanel.borderColor
                                                    border.width: 1
                                                    Behavior on border.color { ColorAnimation { duration: 120 } }

                                                    TextInput {
                                                        id: keyEditInput
                                                        anchors { fill: parent; leftMargin: 10; rightMargin: 34; topMargin: 8; bottomMargin: 8 }
                                                        text: copilotPanel[modelData.keyProp]
                                                        echoMode: showRaw ? TextInput.Normal : TextInput.Password
                                                        property bool showRaw: false
                                                        color: copilotPanel.textColor; font.pixelSize: 13; selectByMouse: true
                                                        onTextChanged: copilotPanel[modelData.keyProp] = text

                                                        MouseArea {
                                                            anchors.fill: parent
                                                            acceptedButtons: Qt.RightButton
                                                            propagateComposedEvents: true
                                                            onClicked: function(mouse) {
                                                                var g = mapToGlobal(mouse.x, mouse.y)
                                                                var pos = panelRoot.mapFromGlobal(g.x, g.y)
                                                                ctxMenu.targetInput = keyEditInput
                                                                ctxMenu.x = Math.min(pos.x, panelRoot.width - ctxMenu.width - 4)
                                                                ctxMenu.y = Math.max(4, pos.y - ctxMenu.height - 4)
                                                                ctxMenu.visible = true
                                                            }
                                                        }
                                                    }
                                                    // Show/hide toggle
                                                    Text {
                                                        anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                                                        text: keyEditInput.showRaw ? "◉" : "○"
                                                        font.pixelSize: 15; color: copilotPanel.subtextColor
                                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                            onClicked: keyEditInput.showRaw = !keyEditInput.showRaw }
                                                    }
                                                }

                                                Rectangle {
                                                    width: 92; height: 36; radius: 6
                                                    color: Qt.rgba(copilotPanel.accentColor.r, copilotPanel.accentColor.g, copilotPanel.accentColor.b, 0.15)
                                                    border.color: copilotPanel.accentColor; border.width: 1
                                                    Text { anchors.centerIn: parent; text: "Speichern"; color: copilotPanel.accentColor; font.pixelSize: 13 }
                                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: {
                                                        var key = keyEditInput.text.trim()
                                                        if (key === "") return
                                                        copilotPanel.lastSaveProvider = modelData.provId
                                                        copilotPanel.lastSaveResult = "saving"
                                                        copilotPanel._saveKeyName = modelData.storeKey
                                                        copilotPanel._saveKeyValue = key
                                                        saveKeyProc.running = true
                                                    }}
                                                }
                                            }

                                            // Test + status row
                                            Row {
                                                spacing: 10; width: parent.width

                                                Rectangle {
                                                    visible: copilotPanel[modelData.keyProp] !== ""
                                                    width: visible ? 130 : 0; height: 28; radius: 6
                                                    color: Qt.rgba(0.3, 0.3, 0.3, 0.2)
                                                    border.color: copilotPanel.borderColor; border.width: 1
                                                    Text { anchors.centerIn: parent; text: "Verbindung testen"; color: copilotPanel.subtextColor; font.pixelSize: 12 }
                                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: {
                                                        var key = copilotPanel[modelData.keyProp]
                                                        copilotPanel.lastTestProvider  = modelData.provId
                                                        copilotPanel.lastTestResult    = "testing"
                                                        copilotPanel._testApiUrl       = modelData.testUrl.replace("KEY", key)
                                                        copilotPanel._testApiHeader    = modelData.testHeader.replace("KEY", key)
                                                        copilotPanel._testApiExtra     = modelData.testExtra || ""
                                                        copilotPanel._testApiBody      = modelData.testBody  || ""
                                                        testKeyProc.running = true
                                                    }}
                                                }

                                                // Spinner dot
                                                Rectangle {
                                                    width: 7; height: 7; radius: 4; anchors.verticalCenter: parent.verticalCenter
                                                    color: copilotPanel.accentColor
                                                    visible: (copilotPanel.lastSaveProvider === modelData.provId && copilotPanel.lastSaveResult === "saving") ||
                                                             (copilotPanel.lastTestProvider  === modelData.provId && copilotPanel.lastTestResult  === "testing")
                                                    SequentialAnimation on opacity {
                                                        running: parent.visible; loops: Animation.Infinite
                                                        NumberAnimation { to: 0.2; duration: 400; easing.type: Easing.InOutSine }
                                                        NumberAnimation { to: 1.0; duration: 400; easing.type: Easing.InOutSine }
                                                    }
                                                }

                                                Text {
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    font.pixelSize: 12; wrapMode: Text.Wrap; width: 200
                                                    text: {
                                                        var p = modelData.provId
                                                        if (copilotPanel.lastSaveProvider === p && copilotPanel.lastSaveResult !== "") {
                                                            if (copilotPanel.lastSaveResult === "saving") return "Speichern…"
                                                            if (copilotPanel.lastSaveResult === "ok")     return "✓ Im Schlüsselbund gespeichert"
                                                            return "✗ " + copilotPanel.lastSaveResult.replace(/^error:?/i, "").trim()
                                                        }
                                                        if (copilotPanel.lastTestProvider === p && copilotPanel.lastTestResult !== "") {
                                                            if (copilotPanel.lastTestResult === "testing") return "Verbinde…"
                                                            if (copilotPanel.lastTestResult === "ok")      return "✓ API erreichbar, Key gültig"
                                                            return "✗ " + copilotPanel.lastTestResult.replace(/^error:?/i, "").trim()
                                                        }
                                                        return ""
                                                    }
                                                    color: {
                                                        var p = modelData.provId
                                                        var saving  = copilotPanel.lastSaveProvider === p && copilotPanel.lastSaveResult === "saving"
                                                        var testing = copilotPanel.lastTestProvider  === p && copilotPanel.lastTestResult  === "testing"
                                                        if (saving || testing) return copilotPanel.subtextColor
                                                        var okSave = copilotPanel.lastSaveProvider === p && copilotPanel.lastSaveResult === "ok"
                                                        var okTest = copilotPanel.lastTestProvider  === p && copilotPanel.lastTestResult  === "ok"
                                                        if (okSave || okTest) return "#4ade80"
                                                        return "#f87171"
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    // Row divider
                                    Rectangle { width: parent.width; height: 1; color: copilotPanel.borderColor; opacity: 0.4 }
                                }
                            }

                            Text {
                                topPadding: 10; width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 11
                                color: copilotPanel.subtextColor
                                text: "Keys werden im OS-Schlüsselbund gespeichert (via secret-tool / GNOME Keyring / KDE Wallet)."
                            }
                        }

                        Item { width: 1; height: 20 }
                    }
                }
            }

            // Scroll buttons - positioned at right edge of chat area
            Rectangle {
                id: scrollTopBtn
                anchors { right: parent.right; rightMargin: 12; top: parent.top; topMargin: headerBar.height + 20 }
                width: 32; height: 32; radius: 16
                color: Qt.rgba(copilotPanel.surfaceColor.r, copilotPanel.surfaceColor.g, copilotPanel.surfaceColor.b, 0.95)
                border.width: 1; border.color: copilotPanel.borderColor
                visible: copilotPanel.showScrollButtons && chatFlick.contentY > 50
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 200 } }
                z: 100

                Text {
                    anchors.centerIn: parent
                    text: "↑"; font.pixelSize: 18
                    color: copilotPanel.textColor
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        chatFlick.contentY = 0
                        copilotPanel.userScrolled = true
                    }
                }
            }

            Rectangle {
                id: scrollBottomBtn
                anchors { right: parent.right; rightMargin: 12; bottom: composerArea.top; bottomMargin: 8 }
                width: 32; height: 32; radius: 16
                color: Qt.rgba(copilotPanel.surfaceColor.r, copilotPanel.surfaceColor.g, copilotPanel.surfaceColor.b, 0.95)
                border.width: 1; border.color: copilotPanel.borderColor
                visible: copilotPanel.showScrollButtons && chatFlick.contentY < chatFlick.contentHeight - chatFlick.height - 10
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 200 } }
                z: 100

                Text {
                    anchors.centerIn: parent
                    text: "↓"; font.pixelSize: 18
                    color: copilotPanel.textColor
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: copilotPanel.scrollToBottom(true)
                }
            }
        }
    }
}
