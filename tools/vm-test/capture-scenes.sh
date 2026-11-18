#!/bin/bash
# Compatibility entry point: capture scenes through the non-destructive driver.
set -euo pipefail
if [ "$#" -ne 3 ]; then echo "usage: $0 VM USER OUTDIR" >&2; exit 2; fi
cd "$(dirname "$0")/../.."
exec python3 tools/capture-screenshots.py --vm-name "$1" --guest-user "$2" --output "$3" \
    --scene settings-background --scene start-menu --scene file-manager \
    --scene task-manager --scene store --scene desktop
