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
