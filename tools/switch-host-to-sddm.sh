#!/bin/bash
# Switch this computer's login screen from GDM to SDDM with the WinDoesNot theme.
# Run with sudo from the project checkout. GDM stays installed; the change takes effect
# at the next boot, the running session is not touched.
#
#   sudo tools/switch-host-to-sddm.sh            switch
#   sudo tools/switch-host-to-sddm.sh --rollback back to GDM
#
# If the login screen fails after reboot: Ctrl+Alt+F3, log in, then
#   sudo systemctl disable sddm && sudo systemctl enable gdm && sudo reboot
set -euo pipefail
((EUID == 0)) || { echo 'Bitte mit sudo starten.' >&2; exit 1; }
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
theme=$src/desktop/share/sddm/themes/windoesnot

if [[ ${1:-} == --rollback ]]; then
    systemctl disable sddm.service
    systemctl enable gdm.service
    echo 'Zurück zu GDM. Wirksam nach dem nächsten Neustart.'
    exit 0
fi

[[ -f $theme/metadata.desktop ]] || { echo "Theme fehlt: $theme" >&2; exit 1; }
user=${SUDO_USER:?Bitte mit sudo aus deinem Benutzerkonto starten}

backup=/var/backups/windoesnot-sddm-$(date +%Y%m%d-%H%M%S)
install -d -m700 "$backup"

# A stray, package-less sddm.service would make pacman refuse the installation.
for stray in /usr/lib/systemd/system/sddm.service; do
    if [[ -e $stray ]] && ! pacman -Qqo "$stray" >/dev/null 2>&1; then
        mv "$stray" "$backup/"
        echo "Verwaiste Datei gesichert: $stray"
    fi
done

pacman -S --needed --noconfirm sddm qt6-multimedia-ffmpeg qt6-virtualkeyboard qt6-imageformats xorg-xrandr
[[ -d /usr/share/sddm/themes/windoesnot ]] && cp -a /usr/share/sddm/themes/windoesnot "$backup/theme"
[[ -d /usr/share/sddm/themes/silentsddm ]] && cp -a /usr/share/sddm/themes/silentsddm "$backup/silentsddm-theme"
[[ -f /etc/sddm.conf.d/windoesnot.conf ]] && cp -a /etc/sddm.conf.d/windoesnot.conf "$backup/"

# Theme and the font the greeter needs.
rm -rf /usr/share/sddm/themes/windoesnot.new
cp -a "$theme" /usr/share/sddm/themes/windoesnot.new
chown -R root:root /usr/share/sddm/themes/windoesnot.new
chmod -R u=rwX,go=rX /usr/share/sddm/themes/windoesnot.new
chmod 755 /usr/share/sddm/themes/windoesnot.new/Xsetup
rm -rf /usr/share/sddm/themes/windoesnot
mv /usr/share/sddm/themes/windoesnot.new /usr/share/sddm/themes/windoesnot
install -d /usr/share/fonts/windoesnot
install -m644 "$theme"/fonts/*.ttf /usr/share/fonts/windoesnot/
fc-cache -f /usr/share/fonts/windoesnot >/dev/null

# Optional second theme, selectable in Settings > Background > Anmeldebildschirm.
silent_theme=$src/desktop/share/sddm/themes/silentsddm
if [[ -d $silent_theme ]]; then
    rm -rf /usr/share/sddm/themes/silentsddm.new
    cp -a "$silent_theme" /usr/share/sddm/themes/silentsddm.new
    chown -R root:root /usr/share/sddm/themes/silentsddm.new
    chmod -R u=rwX,go=rX /usr/share/sddm/themes/silentsddm.new
    rm -rf /usr/share/sddm/themes/silentsddm
    mv /usr/share/sddm/themes/silentsddm.new /usr/share/sddm/themes/silentsddm
    install -d /usr/share/fonts/windoesnot-silentsddm
    find "$silent_theme/fonts" -maxdepth 2 -type f \( -iname '*.otf' -o -iname '*.ttf' \) \
        -exec install -m644 -t /usr/share/fonts/windoesnot-silentsddm {} +
    fc-cache -f /usr/share/fonts/windoesnot-silentsddm >/dev/null
fi

# Same greeter setup as the ISO: X11 greeter, keyboard layout applied by Xsetup.
install -d /etc/sddm.conf.d
cat > /etc/sddm.conf.d/windoesnot.conf <<'EOF'
[General]
DisplayServer=x11
[X11]
DisplayCommand=/usr/share/sddm/themes/windoesnot/Xsetup
[Theme]
Current=windoesnot
EOF

# Preselect this user and the Hyprland session the first time.
install -d -o sddm -g sddm /var/lib/sddm
if [[ ! -f /var/lib/sddm/state.conf ]]; then
    printf '[Last]\nSession=/usr/share/wayland-sessions/hyprland.desktop\nUser=%s\n' "$user" > /var/lib/sddm/state.conf
    chown sddm:sddm /var/lib/sddm/state.conf
fi

systemctl disable gdm.service
systemctl enable sddm.service
echo "Fertig. SDDM ist ab dem nächsten Neustart aktiv. Sicherung: $backup"
echo "Zurück zu GDM: sudo $src/tools/switch-host-to-sddm.sh --rollback"
