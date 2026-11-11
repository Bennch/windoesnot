// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "DllMacro.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"
#include <QVariantMap>
class AppSelectionWidget;
class LiveDesktopBridge;
class PLUGINDLLEXPORT AppSelectionViewStep : public Calamares::ViewStep {
    Q_OBJECT
public:
    explicit AppSelectionViewStep(QObject* parent = nullptr);
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
    void setConfigurationMap(const QVariantMap& configuration) override;
private:
    bool german() const;
    AppSelectionWidget* m_widget = nullptr;
    QWidget* m_errorWidget = nullptr;
    QString m_path;
    bool m_online = false;
    LiveDesktopBridge* m_desktopBridge = nullptr;
};
CALAMARES_PLUGIN_FACTORY_DECLARATION(AppSelectionViewStepFactory)
