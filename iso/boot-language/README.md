# Boot menu language

WinDoesNot boot menus use `/etc/locale.conf`, with `LC_ALL` and `LC_MESSAGES`
taking precedence over `LANG`. German selects German; other languages select the
same English fallback as the desktop. No separate boot language setting exists.

GRUB uses its upstream gettext catalogs. The three other loaders are built with
reviewed German/English text arrays. The same binary supports both languages.
Its configuration is selected before the menu is created:

- systemd-boot: `/boot/loader/windoesnot-language`
- rEFInd: `/boot/EFI/refind/windoesnot-language`
- Limine: `windoesnot_language: de` or `en` in `/boot/limine.conf`

Firmware screens and messages emitted before the loader can read its language
configuration are outside this selection. Debug identifiers, copyright notices,
protocol constants, commands and operating system names are retained. Foreign
boot menus reused by an alongside installation retain their own OS's settings;
the chained WinDoesNot GRUB follows WinDoesNot's language.

The path unit follows locale and generated-menu changes. Native package hooks
stage the matching translated loader before upstream updater hooks and refresh
only EFI copies registered by the installer. Locale changes edit configuration;
they do not write EFI variables or BIOS boot sectors. The normal installer is
responsible for the initial BIOS/UEFI installation.

Original package files are backed up under
`/var/lib/windoesnot/boot-language-originals/<sha256>/`. The native package's
bootloader input files intentionally differ from their original package
checksums; the translation package records its exact artifact hashes. Never
copy an old translated loader over a newer native one. When a native upstream
version changes, rebuild this package against the new reviewed source first.
The helper rejects a version mismatch and never downgrades a newer EFI loader.

Build only the standalone EFI loaders and Limine BIOS stages; do not rebuild or
replace systemd's userspace services. `sources.json` pins upstream archives.
`tools/prepare-boot-language.py` creates an offline source bundle and PKGBUILD.
`tools/patch-boot-language.py` applies translations to a disposable source copy.
The package includes the complete corresponding source, exact local patches,
licenses, build logs and artifact manifest. Upstream checkouts stay unchanged.

English is the original compiled text. The German catalog cannot change printf
argument order or types. ASCII transliteration works with the native Limine and
rEFInd bitmap fonts, without altering keyboard shortcuts or configuration keys.

The rEFInd build uses Arch Linux's `gnu-efi-4-compat.patch` and Fedora-derived
`fix-target-option.patch`, as shipped by Arch refind 0.14.2-3:
https://gitlab.archlinux.org/archlinux/packaging/packages/refind/-/blob/main/PKGBUILD
Their SHA-512 hashes were checked against that PKGBUILD before vendoring.
