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
