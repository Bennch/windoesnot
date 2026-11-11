// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QFileSystemWatcher>
#include <QTimer>
#include <functional>
class LiveDesktopBridge : public QObject {
public:
    explicit LiveDesktopBridge(QObject* parent = nullptr);
    bool darkMode() const { return m_dark; }
    std::function<void(bool)> appearanceChanged;
protected:
    bool eventFilter(QObject* object, QEvent* event) override;
private:
    void applySettings();
    void synchronizeLanguage();
    void synchronizeKeyboard();
    void updateWelcomeLogo();
    void updateSidebar();
    QFileSystemWatcher m_watcher;
    QTimer m_settingsTimer;
    QTimer m_languageTimer;
    QString m_language;
    QString m_keyboard;
    bool m_dark = true;
    bool m_ready = false;
};
