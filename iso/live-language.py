#!/usr/bin/env python3
"""Apply installer and early boot language choices to the disposable live desktop."""
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time


def desktop_locale(language):
    return ('de', 'de_DE.UTF-8') if language.lower().startswith('de') else ('en', 'en_US.UTF-8')


def boot_choice(command_line):
    values = {key: value for word in command_line.split() if (parts := word.partition('='))[1]
              for key, value in [(parts[0], parts[2])]
              if key in ('windoesnot.lang', 'windoesnot.keymap')}
    language = values.get('windoesnot.lang')
    keymap = values.get('windoesnot.keymap')
    return (language if language in ('en', 'de') else None,
            keymap if keymap in ('us', 'de') else None)


def set_live_defaults(language, keymap):
    locale = desktop_locale(language)[1]
    zone = 'Europe/Berlin' if language == 'de' else 'UTC'
    Path('/etc/locale.conf').write_text('LANG=' + locale + '\n')
    Path('/etc/default/keyboard').write_text('XKBLAYOUT="' + keymap + '"\n')
    Path('/etc/vconsole.conf').write_text('KEYMAP=' + keymap + '\n')
    localtime = Path('/etc/localtime')
    localtime.unlink(missing_ok=True)
    localtime.symlink_to('/usr/share/zoneinfo/' + zone)
    # SDDM reads its own greeter environment after a later installed-system boot.
    greeter = Path('/etc/sddm.conf.d/windoesnot.conf')
    if greeter.is_file():
        content = re.sub(r'(?m)^GreeterEnvironment=.*\n?', '', greeter.read_text())
        greeter.write_text(content.replace('[General]\n', '[General]\nGreeterEnvironment=LANG=' + locale + '\n', 1))
    subprocess.run(['runuser', '-u', 'liveuser', '--', '/usr/bin/windoesnot-initialize', '--adopt-system'], check=True)


def settings_ipc(base, account, method, value):
    command = [*base, 'quickshell', 'ipc', '--path', account.pw_dir + '/.config/quickshell/default/shell.qml', 'call', 'windoesnot-settings', method, value]
    for attempt in range(12):
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
        time.sleep(.2)
    raise SystemExit('Live desktop settings IPC unavailable')


def main():
    if sys.argv[1:] == ['--boot']:
        if not Path('/etc/windoesnot-image-build').is_file() or os.geteuid() != 0:
            raise SystemExit('Live image only')
        language, keymap = boot_choice(Path('/proc/cmdline').read_text())
        if language or keymap:
            language = language or Path('/etc/windoesnot-live-language').read_text().strip()
            set_live_defaults(language, keymap or ('de' if language == 'de' else 'us'))
        return
    if sys.argv[1:] == ['--read-preference']:
        path = Path.home() / '.config/quickshell/default/settings.txt'
        language = 'de' if os.environ.get('LANG', '').startswith('de') else 'en'
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
    # Standard folders (Documents, Pictures, ...) follow the live language; never fatal.
    subprocess.run([*base, 'windoesnot-user-dirs', '--locale', locale], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run([*base, 'DBUS_SESSION_BUS_ADDRESS=unix:path=' + runtime + '/bus', 'systemctl', '--user', 'set-environment', 'LANG=' + locale, 'LANGUAGE=' + language], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


if __name__ == '__main__':
    main()
