#!/usr/bin/env python3
"""Fail early if an upstream update breaks the offline image contract."""
import argparse
from pathlib import Path
import yaml

parser=argparse.ArgumentParser();parser.add_argument('profile',type=Path);args=parser.parse_args()
p=args.profile;a=p/'airootfs';cal=a/'usr/share/windoesnot/iso/calamares'
assert (cal/'qml').is_symlink() and (cal/'qml').readlink()==Path('/usr/share/calamares/qml')
settings=yaml.safe_load((cal/'settings.conf').read_text())
sequence=next(s['exec'] for s in settings['sequence'] if 'exec' in s)
assert 'unpackfs' in sequence and 'pacstrap' not in sequence and 'netinstall' not in sequence
assert 'windoesnotapps' in settings['sequence'][0]['show']
assert sequence.index('shellprocess') < sequence.index('windoesnotapps_install') < sequence.index('windoesnotfinish') < sequence.index('umount')
pages=settings['sequence'][0]['show']
assert pages.index('keyboard') < pages.index('windoesnotboot') < pages.index('partition')
assert (a/'usr/share/windoesnot/vendor/calamares/src/modules/windoesnotapps/CMakeLists.txt').is_file()
assert (a/'usr/share/windoesnot/vendor/calamares/src/modules/windoesnotapps_install/module.desc').is_file()
assert (a/'usr/share/windoesnot/iso/software/catalog.json').is_file()
assert 'software/prepare.py' in (a/'root/customize_airootfs.sh').read_text()
assert sequence.index('shellprocess@preparetarget')<sequence.index('initcpiocfg')<sequence.index('initcpio')<sequence.index('bootloader')<sequence.index('shellprocess')
assert sequence.index('shellprocess@preparetarget') < sequence.index('windoesnotprepare') < sequence.index('windoesnotsystem') < sequence.index('initcpiocfg')
assert sequence.index('grubcfg') < sequence.index('bootloader')
boot=yaml.safe_load((cal/'modules/bootloader.conf').read_text())
assert boot['efiBootLoader']=='grub' and boot['efiBootLoaderVar']=='packagechooser_bootloader'
partition=yaml.safe_load((cal/'modules/partition.conf').read_text())
assert partition['efiSystemPartition']=='/boot' and partition['efiSystemPartitionSize']=='1024M'
assert '${USER}' in yaml.safe_load((cal/'modules/shellprocess.conf').read_text())['script'][0]['command']
assert '@@USER@@' not in (cal/'modules/shellprocess.conf').read_text()
welcome=yaml.safe_load((cal/'modules/welcome.conf').read_text())
assert 'internet' not in welcome['requirements']['required']
for instance in settings['instances']:
    assert (cal/'modules'/instance['config']).is_file(),instance
for required in ['unpackfs','users','removeuser','partition','bootloader','displaymanager']:
    assert required in sequence,required
packages=set((p/'packages.x86_64').read_text().split())
for required in ['hyprland','quickshell','sddm','linux-cachyos','linux-cachyos-lts','cachyos-calamares-next']:
    assert required in packages,required
assert 'plymouth' in packages
assert 'windoesnot-boot-errors' in yaml.safe_load((cal/'modules/initcpiocfg.conf').read_text())['hooks']['append']
assert 'Theme=windoesnot' in (a/'etc/plymouth/plymouthd.conf').read_text()
assert (a/'usr/share/plymouth/themes/windoesnot/watermark.png').is_file()
assert 'windoesnot-boot-errors' in (a/'etc/mkinitcpio.conf.d/archiso.conf').read_text()
assert (a/'usr/lib/systemd/system/windoesnot-boot-error@.service.d/99-no-recursion.conf').read_text().endswith('OnFailure=\n')
for forbidden in ['plasma-desktop','plasma-workspace','plasma-login-manager','gnome-shell','gdm','cinnamon','xfce4-session','cosmic-session','mate-session-manager','lxqt-session']:
    assert forbidden not in packages,forbidden
for required in ['usr/share/windoesnot/tools/build-components.sh','usr/share/windoesnot/tools/build-image-packages.sh','usr/share/windoesnot/packaging/PKGBUILD.in','usr/share/windoesnot/packaging/version.json','usr/share/windoesnot/iso/prepare-target.sh','usr/share/windoesnot/iso/finalize-install.sh','root/customize_airootfs.sh']:
    assert (a/required).is_file(),required
# The store is built in the image from pinned, hash-verified, vendored sources only.
store=a/'usr/share/windoesnot/store'
store_pkgbuild=(store/'PKGBUILD').read_text()
assert 'SKIP' not in store_pkgbuild and '--frozen' in store_pkgbuild and 'cargo fetch' not in store_pkgbuild
assert sorted(x.name for x in store.glob('*.tar.gz'))==sorted(x for x in store_pkgbuild.split('source=(',1)[1].split(')',1)[0].replace('"',' ').split())
assert (store/'windoesnot-store.install').is_file()
for required in ['appstream','archlinux-appstream-data','rust','clang']:
    assert required in packages,required
image_packages=(a/'usr/share/windoesnot/tools/build-image-packages.sh').read_text()
assert 'check-packages.py" --store' in image_packages and 'CARGO_NET_OFFLINE=true' in image_packages and 'pacman -Rns' in image_packages
# No prebuilt host ABI can leak into a target image.
assert not list((a/'usr/share/windoesnot/desktop').rglob('*.so'))
assert 'build-image-packages.sh' in (a/'root/customize_airootfs.sh').read_text()
assert 'var MAP = {};' in (a/'usr/share/windoesnot/desktop/config/quickshell/default/IconMap.js').read_text()
# All new-user settings come from explicit defaults, not imported private state.
for private in ['settings.txt','calendar_notes.json','copilot-state.json','icons.json','state.lua','host.lua','geometry.lua']:
    hits=[x for x in (a/'usr/share/windoesnot/desktop/config').rglob(private) if 'widgets/weather' not in str(x)]
    assert not hits,private
launcher=(a/'usr/local/bin/windoesnot-installer').read_text()
assert 'pkexec /usr/bin/env' in launcher and 'QT_QPA_PLATFORM=wayland' in launcher
assert '/usr/bin/calamares -c "$configuration"' in launcher
assert 'windoesnot.install=online' in launcher and '--offline' in launcher
for mode,directory in [('offline',cal),('online',cal/'online')]:
    mode_settings=yaml.safe_load((directory/'settings.conf').read_text())
    assert mode_settings['sequence']==settings['sequence']
    for module in ['windoesnotprepare','windoesnotsystem','windoesnotapps_install','windoesnotfinish','windoesnotapps']:
        assert yaml.safe_load((directory/'modules'/(module+'.conf')).read_text())['mode']==mode
    requirements=yaml.safe_load((directory/'modules/welcome.conf').read_text())['requirements']
    assert ('internet' in requirements['required'])==(mode=='online')
grubmenu=(p/'grub/grub.cfg').read_text()
assert 'default=windoesnot-offline' in grubmenu
assert grubmenu.count('windoesnot.install=offline')==3
assert grubmenu.count('windoesnot.install=online')==3
bios=(p/'syslinux/archiso_sys-linux.cfg').read_text()
assert bios.count('windoesnot.install=offline')==2 and bios.count('windoesnot.install=online')==2
assert 'DEFAULT wdn-offline' in (p/'syslinux/archiso_sys.cfg').read_text()
assert 'subject.user === "liveuser"' in (a/'etc/polkit-1/rules.d/49-nopasswd_global.rules').read_text()
assert 'rm -f /etc/polkit-1/rules.d/49-nopasswd_global.rules' in (a/'usr/share/windoesnot/iso/finalize-install.sh').read_text()
# Branded paths must all exist before spending time on an ISO build.
branding = yaml.safe_load((cal / 'branding/windoesnot/branding.desc').read_text())
assert branding['images']['productIcon'] == 'windoesnot-icon-256.png'
assert branding['windowExpanding'] == 'noexpand'
assert yaml.safe_load((cal / 'modules/users.conf').read_text())['hostname']['template'] == '${first}-windoesnot'
for filename in branding['images'].values():
    assert (cal / 'branding/windoesnot' / filename).is_file(), filename
assert 'Current=windoesnot' in (a / 'etc/sddm.conf.d/windoesnot.conf').read_text()
assert (a / 'usr/share/windoesnot/desktop/share/sddm/themes/windoesnot/Main.qml').is_file()
assert (p / 'grub/themes/windoesnot/theme.txt').is_file()
assert (p / 'grub/themes/windoesnot/windoesnot-logo-hell.png').is_file()
assert 'set theme="(${root})/boot/grub/themes/windoesnot/theme.txt"' in (p / 'grub/grub.cfg').read_text()
grub_dropin = (a / 'etc/default/grub.d/90-windoesnot.cfg').read_text()
assert 'GRUB_THEME=' in grub_dropin and 'GRUB_TOP_LEVEL="/boot/vmlinuz-linux-cachyos"' in grub_dropin
assert 'GRUB_DISABLE_OS_PROBER=false' in grub_dropin and 'GRUB_DISABLE_BOOTNEXT=true' in grub_dropin
assert 'Icon=windoesnot' in (a / 'usr/share/applications/windoesnot-installer.desktop').read_text()
print('PASS: online/offline menus and profiles, required bootloader selection/order, desktop packages, sources-only components and clean defaults')
