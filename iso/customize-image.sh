#!/usr/bin/env bash
# This script runs only in the image chroot created by mkarchiso 91.
set -euo pipefail
[[ -f /etc/windoesnot-image-build ]] || { echo 'Image build marker missing; refusing.' >&2; exit 1; }
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
"$project/tools/build-image-packages.sh"
"$project/tools/build-calamares.sh"
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
