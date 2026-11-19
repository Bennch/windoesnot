#!/usr/bin/env bash
# Start only the disposable CachyOS migration VM. First argument: iso or disk.
set -euo pipefail
cd "$(dirname "$0")/../../.."
mode=${1:-iso}
[[ "$mode" == iso || "$mode" == disk ]] || { echo 'Usage: start-cachy-vm.sh [iso|disk]' >&2; exit 2; }
out="$PWD/out/migrate-sim"
iso=/home/benni/Downloads/cachyos-desktop-linux-250828.iso
mkdir -p "$out" vm
available=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
(( available >= 8 * 1024 * 1024 )) || { echo 'Less than 8 GiB RAM available' >&2; exit 1; }
free -m
if [[ -e "$out/qmp.sock" ]] && tools/vmctl.py --vm-name migrate-cachy status >/dev/null 2>&1; then
    echo 'VM is already running' >&2; exit 1
fi
if [[ -e vm/migrate-cachy && $(readlink -f vm/migrate-cachy) != "$out" ]]; then
    echo 'vm/migrate-cachy belongs to another VM' >&2; exit 1
fi
[[ -L vm/migrate-cachy ]] || ln -s ../out/migrate-sim vm/migrate-cachy
[[ -e "$out/cachy-src.qcow2" ]] || qemu-img create -f qcow2 "$out/cachy-src.qcow2" 60G
[[ -e "$out/ovmf-vars.fd" ]] || cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$out/ovmf-vars.fd"
boot=(-boot order=c)
if [[ "$mode" == iso ]]; then
    [[ -r "$iso" ]] || { echo "Missing ISO: $iso" >&2; exit 1; }
    boot=(-drive "file=$iso,media=cdrom,readonly=on" -boot order=d)
fi
exec systemd-run --user --scope -p MemoryMax=12G -p MemorySwapMax=2G \
    qemu-system-x86_64 -name migrate-cachy -machine q35,accel=kvm -cpu host -m 4096 -smp 2 \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
    -drive "if=pflash,format=raw,file=$out/ovmf-vars.fd" \
    -drive "file=$out/cachy-src.qcow2,if=virtio,format=qcow2" "${boot[@]}" \
    -device virtio-vga -display none -device qemu-xhci -device usb-tablet \
    -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
    -device virtio-serial-pci -chardev "socket,path=$out/guest-agent.sock,server=on,wait=off,id=guest0" \
    -device virtserialport,chardev=guest0,name=org.qemu.guest_agent.0 \
    -qmp "unix:$out/qmp.sock,server=on,wait=off" -serial "file:$out/serial.log"
