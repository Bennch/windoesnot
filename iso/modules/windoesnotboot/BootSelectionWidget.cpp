// SPDX-License-Identifier: GPL-3.0-or-later
#include "BootSelectionWidget.h"
#include <QButtonGroup>
#include <QLabel>
#include <QRadioButton>
#include <QScrollArea>
#include <QVBoxLayout>

namespace {
struct Choice { const char* id; const char* name; const char* de; const char* en; bool efi; };
const Choice choices[] = {
    {"grub", "GRUB", "Bewährte Standardauswahl für WinDoesNot. Unterstützt UEFI und ältere BIOS-Rechner.", "Tested default for WinDoesNot. Supports UEFI and older BIOS computers.", false},
    {"refind", "rEFInd", "Grafisches Startmenü mit automatischer Suche nach Betriebssystemen. Benötigt UEFI.", "Graphical boot menu that automatically finds operating systems. Requires UEFI.", true},
    {"systemd-boot", "systemd-boot", "Einfaches, schlankes Startmenü. Benötigt UEFI.", "A simple, lightweight boot menu. Requires UEFI.", true},
    {"limine", "Limine", "Moderner Bootloader für UEFI und BIOS. Wird auch von CachyOS angeboten.", "Modern bootloader for UEFI and BIOS, also offered by CachyOS.", false},
};
}
BootSelectionWidget::BootSelectionWidget(bool efi, QWidget* parent) : QWidget(parent), m_efi(efi) { build(); }
void BootSelectionWidget::setGerman(bool german) { if(m_german != german) { m_german = german; build(); } }
void BootSelectionWidget::build() {
    if(layout()) {
        QLayoutItem* item;
        while((item=layout()->takeAt(0))) { if(item->widget()) delete item->widget(); delete item; }
        delete layout();
    }
    auto text=[this](const char* de,const char* en) { return QString::fromUtf8(m_german?de:en); };
    auto* outer = new QVBoxLayout(this); outer->setContentsMargins(12,8,12,8); outer->setSpacing(12);
    auto* title=new QLabel(text("Wie soll dein Computer starten?", "How should your computer start?"),this);
    auto font=title->font();font.setPointSize(17);font.setBold(true);title->setFont(font);title->setWordWrap(true);outer->addWidget(title);
    auto* help=new QLabel(text("Der Bootloader startet dein installiertes System. Wenn du unsicher bist, lass GRUB ausgewählt. Alle Optionen sind auch offline verfügbar.", "The bootloader starts your installed system. If unsure, keep GRUB selected. All options are also available offline."),this);
    help->setWordWrap(true);outer->addWidget(help);
    auto* scroll=new QScrollArea(this);scroll->setWidgetResizable(true);outer->addWidget(scroll,1);
    auto* content=new QWidget(scroll);auto* list=new QVBoxLayout(content);list->setSpacing(12);
    auto* group=new QButtonGroup(content);
    for(const auto& choice:choices) {
        if(choice.efi && !m_efi) continue;
        auto* card=new QWidget(content);auto* column=new QVBoxLayout(card);column->setContentsMargins(12,10,12,10);
        auto* button=new QRadioButton(QString::fromUtf8(choice.name),card);button->setObjectName(QStringLiteral("bootloader-")+choice.id);button->setChecked(m_selected==choice.id);group->addButton(button);column->addWidget(button);
        auto* description=new QLabel(text(choice.de,choice.en),card);description->setWordWrap(true);column->addWidget(description);
        connect(button,&QRadioButton::toggled,this,[this,id=QString::fromUtf8(choice.id)](bool checked) { if(checked) m_selected=id; });
        list->addWidget(card);
    }
    list->addStretch();scroll->setWidget(content);
}
