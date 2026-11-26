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
