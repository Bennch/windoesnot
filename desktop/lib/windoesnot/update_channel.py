#!/usr/bin/python3 -I
"""Update channel choice (stable or testing) and the matching pacman drop-in.

Pure functions plus two small file writers. No subprocess, no network. The
stable drop-in is byte-identical to the one the ISO and the one-time bootstrap
install, so existing systems never change unless the user opts in to testing.
"""
import os
from pathlib import Path
import uuid

CHANNELS = ('stable', 'testing')
DEFAULT = 'stable'
CHANNEL_FILE = Path('/etc/windoesnot/channel')
DROPIN_FILE = Path('/etc/pacman.d/windoesnot.conf')
BASE_URL = 'https://download.windoesnot.me/repo'
SIG_LEVEL = 'Required DatabaseRequired TrustedOnly'
REPO_NAMES = {'stable': 'windoesnot', 'testing': 'windoesnot-testing'}
DIRECTORIES = {'stable': 'x86_64', 'testing': 'testing/x86_64'}


def validate_channel(value):
    """Accept exactly the two channel names; anything else is an error."""
    if type(value) is not str or value not in CHANNELS:
        raise ValueError('Invalid update channel')
    return value


def parse_channel(text):
    """Channel from a channel file; empty, unknown or damaged content means stable."""
    value = text.strip() if type(text) is str else ''
    return value if value in CHANNELS else DEFAULT


def default_server(channel):
    return BASE_URL + '/' + DIRECTORIES[validate_channel(channel)]


def rebase_server(server, channel):
    """Keep a custom host (e.g. a test mirror) when the channel changes."""
    validate_channel(channel)
    server = server.strip().rstrip('/')
    for suffix in ('/testing/x86_64', '/x86_64'):
        if server.endswith(suffix):
            return server[:-len(suffix)] + '/' + DIRECTORIES[channel]
    return default_server(channel)


def current_server(dropin_text):
    for line in dropin_text.splitlines():
        key, separator, value = line.partition('=')
        if separator and key.strip() == 'Server' and value.strip():
            return value.strip()
    return None


def dropin_content(channel, server=None):
    """pacman drop-in for the channel: exactly one repository section, signed and trusted only.

    The other channel's section is absent, so the stable repository is disabled
    while testing is enabled (and vice versa)."""
    validate_channel(channel)
    server = default_server(channel) if server is None else rebase_server(server, channel)
    return f'[{REPO_NAMES[channel]}]\nSigLevel = {SIG_LEVEL}\nServer = {server}\n'


def read_channel(path=CHANNEL_FILE):
    try:
        return parse_channel(Path(path).read_text())
    except OSError:
        return DEFAULT


def write_text_atomic(path, text, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.windoesnot-' + uuid.uuid4().hex)
    try:
        with temporary.open('x') as out:
            os.chmod(temporary, mode)
            out.write(text); out.flush(); os.fsync(out.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_if_changed(path, text):
    try:
        if Path(path).read_text() == text:
            return False
    except OSError:
        pass
    write_text_atomic(path, text)
    return True


def apply_channel(channel, channel_file=CHANNEL_FILE, dropin_file=DROPIN_FILE):
    """Persist the channel and rewrite the drop-in. Idempotent; runs as root via system_tools.

    The drop-in is rewritten only when the WinDoesNot repository is already
    configured there (bootstrap or ISO); this never sets up trust by itself."""
    validate_channel(channel)
    dropin_file = Path(dropin_file)
    try:
        existing = dropin_file.read_text()
    except OSError:
        existing = None
    changed = write_if_changed(channel_file, channel + '\n')
    configured = existing is not None
    if configured:
        changed |= write_if_changed(dropin_file, dropin_content(channel, current_server(existing)))
    return {'channel': channel, 'changed': changed, 'repository': configured, 'reboot': False}
