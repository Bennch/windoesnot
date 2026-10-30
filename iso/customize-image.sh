#!/usr/bin/env bash
# This script runs only in the image chroot created by mkarchiso 91.
set -euo pipefail
[[ -f /etc/windoesnot-image-build ]] || { echo 'Image build marker missing; refusing.' >&2; exit 1; }
# A silent Hyprland bump once broke rendering (0.57's
# quirks.skip_non_kms_dmabuf_formats, see desktop/config/hypr/lua/init.lua,
# 2026-10-30): bars went black and Ghostty SIGSEGV'd, on virtio-gpu only.
# Not a build-blocking check — every ISO gets tested by hand regardless —
# just a loud, hard-to-miss flag in the build log when it's worth testing
# rendering and GTK apps extra carefully.
strip_rebuild_suffix() { local release=${1##*-}; printf '%s-%s\n' "${1%-*}" "${release%%.*}"; }
hyprland_installed=$(pacman -Q hyprland | awk '{print $2}')
hyprland_pinned=$(python3 -c "import json; print(json.load(open('/usr/share/windoesnot/sources.json'))['hyprland']['version'])")
if [[ $(strip_rebuild_suffix "$hyprland_installed") != $(strip_rebuild_suffix "$hyprland_pinned") ]]; then
    printf '\n================================================================\n'
    printf 'HYPRLAND VERSION CHANGED since the last tested build:\n'
    printf '  last confirmed-good (sources.json): %s\n' "$hyprland_pinned"
    printf '  installed in this build:            %s\n' "$hyprland_installed"
    printf 'Test bar/taskbar transparency and GTK apps (Ghostty) carefully.\n'
    printf 'Update sources.json once this build is confirmed good.\n'
    printf '================================================================\n\n'
fi
python3 -c 'import sys; sys.path.insert(0,"/usr/share/windoesnot/iso"); from boot_splash import finish_theme; finish_theme("/")'
# Produce archiso initramfs for both boot-menu kernels, without changing host tools.
for kernel in linux-cachyos linux-cachyos-lts; do
    cat > "/etc/mkinitcpio.d/$kernel.preset" <<EOF
ALL_kver='/boot/vmlinuz-$kernel'
PRESETS=('archiso')
archiso_config='/etc/mkinitcpio.conf.d/archiso.conf'
archiso_image='/boot/initramfs-$kernel.img'
EOF
done
mkinitcpio -P
locale-gen
project=/usr/share/windoesnot
"$project/tools/build-image-boot-language.sh"
"$project/tools/build-image-device-manager.sh"
"$project/tools/build-image-connectivity.sh"
"$project/tools/build-image-packages.sh"
"$project/tools/build-calamares.sh"
# The taskbar/Start menu spawn-and-disown a fresh ghostty process per click;
# GTK single-instance's D-Bus handoff can lose that race and the window
# flashes shut. extras/nautilus/windoesnot-terminal.py already avoids this
# the same way for its own launches.
sed -i 's/--gtk-single-instance=true/--gtk-single-instance=false/' /usr/share/applications/com.mitchellh.ghostty.desktop
# Ghostty's own GTK4/EGL context creation fails outright on virtio-gpu
# (BadMatch), independently of the Hyprland-level quirk above. Shadow the
# real binary via PATH so every launch path (desktop file, taskbar/Start
# menu, the power menu's hardcoded "ghostty" fallback) goes through the
# virtio check, not just one call site. See iso/ghostty-wrapper.sh.
install -Dm755 "$project/iso/ghostty-wrapper.sh" /usr/local/bin/ghostty
# Install application launcher desktop files for images, PDFs, and text editors
install -Dm644 "$project/desktop/share/applications/eog.desktop" /usr/share/applications/eog.desktop
install -Dm644 "$project/desktop/share/applications/evince.desktop" /usr/share/applications/evince.desktop
# Version-matched signed optional apps; no online access needed during installation.
python3 "$project/iso/software/prepare.py"
# Bootstrap both skel and the live account using the exact shared code/defaults.
HOME=/etc/skel XDG_CONFIG_HOME=/etc/skel/.config XDG_STATE_HOME=/etc/skel/.local/state /usr/bin/windoesnot-initialize
cp -a /etc/skel/. /home/liveuser/
chown -R liveuser:liveuser /home/liveuser
systemctl disable sddm.service 2>/dev/null || true
systemctl disable systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service 2>/dev/null || true
systemctl enable getty@tty1.service
ln -sfn /usr/lib/systemd/system/getty@.service /etc/systemd/system/autovt@.service
systemctl enable windoesnot-super-tap@liveuser.service
# A serial console makes VM boot failures inspectable without a working GPU.
systemctl enable serial-getty@ttyS0.service
# Re-establish our offline settings after distro package hooks have run.
mkdir -p /etc/windoesnot-calamares
cp -a /usr/share/windoesnot/iso/calamares/. /etc/windoesnot-calamares/
python3 "$project/tools/check-image-installer.py"
printf 'WinDoesNot development image\n' > /etc/issue
pacman -Q > /usr/share/windoesnot/IMAGE-PACKAGES.txt
