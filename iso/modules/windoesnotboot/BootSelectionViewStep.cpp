// SPDX-License-Identifier: GPL-3.0-or-later
#include "BootSelectionViewStep.h"
#include "BootSelectionWidget.h"
#include "GlobalStorage.h"
#include "JobQueue.h"
#include <QFileInfo>
#include <QLocale>
#include <QProcess>
#include <QProcessEnvironment>
#include <QTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
CALAMARES_PLUGIN_FACTORY_DEFINITION(BootSelectionViewStepFactory, registerPlugin<BootSelectionViewStep>();)
BootSelectionViewStep::BootSelectionViewStep(QObject* parent) : Calamares::ViewStep(parent) {
    m_systemsTimer=new QTimer(this);
    m_systemsTimer->setInterval(500);
    connect(m_systemsTimer,&QTimer::timeout,this,&BootSelectionViewStep::refreshSystems);
    m_firmwareProbe=new QProcess(this);
    auto environment=QProcessEnvironment::systemEnvironment();
    environment.insert("LC_ALL","C");
    m_firmwareProbe->setProcessEnvironment(environment);
    m_firmwareTimeout=new QTimer(this);
    m_firmwareTimeout->setSingleShot(true);
    connect(m_firmwareTimeout,&QTimer::timeout,m_firmwareProbe,&QProcess::kill);
    connect(m_firmwareProbe,&QProcess::errorOccurred,this,[this](QProcess::ProcessError) {
        m_firmwareTimeout->stop();
        if(m_widget) m_widget->setFirmwareEntries({},BootSelectionWidget::DetectionState::Unavailable);
    });
    connect(m_firmwareProbe,&QProcess::finished,this,[this](int code,QProcess::ExitStatus status) {
        m_firmwareTimeout->stop();
        if(m_widget) m_widget->setFirmwareEntries(QString::fromUtf8(m_firmwareProbe->readAllStandardOutput()),
            code==0 && status==QProcess::NormalExit?BootSelectionWidget::DetectionState::Available:BootSelectionWidget::DetectionState::Unavailable);
    });
    m_reuseProbe=new QProcess(this);m_reuseProbe->setProcessEnvironment(environment);
    m_reuseTimeout=new QTimer(this);m_reuseTimeout->setSingleShot(true);
    connect(m_reuseTimeout,&QTimer::timeout,m_reuseProbe,&QProcess::terminate);
    connect(m_reuseProbe,&QProcess::started,this,[this] {
        const auto lines=Calamares::JobQueue::instance()->globalStorage()->value("osproberLines").toStringList();
        m_probedSystems=lines;m_haveProbedSystems=true;
        m_reuseProbe->write(QJsonDocument(QJsonObject{{"osprober",QJsonArray::fromStringList(lines)}}).toJson(QJsonDocument::Compact));
        m_reuseProbe->closeWriteChannel();
    });
    connect(m_reuseProbe,&QProcess::errorOccurred,this,[this](QProcess::ProcessError) {
        m_reuseTimeout->stop();if(m_widget) { m_widget->setDetectedBootloader({}); m_widget->setReuseOptions({}); }
    });
    connect(m_reuseProbe,&QProcess::finished,this,[this](int code,QProcess::ExitStatus status) {
        m_reuseTimeout->stop();
        const auto result=QJsonDocument::fromJson(m_reuseProbe->readAllStandardOutput());
        if (m_widget) m_widget->setDetectedBootloader(code==0 && status==QProcess::NormalExit
            ? result.object().value("detected_bootloader").toString() : QString());
        if(m_widget) m_widget->setReuseOptions(code==0 && status==QProcess::NormalExit
            ?result.object().value("candidates").toArray():QJsonArray());
    });
}
QString BootSelectionViewStep::prettyName() const { return QLocale().language()==QLocale::German ? QStringLiteral("Startmenü") : QStringLiteral("Boot menu"); }
QString BootSelectionViewStep::prettyStatus() const {
    if(!m_widget) return {};
    const auto reuse=m_widget->reusePlan();
    return prettyName()+QStringLiteral(": ")+(reuse.isEmpty()?m_widget->selected():reuse.value("label").toString()+QStringLiteral(" → WinDoesNot"));
}
QWidget* BootSelectionViewStep::widget() {
    if(!m_widget) {
        m_widget=new BootSelectionWidget(QFileInfo::exists("/sys/firmware/efi"));
        m_widget->selectionChanged=[this] { emit nextStatusChanged(m_widget->selectionValid()); };
    }
    return m_widget;
}
bool BootSelectionViewStep::isNextEnabled() const { return !m_widget || m_widget->selectionValid(); }
void BootSelectionViewStep::refreshSystems() {
    if(++m_systemsAttempts>=120) m_systemsTimer->stop();
    auto* storage=Calamares::JobQueue::instance()->globalStorage();
    if(storage->contains("osproberLines")) {
        const auto lines=storage->value("osproberLines").toStringList();
        m_widget->setDetectedSystems(lines,BootSelectionWidget::DetectionState::Available);
        // Calamares can publish its list incrementally. Watch that same list;
        // inspect a changed result once, never start another OS scan.
        if(QFileInfo::exists("/sys/firmware/efi") && m_reuseProbe->state()==QProcess::NotRunning
                && (!m_haveProbedSystems || lines!=m_probedSystems)) {
            m_reuseProbe->start("/usr/bin/python3",{QStringLiteral("/usr/share/windoesnot/iso/boot_environment.py")});
            m_reuseTimeout->start(90000);
        }
    } else if(m_systemsAttempts>=120) {
        m_widget->setDetectedSystems({},BootSelectionWidget::DetectionState::Unavailable);
        m_systemsTimer->stop();
    }
}
void BootSelectionViewStep::onActivate() {
    widget();m_widget->setGerman(QLocale().language()==QLocale::German);
    // Reuse Calamares' existing Windows/Linux scan; never run a second os-prober.
    m_systemsAttempts=0;
    m_haveProbedSystems=false;
    m_systemsTimer->start();
    refreshSystems();
    if(QFileInfo::exists("/sys/firmware/efi") && m_firmwareProbe->state()==QProcess::NotRunning) {
        m_widget->setFirmwareEntries({},BootSelectionWidget::DetectionState::Pending);
        // No write flags: show registered entries without changing boot order.
        m_firmwareProbe->start("/usr/bin/efibootmgr",{QStringLiteral("-v")});
        m_firmwareTimeout->start(5000);
    }
}
void BootSelectionViewStep::onLeave() {
    m_systemsTimer->stop();
    if(m_widget && m_widget->selectionValid()) {
        auto* storage=Calamares::JobQueue::instance()->globalStorage();
        const auto reuse=m_widget->reusePlan();
        storage->insert("packagechooser_bootloader",m_widget->selected());
        storage->insert("windoesnotBootReuse",reuse.isEmpty()?QString():QString::fromUtf8(QJsonDocument(reuse).toJson(QJsonDocument::Compact)));
        storage->insert("windoesnotBootInstall",reuse.isEmpty()?m_widget->selected():QStringLiteral("none"));
    }
}
