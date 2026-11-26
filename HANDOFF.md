# Handoff: Recovery, EAC, Store, ISO test (2026-11-26)

Branch `claude/bold-carson-44sqx9` (Bennch/windoesnot), store branch `claude/aur-install-script-review` (Bennch/windoesnot-store). Nothing is merged; no PRs.

## Done (all pushed)
- `iso/packages-extra.txt`: gvfs-mtp, gst-plugin-dav1d, ghostty-terminfo, efibootmgr, cachyos-recovery, kexec-tools.
- `iso/installation.py`: `install_recovery()` runs CachyOS' recovery installer after a UEFI install (non-fatal). Test: `tests/test-recovery-install.py`.
- Settings > Kernel: Easy Anti-Cheat section (`eac-setup` / `eac-status` in a terminal). QML untested (no quickshell here).
- `desktop/lib/windoesnot/recovery.py`: finds Snapper snapshots of WinDoesNot on Btrfs disks, boots one read-only via kexec (snapshot's own kernel + initramfs, overlay hook from `iso/installation.py`). Commands: `list`, `scan-cache`, `boot DEV SUBVOL KERNEL`, `menu`. Test: `tests/test-recovery-snapshots.py`.
- Live session: `iso/windoesnot-recovery-scan.service` (wired in `tools/prepare-profile.py`) writes `/run/windoesnot/restore-points.json` and shows the menu entry only if something is found. Settings > Backups lists the points in the live session (`BackupsCategory.qml`, polkit `org.windoesnot.recovery.policy`).
- Live boot menus (GRUB, BIOS, UEFI): extra entry "Wiederherstellungspunkte von der Festplatte starten" (`windoesnot.recovery=1`, `tools/live_boot_menu.py`, `desktop/bin/windoesnot-recovery-boot`). Test: `tests/test-live-recovery-entries.py`.
- Store (`windoesnot-store`): AUR review now also fetches and checks the `install=` script (`src/core/aur_review.rs`, UI in `src/ui/aur_review.rs`). Core tests pass in an isolated crate; GTK UI never compiled.

## Not verified
- ISO never built; kexec boot of a snapshot, scan service, QML in Settings, boot-menu entries on the real upstream CachyOS layout (`check-profile.py` asserts them at build time).
- Offline tests: `tools/run-offline-tests.py` has ~63 red tests, identical before and after my changes (missing quickshell, lua, rsvg-convert, xdg-user-dirs-update, website files).
- Not done: kms hook removal (kept on purpose, Plymouth splash depends on it), permanent rollback from the live session, LUKS, raising the 384 MiB ESP-reuse minimum for the 70 MB recovery image.

## ISO build attempt (cloud session) and why it stopped
Build: privileged Arch container, `./build-and-run.sh --build-only --language de --build-id vmtest-de`. It got through `fetch-sources` and into `prepare-profile`, then `tools/prepare-boot-language.py` failed: the sandbox proxy returned 403 for
`https://github.com/systemd/systemd/archive/refs/tags/v262.1.tar.gz` (sha256 100fc873b848b9b0297d8a705e8e2ed326256c8483d9960ee1ffe264c8a5c3e3). The other two sources (rEFInd, Limine) were fine. That is a sandbox policy, not a repo bug.

## Next steps
1. Build the ISO where the download works, with KVM: `./build-and-run.sh --language de` (needs archiso on Linux).
2. In a UEFI VM: install WinDoesNot on Btrfs with GRUB (kernel lives inside the snapshot), create a snapshot, reboot the ISO, choose the new boot entry, start the point, check it boots read-only with the overlay.
3. Check `check-profile.py` passes against the real upstream menu files; check the Backups page in the live session and the EAC buttons.

## Mac note (M3 Pro)
Apple Silicon has no KVM and QEMU's HVF only accelerates arm64 guests, so an x86_64 ISO runs emulated (very slow), and `mkarchiso` needs Linux (Docker Desktop with amd64 emulation is slow too). Use a Linux x86_64 machine with KVM for the build and VM test; use the Mac for code, tests and review.

## ESP-based snapshot start (systemd-boot, Limine)
`recovery.py` locates kernel and initramfs on the ESP of the same disk (snapshot, `windoesnot-restore-<N>.conf`, limine.conf entry, or newest ESP kernel only if its version is in the snapshot's /usr/lib/modules). `desktop/lib/windoesnot/sdboot_snapshots.py` creates the systemd-boot entries. Tests: `tests/test-recovery-snapshots.py`, `tests/test-sdboot-snapshots.py`. Never run on a real ESP or Limine install; the limine-snapper-sync file layout is an assumption (see the docstring of `limine_entries`).

## VM test results (second ISO, 2026-11-26, emulated UEFI, no KVM)
Built with the merged branch (rollback, ESP-kernel snapshots, EAC check, sushi, undo menu). Checked over the serial console in the live session:
- GRUB menu shows "Wiederherstellungspunkte von der Festplatte starten"; booting it puts `windoesnot.recovery=1` on the command line, `windoesnot-recovery-scan.service` runs and writes `/run/windoesnot/restore-points.json`, the menu entries appear, `windoesnot-recovery-boot` starts the terminal menu.
- Real Btrfs on a second disk (subvolumes `@`, `@/.snapshots`, a read-only snapshot): `recovery.py list` finds it; `rollback` makes the snapshot the new `@` (marker file back to the old content), keeps the old root as `@-before-restore-<time>`, moves `.snapshots` into the new root; `undo` swaps back. All real `btrfs` commands and output parsing worked.
- `kexec -s -l` with a real kernel and initramfs and a snapshot command line loads (`kexec_loaded` = 1) and unloads.
- `eac_check.py` runs (VM: no TPM, no IOMMU table, as expected), `sushi`, `cachyos-recovery`, `kexec-tools` are installed.
Still NOT verified: actually booting into a snapshot (kexec reboot with the installed system's own initramfs and overlay), systemd-boot restore point entries and hooks, Limine snapshot start, the Settings > Backups list and the Kernel page in the GUI (the emulated screen stayed black), the installer path on a real install, Secure Boot.

## Status end of day (2026-11-26) and plan for the first session with a KVM host and real hardware
Everything below is merged and pushed on `claude/bold-carson-44sqx9`; nothing is merged to `main`, no PRs yet. The offline tests are green except tests that need quickshell, rsvg-convert and similar (49 red, none new). `test-backup-integration.py` is timing-flaky.

Implemented since the first handoff (all unit-tested with fixtures; see TODO.md rows for details): permanent rollback / undo from the live session; snapshot start for systemd-boot and Limine (ESP kernels) and systemd-boot restore-point entries; EAC prerequisite check; Task Manager (`windoesnot-taskmanager`, Ctrl+Shift+Esc); Capture overlay (Print, Super+Shift+S/R; theme from settings.txt; screenshot, region/window/screen, recording); encrypted restic backups engine; branded WinDoesNot recovery entry for all four bootloaders (`iso/recovery_entries.py`); Security Center page (Settings > Security); stable/testing update channels (tools + client + Updates switch); LUKS audit (`docs/ENCRYPTION-AUDIT.md`); `fetch-sources.py` fix; ESP reuse minimum 480 MiB; CI workflow (never run on GitHub); cairo GTK renderer on emulated GPUs.

Seen working in an emulated UEFI VM (virtio-vga, no KVM): live boot entry, scan service, Backups list data, rollback/undo on real Btrfs, kexec load, Task Manager window (with the cairo renderer), Capture overlay end to end incl. region drag, PNG output and recording with the Stop pill.

NOT verified anywhere (do these first on real hardware / KVM):
1. Boot into a snapshot for real (kexec reboot, overlay hook) on GRUB, systemd-boot, Limine, rEFInd installs; systemd-boot restore point entries/hooks; the new recovery entries per bootloader (assumptions are listed in `iso/recovery_entries.py` and TODO.md).
2. QML pages never looked at: Settings > Backups (found restore points in the live session), > Kernel (EAC checks), > Security (new), > Updates (channel switch), file backup card (restic engine, one-time key dialog).
3. Capture overlay: window pick, monitor pick, options popover, clipboard (`wl-copy` timed out in the slow VM), real notifications, multi-monitor, Stop pill inside the recording.
4. Real GPUs: GTK apps with the normal renderer (the cairo fallback only applies to emulated GPUs).
5. Secure Boot (nothing built), EAC on a machine with TPM 2.0, LUKS install per `docs/ENCRYPTION-AUDIT.md` (10-step plan), restic to a network target, a real testing-channel publish (needs gpg), the store install-script review (store repo branch `claude/aur-install-script-review`, GTK part never built).

How the ISOs were built here (details in CONTRIBUTING.md 'Build host requirements' and TODO.md 'Build notes'): privileged Arch container, the CachyOS keyring in the host pacman keyring, rust, store/audio/other forks cloned (now done by tools/fetch-sources.py), the systemd v262.1 tarball rebuilt from the git tag (checksum matches). VM test tips: `-device virtio-vga` plus `-device usb-ehci -device usb-tablet` for mouse input via QMP; desktop takes 10-15 minutes under emulation; serial console gives root without password on the live ISO.
