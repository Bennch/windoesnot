// SPDX-License-Identifier: GPL-3.0-or-later
#include "AppSelectionWidget.h"
#include <QCheckBox>
#include <QEvent>
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
    m_boxes.clear(); m_cards.clear(); m_headings.clear(); m_nav.clear();
    setObjectName("windoesnotApps");
    updateStyle();
    auto* root = new QHBoxLayout(this); root->setContentsMargins(0, 0, 0, 0); root->setSpacing(0);

    // Left: categories in the look of the Store's navigation (rounded row, orange bar on the active entry).
    auto* sidebar = new QWidget(this); sidebar->setObjectName("appsSidebar"); sidebar->setFixedWidth(200);
    auto* side = new QVBoxLayout(sidebar); side->setContentsMargins(10, 24, 10, 12); side->setSpacing(6);
    auto* brand = new QLabel(text("Programme", "Apps"), sidebar); brand->setObjectName("appsBrand"); side->addWidget(brand); side->addSpacing(12);
    auto addNav = [&](const QString& id, const QString& label) {
        auto* button = new QPushButton(sidebar); button->setObjectName("navEntry"); button->setCheckable(true); button->setChecked(id == m_category);
        button->setProperty("catId", id); button->setCursor(Qt::PointingHandCursor); button->setFlat(true); button->setAccessibleName(label); button->setFixedHeight(45);
        // Accent bar like the Store's active entry: a small rounded element (3x22), not a border over the whole row.
        auto* inner = new QHBoxLayout(button); inner->setContentsMargins(4, 0, 10, 0); inner->setSpacing(12);
        auto* bar = new QFrame(button); bar->setObjectName("navBar"); bar->setFixedSize(3, 22); bar->setAttribute(Qt::WA_TransparentForMouseEvents); bar->setProperty("active", id == m_category);
        auto* name = new QLabel(label, button); name->setObjectName("navText"); name->setAttribute(Qt::WA_TransparentForMouseEvents);
        inner->addWidget(bar, 0, Qt::AlignVCenter); inner->addWidget(name, 1);
        connect(button, &QPushButton::clicked, this, [this, id] {
            m_category = id;
            for (auto* other : m_nav) {
                const bool active = other->property("catId").toString() == id; other->setChecked(active);
                if (auto* mark = other->findChild<QFrame*>("navBar")) { mark->setProperty("active", active); mark->style()->unpolish(mark); mark->style()->polish(mark); }
            }
            filter();
        });
        m_nav.append(button); side->addWidget(button);
    };
    addNav(QString(), text("Alle", "All"));
    for (const auto& item : m_catalog.value("categories").toArray()) addNav(item.toObject().value("id").toString(), localized(item.toObject(), "name"));
    side->addStretch(1);
    root->addWidget(sidebar);

    // Right: title with divider, profile tools, search, one row per app.
    auto* page = new QWidget(this); page->setObjectName("appsPage");
    auto* outer = new QVBoxLayout(page); outer->setContentsMargins(22, 18, 22, 12); outer->setSpacing(10);
    m_title = new QLabel(page); m_title->setObjectName("pageTitle"); outer->addWidget(m_title);
    auto* divider = new QFrame(page); divider->setObjectName("divider"); divider->setFixedHeight(1); outer->addWidget(divider);
    auto* help = new QLabel(m_online ? text("Online-Installation: Das Grundsystem kommt vom Installationsmedium, Zusatzprogramme werden aus dem Internet geladen. Mit „Wird nach der Installation geladen“ markierte Programme folgen, sobald du online bist.",
                                           "Online installation: the base system comes from the installation media, optional apps are downloaded. Apps marked “Installed after setup” follow once you are online.")
                                 : text("Das Grundsystem und die meisten Programme lassen sich ohne Internet installieren. Programme mit dem Hinweis „Wird nach der Installation geladen“ kommen, sobald du online bist.",
                                           "The base system and most apps install without internet. Apps marked “Installed after setup” are downloaded once you are online."), page);
    help->setObjectName("helpText"); help->setWordWrap(true); outer->addWidget(help);
    m_search = new QLineEdit(page); m_search->setObjectName("appSearch"); m_search->setPlaceholderText(text("Programme suchen …", "Search apps …")); m_search->setClearButtonEnabled(true); m_search->setAccessibleName(text("Programme suchen", "Search apps"));
    m_profiles = new QComboBox(page); m_profiles->setObjectName("softwareProfile"); m_profiles->setAccessibleName(text("Softwareprofil", "Software profile"));
    for (const auto& item : m_catalog.value("profiles").toArray()) m_profiles->addItem(localized(item.toObject(), "name"), item.toObject().value("id").toString());
    m_profiles->addItem(text("Eigene Auswahl", "Custom selection"), "custom");
    int currentProfile = m_profiles->findData("custom");
    for (const auto& item : m_catalog.value("profiles").toArray()) {
        QSet<QString> ids; for (const auto& value : item.toObject().value("selected").toArray()) ids.insert(value.toString());
        if (ids == m_selected) { currentProfile = m_profiles->findData(item.toObject().value("id").toString()); break; }
    }
    m_profiles->setCurrentIndex(currentProfile);
    m_profiles->setMinimumWidth(220);
    m_profiles->setToolTip(text("Unsicher? Behalte das empfohlene Softwareprofil. Du kannst Programme abwählen und später im Store hinzufügen. „Profil laden/speichern“ überträgt nur die Programmauswahl, keine persönlichen Dateien oder Konten.",
                                "Unsure? Keep the recommended software profile. You can deselect apps and add them later from the Store. “Load/Save profile” transfers only the app selection, not personal files or accounts."));
    auto* topRow = new QHBoxLayout; topRow->setSpacing(10); topRow->addWidget(m_search, 1); topRow->addWidget(m_profiles); outer->addLayout(topRow);
    m_scroll = new QScrollArea(page); m_scroll->setWidgetResizable(true); m_scroll->setFrameShape(QFrame::NoFrame);
    auto* content = new QWidget(m_scroll); content->setObjectName("appsGrid"); m_list = new QVBoxLayout(content); m_list->setContentsMargins(0,0,8,0); m_list->setSpacing(8);
    const auto apps = m_catalog.value("apps").toArray();
    for (const auto& item : apps) {
        const auto app = item.toObject(); const QString id = app.value("id").toString();
        auto* card = new QFrame(content); card->setProperty("appCard", true); card->setProperty("selected", m_selected.contains(id)); card->setProperty("appId", id);
        card->setAttribute(Qt::WA_Hover); card->setMinimumHeight(68); card->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Minimum); card->installEventFilter(this);
        auto* h = new QHBoxLayout(card); h->setContentsMargins(14, 10, 14, 10); h->setSpacing(14);
        auto* icon = new QLabel(card); icon->setFixedSize(32,32);
        QPixmap image;
        for (const auto& extension : {"svg", "png", "xpm"}) { const QString path = QDir(QFileInfo(m_catalogPath).absolutePath()).filePath("icons/"+id+"."+extension); if (QFile::exists(path)) { image = QIcon(path).pixmap(32,32); break; } }
        if (image.isNull()) image = QIcon::fromTheme(app.value("packages").toArray().at(0).toString()).pixmap(32,32);
        if (image.isNull()) { image = QPixmap(32,32); image.fill(Qt::transparent); QPainter p(&image); p.setRenderHint(QPainter::Antialiasing); p.setBrush(QColor("#fe6f2d")); p.setPen(Qt::NoPen); p.drawRoundedRect(image.rect(),7,7); p.setPen(Qt::white); QFont font = p.font(); font.setBold(true); font.setPixelSize(19); p.setFont(font); p.drawText(image.rect(), Qt::AlignCenter, localized(app,"name").left(1)); }
        icon->setPixmap(image); h->addWidget(icon);
        auto* column = new QVBoxLayout(); column->setSpacing(2);
        auto* name = new QLabel(localized(app, "name"), card); name->setObjectName("appName"); column->addWidget(name);
        auto* description = new QLabel(localized(app, "description"), card); description->setObjectName("appDescription"); description->setWordWrap(true); column->addWidget(description);
        if (app.value("source").toString("offline") != "offline") {
            auto* later = new QLabel(app.value("source").toString() == "link" ? text("Wird nach der Installation als Starter angelegt und öffnet die Anleitung im Browser.", "Created as a launcher after setup; it opens the guide in your browser.") : app.value("source").toString() == "webapp" ? text("Wird nach der Installation als Web-App angelegt und öffnet die Webseite.", "Created as a web app after setup; it opens the website.")
                                                                              : text("Wird nach der Installation geladen, sobald du online bist.", "Installed after setup, once you are online."), card);
            later->setWordWrap(true); later->setObjectName("deferredNote"); column->addWidget(later);
        }
        if (app.value("required").toBool()) { auto* required = new QLabel(text("In der Grundausstattung enthalten", "Included in the essentials"), card); required->setObjectName("includedLabel"); column->addWidget(required); }
        h->addLayout(column, 1);
        auto* box = new QCheckBox(card); box->setObjectName("app-" + id); box->setChecked(m_selected.contains(id)); box->setEnabled(!app.value("required").toBool());
        box->setAccessibleName(localized(app, "name")); box->setAccessibleDescription(localized(app, "description")); m_boxes.insert(id, box); h->addWidget(box, 0, Qt::AlignVCenter);
        m_cards.append(card);
        connect(box,&QCheckBox::toggled,this,[this,id,card](bool checked) { if (m_updating) return; if (checked) m_selected.insert(id); else m_selected.remove(id); card->setProperty("selected",checked); card->style()->unpolish(card); card->style()->polish(card); QSignalBlocker block(m_profiles); m_profiles->setCurrentIndex(m_profiles->findData("custom")); notify(); });
    }
    m_scroll->setWidget(content); outer->addWidget(m_scroll,1);
    m_count = new QLabel(page); m_count->setObjectName("countText"); m_count->setWordWrap(true);
    auto* shell = new QComboBox(page);
    shell->setObjectName("userShell");
    shell->addItem(text("Systemstandard", "System default"), QString());
    for (const auto& name : {"bash", "fish", "zsh"})
        shell->addItem(QString::fromUtf8(name), QStringLiteral("/usr/bin/") + name);
    shell->setCurrentIndex(shell->findData(m_shell));
    shell->setToolTip(text("Bestimmt die Shell für neue Terminals. Programme und persönliche Dateien bleiben gleich.", "Selects the shell for new terminals. Apps and personal files stay the same."));
    connect(shell, qOverload<int>(&QComboBox::activated), this, [this, shell](int index) {
        m_shell = shell->itemData(index).toString(); notify();
    });
    auto* importButton = new QPushButton(text("Profil laden", "Load profile"), page); importButton->setObjectName("importProfile");
    auto* exportButton = new QPushButton(text("Profil speichern", "Save profile"), page); exportButton->setObjectName("exportProfile");
    auto* bottomRow = new QHBoxLayout; bottomRow->setSpacing(10);
    bottomRow->addWidget(m_count, 1); bottomRow->addWidget(new QLabel(text("Terminal-Shell", "Terminal shell"), page)); bottomRow->addWidget(shell); bottomRow->addWidget(importButton); bottomRow->addWidget(exportButton);
    outer->addLayout(bottomRow);
    root->addWidget(page, 1);
    connect(m_profiles,qOverload<int>(&QComboBox::activated),this,[this](int index){ applyProfile(m_profiles->itemData(index).toString()); });
    connect(m_search,&QLineEdit::textChanged,this,[this]{ filter(); });
    connect(importButton,&QPushButton::clicked,this,[this] { const QString path = QFileDialog::getOpenFileName(this,text("Softwareprofil laden","Load software profile"),QString(),"WinDoesNot (*.json)",nullptr,QFileDialog::DontUseNativeDialog); if (path.isEmpty()) return; QString error; if (!importProfile(path,&error)) QMessageBox::warning(this,text("Profil nicht geladen","Profile not loaded"),error); });
    connect(exportButton,&QPushButton::clicked,this,[this] { const QString path = QFileDialog::getSaveFileName(this,text("Softwareprofil speichern","Save software profile"),"windoesnot-apps.json","WinDoesNot (*.json)",nullptr,QFileDialog::DontUseNativeDialog); if (path.isEmpty()) return; QString error; if (!exportProfile(path,&error)) QMessageBox::warning(this,text("Profil nicht gespeichert","Profile not saved"),error); });
    m_updating = false; filter(); updateCount();
}
// A click anywhere on an app row toggles its checkbox.
bool AppSelectionWidget::eventFilter(QObject* watched, QEvent* event) {
    if (event->type() == QEvent::MouseButtonRelease && watched->property("appCard").toBool()) {
        if (auto* box = m_boxes.value(watched->property("appId").toString())) if (box->isEnabled()) box->toggle();
        return true;
    }
    return QWidget::eventFilter(watched, event);
}
void AppSelectionWidget::setDarkMode(bool value) { if(m_dark != value) { m_dark = value; updateStyle(); } }
void AppSelectionWidget::updateStyle() {
    // Colours of the Store (store/src/ui/mod.rs ThemePalette), so installer and Store look the same.
    const QString page = m_dark ? "#202020" : "#f2f2f2", sidebar = m_dark ? "#171717" : "#e6e6e6", navSelected = m_dark ? "#2a2a2a" : "#c8c8c8";
    const QString card = m_dark ? "#141414" : "#f5f5f5", border = m_dark ? "#3a3a3a" : "#d0d0d0", hover = m_dark ? "#1e1e1e" : "#e6e6e6";
    const QString text = m_dark ? "#eeeeee" : "#202020", dim = m_dark ? "#888888" : "#666666", control = m_dark ? "#141414" : "#ffffff";
    const QString check = QDir(QFileInfo(m_catalogPath).absolutePath()).filePath("../branding/check.svg");
    QString css = QStringLiteral(
        "QWidget#windoesnotApps, QWidget#appsPage, QWidget#appsGrid, QScrollArea { background:@PAGE@; color:@TEXT@; }"
        "QWidget#appsSidebar { background:@SIDEBAR@; }"
        "QLabel { color:@TEXT@; background:transparent; }"
        "QLabel#appsBrand { font-size:20px; font-weight:700; padding:0 4px; }"
        "QPushButton#navEntry { background:transparent; border:0; border-radius:6px; }"
        "QPushButton#navEntry:hover { background:@HOVER@; }"
        "QPushButton#navEntry:checked { background:@NAVSEL@; }"
        "QLabel#navText { font-size:14px; }"
        "QFrame#navBar { background:transparent; border:0; border-radius:2px; }"
        "QFrame#navBar[active=\"true\"] { background:#fe6f2d; }"
        "QLabel#pageTitle { font-size:24px; font-weight:700; padding-bottom:4px; }"
        "QFrame#divider { background:@BORDER@; border:0; }"
        "QLabel#helpText, QLabel#countText { color:@DIM@; }"
        "QLabel#appName { font-size:14px; font-weight:700; }"
        "QLabel#appDescription, QLabel#deferredNote, QLabel#includedLabel { color:@DIM@; font-size:12px; }"
        "QLabel#groupHeading { font-size:16px; font-weight:700; padding:10px 2px 2px 2px; }"
        "QLineEdit, QComboBox { background:@CONTROL@; color:@TEXT@; border:1px solid @BORDER@; border-radius:6px; padding:7px; min-height:20px; }"
        "QPushButton { background:@CONTROL@; color:@TEXT@; border:1px solid @BORDER@; border-radius:6px; padding:8px 12px; }"
        "QPushButton:hover { border-color:#fe6f2d; }"
        "QComboBox QAbstractItemView { background:@CONTROL@; color:@TEXT@; border:1px solid @BORDER@; selection-background-color:#fe6f2d; selection-color:white; }"
        "QFrame[appCard=\"true\"] { background:@CARD@; border:1px solid @BORDER@; border-radius:10px; }"
        "QFrame[appCard=\"true\"]:hover { background:@HOVER@; }"
        "QFrame[appCard=\"true\"][selected=\"true\"] { border-color:#fe6f2d; }"
        "QCheckBox { background:transparent; spacing:0; }"
        "QCheckBox::indicator { width:18px; height:18px; border:1px solid @BORDER@; border-radius:4px; background:@CONTROL@; }"
        "QCheckBox::indicator:checked { background:#fe6f2d; border-color:#fe6f2d; image:url(@CHECK@); }"
        "QAbstractScrollArea::corner { background:@PAGE@; }");
    css.replace("@PAGE@", page).replace("@SIDEBAR@", sidebar).replace("@NAVSEL@", navSelected).replace("@CARD@", card).replace("@BORDER@", border)
       .replace("@HOVER@", hover).replace("@TEXT@", text).replace("@DIM@", dim).replace("@CONTROL@", control).replace("@CHECK@", check);
    setStyleSheet(css);
}
void AppSelectionWidget::filter() {
    while (auto* item = m_list->takeAt(0)) delete item;
    for (auto* heading : m_headings) delete heading;
    m_headings.clear();
    const QString search = m_search->text().trimmed().toCaseFolded();
    const auto apps = m_catalog.value("apps").toArray();
    QSet<int> shownCards;
    QString title = text("Welche Programme möchtest du nutzen?", "Which apps would you like to use?");
    for (const auto& categoryItem : m_catalog.value("categories").toArray()) {
        const auto categoryObject = categoryItem.toObject(); const QString categoryId = categoryObject.value("id").toString();
        if (!m_category.isEmpty() && categoryId != m_category) continue;
        if (!m_category.isEmpty()) title = localized(categoryObject, "name");
        QList<int> matches;
        for (int i = 0; i < apps.size(); ++i) { const auto app = apps[i].toObject();
            if (app.value("category").toString() == categoryId && (search.isEmpty() || (localized(app, "name") + " " + localized(app, "description")).toCaseFolded().contains(search))) matches << i; }
        if (matches.isEmpty()) continue;
        if (m_category.isEmpty()) {
            auto* heading = new QLabel(QStringLiteral("%1 (%2)").arg(localized(categoryObject, "name")).arg(matches.size()), m_list->parentWidget());
            heading->setObjectName("groupHeading"); m_headings.append(heading); m_list->addWidget(heading);
        }
        for (int i : matches) { m_list->addWidget(m_cards[i]); m_cards[i]->setVisible(true); shownCards.insert(i); }
    }
    for (int i = 0; i < m_cards.size(); ++i) if (!shownCards.contains(i)) m_cards[i]->setVisible(false);
    m_list->addStretch(1);
    if (m_title) m_title->setText(title);
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
