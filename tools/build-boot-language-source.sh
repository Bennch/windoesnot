#!/usr/bin/env bash
# Freestanding bootloaders only; output stays inside the package build tree.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=$(realpath -m -- "${1:?output directory required}")
[[ ! -e $output ]] || { echo 'Use a fresh bootloader build directory.' >&2; exit 1; }
mkdir -p "$output/work" "$output/artifacts" "$output/logs"
for archive in "$project/archives/"*; do tar -xf "$archive" -C "$output/work"; done
python "$project/tools/patch-boot-language.py" systemd-boot "$output/work/systemd-262.1" > "$output/logs/systemd-patch.json"
python "$project/tools/patch-boot-language.py" refind "$output/work/refind-0.14.2" > "$output/logs/refind-patch.json"
python "$project/tools/patch-boot-language.py" limine "$output/work/limine-12.9.4" > "$output/logs/limine-patch.json"
meson setup "$output/systemd-build" "$output/work/systemd-262.1" \
    -Dmode=release -Dbuildtype=release -Dauto_features=disabled -Dbootloader=enabled -Defi=true \
    -Dman=disabled -Dhtml=disabled -Dtests=false -Dinstall-tests=false > "$output/logs/systemd-configure.log" 2>&1
ninja -j "${BUILD_JOBS:-4}" -C "$output/systemd-build" src/boot/systemd-bootx64.efi > "$output/logs/systemd-build.log" 2>&1
mkdir -p "$output/artifacts/systemd-boot" "$output/artifacts/refind" "$output/artifacts/limine"
cp "$output/systemd-build/src/boot/systemd-bootx64.efi" "$output/artifacts/systemd-boot/"
# The source patch adapts rEFInd's old API to GNU-EFI 4; reject an unknown ABI.
[[ $(pacman -Q gnu-efi | cut -d' ' -f2) == 4.* ]] || { echo 'GNU-EFI 4 is required; review the adapter before using another ABI.' >&2; exit 1; }
make -C "$output/work/refind-0.14.2" -j "${BUILD_JOBS:-4}" gnuefi > "$output/logs/refind-build.log" 2>&1
cp "$output/work/refind-0.14.2/refind/refind_x64.efi" "$output/artifacts/refind/"
(
    cd "$output/work/limine-12.9.4"
    CC_FOR_TARGET=gcc LD_FOR_TARGET=ld.bfd OBJCOPY_FOR_TARGET=objcopy OBJDUMP_FOR_TARGET=objdump \
        READELF_FOR_TARGET=readelf AR_FOR_TARGET=ar NM_FOR_TARGET=nm STRIP_FOR_TARGET=strip \
        ./configure --enable-bios --enable-uefi-x86-64 > "$output/logs/limine-configure.log" 2>&1
    make -j "${BUILD_JOBS:-4}" > "$output/logs/limine-build.log" 2>&1
)
cp "$output/work/limine-12.9.4/bin/BOOTX64.EFI" "$output/work/limine-12.9.4/bin/limine-bios.sys" \
    "$output/work/limine-12.9.4/bin/limine" "$output/artifacts/limine/"
python - "$output" "$project" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]);project=Path(sys.argv[2]);versions={'systemd-boot':'262.1','refind':'0.14.2','limine':'12.9.4'}
manifest={'schema_version':1,'loaders':{},'runtime_sha256':hashlib.sha256((project/'desktop/lib/windoesnot/boot_language.py').read_bytes()).hexdigest(),'patcher_sha256':hashlib.sha256((project/'tools/patch-boot-language.py').read_bytes()).hexdigest(),'catalogs':{name:hashlib.sha256((project/f'iso/boot-language/{name}-de.json').read_bytes()).hexdigest() for name in versions},'build_packages':subprocess.check_output(['pacman','-Q','gcc','binutils','gnu-efi','meson','nasm'],text=True).splitlines()}
for name,version in versions.items():
    manifest['loaders'][name]={'version':version,'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'artifacts'/name).iterdir())}}
(root/'artifacts/manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
PY
