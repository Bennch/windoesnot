// SPDX-License-Identifier: GPL-3.0-or-later
#include "AppSelectionViewStep.h"
#include "AppSelectionWidget.h"
#include "LiveDesktopBridge.h"
#include "GlobalStorage.h"
#include "JobQueue.h"
#include <QLabel>
#include <QLocale>
CALAMARES_PLUGIN_FACTORY_DEFINITION(AppSelectionViewStepFactory, registerPlugin<AppSelectionViewStep>();)
AppSelectionViewStep::AppSelectionViewStep(QObject* parent) : Calamares::ViewStep(parent) {
    m_desktopBridge = new LiveDesktopBridge(this);
    m_desktopBridge->appearanceChanged = [this](bool dark) { if(m_widget) m_widget->setDarkMode(dark); };
}
bool AppSelectionViewStep::german() const {
    return QLocale().language() == QLocale::German;
}
QString AppSelectionViewStep::prettyName() const { return german() ? QStringLiteral("Programme") : QStringLiteral("Apps"); }
QString AppSelectionViewStep::prettyStatus() const { return m_widget ? m_widget->summary() : QString(); }
void AppSelectionViewStep::setConfigurationMap(const QVariantMap& config) {
    m_path = config.value("catalog", "/usr/share/windoesnot/iso/software/catalog.json").toString();
    m_online = config.value("mode").toString() == "online";
}
QWidget* AppSelectionViewStep::widget() {
    if (!m_widget && !m_errorWidget) {
        try {
            m_widget = new AppSelectionWidget(m_path);
            m_widget->setOnlineMode(m_online);
            m_widget->setGerman(german());
            m_widget->setDarkMode(m_desktopBridge->darkMode());
            m_widget->selectionChanged = [this] { emit nextStatusChanged(true); };
        } catch (const std::exception&) {
            auto* label = new QLabel(german() ? "Die Programmliste konnte nicht geladen werden. Bitte das Live-System neu starten." : "The application list could not be loaded. Please restart the live system.");
            label->setWordWrap(true); m_errorWidget=label; emit nextStatusChanged(false);
        }
    }
    return m_widget ? static_cast<QWidget*>(m_widget) : m_errorWidget;
}
bool AppSelectionViewStep::isNextEnabled() const { return m_errorWidget == nullptr; }
void AppSelectionViewStep::onActivate() { widget(); if(m_widget) m_widget->setGerman(german()); }
void AppSelectionViewStep::onLeave() {
    if (m_widget) {
        auto* storage = Calamares::JobQueue::instance()->globalStorage();
        storage->insert("windoesnotSoftwareSelection",m_widget->selectedIds());
        storage->insert("windoesnotUserShell", m_widget->selectedShell());
    }
}
