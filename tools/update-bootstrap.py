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
