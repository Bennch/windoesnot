#!/usr/bin/env python3
"""Load the real QML with fixture status; never call a host privileged helper."""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-backup-ui-') as temp:
 base=Path(temp); profile=base/'profile'; (profile/'settings').mkdir(parents=True); (profile/'widgets').mkdir()
 shutil.copytree(source/'i18n',profile/'i18n')
 page=(source/'settings/BackupsCategory.qml').read_text()
 # Disable only the startup probe. Status/actions below are fixture-driven.
 page=page.replace('running: true\n        command: ["sh",', 'running: false\n        command: ["sh",')
 (profile/'settings/BackupsCategory.qml').write_text(page)
 shutil.copy2(source/'widgets/AuthenticationCard.qml',profile/'widgets')
 (profile/'img/Win11-dark/actions/32').mkdir(parents=True)
 shutil.copy2(source/'img/Win11-dark/actions/32/system-lock-screen.svg',profile/'img/Win11-dark/actions/32')
 (profile/'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import "settings"
import "widgets"
ShellRoot {
 Window {
  id: testWindow
  visible: true; width: 900; height: 900
  QtObject { id: preferences; property bool darkMode: true; property string uiLanguage: "de"; property string accentColor: "#fe6f2d"; property int borderRadius: 10; property bool fileDialogOpen: false }
  QtObject { id: flow; property bool isResponseRequired: true; property string actionId: "org.windoesnot.snapshots.create"; property string message: "Snapshot"; property string inputPrompt: "Password:"; property bool responseVisible: false; property var identities: []; property var selectedIdentity: null; property string supplementaryMessage: ""; property bool supplementaryIsError: false; function submit(value) {} }
  BackupsCategory { id: page; width: 650; settingsMenu: preferences }
  AuthenticationCard { id: auth; width: 440; flow: flow; settingsMenu: preferences }
  function find(o, name) { if (o.objectName === name) return o; for (let c of (o.children || [])) { let result=find(c,name); if(result) return result } return null }
  function check(ok, message) { if (!ok) throw new Error(message) }
  Timer {
   running: true; interval: 200
   onTriggered: {
    try {
     testWindow.check(page.pointKind({description:"WinDoesNot installation"}) === "installedPoint", "install label")
     testWindow.check(page.pointKind({description:"manual-quickshell"}) === "manualPoint", "manual label")
     testWindow.check(page.pointKind({description:"pacman -Syu",type:"pre"}) === "beforeUpdate", "update label")
     testWindow.check(page.pointKind({description:"pacman -Syu",type:"post"}) === "afterUpdate", "post label")
     testWindow.check(page.pointKind({description:"other",type:"pre"}) === "beforeChange", "do not invent update")
     testWindow.check(page.pointKind({cleanup:"timeline"}) === "automaticPoint", "automatic label")
     testWindow.check(page.pointKind({description:"unknown"}) === "otherPoint", "do not invent manual author")
     testWindow.check(page.pointKind({description:"tree",type:"post",packageChange:true}) === "afterUpdate", "post package list label")
     page.acceptStatus({ready:true,live:false,snapshots:[{id:"1",date:"2026-10-23T12:00:00",description:"WinDoesNot installation"}],schedule:{daily:"5",hourly:"0",weekly:"0",monthly:"0"},timeline:true,timerActive:true},true)
     testWindow.check(page.pointName("installedPoint", "") === "Nach der Installation", "German label")
     const response = testWindow.find(auth,"authenticationResponse")
     testWindow.check(response.placeholderText === "Passwort eingeben", "German password")
     const instructions = testWindow.find(page,"snapshotBootInstructions")
     page.bootInfo={loader:"grub",configured:true}; page.packageSnapshots=true; page.numberLimit="20"; page.importantLimit="5"
     testWindow.check(instructions.text.indexOf("WinDoesNot snapshots") >= 0, "GRUB guidance")
     page.bootInfo={loader:"systemd-boot",configured:false}
     testWindow.check(instructions.text.indexOf("nicht direkt") >= 0, "honest systemd-boot limit")
     page.bootInfo={loader:"refind",configured:true}
     testWindow.check(instructions.text.indexOf("Kopie") >= 0, "rEFInd writable copy")
     page.deleteCandidateId="1"; page.deleteCandidateImportant=true; page.confirmDeleteVisible=true
     preferences.uiLanguage="en"; preferences.darkMode=false
     testWindow.check(page.pointName("installedPoint", "") === "After installation", "English label")
     testWindow.check(response.placeholderText === "Enter password", "English password")
     page.confirmDeleteVisible=false
     page.acceptStatus({ready:false,live:false,snapshotBoot:true},false)
     testWindow.check(!page.backupsReady && page.snapshotBoot, "snapshot preview cannot mutate")
     console.log("BACKUP_UI_PASS")
    } catch(e) { console.error("BACKUP_UI_FAIL",e) }
    Qt.quit()
   }
  }
 }
}''')
 runtime=base/'runtime';runtime.mkdir(mode=0o700)
 env={**os.environ,'HOME':str(base),'XDG_CONFIG_HOME':str(base/'config'),'XDG_CACHE_HOME':str(base/'cache'),'XDG_RUNTIME_DIR':str(runtime),'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','QT_QPA_PLATFORMTHEME':'basic','DISPLAY':'','WAYLAND_DISPLAY':'','DBUS_SESSION_BUS_ADDRESS':''}
 result=subprocess.run(['quickshell','--no-color','-p',str(profile/'shell.qml')],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
 print(result.stdout)
 assert 'BACKUP_UI_PASS' in result.stdout
 for error in ['ReferenceError','TypeError','Failed to load configuration','Cannot assign','Binding loop','BACKUP_UI_FAIL']:
  assert error not in result.stdout, error
print('PASS: restore-point labels, conservative unknown labels, delete popup, DE/EN, dark/light, translated password prompt')
