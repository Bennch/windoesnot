// SPDX-License-Identifier: GPL-3.0-or-later
#include "AppSelectionWidget.h"
#include <QCheckBox>
#include <QFileInfo>
#include <QIcon>
#include <QLocale>
#include <QPushButton>
#include <QStyle>
#include <QComboBox>
#include <QDir>
#include <QFile>
#include <QFileDialog>
#include <QFrame>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPainter>
#include <QSaveFile>
#include <QScrollArea>
#include <QSignalBlocker>
#include <QVBoxLayout>
#include <algorithm>
#include <stdexcept>

AppSelectionWidget::AppSelectionWidget(const QString& catalogPath, QWidget* parent)
    : QWidget(parent), m_catalogPath(catalogPath) {
    QFile file(catalogPath);
    if (!file.open(QIODevice::ReadOnly)) throw std::runtime_error("Application catalogue missing");
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(file.readAll(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) throw std::runtime_error("Invalid application catalogue");
    m_catalog = document.object();
    if (m_catalog.value("schema_version").toInt() != 1 || m_catalog.value("apps").toArray().isEmpty()) throw std::runtime_error("Unsupported application catalogue");
    m_german = QLocale().language() == QLocale::German;
    for (const auto& item : m_catalog.value("apps").toArray()) if (item.toObject().value("required").toBool()) m_selected.insert(item.toObject().value("id").toString());
    for (const auto& item : m_catalog.value("profiles").toArray()) if (item.toObject().value("id") == "recommended")
        for (const auto& id : item.toObject().value("selected").toArray()) m_selected.insert(id.toString());
    build();
}
QString AppSelectionWidget::text(const char* de, const char* en) const { return QString::fromUtf8(m_german ? de : en); }
QString AppSelectionWidget::localized(const QJsonObject& object, const QString& key) const {
    const auto values = object.value(key).toObject();
    return values.value(m_german ? "de" : "en").toString(values.value("en").toString());
}
void AppSelectionWidget::setGerman(bool value) { if (m_german != value) { m_german = value; build(); } }
void AppSelectionWidget::setOnlineMode(bool value) { if(m_online != value) { m_online=value; build(); } }
QStringList AppSelectionWidget::selectedIds() const { auto result = m_selected.values(); std::sort(result.begin(), result.end()); return result; }
QString AppSelectionWidget::summary() const {
    QStringList names;
    for (const auto& app : m_catalog.value("apps").toArray()) if (m_selected.contains(app.toObject().value("id").toString()) && !app.toObject().value("required").toBool()) names << localized(app.toObject(), "name");
    return text("Zusätzliche Programme: ", "Additional apps: ") + (names.isEmpty() ? text("keine", "none") : names.join(", "));
}
void AppSelectionWidget::notify() { updateCount(); if (selectionChanged) selectionChanged(); }
void AppSelectionWidget::updateCount() {
    int optional = 0;
    for (const auto& app : m_catalog.value("apps").toArray()) if (m_selected.contains(app.toObject().value("id").toString()) && !app.toObject().value("required").toBool()) ++optional;
    m_count->setText((m_online ? text("%1 zusätzliche Programme ausgewählt · Download aus dem Internet", "%1 additional apps selected · Download over the internet") : text("%1 zusätzliche Programme ausgewählt · Offline installierbar", "%1 additional apps selected · Available offline")).arg(optional));
}
void AppSelectionWidget::build() {
    m_updating = true;
    if (layout()) {
        QLayoutItem* item;
        while ((item = layout()->takeAt(0))) { if (item->widget()) delete item->widget(); delete item; }
        delete layout();
    }
    m_boxes.clear(); m_cards.clear();
    setObjectName("windoesnotApps");
    updateStyle();
    auto* outer = new QVBoxLayout(this); outer->setContentsMargins(12, 8, 12, 8); outer->setSpacing(12);
    auto* intro = new QLabel(text("Welche Programme möchtest du nutzen?", "Which apps would you like to use?"), this);
    QFont heading = intro->font(); heading.setPointSize(17); heading.setBold(true); intro->setFont(heading); outer->addWidget(intro);
    auto* help = new QLabel(m_online ? text("Online-Installation: Das Grundsystem kommt vom Installationsmedium. Zusatzprogramme werden in passenden Versionen aus dem Internet geladen.\n\nUnsicher? Behalte das empfohlene Softwareprofil. Du kannst Programme abwählen und später im Store hinzufügen. „Profil laden/speichern“ überträgt nur die Programmauswahl, keine persönlichen Dateien oder Konten.", "Online installation: the base system comes from the installation media. Optional apps are downloaded in matching versions.\n\nUnsure? Keep the recommended software profile. You can deselect apps and add them later from the Store. “Load/Save profile” transfers only the app selection, not personal files or accounts.") : text("Offline-Installation: Das Grundsystem und alle hier angebotenen Programme lassen sich ohne Internet installieren.\n\nUnsicher? Behalte das empfohlene Softwareprofil. Du kannst Programme abwählen und später im Store hinzufügen. „Profil laden/speichern“ überträgt nur die Programmauswahl, keine persönlichen Dateien oder Konten.", "Offline installation: the base system and all apps offered here can be installed without an internet connection.\n\nUnsure? Keep the recommended software profile. You can deselect apps and add them later from the Store. “Load/Save profile” transfers only the app selection, not personal files or accounts."), this);
    help->setWordWrap(true); outer->addWidget(help);
    auto* shellRow = new QHBoxLayout;
    shellRow->addWidget(new QLabel(text("Terminal-Shell", "Terminal shell"), this));
    auto* shell = new QComboBox(this);
    shell->setObjectName("userShell");
    shell->addItem(text("Systemstandard", "System default"), QString());
    for (const auto& name : {"bash", "fish", "zsh"})
        shell->addItem(QString::fromUtf8(name), QStringLiteral("/usr/bin/") + name);
    shell->setCurrentIndex(shell->findData(m_shell));
    shell->setToolTip(text("Bestimmt die Shell für neue Terminals. Programme und persönliche Dateien bleiben gleich.", "Selects the shell for new terminals. Apps and personal files stay the same."));
    connect(shell, qOverload<int>(&QComboBox::activated), this, [this, shell](int index) {
        m_shell = shell->itemData(index).toString(); notify();
    });
    shellRow->addWidget(shell, 1); outer->addLayout(shellRow);
    auto* toolbar = new QWidget(this); auto* row = new QHBoxLayout(toolbar); row->setContentsMargins(0,0,0,0);
    m_profiles = new QComboBox(toolbar); m_profiles->setObjectName("softwareProfile"); m_profiles->setAccessibleName(text("Softwareprofil", "Software profile"));
    for (const auto& item : m_catalog.value("profiles").toArray()) m_profiles->addItem(localized(item.toObject(), "name"), item.toObject().value("id").toString());
    m_profiles->addItem(text("Eigene Auswahl", "Custom selection"), "custom");
    int currentProfile = m_profiles->findData("custom");
    for (const auto& item : m_catalog.value("profiles").toArray()) {
        QSet<QString> ids; for (const auto& value : item.toObject().value("selected").toArray()) ids.insert(value.toString());
        if (ids == m_selected) { currentProfile = m_profiles->findData(item.toObject().value("id").toString()); break; }
    }
    m_profiles->setCurrentIndex(currentProfile); row->addWidget(m_profiles, 1);
    auto* importButton = new QPushButton(text("Profil laden", "Load profile"), toolbar); importButton->setObjectName("importProfile"); row->addWidget(importButton);
    auto* exportButton = new QPushButton(text("Profil speichern", "Save profile"), toolbar); exportButton->setObjectName("exportProfile"); row->addWidget(exportButton);
    outer->addWidget(toolbar);
    auto* filters = new QWidget(this); auto* filterRow = new QHBoxLayout(filters); filterRow->setContentsMargins(0,0,0,0);
    m_search = new QLineEdit(filters); m_search->setObjectName("appSearch"); m_search->setPlaceholderText(text("Programme suchen …", "Search apps …")); m_search->setClearButtonEnabled(true); m_search->setAccessibleName(text("Programme suchen", "Search apps")); filterRow->addWidget(m_search, 1);
    m_categories = new QComboBox(filters); m_categories->setObjectName("appCategory"); m_categories->setAccessibleName(text("Kategorie", "Category")); m_categories->addItem(text("Alle Kategorien", "All categories"), "");
    for (const auto& item : m_catalog.value("categories").toArray()) m_categories->addItem(localized(item.toObject(), "name"), item.toObject().value("id").toString());
    filterRow->addWidget(m_categories); outer->addWidget(filters);
    m_scroll = new QScrollArea(this); m_scroll->setWidgetResizable(true);
    auto* content = new QWidget(m_scroll); content->setObjectName("appsGrid"); m_grid = new QGridLayout(content); m_grid->setContentsMargins(0,0,8,0); m_grid->setSpacing(12); m_grid->setColumnStretch(0,1); m_grid->setColumnStretch(1,1);
    const auto apps = m_catalog.value("apps").toArray();
    for (const auto& item : apps) {
        const auto app = item.toObject(); const QString id = app.value("id").toString();
        auto* card = new QFrame(content); card->setProperty("appCard", true); card->setProperty("selected", m_selected.contains(id)); card->setProperty("appId", id); card->setMinimumHeight(120); card->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Minimum);
        auto* v = new QVBoxLayout(card); v->setContentsMargins(14,12,14,12); v->setSpacing(8);
        auto* top = new QHBoxLayout(); auto* icon = new QLabel(card); icon->setFixedSize(32,32);
        QPixmap image;
        for (const auto& extension : {"svg", "png", "xpm"}) { const QString path = QDir(QFileInfo(m_catalogPath).absolutePath()).filePath("icons/"+id+"."+extension); if (QFile::exists(path)) { image = QIcon(path).pixmap(32,32); break; } }
        if (image.isNull()) image = QIcon::fromTheme(app.value("packages").toArray().first().toString()).pixmap(32,32);
        if (image.isNull()) { image = QPixmap(32,32); image.fill(Qt::transparent); QPainter p(&image); p.setRenderHint(QPainter::Antialiasing); p.setBrush(QColor("#fe6f2d")); p.setPen(Qt::NoPen); p.drawRoundedRect(image.rect(),7,7); p.setPen(Qt::white); QFont font = p.font(); font.setBold(true); font.setPixelSize(19); p.setFont(font); p.drawText(image.rect(), Qt::AlignCenter, localized(app,"name").left(1)); }
        icon->setPixmap(image); top->addWidget(icon);
        auto* box = new QCheckBox(localized(app, "name"), card); box->setObjectName("app-"+id); box->setChecked(m_selected.contains(id)); box->setEnabled(!app.value("required").toBool()); box->setAccessibleDescription(localized(app,"description")); QFont title = box->font(); title.setBold(true); box->setFont(title); m_boxes.insert(id,box); top->addWidget(box,1); v->addLayout(top);
        auto* description = new QLabel(localized(app,"description"),card); description->setWordWrap(true); v->addWidget(description,1);
        if (app.value("required").toBool()) { auto* required = new QLabel(text("In der Grundausstattung enthalten", "Included in the essentials"),card); required->setObjectName("includedLabel"); v->addWidget(required); }
        m_cards.append(card);
        connect(box,&QCheckBox::toggled,this,[this,id,card](bool checked) { if (m_updating) return; if (checked) m_selected.insert(id); else m_selected.remove(id); card->setProperty("selected",checked); card->style()->unpolish(card); card->style()->polish(card); QSignalBlocker block(m_profiles); m_profiles->setCurrentIndex(m_profiles->findData("custom")); notify(); });
    }
    m_scroll->setWidget(content); outer->addWidget(m_scroll,1);
    m_count = new QLabel(this); m_count->setWordWrap(true); outer->addWidget(m_count);
    connect(m_profiles,qOverload<int>(&QComboBox::activated),this,[this](int index){ applyProfile(m_profiles->itemData(index).toString()); });
    connect(m_search,&QLineEdit::textChanged,this,[this]{ filter(); });
    connect(m_categories,qOverload<int>(&QComboBox::currentIndexChanged),this,[this]{ filter(); });
    connect(importButton,&QPushButton::clicked,this,[this] { const QString path = QFileDialog::getOpenFileName(this,text("Softwareprofil laden","Load software profile"),QString(),"WinDoesNot (*.json)",nullptr,QFileDialog::DontUseNativeDialog); if (path.isEmpty()) return; QString error; if (!importProfile(path,&error)) QMessageBox::warning(this,text("Profil nicht geladen","Profile not loaded"),error); });
    connect(exportButton,&QPushButton::clicked,this,[this] { const QString path = QFileDialog::getSaveFileName(this,text("Softwareprofil speichern","Save software profile"),"windoesnot-apps.json","WinDoesNot (*.json)",nullptr,QFileDialog::DontUseNativeDialog); if (path.isEmpty()) return; QString error; if (!exportProfile(path,&error)) QMessageBox::warning(this,text("Profil nicht gespeichert","Profile not saved"),error); });
    m_updating = false; filter(); updateCount();
}
void AppSelectionWidget::setDarkMode(bool value) { if(m_dark != value) { m_dark = value; updateStyle(); } }
void AppSelectionWidget::updateStyle() {
    const QString background = m_dark ? "#202024" : "#f3f3f3";
    const QString foreground = m_dark ? "#eeeeee" : "#202024";
    const QString control = m_dark ? "#29292e" : "#ffffff";
    const QString border = m_dark ? "#44444a" : "#c8c8cc";
    const QString muted = m_dark ? "#aaaaaa" : "#666666";
    const QString check = QDir(QFileInfo(m_catalogPath).absolutePath()).filePath("../branding/check.svg");
    setStyleSheet(QStringLiteral(
        "QWidget#windoesnotApps, QWidget#appsGrid { background:%1; color:%2; }"
        "QWidget#windoesnotApps QLabel, QWidget#windoesnotApps QCheckBox { color:%2; background:transparent; }"
        "QWidget#windoesnotApps QLabel#includedLabel { color:%5; font-size:11px; }"
        "QWidget#windoesnotApps QLineEdit, QWidget#windoesnotApps QComboBox { background:%3; color:%2; border:1px solid %4; border-radius:6px; padding:7px; min-height:20px; }"
        "QWidget#windoesnotApps QPushButton { background:%3; color:%2; border:1px solid %4; border-radius:6px; padding:8px 12px; }"
        "QWidget#windoesnotApps QPushButton:hover { border-color:#fe6f2d; }"
        "QWidget#windoesnotApps QComboBox QAbstractItemView { background:%3; color:%2; border:1px solid %4; selection-background-color:#fe6f2d; selection-color:white; }"
        "QWidget#windoesnotApps QScrollArea { border:0; background:%1; }"
        "QWidget#windoesnotApps QFrame[appCard=\"true\"] { background:%3; border:2px solid %4; border-radius:8px; }"
        "QWidget#windoesnotApps QFrame[appCard=\"true\"][selected=\"true\"] { border-color:#fe6f2d; }"
        "QWidget#windoesnotApps QCheckBox::indicator { width:17px; height:17px; border:1px solid %4; border-radius:3px; background:%3; }"
        "QWidget#windoesnotApps QCheckBox::indicator:checked { background:#fe6f2d; border-color:#fe6f2d; image:url(%6); }"
        "QWidget#windoesnotApps QAbstractScrollArea::corner { background:%1; }")
        .arg(background,foreground,control,border,muted,check));
}
void AppSelectionWidget::filter() {
    while (auto* item = m_grid->takeAt(0)) delete item;
    const QString search = m_search->text().trimmed().toCaseFolded(); const QString category = m_categories->currentData().toString();
    int shown = 0; const auto apps = m_catalog.value("apps").toArray();
    for (int i=0;i<apps.size();++i) { const auto app = apps[i].toObject();
        const bool visible = (category.isEmpty() || app.value("category").toString()==category) && (search.isEmpty() || (localized(app,"name")+" "+localized(app,"description")).toCaseFolded().contains(search));
        m_cards[i]->setVisible(visible); if (visible) { m_grid->addWidget(m_cards[i],shown/2,shown%2); ++shown; }
    }
    m_grid->setRowStretch(shown/2+1,1);
}
bool AppSelectionWidget::setSelection(const QStringList& selected, QString* error) {
    QSet<QString> allowed, required; for (const auto& a : m_catalog.value("apps").toArray()) { allowed.insert(a.toObject().value("id").toString()); if(a.toObject().value("required").toBool()) required.insert(a.toObject().value("id").toString()); }
    QSet<QString> ids(selected.begin(),selected.end());
    if (ids.size()!=selected.size() || !allowed.contains(ids) || !ids.contains(required)) { if(error) *error=text("Das Profil enthält unbekannte Programme oder lässt die Grundausstattung aus.","The profile contains unknown apps or omits required essentials."); return false; }
    m_selected = ids; m_updating=true; for(auto it=m_boxes.begin();it!=m_boxes.end();++it) { it.value()->setChecked(ids.contains(it.key())); auto* card=it.value()->parentWidget(); card->setProperty("selected",ids.contains(it.key())); card->style()->unpolish(card); card->style()->polish(card); } m_updating=false;
    { QSignalBlocker block(m_profiles); m_profiles->setCurrentIndex(m_profiles->findData("custom")); }
    notify(); return true;
}
void AppSelectionWidget::applyProfile(const QString& id) {
    for (const auto& item : m_catalog.value("profiles").toArray()) if (item.toObject().value("id").toString()==id) { QStringList ids; for (const auto& value:item.toObject().value("selected").toArray()) ids<<value.toString(); setSelection(ids); QSignalBlocker block(m_profiles); m_profiles->setCurrentIndex(m_profiles->findData(id)); return; }
}
bool AppSelectionWidget::importProfile(const QString& path, QString* error) {
    QFile f(path); if(!f.open(QIODevice::ReadOnly) || f.size()>65536) { if(error)*error=text("Die Profildatei kann nicht gelesen werden oder ist zu groß.","The profile cannot be read or is too large."); return false; }
    QJsonParseError parse; const auto doc=QJsonDocument::fromJson(f.readAll(),&parse); const auto obj=doc.object();
    if(parse.error!=QJsonParseError::NoError || !doc.isObject() || obj.size()!=2 || obj.value("schema_version").toInt()!=1 || !obj.value("selected").isArray()) { if(error)*error=text("Das ist kein gültiges WinDoesNot-Softwareprofil.","This is not a valid WinDoesNot software profile."); return false; }
    QStringList ids; for(const auto& value:obj.value("selected").toArray()) { if(!value.isString()) { if(error)*error=text("Ungültige Programmauswahl.","Invalid application selection.");return false; } ids<<value.toString(); }
    return setSelection(ids,error);
}
bool AppSelectionWidget::exportProfile(const QString& path, QString* error) const {
    QJsonObject object; object.insert("schema_version",1); object.insert("selected",QJsonArray::fromStringList(selectedIds())); QSaveFile file(path);
    if(!file.open(QIODevice::WriteOnly) || file.write(QJsonDocument(object).toJson())<0 || !file.commit()) { if(error)*error=text("Die Profildatei konnte nicht gespeichert werden.","The profile could not be saved."); return false; } return true;
}
