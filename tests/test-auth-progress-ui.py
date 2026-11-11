#!/usr/bin/env python3
"""Exercise the existing authentication card through password/progress/result states."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
with tempfile.TemporaryDirectory(prefix='wdn-auth-progress-') as d:
    home = Path(d);profile=home/'profile';(profile/'widgets').mkdir(parents=True)
    shutil.copy2(SOURCE/'widgets/AuthenticationCard.qml',profile/'widgets/AuthenticationCard.qml')
    shutil.copytree(SOURCE/'i18n',profile/'i18n')
    icons=profile/'img/Win11-dark/actions/32';icons.mkdir(parents=True)
    shutil.copy2(SOURCE/'img/Win11-dark/actions/32/system-lock-screen.svg',icons/'system-lock-screen.svg')
    (profile/'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import "widgets"
ShellRoot {
 Window {
  id: test; visible:true; width:500; height:700
  property bool submitted:false
  QtObject { id: preferences; property bool darkMode:true; property string uiLanguage:"de"; property color accentColor:"#fe6f2d"; property int borderRadius:10 }
  QtObject {
   id: request
   property bool isResponseRequired:true
   property bool responseVisible:false
   property string inputPrompt:"Password:"
   property string actionId:"org.windoesnot.system.locale-set"
   property string message:"Set up system language"
   property var identities:[]
   property var selectedIdentity:null
   property string supplementaryMessage:""
   property bool supplementaryIsError:false
   function submit(value) { test.submitted=value === "fixture" }
   function cancelAuthenticationRequest() {}
  }
  AuthenticationCard { id: card; x:20; y:20; width:460; height:implicitHeight; settingsMenu:preferences; flow:request; taskActive:true; taskBusy:true; taskTitle:"Systemsprache einrichten"; taskText:"Bitte bestätigen" }
  function check(ok,message) { if(!ok) throw new Error(message) }
  function find(o,name) { if(o.objectName===name) return o;for(let c of o.children || []) {let r=find(c,name);if(r)return r}return null }
  Timer { interval:200;running:true;onTriggered:{
   try {
    const field=test.find(card,"authenticationResponse")
    const progress=test.find(card,"authenticationTaskProgress")
    test.check(field.visible && field.enabled,"same password card accepts authorization")
    field.text="fixture";card.submit()
    test.check(test.submitted && field.text === "","password submitted and cleared")
    card.flow=null;card.taskStep=2;card.taskTotal=3;card.taskText="Sprachdaten werden erstellt"
    test.check(!field.visible && progress.indeterminate,"progress replaces password after authorization")
    card.taskBusy=false
    test.check(!progress.indeterminate && progress.value===1,"success finishes progress")
    card.taskError=true;card.taskDetail="fixture failure"
    test.check(progress.value===0,"failure is not shown as successful completion")
    preferences.darkMode=false;preferences.uiLanguage="en"
    test.check(card.language === "en" && card.dark === false,"shared theme and language")
    console.log("AUTH_PROGRESS_PASS")
   } catch(e) {console.error("AUTH_PROGRESS_FAIL",e)}
   Qt.quit()
  }}
 }
}''')
    runtime=home/'runtime';runtime.mkdir(mode=0o700)
    env={**os.environ,'HOME':d,'XDG_CONFIG_HOME':d+'/config','XDG_RUNTIME_DIR':str(runtime),'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','QT_QPA_PLATFORMTHEME':'basic','DISPLAY':'','WAYLAND_DISPLAY':'','DBUS_SESSION_BUS_ADDRESS':''}
    result=subprocess.run(['qs','--no-color','-p',str(profile/'shell.qml')],env=env,capture_output=True,text=True,timeout=10)
    output=result.stdout+result.stderr
    assert 'AUTH_PROGRESS_PASS' in output,output
    for error in ['ReferenceError','TypeError','Failed to load configuration','Cannot assign','AUTH_PROGRESS_FAIL']:
        assert error not in output,output
print('PASS: shared authentication card, password clearing, progress, success/error and DE/EN themes')
