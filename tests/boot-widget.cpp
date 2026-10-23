#include "BootSelectionWidget.h"
#include <QApplication>
#include <QRadioButton>
#include <cassert>
int main(int argc,char** argv) {
    QApplication app(argc,argv);
    BootSelectionWidget efi(true);
    assert(efi.selected()=="grub");
    for(const auto* id:{"grub","refind","systemd-boot","limine"}) assert(efi.findChild<QRadioButton*>(QString("bootloader-")+id));
    efi.findChild<QRadioButton*>("bootloader-refind")->click();
    assert(efi.selected()=="refind");efi.setGerman(true);assert(efi.selected()=="refind");
    BootSelectionWidget bios(false);
    assert(!bios.findChild<QRadioButton*>("bootloader-refind"));
    assert(!bios.findChild<QRadioButton*>("bootloader-systemd-boot"));
    bios.findChild<QRadioButton*>("bootloader-limine")->click();assert(bios.selected()=="limine");
    return 0;
}
