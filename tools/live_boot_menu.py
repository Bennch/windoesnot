"""Generate explicit installer modes for both UEFI GRUB and BIOS Syslinux."""
import re


def grub_modes(text, language='en'):
    if language not in ('en', 'de'):
        raise ValueError('Unsupported language')
    pattern = re.compile(r'^menuentry "(WinDoesNot[^"]*)"([^\n]*--id \'(cachyos[^\']*)\'[^\n]*)\{\n(.*?)^\}', re.M | re.S)
    def variants(match):
        title, options, old_id, body = match.groups()
        entries = []
        suffix = old_id.removeprefix('cachyos')
        for mode in ('offline', 'online'):
            label = title + (' starten (Offline-Installation)' if mode == 'offline' else ' starten (Online-Installation)') if language == 'de' else title + (' (live, offline install)' if mode == 'offline' else ' (live, online install)')
            selected = options.replace("'" + old_id + "'", "'windoesnot-" + mode + suffix + "'")
            commands = re.sub(r'^(\s*linux .*)$', r'\1 windoesnot.install=' + mode, body, flags=re.M)
            entries.append('menuentry "' + label + '"' + selected + '{\n' + commands + '}')
        return '\n\n'.join(entries)
    result, count = pattern.subn(variants, text)
    if count != 3:
        raise ValueError('Upstream live GRUB layout changed: expected three kernel variants')
    result = result.replace('default=cachyos', 'default=windoesnot-offline')
    if language == 'de':
        for english, german in {'Welcome to WinDoesNot':'Willkommen bei WinDoesNot', 'Run Memtest86+ (RAM test)':'Memtest86+ starten (RAM-Test)', 'UEFI Firmware Settings':'UEFI-Firmware-Einstellungen', 'System shutdown':'System ausschalten', 'System restart':'System neu starten', 'LTS Kernel':'LTS-Kernel', 'Legacy Hardware (GPU nomodeset)':'Ältere Hardware (GPU nomodeset)'}.items():
            result = result.replace(english, german)
    return result


def syslinux_modes(text, language='en'):
    if language not in ('en', 'de'):
        raise ValueError('Unsupported language')
    pattern = re.compile(r'^LABEL (\S+)\n(.*?)(?=^LABEL |\Z)', re.M | re.S)
    def variants(match):
        old_id, body = match.groups()
        if old_id not in ('cos64', 'cos64fb'):
            raise ValueError('Unknown BIOS kernel entry: ' + old_id)
        entries = []
        suffix = '-fallback' if old_id == 'cos64fb' else ''
        for mode in ('offline', 'online'):
            suffix_label = ('Offline-Installation' if mode == 'offline' else 'Online-Installation') if language == 'de' else ('offline install' if mode == 'offline' else 'online install')
            content = re.sub(r'^(MENU LABEL .*)$', r'\1 (' + suffix_label + ')', body, flags=re.M)
            content = re.sub(r'^(APPEND .*)$', r'\1 windoesnot.install=' + mode, content, flags=re.M)
            entries.append('LABEL wdn-' + mode + suffix + '\n' + content)
        return '\n'.join(entries)
    result, count = pattern.subn(variants, text)
    if count != 2:
        raise ValueError('Upstream BIOS layout changed: expected two kernel variants')
    return result.replace('copytoram=auto', 'copytoram=n')
