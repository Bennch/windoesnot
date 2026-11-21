#!/usr/bin/env python3
"""windoesnot-bluetooth-default: choose/clear a default device, connect after login with retries, never pair or power on by itself."""
import os, subprocess, tempfile
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/bin/windoesnot-bluetooth-default'
MAC = '08:EB:ED:11:97:7A'
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    state = t / 'state'; state.mkdir()
    stub = t / 'bluetoothctl'
    stub.write_text(f'''#!/bin/sh
S={state}
case "$1" in
  show) echo "Controller 00:00:00:00:00:00"; echo "	Powered: $(cat $S/powered 2>/dev/null || echo yes)" ;;
  info) echo "Device $2"; echo "	Paired: $(cat $S/paired 2>/dev/null || echo yes)"; echo "	Connected: $(cat $S/connected 2>/dev/null || echo no)" ;;
  connect) n=$(cat $S/calls 2>/dev/null || echo 0); n=$((n+1)); echo $n > $S/calls; echo "$2" >> $S/connect-args
           if [ $n -ge $(cat $S/succeed-at 2>/dev/null || echo 1) ]; then exit 0; else exit 1; fi ;;
  pair|power|trust) echo "$1" >> $S/forbidden ;;
esac
''')
    stub.chmod(0o755)
    env = dict(os.environ, XDG_CONFIG_HOME=str(t / 'cfg'), WINDOESNOT_BLUETOOTHCTL=str(stub), WINDOESNOT_BT_WAIT='0', WINDOESNOT_BT_TRIES='5')
    run = lambda *a: subprocess.run([str(SCRIPT), *a], env=env, capture_output=True, text=True)
    calls = lambda: int((state / 'calls').read_text()) if (state / 'calls').exists() else 0
    assert run('get').stdout.strip() == ''
    assert run('connect').returncode == 0 and calls() == 0, 'no default device: nothing happens'
    assert run('set', 'nonsense').returncode == 2
    assert run('set', MAC.lower()).returncode == 0 and run('get').stdout.strip() == MAC
    (state / 'succeed-at').write_text('3')
    assert run('connect').returncode == 0 and calls() == 3, calls()          # two failures, then success
    assert (state / 'connect-args').read_text().split()[0] == MAC
    (state / 'calls').unlink(); (state / 'succeed-at').write_text('99')
    assert run('connect').returncode == 1 and calls() == 5, 'gives up after the configured tries'
    (state / 'calls').unlink(); (state / 'connected').write_text('yes')
    assert run('connect').returncode == 0 and calls() == 0, 'already connected: no connect call'
    (state / 'connected').write_text('no'); (state / 'paired').write_text('no')
    assert run('connect').returncode == 0 and calls() == 0, 'not paired: never pairs on its own'
    (state / 'paired').write_text('yes'); (state / 'powered').write_text('no')
    assert run('connect').returncode == 0 and calls() == 0, 'controller switched off: respected'
    assert not (state / 'forbidden').exists(), 'must never pair, trust or power on'
    assert run('clear').returncode == 0 and run('get').stdout.strip() == ''
print('PASS: bluetooth default device (choose, clear, retry until connected, give up, never pair or power on)')
