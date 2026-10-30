#!/usr/bin/env bash
# Build WinDoesNot with archiso and boot it in an isolated UEFI QEMU VM.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
rootless=true; mode=both; iso=; dry=false; headless=false; fresh=false; installed=false
memory=8192; cpus=4; graphics=auto; vm_name=debug; build_id=
usage() {
    cat <<EOF
Usage: $0 [options]
  --build-only          Build without launching QEMU
  --rootless            Build in user namespaces without sudo (default)
  --sudo-build          Use sudo for hosts without user namespaces
  --run-only ISO        Reuse an ISO; skip build/downloads
  --boot-installed      Boot the VM's installed disk with no ISO attached
  --headless            No GUI; serial log and QMP socket in vm/<name>/
  --fresh-vm            New VM directory; preserve the previous disk
  --vm-name NAME        VM directory (default: debug)
  --memory MiB          RAM (default: 8192)
  --cpus N              vCPUs (default: 4)
  --graphics gl|soft    VirGL acceleration or software rendering
  --build-id ID         Resume this exact prepared build
  --dry-run             Show actions; do not build, download or launch
  --help                Show help
Only the build subprocess uses sudo. The VM uses its own qcow2 disk.
EOF
}
while (($#)); do
    case "$1" in
        --sudo-build) rootless=false; shift;;
        --rootless) rootless=true; shift;;
        --build-only) mode=build; shift;;
        --run-only) mode=run; iso=${2:?Missing ISO path}; shift 2;;
        --boot-installed) mode=run; installed=true; shift;;
        --headless) headless=true; shift;;
        --fresh-vm) fresh=true; shift;;
        --vm-name) vm_name=${2:?Missing name}; shift 2;;
        --memory) memory=${2:?Missing memory}; shift 2;;
        --cpus) cpus=${2:?Missing CPU count}; shift 2;;
        --graphics) graphics=${2:?Missing graphics mode}; shift 2;;
        --build-id) build_id=${2:?Missing build ID}; shift 2;;
        --dry-run) dry=true; shift;;
        --help|-h) usage; exit 0;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2;;
    esac
done
[[ $memory =~ ^[0-9]+$ && $cpus =~ ^[0-9]+$ && $vm_name =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid VM arguments' >&2; exit 2; }
((memory >= 4096 && cpus >= 1 && cpus <= 64)) || { echo 'Minimum: 4096 MiB and 1 vCPU' >&2; exit 2; }
[[ $graphics == auto || $graphics == gl || $graphics == soft ]] || exit 2
[[ -z $build_id || $build_id =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
if ((EUID == 0)) && [[ $mode != build ]]; then
    echo 'Run as your regular user; only mkarchiso is elevated.' >&2; exit 2
fi
show() { printf '%q ' "$@"; printf '\n'; }
if ((EUID == 0)); then rootless=false; fi
if [[ $mode != run ]]; then
    if $dry; then show python3 "$project/tools/fetch-sources.py"; else python3 "$project/tools/fetch-sources.py"; fi
    build_id=${build_id:-$(date +%Y%m%d-%H%M%S)}
    profile="$project/build/$build_id/profile"
    work="$project/build/$build_id/work"
    output="$project/out/$build_id"
    if [[ ! -e $profile ]]; then
        if $dry; then show python3 "$project/tools/prepare-profile.py" --output "$profile"
        else python3 "$project/tools/prepare-profile.py" --output "$profile"; fi
    fi
    # Never let a partially generated profile fall through to mkarchiso. This
    # marker is written only after all WinDoesNot staging and branding steps
    # completed; without it the upstream CachyOS profile could be packaged.
    $dry || [[ -f "$profile/airootfs/etc/windoesnot-image-build" ]] || {
        echo "Incomplete WinDoesNot profile: $profile (use a new --build-id)" >&2
        exit 1
    }
    if $rootless; then
        if $dry; then
            show "$project/tools/prepare-rootless.sh" "$profile"
        else
            "$project/tools/prepare-rootless.sh" "$profile"
            "$project/tools/prepare-host-tools.sh"
            export PATH="$project/build/host-tools/usr/bin:$PATH"
        fi
    fi
    # A prepared profile may be resumed with --sudo-build after rootless
    # namespace setup failed. Reuse the same isolated GRUB tools if present.
    if [[ -d $project/build/host-tools/usr/bin ]]; then
        export PATH="$project/build/host-tools/usr/bin:$PATH"
    fi
    if ! $dry; then python3 "$project/tools/stage-build-resolver.py" "$profile"; fi
    command=(mkarchiso -v -w "$work" -o "$output" "$profile")
    if ((EUID != 0)) && ! $rootless; then
        # sudo's secure_path hides the signed, unpacked GRUB tools prepared in
        # build/host-tools. Pass only this build PATH explicitly; do not install
        # or modify host packages just to satisfy mkarchiso validation.
        command=(sudo -- env "PATH=$PATH" "${command[@]}")
    fi
    if $dry; then show "${command[@]}"; else
        mkdir -p "$output"
        "${command[@]}" 2>&1 | tee "$output/build.log"
        mapfile -d '' -t images < <(find "$output" -maxdepth 1 -name '*.iso' -type f -print0)
        ((${#images[@]} == 1)) || { echo 'Expected exactly one built ISO' >&2; exit 1; }
        iso=${images[0]}
        # The checksum remains usable when the ISO is copied to another machine.
        (cd -- "$output" && sha256sum -- "$(basename -- "$iso")" > "$(basename -- "$iso").sha256")
    fi
    iso=${iso:-"$output/windoesnot-<date>-x86_64.iso"}
fi
[[ $mode != build ]] || exit 0
if ! $installed; then
    if ! $dry; then iso=$(realpath -e -- "${iso:?Use --run-only ISO or build first}"); fi
    [[ -n $iso ]] || { echo 'Missing ISO' >&2; exit 2; }
fi
if $fresh; then vm_name="$vm_name-$(date +%Y%m%d-%H%M%S)"; fi
vm="$project/vm/$vm_name"
disk="$vm/disk.qcow2"
firmware=/usr/share/edk2/x64/OVMF_CODE.4m.fd
template=/usr/share/edk2/x64/OVMF_VARS.4m.fd
[[ -f $firmware && -f $template ]] || { echo 'edk2-ovmf firmware is required' >&2; exit 1; }
if $installed && ! $dry && [[ ! -f $disk ]]; then echo 'No installed VM disk exists' >&2; exit 1; fi
if ! $dry; then
    mkdir -p "$vm"
    [[ -e $disk ]] || qemu-img create -f qcow2 "$disk" 64G
    [[ -e $vm/OVMF_VARS.fd ]] || cp "$template" "$vm/OVMF_VARS.fd"
fi
# Never open the same writable VM disk from two instances.
if ! $dry; then exec 9>"$vm/running.lock"; flock -n 9 || { echo 'VM already running' >&2; exit 1; }; fi
if [[ -r /dev/kvm && -w /dev/kvm ]]; then accel=(-accel kvm -cpu host)
else accel=(-accel tcg,thread=multi -cpu max); echo 'KVM unavailable; using slower TCG.'; fi
if [[ $graphics == auto ]]; then
    if $headless; then graphics=soft; else graphics=gl; fi
fi
if [[ $graphics == gl ]]; then
    display=(-device virtio-vga-gl)
    if $headless; then display+=(-display egl-headless); else display+=(-display gtk,gl=on); fi
else
    display=(-device virtio-vga)
    if $headless; then display+=(-display none); else display+=(-display gtk,gl=off); fi
fi
command=(qemu-system-x86_64 -name "WinDoesNot-$vm_name" -machine q35 "${accel[@]}" -m "$memory" -smp "$cpus"
    -drive "if=pflash,format=raw,readonly=on,file=$firmware"
    -drive "if=pflash,format=raw,file=$vm/OVMF_VARS.fd"
    -drive "file=$disk,if=virtio,format=qcow2"
    "${display[@]}" -device qemu-xhci -device usb-tablet
    -netdev user,id=net0 -device virtio-net-pci,netdev=net0
    -device virtio-rng-pci
    -device virtio-serial-pci -chardev "socket,path=$vm/guest-agent.sock,server=on,wait=off,id=guest0"
    -device virtserialport,chardev=guest0,name=org.qemu.guest_agent.0
    -serial "file:$vm/serial.log"
    -qmp "unix:$vm/qmp.sock,server=on,wait=off"
    -pidfile "$vm/qemu.pid" -monitor none)
if ! $installed; then command+=(-drive "file=$iso,media=cdrom,readonly=on" -boot order=d,menu=on); else command+=(-boot order=c,menu=on); fi
show "${command[@]}"
$dry && exit 0
printf 'VM logs: %s\n' "$vm"
"${command[@]}" 2>&1 | tee "$vm/qemu.log"
