#!/usr/bin/env python3
"""Finder: looks through a Linux system (or a mounted old one) for everything worth taking along.

It only reads. The result is a manifest (schema 2, kind "finder") with findings grouped and sorted by importance.
The user confirms or removes findings; `copy` then takes exactly the confirmed ones to the new home.

Findings know what they are: personal files, accounts (browser/mail profiles, passwords, keys), settings, programs and
data of programs, and things that can simply be rebuilt (caches, node_modules, downloaded models). Rebuildable things
are listed so their size is visible, but they are not ticked.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import time

SCHEMA = 2

GROUPS = (
    ('personal', 'Persönliche Dateien', 'Personal files'),
    ('accounts', 'Browser, Mail und Konten', 'Browsers, mail and accounts'),
    ('secrets', 'Passwörter und Schlüssel', 'Passwords and keys'),
    ('chat', 'Chats und Kommunikation', 'Chats and communication'),
    ('dev', 'Entwicklung', 'Development'),
    ('vm', 'Virtuelle Maschinen und Container', 'Virtual machines and containers'),
    ('games', 'Spiele', 'Games'),
    ('settings', 'Einstellungen und Programme', 'Settings and programs'),
    ('rebuildable', 'Lässt sich neu laden oder bauen', 'Can be downloaded or rebuilt'),
)

# (id, group, title de, title en, detail de, detail en, importance, secrets, selected, [home-relative paths])
# Paths are relative to the home folder; "!/abs" means absolute inside the old system.
CATALOG = (
    # Browsers: the profile holds bookmarks, extensions, sessions and (Firefox family) saved logins.
    ('firefox', 'accounts', 'Firefox', 'Firefox', 'Profil mit Lesezeichen, Erweiterungen, gespeicherten Logins und Sitzungen.', 'Profile with bookmarks, extensions, saved logins and sessions.', 90, True, True,
     ['.mozilla/firefox', '.var/app/org.mozilla.firefox/.mozilla/firefox']),
    ('librewolf', 'accounts', 'LibreWolf', 'LibreWolf', 'Profil mit Lesezeichen und Logins.', 'Profile with bookmarks and logins.', 85, True, True, ['.librewolf', '.var/app/io.gitlab.librewolf-community/.librewolf']),
    ('floorp', 'accounts', 'Floorp', 'Floorp', 'Profil mit Lesezeichen und Logins.', 'Profile with bookmarks and logins.', 85, True, True, ['.floorp']),
    ('zen', 'accounts', 'Zen Browser', 'Zen Browser', 'Profil mit Lesezeichen und Logins.', 'Profile with bookmarks and logins.', 85, True, True, ['.zen']),
    ('chromium', 'accounts', 'Chromium', 'Chromium', 'Profil. Gespeicherte Passwörter sind mit dem Schlüsselbund verschlüsselt und kommen nur mit ihm (oder per Browser-Sync) mit.', 'Profile. Saved passwords are encrypted with the keyring and only come along with it (or via browser sync).', 80, True, True, ['.config/chromium']),
    ('chrome', 'accounts', 'Google Chrome', 'Google Chrome', 'Profil. Gespeicherte Passwörter sind mit dem Schlüsselbund verschlüsselt; am besten per Chrome-Sync mitnehmen.', 'Profile. Saved passwords are encrypted with the keyring; best taken along via Chrome sync.', 80, True, True, ['.config/google-chrome']),
    ('brave', 'accounts', 'Brave', 'Brave', 'Profil. Gespeicherte Passwörter sind mit dem Schlüsselbund verschlüsselt; Brave-Sync verwenden.', 'Profile. Saved passwords are encrypted with the keyring; use Brave sync.', 80, True, True, ['.config/BraveSoftware']),
    ('vivaldi', 'accounts', 'Vivaldi', 'Vivaldi', 'Profil, Passwörter mit Schlüsselbund verschlüsselt.', 'Profile, passwords encrypted with the keyring.', 78, True, True, ['.config/vivaldi']),
    ('edge', 'accounts', 'Microsoft Edge', 'Microsoft Edge', 'Profil, Passwörter mit Schlüsselbund verschlüsselt.', 'Profile, passwords encrypted with the keyring.', 75, True, True, ['.config/microsoft-edge']),
    ('opera', 'accounts', 'Opera', 'Opera', 'Profil, Passwörter mit Schlüsselbund verschlüsselt.', 'Profile, passwords encrypted with the keyring.', 70, True, True, ['.config/opera']),
    # Mail and calendar
    ('thunderbird', 'accounts', 'Thunderbird', 'Thunderbird', 'Konten, Mails, Adressbuch, Kalender und Filter; eingeloggt wie bisher.', 'Accounts, mail, address book, calendars and filters; stays logged in.', 95, True, True,
     ['.thunderbird', '.var/app/org.mozilla.Thunderbird/.thunderbird']),
    ('evolution', 'accounts', 'Evolution', 'Evolution', 'Konten, Mails und Kalender.', 'Accounts, mail and calendars.', 85, True, True, ['.local/share/evolution', '.config/evolution']),
    ('kmail', 'accounts', 'KMail / Akonadi', 'KMail / Akonadi', 'Konten, Mails und Adressbuch.', 'Accounts, mail and address book.', 80, True, True, ['.local/share/kmail2', '.local/share/akonadi', '.config/akonadi']),
    ('geary', 'accounts', 'Geary', 'Geary', 'Konten und Mails.', 'Accounts and mail.', 70, True, True, ['.local/share/geary', '.config/geary']),
    # Passwords and keys
    ('ssh', 'secrets', 'SSH-Schlüssel', 'SSH keys', 'Private Schlüssel und bekannte Server (~/.ssh).', 'Private keys and known servers (~/.ssh).', 98, True, True, ['.ssh']),
    ('gnupg', 'secrets', 'GPG-Schlüssel', 'GPG keys', 'Signier- und Verschlüsselungsschlüssel (~/.gnupg).', 'Signing and encryption keys (~/.gnupg).', 98, True, True, ['.gnupg']),
    ('pass', 'secrets', 'pass-Passwortspeicher', 'pass password store', 'Mit GPG verschlüsselte Passwörter (~/.password-store).', 'GPG-encrypted passwords (~/.password-store).', 95, True, True, ['.password-store']),
    ('keyring', 'secrets', 'Schlüsselbund (GNOME)', 'Keyring (GNOME)', 'Gespeicherte WLAN-, Mail- und Browser-Passwörter. Wird mit dem Anmeldepasswort entsperrt.', 'Saved Wi-Fi, mail and browser passwords. Unlocked by the login password.', 92, True, True, ['.local/share/keyrings']),
    ('kwallet', 'secrets', 'KDE-Wallet', 'KDE Wallet', 'Gespeicherte Passwörter der KDE-Programme.', 'Saved passwords of KDE programs.', 90, True, True, ['.local/share/kwalletd']),
    ('bitwarden', 'secrets', 'Bitwarden (Desktop)', 'Bitwarden (desktop)', 'Lokale Einstellungen; die Passwörter liegen in der Bitwarden-Cloud.', 'Local settings; the passwords live in the Bitwarden cloud.', 60, True, True, ['.config/Bitwarden']),
    ('rbw', 'secrets', 'rbw (Bitwarden-CLI)', 'rbw (Bitwarden CLI)', 'Anmeldedaten für die Bitwarden-Kommandozeile.', 'Login data for the Bitwarden command line.', 55, True, True, ['.config/rbw']),
    ('cloud-cli', 'secrets', 'Cloud-Zugänge (aws, gcloud, kube, rclone)', 'Cloud access (aws, gcloud, kube, rclone)', 'Zugangsdaten und Konfigurationen der Cloud-Werkzeuge.', 'Credentials and configuration of the cloud tools.', 75, True, True, ['.aws', '.config/gcloud', '.kube', '.config/rclone', '.azure']),
    ('vpn', 'secrets', 'VPN-Konfigurationen', 'VPN configurations', 'WireGuard-, OpenVPN- und Tailscale-Daten im Home.', 'WireGuard, OpenVPN and Tailscale data in the home folder.', 70, True, True, ['.config/openvpn', '.config/wireguard', '.config/Mullvad VPN']),
    # Chat
    ('discord', 'chat', 'Discord', 'Discord', 'Anmeldung und Einstellungen (Nachrichten liegen im Konto).', 'Login and settings (messages live in the account).', 55, True, True, ['.config/discord', '.config/vesktop', '.var/app/com.discordapp.Discord']),
    ('signal', 'chat', 'Signal', 'Signal', 'Daten und Chats. Ohne diese Dateien musst du das Gerät neu koppeln.', 'Data and chats. Without these files the device has to be linked again.', 85, True, True, ['.config/Signal', '.var/app/org.signal.Signal']),
    ('telegram', 'chat', 'Telegram', 'Telegram', 'Anmeldung und lokale Daten.', 'Login and local data.', 55, True, True, ['.local/share/TelegramDesktop', '.var/app/org.telegram.desktop']),
    ('element', 'chat', 'Element (Matrix)', 'Element (Matrix)', 'Anmeldung und Schlüssel für verschlüsselte Räume.', 'Login and keys for encrypted rooms.', 75, True, True, ['.config/Element', '.var/app/im.riot.Riot']),
    ('slack', 'chat', 'Slack', 'Slack', 'Anmeldung.', 'Login.', 40, True, True, ['.config/Slack']),
    ('zoom', 'chat', 'Zoom', 'Zoom', 'Einstellungen und Anmeldung.', 'Settings and login.', 35, True, True, ['.zoom', '.config/zoomus.conf']),
    # Development
    ('git', 'dev', 'Git-Einstellungen', 'Git settings', 'Name, E-Mail, Aliase und Zugangsdaten (~/.gitconfig, ~/.config/git).', 'Name, email, aliases and credentials (~/.gitconfig, ~/.config/git).', 88, True, True, ['.gitconfig', '.config/git', '.git-credentials', '.config/gh']),
    ('vscode', 'dev', 'VS Code', 'VS Code', 'Einstellungen, Tastenkürzel und Erweiterungsliste (ohne Cache).', 'Settings, shortcuts and extension list (without cache).', 70, False, True, ['.config/Code/User', '.vscode/extensions']),
    ('cursor', 'dev', 'Cursor', 'Cursor', 'Einstellungen und Erweiterungen.', 'Settings and extensions.', 65, False, True, ['.config/Cursor/User', '.cursor']),
    ('jetbrains', 'dev', 'JetBrains-IDEs', 'JetBrains IDEs', 'Einstellungen und Lizenzen der IDEs.', 'Settings and licences of the IDEs.', 65, False, True, ['.config/JetBrains']),
    ('neovim', 'dev', 'Neovim', 'Neovim', 'Konfiguration und Plugins.', 'Configuration and plugins.', 60, False, True, ['.config/nvim', '.local/share/nvim']),
    ('shell', 'settings', 'Shell-Einstellungen', 'Shell settings', 'bash, zsh, fish: Aliase, Verlauf und Prompt.', 'bash, zsh, fish: aliases, history and prompt.', 70, False, True, ['.bashrc', '.bash_profile', '.profile', '.bash_history', '.zshrc', '.zsh_history', '.zprofile', '.config/fish', '.config/starship.toml']),
    ('ollama', 'rebuildable', 'Ollama-Modelle', 'Ollama models', 'Heruntergeladene KI-Modelle; lassen sich neu laden.', 'Downloaded AI models; can be downloaded again.', 10, False, False, ['.ollama']),
    ('lmstudio', 'rebuildable', 'LM-Studio-Modelle', 'LM Studio models', 'Heruntergeladene KI-Modelle; lassen sich neu laden.', 'Downloaded AI models; can be downloaded again.', 10, False, False, ['.lmstudio', '.cache/lm-studio']),
    # Virtual machines
    ('vmware', 'vm', 'VMware-Maschinen', 'VMware machines', 'Deine virtuellen Maschinen (~/vmware).', 'Your virtual machines (~/vmware).', 80, False, True, ['vmware', '.vmware']),
    ('virtualbox', 'vm', 'VirtualBox-Maschinen', 'VirtualBox machines', 'Deine virtuellen Maschinen.', 'Your virtual machines.', 80, False, True, ['VirtualBox VMs', '.config/VirtualBox']),
    ('boxes', 'vm', 'GNOME Boxes', 'GNOME Boxes', 'Deine virtuellen Maschinen.', 'Your virtual machines.', 75, False, True, ['.local/share/gnome-boxes']),
    ('docker-user', 'vm', 'Docker (Benutzer)', 'Docker (user)', 'Einstellungen und Rootless-Daten von Docker im Home.', 'Docker settings and rootless data in the home folder.', 50, False, True, ['.docker', '.local/share/docker']),
    ('podman-user', 'vm', 'Podman (Benutzer)', 'Podman (user)', 'Container und Images von Podman im Home.', 'Podman containers and images in the home folder.', 50, False, True, ['.local/share/containers']),
    # Games
    ('steam-saves', 'games', 'Steam: Spielstände und Einstellungen', 'Steam: saves and settings', 'Anmeldung, Cloud-unabhängige Spielstände und Steam-Einstellungen (ohne die Spiele selbst).', 'Login, saves not in the cloud and Steam settings (without the games themselves).', 70, True, True,
     ['.local/share/Steam/userdata', '.local/share/Steam/config', '.steam/registry.vdf']),
    ('steam-games', 'games', 'Steam: installierte Spiele', 'Steam: installed games', 'Die Spiele selbst. Steam lädt sie bei Bedarf neu; nur mitnehmen, wenn die Leitung langsam ist.', 'The games themselves. Steam can download them again; take them only if your connection is slow.', 20, False, False, ['.local/share/Steam/steamapps']),
    ('lutris', 'games', 'Lutris', 'Lutris', 'Bibliothek und Einstellungen.', 'Library and settings.', 50, False, True, ['.config/lutris', '.local/share/lutris']),
    ('heroic', 'games', 'Heroic Games Launcher', 'Heroic Games Launcher', 'Anmeldung und Einstellungen (Epic, GOG).', 'Login and settings (Epic, GOG).', 50, True, True, ['.config/heroic']),
    ('wine', 'games', 'Wine-Präfixe', 'Wine prefixes', 'Windows-Programme und ihre Daten unter Wine.', 'Windows programs and their data under Wine.', 60, False, True, ['.wine', 'Games', '.local/share/wineprefixes']),
    ('minecraft', 'games', 'Minecraft', 'Minecraft', 'Welten und Einstellungen.', 'Worlds and settings.', 65, False, True, ['.minecraft', '.local/share/PrismLauncher', '.local/share/multimc']),
    # Rebuildable
    ('cache', 'rebuildable', 'Zwischenspeicher (.cache)', 'Caches (.cache)', 'Wird von den Programmen neu aufgebaut.', 'Rebuilt by the programs.', 5, False, False, ['.cache']),
    ('trash', 'rebuildable', 'Papierkorb', 'Trash', 'Gelöschte Dateien des alten Systems.', 'Deleted files of the old system.', 3, False, False, ['.local/share/Trash']),
    ('pkg-caches', 'rebuildable', 'Paket-Caches (npm, cargo, pip, go)', 'Package caches (npm, cargo, pip, go)', 'Heruntergeladene Pakete der Entwicklerwerkzeuge.', 'Downloaded packages of developer tools.', 5, False, False, ['.npm', '.cargo/registry', '.cargo/git', '.rustup', '.gradle/caches', '.m2/repository', 'go/pkg']),
)

# Where programs keep user-visible data that is not in the catalogue: the "everything else" findings.
SWEEP_DIRS = (('.config', 'Einstellungen weiterer Programme', 'Settings of other programs', 'Alles in ~/.config, was oben nicht einzeln steht.', 'Everything in ~/.config that is not listed separately above.', 60),
              ('.local/share', 'Daten weiterer Programme', 'Data of other programs', 'Alles in ~/.local/share, was oben nicht einzeln steht.', 'Everything in ~/.local/share that is not listed separately above.', 55),
              ('.var/app', 'Flatpak-Apps (Daten)', 'Flatpak apps (data)', 'Einstellungen und Daten der Flatpak-Programme.', 'Settings and data of Flatpak programs.', 55))

# Never worth taking: machine-bound or regenerated.
NEVER = ('.config/pulse', '.config/pipewire', '.local/share/recently-used.xbel', '.config/dconf/user.lock', '.ICEauthority', '.Xauthority',
         '.local/state', '.dbus', '.config/session', '.xsession-errors', '.local/share/gvfs-metadata', '.config/Code/Cache', '.config/Code/CachedData',
         '.config/Code/logs', '.config/discord/Cache')
# Foreign desktops: their settings do not apply to Hyprland, but nothing is lost by keeping them.
FOREIGN_DESKTOP = ('.config/kde', '.config/plasma', '.config/kwin', '.config/dolphin', '.local/share/plasma', '.config/gnome', '.config/dconf')

REBUILDABLE_DIRS = ('node_modules', 'target', '.venv', 'venv', '__pycache__', '.gradle', '.next', '.nuxt', 'dist-newstyle', '.tox', '.mypy_cache', '.pytest_cache', '.terraform')
PROJECT_DEPTH = 4
IGNORED_BIG = 1 << 30
PERSONAL_NAMES = {'Documents': ('Dokumente', 'Documents'), 'Dokumente': ('Dokumente', 'Documents'), 'Pictures': ('Bilder', 'Pictures'), 'Bilder': ('Bilder', 'Pictures'),
                  'Music': ('Musik', 'Music'), 'Musik': ('Musik', 'Music'), 'Videos': ('Videos', 'Videos'), 'Desktop': ('Schreibtisch', 'Desktop'), 'Schreibtisch': ('Schreibtisch', 'Desktop'),
                  'Downloads': ('Downloads', 'Downloads'), 'Templates': ('Vorlagen', 'Templates'), 'Vorlagen': ('Vorlagen', 'Templates'), 'Public': ('Öffentlich', 'Public'), 'Öffentlich': ('Öffentlich', 'Public')}


def disk_size(info):
    """Size to plan with: the file size, except for big mostly-empty (sparse) files such as VM disks, where the used part counts."""
    allocated = getattr(info, 'st_blocks', 0) * 512
    if info.st_size > (1 << 30) and allocated < info.st_size // 8:
        return allocated
    return info.st_size


def measure(path, skip=()):
    """Logical size of a path. Does not follow symlinks, never raises, skips the given absolute prefixes."""
    skip = tuple(skip)
    total = files = 0
    flags = set()
    stack = [str(path)]
    while stack:
        current = stack.pop()
        if skip and current in skip:
            continue
        try:
            info = os.lstat(current)
        except OSError:
            flags.add('unreadable')
            continue
        if stat.S_ISREG(info.st_mode):
            total += disk_size(info)
            files += 1
        elif stat.S_ISDIR(info.st_mode):
            try:
                with os.scandir(current) as entries:
                    stack.extend(entry.path for entry in entries)
            except OSError:
                flags.add('unreadable')
        elif not stat.S_ISLNK(info.st_mode):
            flags.add('special')
    return total, files, sorted(flags)


def under(path, others):
    path = str(path)
    return any(path == o or path.startswith(o.rstrip('/') + '/') for o in others)


def find_projects(home, claimed):
    """Folders with a .git folder (up to a few levels down) are projects; their rebuildable subfolders are collected."""
    projects, rebuildable, ignored = [], [], []
    home = str(home)
    def walk(directory, depth):
        if depth > PROJECT_DEPTH or under(directory, claimed):
            return
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return
        names = {entry.name for entry in entries}
        if '.git' in names and directory != home:
            projects.append(directory)
            collect(directory)
            ignored_big(directory, entries)
            return
        for entry in entries:
            if entry.is_dir(follow_symlinks=False) and not entry.name.startswith('.') and entry.name not in REBUILDABLE_DIRS:
                walk(entry.path, depth + 1)
    def ignored_big(project, entries):
        """Big top-level folders that Git ignores are usually build output, but they can also be local data: shown, not ticked."""
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False) or entry.name == '.git' or entry.name in REBUILDABLE_DIRS:
                continue
            try:
                ignored_by_git = subprocess.run(['git', '-C', project, 'check-ignore', '-q', '--', entry.name], capture_output=True, timeout=10).returncode == 0
            except (OSError, subprocess.SubprocessError):
                continue
            if ignored_by_git and measure(entry.path)[0] >= IGNORED_BIG:
                ignored.append(entry.path)

    def collect(project):
        for base, dirs, _files in os.walk(project, followlinks=False):
            keep = []
            for name in dirs:
                full = os.path.join(base, name)
                if name in REBUILDABLE_DIRS:
                    rebuildable.append(full)
                elif name != '.git':
                    keep.append(name)
            dirs[:] = keep
    walk(home, 0)
    return projects, rebuildable, ignored


def user_dirs(home):
    result = {}
    try:
        for line in (home / '.config/user-dirs.dirs').read_text(errors='replace').splitlines():
            if line.startswith('XDG_') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').replace('$HOME', str(home))
                result[key] = Path(value)
    except OSError:
        pass
    return result


def finding(ident, group, title, detail, paths, size, files, importance, secrets=False, selected=True, warnings=(), note=None):
    item = {'id': ident, 'group': group, 'title': {'de': title[0], 'en': title[1]}, 'detail': {'de': detail[0], 'en': detail[1]},
            'paths': paths, 'bytes': size, 'files': files, 'importance': importance, 'secrets': secrets, 'selected': selected,
            'warnings': list(warnings)}
    if note:
        item['note'] = note
    return item


def scan_home(root, home, user, progress=None):
    """Findings for one home folder. `root` is the (mounted) old system, `home` the absolute path inside it."""
    root = Path(root)
    base = (root / str(home).lstrip('/')).resolve()
    findings, claimed = [], []
    def report(text):
        if progress:
            progress(text)
    # Projects first: their rebuildable subfolders are carved out of whatever contains them.
    report('projects')
    skip_everywhere = [str(base / p) for p in NEVER]
    projects, rebuildable, ignored = find_projects(base, [str(base / p) for entry in CATALOG for p in entry[9]])
    for entry in CATALOG:
        ident, group, de, en, dde, den, importance, secrets, selected, paths = entry
        report(ident)
        present = []
        for rel in paths:
            full = base / rel
            if full.exists() and not full.is_symlink() or full.is_symlink():
                present.append(rel)
        if not present:
            continue
        total = files = 0
        flags = set()
        for rel in present:
            size, count, f = measure(base / rel, skip=skip_everywhere + rebuildable + ignored)
            total, files = total + size, files + count
            flags.update(f)
            claimed.append(str(base / rel))
        findings.append(finding(ident, group, (de, en), (dde, den), present, total, files, importance, secrets, selected, flags))
    if rebuildable:
        size = sum(measure(p)[0] for p in rebuildable)
        rel = [str(Path(p).relative_to(base)) for p in rebuildable]
        findings.append(finding('build-folders', 'rebuildable', ('Build- und Paketordner der Projekte (node_modules, target, .venv ...)', 'Build and package folders of projects (node_modules, target, .venv ...)'),
                                ('Entstehen beim Bauen neu.', 'Created again when building.'), rel, size, 0, 4, False, False))
    if ignored:
        size = sum(measure(p)[0] for p in ignored)
        rel = [str(Path(p).relative_to(base)) for p in ignored]
        findings.append(finding('ignored-big', 'rebuildable', ('Große, von Git ignorierte Ordner in Projekten', 'Large folders ignored by Git in projects'),
                                ('Meist Build-Ausgaben, VM-Abbilder oder Zwischenstände. Prüfe die Liste, bevor du etwas mitnimmst.', 'Mostly build output, VM images or intermediate results. Check the list before taking anything.'), rel, size, 0, 12, False, False))
    # Personal folders: XDG folders first, then every other top-level folder of the home.
    dirs = user_dirs(base)
    xdg = {p for p in dirs.values() if p != base}
    try:
        top = sorted(os.scandir(base), key=lambda e: e.name)
    except OSError:
        top = []
    project_roots = {str(Path(p).relative_to(base)).split('/')[0] for p in projects}
    for entry in top:
        name = entry.name
        full = Path(entry.path)
        if name.startswith('.') or under(full, claimed) or entry.is_symlink() and not entry.is_dir():
            continue
        if not entry.is_dir(follow_symlinks=False):
            # Loose files in the home: collected below.
            continue
        report(name)
        size, files, flags = measure(full, skip=skip_everywhere + rebuildable + ignored)
        label = PERSONAL_NAMES.get(name)
        is_project_dir = name in project_roots
        if label:
            title, detail, importance = label, ('Deine Dateien in ' + name + '.', 'Your files in ' + name + '.'), 100 if name in ('Documents', 'Dokumente', 'Pictures', 'Bilder') else 90
        elif is_project_dir:
            title, detail, importance = (name, name), ('Ordner mit Git-Projekten (ohne Build-Ordner).', 'Folder with Git projects (without build folders).'), 85
        else:
            title, detail, importance = (name, name), ('Eigener Ordner im Home.', 'Own folder in the home folder.'), 75
        findings.append(finding('dir:' + name, 'dev' if is_project_dir and not label else 'personal', title, detail, [name], size, files, importance, False, True, flags))
        claimed.append(str(full))
    loose = []
    for entry in top:
        if entry.is_file(follow_symlinks=False) and not entry.name.startswith('.') and not under(entry.path, claimed):
            loose.append(entry.name)
    if loose:
        size = sum(os.lstat(base / n).st_size for n in loose)
        findings.append(finding('loose-files', 'personal', ('Einzelne Dateien im Home', 'Single files in the home folder'), ('Dateien, die direkt im Home liegen.', 'Files that lie directly in the home folder.'), loose, size, len(loose), 70))
    def unclaimed(path):
        """Paths below `path` that no catalogue entry owns; folders that contain a claimed path are opened up."""
        relative = str(Path(path).relative_to(base))
        if under(path, claimed) or under(path, skip_everywhere) or any(relative == n or relative.startswith(n + '/') for n in NEVER):
            return []
        if any(c.startswith(path.rstrip('/') + '/') for c in claimed):
            try:
                return [x for child in sorted(os.scandir(path), key=lambda e: e.name) for x in unclaimed(child.path)]
            except OSError:
                return []
        return [path]
    # Everything else in the program folders.
    for rel, de, en, dde, den, importance in SWEEP_DIRS:
        folder = base / rel
        if not folder.is_dir():
            continue
        report(rel)
        rest, size, files = [], 0, 0
        try:
            children = sorted(os.scandir(folder), key=lambda e: e.name)
        except OSError:
            continue
        for child in children:
            for full in unclaimed(child.path):
                s, f, _flags = measure(full, skip=skip_everywhere)
                rest.append(str(Path(full).relative_to(base)))
                size, files = size + s, files + f
        if rest:
            note = 'foreign-desktop' if any(r.startswith(FOREIGN_DESKTOP) for r in rest) else None
            findings.append(finding('sweep:' + rel, 'settings', (de, en), (dde, den), rest, size, files, importance, True, True, (), note))
            claimed.append(str(folder))
    # Hidden files in the home itself (dotfiles not named above).
    dots = []
    for e in top:
        if e.name.startswith('.') and e.name not in ('.config', '.local', '.cache', '.var') and e.name not in NEVER and not e.name.endswith(('.lock', '-errors')):
            dots += [str(Path(x).relative_to(base)) for x in unclaimed(e.path)]
    if dots:
        size = files = 0
        for name in dots:
            s, f, _ = measure(base / name, skip=skip_everywhere)
            size, files = size + s, files + f
        findings.append(finding('dotfiles', 'settings', ('Weitere versteckte Dateien und Ordner', 'Other hidden files and folders'), ('Punktdateien im Home, die oben nicht einzeln stehen.', 'Dot files in the home folder that are not listed separately above.'), dots, size, files, 50, True, True))
    return findings


def scan_system(root, progress=None):
    """Things outside the home folders: Docker, VMs, /opt ... (reuses the Linux-move catalogue when available)."""
    root = Path(root)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mirror
    except ImportError:
        return []
    result = []
    for item in mirror.scan_locations(root):
        group = 'vm' if item['kind'] in ('vm', 'container') else 'settings'
        importance = 70 if item['id'] == 'docker' else 65
        result.append(finding('sys:' + item['id'], group, (item['label'], item['label']), ('Liegt außerhalb des Homes: ' + item['path'] + '.', 'Lives outside the home folder: ' + item['path'] + '.'),
                              [item['path']], item['bytes'], 0, importance, False, item['selected'], item.get('warnings', []), note='absolute'))
    return result


def users_of(root):
    found = []
    try:
        for line in (Path(root) / 'etc/passwd').read_text(errors='replace').splitlines():
            parts = line.split(':')
            if len(parts) == 7 and parts[2].isdigit() and 1000 <= int(parts[2]) < 60000 and parts[5].startswith('/home'):
                found.append({'name': parts[0], 'uid': int(parts[2]), 'gid': int(parts[3]), 'home': parts[5]})
    except OSError:
        pass
    return found


def scan(root='/', user=None, progress=None):
    root = Path(root)
    users = users_of(root)
    if user:
        users = [u for u in users if u['name'] == user]
    if not users:
        raise ValueError('No user found')
    chosen = users[0]
    findings = scan_home(root, chosen['home'], chosen['name'], progress) + scan_system(root, progress)
    order = {key: i for i, (key, _de, _en) in enumerate(GROUPS)}
    findings.sort(key=lambda f: (order.get(f['group'], 99), -f['importance'], -f['bytes']))
    return {'schema': SCHEMA, 'kind': 'finder', 'source_root': str(root.resolve()), 'user': chosen, 'created': int(time.time()),
            'groups': [{'id': key, 'title': {'de': de, 'en': en}} for key, de, en in GROUPS], 'findings': findings}


def selected_bytes(manifest):
    return sum(f['bytes'] for f in manifest['findings'] if f.get('selected'))


def copy(manifest, target_home, target_root='/', progress=None):
    """Copy every selected finding. Home findings go to target_home, absolute ones to the same path below target_root."""
    root = Path(manifest['source_root'])
    user = manifest['user']
    source_home = (root / user['home'].lstrip('/')).resolve()
    target_home = Path(target_home)
    target_root = Path(target_root)
    selected = [f for f in manifest['findings'] if f.get('selected')]
    unselected_paths = [p for f in manifest['findings'] if not f.get('selected') and f.get('note') != 'absolute' for p in f['paths']]
    done, problems = [], []
    free = os.statvfs(target_home).f_bavail * os.statvfs(target_home).f_frsize
    need = sum(f['bytes'] for f in selected)
    if need > free:
        raise OSError('Not enough free space: %d needed, %d free' % (need, free))
    for item in selected:
        if progress:
            progress({'event': 'finding', 'id': item['id'], 'bytes': item['bytes']})
        absolute = item.get('note') == 'absolute'
        for rel in item['paths']:
            if rel.startswith('/') != absolute or '..' in Path(rel).parts:
                raise ValueError('Unsafe path in finding ' + item['id'])
            if absolute:
                source, destination = root / rel.lstrip('/'), target_root / rel.lstrip('/')
                destination.mkdir(parents=True, exist_ok=True)
                args = ['rsync', '-aHAXS', '--numeric-ids', '--no-specials', '--no-devices', '--', str(source) + '/', str(destination) + '/']
            else:
                nested = [p[len(rel) + 1:] for p in unselected_paths if p.startswith(rel + '/')]
                args = ['rsync', '-aHAXS', '--numeric-ids', '--no-specials', '--no-devices', '--relative']
                args += ['--exclude=/' + rel + '/' + n for n in nested]
                args += ['--', './' + rel, str(target_home) + '/']
            result = subprocess.run(args, cwd=None if absolute else source_home, capture_output=True)
            if result.returncode not in (0, 24):
                problems.append({'id': item['id'], 'path': rel, 'error': result.stderr.decode(errors='replace')[-300:]})
        done.append(item['id'])
    return {'copied': done, 'problems': problems}


# --- Transfer package ---------------------------------------------------------------------------------------------
# A package is a folder that can lie on any storage (external disk with any file system, SMB share, USB stick):
#   windoesnot-umzug.json   marker and index; only written when everything is complete ("complete": true)
#   data/<id>.tar           one tar per finding (keeps modes, owners, xattrs and ACLs even on exFAT/NTFS/SMB)
#   SHA256SUMS              checksums of the archives
# The installer looks for the marker; the Windows exporter can write the same layout later.
PACKAGE_MARKER = 'windoesnot-umzug.json'
PACKAGE_SCHEMA = 3


def sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def tar_base(args_extra):
    return ['tar', '--numeric-owner', '--xattrs', '--acls', *args_extra]


def export_package(manifest, destination, progress=None):
    """Write the selected findings as a transfer package below `destination`; returns the package folder."""
    root = Path(manifest['source_root'])
    user = manifest['user']
    source_home = (root / user['home'].lstrip('/')).resolve()
    package = Path(destination) / ('Umzug-%s-%s' % (user['name'], time.strftime('%Y%m%d-%H%M')))
    data = package / 'data'
    data.mkdir(parents=True)
    selected = [f for f in manifest['findings'] if f.get('selected')]
    unselected = [p for f in manifest['findings'] if not f.get('selected') and f.get('note') != 'absolute' for p in f['paths']]
    need = sum(f['bytes'] for f in selected)
    st = os.statvfs(package)
    if need > st.f_bavail * st.f_frsize:
        raise OSError('Not enough free space: %d needed, %d free' % (need, st.f_bavail * st.f_frsize))
    entries, problems, sums = [], [], []
    for item in selected:
        if progress:
            progress({'event': 'finding', 'id': item['id'], 'bytes': item['bytes']})
        absolute = item.get('note') == 'absolute'
        names = []
        for rel in item['paths']:
            if rel.startswith('/') != absolute or '..' in Path(rel).parts:
                raise ValueError('Unsafe path in finding ' + item['id'])
            names.append(rel.lstrip('/'))
        archive = data / (item['id'].replace(':', '_').replace('/', '_') + '.tar')
        # Anchored and literal: an unselected folder is left out only at exactly that path.
        excludes = [] if absolute else ['--anchored', '--no-wildcards'] + ['--exclude=' + p for p in unselected]
        base_dir = root if absolute else source_home
        command = tar_base(['--create', '--format=posix', '--sparse', '--file', str(archive), '-C', str(base_dir), *excludes, '--', *names])
        result = subprocess.run(command, capture_output=True)
        # 1 = a file changed while it was read (normal on a live system), anything else is a real problem.
        if result.returncode not in (0, 1):
            problems.append({'id': item['id'], 'error': result.stderr.decode(errors='replace')[-300:]})
            continue
        digest = sha256_file(archive)
        sums.append('%s  data/%s' % (digest, archive.name))
        entries.append({'id': item['id'], 'group': item['group'], 'title': item['title'], 'archive': 'data/' + archive.name,
                        'kind': 'absolute' if absolute else 'home', 'paths': item['paths'], 'bytes': item['bytes'],
                        'archive_bytes': archive.stat().st_size, 'sha256': digest, 'secrets': bool(item.get('secrets'))})
    (package / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    index = {'schema': PACKAGE_SCHEMA, 'kind': 'package', 'complete': not problems, 'created': int(time.time()),
             'source': {'user': user, 'root': str(root)}, 'groups': manifest['groups'], 'findings': entries, 'problems': problems}
    partial = package / (PACKAGE_MARKER + '.partial')
    partial.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    os.replace(partial, package / PACKAGE_MARKER)
    return {'package': str(package), 'findings': [e['id'] for e in entries], 'problems': problems}


def read_package(package):
    index = json.loads((Path(package) / PACKAGE_MARKER).read_text())
    if index.get('schema') != PACKAGE_SCHEMA or index.get('kind') != 'package':
        raise ValueError('Not a transfer package')
    return index


def find_packages(roots):
    """Packages below the given mount points (one or two levels deep); incomplete ones are reported but flagged."""
    found = []
    for base in roots:
        base = Path(base)
        try:
            candidates = [base] + [c for c in sorted(base.iterdir()) if c.is_dir()]
        except OSError:
            continue
        for candidate in candidates:
            if (candidate / PACKAGE_MARKER).is_file():
                try:
                    index = read_package(candidate)
                except (OSError, ValueError):
                    continue
                found.append({'path': str(candidate), 'complete': bool(index.get('complete')), 'user': index['source']['user']['name'],
                              'created': index.get('created'), 'bytes': sum(f['bytes'] for f in index['findings']),
                              'findings': len(index['findings'])})
    return found


def import_package(package, target_home, target_root='/', uid=None, gid=None, only=None, progress=None):
    """Verify the archives, then unpack them. Home findings go to target_home, absolute ones below target_root."""
    package = Path(package)
    index = read_package(package)
    if not index.get('complete'):
        raise ValueError('The package is incomplete')
    chosen = [f for f in index['findings'] if only is None or f['id'] in only]
    for item in chosen:
        archive = package / item['archive']
        if Path(item['archive']).is_absolute() or '..' in Path(item['archive']).parts or sha256_file(archive) != item['sha256']:
            raise ValueError('Checksum mismatch: ' + item['id'])
    old = index['source']['user']
    done, problems = [], []
    for item in chosen:
        if progress:
            progress({'event': 'finding', 'id': item['id'], 'bytes': item['bytes']})
        target = Path(target_root) if item['kind'] == 'absolute' else Path(target_home)
        target.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(tar_base(['--extract', '--preserve-permissions', '--file', str(package / item['archive']), '-C', str(target)]), capture_output=True)
        if result.returncode:
            problems.append({'id': item['id'], 'error': result.stderr.decode(errors='replace')[-300:]})
            continue
        if item['kind'] == 'home' and uid is not None and (uid != old['uid'] or gid != old['gid']):
            for rel in item['paths']:
                remap_owner(target / rel, old['uid'], old['gid'], uid, gid)
        done.append(item['id'])
    return {'copied': done, 'problems': problems}


PACKAGE_FILESYSTEMS = ('exfat', 'ntfs', 'vfat', 'ext4', 'ext3', 'ext2', 'btrfs', 'xfs', 'f2fs', 'udf')
PACKAGE_MOUNT_BASE = Path('/run/windoesnot/packages')


def mount_for_packages(device, filesystem, name):
    """Mount a partition read-only below /run/windoesnot/packages (installer, runs as root); returns the mount point."""
    target = PACKAGE_MOUNT_BASE / name
    target.mkdir(parents=True, exist_ok=True)
    fstype = {'ntfs': 'ntfs3'}.get(filesystem, filesystem)
    result = subprocess.run(['mount', '-o', 'ro,nosuid,nodev,noexec', '-t', fstype, device, str(target)], capture_output=True, timeout=60)
    if result.returncode:
        try:
            target.rmdir()
        except OSError:
            pass
        return None
    return target


def discover_packages(blockdevices=None, mounter=mount_for_packages):
    """Complete transfer packages on all partitions: already mounted ones are searched in place, others are mounted read-only
    (and kept mounted when they hold a package, because the installer reads them later). Nothing is ever written."""
    if blockdevices is None:
        blockdevices = json.loads(subprocess.check_output(['lsblk', '--json', '-o', 'PATH,TYPE,FSTYPE,LABEL,MOUNTPOINTS'], text=True, timeout=20)).get('blockdevices', [])
    candidates = []
    def visit(node):
        if node.get('type') in ('part', 'disk', 'loop', 'rom') and (node.get('fstype') or '').lower() in PACKAGE_FILESYSTEMS:
            candidates.append(node)
        for child in node.get('children') or []:
            visit(child)
    for node in blockdevices:
        visit(node)
    found = []
    for node in candidates:
        mounts = [m for m in (node.get('mountpoints') or []) if m and m not in ('/', '/boot', '/efi', '/home') and not m.startswith(('/run/archiso', '/boot/', '/var'))]
        temporary = None
        if not mounts:
            if node.get('mountpoints') and any(node['mountpoints']):
                continue   # mounted as part of the running system
            name = Path(node['path']).name
            temporary = mounter(node['path'], (node.get('fstype') or '').lower(), name)
            if temporary is None:
                continue
            mounts = [str(temporary)]
        hits = find_packages(mounts)
        for hit in hits:
            hit.update({'device': node['path'], 'label': node.get('label') or '', 'filesystem': (node.get('fstype') or '').lower()})
        found.extend(hits)
        if temporary is not None and not hits:
            subprocess.run(['umount', str(temporary)], capture_output=True, timeout=30)
            try:
                Path(temporary).rmdir()
            except OSError:
                pass
    return found


def package_manifest(package):
    """The page's view of a package: one 'user' (kind linux so the existing page layout is used) and every finding as a ticked location."""
    index = read_package(package)
    if not index.get('complete'):
        raise ValueError('The package is incomplete')
    user = index['source']['user']
    order = {g['id']: i for i, g in enumerate(index['groups'])}
    findings = sorted(index['findings'], key=lambda f: (order.get(f['group'], 99), -f['bytes']))
    title = lambda f: (f['title'].get('de') or f['title'].get('en') or f['id'])
    return {'schema': 1, 'kind': 'linux', 'package': str(Path(package)), 'system': 'Umzugspaket von ' + user['name'], 'device': str(package),
            'filesystem': 'package', 'users': [{'name': user['name'], 'uid': user['uid'], 'gid': user['gid'], 'home': user['home'],
                                                'bytes': 0, 'selected': True, 'warnings': [], 'folders': [], 'exclude': []}],
            'locations': [{'id': f['id'], 'kind': 'finding', 'path': '/' + f['id'], 'label': title(f) + (' (Zugangsdaten)' if f.get('secrets') else ''), 'bytes': f['bytes'],
                           'warnings': [], 'selected': f['group'] != 'rebuildable'} for f in findings],
            'packages': {}, 'services': [], 'warnings': []}


def remap_owner(path, old_uid, old_gid, uid, gid):
    """The new account may have another numeric id than the old one."""
    stack = [str(path)]
    while stack:
        current = stack.pop()
        try:
            info = os.lstat(current)
            if info.st_uid == old_uid or info.st_gid == old_gid:
                os.lchown(current, uid if info.st_uid == old_uid else -1, gid if info.st_gid == old_gid else -1)
            if stat.S_ISDIR(info.st_mode):
                stack.extend(entry.path for entry in os.scandir(current))
        except OSError:
            continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    scan_parser = sub.add_parser('scan')
    scan_parser.add_argument('--root', default='/')
    scan_parser.add_argument('--user')
    scan_parser.add_argument('--output')
    copy_parser = sub.add_parser('copy')
    copy_parser.add_argument('manifest')
    copy_parser.add_argument('target_home')
    copy_parser.add_argument('--target-root', default='/')
    export_parser = sub.add_parser('export')
    export_parser.add_argument('manifest')
    export_parser.add_argument('destination')
    import_parser = sub.add_parser('import')
    import_parser.add_argument('package')
    import_parser.add_argument('target_home')
    import_parser.add_argument('--target-root', default='/')
    import_parser.add_argument('--uid', type=int)
    import_parser.add_argument('--gid', type=int)
    find_parser = sub.add_parser('find')
    find_parser.add_argument('roots', nargs='+')
    args = parser.parse_args()
    if args.action == 'find':
        print(json.dumps(find_packages(args.roots), ensure_ascii=False))
        return
    if args.action == 'import':
        print(json.dumps(import_package(args.package, args.target_home, args.target_root, args.uid, args.gid,
                                        progress=lambda e: print(json.dumps(e), flush=True)), ensure_ascii=False))
        return
    if args.action == 'export':
        manifest = json.loads(Path(args.manifest).read_text())
        if manifest.get('schema') != SCHEMA or manifest.get('kind') != 'finder':
            raise ValueError('Not a finder manifest')
        print(json.dumps(export_package(manifest, args.destination, lambda e: print(json.dumps(e), flush=True)), ensure_ascii=False))
        return
    if args.action == 'scan':
        manifest = scan(args.root, args.user)
        text = json.dumps(manifest, ensure_ascii=False, indent=1)
        if args.output:
            Path(args.output).write_text(text)
        else:
            print(text)
        return
    manifest = json.loads(Path(args.manifest).read_text())
    if manifest.get('schema') != SCHEMA or manifest.get('kind') != 'finder':
        raise ValueError('Not a finder manifest')
    print(json.dumps(copy(manifest, args.target_home, args.target_root, lambda e: print(json.dumps(e), flush=True)), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
