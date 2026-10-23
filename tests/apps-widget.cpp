// SPDX-License-Identifier: GPL-3.0-or-later
#include "AppSelectionWidget.h"
#include <QApplication>
#include <QCheckBox>
#include <QComboBox>
#include <QLineEdit>
#include <QFile>
#include <QTemporaryDir>
#include <QTimer>
#include <iostream>
int main(int argc,char** argv) {
    QApplication app(argc,argv);
    if(argc<2)return 1;
    AppSelectionWidget widget(QString::fromLocal8Bit(argv[1]));
    widget.resize(760,620);widget.show();app.processEvents();
    auto require=[](bool condition,const char* message){if(!condition){std::cerr<<message<<"\n";std::exit(2);}};
    require(widget.selectedIds().contains("libreoffice"),"recommended selection missing");
    widget.applyProfile("minimal");require(widget.selectedIds()==QStringList{"firefox"},"minimal profile wrong");
    widget.applyProfile("gaming");require(widget.selectedIds().contains("steam"),"gaming profile wrong");
    auto* search=widget.findChild<QLineEdit*>("appSearch");search->setText("gimp");app.processEvents();
    require(widget.findChild<QCheckBox*>("app-gimp")->isVisible(),"matching search hidden");
    require(!widget.findChild<QCheckBox*>("app-steam")->isVisible(),"nonmatching search visible");
    require(widget.selectedIds().contains("steam"),"filter erased selection");search->clear();
    require(!widget.findChild<QCheckBox*>("app-firefox")->isEnabled(),"required app selectable");
    QString error;const auto before=widget.selectedIds();require(!widget.setSelection({"arbitrary-package"},&error),"unknown selection accepted");require(widget.selectedIds()==before,"invalid import changed selection");
    QTemporaryDir temp;QString path=temp.filePath("my profile.json");require(widget.exportProfile(path,&error),"export failed");widget.applyProfile("minimal");require(widget.importProfile(path,&error),"import failed");require(widget.selectedIds()==before,"roundtrip lost selection");
    QFile bad(temp.filePath("bad.json"));require(bad.open(QIODevice::WriteOnly),"cannot write invalid fixture");bad.write("{\"schema_version\":1,\"selected\":[\"firefox\"],\"command\":\"ignored\"}");bad.close();require(!widget.importProfile(bad.fileName(),&error),"unknown profile field accepted");
    widget.setGerman(true);widget.applyProfile("recommended");app.processEvents();
    const auto selectedBeforeTheme = widget.selectedIds();
    widget.setDarkMode(false); app.processEvents();
    require(widget.styleSheet().contains("#f3f3f3"),"light appearance missing");
    require(widget.selectedIds()==selectedBeforeTheme,"appearance switch erased selection");
    if(argc>2)widget.grab().save(QString::fromLocal8Bit(argv[2])+".light.png");
    widget.setDarkMode(true); app.processEvents();
    require(widget.styleSheet().contains("#202024"),"dark appearance missing");

    if(argc>2)widget.grab().save(QString::fromLocal8Bit(argv[2]));
    std::cout<<"PASS: recommended/minimal/gaming profiles, filter preserves selection, required apps, invalid imports, portable profile roundtrip, German rendering\n";
    return 0;
}
