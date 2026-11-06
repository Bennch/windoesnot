// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QWidget>
#include <QJsonObject>
#include <QSet>
#include <QMap>
#include <functional>
class QCheckBox;
class QComboBox;
class QLineEdit;
class QLabel;
class QVBoxLayout;
class QPushButton;
class QScrollArea;
class QEvent;
class AppSelectionWidget : public QWidget {
public:
    explicit AppSelectionWidget(const QString& catalogPath, QWidget* parent = nullptr);
    QStringList selectedIds() const;
    QString summary() const;
    QString selectedShell() const { return m_shell; }
    void setGerman(bool value);
    void setDarkMode(bool value);
    void setOnlineMode(bool value);
    bool importProfile(const QString& path, QString* error = nullptr);
    bool exportProfile(const QString& path, QString* error = nullptr) const;
    bool setSelection(const QStringList& selected, QString* error = nullptr);
    void applyProfile(const QString& id);
    std::function<void()> selectionChanged;
private:
    QString localized(const QJsonObject& object, const QString& key) const;
    QString text(const char* de, const char* en) const;
    void build();
    void updateStyle();
    void filter();
    void updateCount();
    void notify();
    bool eventFilter(QObject* watched, QEvent* event) override;
    QJsonObject m_catalog;
    QString m_catalogPath;
    QString m_shell;
    QSet<QString> m_selected;
    QMap<QString, QCheckBox*> m_boxes;
    QList<QWidget*> m_cards;
    QComboBox* m_profiles = nullptr;
    QString m_category;
    QList<QPushButton*> m_nav;
    QList<QWidget*> m_headings;
    QLabel* m_title = nullptr;
    QLineEdit* m_search = nullptr;
    QLabel* m_count = nullptr;
    QVBoxLayout* m_list = nullptr;
    QScrollArea* m_scroll = nullptr;
    bool m_german = false;
    bool m_dark = true;
    bool m_online = false;
    bool m_updating = false;
};
