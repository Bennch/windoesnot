#!/usr/bin/env python3
"""Compile the actual settings pages with isolated fixture state; no host actions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'desktop/config/quickshell/default'
fixture={'live':False,'setup':None,'cpuLevel':'v3','repositories':['cachyos-v3'],
         'drivers':'intel','nvidia':False,'release':'7.2.7-test','running':'linux-cachyos',
         'bootloader':'grub','kernels':[
             {'name':'linux-cachyos','installed':'7.2.7','available':'7.2.7','running':True,'removable':False,'selectable':True},
             {'name':'linux-cachyos-bore','installed':'','available':'7.2.7','running':False,'removable':False,'selectable':True}],
         'scx':{'supported':True,'installed':True,'schedulers':['scx_lavd','scx_bpfland'],
                'defaultScheduler':'scx_bpfland','defaultMode':'PowerSave','enabled':True,'active':True,'current':'scx_bpfland','state':'enabled'}}
with tempfile.TemporaryDirectory(prefix='wdn-system-ui-') as temp:
    base=Path(temp); profile=base/'profile'; (profile/'settings').mkdir(parents=True)
    shutil.copytree(SOURCE/'i18n',profile/'i18n')
    shutil.copy2(SOURCE/'settings/KernelCategory.qml',profile/'settings')
    for name in ('SystemToolsButton','SystemToolsChoice','SystemToolsToggle','SystemToolsConfirm'):
        shutil.copy2(SOURCE/('settings/'+name+'.qml'),profile/'settings')
    shutil.copy2(SOURCE/'settings/MaintenanceCategory.qml',profile/'settings')
    (profile/'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import QtQuick.Controls
import Quickshell
ShellRoot {
 Window {
  id: testWindow
  visible: true; width: 900; height: 1100
  QtObject { id: preferences; property bool darkMode: true; property string uiLanguage: "de"; property string accentColor: "#fe6f2d"; property bool fileDialogOpen: false; property int borderRadius: 10 }
  property var page: kernelLoader.item
  Loader { id: kernelLoader; width: 650; Component.onCompleted: setSource("settings/KernelCategory.qml", {settingsMenu:preferences,autoLoad:false}) }
  property var maintenance: maintenanceLoader.item
  Loader { id: maintenanceLoader; width: 650; visible: false; Component.onCompleted: setSource("settings/MaintenanceCategory.qml", {settingsMenu:preferences,autoLoad:false}) }
  function check(ok,message) { if(!ok) throw new Error(message) }
  function find(o,predicate) { if(predicate(o)) return o; for(let c of (o.children || [])) { let r=find(c,predicate); if(r) return r } return null }
  Timer { id: finish; interval: 100; onTriggered: {
   try { const page=kernelLoader.item; const maintenance=maintenanceLoader.item; testWindow.check(testWindow.find(page,o => o.objectName === "systemToolsMode").currentText === "PowerSave", "mode survives model settling"); testWindow.check(page.height > 600, "scrollable kernel content"); testWindow.check(maintenance.height > 800, "scrollable maintenance content"); console.log("SYSTEM_TOOLS_UI_PASS") }
   catch(e) { console.error("SYSTEM_TOOLS_UI_FAIL",e) }
   Qt.quit()
  } }
  Timer { running: true; interval: 200; onTriggered: {
   try {
    const page=kernelLoader.item; const maintenance=maintenanceLoader.item
    page.acceptStatus(FIXTURE)
    testWindow.check(page.ready, "status applied")
    page.resultKey="kernel.statusFailed"; page.resultDetail="pacman: missing database"
    testWindow.check(page.resultText.indexOf("pacman") < 0, "friendly error summary")
    const details = testWindow.find(page, o => o.text === page.resultDetail)
    testWindow.check(details && !details.visible, "technical error hidden initially")
    page.detailsExpanded=true
    testWindow.check(details.visible, "technical error can be expanded")
    page.detailsExpanded=false; page.resultKey=""; page.resultDetail=""
    const offline = JSON.parse(JSON.stringify(FIXTURE)); offline.catalogAvailable=false
    offline.kernels=offline.kernels.filter(k => !!k.installed)
    page.acceptStatus(offline)
    testWindow.check(page.ready && page.state.kernels.length === 1, "offline status keeps installed kernel")
    testWindow.check(!!testWindow.find(page, o => o.text === page.tr("kernel.catalogMissing") && o.visible), "offline guidance visible")
    page.acceptStatus(FIXTURE)
    testWindow.check(page.tr("header.kernel") === "Kernel und Leistung", "DE")
    const modeChoice = testWindow.find(page,o => o.objectName === "systemToolsMode")
    testWindow.check(modeChoice.currentText === "PowerSave", "selected mode")
    const remove = testWindow.find(page, o => o.text === "Entfernen")
    testWindow.check(remove && !remove.enabled, "running kernel protected in UI")
    page.requestAction("kernel-install", {kernel:"linux-cachyos-bore"}, "test")
    testWindow.check(page.pendingAction === "kernel-install", "confirmation before mutation")
    page.busy = true
    page.requestAction("kernel-remove", {kernel:"linux-cachyos"}, "test")
    testWindow.check(page.pendingAction === "kernel-install", "busy blocks second action")
    page.busy = false
    preferences.uiLanguage="en"; preferences.darkMode=false
    testWindow.check(page.tr("header.kernel") === "Kernel and performance", "EN")
    testWindow.check(modeChoice.currentText === "PowerSave" && modeChoice.displayText === "Power saving", "language switch preserves scheduler mode")
    const live = JSON.parse(JSON.stringify(FIXTURE)); live.live=true; live.scx.supported=false
    page.acceptStatus(live)
    page.requestAction("scx-stop", {}, "test")
    testWindow.check(page.pendingAction === "kernel-install", "live blocks actions")
    maintenance.acceptStatus({live:false, setup:{drivers:"pending"}, tools:{paccache:true,chwd:true,"pacman-key":true,"cachyos-rate-mirrors":true,curl:true},
        cacheBytes:104857600,lockExists:true,processesVisible:true,packageProcesses:[],mirrorsRanked:false,orphans:["example","second"],failedServices:[]})
    testWindow.check(maintenance.ready, "maintenance status")
    testWindow.check(maintenance.sizeText(104857600) === "100.0 MiB", "cache size")
    maintenance.showOrphans=true; maintenance.showFailed=true
    maintenance.requestAction("orphans-remove",{packages:maintenance.state.orphans.slice()},maintenance.state.orphans.join("\\n"))
    testWindow.check(maintenance.pendingArgs.packages.length === 2, "reviewed package list")
    testWindow.check(maintenance.pendingDescription.indexOf("second") >= 0, "confirmation lists packages")
    const locked = JSON.parse(JSON.stringify(maintenance.state)); locked.live=true
    maintenance.acceptStatus(locked)
    maintenance.requestAction("lock-remove",{},"test")
    testWindow.check(maintenance.pendingAction === "orphans-remove", "maintenance live guard")
    preferences.uiLanguage="de"; preferences.darkMode=true
    testWindow.check(maintenance.tr("header.maintenance") === "Wartung", "maintenance DE")
    maintenance.resultKey="systemTools.cancelled"
    testWindow.check(maintenance.resultText.indexOf("Abgebrochen") === 0, "translated result DE")
    preferences.uiLanguage="en"; preferences.darkMode=false
    testWindow.check(maintenance.tr("header.maintenance") === "Maintenance", "maintenance EN")
    testWindow.check(maintenance.resultText.indexOf("Cancelled") === 0, "translated result EN")
    finish.start()
   } catch(e) { console.error("SYSTEM_TOOLS_UI_FAIL",e); Qt.quit() }
  } }
 }
}'''.replace('FIXTURE',json.dumps(fixture)))
    runtime=base/'runtime';runtime.mkdir(mode=0o700)
    env={**os.environ,'HOME':str(base),'XDG_CONFIG_HOME':str(base/'config'),'XDG_CACHE_HOME':str(base/'cache'),
         'XDG_RUNTIME_DIR':str(runtime),'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software',
         'QT_QPA_PLATFORMTHEME':'basic','DISPLAY':'','WAYLAND_DISPLAY':'','DBUS_SESSION_BUS_ADDRESS':''}
    result=subprocess.run(['quickshell','--no-color','-p',str(profile/'shell.qml')],env=env,text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
    print(result.stdout)
    assert 'SYSTEM_TOOLS_UI_PASS' in result.stdout
    for error in ['ReferenceError','TypeError','Failed to load configuration','Cannot assign','Binding loop','SYSTEM_TOOLS_UI_FAIL']:
        assert error not in result.stdout,error
print('PASS: kernel page, DE/EN, dark/light, confirmation, running-kernel/live/busy guards, maintenance previews and pending drivers')
