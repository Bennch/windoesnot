#!/usr/bin/env bash
set -euo pipefail
[[ -f /etc/windoesnot-image-build ]] || { echo 'Not a WinDoesNot installation target' >&2; exit 1; }
install_user=${1:?Missing target username}
[[ "$install_user" =~ ^[a-z_][a-z0-9_.-]*$ ]] || exit 2
getent passwd "$install_user" >/dev/null
# These are live-only; never carry autologin, live services or temporary keys over.
rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
systemctl disable windoesnot-live-language.service 2>/dev/null || true
rm -f /etc/polkit-1/rules.d/49-nopasswd_global.rules
rm -f /etc/systemd/system/etc-pacman.d-gnupg.mount
systemctl disable pacman-init.service windoesnot-super-tap@liveuser.service serial-getty@ttyS0.service 2>/dev/null || true
systemctl disable systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service 2>/dev/null || true
# The live image waits for network time before refreshing package keys. An
# installed/offline desktop must not wait for NTP before permitting login.
systemctl disable systemd-time-wait-sync.service 2>/dev/null || true
systemctl enable sddm.service NetworkManager.service bluetooth.service getty@tty1.service
systemctl enable "windoesnot-super-tap@$install_user.service"
# sddm writes /etc/sddm.conf itself on its first run, with a stray, broken
# [Autologin] Session=hyprland (no matching session, no User=, so autologin
# never actually triggers) that only causes a spurious "Autologin failed"
# log line on every normal start. No package owns this file; drop that
# section so our own /etc/sddm.conf.d/windoesnot.conf is the only source.
[[ -f /etc/sddm.conf ]] && sed -i '/^\[Autologin\]$/,/^$/{/^\[Autologin\]$/d;/^Session=/d}' /etc/sddm.conf
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
find "$user_home" -maxdepth 2 -name windoesnot-installer.desktop -delete
# Installed systems start with the firewall on. Order matters: ufw only touches the netfilter
# state when ENABLED=yes, so rules are written first with ENABLED=no, and ENABLED is switched
# on last. Nothing here may stop the installation, so every step only warns on failure.
if [[ -f /etc/ufw/ufw.conf ]]; then
  sed -i 's/^ENABLED=.*/ENABLED=no/' /etc/ufw/ufw.conf
  # 5353/udp: mDNS, needed for network printer discovery. LocalSend (53317) is not opened yet.
  for rule in 5353/udp; do
    ufw allow "$rule" >/dev/null 2>&1 || echo "Firewall rule $rule was not written" >&2
  done
  sed -i 's/^ENABLED=.*/ENABLED=yes/' /etc/ufw/ufw.conf
  systemctl enable ufw.service 2>/dev/null || echo 'ufw.service could not be enabled' >&2
fi
# Network printer discovery (cups dnssd backend, nss-mdns) needs avahi. cups stays on demand.
systemctl enable avahi-daemon.service 2>/dev/null || echo 'avahi-daemon.service could not be enabled' >&2
systemctl set-default graphical.target
