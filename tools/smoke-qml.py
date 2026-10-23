#!/usr/bin/env python3
"""Compile the full shell with a throwaway HOME and no access to session IPC."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='wdn-qml-') as temporary:
    home=Path(temporary);runtime=home/'run';runtime.mkdir(mode=0o700)
    env={**os.environ,'HOME':str(home),'XDG_CONFIG_HOME':str(home/'.config'),'XDG_CACHE_HOME':str(home/'.cache'),'XDG_DATA_HOME':str(home/'.local/share'),'XDG_RUNTIME_DIR':str(runtime),'QT_QPA_PLATFORM':'offscreen','DBUS_SESSION_BUS_ADDRESS':'unix:path='+str(runtime/'no-session-bus'),'HYPRLAND_INSTANCE_SIGNATURE':'windoesnot-isolated-smoke','WINDOESNOT_SOURCE':str(ROOT),'PATH':str(home/'.local/bin')+':/usr/local/bin:/usr/bin'}
    subprocess.run([ROOT/'desktop/bin/windoesnot-initialize'],env=env,check=True)
    module=home/'.config/quickshell/default/widgets/terminalmodule/LocalTerminal'
    shutil.copytree(ROOT/'build/components/LocalTerminal',module,dirs_exist_ok=True)
    with (ROOT/'checks/qml-runtime-smoke.log').open('w') as log:
        process=subprocess.Popen(['quickshell','--no-color','-p',str(home/'.config/quickshell/default')],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
    output=(ROOT/'checks/qml-runtime-smoke.log').read_text()
    print('\n'.join(output.splitlines()[:35]))
    if 'Failed to load configuration' in output:raise SystemExit(1)
    if 'Configuration Loaded' not in output:raise SystemExit('No successful QML load marker; inspect log')
    print('PASS: shell QML loads; offscreen test cannot validate desktop rendering or interaction')
