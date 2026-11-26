#!/usr/bin/env python3
"""Read-only prerequisite check for CachyOS eac-setup. Prints a JSON list of
{id, ok, detail}; ok is true, false or null (unknown). Touches nothing."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path('/')
UTF16 = 'utf-16-le'


def _read(path):
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def _efivar(root, prefix):
    """Payload of the first efivar named prefix-*, without the 4-byte attributes."""
    base = Path(root) / 'sys/firmware/efi/efivars'
    try:
        for entry in sorted(base.glob(prefix + '-*')):
            data = _read(entry)
            if data is not None and len(data) > 4:
                return data[4:]
    except OSError:
        pass
    return None


def check_uefi(root):
    ok = (Path(root) / 'sys/firmware/efi').is_dir()
    return {'id': 'uefi', 'ok': ok, 'detail': 'uefi' if ok else 'bios'}


def check_tpm2(root):
    data = _read(Path(root) / 'sys/class/tpm/tpm0/tpm_version_major')
    if data is None:
        return {'id': 'tpm2', 'ok': False, 'detail': 'missing'}
    version = data.decode('ascii', 'replace').strip()
    return {'id': 'tpm2', 'ok': version == '2', 'detail': version}


def check_iommu_table(root):
    tables = Path(root) / 'sys/firmware/acpi/tables'
    for name in ('DMAR', 'IVRS'):
        if (tables / name).exists():
            return {'id': 'iommu_table', 'ok': True, 'detail': name}
    if not tables.is_dir():
        return {'id': 'iommu_table', 'ok': None, 'detail': 'unreadable'}
    return {'id': 'iommu_table', 'ok': False, 'detail': 'missing'}


def check_secure_boot(root):
    if not (Path(root) / 'sys/firmware/efi').is_dir():
        return {'id': 'secure_boot', 'ok': None, 'detail': 'no-uefi'}
    secure, setup = _efivar(root, 'SecureBoot'), _efivar(root, 'SetupMode')
    if secure is None or setup is None:
        return {'id': 'secure_boot', 'ok': None, 'detail': 'unknown'}
    if setup[0] == 1:
        return {'id': 'secure_boot', 'ok': True, 'detail': 'setup-mode'}
    return {'id': 'secure_boot', 'ok': False,
            'detail': 'enabled' if secure[0] == 1 else 'disabled'}


def check_boot_manager(root):
    root = Path(root)
    info = _efivar(root, 'LoaderInfo')
    if info:
        text = info.decode(UTF16, 'ignore').strip('\x00 ').lower()
        for key, name in (('systemd-boot', 'systemd-boot'), ('limine', 'limine'),
                          ('refind', 'rEFInd'), ('grub', 'grub')):
            if key in text:
                return {'id': 'boot_manager', 'ok': True, 'detail': name}
    found = []
    for name, paths in (('systemd-boot', ('boot/loader/loader.conf', 'efi/loader/loader.conf', 'boot/efi/loader/loader.conf')),
                        ('limine', ('boot/limine.conf', 'boot/limine/limine.conf', 'efi/limine.conf', 'efi/EFI/limine/limine.conf', 'boot/EFI/limine/limine.conf')),
                        ('rEFInd', ('boot/EFI/refind/refind.conf', 'efi/EFI/refind/refind.conf', 'boot/efi/EFI/refind/refind.conf')),
                        ('grub', ('boot/grub/grub.cfg',))):
        if any((root / p).is_file() for p in paths):
            found.append(name)
    if len(found) == 1:
        return {'id': 'boot_manager', 'ok': True, 'detail': found[0]}
    return {'id': 'boot_manager', 'ok': None, 'detail': 'unknown'}


def check_not_snapshot_boot(root):
    data = _read(Path(root) / 'proc/cmdline')
    if data is None:
        return {'id': 'not_snapshot_boot', 'ok': None, 'detail': 'unknown'}
    snapshot = b'.snapshots' in data
    return {'id': 'not_snapshot_boot', 'ok': not snapshot, 'detail': 'snapshot' if snapshot else 'normal'}


def check_tools(path=None):
    found = shutil.which('eac-setup', path=path)
    return {'id': 'eac_tools_installed', 'ok': found is not None, 'detail': found or 'missing'}


def run_checks(root=ROOT, path=None):
    return [check_uefi(root), check_tpm2(root), check_iommu_table(root),
            check_secure_boot(root), check_boot_manager(root),
            check_not_snapshot_boot(root), check_tools(path)]


if __name__ == '__main__':
    json.dump(run_checks(), sys.stdout)
    sys.stdout.write('\n')
