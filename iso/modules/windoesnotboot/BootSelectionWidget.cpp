// SPDX-License-Identifier: GPL-3.0-or-later
#include "BootSelectionWidget.h"
#include <QButtonGroup>
#include <QComboBox>
#include <QLabel>
#include <QRadioButton>
#include <QRegularExpression>
#include <QScrollArea>
#include <QToolButton>
#include <QVBoxLayout>

namespace {
struct Choice { const char* id; const char* name; const char* de; const char* en; bool efi; };
const Choice choices[] = {
    {"grub", "GRUB", "Empfohlen, wenn du unsicher bist. Kann erkannte Windows- und Linux-Systeme im gemeinsamen Startmenü anbieten. Unterstützt UEFI und ältere BIOS-Rechner.", "Recommended if you are unsure. Can offer detected Windows and Linux systems in a shared boot menu. Supports UEFI and older BIOS computers.", false},
    {"refind", "rEFInd", "Grafisches Startmenü mit automatischer Suche nach Betriebssystemen. Benötigt UEFI.", "Graphical boot menu that automatically finds operating systems. Requires UEFI.", true},
    {"systemd-boot", "systemd-boot", "Schlichtes Startmenü für UEFI-Rechner. Erkennt Windows auf derselben EFI-Systempartition. Für erfahrene Nutzer mit passender Partitionierung.", "A simple boot menu for UEFI computers. Detects Windows on the same EFI system partition. For experienced users with a suitable partition layout.", true},
    {"limine", "Limine", "Alternative für Nutzer, die Limine bereits kennen. Unterstützt UEFI und BIOS. Die Einbindung anderer Systeme hängt von seiner Konfiguration ab.", "An alternative for users already familiar with Limine. Supports UEFI and BIOS. Showing other operating systems requires a suitable configuration.", false},
};
}
BootSelectionWidget::BootSelectionWidget(bool efi, QWidget* parent) : QWidget(parent), m_efi(efi) { build(); }
void BootSelectionWidget::setGerman(bool german) { if(m_german != german) { m_german = german; build(); } }
void BootSelectionWidget::setDetectedSystems(const QStringList& lines,DetectionState state) {
    m_systems=lines;m_systemsState=state;updateDetectionText();
}
void BootSelectionWidget::setFirmwareEntries(const QString& output,DetectionState state) {
    m_firmwareOutput=output;m_firmwareState=state;updateDetectionText();
}
QJsonObject BootSelectionWidget::reusePlan() const {
    return m_reuseMode && m_reuseIndex>=0 && m_reuseIndex<m_reuseOptions.size()
        ?m_reuseOptions[m_reuseIndex].toObject():QJsonObject();
}
void BootSelectionWidget::setDetectedBootloader(const QString& loader) {
    const QString valid = m_efi && QStringList{"grub", "systemd-boot", "refind", "limine"}.contains(loader) ? loader : QString();
    if (valid == m_detectedLoader) return;
    m_detectedLoader = valid;
    if (!m_userSelected) m_selected = m_detectedLoader.isEmpty() ? QStringLiteral("grub") : m_detectedLoader;
    build();
    if (selectionChanged) selectionChanged();
}
void BootSelectionWidget::setReuseOptions(const QJsonArray& options) {
    const auto previous=reusePlan().value("id").toString();
    const bool requested=m_reuseMode;
    m_reuseOptions=options;m_reuseIndex=0;
    bool found=false;
    for(int index=0;index<options.size();++index)
        if(!previous.isEmpty() && options[index].toObject().value("id").toString()==previous) {
            m_reuseIndex=index;found=true;break;
        }
    // A disappearing menu must never silently turn reuse into replacement.
    if(requested && !found) m_reuseIndex=-1;
    build();
    if(selectionChanged) selectionChanged();
}
void BootSelectionWidget::updateDetectionText() {
    if(!m_detection) return;
    auto text=[this](const char* de,const char* en) { return QString::fromUtf8(m_german?de:en); };
    QStringList systems;
    QStringList systemNames;
    for(const auto& line:m_systems) {
        const auto fields=line.split(':');
        if(fields.size()<3 || !fields[0].startsWith("/dev/")) continue;
        const auto name=fields[1].simplified().isEmpty()?fields[2].simplified():fields[1].simplified();
        systems.append(name+QStringLiteral(" — ")+fields[0].section('@',0,0));
        systemNames.append(name);
    }
    systems.removeDuplicates();
    QString result=text("Vorhandene Betriebssysteme: ","Existing operating systems: ");
    if(m_systemsState==DetectionState::Pending) result+=text("Calamares sucht noch …","Calamares is still scanning …");
    else if(m_systemsState==DetectionState::Unavailable) result+=text("Erkennung nicht verfügbar. Prüfe die Datenträgerauswahl im nächsten Schritt.","Detection unavailable. Check the drive selection in the next step.");
    else if(systems.isEmpty()) result+=text("Keine erkannt. Das beweist nicht, dass die Datenträger leer sind; verschlüsselte Systeme können verborgen bleiben.","None detected. This does not prove the drives are empty; encrypted systems may remain hidden.");
    else result+=QStringLiteral("\n• ")+systems.join(QStringLiteral("\n• "));
    systemNames.removeDuplicates();
    QString summary=m_systemsState==DetectionState::Available && !systemNames.isEmpty()
        ?text("Erkannte Systeme: ","Detected systems: ")+systemNames.join(QStringLiteral(", ")):result;

    if(m_efi) {
        result+=text("\n\nRegistrierte UEFI-Starteinträge: ","\n\nRegistered UEFI boot entries: ");
        if(m_firmwareState==DetectionState::Pending) {
            result+=text("Werden gelesen …","Reading …");
            summary+=text("\nVorhandene UEFI-Startmenüs werden geprüft …","\nChecking existing UEFI boot entries …");
        } else if(m_firmwareState==DetectionState::Unavailable) {
            result+=text("Nicht lesbar. Das ist kein Nachweis, dass kein Startmenü vorhanden ist.","Cannot be read. This does not prove that no boot menu exists.");
            summary+=text("\nDas bisherige Startmenü konnte nicht bestimmt werden.","\nThe existing boot menu could not be determined.");
        }
        else {
            QStringList entries;
            QString firstName;
            const QRegularExpression entry(QStringLiteral("^Boot([0-9A-Fa-f]{4})\\*?\\s+(.+)$"));
            const QRegularExpression devicePath(QStringLiteral("\\s+(?=(?:HD|PciRoot|Pci|VenHw|VenMsg|USB|BBS|FvFile|FvVol)\\()"));
            const QRegularExpression file(QStringLiteral("File\\(([^)]*)\\)"),QRegularExpression::CaseInsensitiveOption);
            QString first;
            for(const auto& line:m_firmwareOutput.split('\n'))
                if(line.startsWith("BootOrder:")) first=line.mid(10).trimmed().section(',',0,0);
            for(const auto& line:m_firmwareOutput.split('\n')) {
                const auto match=entry.match(line);
                if(!match.hasMatch()) continue;
                auto label=match.captured(2).section('\t',0,0);
                const auto path=devicePath.match(label);
                if(path.hasMatch()) label=label.left(path.capturedStart());
                label=label.trimmed();
                if(match.captured(1).compare(first,Qt::CaseInsensitive)==0) firstName=label;
                const auto loader=file.match(match.captured(2));
                if(loader.hasMatch()) label+=QStringLiteral(" — ")+loader.captured(1);
                if(match.captured(1).compare(first,Qt::CaseInsensitive)==0)
                    label+=text(" (zuerst in der Standardreihenfolge)"," (first in the default order)");
                entries.append(label);
            }
            entries.removeDuplicates();
            result+=entries.isEmpty()?text("Keine gemeldet.","None reported."):QStringLiteral("\n• ")+entries.join(QStringLiteral("\n• "));
            result+=text("\nDiese Firmware-Einträge können auch den Installationsstick oder veraltete Einträge enthalten. Sie bestätigen nicht, dass ein System startfähig ist.","\nThese firmware entries may include the installation USB or stale entries. They do not confirm that a system is bootable.");
            summary+=firstName.isEmpty()?text("\nKein eindeutiges Standard-Startmenü gemeldet.","\nNo unambiguous default boot menu was reported.")
                :text("\nErster UEFI-Eintrag der Standardreihenfolge: ","\nFirst UEFI entry in the default order: ")+firstName;
        }
    } else {
        const auto note=text("\n\nDieser Installationsstart verwendet BIOS. Ein vorhandenes BIOS-Startmenü lässt sich aus der Betriebssystemliste nicht zuverlässig bestimmen.","\n\nThis installation session uses BIOS. The operating system list alone cannot reliably identify an existing BIOS boot menu.");
        result+=note;summary+=note;
    }
    m_detection->setText(summary);
    if(m_detectionDetails) m_detectionDetails->setText(result);
}
void BootSelectionWidget::build() {
    m_detection=nullptr;m_detectionDetails=nullptr;
    if(layout()) {
        QLayoutItem* item;
        while((item=layout()->takeAt(0))) { if(item->widget()) delete item->widget(); delete item; }
        delete layout();
    }
    auto text=[this](const char* de,const char* en) { return QString::fromUtf8(m_german?de:en); };
    auto* outer = new QVBoxLayout(this); outer->setContentsMargins(12,8,12,8); outer->setSpacing(12);
    auto* title=new QLabel(text("Wie soll dein Computer starten?", "How should your computer start?"),this);
    auto font=title->font();font.setPointSize(17);font.setBold(true);title->setFont(font);title->setWordWrap(true);outer->addWidget(title);
    auto* help=new QLabel(text("Der Bootloader ist das Startmenü vor dem Betriebssystem. Lass GRUB ausgewählt, wenn du unsicher bist. Alle Optionen sind auch offline verfügbar.\n\nWindows oder Linux behalten? Wähle im nächsten Schritt bei der Speicheraufteilung „Parallel dazu installieren“, sofern angeboten. Die Wahl des Startmenüs allein legt das noch nicht fest.", "The bootloader is the menu shown before the operating system starts. Keep GRUB selected if you are unsure. All options are also available offline.\n\nWant to keep Windows or Linux? In the next step, choose “Install alongside” when offered. Choosing a boot menu alone does not decide how your disk is used."),this);
    help->setWordWrap(true);outer->addWidget(help);
    auto* scroll=new QScrollArea(this);scroll->setWidgetResizable(true);outer->addWidget(scroll,1);
    auto* content=new QWidget(scroll);auto* list=new QVBoxLayout(content);list->setSpacing(12);
    m_detection=new QLabel(content);
    m_detection->setObjectName("boot-detection");
    m_detection->setTextFormat(Qt::PlainText);
    m_detection->setWordWrap(true);
    m_detection->setTextInteractionFlags(Qt::TextSelectableByMouse);
    list->addWidget(m_detection);
    auto* detectionButton=new QToolButton(content);
    detectionButton->setObjectName("help-detected");
    detectionButton->setText(text("Details zur Erkennung", "Detection details"));
    detectionButton->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
    detectionButton->setArrowType(Qt::RightArrow);
    detectionButton->setCheckable(true);
    list->addWidget(detectionButton);
    m_detectionDetails=new QLabel(content);
    m_detectionDetails->setObjectName("boot-detection-details");
    m_detectionDetails->setTextFormat(Qt::PlainText);
    m_detectionDetails->setWordWrap(true);
    m_detectionDetails->setTextInteractionFlags(Qt::TextSelectableByMouse);
    m_detectionDetails->hide();list->addWidget(m_detectionDetails);
    connect(detectionButton,&QToolButton::toggled,m_detectionDetails,&QWidget::setVisible);
    connect(detectionButton,&QToolButton::toggled,detectionButton,[detectionButton](bool expanded) {
        detectionButton->setArrowType(expanded?Qt::DownArrow:Qt::RightArrow);
    });
    updateDetectionText();
    auto* group=new QButtonGroup(content);
    for(const auto& choice:choices) {
        if(choice.efi && !m_efi) continue;
        auto* card=new QWidget(content);auto* column=new QVBoxLayout(card);column->setContentsMargins(12,10,12,10);
        auto* button=new QRadioButton(QString::fromUtf8(choice.name),card);button->setObjectName(QStringLiteral("bootloader-")+choice.id);button->setChecked(m_selected==choice.id && !m_reuseMode);group->addButton(button);column->addWidget(button);
        if (m_detectedLoader == choice.id) {
            auto* badge = new QLabel(text("Bereits installiert", "Already installed"), card);
            badge->setObjectName("bootloader-installed"); column->addWidget(badge);
        }
        auto* description=new QLabel(text(choice.de,choice.en),card);description->setWordWrap(true);column->addWidget(description);
        connect(button,&QRadioButton::toggled,this,[this,id=QString::fromUtf8(choice.id)](bool checked) { if(checked) { m_userSelected=true;m_selected=id;m_reuseMode=false;if(selectionChanged) selectionChanged(); } });
        list->addWidget(card);
        if(QString::fromUtf8(choice.id)=="grub" && m_efi) {
            auto* existing=new QWidget(content);auto* options=new QVBoxLayout(existing);options->setContentsMargins(12,10,12,10);
            auto* reuse=new QRadioButton(text("Vorhandenes Linux-Startmenü weiterverwenden", "Reuse an existing Linux boot menu"),existing);
            reuse->setObjectName("bootloader-existing");reuse->setEnabled(!m_reuseOptions.isEmpty());reuse->setChecked(m_reuseMode);
            group->addButton(reuse);options->addWidget(reuse);
            auto* explanation=new QLabel(m_reuseOptions.isEmpty()
                ?text("Noch kein unterstütztes Menü bestätigt. Die Prüfung benötigt ein vorhandenes UEFI-Menü mit kompatibler Konfiguration und freien Ablagepfaden. Windows erhält mit der GRUB-Auswahl ein gemeinsames Menü.", "No supported menu confirmed yet. The check requires an existing UEFI menu with a compatible configuration and unused file paths. For Windows, choosing GRUB creates a shared menu.")
                :text("Fügt WinDoesNot als Eintrag hinzu und behält das bisherige Hauptmenü sowie die UEFI-Startreihenfolge. Im nächsten Schritt „Parallel dazu installieren“ wählen und die bestehende EFI-Systempartition erhalten. WinDoesNot verwendet für seine Kernel und Wiederherstellungspunkte ein eigenes GRUB-Untermenü.", "Adds a WinDoesNot entry while keeping the existing main menu and UEFI boot order. Choose “Install alongside” in the next step and preserve the existing EFI system partition. WinDoesNot uses its own GRUB submenu for kernels and restore points."),existing);
            explanation->setWordWrap(true);options->addWidget(explanation);
            if(!m_reuseOptions.isEmpty()) {
                auto* menus=new QComboBox(existing);menus->setObjectName("existing-boot-menu");
                menus->setAccessibleName(text("Vorhandenes Startmenü", "Existing boot menu"));
                for(const auto& item:m_reuseOptions) { const auto menu=item.toObject();menus->addItem(menu.value("label").toString()+" ("+menu.value("kind").toString()+")"); }
                menus->setCurrentIndex(m_reuseIndex);options->addWidget(menus);
                connect(menus,qOverload<int>(&QComboBox::currentIndexChanged),this,[this](int index) { m_reuseIndex=index;if(selectionChanged) selectionChanged(); });
            }
            connect(reuse,&QRadioButton::toggled,this,[this](bool checked) { if(checked) { m_userSelected=true;m_reuseMode=true;m_selected="grub";if(selectionChanged) selectionChanged(); } });
            list->addWidget(existing);
        }
    }
    auto addHelp=[&](const char* id,const QString& heading,const QString& body) {
        auto* button=new QToolButton(content);
        button->setObjectName(QStringLiteral("help-")+id);
        button->setText(heading);
        button->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
        button->setArrowType(Qt::RightArrow);
        button->setCheckable(true);
        button->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Preferred);
        list->addWidget(button);
        auto* detail=new QLabel(body,content);
        detail->setObjectName(QStringLiteral("help-text-")+id);
        detail->setTextFormat(Qt::PlainText);
        detail->setWordWrap(true);
        detail->setContentsMargins(12,0,12,8);
        detail->hide();
        list->addWidget(detail);
        connect(button,&QToolButton::toggled,detail,&QWidget::setVisible);
        connect(button,&QToolButton::toggled,button,[button](bool expanded) {
            button->setArrowType(expanded?Qt::DownArrow:Qt::RightArrow);
        });
    };
    addHelp("partition",text("Windows oder Linux behalten?", "Keep Windows or Linux?"),
        text("„Parallel dazu installieren“: Calamares verkleinert eine geeignete vorhandene Partition und erstellt daneben Platz für WinDoesNot. Du stellst die Aufteilung mit einem Größenregler ein.\n\n„Festplatte löschen“: Alle Partitionen und Daten auf dem ausgewählten Datenträger werden gelöscht.\n\n„Eine Partition ersetzen“: Der Inhalt der ausgewählten Partition wird gelöscht und durch WinDoesNot ersetzt.\n\n„Manuelle Partitionierung“: Du legst selbst fest, welche Bereiche verwendet oder formatiert werden. Das ist für erfahrene Nutzer gedacht.\n\nFehlt eine passende Option, prüfe zuerst den gewählten Datenträger und den freien Platz. „Parallel dazu installieren“ wird nur angeboten, wenn sich genügend Speicherplatz für WinDoesNot freimachen lässt. Ist dein vorhandenes System nicht erkannt oder keine Partition verkleinerbar, fahre nicht mit einer Löschoption fort, wenn du es behalten möchtest. Sichere wichtige Daten vor Änderungen an Partitionen. Bei BitLocker halte den Wiederherstellungsschlüssel bereit; eine verschlüsselte Windows-Partition lässt sich hier nicht einfach verkleinern.",
             "“Install alongside”: Calamares shrinks a suitable existing partition and creates space for WinDoesNot beside it. You choose the split using a size slider.\n\n“Erase disk”: All partitions and data on the selected drive are deleted.\n\n“Replace a partition”: The contents of the selected partition are deleted and replaced with WinDoesNot.\n\n“Manual partitioning”: You decide which areas to use or format. This is intended for experienced users.\n\nIf a suitable option is missing, first check the selected drive and its free space. “Install alongside” is only offered when enough space can be made available for WinDoesNot. If your existing system is not detected or no partition can be shrunk, do not proceed with an erase option when you want to keep it. Back up important data before changing partitions. If BitLocker is enabled, keep the recovery key available; an encrypted Windows partition cannot simply be shrunk here."));
    addHelp("existing",text("Ein vorhandenes Startmenü behalten?", "Keep an existing boot menu?"),
        text("„Vorhandenes Linux-Startmenü weiterverwenden“ erscheint für bestätigte, unterstützte UEFI-Konfigurationen mit GRUB, systemd-boot oder rEFInd. Das vorhandene Menü erhält einen WinDoesNot-Eintrag. Seine Startdateien und die UEFI-Startreihenfolge werden beibehalten; geänderte Menüdateien werden vorher gesichert.\n\nDie Weiterverwendung unterstützt das bestätigte UEFI-Standardmenü und ein unverschlüsseltes WinDoesNot-Ziel. Sie setzt „Parallel dazu installieren“ voraus. Nicht jede GRUB-Konfiguration ist automatisch ergänzbar, etwa mit separater Bootpartition oder fehlendem custom.cfg-Verweis. Verschlüsselte oder unbekannte Konfigurationen können unbestimmt bleiben.\n\nBei einer bisherigen Windows-Installation ist GRUB die empfohlene Auswahl: Es bietet Windows und WinDoesNot gemeinsam an. Das Windows-Bootmenü selbst wird nicht um einen Linux-Eintrag erweitert.\n\nBei normaler Bootloader-Installation kann sich die Startreihenfolge ändern. Vorhandene gleichnamige Linux-Startdateien werden vor dem Kopieren erkannt; dann wird eine getrennte EFI-Systempartition benötigt.",
             "“Reuse an existing Linux boot menu” is available for verified, supported UEFI configurations using GRUB, systemd-boot or rEFInd. A WinDoesNot entry is added to the existing menu. Its boot files and UEFI boot order are retained; menu files are backed up before being edited.\n\nReuse supports the verified default UEFI menu and an unencrypted WinDoesNot target. It requires “Install alongside”. Not every GRUB configuration can be extended automatically, for example with a separate boot partition or a missing custom.cfg include. Encrypted or unknown configurations may remain undetermined.\n\nFor an existing Windows installation, GRUB is recommended: it offers Windows and WinDoesNot together. The Windows boot menu itself is not extended with a Linux entry.\n\nNormal bootloader installation may change the boot order. Existing Linux boot files with overlapping names are detected before copying; a separate EFI system partition is needed in that case."));
    addHelp("terms",text("Datenträger, Dateisystem und EFI?", "Drive, file system and EFI?"),
        text("Ein Datenträger ist zum Beispiel eine SSD. Partitionen teilen ihn in Bereiche auf. Prüfe Modell und Größe, damit du den richtigen Datenträger auswählst.\n\nDas Dateisystem bestimmt, wie Dateien gespeichert werden. Btrfs ermöglicht WinDoesNot-Wiederherstellungspunkte, etwa vor Paketänderungen. Diese Wiederherstellungspunkte ersetzen keine Sicherung persönlicher Dateien.\n\nUEFI ist die Startumgebung moderner Rechner. Die EFI-Systempartition ist ein kleiner FAT-Bereich mit Startdateien, oft auch für Windows. Formatiere eine vorhandene EFI-Systempartition bei manueller Partitionierung nicht, wenn du andere Systeme behalten möchtest. Unser Installer verwendet sie unter /boot; dort muss genug Platz für die Linux-Startdateien vorhanden sein.",
             "A drive is a device such as an SSD. Partitions divide it into separate areas. Check the model and size to select the correct drive.\n\nThe file system determines how files are stored. Btrfs enables WinDoesNot system restore points, for example before package changes. These restore points do not replace backups of personal files.\n\nUEFI is the startup environment on modern computers. The EFI system partition is a small FAT area containing boot files, often including those for Windows. When partitioning manually, do not format an existing EFI system partition if you want to keep other systems. Our installer uses it at /boot; it needs enough room for the Linux boot files."));
    addHelp("next",text("Was passiert in den weiteren Schritten?", "What happens in the remaining steps?"),
        text("Tastaturlayout: Prüfe Sonderzeichen, bevor du ein Passwort festlegst. Region und Zeitzone bestimmen unter anderem Uhrzeit und Datumsformat.\n\nProgramme: Die empfohlene Auswahl ist ein guter Start. Weitere Programme kannst du nach der Installation im Store hinzufügen.\n\nBenutzer: Lege deinen Namen und dein Anmeldepasswort fest. Der Rechnername ist der Name des Geräts im Netzwerk.\n\nZusammenfassung: Prüfe besonders den ausgewählten Datenträger und alle geplanten Lösch- und Formatierungsaktionen. Erst nach deiner Bestätigung startet die eigentliche Installation.\n\nNach dem Abschluss: Starte neu und entferne den Installationsstick, wenn du dazu aufgefordert wirst, damit der Rechner von der installierten SSD startet.",
             "Keyboard layout: Check special characters before choosing a password. Your region and time zone determine the clock and date format.\n\nApps: The recommended selection is a useful starting point. You can add more apps from the Store after installation.\n\nUser: Choose your name and login password. The computer name identifies this device on the network.\n\nSummary: Check the selected drive and every planned deletion or formatting action carefully. Installation only starts after you confirm.\n\nWhen finished: Restart and remove the installation USB when prompted so the computer starts from the installed SSD."));
    list->addStretch();scroll->setWidget(content);
}
