#!/usr/bin/env python3
"""Real store preference CLI + real QML page, isolated from host settings/packages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / 'store/target/release/windoesnot-store'
with tempfile.TemporaryDirectory(prefix='wdn-aur-') as tmp:
    base = Path(tmp)
    env = {**os.environ, 'HOME': tmp, 'XDG_CONFIG_HOME': str(base/'config'),
           'XDG_CACHE_HOME': str(base/'cache'), 'XDG_RUNTIME_DIR': str(base/'run'),
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': 'basic', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path='+tmp+'/no-bus'}
    env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
    (base/'run').mkdir(mode=0o700)
    def cli(*args):
        return subprocess.run([str(BINARY), *args], env=env, text=True, capture_output=True, timeout=10)
    assert cli('--set-aur', 'nonsense').returncode == 2
    assert cli('--set-aur').returncode == 2
    assert json.loads(cli('--aur-status-json').stdout)['aur_enabled'] is False
    assert cli('--set-aur', 'true').returncode == 0
    settings = base/'config/windoesnot-store/settings.json'
    settings.write_text(json.dumps({'aur_enabled':True,'theme':'Dark','personal_extra':{'keep':42}}))
    assert cli('--disable-aur').returncode == 0
    assert json.loads(settings.read_text())['personal_extra'] == {'keep':42}
    assert json.loads(settings.read_text())['theme'] == 'Dark'
    settings.write_text('invalid json')
    assert cli('--enable-aur').returncode != 0
    assert settings.read_text() == 'invalid json'
    settings.write_text(json.dumps({'aur_enabled':False,'theme':'Dark','personal_extra':{'keep':42}}))

    # QML uses the actual CLI to save/read; only network/update queries are mocked.
    bindir = base/'bin'; bindir.mkdir()
    wrapper = bindir/'windoesnot-store'
    wrapper.write_text('''#!/usr/bin/python3
import json, os, subprocess, sys
from pathlib import Path
real = '''+repr(str(BINARY))+'''
args = sys.argv[1:]
if args and args[0] == '--status-json':
    current = json.loads(subprocess.check_output([real, '--aur-status-json']))
    current.update({'checked':1700000000,'updates':([{'name':'sample-bin','old':'1','new':'2','source':'aur'}] if current['aur_enabled'] else []),'news':[],'news_unavailable':False,'reboot':False,'relogin':False,'aur_error':None})
    print(json.dumps(current))
elif args and args[0] == '--set-aur' and Path(os.environ['HOME']+'/fail-save').exists():
    print('simulated write failure', file=sys.stderr); sys.exit(1)
else:
    os.execv(real, [real]+args)
''')
    wrapper.chmod(0o755)
    env['PATH'] = str(bindir)+':'+os.environ['PATH']
    profile = base/'profile'; (profile/'settings').mkdir(parents=True)
    shutil.copy2(ROOT/'desktop/config/quickshell/default/settings/UpdateCategory.qml', profile/'settings/UpdateCategory.qml')
    shutil.copytree(ROOT/'desktop/config/quickshell/default/i18n',profile/'i18n')
    (profile/'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io
ShellRoot {
    Window {
        visible: true; width: 900; height: 900
        QtObject { id: preferences; property bool darkMode: true; property string uiLanguage: "de"; property string accentColor: "#fe6f2d"; property int borderRadius: 10; property bool visible: true }
        Loader { id: page; width: 650; Component.onCompleted: setSource("settings/UpdateCategory.qml", {settingsMenu: preferences}) }
        Process { id: externalToggle; command: ["windoesnot-store", "--disable-aur"] }
        Process { id: failSave; command: ["touch", "'''+str(base/'fail-save')+'''"] }
        Timer {
            running: true; repeat: true; interval: 100
            property int stage: 0
            property int ticks: 0
            onTriggered: {
                if (++ticks > 160) { console.error("AUR_UI_TIMEOUT stage="+stage); Qt.quit(); return }
                if (!page.item || page.item.checking || page.item.settingAur || !page.item.status) return
                if (stage === 0) {
                    if (page.item.aurEnabled) { console.error("BAD_DEFAULT"); Qt.quit(); return }
                    page.item.setAur(true); stage=1
                } else if (stage === 1 && page.item.aurEnabled && page.item.updateCount === 1) {
                    preferences.darkMode=false; preferences.uiLanguage="en"
                    externalToggle.running=true; stage=2
                } else if (stage === 2 && !page.item.aurEnabled && page.item.updateCount === 0) {
                    failSave.running=true; stage=3
                } else if (stage === 3 && !failSave.running) {
                    page.item.setAur(true); stage=4
                } else if (stage === 4 && page.item.actionError.length > 0) {
                    if (page.item.aurEnabled) { console.error("FAILED_SAVE_CHANGED_SWITCH"); Qt.quit(); return }
                    console.log("AUR_UPDATER_READY"); Qt.quit()
                }
            }
        }
    }
}
''')
    result = subprocess.run(['quickshell','--no-color','-p',str(profile/'shell.qml')],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=22)
    (ROOT/'checks/aur-updater-qml.log').write_text(result.stdout)
    assert 'AUR_UPDATER_READY' in result.stdout, result.stdout
    for error in ('ReferenceError','TypeError','Failed to load configuration','Cannot assign'):
        assert error not in result.stdout, result.stdout
    final=json.loads(settings.read_text())
    assert final['personal_extra']=={'keep':42} and final['theme']=='Dark' and final['aur_enabled'] is False
print('PASS: strict real CLI, preference preservation, real QML toggle, external sync, update refresh, failed-save recovery, DE/EN and light/dark')
