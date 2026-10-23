#!/usr/bin/env bash
# Calamares target chroot, before initcpiocfg/initcpio.
set -euo pipefail
[[ -f /etc/windoesnot-image-build ]] || exit 1
# Keep the installed root owned by root. Its mode is managed by the distro's
# /usr/lib/tmpfiles.d/root.conf (currently 0555); do not override that policy.
chown root:root /
sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="WinDoesNot"/' /etc/default/grub
rm -f /etc/mkinitcpio.conf.d/archiso.conf /etc/mkinitcpio.d/linux.preset
for kernel in linux-cachyos linux-cachyos-lts; do
    cat > "/etc/mkinitcpio.d/$kernel.preset" <<EOF
ALL_config='/etc/mkinitcpio.conf'
ALL_kver='/boot/vmlinuz-$kernel'
PRESETS=('default')
default_image='/boot/initramfs-$kernel.img'
EOF
done

# Copy the packaged theme onto the EFI partition before grub-mkconfig runs.
# This also keeps boot graphics readable independently of the root filesystem.
install -d /boot/grub/themes/windoesnot
cp -a /usr/share/grub/themes/windoesnot/. /boot/grub/themes/windoesnot/
