// ChatMessageView.qml
// Renders assistant message content: prose via MarkdownText, code via KDE SyntaxHighlighter.
// Usage: ChatMessageView { messageText: msg; accentColor: ...; textColor: ...; darkMode: ... }

import QtQuick
import org.kde.syntaxhighlighting

Item {
    id: root
    implicitHeight: segColumn.implicitHeight

    property string messageText: ""
    property bool   darkMode:        true
    property color  textColor:       "#e8e8e8"
    property color  mutedColor:      "#8a8a8f"
    property color  accentColor:     "#FE6F2D"
    property color  codeBgColor:     Qt.rgba(0.08, 0.08, 0.10, 1.0)
    property color  codeBorderColor: Qt.rgba(1, 1, 1, 0.08)
    property int    textPixelSize:   13
    property int    codePixelSize:   12

    // Hidden TextEdit for clipboard access
    TextEdit { id: clipHelper; visible: false }
    function _copyToClipboard(txt) {
        clipHelper.text = txt
        clipHelper.selectAll()
        clipHelper.copy()
        clipHelper.deselect()
    }

    // Split text into [{type, content, lang}] segments on ``` fences
    property var segments: {
        var segs = [], last = 0, m
        var fence = /```(\w*)\n?([\s\S]*?)```/g
        while ((m = fence.exec(messageText)) !== null) {
            if (m.index > last)
                segs.push({type: "text", content: messageText.slice(last, m.index), lang: ""})
            segs.push({type: "code", content: m[2].replace(/\n$/, ""), lang: m[1] || ""})
            last = m.index + m[0].length
        }
        if (last < messageText.length)
            segs.push({type: "text", content: messageText.slice(last), lang: ""})
        return segs.length > 0 ? segs : [{type: "text", content: messageText, lang: ""}]
    }

    // Split a prose string into logical display blocks so each gets its own
    // TextEdit with appropriate padding — headings, lists, tables, paragraphs.
    function _proseBlocks(text) {
        var lines = text.trim().split('\n')
        var blocks = []
        var buf = [], bufType = "para"

        function flush() {
            if (buf.length === 0) return
            // Trim leading/trailing blank lines from buffer
            while (buf.length > 0 && buf[0].trim() === '') buf.shift()
            while (buf.length > 0 && buf[buf.length - 1].trim() === '') buf.pop()
            if (buf.length > 0)
                blocks.push({type: bufType, content: buf.join('\n')})
            buf = []
            bufType = "para"
        }

        for (var i = 0; i < lines.length; i++) {
            var line = lines[i]
            var isHeading = /^#{1,6} /.test(line)
            var isList    = /^(\s*[-*+]|\s*\d+\.) /.test(line)
            var isContList= buf.length > 0 && bufType === "list" && line.trim() !== ""
            var isTable   = /^\|/.test(line)
            var isBlank   = line.trim() === ''

            if (isHeading) {
                flush()
                blocks.push({type: "heading", content: line})
            } else if (isBlank) {
                flush()
            } else if (isTable) {
                if (bufType !== "table") flush()
                bufType = "table"
                buf.push(line)
            } else if (isList || isContList) {
                if (bufType !== "list") flush()
                bufType = "list"
                buf.push(line)
            } else {
                if (bufType !== "para") flush()
                bufType = "para"
                buf.push(line)
            }
        }
        flush()
        return blocks.length > 0 ? blocks : [{type: "para", content: text.trim()}]
    }

    function _kdeLang(lang) {
        return ({
            "python": "Python",    "py":   "Python",
            "javascript": "JavaScript", "js": "JavaScript",
            "typescript": "TypeScript", "ts": "TypeScript",
            "bash": "Bash", "sh": "Bash", "shell": "Bash", "zsh": "Bash", "fish": "Fish",
            "cpp": "C++",  "c++": "C++", "cxx": "C++",    "c":   "C",
            "java": "Java",   "rust": "Rust",  "rs":  "Rust",
            "go":   "Go",     "json": "JSON",  "yaml": "YAML", "yml": "YAML",
            "toml": "TOML",   "html": "HTML",  "css":  "CSS",  "sql": "SQL",
            "xml":  "XML",    "qml":  "QML",   "cmake":"CMake","diff":"Diff",
            "makefile": "Makefile",
        })[lang.toLowerCase()] || ""
    }

    Column {
        id: segColumn
        width: parent.width
        spacing: 8

        Repeater {
            model: root.segments
            delegate: Loader {
                width: segColumn.width
                readonly property var seg: modelData
                sourceComponent: seg.type === "code" ? codeComp : textComp
            }
        }
    }

    // ── Prose segment — split into blocks for proper per-element spacing ───────
    Component {
        id: textComp
        Column {
            id: proseCol
            width: parent ? parent.width : 0
            spacing: 0

            Repeater {
                model: root._proseBlocks(seg.content)
                delegate: TextEdit {
                    required property var modelData
                    width: proseCol.width
                    text: modelData.content
                    textFormat: TextEdit.MarkdownText
                    color: root.textColor
                    font.pixelSize: root.textPixelSize
                    wrapMode: TextEdit.Wrap
                    readOnly: true
                    selectByMouse: true
                    selectedTextColor: root.textColor
                    selectionColor: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.4)
                    // Headings get extra breathing room; lists/tables a bit less
                    topPadding:    modelData.type === "heading" ? 10 : (modelData.type === "para" ? 3 : 5)
                    bottomPadding: modelData.type === "heading" ? 4  : 2
                }
            }
        }
    }

    // ── Code block segment ────────────────────────────────────────────────────
    Component {
        id: codeComp
        Rectangle {
            id: codeBox
            width: parent ? parent.width : 0
            height: codeEdit.contentHeight + (seg.lang ? 30 : 20)
            color: root.codeBgColor
            radius: 6
            border.width: 1
            border.color: root.codeBorderColor

            // Copy button (top-left) — icon matches rest of UI
            Rectangle {
                id: copyBtn
                anchors { left: parent.left; top: parent.top; margins: 5 }
                width: 22; height: 18
                radius: 3
                color: copyHover.containsMouse
                    ? Qt.rgba(1, 1, 1, 0.12)
                    : Qt.rgba(1, 1, 1, 0.0)

                Image {
                    anchors.centerIn: parent
                    width: 12; height: 12
                    source: copyBtn._copied
                        ? "../img/Win11-dark/actions/16/dialog-ok-apply.svg"
                        : "../img/Win11-dark/actions/16/spray-mode-copy.svg"
                    opacity: copyHover.containsMouse ? 1.0 : 0.5
                }

                property bool _copied: false

                MouseArea {
                    id: copyHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root._copyToClipboard(seg.content)
                        copyBtn._copied = true
                        copyResetTimer.restart()
                    }
                }

                Timer {
                    id: copyResetTimer
                    interval: 1500
                    onTriggered: copyBtn._copied = false
                }
            }

            // Language label (top-right)
            Text {
                visible: seg.lang !== ""
                anchors { right: parent.right; top: parent.top; margins: 6 }
                text: seg.lang
                color: root.mutedColor
                font.pixelSize: 10
                font.family: "monospace"
            }

            TextEdit {
                id: codeEdit
                anchors {
                    left: parent.left; right: parent.right; bottom: parent.bottom
                    top: parent.top
                    leftMargin: 10; rightMargin: 10; bottomMargin: 10
                    topMargin: seg.lang ? 22 : 10
                }
                text: seg.content
                font.family: "monospace"
                font.pixelSize: root.codePixelSize
                wrapMode: TextEdit.Wrap
                readOnly: true
                selectByMouse: true
                color: "#d4d4d4"
                selectedTextColor: "#ffffff"
                selectionColor: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.5)
            }

            SyntaxHighlighter {
                textEdit: codeEdit
                definition: root._kdeLang(seg.lang)
                theme: Repository.defaultTheme(
                    root.darkMode ? Repository.DarkTheme : Repository.LightTheme
                )
            }
        }
    }
}
