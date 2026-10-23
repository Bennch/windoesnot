#!/usr/bin/env python3
"""Apply Calamares' supported UI language and keyboard layout to the disposable live desktop only."""
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time


def desktop_locale(language):
    return ('de', 'de_DE.UTF-8') if language.lower().startswith('de') else ('en', 'en_US.UTF-8')


def settings_ipc(base, account, method, value):
    command = [*base, 'quickshell', 'ipc', '--path', account.pw_dir + '/.config/quickshell/default/shell.qml', 'call', 'windoesnot-settings', method, value]
    for attempt in range(12):
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
        time.sleep(.2)
    raise SystemExit('Live desktop settings IPC unavailable')


def main():
    if sys.argv[1:] == ['--read-preference']:
        path = Path.home() / '.config/quickshell/default/settings.txt'
        language = 'de'
        if path.is_file():
            for line in path.read_text().splitlines():
                if line.startswith('uiLanguage='): language = line.split('=', 1)[1]
        print(desktop_locale(language)[1])
        return
    if not Path('/etc/windoesnot-image-build').is_file() or os.geteuid() != 0:
        raise SystemExit('Live image only')
    account = pwd.getpwnam('liveuser')
    runtime = f'/run/user/{account.pw_uid}'
    if sys.argv[1:2] == ['--keyboard']:
        # Calamares' keyboard step only informs locale1, which Hyprland ignores.
        # Without this, passwords chosen in the installer are typed on the US layout.
        layout = sys.argv[2] if len(sys.argv) == 3 else ''
        if not re.fullmatch(r'[a-z]{2,8}(,[a-z]{2,8})?', layout):
            raise SystemExit('Unsupported keyboard layout')
        base = ['runuser', '-u', account.pw_name, '--', 'env', 'XDG_RUNTIME_DIR=' + runtime, 'WAYLAND_DISPLAY=wayland-1']
        if settings_ipc(base, account, 'setKeyboardLayout', layout) != layout:
            raise SystemExit('Live desktop rejected keyboard layout')
        return
    language, locale = desktop_locale(sys.argv[1])
    base = ['runuser', '-u', account.pw_name, '--', 'env', 'XDG_RUNTIME_DIR=' + runtime, 'WAYLAND_DISPLAY=wayland-1', 'LANG=' + locale, 'LANGUAGE=' + language]
    settings_ipc(base, account, 'setLanguage', language)
    Path('/etc/locale.conf').write_text('LANG=' + locale + '\n')
    subprocess.run([*base, 'DBUS_SESSION_BUS_ADDRESS=unix:path=' + runtime + '/bus', 'systemctl', '--user', 'set-environment', 'LANG=' + locale, 'LANGUAGE=' + language], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


if __name__ == '__main__':
    main()
