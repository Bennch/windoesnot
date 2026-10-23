"""Read installer/system locale and keyboard choices without running shell code."""
from pathlib import Path
import re
import shlex


def assignments(path):
    result = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and re.fullmatch(r'[A-Z_]+', key.strip()):
                fields = shlex.split(value, comments=True)
                result[key.strip()] = fields[0] if fields else ''
    return result


def system_defaults(root=Path('/')):
    keyboard = assignments(root / 'etc/default/keyboard')
    locale = assignments(root / 'etc/locale.conf').get('LANG', 'en_US.UTF-8')
    layout = keyboard.get('XKBLAYOUT', 'us') or 'us'
    timezone = 'UTC'
    localtime = root / 'etc/localtime'
    if localtime.is_symlink():
        target = str(localtime.readlink())
        if '/zoneinfo/' in target:
            timezone = target.split('/zoneinfo/', 1)[1]
    return {
        'settings': {'keyboardLayout': layout, 'uiLanguage': 'de' if locale.startswith('de') else 'en', 'systemLocale': locale, 'timeZone': timezone},
        'options': {'input.kb_layout': layout, 'input.kb_model': keyboard.get('XKBMODEL', ''), 'input.kb_variant': keyboard.get('XKBVARIANT', ''), 'input.kb_options': keyboard.get('XKBOPTIONS', '')},
    }
