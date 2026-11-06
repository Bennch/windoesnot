# Changelog

Generated from `packaging/changelog.json` (newest first). Releases with downloads: https://github.com/Bennch/windoesnot/releases

## 0.1.0-24 (2026-11-06)

- New app “Graphics” (based on LACT): control and monitor AMD, NVIDIA and Intel graphics cards, with fans, power limit, clocks and temperatures. It follows the WinDoesNot look and takes language, light/dark and accent colour from Settings.
- The taskbar has a graphics icon (double-click opens the Graphics app; show or hide it under Settings → Apps). App icons in the tray keep their own right-click menus; the Audio app menu opens from the existing volume icon. The volume icon now shows the volume.
- Store: updates are sorted by source and topic (programs, system & drivers, tools, libraries); the home page has a quick search with results while typing, plus popular and trending apps from Flathub. The details page shows screenshots, a formatted description and more information, and says when a system update is required.
- Store: Flatpak is preferred for new installs when available. A progress bar with expandable logs, optional immediate actions and refreshed installation states make package management clearer.
- The Start menu refreshes newly installed apps when opened and shows full names for long app labels in tooltips.
- Network, Bluetooth and Audio share the WinDoesNot look with the logo. Bluetooth starts with the device list, the Wi-Fi page is no longer hidden when an Ethernet port exists, and Audio follows language, light/dark and accent colour from Settings and opens on “Players”.
- The shared clipboard with virtual machines now also works in QEMU, in both directions.

## 0.1.0-23 (2026-10-31)

- Settings has a full-text search (Ctrl+F). It finds settings in any language, jumps to the switch and highlights it.
- Settings are regrouped: “Taskbar & start menu”, “Input, language & time”, and window radius and gaps now sit under “Appearance”.
- The About page shows the installed version instead of a fixed number.
- The weather and start menu settings are translated and also appear in English.
- Fixed: GTK 3 programs reported errors because of the Nautilus color rules.
- Already in 0.1.0-22 but not listed there: weather only with a location, instant terminal shell choice, and reworked Store, Bluetooth and Network windows.

## 0.1.0-22 (2026-10-31)

- Apps without their own icon show a matching stand-in icon instead of a placeholder image.
- The right-click menu of an app in the start menu closes with any click inside the menu.
- Selected folders and files in Nautilus follow the accent color from Settings. Changing the color closes open Nautilus windows.
- The audio mixer in the taskbar opens WinDoesNot Audio, with bundled EasyEffects presets.
- Battery and power: brightness via DDC/CI as well, and an eye-care (night light) mode.
- Images and PDFs open in dedicated viewers. Nautilus has a sidebar with the usual folders and follows the system language.
- New login screen “Silent”: shows your current wallpaper from the main monitor.

## 0.1.0-21 (2026-10-29)

- New Windows-like keyboard shortcuts: lock, show desktop, Task Manager and Settings are directly accessible.
- Settings now includes a dedicated battery/power page and a more consistent, consolidated navigation.
- Tray and taskbar context menus are anchored to their respective icons and close reliably when clicking outside.
- Nautilus now uses the WinDoesNot accent color in the file manager as well.
- The native Hyprland plugins hyprbars and hyprdrag are ported to the current Hyprland API.

## 0.1.0-19 (2026-10-24)

- The desktop packages include the public WinDoesNot release key for setting up signed package updates. The update channel needs a one-time setup.
- The update page now calls directly configured desktop files a “local desktop installation”.

## 0.1.0-18 (2026-10-24)

- During installation WinDoesNot detects your processor and enables the matching optimized CachyOS packages (x86-64-v3, v4 or Zen 4/5).
- Graphics drivers for NVIDIA, AMD, Intel and virtual machines are set up automatically, even offline, including 32-bit drivers for games.
- The fastest download servers are chosen automatically: during an online installation, otherwise on the first internet connection.
- After the first login a notification shows what was detected and set up.
- Store: choose the installation source (repositories, Flathub, AUR) and review AUR packages before building.
- New settings pages “Kernel and performance” (switch kernels, sched-ext) and “Maintenance” (mirrors, cache, keyring, drivers).
- Restore points before and after every program change; with GRUB, Limine and rEFInd an earlier state can be started from the boot menu.
- Five bundled wallpapers, selectable right in Settings.

## 0.1.0-17 (2026-10-23)

- Updates in plain language: one button for everything, grouped into WinDoesNot, programs and system, with restart hints.
- “Update now” opens the Store with all updates and important Arch notices right away.
- Backups are now called restore points and explain what is and is not saved.
- Does sits pinned right above the taskbar and closes normally again after detaching.
- The login screen shows the correct keyboard layout; the live system shows the boot logo.

## 0.1.0-16 (2026-10-23)

- The AI assistant is now called Does and has its own icon.
- A detached Does window opens again after it was closed.
- The settings update page shows real data: WinDoesNot changes, system updates, Arch news and whether a restart is needed.
- Backups: the password prompt appears inside the settings; listing snapshots no longer asks for a password.
- AUR can be toggled consistently from the Store and desktop settings; updates and search results follow the preference.

## 0.1.0-15 (2026-10-23)

- The terminal in the AI panel loads again.
- New users get the right icons from their first login.
- No Hyprland splash text in the background and no Hyprland update notice after upgrades.

## 0.1.0-14 (2026-10-22)

- The WinDoesNot Store has a fixed taskbar button (can be turned off in the settings).
- Programs installed during a session get their taskbar icon right away.
