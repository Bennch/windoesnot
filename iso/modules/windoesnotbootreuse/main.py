# SPDX-License-Identifier: GPL-3.0-or-later
"""Protect shared EFI files and add WinDoesNot to a verified existing menu."""
import json
from pathlib import Path
import re
import sys
import libcalamares

sys.path.insert(0, '/usr/share/windoesnot/iso')
import boot_environment as boot


def pretty_name():
    return 'Vorhandenes Startmenü prüfen und ergänzen' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Check and extend the existing boot menu'


def run():
    storage = libcalamares.globalstorage
    stage = libcalamares.job.configuration.get('stage')
    if storage.value('firmwareType') != 'efi':
        return None
    try:
        selected = storage.value('windoesnotBootReuse')
        plan = json.loads(selected) if selected else None
        if stage == 'preflight':
            if not plan:
                return None
            if storage.value('packagechooser_bootloader') != 'grub' or storage.value('windoesnotBootInstall') != 'none':
                raise RuntimeError('Inconsistent boot menu selection')
            if storage.value('partitionChoices').get('install') != 'alongside':
                raise RuntimeError('Keeping an existing boot menu requires “Install alongside”. Return to the partition page.')
            if storage.value('luksPassphrase'):
                raise RuntimeError('Reusing a boot menu currently requires an unencrypted installation target. Choose normal GRUB installation for an encrypted target.')
            plan = boot.validate_plan(plan, storage.value('osproberLines') or [])
            order = re.search(r'(?m)^BootOrder:\s*(.*)$', boot.command(['efibootmgr', '-v']))
            if order is None:
                raise RuntimeError('The existing UEFI boot order cannot be read')
            plan['boot_order'] = order[1].strip()
            storage.insert('windoesnotBootReuseValidated', json.dumps(plan))
            return None
        validated = storage.value('windoesnotBootReuseValidated')
        if plan and not validated:
            raise RuntimeError('The existing menu has not passed the pre-installation check')
        plan = json.loads(validated) if validated else None
        target = storage.value('rootMountPoint')
        if not isinstance(target, str) or not target:
            raise RuntimeError('Installation target missing')
        if stage == 'guard':
            # Runs after mounts but before unpackfs can write kernels onto the ESP.
            boot.guard(target, plan)
        elif stage == 'install':
            destination = Path(target).resolve()
            if destination == Path('/') or not (destination / 'etc/windoesnot-image-build').is_file():
                raise RuntimeError('Not a WinDoesNot installation target')
            # Keep the same upstream probe extension available during future
            # grub-mkconfig runs in the installed system as in the live installer.
            hook = Path('/usr/share/windoesnot/iso/os-prober-btrfs')
            installed = destination / 'usr/lib/os-probes/55windoesnot-btrfs'
            boot.atomic_write(installed, hook.read_text())
            installed.chmod(0o755)
            if not plan:
                return None
            # A private GRUB chainloader handles our normal kernel/snapshot hooks.
            # Keep the existing main menu, EFI fallback loader and boot order.
            result = libcalamares.utils.target_env_call([
                'grub-install', '--target=x86_64-efi', '--efi-directory=/boot',
                '--bootloader-id=WinDoesNot', '--no-nvram'])
            if result:
                raise RuntimeError('Could not install the WinDoesNot chainloader')
            if libcalamares.utils.target_env_call(['grub-mkconfig', '-o', '/boot/grub/grub.cfg']):
                raise RuntimeError('Could not generate the WinDoesNot boot menu')
        elif stage == 'finish':
            if not plan:
                return None
            order = re.search(r'(?m)^BootOrder:\s*(.*)$', boot.command(['efibootmgr', '-v']))
            if order is None or order[1].strip() != plan['boot_order']:
                raise RuntimeError('The UEFI boot order changed; the existing menu has not been edited')
            boot.integrate(target, plan)
            record = Path(target) / 'var/lib/windoesnot/boot-menu.json'
            boot.atomic_write(record, json.dumps({'schema_version': 1, 'existing_menu': plan}, indent=2) + '\n')
        else:
            raise RuntimeError('Unknown boot integration stage')
    except Exception as error:
        german = str(storage.value('locale')).startswith('de')
        detail = str(error)
        if german:
            if 'requires “Install alongside”' in detail:
                detail = 'Die Weiterverwendung benötigt „Parallel dazu installieren“. Starte den Installer erneut und wähle diese Option bei der Speicheraufteilung.'
            elif 'Existing Linux boot files would overlap:' in detail:
                detail = 'Auf der gewählten EFI-Systempartition liegen bereits Linux-Startdateien mit gleichen Namen. Sie wurden nicht überschrieben. Verwende eine separate EFI-Systempartition für WinDoesNot.'
            elif 'at least 384 MiB free' in detail:
                detail = 'Die EFI-Systempartition benötigt mindestens 384 MiB freien Platz für die beiden Linux-Kernel und ihre Startdateien. Verwende eine größere oder separate EFI-Systempartition.'
            elif 'Choose the existing menu’s EFI' in detail:
                detail = 'Wähle die EFI-Systempartition des vorhandenen Menüs und erhalte ihren Inhalt. Die gewählte Partition gehört zu einem anderen Startmenü.'
            elif 'unencrypted installation target' in detail:
                detail = 'Die automatische Weiterverwendung unterstützt derzeit unverschlüsselte Zielsysteme. Für ein verschlüsseltes WinDoesNot-Ziel wähle die normale GRUB-Installation.'
            else:
                libcalamares.utils.warning(detail)
                detail = 'Das vorhandene Startmenü konnte nicht unverändert und eindeutig übernommen werden. Die Installation wurde angehalten. Prüfe die Startmenü- und Datenträgerauswahl; technische Einzelheiten stehen im Installationsprotokoll.'
        return ('Startmenü konnte nicht sicher eingerichtet werden' if german else 'Could not safely configure the boot menu',
                detail)
    return None
