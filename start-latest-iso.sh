#!/usr/bin/env bash
# Start the NEWEST WinDoesNot ISO in a fresh QEMU VM (UEFI, KVM) with one command.
#
#   ./start-latest-iso.sh                 newest ISO, fresh VM, QEMU's own GTK window
#   ./start-latest-iso.sh --spice         SPICE viewer instead (shared clipboard)
#   ./start-latest-iso.sh --keep          reuse the previous VM disk (e.g. after an installation)
#   ./start-latest-iso.sh --list          show the ISOs found, newest first
#   ./start-latest-iso.sh --iso FILE      use this ISO instead of the newest one
#   ./start-latest-iso.sh --memory 6144 --cpus 2 --graphics soft    (passed on to build-and-run.sh)
#
# "Newest" = most recently modified windoesnot-*.iso under out/ (builds and release-* folders).
# Old VM directories are kept (AGENTS.md: keep only the last 3 under vm/; this script prunes
# the ones it created itself, see KEEP below).
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$project"

viewer=--gtk-display; fresh=--fresh-vm; iso=; list=false; extra=(); KEEP=3
while (($#)); do
    case "$1" in
        --spice) viewer=; shift;;
        --gtk) viewer=--gtk-display; shift;;
        --keep) fresh=; shift;;
        --list) list=true; shift;;
        --iso) iso=${2:?Missing ISO path}; shift 2;;
        -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0;;
        *) extra+=("$1"); shift;;
    esac
done

# Newest first. Archived "archive-before-*" copies are skipped.
mapfile -t isos < <(find out -maxdepth 3 -type f -name 'windoesnot-*.iso' -not -path '*/archive-*' \
                       -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-)
((${#isos[@]})) || { echo "No windoesnot-*.iso found under $project/out" >&2; exit 1; }

if $list; then
    for f in "${isos[@]}"; do printf '%s  %s  %s\n' "$(date -r "$f" '+%F %H:%M')" "$(du -h "$f" | cut -f1)" "$f"; done
    exit 0
fi

iso=${iso:-${isos[0]}}
[[ -f $iso ]] || { echo "ISO not found: $iso" >&2; exit 1; }
if [[ -f $iso.sha256 ]]; then
    (cd "$(dirname "$iso")" && sha256sum --quiet -c "$(basename "$iso").sha256") \
        || { echo "Checksum mismatch for $iso" >&2; exit 1; }
fi
echo "ISO:  $iso  ($(date -r "$iso" '+%F %H:%M'), $(du -h "$iso" | cut -f1))"

name=latest
if [[ -n $fresh ]]; then
    # Remove the oldest VMs this script created before starting a new one (never other VM directories).
    mapfile -t old < <(find vm -maxdepth 1 -type d -name "${name}-*" -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2- | tail -n +"$KEEP")
    for d in "${old[@]}"; do [[ -n $d ]] && rm -rf -- "$d"; done
fi
exec ./build-and-run.sh --run-only "$iso" $fresh --vm-name "$name" $viewer "${extra[@]}"
