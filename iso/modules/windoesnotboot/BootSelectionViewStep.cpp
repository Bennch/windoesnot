// SPDX-License-Identifier: GPL-3.0-or-later
#include "BootSelectionViewStep.h"
#include "BootSelectionWidget.h"
#include "GlobalStorage.h"
#include "JobQueue.h"
#include <QFileInfo>
#include <QLocale>
CALAMARES_PLUGIN_FACTORY_DEFINITION(BootSelectionViewStepFactory, registerPlugin<BootSelectionViewStep>();)
BootSelectionViewStep::BootSelectionViewStep(QObject* parent) : Calamares::ViewStep(parent) {}
QString BootSelectionViewStep::prettyName() const { return QStringLiteral("Bootloader"); }
QString BootSelectionViewStep::prettyStatus() const { return m_widget ? QStringLiteral("Bootloader: ")+m_widget->selected() : QString(); }
QWidget* BootSelectionViewStep::widget() {
    if(!m_widget) m_widget=new BootSelectionWidget(QFileInfo::exists("/sys/firmware/efi"));
    return m_widget;
}
void BootSelectionViewStep::onActivate() { widget(); m_widget->setGerman(QLocale().language()==QLocale::German); }
void BootSelectionViewStep::onLeave() {
    if(m_widget) Calamares::JobQueue::instance()->globalStorage()->insert("packagechooser_bootloader",m_widget->selected());
}
