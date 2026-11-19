#!/usr/bin/env bash
# Run only inside the disposable WinDoesNot live VM from start-move-vm.sh.
set -euo pipefail
[[ $(systemd-detect-virt) == kvm && $EUID == 0 ]] || { echo 'Expected root in KVM' >&2; exit 1; }
[[ $(blockdev --getsize64 /dev/vda) == 42949672960 && $(blockdev --getro /dev/vdb) == 1 && $(blkid -s TYPE -o value /dev/vdb2) == btrfs ]] || { echo 'Unexpected disks' >&2; exit 1; }
if blkid -p /dev/vda >/dev/null 2>&1; then echo 'Target is not blank; refusing to format' >&2; exit 1; fi
mkfs.ext4 -F -q /dev/vda
mkdir -p /mnt/move-target
mount /dev/vda /mnt/move-target
mkdir -p /mnt/move-target/home/benni
chown 1000:1000 /mnt/move-target/home/benni
python3 /root/mirror.py scan /dev/vdb2 > /mnt/move-target/scan.json 2> /mnt/move-target/scan.err
python3 - <<'PY'
import json
p='/mnt/move-target/'
d=json.load(open(p+'scan.json'))
for u in d['users']: u['selected'] = u['name'] == 'benni'
for x in d['locations']: x['selected'] = False
d['wlan_selected'] = False
json.dump(d, open(p+'selected.json', 'w'))
PY
python3 /root/mirror.py copy /mnt/move-target/selected.json /mnt/move-target/home/benni --target-root /mnt/move-target --progress-json > /mnt/move-target/copy.log 2> /mnt/move-target/copy.err
mkdir -p /mnt/source-ro /mnt/verify-source/home/benni /mnt/move-target/compare/home
mount -t btrfs -o ro,subvol=@ /dev/vdb2 /mnt/source-ro
mount -t btrfs -o ro,subvol=@home /dev/vdb2 /mnt/source-ro/home
mount --bind /mnt/source-ro/home/benni /mnt/verify-source/home/benni
cp -al /mnt/move-target/home/benni /mnt/move-target/compare/home/benni
python3 - <<'PY'
import pathlib, shutil
h=pathlib.Path('/mnt/move-target/compare/home/benni')
a=h/'Umzug-benni/original'
for n in ('hypr','hyprdesk','quickshell','snappy-switcher','swaync','ghostty','gtk-3.0','gtk-4.0','fish'):
    if (a/'.config'/n).is_dir():
        shutil.rmtree(h/'.config'/n, ignore_errors=True)
        shutil.move(str(a/'.config'/n), str(h/'.config'/n))
if (h/'Umzug-benni').exists(): shutil.rmtree(h/'Umzug-benni')
PY
set +e
python3 /root/verify.py /mnt/verify-source /mnt/move-target/compare > /mnt/move-target/verify.log 2>&1
result=$?
set -e
printf '%s\n' "$result" > /mnt/move-target/verify.status
cat /mnt/move-target/verify.log
exit "$result"
