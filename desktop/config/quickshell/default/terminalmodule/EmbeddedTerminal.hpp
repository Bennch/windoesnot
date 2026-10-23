#pragma once

#include <QPointer>
#include <QStringList>
#include <QWindow>
#include <QtQml/qqml.h>

class QWidget;
class QTermWidget;

class EmbeddedTerminal : public QObject {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QWindow *window READ window NOTIFY windowChanged)
    Q_PROPERTY(QString program READ program WRITE setProgram NOTIFY programChanged)
    Q_PROPERTY(QStringList arguments READ arguments WRITE setArguments NOTIFY argumentsChanged)
    Q_PROPERTY(QString workingDirectory READ workingDirectory WRITE setWorkingDirectory NOTIFY workingDirectoryChanged)
    Q_PROPERTY(QString startupCommand READ startupCommand WRITE setStartupCommand NOTIFY startupCommandChanged)
    Q_PROPERTY(QString fontFamily READ fontFamily WRITE setFontFamily NOTIFY fontFamilyChanged)
    Q_PROPERTY(int fontPixelSize READ fontPixelSize WRITE setFontPixelSize NOTIFY fontPixelSizeChanged)
    Q_PROPERTY(bool running READ running NOTIFY runningChanged)

public:
    explicit EmbeddedTerminal(QObject *parent = nullptr);
    ~EmbeddedTerminal() override;

    QWindow *window() const;

    QString program() const;
    void setProgram(const QString &program);

    QStringList arguments() const;
    void setArguments(const QStringList &arguments);

    QString workingDirectory() const;
    void setWorkingDirectory(const QString &workingDirectory);

    QString startupCommand() const;
    void setStartupCommand(const QString &startupCommand);

    QString fontFamily() const;
    void setFontFamily(const QString &fontFamily);

    int fontPixelSize() const;
    void setFontPixelSize(int fontPixelSize);

    bool running() const;

    Q_INVOKABLE void start();
    Q_INVOKABLE void stop();
    Q_INVOKABLE void restart();
    Q_INVOKABLE void sendText(const QString &text);

signals:
    void windowChanged();
    void programChanged();
    void argumentsChanged();
    void workingDirectoryChanged();
    void startupCommandChanged();
    void fontFamilyChanged();
    void fontPixelSizeChanged();
    void runningChanged();
    void receivedData(const QString &text);

private:
    void destroyTerminal();
    void setRunning(bool running);

    QString m_program = "/usr/bin/bash";
    QStringList m_arguments;
    QString m_workingDirectory;
    QString m_startupCommand;
    QString m_fontFamily = "Monospace";
    int m_fontPixelSize = 13;
    bool m_running = false;
    QPointer<QWidget> m_hostWidget;
    QPointer<QTermWidget> m_terminalWidget;
    QPointer<QWindow> m_window;

    // Output processing
    QString m_currentLine;
    QString m_escapeBuf;   // holds trailing incomplete ESC across chunks
    QTimer *m_flushTimer = nullptr;
};
