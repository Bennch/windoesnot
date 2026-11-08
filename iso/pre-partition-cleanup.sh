#!/usr/bin/env bash
# Pre-partition cleanup: unmount any leftover target mounts from a previous
# failed installation. Without this, sfdisk --wipe=always fails with EBUSY
# when the user restarts the installer after a mid-install failure.
for mp in /tmp/calamares-root-*/; do
    [ -d "$mp" ] && umount -R --lazy "$mp" 2>/dev/null
done
swapoff -a 2>/dev/null
exit 0
