# TODO: next big version

Source: outside analysis (comparison with KDE Linux, GNOME OS, Fedora Atomic, Pop!_OS, Zorin, Bazzite and others), checked against this repository on 2026-11-26.
Status: **have** = in the repo, **partial** = exists but incomplete or untested, **missing** = nothing found. "Untested" means: never run on real hardware or a real ISO.

Priority principle (from the analysis): reliability before new features. Windows switchers should never have to repair the system in a terminal.

## Phase 1: Reliability

| Item | Status | What exists / what is missing |
| --- | --- | --- |
| CI/CD | partial | `.github/` only has issue templates (`bug_report.yml`, `config.yml`, `hardware_test.yml`), no workflows. Tests run by hand: `tools/run-offline-tests.py` (about 63 red tests only because tools are missing locally: quickshell, lua, rsvg-convert, xdg-user-dirs-update, website files). TODO: workflow that runs the offline tests in a container with those tools, a Rust build and test for the store, ISO build as a nightly job. |
| System rollback end to end | partial | Snapper, `snapshots.py` (create, delete, restore, schedule), bootloader hooks for GRUB, Limine, rEFInd, systemd-boot (`iso/installation.py`). Done in this branch, untested on a real ISO: snapshot boot from the live session (`recovery.py`, kexec), list in Settings > Backups, live boot entry. Done, untested on a real disk: permanent rollback from the live session (`recovery.py rollback` / `undo` and the menu choices; plain `@` layout only, old root kept as `<root>-before-restore-<time>`). Done, untested on a real ESP: snapshot start for systemd-boot and Limine (kernel on the ESP: `recovery.py` finds copies, Limine entries or a matching current kernel; `sdboot_snapshots.py` writes systemd-boot restore point entries). Menu entry for `undo` done; bootloader regeneration after rollback/undo is a printed next-step message only (the installed system's hooks do it; `snapper -c root create` triggers them). Missing: LUKS, regenerating bootloader entries from the live session. TODO: VM test matrix (4 bootloaders x ext4/Btrfs, rollback, snapshot boot). |
| Hardware compatibility matrix | partial | `hwcheck.py`, `.github/ISSUE_TEMPLATE/hardware_test.yml`, README says Secure Boot and AMD graphics untested. TODO: published table (Intel, AMD, NVIDIA, laptops, docking, suspend, multi-monitor), test checklist, ideally a hardware database fed by the diagnosis report. |
| Secure Boot | missing | Only detection (`iso/boot_environment.py`). The ISO is not signed/shimmed. TODO: decide (shim and MOK, sbctl, signed UKI), test with Secure Boot on. Related: CachyOS `eac-setup` needs Setup Mode, see below. |
| Security audit of privileged helpers | partial | Polkit actions in `desktop/share/polkit-1/actions/` with fixed argv, tests like `test-system-tools.py`. TODO: systematic audit (input validation, TOCTOU, `pkexec` environment), including the new `recovery.py boot`. |

## Phase 2: Control over the operating system

| Item | Status | What exists / what is missing |
| --- | --- | --- |
| Stable / Testing / Nightly channels | partial | One signed channel (`UPDATE-CHANNEL.md`, `build-repository.py`, `publish-repository-r2.py`, `preflight-release.py`, `prepare-release.py`). No separate channels found. |
| Curated rolling release (frozen CachyOS/Arch snapshots) | partial | ISO is built from a pinned snapshot (`sources.json`, repository snapshot in the installer). Installed systems still take system packages straight from CachyOS/Arch. TODO: own mirror or snapshot repo, test then release, security fast path, disk space plan. |
| Automated release approval and update gate | partial | `test-update-gate.py`, `test-package-abi-guard.py`, `test-update-gate-inventory.py` exist. TODO: connect to CI and the channels. |
| Boot and update health check | missing | TODO: after an update, check the boot (for example systemd boot-counting) and roll back to the last snapshot on failure. |
| Absorb the CachyOS November release | partial | Small items done (`gvfs-mtp`, `gst-plugin-dav1d`, terminfo, `cachyos-recovery`, EAC section in Settings > Kernel). TODO: re-check `cachyos-drm-awaiter` and the initramfs `kms` hook on real hardware (kept on purpose), post-update step `chwd -a -f` for existing users, `systemd-boot-manager` UKI behaviour with `bootnames`. |

## Phase 3: Features for end users

| Item | Status | What exists / what is missing |
| --- | --- | --- |
| Recovery environment | partial | CachyOS recovery image is installed on the ESP after UEFI installs (`install_recovery()`), live-session recovery from disks (see Phase 1). Missing: our own branded recovery image that is reachable from the installed system's boot menu without a USB stick. |
| Repair (broken packages, services, bootloader) | missing | Parts exist: Maintenance page (`MaintenanceCategory.qml`), diagnosis (`DiagnoseCategory.qml`), `old-gpu-setup`. TODO: one guided repair flow. |
| Reset (factory settings, keep data) | missing | TODO: reinstall or reset with data kept (Pop!_OS style). |
| Windows Compatibility Center | partial | `windoesnot-windows-program` opens Windows programs (`desktop/bin`). No management of Wine prefixes or Bottles, no compatibility database. |
| Security Center | partial | Firewall with profiles, update page, Backups, but no single page. Missing: disk encryption status, Secure Boot status, one overview. |
| Hardware check before installing | partial | `hwcheck.py` and the Windows-side tools in `windows/` (`WinDoesNotSetup.ps1`, `WinDoesNotStick.*`). Compatibility database missing. |
| Easy Anti-Cheat | partial | Setup via the CachyOS `eac-setup` (terminal) in Settings > Kernel. Read-only prerequisite list (UEFI, TPM 2.0, IOMMU table, Secure Boot/Setup Mode, boot manager, snapshot boot, tool installed) in the same page via `eac_check.py`; QML not yet run in Quickshell. TODO: guided setup flow (act on the checks), test on real hardware, decide whether the EAC kernel should be in the ISO. |
| Gaming Center | missing | Steam, Proton, Lutris, Heroic only appear as catalog entries. |
| Sync (settings between computers) | missing | Looks like a "later" item; export exists (`ExportSystem.qml`, `export-dotfiles.py`). |
| Mobile Connect (KDE Connect) | missing | Not found in the repo outside the upstream Calamares netinstall list and a store text. |
| Store: AUR review | partial | PKGBUILD review existed. New in the store repo: install script check. TODO there: AppImage support, mirror ranking button, opt-in switch for AUR and Flatpak (check what exists first). |

## Phase 4: Platform and ecosystem

| Item | Status | What exists / what is missing |
| --- | --- | --- |
| WinDoesNot SDK and design guidelines | missing | `DESIGN-mirror.md` exists, no SDK or public API guide. |
| Developer mode (containers, dev environments) | missing | |
| Immutable edition | missing | Analysis says: not now. Keep pacman and AUR as the main path; optional later. |
| ARM64 | missing | Low priority. Note: the dev machine (M3 Pro) can only run x86_64 images emulated. |
| Hardware partners, preinstallation | missing | |

## Second input: comparison with WildOS (Debian 13, KDE Plasma 6, Kicksecure)

Checked against this repository on 2026-11-26. The comparison does not start any system, so "not found" below means "not found in the repo", not "does not exist". WildOS has an own app suite and a Windows VM mode; our strengths stay: Windows migration, AI assistant, tiling/floating, Lite mode, AUR, CachyOS performance, four bootloaders, device manager, own audio/graphics/network/Bluetooth apps.

### Merged with the roadmap above (same topic, raise priority)
- **Windows Mode (P0, new)**: Windows programs as single windows from a KVM/libvirt VM via FreeRDP (WinBoat or similar), taskbar and start menu integration, `.exe`/`.msi` association, auto start and pause, shared folders. Today: `windoesnot-windows-program` (82 lines) only points to Bottles and ProtonDB; the catalog has Bottles, virt-manager, Remmina, Lutris, Heroic, Steam, but no VM integration. Needs a Windows licence and about 16 GB RAM to be useful; GPU-heavy programs stay limited. Combine with the existing migration assistant.
- **Recovery and reset (P0)**: already in Phase 3. Add: graphical recovery at boot, undo of a rollback, snapshots on ext4 (rsync based; today only Btrfs and Snapper), separately stored kernel and initramfs per restore point (needed for systemd-boot and Limine).
- **Security Center (P0/P1)**: extends the Phase 3 item. Firewall profiles and updates exist; missing: LUKS2 default check in the installer, recovery key for encryption, Secure Boot status, security levels (standard, strict, maximum), AppArmor profiles, USBGuard, sysctl/kernel hardening, private reporting of vulnerabilities (SECURITY.md). Kicksecure is Debian based and cannot be installed on Arch; copy the ideas, not the packages.
- **Backups with encryption (P0)**: `filebackup.py` uses rsync. No encryption, no deduplication. Candidate: restic (or borg). Also: start a backup when the drive is attached, back up the Windows VM disk once Windows Mode exists.
- **Stable and beta channels (P0)**: same as Phase 2 channels.

### New items for desktop comfort (P2)
| Item | State in repo |
| --- | --- |
| Quick Look (preview with the space bar) | not found as a feature; search results are noisy, check `SearchWindow.qml` |
| Clipboard history with pinned entries, auto clear of sensitive data | history exists (cliphist, search window); pinning and sensitive clearing not found |
| Keep awake in quick settings | not found |
| Scheduled Do Not Disturb | switch exists (`NotificationSettings.qml`), schedule not checked |
| Snap Assist with window suggestions | snap layouts exist; suggestions not found |
| End a task from the taskbar, switch between windows of one app | not checked |
| Configurable title bar double click | not found |
| Different power profiles on battery and on AC | partly (`PowerCategory.qml`, power-profiles-daemon) |
| Own system dialogs and XDG desktop portal UI | partly (Flatpak permission dialogs); no own portal |
| Screenshot and screen recording centre | `windoesnot-capture` (region/window/screen, delay, clipboard, wf-recorder recording, Win+Shift+S, Win+Shift+R) exists; untested on a real session (GTK window and Hyprland binds), no region-recording UI polish or monitor picker |
| RGB (OpenRGB), cooling monitor | not found, optional |

### Own apps worth building (priority from the input, my notes in brackets)
High: Task Manager (we ship `gnome-system-monitor`; a Windows-like own one is a real gap), Remote Center (SSH, RDP, SFTP; Remmina is in the catalog), Capture, Report (error report that the user can read before sending; `MaintenanceCategory`/diagnosis report exist).
Medium: Notes, Archive.
Low: Mail, PDF, Music, Videos, Office: integrate existing apps (LibreOffice is in the catalog); do not build an own office suite.

### Ecosystem
Shared UI component library with a gallery (we have QML components, no gallery), SDK and design rules, ISO build via Docker on Windows and macOS (today Linux only; this session needed an Arch container with Rust and the CachyOS keyring, see "Build notes"), interactive tour (welcome assistant exists), OpenRGB, cooling monitor, own notes and archive apps.

### Top five (my order after merging both inputs)
1. Reliability first: CI, VM tests for rollback on all four bootloaders, Secure Boot. Without this the rest is hard to trust.
2. Recovery and reset, including the boot menu entry.
3. Windows Mode.
4. Security Center and hardening, LUKS2 default, encrypted backups with restic.
5. Quick Look and the small comfort items (cheap and visible).

## Build notes (found while building the ISO in a cloud container)
- `tools/fetch-sources.py` clones the Device Manager, Bluetooth, Network and Graphics forks, but not the Audio fork and not the Store; `prepare-profile.py` then stops with "Audio pin not found". Clone them by hand or add them to the script.
- A build host needs: archiso, python-yaml, librsvg, rust (store vendoring), grub tools, and the CachyOS keyring in the host pacman keyring (`pacman-key --init`, then `--populate cachyos`).
- The systemd v262.1 tarball for the translated bootloaders can be rebuilt bit-identically from the git tag with `git archive --prefix=systemd-262.1/ v262.1 | gzip -n -6`; the pinned sha256 matches.

## Already there (do not redo)
Own shell (Quickshell on Hyprland), own settings, store (pacman, AUR, Flatpak), ISO with Calamares (online and offline, four bootloaders), Windows migration, file backup, AI assistant, device manager, signed component updates, hardware diagnosis, onboarding and help, accessibility, build infrastructure with pinned sources and QEMU tests.

## Requirement: restore point and recovery entry in ALL bootloaders (user request)
Goal: the same restore point / recovery option in the boot menu of every supported bootloader, on the installed system and on the live ISO.
- Live ISO: entry exists in GRUB (seen in the built ISO). BIOS (Syslinux) and UEFI systemd-boot entries are generated and checked by `check-profile.py`, not yet seen in a menu.
- Installed system, today: GRUB (grub-btrfs), Limine (limine-snapper-sync) and rEFInd (refind-btrfs) list snapshots; systemd-boot gets up to 3 restore point entries from `desktop/lib/windoesnot/sdboot_snapshots.py` (pacman pre/post hooks and a path unit; untested on a real system). Recovery image (CachyOS `cachyos-recovery`) is placed on the ESP for UEFI installs and registered for Limine and EFI; GRUB entry only for BIOS.
- Done (untested on real hardware): snapshot entries for systemd-boot (kernel and initramfs copy per restore point on the ESP, BLS entries, max 3, cleanup). TODO: one test per bootloader (4 x ext4/Btrfs), our own recovery entry (branded) in all four, BIOS case for GRUB and Limine, Secure Boot signing of the extra files.

## Next sensible steps
1. Get the ISO build and a UEFI VM test running on a machine with KVM (see `HANDOFF.md`), then fix what it shows.
2. Add CI workflows (Phase 1) so the offline tests run on every push.
3. Permanent rollback from the live session and check the new ESP-based snapshot start (systemd-boot, Limine) in a VM.
4. Decide about channels (stable and testing) and the curated snapshot repository.
