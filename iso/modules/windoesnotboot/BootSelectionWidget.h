// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QWidget>
#include <QString>
#include <QStringList>
#include <QJsonArray>
#include <QJsonObject>
#include <functional>
class QLabel;
class BootSelectionWidget : public QWidget {
public:
    enum class DetectionState { Pending, Available, Unavailable };
    explicit BootSelectionWidget(bool efi, QWidget* parent = nullptr);
    QString selected() const { return m_selected; }
    void setGerman(bool german);
    void setDetectedSystems(const QStringList& lines, DetectionState state);
    void setFirmwareEntries(const QString& output, DetectionState state);
    void setReuseOptions(const QJsonArray& options);
    void setDetectedBootloader(const QString& loader);
    QJsonObject reusePlan() const;
    bool selectionValid() const { return !m_reuseMode || !reusePlan().isEmpty(); }
    std::function<void()> selectionChanged;
private:
    void build();
    void updateDetectionText();
    bool m_efi;
    bool m_german = false;
    QString m_selected = QStringLiteral("grub");
    QString m_detectedLoader;
    bool m_userSelected = false;
    QStringList m_systems;
    QString m_firmwareOutput;
    DetectionState m_systemsState = DetectionState::Pending;
    DetectionState m_firmwareState = DetectionState::Pending;
    QLabel* m_detection = nullptr;
    QLabel* m_detectionDetails = nullptr;
    QJsonArray m_reuseOptions;
    bool m_reuseMode = false;
    int m_reuseIndex = 0;
};
