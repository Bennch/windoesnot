# WinDoesNotMac installer

Private downstream source copy of
https://github.com/asahi-alarm/asahi-alarm-installer at
`3cfef52bc372a7b84b59823027c75327e129d6ec` (MIT; LICENSE retained).
This is a source fork within the private Mac repository, not a public GitHub fork.
Upstream GitHub workflows are intentionally excluded.

## Current changes and limits

- Imported Python/shell sources have trailing whitespace normalized.
- Default installer name and documentation link identify WinDoesNotMac.
- Production, development and local bootstrap entry points stop before downloading
  or installing anything. We have no tested WinDoesNotMac image or release server
  yet; silently installing ALARM under our name would be incorrect.
- Apple device checks, partition logic, firmware extraction, recovery steps and
  boot policy logic remain upstream code. Do not replace technical Asahi names.
- No macOS build, partition operation, recovery transition or installation has
  been tested. This directory is not a finished installer.

## Intended installation flow

1. Start our bootstrap from the installed macOS. A future graphical macOS frontend
   can present choices and actual backend progress; the current backend is CLI.
2. Asahi prepares partitions, downloads our image and sets up Apple's boot chain.
3. Follow the shutdown and power-button instructions to enter the installation's
   recovery environment and authorize its boot policy. This physical step cannot
   be replaced by a Calamares window in Linux.
4. Boot the installed Linux image with our branding already present.
5. Launch our Calamares first-boot setup for user, language and keyboard. Do not
   reuse the x86 ISO partition/bootloader sequence on the installed Mac system.

Calamares first-boot configuration is a separate downstream component:
https://github.com/asahi-alarm/asahi-calamares-configs . It is not integrated yet.
The precise reason this host never displayed Calamares has not been established;
it must not be described as having run invisibly.

## Build prerequisites

The upstream build expects macOS tools and two submodule checkouts. Since this
source copy lives inside another repository, populate the following directories
explicitly at the recorded revisions before building:

| Directory | Upstream | Revision |
| --- | --- | --- |
| m1n1 | https://github.com/AsahiLinux/m1n1 | 06a4601a351ebfd1abb6abba9a44c34e40d94776 |
| artwork | https://github.com/AsahiLinux/artwork | 634948f40aea08fafde8f5fe8f4221c248a7df46 |

Supply `LOGO` as an absolute path to our logo converted to ICNS. The shared source
artwork is in `desktop/config/quickshell/default/img/brand/`. Upstream LICENSE
and dependencies' notices must remain in redistributions. Builds download more
dependencies; pinning this source does not establish a reproducible release yet.

Before enabling bootstrap scripts: publish and verify our installer archive,
version marker, distribution metadata and ARM image; define explicit HTTPS
endpoints; test clean installation on supported hardware; then validate first-boot
Calamares and recovery/resume paths. Private sources require an authenticated
artifact delivery plan rather than embedding GitHub credentials in bootstrap.
