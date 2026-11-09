# Changelog

Generated from `packaging/changelog.json` (newest first). Releases with downloads: https://github.com/Bennch/windoesnot/releases

## 0.1.0-27 (2026-11-09)

- Printers are detected automatically. Maintenance shows a printer card with the printer status.
- The firewall is on. Network name discovery (mDNS) stays allowed, so printers and other devices can be found.
- New account page in Settings: change your password and set a profile picture.
- New default apps in the software catalog: image viewer, calendar and contacts.
- Settings has fewer pages. Account and info are combined.
- VMware guests use software rendering. The screen no longer stays black.
- Maintenance shows the firmware version of your computer.
- Installer and boot: a boot error in the time service is fixed. Startup no longer waits for time synchronization.

## 0.1.0-26 (2026-11-09)

- System updates stay possible: the window bars (Hyprland plugins) and the embedded terminal no longer depend on a fixed Hyprland, Qt or C++ library version. They are rebuilt automatically after an update. The WinDoesNot update channel is set up from the start.
- A guard in the Store warns when a system update outruns our window bars. You can wait or update anyway.
- There is an English and a German ISO. The start menu, installer, login screen and boot menus follow the chosen language. The kernel parameter windoesnot.lang=en or de changes the language at boot.
- The taskbar comes back when you unplug and replug the main monitor's cable. New in the desktop and taskbar context menus: "Restart interface".
- The desktop context menus no longer have a scrollbar. "New" opens its own menu next to it, and the menus follow light/dark, accent colour and corner radius from the settings.
- New in the installer: icon for the GTA 2 guide.
- New boot themes for rEFInd, Limine and GRUB with the WinDoesNot logo, a background and a clearly visible selection. You can switch them on and off in Settings > Background. The switch also detects GRUB after installation.
- Windows migration: files from the Windows desktop land in the right folder, sizes are shown in KiB, there is a note about passwords, and the false warning triangle is gone.
- Web apps start as their own windows without a browser bar and with their own icon.
- The ArtCraft apps (Launcher, PdfCraft, PhotoCraft, VectorCraft, FilmCraft, Alpha) can be selected and are downloaded after installation.
- The terminal greets you with a banner and system info. You can turn it off in Settings > Apps > Shell.
- Desktop: copy, cut and paste (Ctrl+C, Ctrl+X, Ctrl+V and menu) and dropping files from the file manager. Icons no longer jump when you minimize.
- The Alt+Tab switcher is now version 4.5.0 and appears on the main monitor. The accent colour applies immediately.
- The workspace overview is updated and follows accent colour and corner radius immediately.
- The interface starts on the main monitor without jumping over from another monitor.
- Installer: the launcher is removed after installation, the live ISO boot menu is easy to read, and the version is shown in the banner.
- New icon for the Graphics app.
- If the wallpaper service hyprpaper crashes without 3D acceleration, a fallback now takes over.

## 0.1.0-25 (2026-11-07)

- The installer has a new page "About WinDoesNot", and the logo on the welcome page is smaller.
- More apps in the installer, including Google Chrome, Sublime Text and AI tools. They are installed after setup, once you are online. Web apps such as Netflix or YouTube are created as their own launchers.
- The standard folders (Documents, Pictures and so on) follow the system language, also when you change it later.
- Flatpak with Flathub is prepared, plus an additional icon theme so the Store shows more app icons.
- The Store lists apps from the installer that are still waiting to be installed.
- The audio widget has a mixer: volume and mute for each application, switchable with the output devices. The volume icon now matches the one in the taskbar.
- The graphics icon in the taskbar shows temperature, load, fan, power and memory of the graphics card with one click, with a switch for the graphics service. A double-click still opens the graphics settings.
- In the Start button's context menu, "Installed apps" now opens the WinDoesNot Store directly on the Installed page.

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

