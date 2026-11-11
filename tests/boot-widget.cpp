#include "BootSelectionWidget.h"
#include <QApplication>
#include <QRadioButton>
#include <QLabel>
#include <QToolButton>
#include <QComboBox>
#include <cassert>
int main(int argc,char** argv) {
    QApplication app(argc,argv);
    BootSelectionWidget autoDetected(true);
    autoDetected.setDetectedBootloader("systemd-boot");
    assert(autoDetected.selected() == "systemd-boot");
    assert(autoDetected.findChild<QLabel*>("bootloader-installed"));
    autoDetected.setDetectedBootloader({});
    assert(autoDetected.selected() == "grub");
    assert(!autoDetected.findChild<QLabel*>("bootloader-installed"));
    autoDetected.setDetectedBootloader("systemd-boot");
    autoDetected.findChild<QRadioButton*>("bootloader-grub")->click();
    autoDetected.setDetectedBootloader("refind");
    assert(autoDetected.selected() == "grub");
    BootSelectionWidget legacy(false);
    legacy.setDetectedBootloader("refind");
    assert(legacy.selected() == "grub");
    assert(!legacy.findChild<QLabel*>("bootloader-installed"));
    BootSelectionWidget efi(true);
    assert(efi.selected()=="grub");
    for(const auto* id:{"grub","refind","systemd-boot","limine"}) assert(efi.findChild<QRadioButton*>(QString("bootloader-")+id));
    efi.findChild<QRadioButton*>("bootloader-refind")->click();
    assert(efi.selected()=="refind");efi.setGerman(true);assert(efi.selected()=="refind");
    using State=BootSelectionWidget::DetectionState;
    efi.setDetectedSystems({"/dev/nvme0n1p1@/EFI/Microsoft/Boot/bootmgfw.efi:Windows Boot Manager:Windows:efi",
                            "/dev/nvme1n1p2:Ubuntu 26.10:Ubuntu:linux",
                            "/dev/sda2:Arch Linux:Arch:linux"},State::Available);
    efi.setFirmwareEntries("BootCurrent: 0003\nBootOrder: 0001,0002,0003\n"
                          "Boot0001* ubuntu\tHD(1,GPT,example)/File(\\EFI\\ubuntu\\shimx64.efi)\n"
                          "Boot0002* Windows Boot Manager HD(1,GPT,example)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)\n"
                          "Boot0003* UEFI USB\tUSB(0,0)\n",State::Available);
    assert(efi.findChild<QLabel*>("boot-detection")->text().contains("Ubuntu 26.10"));
    auto* detected=efi.findChild<QLabel*>("boot-detection-details");
    assert(detected->textFormat()==Qt::PlainText);
    assert(detected->text().contains("Windows Boot Manager — /dev/nvme0n1p1"));
    assert(detected->text().contains("Ubuntu 26.10 — /dev/nvme1n1p2"));
    assert(detected->text().contains("Arch Linux — /dev/sda2"));
    assert(detected->text().contains("ubuntu — \\EFI\\ubuntu\\shimx64.efi (zuerst"));
    assert(detected->text().contains("Windows Boot Manager — \\EFI\\Microsoft\\Boot\\bootmgfw.efi"));
    auto* help=efi.findChild<QToolButton*>("help-partition");
    auto* detail=efi.findChild<QLabel*>("help-text-partition");
    assert(detail->isHidden());help->click();assert(!detail->isHidden());
    assert(efi.selected()=="refind");help->click();assert(detail->isHidden());
    efi.setGerman(false);
    assert(efi.selected()=="refind");
    detected=efi.findChild<QLabel*>("boot-detection-details");
    assert(detected->text().contains("Ubuntu 26.10 — /dev/nvme1n1p2"));
    assert(detected->text().contains("first in the default order"));
    efi.setDetectedSystems({},State::Available);
    assert(detected->text().contains("does not prove the drives are empty"));
    efi.setFirmwareEntries({},State::Unavailable);
    assert(detected->text().contains("Cannot be read"));
    efi.setReuseOptions(QJsonArray{QJsonObject{{"id","test-existing"},{"label","Ubuntu"},{"kind","grub"}}});
    auto* reuse=efi.findChild<QRadioButton*>("bootloader-existing");
    assert(reuse && reuse->isEnabled());reuse->click();
    assert(efi.selected()=="grub");assert(efi.reusePlan().value("id")=="test-existing");
    efi.setGerman(true);assert(efi.reusePlan().value("id")=="test-existing");
    efi.setReuseOptions({});assert(!efi.selectionValid());assert(efi.reusePlan().isEmpty());
    efi.findChild<QRadioButton*>("bootloader-refind")->click();
    assert(efi.selectionValid());assert(efi.reusePlan().isEmpty());assert(efi.selected()=="refind");
    efi.setReuseOptions({});assert(efi.reusePlan().isEmpty());
    assert(!efi.findChild<QRadioButton*>("bootloader-existing")->isEnabled());
    BootSelectionWidget bios(false);
    assert(!bios.findChild<QRadioButton*>("bootloader-refind"));
    assert(!bios.findChild<QRadioButton*>("bootloader-systemd-boot"));
    bios.findChild<QRadioButton*>("bootloader-limine")->click();assert(bios.selected()=="limine");
    bios.setDetectedSystems({"/dev/sda2:Debian GNU/Linux:Debian:linux"},State::Available);
    assert(bios.findChild<QLabel*>("boot-detection")->text().contains("Debian GNU/Linux"));
    assert(bios.findChild<QLabel*>("boot-detection")->text().contains("cannot reliably identify an existing BIOS boot menu"));
    return 0;
}
