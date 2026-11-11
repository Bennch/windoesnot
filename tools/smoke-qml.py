#!/usr/bin/env python3
"""Load the full shell in an isolated headless Wayland session (no user IPC)."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent


def stop(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


with tempfile.TemporaryDirectory(prefix='wdn-qml-') as temporary:
    home = Path(temporary)
    runtime = home / 'run'
    runtime.mkdir(mode=0o700)
    env = {**os.environ, 'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'),
           'XDG_CACHE_HOME': str(home / '.cache'), 'XDG_DATA_HOME': str(home / '.local/share'),
           'XDG_RUNTIME_DIR': str(runtime), 'QT_QPA_PLATFORM': 'wayland',
           'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-session-bus'),
           'HYPRLAND_INSTANCE_SIGNATURE': 'windoesnot-isolated-smoke',
           'WINDOESNOT_SOURCE': str(ROOT), 'PATH': str(home / '.local/bin') + ':/usr/local/bin:/usr/bin',
           'WLR_BACKENDS': 'headless', 'WLR_RENDERER': 'pixman', 'WLR_HEADLESS_OUTPUTS': '1'}
    for key in ['WAYLAND_DISPLAY', 'DISPLAY', 'WAYLAND_SOCKET', 'LD_PRELOAD']:
        env.pop(key, None)
    subprocess.run([ROOT / 'desktop/bin/windoesnot-initialize'], env=env, check=True)
    module = home / '.config/quickshell/default/widgets/terminalmodule/LocalTerminal'
    shutil.copytree(ROOT / 'build/components/LocalTerminal', module, dirs_exist_ok=True)
    compositor = shell = None
    with (ROOT / 'checks/qml-compositor.log').open('w') as compositor_log, \
            (ROOT / 'checks/qml-runtime-smoke.log').open('w') as log:
        try:
            compositor = subprocess.Popen(['labwc', '-C', str(home / '.config/labwc')],
                                          env=env, stdout=compositor_log, stderr=subprocess.STDOUT,
                                          start_new_session=True)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                sockets = [p for p in runtime.glob('wayland-*') if p.is_socket()]
                if sockets:
                    env['WAYLAND_DISPLAY'] = sockets[0].name
                    break
                if compositor.poll() is not None:
                    raise SystemExit('Test compositor failed; inspect checks/qml-compositor.log')
                time.sleep(0.1)
            else:
                raise SystemExit('Test Wayland socket did not appear')
            shell = subprocess.Popen(['quickshell', '--no-color', '-p', str(home / '.config/quickshell/default')],
                                     env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                shell.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            else:
                raise SystemExit('Shell exited unexpectedly; inspect checks/qml-runtime-smoke.log')
        finally:
            stop(shell)
            stop(compositor)
    output = (ROOT / 'checks/qml-runtime-smoke.log').read_text()
    print('\n'.join(output.splitlines()[:35]))
    if 'Failed to load configuration' in output:
        raise SystemExit(1)
    if 'Configuration Loaded' not in output:
        raise SystemExit('No successful QML load marker; inspect log')
    print('PASS: shell QML loads in isolated Wayland; physical rendering and interaction need a live test')
