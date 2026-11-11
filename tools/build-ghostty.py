#!/usr/bin/env python3
"""Build the shared Ghostty terminal when the architecture has no distro package.

Uses official release archives with pinned SHA256 checksums. Needs gtk4,
libadwaita, gtk4-layer-shell, pkgconf and gettext installed on the build host.
Default output is build/ghostty; --prefix selects a user or staging installation.
"""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.request

VERSION = "1.4.0"
ZIG_VERSION = "0.17.0"
SOURCE_SHA = "cb188ac6c3a8278d5fd7bfef15d8c017104c87f638b5560eb38024a71ae0f005"
ZIG_SHA = {
    "aarch64": "9e8d11661d4ae3bd57702a3832781e23ad151dde5798e16a5ccd503f65234ff8",
    "x86_64": "1cbe9df9f27e6b78d14ccbca43b6703a404ef79ef1c463de901d7f088d4e2026",
}
ROOT = Path(__file__).resolve().parent.parent


def archive(url, target, digest):
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        temporary = target.with_suffix(target.suffix + ".download")
        urllib.request.urlretrieve(url, temporary)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
            temporary.unlink()
            raise SystemExit("Archive checksum mismatch: " + url)
        temporary.replace(target)
    with tarfile.open(target) as bundle:
        bundle.extractall(target.parent, filter="data")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=ROOT / "build/ghostty")
    args = parser.parse_args()
    architecture = platform.machine()
    if architecture not in ZIG_SHA:
        raise SystemExit("Unsupported architecture: " + architecture)
    subprocess.run(["pkg-config", "--exists", "gtk4", "libadwaita-1", "gtk4-layer-shell-0"], check=True)
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "windoesnot-ghostty"
    cache.mkdir(parents=True, exist_ok=True)
    archive(f"https://release.files.ghostty.org/{VERSION}/ghostty-{VERSION}.tar.gz",
            cache / f"ghostty-{VERSION}.tar.gz", SOURCE_SHA)
    zig_name = f"zig-{architecture}-linux-{ZIG_VERSION}"
    archive(f"https://ziglang.org/download/{ZIG_VERSION}/{zig_name}.tar.xz",
            cache / f"{zig_name}.tar.xz", ZIG_SHA[architecture])
    subprocess.run([str(cache / zig_name / "zig"), "build", "-Doptimize=ReleaseFast", "-Dversion-string=" + VERSION,
                    "-p", str(args.prefix.resolve()), "-j" + os.environ.get("BUILD_JOBS", "4")],
                   cwd=cache / f"ghostty-{VERSION}", check=True)
    print("Ghostty installed at " + str(args.prefix.resolve()))


if __name__ == "__main__":
    main()
