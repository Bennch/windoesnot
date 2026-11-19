#!/usr/bin/env python3
"""SMB: the address is validated, the password only travels in the environment, a share without a package is released again."""
import importlib.util
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('finder', root / 'desktop/lib/windoesnot/finder.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

assert f.smb_parts('smb://nas/umzug') == ('nas', 'umzug', '')
assert f.smb_parts('//192.168.1.5/Umzug Paket/sub/dir') == ('192.168.1.5', 'Umzug Paket', 'sub/dir')
for bad in ('nas/umzug', 'smb://nas', 'smb://na;s/x', 'smb://nas/../x', 'ftp://nas/x', 'smb://nas/a;b'):
    try:
        f.smb_parts(bad)
        raise AssertionError('accepted ' + bad)
    except ValueError:
        pass

class Result:
    def __init__(self, code=0, err=b''):
        self.returncode, self.stderr = code, err

with tempfile.TemporaryDirectory() as tmp:
    f.PACKAGE_MOUNT_BASE = Path(tmp)
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs.get('env', {}).get('PASSWD')))
        return Result()
    hits = f.connect_smb('smb://nas/umzug', 'anna', 'geheim!', runner=runner)
    assert hits == [] and calls[0][0][:3] == ['mount', '-t', 'cifs'] and calls[0][1] == 'geheim!'
    assert 'geheim' not in ' '.join(calls[0][0]), 'password must not be in the command line'
    assert 'username=anna' in calls[0][0][-1] and calls[1][0][0] == 'umount', 'a share without a package is released'
    # A refused login is an error with the server's message, and leaves no mount directory behind.
    def failing(command, **kwargs):
        return Result(32, b'mount error(13): Permission denied')
    try:
        f.connect_smb('smb://nas/umzug', 'anna', 'wrong', runner=failing)
        raise AssertionError('login failure ignored')
    except OSError as error:
        assert 'Permission denied' in str(error)
    assert not any(Path(tmp).iterdir())
    # A package on the share is reported and the share stays mounted.
    share = Path(tmp) / 'smb-nas-umzug'
    def with_package(command, **kwargs):
        if command[0] == 'mount':
            (share / 'Umzug-anna-x' / 'data').mkdir(parents=True, exist_ok=True)
            (share / 'Umzug-anna-x' / f.PACKAGE_MARKER).write_text('{"schema": 3, "kind": "package", "complete": true, "created": 1, "source": {"user": {"name": "anna"}}, "findings": [{"bytes": 5}]}')
        return Result()
    hits = f.connect_smb('smb://nas/umzug', None, None, runner=with_package)
    assert len(hits) == 1 and hits[0]['filesystem'] == 'cifs' and hits[0]['user'] == 'anna' and share.is_dir()
print('PASS package smb')
