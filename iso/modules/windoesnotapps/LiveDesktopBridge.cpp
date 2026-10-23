// SPDX-License-Identifier: GPL-3.0-or-later
#include "LiveDesktopBridge.h"
#include <QApplication>
#include <QWidget>
#include <QEvent>
#include <QFile>
#include <QFileInfo>
#include <QLocale>
#include <QPalette>
#include <QProcess>
#include <QStyleFactory>
#include <QPixmap>
#include <QMetaObject>
#include <QAbstractItemView>
#include <QStyledItemDelegate>
#include <QPainter>
#include "GlobalStorage.h"
#include "JobQueue.h"
#include "ViewManager.h"

namespace {
const QString preferences = QStringLiteral("/home/liveuser/.config/quickshell/default/settings.txt");
class SidebarDelegate : public QStyledItemDelegate {
public:
    using QStyledItemDelegate::QStyledItemDelegate;
    void paint(QPainter* painter,const QStyleOptionViewItem& option,const QModelIndex& index) const override {
        const bool selected = index.row()==index.data(Calamares::ViewManager::ProgressTreeItemCurrentIndex).toInt();
        painter->save();
        painter->fillRect(option.rect,selected?QColor("#fe6f2d"):qApp->palette().color(QPalette::Window));
        painter->setPen(selected?QColor("#ffffff"):qApp->palette().color(QPalette::WindowText));
        auto font=qApp->font();font.setPointSize(font.pointSize()+3);painter->setFont(font);
        const auto text=painter->fontMetrics().elidedText(index.data().toString(),Qt::ElideRight,option.rect.width()-16);
        painter->drawText(option.rect.adjusted(8,0,-8,0),Qt::AlignCenter,text);painter->restore();
    }
    QSize sizeHint(const QStyleOptionViewItem& option,const QModelIndex&) const override {
        auto font=qApp->font();font.setPointSize(font.pointSize()+3);
        return QSize(option.rect.width(),QFontMetrics(font).height()+16);
    }
};
}
LiveDesktopBridge::LiveDesktopBridge(QObject* parent) : QObject(parent) {
    if (!QFileInfo::exists("/etc/windoesnot-image-build")) return;
    qApp->setStyle(QStyleFactory::create("Fusion"));
    m_settingsTimer.setSingleShot(true); m_settingsTimer.setInterval(100);
    m_languageTimer.setSingleShot(true); m_languageTimer.setInterval(150);
    connect(&m_settingsTimer,&QTimer::timeout,this,[this]{ applySettings(); });
    connect(&m_languageTimer,&QTimer::timeout,this,[this]{ synchronizeLanguage(); });
    connect(&m_watcher,&QFileSystemWatcher::fileChanged,this,[this]{ m_settingsTimer.start(); });
    connect(&m_watcher,&QFileSystemWatcher::directoryChanged,this,[this]{ m_settingsTimer.start(); });
    m_watcher.addPath(QFileInfo(preferences).absolutePath());
    applySettings();
    qApp->installEventFilter(this);
    m_languageTimer.start();
    // The keyboard step stores its choice when the page is left, before any password is typed.
    // Queued: GlobalStorage emits changed() while still holding its non-recursive mutex.
    if(auto* queue=Calamares::JobQueue::instance())
        connect(queue->globalStorage(),&Calamares::GlobalStorage::changed,this,[this]{ synchronizeKeyboard(); },Qt::QueuedConnection);
}
void LiveDesktopBridge::applySettings() {
    QFile file(preferences); bool dark = true;
    if(file.open(QIODevice::ReadOnly)) for(const auto& line:file.readAll().split('\n')) if(line.startsWith("darkMode=")) dark = line.mid(9).trimmed() != "false";
    if(!m_watcher.files().contains(preferences) && QFileInfo::exists(preferences)) m_watcher.addPath(preferences);
    if(m_ready && dark == m_dark) return;
    m_ready = true; m_dark = dark;
    QPalette palette;
    const QColor background(dark ? "#202024" : "#f3f3f3");
    const QColor foreground(dark ? "#eeeeee" : "#202024");
    const QColor base(dark ? "#29292e" : "#ffffff");
    for(auto group:{QPalette::Active,QPalette::Inactive,QPalette::Disabled}) {
        palette.setColor(group,QPalette::Window,background); palette.setColor(group,QPalette::WindowText,foreground);
        palette.setColor(group,QPalette::Base,base); palette.setColor(group,QPalette::AlternateBase,background);
        palette.setColor(group,QPalette::Text,foreground); palette.setColor(group,QPalette::Button,base);
        palette.setColor(group,QPalette::ButtonText,foreground); palette.setColor(group,QPalette::ToolTipBase,base);
        palette.setColor(group,QPalette::ToolTipText,foreground); palette.setColor(group,QPalette::Highlight,QColor("#fe6f2d"));
        palette.setColor(group,QPalette::HighlightedText,QColor("#ffffff"));
    }
    palette.setColor(QPalette::Disabled,QPalette::Text,QColor(dark?"#888888":"#777777"));
    qApp->setPalette(palette);
    QFile stylesheet(QStringLiteral("/usr/share/windoesnot/iso/branding/")+(dark?"dark.qss":"light.qss"));
    if(stylesheet.open(QIODevice::ReadOnly)) qApp->setStyleSheet(QString::fromUtf8(stylesheet.readAll()));
    updateWelcomeLogo();
    updateSidebar();
    if(appearanceChanged) appearanceChanged(dark);
}
bool LiveDesktopBridge::eventFilter(QObject* object,QEvent* event) {
    if(event->type()==QEvent::Show && object->objectName()=="welcomeLogo") updateWelcomeLogo();
    if(event->type()==QEvent::Show && object->objectName()=="sidebarMenuApp") updateSidebar();
    if(event->type()==QEvent::LanguageChange) m_languageTimer.start();
    return QObject::eventFilter(object,event);
}
void LiveDesktopBridge::synchronizeLanguage() {
    const QString language = QLocale().name();
    if(language == m_language) return;
    m_language = language;
    QProcess::startDetached("/usr/bin/python3", {"/usr/share/windoesnot/iso/live-language.py",language});
}
void LiveDesktopBridge::synchronizeKeyboard() {
    const auto* storage = Calamares::JobQueue::instance()->globalStorage();
    QString layout = storage->value("keyboardLayout").toString();
    const QString additional = storage->value("keyboardAdditionalLayout").toString();
    if(!additional.isEmpty()) layout += "," + additional;
    if(layout.isEmpty() || layout == m_keyboard) return;
    m_keyboard = layout;
    QProcess::startDetached("/usr/bin/python3", {"/usr/share/windoesnot/iso/live-language.py","--keyboard",layout});
}

void LiveDesktopBridge::updateWelcomeLogo() {
    const QPixmap image(QStringLiteral("/usr/share/windoesnot/branding/windoesnot-logo-")+(m_dark?"hell.png":"dunkel.png"));
    if(image.isNull()) return;
    for(auto* widget:qApp->allWidgets()) if(widget->objectName()=="welcomeLogo")
        QMetaObject::invokeMethod(widget,"setPixmap",Qt::DirectConnection,Q_ARG(QPixmap,image));
}

void LiveDesktopBridge::updateSidebar() {
    for(auto* widget:qApp->allWidgets()) if(widget->objectName()=="sidebarMenuApp") {
        auto* view=qobject_cast<QAbstractItemView*>(widget);
        if(view && !view->property("windoesnotDelegate").toBool()) {
            view->setItemDelegate(new SidebarDelegate(view));
            view->setProperty("windoesnotDelegate",true);
        }
        if(view) { view->setPalette(qApp->palette());view->viewport()->update(); }
    }
}
