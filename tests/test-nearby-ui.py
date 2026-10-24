#!/usr/bin/env python3
"""Compile real Nearby widgets and exercise tray/IPC without a network service."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/config/quickshell/default'
shell = (SOURCE / 'shell.qml').read_text()
tray = re.search(r'    function rebuildTrayModel\(\) \{.*?\n    \}', shell, re.S).group()
ipc = shell[shell.index('IpcHandler {\n    target: "windoesnot-nearby"'):shell.index('PanelWindow {\n    id: nearbyWindow')]
ipc = ipc.replace('IpcHandler {', 'IpcHandler { id: nearbyIpc', 1)
fixture = {'receiving': True, 'requestedReceiving': True, 'alias': 'Test PC', 'error': '',
           'devices': [{'id': 'other', 'alias': 'Other computer', 'protocol': 'https'}],
           'selected': ['space ü.txt'],
           'incoming': {'id': 'request', 'direction': 'receive', 'peer': '<b>Other</b>', 'files': ['hello.txt'],
                        'status': 'waiting', 'bytes': 0, 'total': 1024},
           'outgoing': None, 'history': [{'id': 'old', 'direction': 'send', 'peer': 'Other', 'files': ['earlier.txt'],
                                         'status': 'done', 'bytes': 5, 'total': 5, 'time': 1792850000}]}
with tempfile.TemporaryDirectory(prefix='wdn-nearby-ui-') as temp:
    base = Path(temp)
    profile = base / 'profile'
    (profile / 'widgets').mkdir(parents=True)
    (profile / 'settings').mkdir()
    shutil.copytree(SOURCE / 'i18n', profile / 'i18n')
    for name in ('NearbyService', 'NearbyPanel'):
        shutil.copy2(SOURCE / f'widgets/{name}.qml', profile / 'widgets')
    for name in ('SystemToolsButton', 'SystemToolsToggle'):
        shutil.copy2(SOURCE / f'settings/{name}.qml', profile / 'settings')
    (profile / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io
import "widgets"
ShellRoot {
 id: desktopShell
 property int opened: 0
 function openNearby() { opened++ }
 Window {
  id: testWindow; visible:true; width:400; height:580
  property int incomingCount: 0
  NearbyService { id:nearbyService; autoStart:false; onIncomingRequest: testWindow.incomingCount++ }
  NearbyPanel { id:panel; anchors.fill:parent; service:nearbyService }
  QtObject { id:settingsMenu; property string trayOrder:"audio,network,bluetooth"; property bool weatherEnabled:false; property string weatherLocation:"tray"; property bool showDockerTray:false; property bool showOllamaTray:false }
  ListModel { id:trayIconModel }
  QtObject { id:panelWindow; TRAY }
  INSERT_IPC
  function check(ok,message) { if(!ok) throw new Error(message) }
  function find(o,predicate) { if(predicate(o)) return o; for(let c of(o.children||[])) {let result=find(c,predicate); if(result)return result} return null }
  Timer { interval:200; running:true; onTriggered: {
   try {
    nearbyService.acceptState(FIXTURE)
    testWindow.check(testWindow.incomingCount===1,"incoming request opens panel once")
    nearbyService.acceptState(FIXTURE)
    testWindow.check(testWindow.incomingCount===1,"progress does not steal focus repeatedly")
    testWindow.check(panel.tr("nearby.title")==="In der Nähe teilen","German")
    const accept=testWindow.find(panel,o=>o.text==="Annehmen")
    testWindow.check(accept && accept.visible,"explicit approval offered")
    testWindow.check(testWindow.find(panel,o=>o.text==="Anfrage von <b>Other</b>").textFormat===Text.PlainText,"peer text is plain")
    panel.act("reject",{id:"request"})
    testWindow.check(nearbyService.pendingCommands[0].action==="reject","reject command routed")
    panel.uiLanguage="en"; panel.darkMode=false
    testWindow.check(panel.tr("nearby.title")==="Nearby sharing","English")
    testWindow.check(accept.text==="Accept","buttons follow language")
    panelWindow.rebuildTrayModel()
    let count=0; for(let i=0;i<trayIconModel.count;i++) if(trayIconModel.get(i).iconType==="nearby")count++
    testWindow.check(count===1 && settingsMenu.trayOrder==="audio,network,bluetooth","legacy tray order gets one icon without overwriting preferences")
    testWindow.check(nearbyIpc.share(JSON.stringify(["/tmp/space ü.txt"]))==="opened" && desktopShell.opened===1,"Nautilus IPC opens panel")
    testWindow.check(nearbyService.pendingCommands[1].files[0]==="/tmp/space ü.txt","file path passes as JSON")
    testWindow.check(nearbyIpc.share("{}")==="invalid" && nearbyIpc.share("[]")==="invalid","invalid IPC rejected")
    console.log("NEARBY_UI_PASS")
   } catch(e) {console.error("NEARBY_UI_FAIL",e)}
   Qt.quit()
  } }
 }
}'''.replace('TRAY', tray).replace('INSERT_IPC', ipc).replace('FIXTURE', json.dumps(fixture)))
    runtime = base / 'run'
    runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(base), 'XDG_CONFIG_HOME': str(base / 'config'),
           'XDG_CACHE_HOME': str(base / 'cache'), 'XDG_RUNTIME_DIR': str(runtime),
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': 'basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DBUS_SESSION_BUS_ADDRESS': ''}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(profile / 'shell.qml')], env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
    print(result.stdout)
    assert 'NEARBY_UI_PASS' in result.stdout
    for error in ('ReferenceError', 'TypeError', 'Failed to load configuration', 'Cannot assign', 'Binding loop', 'NEARBY_UI_FAIL'):
        assert error not in result.stdout, error
print('PASS: Nearby panel DE/EN, dark/light, approval, plain peer text, service routing, existing tray order and Nautilus IPC')
