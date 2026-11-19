#!/usr/bin/env python3
"""Keep GRUB quiet while it starts the kernel.

grub-mkconfig writes `echo 'Loading Linux ...'` and `echo 'Loading initial ramdisk ...'` in front of every entry, and GRUB prints
them between the menu and the splash. This removes exactly those lines from grub.cfg (a copy is only replaced when the
result still has its menu entries). It runs after every grub-mkconfig that we start or that a package update triggers.

  grub_quiet.py filter [grub.cfg]        remove the messages from an existing file
  grub_quiet.py mkconfig -o grub.cfg     grub-mkconfig, then filter (for tools that call grub-mkconfig, e.g. grub-btrfsd)
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CONFIG = Path('/boot/grub/grub.cfg')
MESSAGE = re.compile(r"^[ \t]*echo[ \t]+'Loading (?:Linux [^'\n]*|initial ramdisk) \.\.\.'[ \t]*\r?\n", re.MULTILINE)


def quiet_text(text):
    return MESSAGE.sub('', text)


def filter_file(path=CONFIG):
    path = Path(path)
    try:
        text = path.read_text()
    except OSError:
        return False
    result = quiet_text(text)
    if result == text:
        return False
    if text.count('menuentry') != result.count('menuentry') or 'menuentry' not in result:
        return False  # never touch the file if the menu would change
    info = path.stat()
    fd, temporary = tempfile.mkstemp(prefix='.grub.cfg.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(result)
        os.chmod(temporary, info.st_mode & 0o7777)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == 'filter':
        filter_file(sys.argv[2] if len(sys.argv) > 2 else CONFIG)
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == 'mkconfig':
        code = subprocess.run(['/usr/bin/grub-mkconfig', *sys.argv[2:]]).returncode
        target = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv[2:] else None
        if code == 0 and target:
            filter_file(target)
        return code
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
