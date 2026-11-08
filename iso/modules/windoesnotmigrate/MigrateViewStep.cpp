// SPDX-License-Identifier: GPL-3.0-or-later
#include "DllMacro.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"
#include "GlobalStorage.h"
#include "JobQueue.h"
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDir>
#include <QLabel>
#include <QLocale>
#include <QProcess>
#include <QPushButton>
#include <QQmlContext>
#include <QQuickWidget>
#include <QStringList>
#include <QStorageInfo>
#include <QUrl>
#include <QVBoxLayout>
#include <QWidget>

class MigrateBridge : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString manifest READ manifest NOTIFY changed)
    Q_PROPERTY(QString devices READ devices NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(bool german READ german CONSTANT)
    Q_PROPERTY(qint64 freeBytes READ freeBytes CONSTANT)
public:
    explicit MigrateBridge(QObject* parent = nullptr) : QObject(parent) {
        connect(&m_process, &QProcess::started, this, [this] {
            if (m_action == QStringLiteral("unlock")) { m_process.write(m_secret.toUtf8() + "\n"); m_process.closeWriteChannel(); }
        });
        connect(&m_process, &QProcess::finished, this, [this](int code, QProcess::ExitStatus status) {
            m_busy = false;
            const auto data = m_process.readAllStandardOutput();
            if (code != 0 || status != QProcess::NormalExit) {
                m_error = QString::fromUtf8(m_process.readAllStandardError()).trimmed();
            } else if (m_action == QStringLiteral("partitions")) {
                m_devices = QString::fromUtf8(data).trimmed();
                const auto devices = QJsonDocument::fromJson(data).array();
                bool found = false;
                for (const auto& value : devices) {
                    const auto entry = value.toObject();
                    if (entry.value("filesystem").toString() == QStringLiteral("ntfs")) {
                        scan(entry.value("device").toString());
                        found = true; break;
                    }
                }
                if (!found && !devices.isEmpty()) { scan(devices.first().toObject().value("device").toString()); return; }
            } else {
                m_manifest = QString::fromUtf8(data).trimmed();
            }
            emit changed();
        });
    }
    QString manifest() const { return m_manifest; }
    QString devices() const { return m_devices; }
    QString error() const { return m_error; }
    bool busy() const { return m_busy; }
    bool german() const { return QLocale().language() == QLocale::German; }
    qint64 freeBytes() const {
        auto* storage = Calamares::JobQueue::instance()->globalStorage();
        const QString path = storage->value("rootMountPoint").toString();
        if (path.isEmpty()) return -1;
        QStorageInfo info(path);
        return info.isValid() && info.isReady() && QDir::cleanPath(info.rootPath()) == QDir::cleanPath(path) ? info.bytesAvailable() : -1;
    }
    QString secret() const { return m_secret; }
    bool skipped() const { return m_skip; }
    Q_INVOKABLE void discover() { start(QStringLiteral("partitions"), {}); }
    Q_INVOKABLE void scan(const QString& device) {
        if (device.isEmpty()) return;
        m_device = device; m_manifest.clear(); m_secret.clear(); emit changed();
        start(QStringLiteral("scan"), {device, QStringLiteral("--locale"), german() ? QStringLiteral("de_DE.UTF-8") : QStringLiteral("en_US.UTF-8")});
    }
    Q_INVOKABLE void unlock(const QString& secret) {
        if (secret.isEmpty() || m_device.isEmpty()) return;
        m_secret = secret;
        start(QStringLiteral("unlock"), {m_device, QStringLiteral("--locale"), german() ? QStringLiteral("de_DE.UTF-8") : QStringLiteral("en_US.UTF-8"), QStringLiteral("--secret-stdin")});
    }
    Q_INVOKABLE void setSelected(int profile, int item, bool selected) {
        auto document = QJsonDocument::fromJson(m_manifest.toUtf8());
        auto root = document.object(); auto profiles = root.value("profiles").toArray();
        if (profile < 0 || profile >= profiles.size()) return;
        auto person = profiles[profile].toObject(); auto items = person.value("items").toArray();
        if (item < 0 || item >= items.size()) return;
        auto entry = items[item].toObject(); entry.insert("selected", selected); items[item] = entry;
        person.insert("items", items); profiles[profile] = person; root.insert("profiles", profiles);
        m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed();
    }
    Q_INVOKABLE void setSkipped(bool skipped) { m_skip = skipped; emit changed(); }
    Q_INVOKABLE void setWlanSelected(bool selected) {
        auto document = QJsonDocument::fromJson(m_manifest.toUtf8());
        auto root = document.object(); auto handoff = root.value("handoff").toObject();
        if (handoff.isEmpty()) return;
        handoff.insert("wlan_selected", selected); root.insert("handoff", handoff);
        m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed();
    }
    Q_INVOKABLE void setSecret(const QString& secret) { m_secret = secret; }
    void start(const QString& action, const QStringList& args) {
        if (m_process.state() != QProcess::NotRunning) return;
        m_action = action; m_error.clear(); m_busy = true; emit changed();
        m_process.start(QStringLiteral("/usr/bin/python3"), QStringList{QStringLiteral("/usr/lib/windoesnot/migrate.py"), action == QStringLiteral("unlock") ? QStringLiteral("scan") : action} + args);
    }
signals:
    void changed();
private:
    QProcess m_process;
    QString m_action, m_device, m_manifest, m_devices, m_error, m_secret;
    bool m_busy = false, m_skip = false;
};

class PLUGINDLLEXPORT MigrateViewStep : public Calamares::ViewStep {
    Q_OBJECT
public:
    explicit MigrateViewStep(QObject* parent = nullptr) : Calamares::ViewStep(parent) {}
    QString prettyName() const override { return m_resultMode ? (QLocale().language() == QLocale::German ? QStringLiteral("Abschließen") : QStringLiteral("Done")) : (QLocale().language() == QLocale::German ? QStringLiteral("Windows-Daten") : QStringLiteral("Windows data")); }
    QString prettyStatus() const override {
        const bool german = QLocale().language() == QLocale::German;
        if (m_resultMode) return prettyName();
        if (!m_bridge || m_bridge->skipped()) return german ? QStringLiteral("Keine Windows-Daten") : QStringLiteral("No Windows data");
        const auto plan = QJsonDocument::fromJson(m_bridge->manifest().toUtf8()).object();
        QStringList folders;
        qint64 bytes = 0;
        for (const auto& person : plan.value("profiles").toArray()) {
            for (const auto& value : person.toObject().value("items").toArray()) {
                const auto item = value.toObject();
                if (!item.value("selected").toBool()) continue;
                QString name = item.value("kind").toString();
                if (german) {
                    if (name == QStringLiteral("Documents")) name = QStringLiteral("Dokumente");
                    else if (name == QStringLiteral("Pictures")) name = QStringLiteral("Bilder");
                    else if (name == QStringLiteral("Music")) name = QStringLiteral("Musik");
                }
                folders << name;
                bytes += qint64(item.value("bytes").toDouble());
            }
        }
        if (plan.value("handoff").toObject().value("wlan_selected").toBool()) folders << (german ? QStringLiteral("WLAN") : QStringLiteral("Wi-Fi"));
        if (folders.isEmpty()) return german ? QStringLiteral("Keine Windows-Daten") : QStringLiteral("No Windows data");
        const QString amount = bytes >= 1073741824 ? QString::number(double(bytes) / 1073741824.0, 'f', 1) + QStringLiteral(" GiB") : QString::number(double(bytes) / 1048576.0, 'f', 1) + QStringLiteral(" MiB");
        const QString names = folders.size() > 4 ? folders.mid(0, 4).join(QStringLiteral(", ")) + QStringLiteral(" …") : folders.join(QStringLiteral(", "));
        return names + QStringLiteral(" · ") + amount;
    }
    QWidget* widget() override {
        if (!m_widget) {
            m_widget = new QWidget;
            if (m_resultMode) {
                auto* layout = new QVBoxLayout(m_widget);
                layout->setContentsMargins(28, 28, 28, 28);
                layout->setSpacing(16);
                const bool german = QLocale().language() == QLocale::German;
                auto* gs = Calamares::JobQueue::instance()->globalStorage();
                const QString manifest = gs->value(QStringLiteral("windoesnotMigrateManifest")).toString();
                const QString warning = gs->value(QStringLiteral("windoesnotMigrateWarning")).toString();
                const bool migrated = !manifest.isEmpty();
                auto* title = new QLabel(german ? QStringLiteral("WinDoesNot wurde installiert.") : QStringLiteral("WinDoesNot has been installed."), m_widget);
                title->setStyleSheet(QStringLiteral("color:#eeeeee;font-size:24px;font-weight:700;"));
                layout->addWidget(title);
                if (migrated) {
                    if (warning.isEmpty()) {
                        auto* detail = new QLabel(german ? QStringLiteral("Windows-Daten wurden übernommen.") : QStringLiteral("Windows data was transferred."), m_widget);
                        detail->setTextFormat(Qt::PlainText);
                        detail->setWordWrap(true);
                        detail->setStyleSheet(QStringLiteral("color:#eeeeee;background:#141414;border:1px solid #3a3a3a;border-radius:10px;padding:16px;"));
                        layout->addWidget(detail);
                    } else {
                        auto* detail = new QLabel((german ? QStringLiteral("Hinweis zum Windows-Datenumzug:\n") : QStringLiteral("Windows data migration notice:\n")) + warning, m_widget);
                        detail->setTextFormat(Qt::PlainText);
                        detail->setWordWrap(true);
                        detail->setStyleSheet(QStringLiteral("color:#f3c99d;background:#382d22;border:1px solid #b8804b;border-radius:10px;padding:16px;"));
                        layout->addWidget(detail);
                        auto* retry = new QLabel(german ? QStringLiteral("Nach dem Start können Sie ›Windows-Daten übernehmen‹ erneut öffnen.") : QStringLiteral("You can open ‘Bring Windows data’ again after the first boot."), m_widget);
                        retry->setWordWrap(true);
                        retry->setStyleSheet(QStringLiteral("color:#aaaaaa;"));
                        layout->addWidget(retry);
                    }
                }
                layout->addStretch();
                auto* restartBtn = new QPushButton(german ? QStringLiteral("Jetzt neu starten") : QStringLiteral("Restart now"), m_widget);
                restartBtn->setStyleSheet(QStringLiteral("QPushButton{background:#fe6f2d;color:#ffffff;border:none;border-radius:6px;padding:10px 24px;font-size:14px;font-weight:600;}QPushButton:hover{background:#ff8040;}QPushButton:pressed{background:#e05a1a;}"));
                QObject::connect(restartBtn, &QPushButton::clicked, [](){ QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("-i"), QStringLiteral("reboot")}); });
                layout->addWidget(restartBtn, 0, Qt::AlignRight);
                m_widget->setStyleSheet(QStringLiteral("background:#202020;"));
                return m_widget;
            }
            m_bridge = new MigrateBridge(m_widget);
            auto* layout = new QVBoxLayout(m_widget); layout->setContentsMargins(0, 0, 0, 0);
            auto* quick = new QQuickWidget(m_widget);
            quick->rootContext()->setContextProperty(QStringLiteral("migrateBridge"), m_bridge);
            quick->setResizeMode(QQuickWidget::SizeRootObjectToView);
            quick->setSource(QUrl::fromLocalFile(QStringLiteral("/usr/share/windoesnot/iso/modules/windoesnotmigrate/main.qml")));
            layout->addWidget(quick);
            m_bridge->discover();
        }
        return m_widget;
    }
    bool isNextEnabled() const override { return true; }
    bool isBackEnabled() const override { return !m_resultMode; }
    bool isAtBeginning() const override { return true; }
    bool isAtEnd() const override { return true; }
    void onLeave() override {
        if (!m_bridge || m_resultMode) return;
        auto* storage = Calamares::JobQueue::instance()->globalStorage();
        storage->insert("windoesnotMigrateManifest", m_bridge->skipped() ? QString() : m_bridge->manifest());
        storage->insert("windoesnotMigrateSecret", m_bridge->skipped() ? QString() : m_bridge->secret());
    }
    Calamares::JobList jobs() const override { return {}; }
    void setConfigurationMap(const QVariantMap& config) override { m_resultMode = config.value(QStringLiteral("mode")).toString() == QStringLiteral("result"); }
private:
    QWidget* m_widget = nullptr;
    MigrateBridge* m_bridge = nullptr;
    bool m_resultMode = false;
};
CALAMARES_PLUGIN_FACTORY_DECLARATION(MigrateViewStepFactory)
CALAMARES_PLUGIN_FACTORY_DEFINITION(MigrateViewStepFactory, registerPlugin<MigrateViewStep>();)
#include "MigrateViewStep.moc"
