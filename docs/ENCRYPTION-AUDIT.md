# Disk encryption (LUKS2) audit

Status: audit from reading code. Nothing here was run in a VM or on hardware. Every statement is tagged:
**[code]** = read in our tree or in the upstream CachyOS Calamares checkout (`upstream/cachyos-calamares/`),
**[assumed]** = follows from how a tool normally behaves but was not verified here, **[untested]** = needs the test plan below.

## 1. Summary

- The installer almost certainly already shows an "Encrypt system" checkbox with a passphrase field (upstream default, we do not turn it off) and creates LUKS2. It is not advertised anywhere in our own pages, it is off by default, and nothing was ever tested. **[code]**
- Because our layout puts **/boot on the unencrypted FAT ESP** for every bootloader, the usual LUKS pain points (GRUB reading LUKS2/argon2id, a keyfile to avoid a second prompt, systemd-boot needing an unencrypted ESP) do not apply. The kernel and initramfs are public, the root (and everything in it) is encrypted, the initramfs asks for the passphrase once. **[code]**
- The installed system very likely boots, and snapshots inside it very likely work (the snapshot overlay hook is independent of LUKS). **[assumed, untested]**
- The live-session tools do not work with LUKS: `recovery.py` never sees a locked volume, cannot unlock it, and its kexec command line has no `rd.luks.uuid`. Permanent rollback refuses LUKS on purpose. **[code]**
- Recommended: make "Encrypt" a visible, explained option (default off, one sentence about the lost-passphrase risk), test it per the plan, then consider default-on for Erase disk on laptops. Do not make it default before the plan passes.

## 2. What the installer offers today

| Question | Answer | Evidence |
|---|---|---|
| Encrypt checkbox | Shown for Erase disk, Replace partition and Install alongside; hidden for Manual (manual has its own "Encrypt" box in the create-partition dialog) | `partition/gui/ChoicePage.cpp` `shouldShowEncryptWidget()`; `PartitionViewStep.cpp:969` reads `enableLuksAutomatedPartitioning` with default **true**; upstream `partition.conf` has it commented out; `tools/prepare-profile.py:304-309` copies that file and only changes ESP settings. **[code]**, UI never seen running. |
| Pre-checked | No (`preCheckEncryption` default false, `Config.cpp:450`) | **[code]** |
| Filesystems that can be encrypted | btrfs, ext4, xfs, f2fs (our `availableFileSystemTypes`); zfs removed in our profile | `prepare-profile.py:307` **[code]** |
| LUKS version | LUKS2 (`luksGeneration: luks2` at top level of upstream `partition.conf`; we drop `bootloaderOverrides`, so the top level wins) | **[code]** |
| Key derivation | Not set by us or Calamares. The partition module passes only the generation to kpmcore, so cryptsetup's own default applies: argon2id for LUKS2 on current cryptsetup. `luks2Hash: default` in `luksbootkeyfile.conf` only concerns the keyfile job. | **[assumed]**; check with `cryptsetup luksDump` (test plan step 3) |
| Is /boot encrypted | No. `efiSystemPartition: /boot`, 1024M FAT, kernel and initramfs on it (comment in `prepare-profile.py:305`). Calamares therefore treats it as "unencrypted separate /boot": no `crypto_keyfile.bin` (`LuksBootKeyFileJob.cpp:286`), no `GRUB_ENABLE_CRYPTODISK` (`grubcfg/main.py:288`), no keyfile in initramfs FILES (`initcpiocfg/main.py:176,186`) | **[code]** |
| Swap | None (`initialSwapChoice: none`, `userSwapChoices: [none]`), so no encrypted swap and no hibernation | **[code]** |
| Windows-switcher relevance | Our boot page mentions BitLocker for the existing Windows partition (`windoesnotboot/BootSelectionWidget.cpp:216`). The new encrypt box encrypts only the new WinDoesNot partition. | **[code]** |
| Boot-menu reuse | Refuses an encrypted target by design (`windoesnotbootreuse/main.py:32`) | **[code]** |

## 3. Initramfs and kernel command line

- Our source file `/etc/mkinitcpio-windoesnot.conf` has `base systemd ... sd-vconsole ...`, and `initcpiocfg.conf` sets `useSystemdHook: true` (`prepare-profile.py:247,338`). Calamares' `initcpiocfg` builds the hook list itself: `base systemd autodetect microcode kms modconf block keyboard sd-vconsole [plymouth] sd-encrypt filesystems` (fsck omitted for btrfs), then appends `windoesnot-boot-errors`. So the **systemd-based `sd-encrypt`** is chosen, not `encrypt`, whenever `systemd-cat` exists in the target. Keyboard and vconsole come before it and plymouth comes before it (needed for a graphical prompt). **[code]**
- Kernel parameters come from `bootloader/main.py:get_kernel_params` (systemd-boot, Limine, rEFInd) and `grubcfg/main.py` (GRUB). Because `/etc/mkinitcpio.conf` contains the `systemd` hook, they use the systemd naming: `rd.luks.uuid=<LUKS UUID>` plus (non-GRUB) `root=/dev/mapper/luks-<UUID>`. GRUB gets `rd.luks.uuid=` only and relies on `grub-mkconfig` for `root=UUID=<inner fs UUID>`. **[code]**. The detection `grep '^HOOKS.*systemd' /etc/mkinitcpio.conf` depends on `initcpiocfg` running before `bootloader`; `tools/check-profile.py:60` asserts the order of `initcpiocfg` relative to our modules, but not that LUKS naming is produced. **[code]**
- Our snapshot hook: `enable_snapshot_hook()` (`installation.py:65`) only removes and re-appends its own hook at the end of `HOOKS`, so the hook order `sd-encrypt` before `filesystems` stays intact. The overlay unit runs `After=initrd-fs.target`, i.e. after the encrypted root is open and mounted at `/sysroot`; its checks (`findmnt` source `*/.snapshots/*/snapshot]`, btrfs ro property) do not care that the source is `/dev/mapper/luks-...`. **[code]**, boot with a snapshot **[untested]**.
- The upstream `windoesnot-boot-errors` hook and plymouth were never checked for the passphrase prompt (does the splash show a password box, does the keyboard layout match the one used in the installer). **[untested]**

## 4. Gaps per bootloader

All four write the cmdline from the same `get_kernel_params`, so the cmdline gap is shared; the differences are snapshots.

| Bootloader | Boots encrypted root? | Snapshot start from the installed system | Gap |
|---|---|---|---|
| GRUB | Expected yes: GRUB reads kernel and initramfs from the ESP, never opens LUKS, so LUKS2 and argon2id are irrelevant. `GRUB_ENABLE_CRYPTODISK` stays unset. **[code]** | `grub-btrfs` builds menu entries by reading `/boot` inside each snapshot. In our layout `/boot` is the ESP, so how those entries find a kernel at all is not clear from the code; with LUKS GRUB cannot read the btrfs root either. Probably the snapshot submenu is empty or wrong under LUKS. **[assumed, untested]**. Also GRUB cannot read btrfs reliably here anyway (`prepare-profile.py:305`). | Verify what the snapshot submenu contains on an unencrypted install first, then on LUKS. If it only worked via GRUB reading btrfs, it cannot work under LUKS. |
| systemd-boot | Yes: ESP is unencrypted by construction. `/etc/kernel/cmdline` is written with `rd.luks.uuid`. **[code]** | `sdboot_snapshots.py` copies the running entry's options (`base_options`), drops `root=`, `rootflags`, `ro` (`DROP_OPTIONS`) and writes `root=UUID=<btrfs UUID> rootflags=subvol=... ro` plus the kept words. `rd.luks.uuid=...` survives the filter, so the restore entries should unlock. **[code]**, `findmnt` gives the inner btrfs UUID. **[untested]** | Test only. If the running cmdline is unavailable (fallback path) the entry has no `rd.luks.uuid`. |
| Limine | Yes (ESP). `KERNEL_CMDLINE[default]` in `/etc/default/limine` includes `rd.luks.uuid`. **[code]** | `limine-snapper-sync` writes entries from that cmdline template. **[assumed]** | Test only. |
| rEFInd | Yes. `boot/refind_linux.conf` carries the same cmdline; our `configure_refind_entries()` copies its first line into `windoesnot-linux.conf`. **[code]** | `refind-btrfs` clones boot stanzas; options with `rd.luks.uuid` are copied. **[assumed]** | Test only. |

BIOS (non-UEFI) installs: GRUB only (`installation.py:validate_choice`). On BIOS the `/boot` ESP layout does not exist in the same way; encryption on BIOS was not looked at. **[not checked]**

## 5. Risks

1. **Lost passphrase = lost data.** There is no recovery key and no second keyslot. A Windows user who has never met LUKS will not expect this. Needs a clear sentence in the installer and, later, a recovery-key keyslot (`cryptsetup luksAddKey` with a generated key shown once).
2. **Keyboard layout mismatch.** The passphrase is typed in the live session with its layout; the initramfs uses `sd-vconsole` with the layout the installer configured. If they differ (non-ASCII or QWERTZ/QWERTY), the user is locked out at first boot. Mitigation: ask for the passphrase twice (Calamares does) and, in the dialog, tell the user to use only ASCII letters and digits; test with `de` layout.
3. **argon2id memory.** cryptsetup chooses the unlock memory when formatting, up to 1 GiB or about half of RAM on the installing machine. On the 3 GB minimum we require (`prepare-profile.py:353`) the initramfs unlock can run out of memory if the volume was formatted on a bigger machine. Rare; document `cryptsetup luksConvertKey --pbkdf-memory 262144`. **[assumed]**
4. **Plain ESP leaks.** Kernel, initramfs, and for systemd-boot/Limine also copied restore-point initramfs files, live unencrypted on the ESP. They include `crypttab`, hostnames and configs but never the key (no keyfile is used). Acceptable, but "encrypted" must not be sold as "evil maid safe". Secure Boot is not in place.
5. **Hibernation unavailable** (no swap partition). Swap file on btrfs inside LUKS would work later but is not offered.
6. **Alongside with BitLocker Windows.** Existing text warns that an encrypted Windows partition cannot be shrunk. The new box does not change that.
7. **Rollback and snapshot boot from live medium do not work with LUKS** (section 6). A user with an encrypted system loses the "recovery from the stick" feature unless it is extended.
8. **Passphrase handling in Calamares**: it is stored obscured in globalstorage (`ChoicePage.cpp:708`) and passed to cryptsetup on stdin by kpmcore. Not reviewed beyond that.

## 6. What the snapshot and recovery tools assume

| Component | What it does with LUKS | Evidence |
|---|---|---|
| `recovery.py` scan | `block_devices()` takes only `fstype == btrfs`. A locked volume has `fstype crypto_LUKS` and is skipped silently, so the user sees "no restore points" with no hint. An unlocked one appears as a `crypt` child with fstype btrfs and **would** be scanned. | `parse_block_devices` **[code]** |
| `recovery.py` boot (kexec) | `command_line()` returns `root=UUID=<btrfs uuid> rootflags=subvol=<sub> ro quiet splash`. For LUKS it also needs `rd.luks.uuid=<UUID of the crypto_LUKS parent>` (the initramfs has `sd-encrypt` and will ask for the passphrase again on the console after kexec). The live mapping is not carried across kexec. | `recovery.py:277` **[code]** |
| `recovery.py` rollback/undo | Refuses LUKS (`check_device`, line 446). Reasonable until tested; the btrfs top-level mount works fine after unlock, so only the refusal needs lifting. | **[code]** |
| `sdboot_snapshots.py` | Carries `rd.luks.uuid` from the running entry (section 4). | **[code]** |
| `snapshots.py` restore (installed system) | Compares `etc/crypttab` and the mkinitcpio configs between the point and now, so a point from before/after enabling a keyfile is refused. Requires standard `/@` layout, independent of LUKS. | line 229 **[code]** |
| `windoesnotmigrate` | Shows "unlock encrypted drive" for foreign Linux LUKS, has no concept of our own installs. | **[code]** |
| `windoesnotbootreuse` | Refuses encrypted targets. | **[code]** |

What is needed to support LUKS in `recovery.py` (not implemented; the change is larger than a safe tiny fix):

1. Before `scan()`: list `crypto_LUKS` partitions (`lsblk -J -p -o PATH,FSTYPE,UUID,TYPE`), ask for the passphrase in the menu (a `kdialog`/terminal prompt, never on the command line), run `cryptsetup open --type luks <dev> wdn-<uuid>` with the passphrase on stdin, close afterwards or before kexec.
2. In `parse_block_devices`/`find_snapshots` remember the parent LUKS UUID (`lsblk -s`) for a btrfs filesystem living on a `crypt` device, and put `rd.luks.uuid=<it>` into `command_line()`; validate it with the same regex used for the UUID.
3. Close all `wdn-*` mappings before `systemctl kexec`, otherwise the kexec'd kernel may find stale state.
4. Lift the `check_device` refusal for rollback only after the above is tested; test `undo` as well.
5. Unit tests in `tests/test-recovery-snapshots.py` using the existing `lsblk` JSON fixtures: a locked volume yields a "locked" entry, an unlocked one yields the `rd.luks.uuid` in the command line.

## 7. Recommended policy

1. Keep LUKS2 and the unencrypted-ESP layout for all four bootloaders. Do not encrypt /boot and do not add a keyfile (one prompt, no secret on the ESP).
2. Make the encrypt option visible and explained in our own page (`windoesnotboot`) as "Encrypt the disk (recommended on laptops)", default off for the first release, later default on for Erase disk on laptops only after the test plan passed on every bootloader. Always show: "If you forget this passphrase your data cannot be recovered."
3. Offer encryption only for btrfs and ext4 in the simple flows (what we will test); keep xfs/f2fs available in Manual.
4. Advise ASCII-only passphrases, test with German keymap, generate a recovery key slot in a later step.
5. Disable or clearly mark features that do not support LUKS yet: boot reuse (already), permanent rollback (already), "snapshot start from live medium" (skip with a visible message "this disk is encrypted and locked" instead of silently listing nothing; that is the smallest useful UI fix).
6. Add a regression check in `tools/check-profile.py` once the first test passes: the generated `initcpiocfg.conf` has `useSystemdHook: true` and `partition.conf` has `luksGeneration: luks2` and no `bootloaderOverrides`.

## 8. Test plan (KVM host, about half a day)

Prerequisites: the built ISO, `qemu-system-x86_64` with OVMF, 4 GB RAM, 40 GB disk, `swtpm` not needed. Use one fresh qcow2 per run and save a copy before each so a failed run is cheap.

```sh
qemu-img create -f qcow2 enc-grub.qcow2 40G
cp /usr/share/edk2/x64/OVMF_VARS.4m.fd enc-grub.vars.fd
qemu-system-x86_64 -enable-kvm -m 4096 -smp 2 -machine q35 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file=enc-grub.vars.fd \
  -drive file=enc-grub.qcow2,if=virtio -cdrom windoesnot.iso -boot d \
  -device virtio-vga -display gtk
```

Run the matrix: bootloader (grub, systemd-boot, limine, refind) x filesystem (btrfs first, ext4 for one bootloader). Per run:

1. In the installer choose "Erase disk", tick **Encrypt system**, enter passphrase `Test1234-Pass` (ASCII), then repeat once with the German keyboard layout selected and a passphrase containing `y`/`z` to check risk 2. Record: is the checkbox visible, is the text understandable, does an empty or mismatched passphrase block "Next".
2. After install, before reboot, in a terminal of the live session (the target is still mounted under `/tmp/calamares-root-*`): `grep HOOKS /tmp/calamares-root-*/etc/mkinitcpio.conf` must contain `sd-encrypt` before `filesystems`; `cat .../etc/crypttab`; `ls .../boot` must show no `crypto_keyfile.bin` and `ls .../crypto_keyfile.bin` must not exist; the cmdline in `.../etc/kernel/cmdline`, `.../boot/refind_linux.conf`, `.../etc/default/limine` or `.../etc/default/grub` must contain `rd.luks.uuid=`.
3. `cryptsetup luksDump /dev/vda2` (adjust): record version (expect 2), keyslot PBKDF (expect `argon2id`), memory, iterations.
4. Reboot. Expect: a passphrase prompt (with the plymouth splash if it works), then normal login. Record the time to unlock and whether the keyboard layout is right. Wrong passphrase must retry, not hang.
5. Installed system: `lsblk -f` (crypt device with btrfs), `systemctl status systemd-cryptsetup@*`, `snapper -c root create -d t1`, install a package with pacman (snap-pac pre/post), check the bootloader entries for the snapshots (GRUB submenu "WinDoesNot restore points", `/boot/loader/entries/windoesnot-restore-*.conf`, `limine.conf`, `refind.conf`).
6. Boot a restore point from the boot menu: expect another passphrase prompt, then a working desktop with the RAM overlay (`cat /run/windoesnot-snapshot-boot` prints `overlay`). This is the item most likely to fail on GRUB (section 4).
7. Boot the ISO again, open a terminal, run `sudo /usr/lib/windoesnot/recovery.py list` (or the repo path). Expected today: empty list. Then `sudo cryptsetup open /dev/vda2 wdn-test`, run `list` again: restore points should appear; run `boot` and confirm it fails to find the root (no `rd.luks.uuid`). This proves section 6 and produces the baseline for the fix.
8. Negative tests: pull `-drive` boot disk of a different VM and boot with a wrong passphrase three times; shrink RAM to 3 GB (`-m 3072`) after installing with 8 GB (risk 3); reboot with `-m 2048`.
9. Alongside install next to a Windows VM disk: encrypt box appears, only the new partition is encrypted, the Windows entry still boots (GRUB).
10. Record every result in `docs/HARDWARE.md` style rows (or in an issue), including screenshots of the passphrase prompt.

Exit criteria for "default on": steps 1-6 pass for all four bootloaders on btrfs, step 7 either fixed or the message from section 7.5 shipped, and the German-layout run unlocked correctly.

## 9. What was not checked

kpmcore's actual `cryptsetup luksFormat` arguments (not in the tree), the real UI, `grub-mkconfig` output on a LUKS root, grub-btrfs behaviour with an ESP-backed `/boot`, limine/refind snapshot packages, BIOS installs, and anything about Secure Boot or TPM unlocking. All of these are covered or flagged in the test plan.
