#!/usr/bin/env bash
# Write a WinDoesNot ISO to the one removable USB disk. Run as root:
#   sudo tools/write-usb.sh out/<build>/windoesnot-...iso [/dev/sdX]
# Refuses unless the target is a removable USB disk with no mounted partitions
# and (without an explicit device) exactly one such disk is present.
set -euo pipefail
iso=${1:?usage: write-usb.sh ISO [DEVICE]}
[[ $EUID -eq 0 ]] || { echo 'Run as root (sudo).' >&2; exit 1; }
[[ -f $iso ]] || { echo "No such ISO: $iso" >&2; exit 1; }
if [[ -f $iso.sha256 ]]; then
    (cd "$(dirname "$iso")" && sha256sum -c "$(basename "$iso").sha256") || { echo 'Checksum mismatch; aborting.' >&2; exit 1; }
fi
candidates=$(lsblk -dnpo NAME,TYPE,RM,TRAN | awk '$2=="disk" && $3==1 && $4=="usb" {print $1}')
if [[ -n ${2:-} ]]; then
    dev=$2
    grep -qx "$dev" <<<"$candidates" || { echo "$dev is not a removable USB disk." >&2; exit 1; }
else
    [[ $(wc -l <<<"$candidates") -eq 1 && -n $candidates ]] || { echo "Need exactly one removable USB disk, found: ${candidates:-none}" >&2; exit 1; }
    dev=$candidates
fi
size=$(blockdev --getsize64 "$dev"); iso_size=$(stat -c %s "$iso")
(( size > iso_size )) || { echo "$dev (${size} bytes) is smaller than the ISO." >&2; exit 1; }
if lsblk -rno MOUNTPOINTS "$dev" | grep -q .; then
    echo "Unmounting partitions of $dev ..."
    for part in $(lsblk -rnpo NAME "$dev" | tail -n +2); do umount "$part" 2>/dev/null || true; done
    lsblk -rno MOUNTPOINTS "$dev" | grep -q . && { echo "$dev still mounted; aborting." >&2; exit 1; }
fi
echo "Target: $dev  $(lsblk -dno SIZE,MODEL "$dev")"
echo "ISO:    $iso  $(numfmt --to=iec "$iso_size")"
echo 'Everything on the target will be overwritten. Starting in 5 seconds (Ctrl+C to abort).'
sleep 5
dd if="$iso" of="$dev" bs=4M status=progress oflag=sync conv=fsync
sync
echo 'Verifying ...'
cmp -n "$iso_size" "$iso" "$dev" && echo "OK: $dev matches the ISO."
