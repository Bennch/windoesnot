// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "DllMacro.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"
#include <QStringList>
#include <QVariantMap>
class BootSelectionWidget;
class QProcess;
class QTimer;
class PLUGINDLLEXPORT BootSelectionViewStep : public Calamares::ViewStep {
    Q_OBJECT
public:
    explicit BootSelectionViewStep(QObject* parent = nullptr);
    QString prettyName() const override;
    QString prettyStatus() const override;
    QWidget* widget() override;
    bool isNextEnabled() const override;
    bool isBackEnabled() const override { return true; }
    bool isAtBeginning() const override { return true; }
    bool isAtEnd() const override { return true; }
    void onActivate() override;
    void onLeave() override;
    Calamares::JobList jobs() const override { return {}; }
    void setConfigurationMap(const QVariantMap&) override {}
private:
    BootSelectionWidget* m_widget = nullptr;
    QProcess* m_firmwareProbe = nullptr;
    QTimer* m_firmwareTimeout = nullptr;
    QTimer* m_systemsTimer = nullptr;
    QProcess* m_reuseProbe = nullptr;
    QTimer* m_reuseTimeout = nullptr;
    int m_systemsAttempts = 0;
    QStringList m_probedSystems;
    bool m_haveProbedSystems = false;
    void refreshSystems();
};
CALAMARES_PLUGIN_FACTORY_DECLARATION(BootSelectionViewStepFactory)
