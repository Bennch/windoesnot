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


RECOVERY_LABEL = {'en': 'Start restore points from disk', 'de': 'Wiederherstellungspunkte von der Festplatte starten'}
RECOVERY_PARAMETER = 'windoesnot.recovery=1'


def grub_recovery(text, language='en'):
    """Add a menu entry that boots the live system straight into the restore point list."""
    if language not in RECOVERY_LABEL:
        raise ValueError('Unsupported language')
    pattern = re.compile(r'^menuentry "[^"\n]*"[^\n]*--id \'windoesnot-offline\'[^\n]*\{\n.*?^\}', re.M | re.S)
    match = pattern.search(text)
    if not match:
        raise ValueError('Upstream live GRUB layout changed: no stable offline entry')
    entry = re.sub(r'^menuentry "[^"\n]*"', 'menuentry "' + RECOVERY_LABEL[language] + '"', match[0])
    entry = entry.replace("--id 'windoesnot-offline'", "--id 'windoesnot-recovery'")
    entry = re.sub(r'^(\s*linux .*)$', lambda m: re.sub(r' windoesnot\.install=\w+', '', m[1]) + ' ' + RECOVERY_PARAMETER, entry, flags=re.M)
    return text[:match.end()] + '\n\n' + entry + text[match.end():]


def syslinux_recovery(text, language='en'):
    if language not in RECOVERY_LABEL:
        raise ValueError('Unsupported language')
    match = re.search(r'^LABEL wdn-offline\n.*?(?=^LABEL |\Z)', text, re.M | re.S)
    if not match:
        raise ValueError('Upstream BIOS layout changed: no stable offline entry')
    entry = match[0].replace('LABEL wdn-offline', 'LABEL wdn-recovery', 1)
    entry = re.sub(r'^MENU LABEL .*$', lambda m: 'MENU LABEL ' + RECOVERY_LABEL[language], entry, flags=re.M)
    entry = re.sub(r'^MENU DEFAULT\n', '', entry, flags=re.M)
    entry = re.sub(r'^(APPEND .*)$', lambda m: re.sub(r' windoesnot\.install=\w+', '', m[1]) + ' ' + RECOVERY_PARAMETER, entry, flags=re.M)
    return text[:match.end()].rstrip('\n') + '\n' + entry.rstrip('\n') + '\n' + text[match.end():]


def efi_recovery(directory, language='en'):
    """systemd-boot: copy the first live entry as a recovery entry; returns the new file or None."""
    from pathlib import Path
    if language not in RECOVERY_LABEL:
        raise ValueError('Unsupported language')
    sources = sorted(path for path in Path(directory).glob('*.conf') if 'recovery' not in path.name)
    if not sources:
        return None
    text = sources[0].read_text()
    text = re.sub(r'^title .*$', lambda m: 'title ' + RECOVERY_LABEL[language], text, count=1, flags=re.M)
    text = re.sub(r'^sort-key .*\n', '', text, flags=re.M)
    text = re.sub(r'^(options .*)$', lambda m: re.sub(r' windoesnot\.install=\w+', '', m[1]) + ' ' + RECOVERY_PARAMETER, text, count=1, flags=re.M)
    target = Path(directory) / '99-windoesnot-recovery.conf'
    target.write_text(text)
    return target
