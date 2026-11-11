#!/usr/bin/env bash
# Install the WinDoesNot dotfiles on Arch Linux / Arch Linux ARM.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
usage() {
    cat <<'HELP'
Usage: tools/install-desktop.sh [--apply] [--skip-deps] [--skip-build]
Without --apply, show the plan without changing anything.
Run as the desktop user; sudo is used only for package/helper installation.
Supports x86_64 and aarch64 Arch-based systems, including Asahi/ALARM.
Existing configuration is backed up. No reboot or live-session reload is performed.
--skip-deps   Use already installed dependencies (also skips system upgrades).
--skip-build  Reuse previously built components for this exact installed Hyprland/Qt.
HELP
}
apply=false; deps=true; build=true
for arg in "$@"; do
    case $arg in
        --apply) apply=true ;;
        --skip-deps) deps=false ;;
        --skip-build) build=false ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; usage; exit 2 ;;
    esac
done
case $(uname -m) in x86_64|aarch64) ;; *) echo 'Unsupported architecture' >&2; exit 1 ;; esac
command -v pacman >/dev/null || { echo 'Requires an Arch-based system.' >&2; exit 1; }
packages=(base-devel git cmake ninja pkgconf lua python python-yaml hyprland quickshell
    qtermwidget labwc wayland-protocols libinput libdrm pixman cairo pango json-c librsvg
    qt6-5compat qt6-svg qt6-multimedia qt6-virtualkeyboard qt6-imageformats qt6-wayland
    qt6-tools syntax-highlighting hyprpaper hyprpicker hyprlock hypridle hyprsunset
    hyprshot firefox firefox-i18n-de firefox-i18n-en-us nautilus nautilus-python polkit-gnome gtk4-layer-shell
    python-gobject python-cairo python-evdev python-requests python-websockets
    python-xlib upower power-profiles-daemon pavucontrol blueman bluez bluez-utils
    nm-connection-editor network-manager-applet swaync wl-clipboard wl-clip-persist
    cliphist xclip jq libnotify libsecret grim slurp xorg-xwayland xorg-xauth
    xorg-xrandr xorg-xsetroot xdg-desktop-portal-hyprland xdg-desktop-portal-gtk
    xdg-user-dirs ttf-jetbrains-mono-nerd ttf-nerd-fonts-symbols noto-fonts-emoji
    adw-gtk-theme papirus-icon-theme curl imagemagick ddcutil brightnessctl mesa-utils vulkan-tools libadwaita gettext)
build_ghostty=false
if pacman -Si ghostty >/dev/null 2>&1; then
    packages+=(ghostty)
elif ! command -v ghostty >/dev/null 2>&1; then
    build_ghostty=true
    echo 'Ghostty: build official source release for this architecture (no repository package).' 
fi
printf 'Architecture: %s\nSource: %s\n' "$(uname -m)" "$project"
printf 'Dependencies: %s\n' "${packages[*]}"
printf 'Install dependencies: %s; build components: %s\n' "$deps" "$build"
$apply || { echo 'Plan only. Add --apply to install.'; exit 0; }
(( EUID != 0 )) || { echo 'Run as your desktop user, not root.' >&2; exit 1; }
command -v sudo >/dev/null || { echo 'sudo is required.' >&2; exit 1; }
cd "$project"
if $deps; then
    # Full upgrade avoids unsupported partial upgrades on rolling Arch systems.
    sudo pacman -Syu --needed "${packages[@]}"
fi
if $build_ghostty; then
    python3 tools/build-ghostty.py --prefix "$HOME/.local"
fi
if $build; then tools/build-components.sh; fi
for artifact in plugins/hyprbars.so plugins/hyprdrag.so LocalTerminal/qmldir bin/snappy-switcher; do
    [[ -f build/components/$artifact ]] || { echo "Missing component: $artifact" >&2; exit 1; }
done
# Refuse binaries from a different installed library set even with --skip-build.
[[ $(cat build/components/BUILD-ARCH.txt) == "$(uname -m)" ]] || { echo "Component architecture mismatch; rebuild first." >&2; exit 1; }
pacman -Q hyprland quickshell qt6-base qtermwidget gcc | diff - build/components/BUILD-PACKAGES.txt
python3 tools/validate-desktop.py
python3 tools/smoke-qml.py
config=${XDG_CONFIG_HOME:-$HOME/.config}
backup="$HOME/Backups/windoesnot-release/$(date +%Y%m%d-%H%M%S)-before-install"
mkdir -p "$backup"
if [[ -d $config ]]; then cp -a "$config" "$backup/config"; fi
if [[ -d $HOME/.local/bin ]]; then cp -a "$HOME/.local/bin" "$backup/bin"; fi
printf 'Configuration backup: %s\n' "$backup"
sudo tools/install-system.sh
WINDOESNOT_SOURCE="$project" desktop/bin/windoesnot-initialize
python3 tools/install-user.py --apply
mkdir -p "$config/hypr/plugins"
for plugin in hyprbars hyprdrag; do
    install -m755 "build/components/plugins/$plugin.so" "$config/hypr/plugins/$plugin.so"
done
mkdir -p "$HOME/.local/share/wayland-sessions"
cat > "$HOME/.local/share/wayland-sessions/windoesnot.desktop" <<SESSION
[Desktop Entry]
Name=WinDoesNot
Comment=WinDoesNot desktop on Hyprland
Exec=/usr/local/bin/windoesnot-session
Type=Application
DesktopNames=Hyprland
SESSION
printf 'Installed. Start windoesnot-session from a TTY after logging out.\nBackup: %s\n' "$backup"
