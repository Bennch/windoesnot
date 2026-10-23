#!/usr/bin/env python3
"""Generate an isolated archiso profile; never mutate upstream or host config."""
import argparse
import hashlib
import json
import tempfile
import shlex
import re
from pathlib import Path
import shutil
import subprocess
import sys
import yaml
from live_boot_menu import grub_modes, syslinux_modes

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'iso'))
from boot_splash import KERNEL_PARAMS, add_hook, quiet_commandline, stage as stage_boot_splash
DROP = set((ROOT / 'iso/packages-remove.txt').read_text().split())
BUILD_ONLY = {line.strip() for line in (ROOT / 'iso/packages-build-only.txt').read_text().splitlines() if line.strip() and not line.startswith('#')}

def write(path, text, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if executable:
        path.chmod(0o755)

def stage_store(pin, target):
    """Stage the WinDoesNot Store from its exact pinned commit for the in-image build.

    The archive and PKGBUILD come only from git objects of that commit, so
    uncommitted changes in store/ never reach an image, and the archive hash
    replaces the upstream PKGBUILD's SKIP.
    """
    repo = ROOT / pin.get('path', 'store')
    commit = pin['commit']
    def show(name):
        return subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{name}'], text=True)
    if subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', f'{commit}^{{commit}}']).returncode:
        raise SystemExit(f'Store pin not found in {repo}: {commit}')
    version = re.search(r'^version = "([^"]+)"', show('Cargo.toml'), re.M).group(1)
    pkgbuild = show('PKGBUILD')
    if f'pkgver={version}' not in pkgbuild:
        raise SystemExit(f'Store PKGBUILD does not match Cargo version {version}')
    target.mkdir(parents=True)
    archive = target / f'windoesnot-store-{version}.tar.gz'
    subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar.gz', f'--prefix=windoesnot-store-{version}/',
                    '-o', str(archive), commit], check=True)
    # The image chroot has no network: vendor the locked crates here, as a
    # reproducible archive (sorted, fixed mtime/owner, gzip without timestamp).
    vendor = target / f'windoesnot-store-{version}-vendor.tar.gz'
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        subprocess.run(['tar', '-xzf', str(archive), '-C', str(temp)], check=True)
        source = temp / f'windoesnot-store-{version}'
        subprocess.run(['cargo', 'vendor', '--locked', '--versioned-dirs', '--quiet', str(temp / 'vendor')],
                       cwd=source, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(f"tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C {shlex.quote(str(temp))} -cf - vendor"
                       f" | gzip -n > {shlex.quote(str(vendor))}", shell=True, check=True)
    digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (archive, vendor)]
    pkgbuild = re.sub(r'^source=.*$', f'source=("{archive.name}" "{vendor.name}")', pkgbuild, count=1, flags=re.M)
    pkgbuild = re.sub(r"^sha256sums=.*$", f"sha256sums=('{digests[0]}' '{digests[1]}')", pkgbuild, count=1, flags=re.M)
    offline_prepare = (
        'prepare() {\n'
        '  cd "$pkgname-$pkgver"\n'
        '  mkdir -p .cargo\n'
        '  printf \'[source.crates-io]\\nreplace-with = "vendored-sources"\\n[source.vendored-sources]\\ndirectory = "%s"\\n\' "$srcdir/vendor" > .cargo/config.toml\n'
        '}\n')
    pkgbuild, count = re.subn(r'^prepare\(\) \{\n.*?^\}\n', lambda _: offline_prepare, pkgbuild, count=1, flags=re.M | re.S)
    if count != 1:
        raise SystemExit('Store PKGBUILD has no prepare() to replace')
    # Same flags for build and check, so the tests reuse the build; the remap
    # keeps build directory paths out of the binaries.
    remap = 'RUSTFLAGS="${RUSTFLAGS:-} --remap-path-prefix=$srcdir=/usr/src/debug/$pkgname"'
    for step in ('build', 'test'):
        old = f'cargo {step} --release --locked'
        if pkgbuild.count(old) != 1:
            raise SystemExit(f'Store PKGBUILD lacks: {old}')
        pkgbuild = pkgbuild.replace(old, f'{remap} cargo {step} --release --frozen')
    write(target / 'PKGBUILD', pkgbuild)
    write(target / 'windoesnot-store.install', show('windoesnot-store.install'))
    return {'version': version, 'commit': commit, 'archive_sha256': digests[0], 'vendor_sha256': digests[1]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources-root', type=Path, default=ROOT / 'upstream')
    parser.add_argument('--source-manifest', type=Path, default=ROOT / 'sources.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/profile')
    args = parser.parse_args()
    profile = args.output.resolve()
    if profile == ROOT or ROOT not in profile.parents or profile.name in ['desktop', 'upstream']:
        raise SystemExit('Profile output must be a dedicated directory below this project')
    if profile.exists():
        raise SystemExit(f'Output already exists: {profile}; use a new build directory')
    pins=json.loads(args.source_manifest.read_text())
    for name in ['cachyos-live-iso','cachyos-calamares']:
        actual=subprocess.check_output(['git','-C',str(args.sources_root/name),'rev-parse','HEAD'],text=True).strip()
        if actual != pins[name]['commit']:raise SystemExit(f'Upstream pin mismatch: {name}')
        if subprocess.check_output(['git','-C',str(args.sources_root/name),'status','--porcelain'],text=True).strip():raise SystemExit(f'Upstream worktree has local changes: {name}')
    upstream = args.sources_root / 'cachyos-live-iso/archiso'
    shutil.copytree(upstream, profile, symlinks=True)
    a = profile / 'airootfs'
    packages = {line.strip() for line in (upstream / 'packages_desktop.x86_64').read_text().splitlines() if line.strip() and not line.startswith('#')}
    packages -= DROP
    packages |= set((ROOT / 'iso/packages-extra.txt').read_text().split())
    packages |= BUILD_ONLY
    packages = {p for p in packages if '-zfs' not in p and p!='zfs-utils'}
    write(profile / 'packages.x86_64', '\n'.join(sorted(packages)) + '\n')
    # Profile selection is explicit; no upstream online/Plasma package choices.
    for p in profile.glob('packages_*.x86_64'):
        p.unlink()
    payload = a / 'usr/share/windoesnot'
    shutil.copytree(ROOT / 'desktop', payload / 'desktop', ignore=shutil.ignore_patterns('import-manifest.json', '.*', '__pycache__'))
    shutil.copytree(ROOT / 'tools', payload / 'tools', ignore=shutil.ignore_patterns('__pycache__','import-desktop.py'))
    shutil.copytree(ROOT / 'iso', payload / 'iso', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ROOT / 'packaging', payload / 'packaging')
    for name in ['LICENSE', 'THIRD-PARTY.md']:
        shutil.copy2(ROOT / name, payload / name)
    store =stage_store(pins['windoesnot-store'], payload / 'store')
    shutil.copytree(args.sources_root/'cachyos-calamares',payload/'vendor/calamares',ignore=shutil.ignore_patterns('.git','__pycache__','build'))
    # Keep the upstream checkout untouched; add our modules only to the generated build copy.
    shutil.copytree(ROOT / 'iso/modules', payload / 'vendor/calamares/src/modules', dirs_exist_ok=True)
    shutil.copy2(args.source_manifest, payload / 'sources.json')
    # Win11 assets already used by the shell; preserve their accompanying metadata.
    icon_source = ROOT / 'desktop/config/quickshell/default/img/Win11-dark'
    shutil.copytree(icon_source, a / 'usr/share/icons/Win11', dirs_exist_ok=True)
    write(a / 'usr/share/backgrounds/windoesnot/wallpaper.svg', '<svg xmlns="http://www.w3.org/2000/svg" width="2560" height="1440"><defs><radialGradient id="g"><stop stop-color="#60372a"/><stop offset="1" stop-color="#111316"/></radialGradient></defs><path fill="url(#g)" d="M0 0h2560v1440H0z"/><path d="M0 1180 920 660l720 330 920-650" fill="none" stroke="#fe6f2d" stroke-opacity=".25" stroke-width="2"/></svg>\n')
    write(a / 'etc/windoesnot-image-build', 'development\n')
    write(a/'etc/hostname','windoesnot-live\n')
    # German live preview; Calamares applies the chosen language to the target.
    write(a/'etc/locale.conf','LANG=de_DE.UTF-8\n')
    write(a/'etc/locale.gen','de_DE.UTF-8 UTF-8\nen_US.UTF-8 UTF-8\n')
    # Passwordless administration belongs only to the disposable live account.
    write(a/'etc/polkit-1/rules.d/49-nopasswd_global.rules', 'polkit.addRule(function(action, subject) {\n    if (subject.user === "liveuser" && subject.isInGroup("wheel")) {\n        return polkit.Result.YES;\n    }\n});\n')
    # Do not start any other graphical session in the live image.
    for name in ['etc/plasmalogin.conf', 'etc/plasmalogin.conf.d', 'etc/skel/.config', 'etc/skel/.local', 'etc/systemd/system/display-manager.service','etc/systemd/system/multi-user.target.wants/sshd.service','etc/systemd/system/multi-user.target.wants/systemd-networkd.service','etc/systemd/system/sockets.target.wants/systemd-networkd.socket']:
        p=a/name
        if p.is_symlink() or p.is_file(): p.unlink()
        elif p.is_dir(): shutil.rmtree(p)
    write(a / 'etc/skel/.bash_profile', 'if [[ $(tty) == /dev/tty1 && -z ${WAYLAND_DISPLAY:-} && $(id -un) == liveuser ]]; then\n    mkdir -p "$HOME/.local/state/windoesnot"\n    windoesnot-session >"$HOME/.local/state/windoesnot/live-session.log" 2>&1\n    session_status=$?\n    if (( session_status != 0 )); then cat "$HOME/.local/state/windoesnot/live-session.log"; read -r -p "Desktop start failed. Press Enter to return to login."; fi\n    exit "$session_status"\nfi\n[[ -f ~/.bashrc ]] && . ~/.bashrc\n')
    write(a / 'etc/skel/.hushlogin', '')
    write(a / 'etc/systemd/system/getty@tty1.service.d/autologin.conf', '[Service]\nExecStart=\nExecStart=-/usr/bin/agetty --noreset --noclear --noissue --skip-login --autologin liveuser - ${TERM}\n')
    write(a / 'etc/sddm.conf.d/windoesnot.conf', '[General]\nDisplayServer=x11\n[Theme]\nCurrent=windoesnot\n[Wayland]\nSessionDir=/usr/share/windoesnot/wayland-sessions\n[Autologin]\nSession=windoesnot.desktop\n')
    # Explicit mode selection keeps the same native ABI in both installation paths.
    launch=(ROOT / 'iso/windoesnot-installer').read_text()
    write(a / 'usr/local/bin/windoesnot-installer', launch, True)
    write(a / 'usr/local/bin/calamares-online.sh', launch, True)
    write(a / 'usr/share/applications/windoesnot-installer.desktop', '[Desktop Entry]\nType=Application\nName=Install WinDoesNot\nName[de]=WinDoesNot installieren\nExec=windoesnot-installer\nIcon=windoesnot\nTerminal=false\nCategories=System;\n')
    write(a / 'etc/skel/Desktop/windoesnot-installer.desktop', (a / 'usr/share/applications/windoesnot-installer.desktop').read_text(), True)
    write(a / 'etc/xdg/xdg-desktop-portal/hyprland-portals.conf', '[preferred]\ndefault=hyprland;gtk\norg.freedesktop.impl.portal.FileChooser=gtk\n')
    # Use supported distro hooks to generate installed initramfs without archiso hooks.
    write(a / 'etc/mkinitcpio-windoesnot.conf', add_hook('MODULES=()\nBINARIES=()\nFILES=()\nHOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck)\n'))
    stage_boot_splash(a, ROOT/'iso/boot-splash', ROOT/'desktop/config/quickshell/default/img/brand/windoesnot-logo-hell.png')
    live_hooks=a/'etc/mkinitcpio.conf.d/archiso.conf'
    live_hooks.write_text(add_hook(live_hooks.read_text().replace('modconf memdisk','modconf kms memdisk')))
    cal = payload / 'iso/calamares'; cal.mkdir(parents=True)
    (cal/'qml').symlink_to('/usr/share/calamares/qml',target_is_directory=True)
    modules = args.sources_root / 'cachyos-calamares/src/modules'
    settings = yaml.safe_load((args.sources_root / 'cachyos-calamares/settings_offline.conf').read_text())
    settings['branding']='windoesnot'
    branding=yaml.safe_load((args.sources_root/'cachyos-calamares/src/branding/cachyos/branding.desc').read_text())
    branding.update(componentName='windoesnot',sidebar='widget',slideshow='show.qml',slideshowAPI=2,windowSize='1000px,600px',
                    # Normal expansion resizes past the tiled/reserved area; scroll the summary instead.
                    windowExpanding='noexpand')
    branding['strings'].update(productName='WinDoesNot',shortProductName='WinDoesNot',version='0.1-dev',shortVersion='0.1-dev',versionedName='WinDoesNot 0.1-dev',shortVersionedName='WinDoesNot',bootloaderEntryName='WinDoesNot',homeUrl='',supportUrl='',knownIssuesUrl='',releaseNotesUrl='',donateUrl='')
    branding['images']={'productLogo':'windoesnot-icon-256.png', 'productIcon':'windoesnot-icon-256.png', 'productWelcome':'windoesnot-logo-dunkel.png'}
    branding['style']={'SidebarBackground':'#202024','SidebarText':'#eeeeee','SidebarTextCurrent':'#ffffff','SidebarBackgroundCurrent':'#fe6f2d'}
    branding.pop('uploadServer',None)
    shutil.copytree(ROOT/'iso/branding',cal/'branding/windoesnot')
    brand = ROOT / 'desktop/config/quickshell/default/img/brand'
    for name in ['windoesnot-logo-hell.png', 'windoesnot-logo-dunkel.png', 'windoesnot-icon-256.png']:
        shutil.copy2(brand / name, cal / 'branding/windoesnot' / name)
    write(cal/'branding/windoesnot/branding.desc',yaml.safe_dump(branding,sort_keys=False))
    settings['instances'] = [{'id':'preparetarget','module':'shellprocess','config':'shellprocess-preparetarget.conf'}]
    execution = next(x['exec'] for x in settings['sequence'] if 'exec' in x)
    execution[:] = [x for x in execution if x not in ['zfs','zfshostid','packages@offline','shellprocess@before']]
    (cal / 'modules').mkdir(exist_ok=True)
    needed = set(execution) | {'welcome','keyboard','locale','partition','users','finished','summary'}
    execution.insert(execution.index('initcpiocfg'), 'shellprocess@preparetarget')
    execution.insert(execution.index('initcpiocfg'), 'windoesnotprepare')
    execution.insert(execution.index('bootloader'), 'grubcfg')
    needed.add('grubcfg')
    pages = next(x['show'] for x in settings['sequence'] if 'show' in x)
    pages.insert(pages.index('partition'), 'windoesnotboot')
    pages.insert(pages.index('users'), 'windoesnotapps')
    # The finalizer has initialized the target keyring before offline app installation.
    execution.insert(execution.index('shellprocess') + 1, 'windoesnotapps_install')
    execution.insert(execution.index('windoesnotapps_install') + 1, 'windoesnotfinish')
    for name in needed:
        p = modules / name / f'{name}.conf'
        if p.exists(): shutil.copy2(p, cal / 'modules' / p.name)
    def cfg(name, data): write(cal / 'modules' / name, yaml.safe_dump(data, sort_keys=False))
    write(cal / 'settings.conf', yaml.safe_dump(settings, sort_keys=False))
    partition=yaml.safe_load((modules/'partition/partition.conf').read_text())
    # Keep both kernels/initramfs on FAT. GRUB 2.16 in the tested target cannot
    # read these identical kernels reliably from Btrfs (premature end of file).
    partition.update(efiSystemPartition='/boot',efiSystemPartitionSize='1024M',availableFileSystemTypes=['btrfs','xfs','ext4','f2fs'])
    partition.pop('bootloaderOverrides',None)
    cfg('partition.conf',partition)
    users=yaml.safe_load((modules/'users/users.conf').read_text())
    # Upstream suggests "cachyos-${cpu}"; derive a branded name from the user's first name.
    users['hostname']['template']='${first}-windoesnot'
    cfg('users.conf',users)
    cfg('windoesnotboot.conf', {})
    cfg('windoesnotapps.conf', {'catalog':'/usr/share/windoesnot/iso/software/catalog.json', 'mode':'offline'})
    for job in ['windoesnotprepare','windoesnotapps_install','windoesnotfinish']:
        cfg(job + '.conf', {'mode':'offline'})
    locale=yaml.safe_load((modules/'locale/locale.conf').read_text())
    locale['geoip']={'style':'none'}
    locale['useSystemTimezone']=True
    cfg('locale.conf',locale)
    cfg('displaymanager.conf', {'displaymanagers':['sddm'], 'sysconfigSetup':False, 'sddm':{'configuration_file':'/etc/sddm.conf'}})
    cfg('shellprocess-preparetarget.conf', {'dontChroot':False,'timeout':30,'script':['/usr/share/windoesnot/iso/prepare-target.sh']})
    cfg('shellprocess.conf', {'dontChroot':False,'timeout':120,'script':[{'command':'/usr/share/windoesnot/iso/finalize-install.sh "${USER}"','timeout':120}]})
    cfg('services-systemd.conf', {'units':[{'name':n,'action':'enable','mandatory':False} for n in ['NetworkManager','bluetooth','systemd-timesyncd','fstrim.timer','sddm']]})
    cfg('initcpiocfg.conf', {'useSystemdHook':True,'source':'/etc/mkinitcpio-windoesnot.conf','hooks':{'append':['windoesnot-boot-errors'],'remove':['archiso','archiso_loop_mnt','archiso_pxe_common','archiso_pxe_nbd','archiso_pxe_http','archiso_pxe_nfs']}})
    cfg('initcpio.conf', {'kernel':'all','be_unsafe':False})
    unpack = yaml.safe_load((modules / 'unpackfs/unpackfs.conf').read_text())
    unpack['unpack'].append({'source':'/run/archiso/bootmnt/arch/boot/x86_64/vmlinuz-linux-cachyos-lts','sourcefs':'file','destination':'/boot/vmlinuz-linux-cachyos-lts'})
    cfg('unpackfs.conf', unpack)
    boot = yaml.safe_load((modules / 'bootloader/bootloader.conf').read_text())
    boot['efiBootLoaderVar']='packagechooser_bootloader'
    boot.update(efiBootLoader='grub',efiBootloaderId='WinDoesNot',installEFIFallback=True)
    boot['kernelParams']=[p for p in KERNEL_PARAMS if p!='splash']  # Upstream adds splash when Plymouth is present.
    boot.pop('limineSplashLogo',None)
    cfg('bootloader.conf', boot)
    grub = yaml.safe_load((modules / 'grubcfg/grubcfg.conf').read_text())
    grub['kernel_params']=[p for p in KERNEL_PARAMS if p!='splash']+['nowatchdog','nvme_load=YES']
    grub['defaults'].update(GRUB_THEME='/boot/grub/themes/windoesnot/theme.txt',GRUB_DISABLE_BOOTNEXT=True)
    cfg('grubcfg.conf',grub)
    welcome = yaml.safe_load((modules / 'welcome/welcome.conf').read_text()); welcome['requirements']['requiredStorage']=30;welcome['requirements']['requiredRam']=3
    welcome['requirements']['check']=[x for x in welcome['requirements']['check'] if x!='internet']
    welcome['requirements']['required']=[x for x in welcome['requirements']['required'] if x!='internet'];welcome['geoip']={'style':'none'}
    cfg('welcome.conf', welcome)
    # Online downloads the exact ISO package snapshot; no rolling partial upgrade.
    online = cal / 'online'
    online.mkdir()
    (online / 'qml').symlink_to('/usr/share/calamares/qml',target_is_directory=True)
    (online / 'branding').symlink_to('../branding',target_is_directory=True)
    shutil.copytree(cal / 'modules', online / 'modules')
    write(online / 'settings.conf',yaml.safe_dump(settings,sort_keys=False))
    for job in ['windoesnotprepare','windoesnotapps_install','windoesnotfinish','windoesnotapps']:
        config=yaml.safe_load((online / 'modules' / (job+'.conf')).read_text())
        config['mode']='online'
        write(online / 'modules' / (job+'.conf'),yaml.safe_dump(config,sort_keys=False))
    welcome['requirements']['check']=list(dict.fromkeys(welcome['requirements']['check']+['internet']))
    welcome['requirements']['required']=list(dict.fromkeys(welcome['requirements']['required']+['internet']))
    write(online / 'modules/welcome.conf',yaml.safe_dump(welcome,sort_keys=False))
    shutil.copy2(ROOT / 'iso/customize-image.sh', a / 'root/customize_airootfs.sh')
    # mkarchiso applies these modes even when copied from a normal user's checkout.
    p=profile/'profiledef.sh'; t=p.read_text().replace('iso_name="cachyos"','iso_name="windoesnot"').replace('COS_','WDN_').replace('iso_publisher="CachyOS <https://cachyos.org>"','iso_publisher="WinDoesNot"').replace('iso_application="CachyOS Live/Rescue DVD"','iso_application="WinDoesNot Hyprland Live and Offline Installer"').replace("airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86' '-b' '1M' '-Xdict-size' '1M')", "airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '8' '-b' '1M')")
    t+='\nfile_permissions["/root/customize_airootfs.sh"]="0:0:755"\n'
    t+='file_permissions["/usr/lib/windoesnot/boot-error"]="0:0:755"\n'
    for f in [a/'usr/local/bin/windoesnot-installer',a/'etc/skel/Desktop/windoesnot-installer.desktop',payload/'iso/finalize-install.sh',payload/'iso/prepare-target.sh',payload/'tools/build-components.sh']:
        t+=f'file_permissions["/{f.relative_to(a)}"]="0:0:755"\n'
    for f in payload.rglob('*'):
        if f.is_file() and f.stat().st_mode & 0o111:
            t+=f'file_permissions["/{f.relative_to(a)}"]="0:0:755"\n'
    p.write_text(t)
    # Build dependency resolution uses an independent DB, generic x86-64 repos.
    conf=(profile/'pacman.conf').read_text().replace('Include = /etc/pacman.d/mirrorlist','Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch')
    write(profile/'pacman.conf',conf)
    write(a/'etc/pacman.conf',conf)
    for f in (profile/'grub').rglob('*.cfg') if (profile/'grub').exists() else []:
        f.write_text(f.read_text().replace('CachyOS','WinDoesNot').replace('CACHYOS_VERSION="GIT"','CACHYOS_VERSION="0.1-dev"').replace('copytoram=auto','copytoram=n').replace('nvme_load=yes','nvme_load=yes console=tty0 console=ttyS0,115200n8'))
    # Brand only the generated image, leaving upstream and the host bootloader alone.
    theme = profile / 'grub/themes/windoesnot'
    shutil.copytree(ROOT / 'desktop/share/grub/themes/windoesnot', theme)
    boot_cfg = profile / 'grub/grub.cfg'
    boot_cfg.write_text(grub_modes(boot_cfg.read_text()).replace('set gfxmode="auto"', 'set gfxmode="1280x800,1024x768,800x600,auto"').replace('    terminal_output gfxterm', '    terminal_output gfxterm\n    insmod png\n    insmod gfxmenu\n    if [ -f "(${root})/boot/grub/themes/windoesnot/theme.txt" ]; then\n        set theme="(${root})/boot/grub/themes/windoesnot/theme.txt"\n    fi'))
    # Upstream's grubcfg defaults are absent from the offline sequence: keep stable before LTS
    # and detect Windows via os-prober. GRUB 2.16 BootNext would list PXE/HTTP/shell entries.
    write(a / 'etc/default/grub.d/90-windoesnot.cfg', 'GRUB_THEME="/boot/grub/themes/windoesnot/theme.txt"\nGRUB_TOP_LEVEL="/boot/vmlinuz-linux-cachyos"\nGRUB_DISABLE_OS_PROBER=false\nGRUB_DISABLE_BOOTNEXT=true\n')
    # BIOS vesamenu needs a flattened 640x480 background. Render the supplied
    # PNG through an SVG layout; never stretch the wordmark with the screen.
    import base64
    png = base64.b64encode((brand / 'windoesnot-logo-hell.png').read_bytes()).decode()
    svg = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="640" height="480"><rect width="640" height="480" fill="#141414"/><image x="80" y="28" width="480" height="90" preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,' + png + '"/></svg>'
    subprocess.run(['rsvg-convert', '-o', str(profile / 'syslinux/splash.png')], input=svg.encode(), check=True)
    for cfg_path in (profile / 'syslinux').glob('*.cfg'):
        cfg_path.write_text(cfg_path.read_text().replace('CachyOS', 'WinDoesNot').replace('#9033ccff', '#fffe6f2d'))
    bios=profile/'syslinux/archiso_sys-linux.cfg'
    bios.write_text(syslinux_modes(bios.read_text()))
    bios=profile/'syslinux/archiso_sys.cfg'
    bios.write_text(bios.read_text().replace('DEFAULT arch64','DEFAULT wdn-offline'))
    for directory,pattern in [('grub',r'^(\s*linux )(.*)$'),('syslinux',r'^(APPEND )(.*)$')]:
        for menu in (profile/directory).glob('*.cfg'):
            menu.write_text(re.sub(pattern,lambda match:match.group(1)+quiet_commandline(match.group(2)),menu.read_text(),flags=re.M))
    report={'sources':pins,'store':store,'removed_packages':sorted(DROP),'added_packages':sorted((ROOT/'iso/packages-extra.txt').read_text().split()),'build_only_packages':sorted(BUILD_ONLY),'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'overlays':{},'boot_splash':{'kernel_parameters':KERNEL_PARAMS,'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'iso/boot_splash.py',*sorted((ROOT/'iso/boot-splash').iterdir())] if path.is_file()}}}
    for f in (payload/'iso/calamares').rglob('*'):
        if f.is_file():report['overlays'][str(f.relative_to(a))]=hashlib.sha256(f.read_bytes()).hexdigest()
    write(profile/'PATCH-MANIFEST.json',json.dumps(report,indent=2)+'\n')
    subprocess.run(['python3',str(ROOT/'tools/check-profile.py'),str(profile)],check=True)
    print(profile)

if __name__=='__main__': main()
