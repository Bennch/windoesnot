#!/usr/bin/env python3
"""Run only inside an image-builder chroot, never on the installed desktop."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SOURCE = Path('/files/windoesnot-image')


def main():
    if not Path('/etc/windoesnot-image-build').is_file() or not Path('/boot/efi/.builder').exists():
        raise SystemExit('An isolated Asahi image-build chroot is required')
    spec = importlib.util.spec_from_file_location('branding', SOURCE / 'tools/brand-asahi.py')
    branding = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(branding)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        branding.stage(root, Path('/etc/default/grub').read_text(),
                       Path('/etc/mkinitcpio.conf').read_text(), 'alarm\n',
                       Path('/etc/hosts').read_text())
        shutil.copytree('/usr/share/plymouth/themes/spinner', root / 'usr/share/plymouth/themes/spinner')
        branding.splash.finish_theme(root)
        shutil.rmtree(root / 'usr/share/plymouth/themes/spinner')
        # Replace /etc/os-release itself, rather than writing through the seed's
        # symlink into the base distribution's package-owned /usr/lib/os-release.
        for source in sorted(root.rglob('*')):
            if source.is_file():
                branding.atomic_copy(source, Path('/') / source.relative_to(root))
    firstboot = SOURCE / 'firstboot'
    dest = Path('/usr/share/calamares-windoesnotmac')
    shutil.copytree(firstboot / 'calamares', dest)
    custom = dest / 'modules/windoesnotmacfinish'
    shutil.copytree(custom, '/usr/lib/calamares/modules/windoesnotmacfinish')
    brand = dest / 'branding/windoesnotmac'
    for name in ('windoesnot-icon-256.png', 'windoesnot-logo-hell.png'):
        shutil.copy2(branding.BRAND / name, brand / name)
    shutil.copy2(SOURCE / 'iso/branding/dark.qss', brand / 'stylesheet.qss')
    # The shared stylesheet's checkmark must resolve inside this branding folder.
    p = brand / 'stylesheet.qss'
    p.write_text(p.read_text().replace('/usr/share/windoesnot/iso/branding/check.svg',
                                     str(brand / 'check.svg')))
    shutil.copy2(SOURCE / 'iso/branding/check.svg', brand / 'check.svg')
    shutil.copy2(firstboot / 'firstboot', '/usr/lib/windoesnot/firstboot')
    Path('/usr/lib/windoesnot/firstboot').chmod(0o755)
    shutil.copy2(firstboot / 'windoesnot-firstboot.service', '/usr/lib/systemd/system/')
    state = Path('/var/lib/windoesnot')
    state.mkdir(parents=True, exist_ok=True)
    (state / 'firstboot-pending').write_text('WinDoesNotMac\n')
    sddm = Path('/etc/sddm.conf.d/50-windoesnotmac.conf')
    sddm.parent.mkdir(parents=True, exist_ok=True)
    sddm.write_text('[Theme]\nCurrent=windoesnot\n[Users]\nHideUsers=alarm\n')
    # Do not let SDDM bypass an unsuccessful first-boot service.
    gate = Path('/etc/systemd/system/sddm.service.d/50-firstboot.conf')
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.write_text('[Unit]\nRequires=windoesnot-firstboot.service\nAfter=windoesnot-firstboot.service\n')
    subprocess.run(['systemctl', 'enable', 'windoesnot-firstboot.service', 'sddm.service',
                    'NetworkManager.service', 'bluetooth.service'], check=True)
    subprocess.run(['systemctl', 'set-default', 'graphical.target'], check=True)
    # The seed archive's default account must never be shipped in our image.
    if subprocess.run(['getent', 'passwd', 'alarm'], stdout=subprocess.DEVNULL).returncode == 0:
        subprocess.run(['userdel', '-r', 'alarm'], check=True)
    subprocess.run(['passwd', '-l', 'root'], check=True)
    subprocess.run(['mkinitcpio', '-P'], check=True)
    # Blank identity: systemd generates a fresh machine ID on the installed Mac.
    Path('/etc/machine-id').write_text('')
    Path('/var/lib/dbus/machine-id').unlink(missing_ok=True)
    Path('/var/lib/dbus').mkdir(parents=True, exist_ok=True)
    Path('/var/lib/dbus/machine-id').symlink_to('/etc/machine-id')
    for p in Path('/etc/ssh').glob('ssh_host_*'):
        p.unlink()
    Path('/etc/windoesnot-image-build').unlink()


if __name__ == '__main__':
    main()
