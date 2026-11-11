#include "EmbeddedTerminal.hpp"

#include <QFont>
#include <QHBoxLayout>
#include <QRegularExpression>
#include <QTimer>
#include <QWidget>

#include <qtermwidget.h>

// Returns true if a stripped terminal line contains enough real text to be worth showing.
// Filters box-drawing borders, very short noise, and highly repetitive sequences.
static bool isUsableLine(const QString &line) {
    if (line.length() < 3) return false;

    int letters = 0;
    QChar prev;
    int runLen = 1, maxRun = 1;
    for (const QChar &c : line) {
        if (c.isLetter()) letters++;
        if (c == prev) { runLen++; maxRun = qMax(maxRun, runLen); } else runLen = 1;
        prev = c;
    }

    if (letters < 4) return false;                                // not enough real text
    if (line.length() > 8 && letters * 4 < line.length()) return false; // < 25 % letters
    if (maxRun > line.length() / 2) return false;                // solid-border run

    return true;
}

EmbeddedTerminal::EmbeddedTerminal(QObject *parent)
    : QObject(parent) {
    m_flushTimer = new QTimer(this);
    m_flushTimer->setSingleShot(true);
    m_flushTimer->setInterval(600);
    connect(m_flushTimer, &QTimer::timeout, this, [this]() {
        const QString trimmed = m_currentLine.trimmed();
        if (!trimmed.isEmpty() && isUsableLine(trimmed)) {
            emit receivedData(trimmed + QLatin1Char('\n'));
        }
        m_currentLine.clear();
    });
}

EmbeddedTerminal::~EmbeddedTerminal() {
    destroyTerminal();
}

QWindow *EmbeddedTerminal::window() const {
    return m_window.data();
}

QString EmbeddedTerminal::program() const {
    return m_program;
}

void EmbeddedTerminal::setProgram(const QString &program) {
    const QString nextProgram = program.trimmed().isEmpty() ? QStringLiteral("/usr/bin/bash") : program.trimmed();
    if (m_program == nextProgram) {
        return;
    }

    m_program = nextProgram;
    emit programChanged();
}

QStringList EmbeddedTerminal::arguments() const {
    return m_arguments;
}

void EmbeddedTerminal::setArguments(const QStringList &arguments) {
    if (m_arguments == arguments) {
        return;
    }

    m_arguments = arguments;
    emit argumentsChanged();
}

QString EmbeddedTerminal::workingDirectory() const {
    return m_workingDirectory;
}

void EmbeddedTerminal::setWorkingDirectory(const QString &workingDirectory) {
    if (m_workingDirectory == workingDirectory) {
        return;
    }

    m_workingDirectory = workingDirectory;
    emit workingDirectoryChanged();
}

QString EmbeddedTerminal::startupCommand() const {
    return m_startupCommand;
}

void EmbeddedTerminal::setStartupCommand(const QString &startupCommand) {
    if (m_startupCommand == startupCommand) {
        return;
    }

    m_startupCommand = startupCommand;
    emit startupCommandChanged();
}

QString EmbeddedTerminal::fontFamily() const {
    return m_fontFamily;
}

void EmbeddedTerminal::setFontFamily(const QString &fontFamily) {
    if (m_fontFamily == fontFamily || fontFamily.trimmed().isEmpty()) {
        return;
    }

    m_fontFamily = fontFamily;
    emit fontFamilyChanged();
}

int EmbeddedTerminal::fontPixelSize() const {
    return m_fontPixelSize;
}

void EmbeddedTerminal::setFontPixelSize(int fontPixelSize) {
    if (m_fontPixelSize == fontPixelSize || fontPixelSize < 8) {
        return;
    }

    m_fontPixelSize = fontPixelSize;
    emit fontPixelSizeChanged();
}

bool EmbeddedTerminal::running() const {
    return m_running;
}

void EmbeddedTerminal::start() {
    if (m_running) {
        return;
    }

    auto *hostWidget = new QWidget();
    hostWidget->setAttribute(Qt::WA_DeleteOnClose);
    hostWidget->setAttribute(Qt::WA_NativeWindow);

    auto *layout = new QHBoxLayout(hostWidget);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    auto *terminalWidget = new QTermWidget(0, hostWidget);
    terminalWidget->setShellProgram(m_program);
    terminalWidget->setArgs(m_arguments);
    terminalWidget->setTerminalFont(QFont(m_fontFamily, -1, QFont::Normal, false));
    terminalWidget->setAutoClose(false);
    terminalWidget->setColorScheme(QStringLiteral("WhiteOnBlack"));
    if (!m_workingDirectory.trimmed().isEmpty()) {
        terminalWidget->setWorkingDirectory(m_workingDirectory.trimmed());
    }

    QFont font = terminalWidget->getTerminalFont();
    font.setPixelSize(m_fontPixelSize);
    terminalWidget->setTerminalFont(font);

    layout->addWidget(terminalWidget);
    hostWidget->setWindowTitle(QStringLiteral("quickshell-agent-terminal"));
    hostWidget->resize(900, 640);
    hostWidget->show();

    // OSC must come BEFORE the generic Fe pattern because ] is inside [@-Z\-_].
    // If Fe matches first it eats \x1b] and leaves the OSC body unstripped.
    static QRegularExpression ansiRe(QStringLiteral(
        "\\x1b(?:"
        "\\][^\\x07\\x1b]*(?:\\x07|\\x1b\\\\)|"   // OSC: ESC ] … BEL|ST
        "P[^\\x1b]*\\x1b\\\\|"                     // DCS: ESC P … ST
        "\\[[0-?]*[ -/]*[@-~]|"                    // CSI: ESC [ … final-byte
        "[@-Z\\\\-_]"                              // Fe:  ESC + single char
        ")"
    ));
    // Keep \t (0x09) and \n (0x0a); strip all other control chars incl. \r and C1 range
    static QRegularExpression controlRe(QStringLiteral("[\\x00-\\x08\\x0b-\\x0d\\x0e-\\x1f\\x7f-\\x9f]"));

    connect(terminalWidget, &QTermWidget::receivedData, this, [this](const QString &text) {
        // QTermWidget emits PTY bytes as Latin-1 characters (one char per byte).
        // Re-interpret those bytes as UTF-8 so box-drawing and other Unicode
        // is decoded correctly instead of appearing as garbled â/Â sequences.
        QString input = m_escapeBuf + QString::fromUtf8(text.toLatin1());
        m_escapeBuf.clear();

        // Normalise Windows-style CRLF so \r doesn't wipe a line before \n sees it
        input.replace(QStringLiteral("\r\n"), QStringLiteral("\n"));

        input.remove(ansiRe);

        // If a bare ESC sits at the very end it may be the start of a split sequence;
        // save it for the next chunk so the regex can match it completely then.
        if (input.endsWith(QLatin1Char('\x1b'))) {
            m_escapeBuf = QStringLiteral("\x1b");
            input.chop(1);
        }

        // Strip remaining control chars (lone \r overwrite-return and others)
        input.remove(controlRe);

        m_flushTimer->stop();

        // Buffer by line; only emit complete lines that pass the content quality check
        QString toEmit;
        for (const QChar &ch : std::as_const(input)) {
            if (ch == QLatin1Char('\n')) {
                const QString trimmed = m_currentLine.trimmed();
                if (!trimmed.isEmpty() && isUsableLine(trimmed))
                    toEmit += trimmed + QLatin1Char('\n');
                m_currentLine.clear();
            } else {
                m_currentLine += ch;
            }
        }

        if (!toEmit.isEmpty())
            emit receivedData(toEmit);

        // Flush any partial line (streaming token without trailing \n) after 600 ms
        if (!m_currentLine.trimmed().isEmpty())
            m_flushTimer->start();
    });

    terminalWidget->startShellProgram();

    m_hostWidget = hostWidget;
    m_terminalWidget = terminalWidget;
    m_window = hostWidget->windowHandle();

    connect(hostWidget, &QObject::destroyed, this, [this]() {
        m_hostWidget = nullptr;
        m_terminalWidget = nullptr;
        m_window = nullptr;
        setRunning(false);
        emit windowChanged();
    });

    setRunning(true);
    emit windowChanged();

    if (!m_startupCommand.trimmed().isEmpty()) {
        const QString command = m_startupCommand;
        QTimer::singleShot(160, this, [this, command]() {
            if (m_terminalWidget) {
                m_terminalWidget->sendText(command + QLatin1Char('\n'));
            }
        });
    }
}

void EmbeddedTerminal::stop() {
    destroyTerminal();
}

void EmbeddedTerminal::restart() {
    destroyTerminal();
    start();
}

void EmbeddedTerminal::sendText(const QString &text) {
    if (!m_terminalWidget) {
        return;
    }

    m_terminalWidget->sendText(text);
}

void EmbeddedTerminal::destroyTerminal() {
    m_flushTimer->stop();
    m_currentLine.clear();
    m_escapeBuf.clear();

    if (!m_hostWidget) {
        if (m_running) {
            setRunning(false);
        }
        return;
    }

    auto *hostWidget = m_hostWidget.data();
    m_hostWidget = nullptr;
    m_terminalWidget = nullptr;
    m_window = nullptr;
    emit windowChanged();
    setRunning(false);
    hostWidget->close();
    hostWidget->deleteLater();
}

void EmbeddedTerminal::setRunning(bool running) {
    if (m_running == running) {
        return;
    }

    m_running = running;
    emit runningChanged();
}
