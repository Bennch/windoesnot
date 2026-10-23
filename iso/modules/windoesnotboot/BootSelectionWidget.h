// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QWidget>
#include <QString>
class BootSelectionWidget : public QWidget {
public:
    explicit BootSelectionWidget(bool efi, QWidget* parent = nullptr);
    QString selected() const { return m_selected; }
    void setGerman(bool german);
private:
    void build();
    bool m_efi;
    bool m_german = false;
    QString m_selected = QStringLiteral("grub");
};
