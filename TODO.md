# TODO: next big version

Source: outside analysis (comparison with KDE Linux, GNOME OS, Fedora Atomic, Pop!_OS, Zorin, Bazzite and others), checked against this repository on 2026-11-26.
Status: **have** = in the repo, **partial** = exists but incomplete or untested, **missing** = nothing found. "Untested" means: never run on real hardware or a real ISO.

Priority principle (from the analysis): reliability before new features. Windows switchers should never have to repair the system in a terminal.

## Phase 1: Reliability

| Item | Status | What exists / what is missing |
| --- | --- | --- |
| CI/CD | partial | `.github/` only has issue templates (`bug_report.yml`, `config.yml`, `hardware_test.yml`), no workflows. Tests run by hand: `tools/run-offline-tests.py` (about 63 red tests only because tools are missing locally: quickshell, lua, rsvg-convert, xdg-user-dirs-update, website files). TODO: workflow that runs the offline tests in a container with those tools, a Rust build and test for the store, ISO build as a nightly job. |
| System rollback end to end | partial | Snapper, `snapshots.py` (create, delete, restore, schedule), bootloader hooks for GRUB, Limine, rEFInd, systemd-boot (`iso/installation.py`). Done in this branch, untested on a real ISO: snapshot boot from the live session (`recovery.py`, kexec), list in Settings > Backups, live boot entry. Missing: permanent rollback from the live session, snapshot start for systemd-boot and Limine (kernel on the ESP), LUKS. TODO: VM test matrix (4 bootloaders x ext4/Btrfs, rollback, snapshot boot). |
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
| Easy Anti-Cheat | partial | Setup via the CachyOS `eac-setup` (terminal) in Settings > Kernel. TODO: guided setup (TPM, IOMMU, Setup Mode checks in the UI), test on real hardware, decide whether the EAC kernel should be in the ISO. |
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

## Already there (do not redo)
Own shell (Quickshell on Hyprland), own settings, store (pacman, AUR, Flatpak), ISO with Calamares (online and offline, four bootloaders), Windows migration, file backup, AI assistant, device manager, signed component updates, hardware diagnosis, onboarding and help, accessibility, build infrastructure with pinned sources and QEMU tests.

## Next sensible steps
1. Get the ISO build and a UEFI VM test running on a machine with KVM (see `HANDOFF.md`), then fix what it shows.
2. Add CI workflows (Phase 1) so the offline tests run on every push.
3. Permanent rollback from the live session and snapshot start for systemd-boot and Limine.
4. Decide about channels (stable and testing) and the curated snapshot repository.
