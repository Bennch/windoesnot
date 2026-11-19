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
    Q_PROPERTY(QString installChoice READ installChoice NOTIFY changed)
public:
    explicit MigrateBridge(QObject* parent = nullptr) : QObject(parent) {
        connect(&m_process, &QProcess::started, this, [this] {
            if (m_action == QStringLiteral("unlock") || m_action == QStringLiteral("smb")) { m_process.write(m_secret.toUtf8() + "\n"); m_process.closeWriteChannel(); }
        });
        connect(&m_process, &QProcess::finished, this, [this](int code, QProcess::ExitStatus status) {
            m_busy = false;
            const auto data = m_process.readAllStandardOutput();
            if (code != 0 || status != QProcess::NormalExit) {
                m_error = QString::fromUtf8(m_process.readAllStandardError()).trimmed();
            } else if (m_action == QStringLiteral("partitions")) {
                m_windows = QJsonDocument::fromJson(data).array();
                start(QStringLiteral("linuxPartitions"), {});
                return;
            } else if (m_action == QStringLiteral("linuxPartitions")) {
                auto entries = m_windows;
                for (const auto& value : QJsonDocument::fromJson(data).array()) entries.append(value);
                m_devices = QString::fromUtf8(QJsonDocument(entries).toJson(QJsonDocument::Compact));
                if (!entries.isEmpty()) {
                    QString device = entries.first().toObject().value("device").toString();
                    for (const auto& value : entries) {
                        const auto entry = value.toObject();
                        if (entry.value("filesystem").toString() == QStringLiteral("ntfs")) { device = entry.value("device").toString(); break; }
                    }
                    scan(device); return;
                }
            } else if (m_action == QStringLiteral("smb")) {
                // Packages found on a network share join the list of sources; the first one is opened right away.
                auto entries = QJsonDocument::fromJson(m_devices.toUtf8()).array();
                QString first;
                for (const auto& value : QJsonDocument::fromJson(data).array()) {
                    entries.append(value);
                    if (first.isEmpty()) first = value.toObject().value("device").toString();
                }
                m_secret.clear();
                m_devices = QString::fromUtf8(QJsonDocument(entries).toJson(QJsonDocument::Compact));
                if (first.isEmpty()) { m_error = german() ? QStringLiteral("Auf der Freigabe liegt kein Umzugspaket.") : QStringLiteral("There is no transfer package on the share."); emit changed(); return; }
                emit changed();
                scan(first);
                return;
            } else {
                auto root = QJsonDocument::fromJson(data).object();
                if (root.value("kind").toString() == QStringLiteral("linux")) {
                    auto users = root.value("users").toArray();
                    for (int i = 0; i < users.size(); ++i) {
                        auto user = users[i].toObject(); user.insert("selected", i == 0); users[i] = user;
                    }
                    root.insert("users", users); root.insert("wlan_selected", true);
                    QJsonObject groups;
                    for (const auto& key : {"arch_explicit", "arch_foreign", "deb_manual", "flatpak"}) groups.insert(key, true);
                    root.insert("package_selection", groups);
                    auto entries = QJsonDocument::fromJson(m_devices.toUtf8()).array();
                    for (int i = 0; i < entries.size(); ++i) {
                        auto entry = entries[i].toObject();
                        if (entry.value("device").toString() == m_device) { entry.insert("system", root.value("system")); entries[i] = entry; }
                    }
                    m_devices = QString::fromUtf8(QJsonDocument(entries).toJson(QJsonDocument::Compact));
                }
                m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact));
            }
            emit changed();
        });
    }
    QString manifest() const { return m_manifest; }
    QString devices() const { return m_devices; }
    QString error() const { return m_error; }
    bool busy() const { return m_busy; }
    bool german() const { return QLocale().language() == QLocale::German; }
    QString installChoice() const {
        return Calamares::JobQueue::instance()->globalStorage()->value(QStringLiteral("partitionChoices"))
            .toMap().value(QStringLiteral("install")).toString();
    }
    void refreshChoice() { emit changed(); }
    qint64 freeBytes() const {
        auto* storage = Calamares::JobQueue::instance()->globalStorage();
        const QString path = storage->value("rootMountPoint").toString();
        if (path.isEmpty()) return -1;
        QStorageInfo info(path);
        return info.isValid() && info.isReady() && QDir::cleanPath(info.rootPath()) == QDir::cleanPath(path) ? info.bytesAvailable() : -1;
    }
    QString secret() const { return m_secret; }
    QString envelopeSecret() const { return m_envelopeSecret; }
    bool skipped() const { return m_skip; }
    Q_INVOKABLE void discover() { start(QStringLiteral("partitions"), {}); }
    Q_INVOKABLE void scan(const QString& device) {
        if (device.isEmpty()) return;
        m_device = device; m_manifest.clear(); m_secret.clear(); m_envelopeSecret.clear(); emit changed();
        m_linux = false; QString fs;
        for (const auto& value : QJsonDocument::fromJson(m_devices.toUtf8()).array()) {
            auto entry = value.toObject();
            if (entry.value("device").toString() == device) fs = entry.value("filesystem").toString();
        }
        m_linux = fs != QStringLiteral("ntfs") && fs != QStringLiteral("bitlocker");
        if (fs == QStringLiteral("crypto_luks")) {
            QJsonObject root; root.insert("kind", "linux"); root.insert("device", device); root.insert("system", "Linux"); root.insert("warnings", QJsonArray{QStringLiteral("luks_locked")});
            m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed(); return;
        }
        if (m_linux) start(QStringLiteral("scan"), {device});
        else start(QStringLiteral("scan"), {device, QStringLiteral("--locale"), german() ? QStringLiteral("de_DE.UTF-8") : QStringLiteral("en_US.UTF-8")});
    }
    Q_INVOKABLE void unlock(const QString& secret) {
        if (secret.isEmpty() || m_device.isEmpty()) return;
        m_secret = secret;
        if (m_linux) start(QStringLiteral("unlock"), {m_device, QStringLiteral("--secret-stdin")});
        else start(QStringLiteral("unlock"), {m_device, QStringLiteral("--locale"), german() ? QStringLiteral("de_DE.UTF-8") : QStringLiteral("en_US.UTF-8"), QStringLiteral("--secret-stdin")});
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
    Q_INVOKABLE void setLinuxUser(int index, bool selected) {
        auto root = QJsonDocument::fromJson(m_manifest.toUtf8()).object(); auto users = root.value("users").toArray();
        for (int i = 0; i < users.size(); ++i) { auto user = users[i].toObject(); user.insert("selected", i == index ? selected : (selected ? false : user.value("selected").toBool())); users[i] = user; }
        root.insert("users", users); m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed();
    }
    Q_INVOKABLE void setLinuxGroup(const QString& group, bool selected) {
        auto root = QJsonDocument::fromJson(m_manifest.toUtf8()).object();
        if (group == QStringLiteral("wlan")) root.insert("wlan_selected", selected);
        else {
            auto groups = root.value("package_selection").toObject();
            if (group == QStringLiteral("packages")) { groups.insert("arch_explicit", selected); groups.insert("arch_foreign", selected); groups.insert("deb_manual", selected); }
            if (group == QStringLiteral("flatpak")) groups.insert("flatpak", selected);
            root.insert("package_selection", groups);
        }
        m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed();
    }
    Q_INVOKABLE void setLinuxLocation(const QString& id, bool selected) {
        auto root = QJsonDocument::fromJson(m_manifest.toUtf8()).object(); auto locations = root.value("locations").toArray();
        for (int i = 0; i < locations.size(); ++i) { auto item = locations[i].toObject(); if (item.value("id").toString() == id) { item.insert("selected", selected); locations[i] = item; } }
        root.insert("locations", locations); m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed();
    }
    // A big top-level home folder can be left out; it stays on the old disk.
    Q_INVOKABLE void setHomeFolder(int index, const QString& name, bool included) {
        auto root = QJsonDocument::fromJson(m_manifest.toUtf8()).object(); auto users = root.value("users").toArray();
        if (index < 0 || index >= users.size() || name.isEmpty() || name.contains(QLatin1Char('/'))) return;
        auto user = users[index].toObject(); QJsonArray exclude;
        for (const auto& value : user.value("exclude").toArray()) if (value.toString() != name) exclude.append(value);
        if (!included) exclude.append(name);
        user.insert("exclude", exclude); users[index] = user;
        root.insert("users", users); m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed();
    }
    Q_INVOKABLE void setSkipped(bool skipped) { m_skip = skipped; emit changed(); }
    Q_INVOKABLE void setWlanSelected(bool selected) {
        auto document = QJsonDocument::fromJson(m_manifest.toUtf8());
        auto root = document.object(); auto handoff = root.value("handoff").toObject();
        if (handoff.isEmpty()) return;
        handoff.insert("wlan_selected", selected); root.insert("handoff", handoff);
        m_manifest = QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)); emit changed();
    }
    // Mounts //host/share read-only through mirror.py (the password goes to its stdin, never into a command line).
    Q_INVOKABLE void connectShare(const QString& address, const QString& user, const QString& password) {
        if (address.trimmed().isEmpty()) return;
        m_secret = password;
        QStringList args{address.trimmed()};
        if (!user.trimmed().isEmpty()) args << QStringLiteral("--user") << user.trimmed();
        args << QStringLiteral("--password-stdin");
        start(QStringLiteral("smb"), args);
    }
    Q_INVOKABLE void setSecret(const QString& secret) { m_secret = secret; }
    Q_INVOKABLE void setEnvelopeSecret(const QString& secret) { m_envelopeSecret = secret; }
    void start(const QString& action, const QStringList& args) {
        if (m_process.state() != QProcess::NotRunning) return;
        m_action = action; m_error.clear(); m_busy = true; emit changed();
        m_process.start(QStringLiteral("/usr/bin/python3"), QStringList{(action == QStringLiteral("linuxPartitions") || action == QStringLiteral("smb") || (action != QStringLiteral("partitions") && m_linux)) ? QStringLiteral("/usr/lib/windoesnot/mirror.py") : QStringLiteral("/usr/lib/windoesnot/migrate.py"), action == QStringLiteral("unlock") ? QStringLiteral("scan") : (action == QStringLiteral("linuxPartitions") ? QStringLiteral("partitions") : action)} + args);
    }
signals:
    void changed();
private:
    QProcess m_process;
    QString m_action, m_device, m_manifest, m_devices, m_error, m_secret, m_envelopeSecret;
    QJsonArray m_windows;
    bool m_busy = false, m_skip = false, m_linux = false;
};

class PLUGINDLLEXPORT MigrateViewStep : public Calamares::ViewStep {
    Q_OBJECT
public:
    explicit MigrateViewStep(QObject* parent = nullptr) : Calamares::ViewStep(parent) {}
    QString prettyName() const override { return m_resultMode ? (QLocale().language() == QLocale::German ? QStringLiteral("Abschließen") : QStringLiteral("Done")) : (QLocale().language() == QLocale::German ? QStringLiteral("Umzug") : QStringLiteral("Move data")); }
    QString prettyStatus() const override {
        const bool german = QLocale().language() == QLocale::German;
        if (m_resultMode) return prettyName();
        if (!m_bridge || m_bridge->skipped()) return german ? QStringLiteral("Keine Daten") : QStringLiteral("No data");
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
        for (const auto& value : plan.value("users").toArray()) {
            const auto user = value.toObject();
            if (user.value("selected").toBool()) { folders << user.value("name").toString(); bytes += qint64(user.value("bytes").toDouble()); }
        }
        if (plan.value("wlan_selected").toBool()) folders << (german ? QStringLiteral("WLAN") : QStringLiteral("Wi-Fi"));
        if (plan.value("handoff").toObject().value("wlan_selected").toBool()) folders << (german ? QStringLiteral("WLAN") : QStringLiteral("Wi-Fi"));
        if (folders.isEmpty()) return german ? QStringLiteral("Keine Daten") : QStringLiteral("No data");
        const QString amount = bytes >= 1073741824 ? QString::number(double(bytes) / 1073741824.0, 'f', 1) + QStringLiteral(" GiB") : QString::number(double(bytes) / 1048576.0, 'f', 1) + QStringLiteral(" MiB");
        const QString names = folders.size() > 4 ? folders.mid(0, 4).join(QStringLiteral(", ")) + QStringLiteral(" …") : folders.join(QStringLiteral(", "));
        return names + QStringLiteral(" · ") + amount;
    }
    // The result page shows what the copy job reported, so it is built when the page is shown (the job runs after
    // the widget is created) and again on every activation.
    void buildResult() {
        auto* layout = new QVBoxLayout(m_widget);
        layout->setContentsMargins(28, 28, 28, 28);
        layout->setSpacing(16);
        const bool german = QLocale().language() == QLocale::German;
        auto* gs = Calamares::JobQueue::instance()->globalStorage();
        const QString warning = gs->value(QStringLiteral("windoesnotMigrateWarning")).toString();
        QString system = gs->value(QStringLiteral("windoesnotMigrateSystem")).toString();
        if (system.isEmpty()) system = QStringLiteral("Windows");
        const bool migrated = gs->value(QStringLiteral("windoesnotMigrateCompleted")).toBool();
        auto* title = new QLabel(m_failed ? (german ? QStringLiteral("Die Installation ist fehlgeschlagen.") : QStringLiteral("The installation failed."))
                                          : (german ? QStringLiteral("WinDoesNot wurde installiert.") : QStringLiteral("WinDoesNot has been installed.")), m_widget);
        title->setWordWrap(true);
        title->setStyleSheet(QStringLiteral("color:#eeeeee;font-size:24px;font-weight:700;"));
        layout->addWidget(title);
        if (m_failed) {
            auto* hint = new QLabel(german ? QStringLiteral("Die Einzelheiten stehen im Fehlerfenster. Schließe es, um das Installationsprogramm zu beenden.")
                                           : QStringLiteral("Details are in the error window. Close it to quit the installer."), m_widget);
            hint->setWordWrap(true);
            hint->setStyleSheet(QStringLiteral("color:#aaaaaa;"));
            layout->addWidget(hint);
            layout->addStretch();
            m_widget->setStyleSheet(QStringLiteral("background:#202020;"));
            return;
        }
        if (migrated || !warning.isEmpty()) {
            if (migrated && warning.isEmpty()) {
                auto* detail = new QLabel(german ? QStringLiteral("Daten aus ") + system + QStringLiteral(" wurden übernommen.") : QStringLiteral("Data from ") + system + QStringLiteral(" was transferred."), m_widget);
                detail->setTextFormat(Qt::PlainText);
                detail->setWordWrap(true);
                detail->setStyleSheet(QStringLiteral("color:#eeeeee;background:#141414;border:1px solid #3a3a3a;border-radius:10px;padding:16px;"));
                layout->addWidget(detail);
            } else {
                auto* detail = new QLabel((german ? QStringLiteral("Hinweis zum Datenumzug aus ") + system + QStringLiteral(":\n") : QStringLiteral("Notice about the data move from ") + system + QStringLiteral(":\n")) + warning, m_widget);
                detail->setTextFormat(Qt::PlainText);
                detail->setWordWrap(true);
                detail->setStyleSheet(QStringLiteral("color:#f3c99d;background:#382d22;border:1px solid #b8804b;border-radius:10px;padding:16px;"));
                layout->addWidget(detail);
                auto* retry = new QLabel(german ? QStringLiteral("Nach dem Start können Sie ›Daten übernehmen‹ erneut öffnen.") : QStringLiteral("You can open ‘Bring data’ again after the first boot."), m_widget);
                retry->setWordWrap(true);
                retry->setStyleSheet(QStringLiteral("color:#aaaaaa;"));
                layout->addWidget(retry);
            }
        }
        layout->addStretch();
        auto* restartBtn = new QPushButton(german ? QStringLiteral("Jetzt neu starten") : QStringLiteral("Restart now"), m_widget);
        restartBtn->setStyleSheet(QStringLiteral("QPushButton{background:#fe6f2d;color:#ffffff;border:none;border-radius:6px;padding:10px 24px;font-size:14px;font-weight:600;}QPushButton:hover{background:#ff8040;}QPushButton:pressed{background:#e05a1a;}"));
        QObject::connect(restartBtn, &QPushButton::clicked, [](){ QProcess::startDetached(QStringLiteral("timeout"), {QStringLiteral("10"), QStringLiteral("systemctl"), QStringLiteral("-i"), QStringLiteral("reboot")}); });
        layout->addWidget(restartBtn, 0, Qt::AlignRight);
        m_widget->setStyleSheet(QStringLiteral("background:#202020;"));
    }

    QWidget* widget() override {
        if (!m_widget) {
            m_widget = new QWidget;
            if (m_resultMode) {
                buildResult();
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
    void onActivate() override {
        widget();
        if (m_resultMode) {
            if (auto* old = m_widget->layout()) {
                while (auto* item = old->takeAt(0)) {
                    if (item->widget()) item->widget()->deleteLater();
                    delete item;
                }
                delete old;
            }
            buildResult();
            return;
        }
        if (m_bridge) m_bridge->refreshChoice();
    }
    bool isBackEnabled() const override { return !m_resultMode; }
    bool isAtBeginning() const override { return true; }
    bool isAtEnd() const override { return true; }
    void onLeave() override {
        if (!m_bridge || m_resultMode) return;
        auto* storage = Calamares::JobQueue::instance()->globalStorage();
        storage->insert("windoesnotMigrateManifest", m_bridge->skipped() ? QString() : m_bridge->manifest());
        storage->insert("windoesnotMigrateSecret", m_bridge->skipped() ? QString() : m_bridge->secret());
        storage->insert("windoesnotMigrateEnvelopeSecret", m_bridge->skipped() ? QString() : m_bridge->envelopeSecret());
    }
    Calamares::JobList jobs() const override { return {}; }
    void setConfigurationMap(const QVariantMap& config) override {
        m_resultMode = config.value(QStringLiteral("mode")).toString() == QStringLiteral("result");
        // The job queue emits failed() before it moves on to this page; remember it so the page does not claim success.
        if (m_resultMode)
            if (auto* queue = Calamares::JobQueue::instance())
                connect(queue, &Calamares::JobQueue::failed, this, [this](const QString&, const QString&) { m_failed = true; });
    }
private:
    QWidget* m_widget = nullptr;
    MigrateBridge* m_bridge = nullptr;
    bool m_resultMode = false;
    bool m_failed = false;
};
CALAMARES_PLUGIN_FACTORY_DECLARATION(MigrateViewStepFactory)
CALAMARES_PLUGIN_FACTORY_DEFINITION(MigrateViewStepFactory, registerPlugin<MigrateViewStep>();)
#include "MigrateViewStep.moc"
