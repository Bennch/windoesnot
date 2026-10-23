#!/usr/bin/env bash
set -euo pipefail
[[ -f /etc/windoesnot-image-build ]] || { echo 'Not a WinDoesNot installation target' >&2; exit 1; }
install_user=${1:?Missing target username}
[[ "$install_user" =~ ^[a-z_][a-z0-9_.-]*$ ]] || exit 2
getent passwd "$install_user" >/dev/null
# These are live-only; never carry autologin, live services or temporary keys over.
rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
rm -f /etc/polkit-1/rules.d/49-nopasswd_global.rules
rm -f /etc/systemd/system/etc-pacman.d-gnupg.mount
systemctl disable pacman-init.service windoesnot-super-tap@liveuser.service serial-getty@ttyS0.service 2>/dev/null || true
systemctl disable systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service 2>/dev/null || true
# The live image waits for network time before refreshing package keys. An
# installed/offline desktop must not wait for NTP before permitting login.
systemctl disable systemd-time-wait-sync.service 2>/dev/null || true
systemctl enable sddm.service NetworkManager.service bluetooth.service getty@tty1.service
systemctl enable "windoesnot-super-tap@$install_user.service"
install -d -o sddm -g sddm /var/lib/sddm
printf '[Last]\nSession=/usr/share/windoesnot/wayland-sessions/windoesnot.desktop\nUser=%s\n' "$install_user" > /var/lib/sddm/state.conf
chown sddm:sddm /var/lib/sddm/state.conf
ln -sfn /usr/lib/systemd/system/getty@.service /etc/systemd/system/autovt@.service
# Calamares users module copied skel; re-run the idempotent initializer as the user.
runuser -u "$install_user" -- /usr/bin/windoesnot-initialize --adopt-system
# Calamares sets passwords itself; remove the live account's passwordless sudo rule.
rm -f /etc/sudoers.d/g_wheel
printf '%%wheel ALL=(ALL:ALL) ALL\n' > /etc/sudoers.d/windoesnot-wheel
chmod 440 /etc/sudoers.d/windoesnot-wheel
# unpackfs copies the immutable image, not the live session's tmpfs keyring.
# Initialize each installed system independently, entirely offline.
# The preparation job initialized the keyring before bootloader dependencies.
# The finish job removes the live marker after boot maintenance, before snapshots.
rm -f /usr/share/applications/windoesnot-installer.desktop
user_home=$(getent passwd "$install_user" | cut -d: -f6)
rm -f "$user_home/Desktop/windoesnot-installer.desktop"
systemctl set-default graphical.target
