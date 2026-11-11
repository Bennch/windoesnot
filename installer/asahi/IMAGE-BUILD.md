# WinDoesNotMac image build

The output is an Asahi installer ZIP containing `root.img` (BTRFS with `@` and
`@home`) and an `esp/` tree, not an x86 ISO. macOS bootstrapping and Recovery
authorization remain necessary. All steps below run in a dedicated ARM64 Linux
build environment. Do not copy the installed Mac's root filesystem or home data.

## Implemented

- Pinned image builder: `asahi-alarm/asahi-alarm-builder`, commit
  `58cc158c7fda3ef6aeae36606f84a63b4b0867e7`, MIT, exported from git objects.
  Upstream publish workflows are removed. A downstream script generates only
  our BTRFS desktop image with its own filesystem label and UUIDs.
- Shared WinDoesNot logo, GRUB theme and Plymouth theme. `/etc/os-release`
  overrides the base package's identity while `/usr/lib/os-release` and the
  working Asahi package repositories remain unchanged.
- Packaged desktop installed before first boot; Firefox and Ghostty are desktop
  dependencies. No Kitty dependency is introduced.
- Calamares OEM setup: welcome/language, locale, keyboard, user, summary, finish.
  No partitioning, filesystem extraction, bootloader installation or package
  download phase. Built-in Calamares translations supply its standard pages.
- Own first-boot service and completion marker. SDDM depends on successful
  completion, so failed setup cannot silently lead to an unconfigured login.
  The actual new user receives Apple defaults through `windoesnot-initialize`.
- No seed `alarm` user, unlocked root account, machine ID or host SSH keys in the
  final image. The existing development Mac's accounts are not changed.
- Retina scaling and a software-rendering fallback in the setup compositor.

## Inputs

Prepare the normal desktop source bundle with `tools/prepare-packages.py`. The
split PKGBUILD supports ARM64 and builds native plugins/components using generic
ARMv8 flags. Use two jobs on the development Mac if building there:

```sh
python tools/prepare-packages.py --output build/asahi-native-packages
cd build/asahi-native-packages
BUILD_JOBS=2 nice -n 10 makepkg --noconfirm --nocheck
```

Build the native packages in an environment with their build dependencies
installed. Application packages required in the package input directory:

`windoesnot-desktop`, `windoesnot-tools`, `windoesnot-plugins`,
`windoesnot-components`, `windoesnot-device-manager`, `windoesnot-bluetooth`,
`windoesnot-network`, `ghostty`, `localsend`.

Only `aarch64` and architecture-independent packages are accepted. Their remaining
dependencies are resolved by pacman inside the image; an unavailable dependency
fails the build. The four core packages must share one version/release.

Supply a clean Arch Linux ARM aarch64 seed archive and its independently verified
SHA-256. The generated builder does not fetch a mutable `latest` seed itself.
Build tools include arch-install-scripts, btrfs-progs, rsync, zip, grub and Python.
The build environment must have the Asahi repository/keyring configured, as in
the pinned upstream builder environment.

```sh
git clone https://github.com/asahi-alarm/asahi-alarm-builder.git build/asahi-upstream
git -C build/asahi-upstream checkout 58cc158c7fda3ef6aeae36606f84a63b4b0867e7
python tools/prepare-asahi-image.py --builder-source build/asahi-upstream \
  --output build/asahi-image --packages-dir /path/to/arm-packages \
  --base-archive /path/to/verified-seed.tar.gz --base-sha256 VERIFIED_SHA256
```

Read `build/asahi-image/build-inputs.json`, then run `build-image.sh` there as root
in the dedicated builder. It checks every recorded input before running.
Missing local packages or an unverified seed stop the build. Repository packages
are still rolling: input hashes plus the installed package inventory document a
build, but this is not yet bit-for-bit reproducibility from a package snapshot.

## Validation still required

No complete WinDoesNotMac image has been built or booted yet. As of this session,
the four core desktop packages were built successfully on aarch64, without
installing them on the host. The five application packages listed above remain
to be provided. The seed download's redirect points to HTTP; direct HTTPS on
`os.archlinuxarm.org` returned a certificate hostname error during this session.
An independently verified seed is therefore still needed.

Next: build the remaining application packages and resolve dependency closure;
build the isolated image; boot on spare supported hardware; validate Calamares
in Cage (including missing-GPU fallback), language/Apple layout adoption, SDDM,
restart and failure/retry behavior. Validate U-Boot/GRUB compatibility and root
filesystem growth. Only then derive installer metadata from the actual ZIP sizes
and supported firmware and enable the private bootstrap download endpoints.

The existing host has no display manager; the first-boot service is staged only
in the image and is not enabled on this development installation.
