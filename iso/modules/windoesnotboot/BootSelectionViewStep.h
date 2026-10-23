// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "DllMacro.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"
#include <QVariantMap>
class BootSelectionWidget;
class PLUGINDLLEXPORT BootSelectionViewStep : public Calamares::ViewStep {
    Q_OBJECT
public:
    explicit BootSelectionViewStep(QObject* parent = nullptr);
    QString prettyName() const override;
    QString prettyStatus() const override;
    QWidget* widget() override;
    bool isNextEnabled() const override { return true; }
    bool isBackEnabled() const override { return true; }
    bool isAtBeginning() const override { return true; }
    bool isAtEnd() const override { return true; }
    void onActivate() override;
    void onLeave() override;
    Calamares::JobList jobs() const override { return {}; }
    void setConfigurationMap(const QVariantMap&) override {}
private:
    BootSelectionWidget* m_widget = nullptr;
};
CALAMARES_PLUGIN_FACTORY_DECLARATION(BootSelectionViewStepFactory)
