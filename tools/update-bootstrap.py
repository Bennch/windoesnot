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
