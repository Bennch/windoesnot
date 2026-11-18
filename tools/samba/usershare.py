"""Usershare validation and command construction; no system changes on import.

This is an unintegrated building block, not a complete sharing service.
"""
from pathlib import Path
import re

_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z')
_USER = re.compile(r'[a-z_][a-z0-9_-]*\$?\Z')


def validate_name(name):
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError('Invalid share name')
    return name


def validate_path(path, home):
    home = Path(home).resolve(strict=True)
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('An absolute path is required')
    path = path.resolve(strict=True)
    if path == home or not path.is_relative_to(home) or not path.is_dir():
        raise ValueError('Choose a directory inside your home')
    return str(path)


def add_command(name, path, home, user, writable=False, guest=False):
    validate_name(name)
    if not isinstance(user, str) or not _USER.fullmatch(user):
        raise ValueError('Invalid user name')
    if type(writable) is not bool or type(guest) is not bool:
        raise ValueError('Options must be boolean')
    if guest and writable:
        raise ValueError('Guest access must be read-only')
    path = validate_path(path, home)
    acl = 'Everyone:R' if guest else f'{user}:{"F" if writable else "R"}'
    return ['/usr/bin/net', 'usershare', 'add', name, path, '', acl,
            'guest_ok=y' if guest else 'guest_ok=n']


def remove_command(name):
    return ['/usr/bin/net', 'usershare', 'delete', validate_name(name)]
