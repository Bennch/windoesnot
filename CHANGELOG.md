# Changelog

Generated from `packaging/changelog.json` (newest first). Releases with downloads: https://github.com/Bennch/windoesnot/releases





## 0.1.0-32 (2026-11-19)

- Updates check package dependencies and protect boot entries when kernels change.
- The Store explains system update problems more clearly.
- New firewall in the Network app: open ports live with explanations, a profile per network (Home, Public, Trust only), rules and templates. It replaces ufw on update automatically; if you switch it off, it stays off.
- New Diagnosis under Settings, Maintenance & Kernel: quick checks (sound, Bluetooth, network, disk space, graphics, firewall and more), errors since boot and a report without personal data to copy or save.
- Share folders in the network: right-click in the file manager, own dialog, access from Windows and Mac (Samba). Guests read-only and only on request.
- Calendar with holidays for Germany, Austria, Switzerland, the US, the UK and France, week numbers and a selectable first day of the week. Everything can be switched off in Settings.
- Notifications: position and on-screen display are adjustable; the notification centre stays at the top centre.
- Settings: Flatpak app permissions as clear tables, every page scrolls all the way down, new card Export my system.
- Store: Update WinDoesNot only below the list of updates, shown when there are some.
- The network icon shows the cable symbol on a wired connection; Open Network in the right-click menu opens the Network app, plus Open Firewall.
- New search: files and folders first (sorted by name, your folders and recency), apps with abbreviations like “vsc”, a calculator with percentages and units (5 km in mi), type filters with Tab or /pdf, /images, “Search the web” and “Run in terminal”. The search learns which apps you start often.
- Emoji and special characters: all emoji with German and English names plus a tab with special characters (quotes, dashes, maths, currencies, arrows, accents). Enter types the character straight into the text field.
- Web apps get their own window without browser bars and the website's icon; create your own under Settings, Apps. Netflix, Prime Video and Disney+ stay in the browser (copy protection).
- Looks: save your own looks with a name (light/dark, accent colour, corner radius, wallpaper).
- Desktop right-click on files and folders in file manager order: Open, open and copy file path, Send to (nearby device, network share), Cut, Copy, Delete, Rename, Properties.
- Installer: ten runtimes to install later (Python, Node.js, Java, .NET, C/C++, PHP, Go, Rust, Ruby, Kotlin).
- Search: apps are found by German and English names and keywords (“screenshot” finds Screenshot/Bildschirmfoto); every app has an icon; files show the icon of their type.
- Store: the Install button locks with a spinner while an app is queued or installing; names and icons appear correctly right after the first start; optimized builds for your processor no longer count as updates, and installing one app does not download hundreds of them.
- Start menu: Show desktop works again; Disk Management, Event Viewer and Power Statistics ship with the system; Papers opens PDF files.
- Windows in floating mode: snapping reacts to every pointer motion, the preview follows the pointer and leaves a little more time to let go; windows then jump into place faster.
- New layout menu on the maximize button like in Windows 11: six arrangements with individually clickable zones that light up in the accent colour. It also works for apps with their own title bar such as Steam, Discord and Zoom.
- Steam, Discord and Zoom: can be dragged by their own bar again, minimize and maximize work (including toggling back), a click on the Steam tray icon opens Steam.
- Edges: dragging a side edge changes only the width, the bottom edge only the height, the corners both; the arrows stay visible while hovering. Windows snapped side by side follow the shared edge immediately.
- Settings, Updates: the Update button now opens the Store on the updates page even when it is already running; before, nothing happened.
- All GTK programs (Store, Network, Bluetooth and more) show a single close button in the window bar instead of two.
- Start menu: search also finds programs by their English or German name and keywords ("screenshot" finds Bildschirmfoto).
- Fixed: updates and installs aborted on systems with GRUB, rEFInd or Limine (Limine is now offered on UEFI only); the holiday and week number switches did not respond; Performance mode was not offered; the Nearby window was cut off at the top; Does now says when it is not set up yet; the Network app has a single close button.

## 0.1.0-31 (2026-11-17)

- Moving from Windows: several Windows accounts no longer end up in one folder; each further account gets its own subfolder. The page shows which system the data comes from.
- Moving: Thunderbird profiles, Windows Live Mail and Outlook mailboxes (PST) come along as e-mail. Saved browser passwords can be protected with their own password and saved as a file for the browser import.
- New: Linux to Linux. Home, Wi-Fi connections and the package list of another Linux on the disk can come along when you install alongside.
- New: Remove old system under Settings, Maintenance. After the move, the assistant removes Windows and gives the space to your system. It shows exactly what disappears first and asks for confirmation.
- The installer now says up front that the move only works with Install alongside. The first start has an optional donation card.
- New: keyboard shortcut overview and a guided welcome checklist for the first start.
- New: app permissions for Flatpak programs in the settings. You see what an app may access.
- New: media format check and help for Windows programs (with Bottles).
- New: Looks under Settings, Appearance. Six ready-made combinations of light or dark, accent colour, corner radius and background, with a way back to your own settings.
- The exporter for Windows 7 and 8.1 now has three steps with a sidebar and matches the look of the large Windows app.
- Shortcut overview with key caps. The welcome checklist ticks Wi-Fi, updates and shortcuts by itself.
- Optimized package builds for your processor no longer count as hundreds of updates. The Performance power plan stays visible even when your device does not offer it.

## 0.1.0-30 (2026-11-15)

- Updates from older versions: fixed a file conflict on the Ghostty launcher shim so pacman -Syu runs through cleanly.

## 0.1.0-29 (2026-11-14)

- Installation with the systemd-boot menu no longer aborts. If the German translation does not match the version, the standard English menu stays.
- Old computers: if an old NVIDIA card is detected, the nouveau driver is no longer blocked and the desktop starts in Lite Mode with software drawing, fewer effects and a light terminal. Settings, Maintenance: Lite Mode can be switched on and off.
- Less background load: Bluetooth, notifications, network and volume no longer poll constantly but react to events. If a service hangs, processes no longer pile up. This helps most on weak PCs.
- Wallpaper: a new renderer replaces hyprpaper and also works without 3D acceleration, for example in virtual machines. If it does not start, it is started again.
- File manager: right-click scripts and programs, Run as administrator.
- Settings, Maintenance: the new Your device card shows processor, memory and graphics and recommends Lite Mode on older devices. Nothing is sent.
- Settings, Maintenance: new configuration files (.pacnew) are shown with a comparison. Nothing is changed automatically. The Desktop state card shows configuration errors and loaded window extensions.
- Sharing: the window shows your own IP address and the addresses of devices found.
- Start menu: technical programs are hidden and can be shown with a switch.
- Installer: German texts consistently use the informal du, and Größe instead of Grösse.
- The desktop icons restart automatically after a start error.
- The pacman warning about DownloadUser is gone.
- Older machines: All bundled apps (Store, Network, Bluetooth, Audio, Graphics, Device Manager) now run on any 64-bit processor. Before, they crashed on computers whose processor is older than the build machine's.
- Desktop icons appear reliably on slow machines; startup now waits longer for the icon layer.
- Faster startup: the icon mapping is only rebuilt when the list of installed apps changes.
- The weather window appears at its place above the taskbar right away instead of gliding in from the middle of the screen.
- Older machines: Lite mode now also switches itself on once for machines with less than 3 GB of memory or a processor without SSE4.1. It can be switched off in Settings.
- Legacy NVIDIA cards: after installation the desktop starts with the free nouveau driver. The blue error screen for graphics driver problems now explains in German and English what to do.
- Installer: “Install alongside” preselects the only shrinkable partition and shows its hint clearly. On disks with extended partitions (MBR) the new partition is created correctly.
- Installer: Windows data migration works with “Install alongside” and leaves the Windows data untouched. With erase, replace or manual partitioning it is stopped before partitioning.
- Installer: files from the live session (Desktop, Documents, Downloads, Pictures, Music, Videos) are carried over to the new user account.
- Installer: on old computers the installer window renders without graphics glitches, and system files are copied with lighter compression.
- Screenshots: after a capture a notification appears at the top right, a click opens the picture. It is also on the clipboard.
- Terminal in lite mode: the pinned taskbar launcher works again, and the window groups under the Ghostty icon.
- Remote support: the windoesnot-remote-support command allows help from afar on request, only after explicit confirmation.

## 0.1.0-28 (2026-11-12)

- At first start you set resolution, zoom and pointer speed. A new display setting is reverted after 12 seconds unless you keep it.
- Snap windows: dragging a title bar shows a preview. The maximize button opens the layout picker.
- Alt-Tab shows previews of each window.
- New full-screen task view: all windows at a glance.
- Window mode: existing windows float when you switch, and you can switch in both directions.
- Battery and power: the popup shows brightness, power profile and night light and fits its content. The taskbar shows the battery level, and desktop PCs without a battery show a bolt symbol.
- Brightness also works with several external monitors.
- If the system language is missing, it is detected. Setup asks for your password and shows progress.
- File sharing: drag files onto the sharing icon and the window opens with a drop zone. History is its own tab, and a green light shows that receiving is on.
- If the firewall blocks LocalSend, open the ports with one click.
- System settings: kernel selection and sections are clearer. The Wi-Fi password dialog closes after a successful connection.
- Installer and boot: choosing the mirror server no longer causes a boot error.
- If the desktop shell crashes in its first seconds, it starts again automatically.

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
