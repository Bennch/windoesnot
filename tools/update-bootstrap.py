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
