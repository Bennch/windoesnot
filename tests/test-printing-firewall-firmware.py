#!/usr/bin/env python3
"""Pure logic checks for printer, firewall and firmware helper actions. Runs no system commands."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'desktop/lib/windoesnot'))
import system_tools as tools

# Parsing of lpstat/lpinfo output.
parsed = tools.parse_printers(
    'device for HP_Office: ipp://192.168.1.20/ipp/print\n',
    'system default destination: HP_Office\n',
    'network dnssd://HP%20Office._ipp._tcp.local/\ndirect usb://Brother/HL?serial=1\nfile cups-pdf:/\nnetwork https://evil.example/\n')
assert parsed['printers'] == [{'name': 'HP_Office', 'uri': 'ipp://192.168.1.20/ipp/print'}], parsed
assert parsed['default'] == 'HP_Office'
assert parsed['candidates'] == ['dnssd://HP%20Office._ipp._tcp.local/', 'usb://Brother/HL?serial=1'], parsed['candidates']
assert tools.parse_printers('', 'no system default destination', '')['default'] is None

# Firmware JSON: only devices with a release count, malformed output is unknown (None).
raw = json.dumps({'Devices': [
    {'Name': 'SSD', 'Releases': [{'Version': '2.1'}]},
    {'Name': 'Dock', 'Releases': []},
    {'Name': 'Mainboard', 'Releases': [{'Version': '1.5'}]}]})
assert tools.parse_firmware(raw) == [{'device': 'SSD', 'version': '2.1'}, {'device': 'Mainboard', 'version': '1.5'}]
assert tools.parse_firmware('No updates available') is None
assert tools.parse_firmware('{"Error": "x"}') is None

# Payloads: only the fixed shapes are accepted, no free-form commands or URIs.
ok = [('printer-add', {'uri': 'ipp://192.168.1.20/ipp/print', 'name': 'HP_Office'}),
      ('printer-default', {'name': 'HP_Office'}), ('firewall-set', {'enabled': True}),
      ('firewall-set', {'enabled': False}), ('firmware-apply', {}), ('printer-service-start', {})]
for action, payload in ok:
    tools.validate(action, payload)
bad = [('printer-add', {'uri': 'ipp://x', 'name': 'a b'}), ('printer-add', {'uri': '/bin/sh -c id', 'name': 'x'}),
       ('printer-add', {'uri': 'ipp://x', 'name': 'x', 'extra': 1}), ('printer-default', {'name': '../x'}),
       ('firewall-set', {'enabled': 'yes'}), ('firewall-set', {}), ('firmware-apply', {'file': '/tmp/x'})]
for action, payload in bad:
    try:
        tools.validate(action, payload)
    except ValueError:
        continue
    raise AssertionError(f'accepted {action} {payload}')

# Firewall enable: rules must be in place before ufw enable; service enable comes last.
calls = []
def record(*args, **kwargs):
    calls.append(args)
with patch.object(tools, 'available', return_value=True), patch.object(tools, 'command', side_effect=record):
    tools.apply('firewall-set', {'enabled': True})
assert calls[-2:] == [('/usr/bin/ufw', '--force', 'enable'), ('/usr/bin/systemctl', 'enable', 'ufw.service')], calls
# No LocalSend port is opened until it has been tested.
assert not any(c[:2] == ('/usr/bin/ufw', 'allow') for c in calls), calls

# Only whitelisted, fixed commands run for the new actions.
allowed_binaries = {'/usr/bin/ufw', '/usr/bin/systemctl', '/usr/bin/lpadmin', '/usr/bin/fwupdmgr'}
assert all(c[0] in allowed_binaries for c in calls)

# Account actions: payloads come on stdin, so argv must stay empty and extra arguments are refused.
tools.validate('password-change', {})
tools.validate('avatar-set', {})
for action in ('password-change', 'avatar-set'):
    try:
        tools.validate(action, {'password': 'x'})
    except ValueError:
        pass
    else:
        raise AssertionError(f'accepted arguments for {action}')
assert set(tools.STDIN_ACTIONS) == {'password-change', 'avatar-set'}

# Password payload: exact keys, 8 to 256 characters, no control characters.
tools.validate_password_change({'current': 'old-secret', 'password': 'new-secret-1'})
for data in ({'current': 'x', 'password': 'short'}, {'current': '', 'password': 'long-enough-1'},
             {'current': 'x', 'password': 'with\nnewline'}, {'current': 'x'}, {'current': 'x', 'password': 'a' * 257},
             {'current': 'x', 'password': 'ok-password', 'user': 'root'}, {'current': 1, 'password': 'ok-password'}):
    try:
        tools.validate_password_change(data)
    except ValueError:
        continue
    raise AssertionError(f'accepted password data {sorted(data)}')

# Current password check against libcrypt, with the stored hash patched in (no real shadow access).
stored = tools.crypt_hash('correct-horse', '$6$testsalt$')
assert stored and stored.startswith('$6$testsalt$'), stored
yescrypt = tools.crypt_hash('correct-horse', '$y$j9T$testsalt$')
assert yescrypt and yescrypt.startswith('$y$'), yescrypt
for hash_value, password, expected in ((stored, 'correct-horse', True), (stored, 'wrong-horse', False),
                                       (yescrypt, 'correct-horse', True), (yescrypt, 'wrong-horse', False),
                                       ('!' + stored, 'correct-horse', False), ('*', 'correct-horse', False),
                                       ('', 'correct-horse', False)):
    with patch.object(tools, 'stored_password_hash', return_value=hash_value):
        assert tools.verify_current_password('benni', password) is expected, (hash_value[:6], password)

# Profile picture: only PNG data up to the size limit; anything else is refused before any write.
assert tools.PNG_SIGNATURE == b'\x89PNG\r\n\x1a\n'
for data in (b'GIF89a' + b'0' * 100, b'\x89PNG\r\n\x1a\n', b'\x89PNG\r\n\x1a\n' + b'0' * tools.AVATAR_MAX, 'text'):
    try:
        tools.validate_png(data)
    except ValueError:
        continue
    raise AssertionError(f'accepted image data {data[:8]!r}')
tools.validate_png(tools.PNG_SIGNATURE + b'0' * 100)

# The account actions write only under the caller's name, into a scratch directory under build/.
import io
import os
import shutil
scratch = ROOT / 'build' / 'test-account-scratch'
shutil.rmtree(scratch, ignore_errors=True)
(scratch / 'users').mkdir(parents=True)
(scratch / 'users' / 'benni').write_text('[User]\nLanguage=de_DE.UTF-8\nXSession=windoesnot\n')
with patch.object(tools, 'ACCOUNTS_DIR', scratch), patch.dict(os.environ, {'PKEXEC_UID': '1000'}), \
        patch.object(tools.pwd, 'getpwuid', return_value=type('P', (), {'pw_name': 'benni'})()):
    assert tools.caller_account() == 'benni'
    tools.set_own_avatar(tools.PNG_SIGNATURE + b'0' * 100)
written = (scratch / 'users' / 'benni').read_text()
assert 'Icon=' + str(scratch / 'icons' / 'benni') in written and 'Language=de_DE.UTF-8' in written and 'XSession=windoesnot' in written, written
assert (scratch / 'icons' / 'benni').read_bytes().startswith(tools.PNG_SIGNATURE)
shutil.rmtree(scratch)

# Root and system accounts are never changed by these actions.
for uid in ('0', '999', '65534', ''):
    with patch.dict(os.environ, {'PKEXEC_UID': uid}):
        try:
            tools.caller_account()
        except ValueError:
            continue
        raise AssertionError(f'accepted PKEXEC_UID {uid!r}')

print('ok: printer, firewall and firmware helper checks passed')
