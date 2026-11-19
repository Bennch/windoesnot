#!/usr/bin/env python3
"""One-time offline bootstrap for WinDoesNot 29/30; no pacman or reboot."""
import argparse
import base64
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import types
import zlib

MIGRATION = zlib.decompress(base64.b64decode('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'))
PACKAGED_HOOK = '[Trigger]\nOperation = Install\nOperation = Upgrade\nType = Path\nTarget = usr/lib/modules/*/vmlinuz\n\n[Trigger]\nOperation = Install\nOperation = Upgrade\nType = Package\nTarget = windoesnot-tools\n\n[Action]\nDescription = Checking WinDoesNot boot filesystem before update...\nWhen = PreTransaction\nExec = /usr/bin/python3 /usr/lib/windoesnot/boot_entry_migration.py --preflight\nAbortOnFail\n'.encode()
SCRIPT = 'var/lib/windoesnot/migrations/bootstrap/boot_entry_migration.py'
HOOK = 'etc/pacman.d/hooks/00-windoesnot-boot-guard.hook'
TEMP_HOOK = PACKAGED_HOOK.replace(b'/usr/lib/windoesnot/boot_entry_migration.py', b'/' + SCRIPT.encode())


def same(path, content):
    return path.is_file() and not path.is_symlink() and path.read_bytes() == content


def atomic(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.windoesnot-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(root):
    root = Path(root).resolve()
    hook, script = root / HOOK, root / SCRIPT
    # Refuse every foreign override, including dangling symlinks, before migration.
    for path, expected in ((hook, TEMP_HOOK), (script, MIGRATION)):
        if (path.exists() or path.is_symlink()) and not same(path, expected):
            raise RuntimeError('Fremde oder geänderte Datei bleibt erhalten: ' + str(path))
    migration = types.ModuleType('boot_entry_migration')
    exec(compile(MIGRATION, SCRIPT, 'exec'), migration.__dict__)
    kind = migration.classify(root)
    if kind == 'systemd-boot-unavailable':
        raise RuntimeError('EFI-Partition auf /boot fehlt; vor dem Update einhängen.')
    if kind == 'not-applicable':
        print('Kein systemd-boot-Layout; keine Änderung erforderlich.')
        return
    migration.check_mount(migration.mount_info(root))
    migration.plan(root)
    # apply backs up retired entries before removal and repairs defaults first.
    migration.apply(root, set_default=migration.bootctl_set_default if root == Path('/') else None)
    installed = same(root / 'usr/share/libalpm/hooks/00-windoesnot-boot-guard.hook', PACKAGED_HOOK) and same(root / 'usr/lib/windoesnot/boot_entry_migration.py', MIGRATION)
    if installed:
        # An administrator may have modified the override: only our exact bytes are removed.
        if same(hook, TEMP_HOOK):
            hook.unlink()
        if same(script, MIGRATION):
            script.unlink()
        print('Paket-Guard vorhanden; eigene temporäre Dateien entfernt.')
    else:
        # Script first, then hook: an interrupted install never installs a broken guard.
        if not same(script, MIGRATION):
            atomic(script, MIGRATION, 0o755)
        if not same(hook, TEMP_HOOK):
            atomic(hook, TEMP_HOOK, 0o644)
        print('Migration abgeschlossen; temporärer Update-Guard aktiv.')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='/')
    args = parser.parse_args(argv)
    try:
        run(args.root)
        return 0
    except Exception as exc:
        print('Bootstrap fehlgeschlagen: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
