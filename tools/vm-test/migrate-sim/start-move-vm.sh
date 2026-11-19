#!/usr/bin/env bash
# Start a disposable live VM with a writable target and read-only source.
set -euo pipefail
cd "$(dirname "$0")/../../.."
out="$PWD/out/migrate-sim"
live="$out/live"
source_disk="$out/cachy-src.qcow2"
iso="$PWD/out/20261119-164558-en/windoesnot-2026.11.19-en-x86_64.iso"
[[ -r $source_disk && -r $iso ]] || { echo 'Source disk or live ISO missing' >&2; exit 1; }
available=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
(( available >= 8 * 1024 * 1024 )) || { echo 'Less than 8 GiB RAM available' >&2; exit 1; }
free -m
mkdir -p "$live" vm
if [[ -e vm/migrate-live && $(readlink -f vm/migrate-live) != "$live" ]]; then echo 'VM name already in use' >&2; exit 1; fi
[[ -L vm/migrate-live ]] || ln -s ../out/migrate-sim/live vm/migrate-live
if [[ -e "$live/qmp.sock" ]] && tools/vmctl.py --vm-name migrate-live status >/dev/null 2>&1; then echo 'VM already running' >&2; exit 1; fi
[[ -e "$live/target.qcow2" ]] || qemu-img create -f qcow2 "$live/target.qcow2" 40G
[[ -e "$live/OVMF_VARS.fd" ]] || cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$live/OVMF_VARS.fd"
exec systemd-run --user --scope -p MemoryMax=12G -p MemorySwapMax=2G \
 qemu-system-x86_64 -name migrate-live -machine q35,accel=kvm -cpu host -m 4096 -smp 2 \
 -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
 -drive "if=pflash,format=raw,file=$live/OVMF_VARS.fd" \
 -drive "file=$live/target.qcow2,if=virtio,format=qcow2" \
 -drive "file=$source_disk,if=virtio,format=qcow2,readonly=on" \
 -drive "file=$iso,media=cdrom,readonly=on" -boot order=d \
 -device virtio-vga -display none -device qemu-xhci -device usb-tablet \
 -device virtio-rng-pci -device virtio-serial-pci \
 -chardev "socket,path=$live/guest-agent.sock,server=on,wait=off,id=guest0" \
 -device virtserialport,chardev=guest0,name=org.qemu.guest_agent.0 \
 -qmp "unix:$live/qmp.sock,server=on,wait=off" -serial "file:$live/serial.log" -nic none
