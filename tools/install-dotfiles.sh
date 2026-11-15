#!/usr/bin/env bash
set -euo pipefail

lang=${LANG:-en}
[[ $lang == de* ]] && lang=de || lang=en
check=0 dry=0 yes=0 no_aur=0
while (($#)); do
    case $1 in
        --lang) (($# >= 2)) || { printf '%s\n' 'Missing language' >&2; exit 2; }; lang=$2; shift ;;
        --check) check=1 ;;
        --dry-run) dry=1 ;;
        --yes) yes=1 ;;
        --no-aur) no_aur=1 ;;
        --help) printf '%s\n' 'Usage: install-dotfiles.sh [--lang de|en] [--check] [--dry-run] [--yes] [--no-aur] [--help]'; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done
[[ $lang == de || $lang == en ]] || { printf '%s\n' 'Language must be de or en' >&2; exit 2; }
say() { if [[ $lang == de ]]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi; }
ask() {
    local answer prompt=$1 default=$2
    if ((yes)); then [[ $default == yes ]]; return; fi
    if [[ $default == yes ]]; then prompt+=' [Y/n] '; else prompt+=' [y/N] '; fi
    printf '%s' "$prompt"
    if ! read -r answer; then return 1; fi
    case $answer in y|Y|yes|YES|j|J|ja|JA) return 0 ;; '') [[ $default == yes ]] ;; *) return 1 ;; esac
}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root_dir=$(dirname -- "$script_dir")
prepare=$script_dir/prepare-packages.py
cache=${XDG_CACHE_HOME:-$HOME/.cache}/windoesnot-install
build=$cache/build
os_release=${WDN_OS_RELEASE:-/etc/os-release}
if ((EUID == 0)); then say 'Bitte als normaler Benutzer starten, nicht als root.' 'Run as a normal user, not root.' >&2; exit 1; fi
if [[ ! -f $prepare || ! -f $root_dir/packaging/PKGBUILD.in ]]; then say 'Export unvollständig: prepare-packages.py oder PKGBUILD.in fehlt.' 'Incomplete export: prepare-packages.py or PKGBUILD.in missing.' >&2; exit 1; fi
# Read only the two os-release fields, without executing the file.
if ! awk -F= '/^(ID|ID_LIKE)=/ {gsub(/["\047]/,"",$2); n=split($2,a,/ /); for(i=1;i<=n;i++) if(a[i]=="arch" || a[i]=="cachyos") found=1} END {exit !found}' "$os_release"; then
    say 'Dieses System wird nicht unterstützt. Die WinDoesNot-ISO: https://windoesnot.me/download/' 'This system is not supported. Get the WinDoesNot ISO: https://windoesnot.me/download/' >&2; exit 1
fi
say 'Pakete werden lokal gebaut und mit pacman -U installiert; Deinstallation ist möglich. ~/.config wird nicht ohne Backup geändert. Keine Telemetrie.' 'Packages are built locally and installed with pacman -U; they can be removed. ~/.config is not changed without a backup. No telemetry.'
say 'Prüfe Voraussetzungen und Paketquellen.' 'Checking prerequisites and package repositories.'
command -v pacman >/dev/null || { say 'pacman fehlt.' 'pacman is missing.' >&2; exit 1; }
if ! command -v python3 >/dev/null; then
    say 'python3 fehlt; Repository-Paket: python.' 'python3 is missing; repository package: python.'
    if ((check || dry)); then exit 1; fi
    if pacman -Si python >/dev/null 2>&1 && pacman -Sp python >/dev/null 2>&1; then
        say 'Befehl: sudo pacman -S --needed python' 'Command: sudo pacman -S --needed python'
        if ask "$(say 'Python installieren?' 'Install Python?')" yes; then sudo pacman -S --needed python; else exit 1; fi
    else
        say 'Python ist im Repository nicht verfügbar.' 'Python is not available in the repositories.' >&2; exit 1
    fi
fi
pkgbuild=$root_dir/packaging/PKGBUILD.in
if (( ! check && ! dry )); then
    mkdir -p -- "$cache"
    exec > >(tee -a "$cache/install.log") 2>&1
    cleanup() {
        trap - INT
        say 'Abgebrochen. Nur der Arbeitsordner kann entfernt werden.' 'Interrupted. Only the build directory can be removed.'
        if [[ -d $build ]] && ask "$(say 'Arbeitsordner löschen?' 'Remove the build directory?')" no; then
            if [[ $build == "$cache/build" && $build == /* && ! -L $build ]]; then rm -r -- "$build"; fi
        fi
        exit 130
    }
    trap cleanup INT
    if [[ -e $build ]]; then
        say "Vorhandener Arbeitsordner: $build. Bitte bei Bedarf entfernen, um neue Quellen zu erzeugen." "Existing build directory: $build. Remove it when you need fresh sources."
        [[ -f $build/PKGBUILD ]] || { say 'Arbeitsordner ist unvollständig.' 'Build directory is incomplete.' >&2; exit 1; }
    else
        say "Befehl: python3 $prepare --output $build" "Command: python3 $prepare --output $build"
        python3 "$prepare" --output "$build"
    fi
    pkgbuild=$build/PKGBUILD
fi
# Parse literal dependency arrays only; never source or execute a PKGBUILD.
mapfile -t deps < <(python3 - "$pkgbuild" <<'PY'
import re, shlex, sys
text = open(sys.argv[1], encoding='utf-8').read()
items = set()
for match in re.finditer(r'^\s*(?:make)?depends\+?=\(([^\n]*)\)', text, re.M):
    for value in shlex.split(match.group(1), comments=True):
        name = re.split(r'[<>=]', value, 1)[0]
        if re.fullmatch(r'[a-zA-Z0-9@._+:-]+', name) and name not in {'windoesnot-desktop', 'windoesnot-tools', 'windoesnot-plugins', 'windoesnot-components'}:
            items.add(name)
items.update(('hyprland', 'quickshell', 'base-devel', 'git', 'python', 'cmake', 'ninja'))
print('\n'.join(sorted(items)))
PY
)
repo=() unavailable=()
for dep in "${deps[@]}"; do
    if pacman -Q "$dep" >/dev/null 2>&1; then continue; fi
    if pacman -Si "$dep" >/dev/null 2>&1; then
        repo+=("$dep")
        if ! pacman -Sp --print-format '%n' "$dep" >/dev/null 2>&1; then
            say "Paketauflösung fehlgeschlagen: $dep (Repository oder Abhängigkeiten prüfen)." "Package resolution failed: $dep (check repositories or dependencies)."
        fi
    else unavailable+=("$dep"); fi
done
say "Fehlende Repository-Pakete: ${repo[*]:-(keine)}" "Missing repository packages: ${repo[*]:-(none)}"
say "Nicht in konfigurierten Repositories gefunden (eventuell AUR oder Zusatz-Repository): ${unavailable[*]:-(keine)}" "Not found in configured repositories (possibly AUR or an additional repository): ${unavailable[*]:-(none)}"
if ((check)); then
    ((${#repo[@]} == 0 && ${#unavailable[@]} == 0)) || exit 1
    say 'Voraussetzungen erfüllt.' 'Prerequisites satisfied.'; exit 0
fi
if ((dry)); then
    say "Trockenlauf: würde Pakete nach Bestätigung installieren, $build erzeugen, ~/.config sichern, makepkg -s ausführen, Pakete installieren und Initialisierung anbieten." "Dry run: would confirm package installs, generate $build, back up ~/.config, run makepkg -s, install packages and offer initialization."
    say "Geplant: sudo pacman -S --needed ${repo[*]}; AUR-Helfer nur nach Frage; python3 $prepare --output $build; cp -a ~/.config ~/.config-backup-<Datum>; makepkg -s --force; sudo pacman -U <gebaute Pakete>; windoesnot-initialize." "Planned: sudo pacman -S --needed ${repo[*]}; AUR helper only after confirmation; python3 $prepare --output $build; cp -a ~/.config ~/.config-backup-<date>; makepkg -s --force; sudo pacman -U <built packages>; windoesnot-initialize."
    say 'Anmeldung: Sitzung WinDoesNot auswählen. Log: ~/.cache/windoesnot-install/install.log' 'Login: choose the WinDoesNot session. Log: ~/.cache/windoesnot-install/install.log'; exit 0
fi
if ((${#repo[@]})); then
    say "Befehl: sudo pacman -S --needed ${repo[*]}" "Command: sudo pacman -S --needed ${repo[*]}"
    if ask "$(say 'Diese Liste installieren?' 'Install this list?')" yes; then sudo pacman -S --needed "${repo[@]}"; else exit 1; fi
fi
if ((${#unavailable[@]})); then
    helper=''
    if (( ! no_aur )); then
        for candidate in paru yay; do if command -v "$candidate" >/dev/null; then helper=$candidate; break; fi; done
    fi
    if [[ -n $helper ]]; then
        say "Befehl: $helper -S --needed ${unavailable[*]} (der Helfer kann pacman/sudo aufrufen)." "Command: $helper -S --needed ${unavailable[*]} (the helper may invoke pacman/sudo)."
        if ask "$(say 'Diese Liste mit dem AUR-Helfer installieren?' 'Install this list with the AUR helper?')" no; then "$helper" -S --needed "${unavailable[@]}"; fi
    fi
    missing=()
    for dep in "${unavailable[@]}"; do pacman -Q "$dep" >/dev/null 2>&1 || missing+=("$dep"); done
    if ((${#missing[@]})); then
        say "Noch fehlend: ${missing[*]}. Bitte Paketnamen und Quellen prüfen, ein passendes Repository konfigurieren oder vertrauenswürdige AUR-Pakete selbst installieren; danach erneut starten." "Still missing: ${missing[*]}. Check package names and sources, configure an appropriate repository or install trusted AUR packages yourself, then rerun."
        exit 1
    fi
fi
if [[ -d $HOME/.config ]]; then
    backup=$HOME/.config-backup-$(date +%Y%m%d-%H%M%S)
    say "Befehl: cp -a ~/.config $backup" "Command: cp -a ~/.config $backup"
    if ask "$(say 'Konfiguration sichern?' 'Back up configuration?')" yes; then cp -a -- "$HOME/.config" "$backup"; else say 'Ohne Backup keine Installation.' 'Installation requires a backup.'; exit 1; fi
fi
say 'Befehl: makepkg -s --force (fehlende Abhängigkeiten könnten pacman aufrufen).' 'Command: makepkg -s --force (missing dependencies could invoke pacman).'
if ! ask "$(say 'Pakete bauen?' 'Build packages?')" yes; then exit 1; fi
# All dependencies must already be installed: makepkg must not silently install more.
if ! pacman -T "${deps[@]}" >/dev/null; then say 'Abhängigkeiten fehlen noch; bitte prüfen und erneut starten.' 'Dependencies are still missing; check them and rerun.'; exit 1; fi
(cd "$build" && makepkg -s --force)
mapfile -t packages < <(cd "$build" && makepkg --packagelist)
for package in "${packages[@]}"; do [[ -f $package ]] || { say "Paket fehlt: $package" "Package missing: $package"; exit 1; }; done
((${#packages[@]})) || { say 'Keine Pakete gebaut.' 'No packages built.'; exit 1; }
say "Befehl: sudo pacman -U ${packages[*]}" "Command: sudo pacman -U ${packages[*]}"
if ask "$(say 'Diese Pakete installieren?' 'Install these packages?')" yes; then sudo pacman -U "${packages[@]}"; else exit 1; fi
if systemctl is-active --quiet display-manager.service 2>/dev/null; then say 'Ein Display-Manager ist aktiv.' 'A display manager is active.'; else say 'Kein aktiver Display-Manager erkannt; bitte bei Bedarf selbst einrichten.' 'No active display manager detected; set one up if needed.'; fi
say 'Wähle die Sitzung WinDoesNot beim Anmelden.' 'Choose the WinDoesNot session at login.'
say 'Befehl: windoesnot-initialize (legt nur fehlende Standardwerte an).' 'Command: windoesnot-initialize (creates missing defaults only).'
if ask "$(say 'Initialisierung ausführen?' 'Run initialization?')" yes; then windoesnot-initialize; fi
say "Installiert: ${packages[*]}. Log: $cache/install.log" "Installed: ${packages[*]}. Log: $cache/install.log"
say 'Deinstallation: sudo pacman -Rns windoesnot-desktop windoesnot-tools windoesnot-plugins windoesnot-components. Backup bei Bedarf wiederherstellen.' 'Uninstall: sudo pacman -Rns windoesnot-desktop windoesnot-tools windoesnot-plugins windoesnot-components. Restore your backup if needed.'
