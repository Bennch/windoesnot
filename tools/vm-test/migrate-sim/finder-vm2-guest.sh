#!/bin/bash
set -u
mkdir -p /mnt/a /mnt/b /mnt/source
mount /dev/vda /mnt/a
mount -o ro,subvol=@ /dev/vdb2 /mnt/source
mount -o ro,subvol=@home /dev/vdb2 /mnt/source/home
mount -o ro,loop /mnt/source/var/lib/migrate-sim/daten.img /mnt/source/home/benni/Daten
mkdir -p /mnt/a/vm2/log /mnt/b
L=/mnt/a/vm2/log
exec > >(tee "$L/run.log") 2>&1
set -x
blockdev --getro /dev/vdb
python3 /root/finder.py scan --root /mnt/source --user benni --output "$L/scan.json"
python3 /root/finder-reference.py "$L/scan.json" /mnt/a/vm2/reference
mkdir -p /mnt/a/vm2/direct/home/benni
chown 1000:1000 /mnt/a/vm2/direct/home/benni
(time python3 /root/finder.py copy "$L/scan.json" /mnt/a/vm2/direct/home/benni --target-root /mnt/a/vm2/direct) > "$L/direct.log" 2>&1
python3 /root/verify.py /mnt/a/vm2/reference /mnt/a/vm2/direct > "$L/verify-direct.log" 2>&1
stat -c '%n %i %h %u:%g' /mnt/source/home/benni/hardlink-{original,second} /mnt/a/vm2/direct/home/benni/hardlink-{original,second} > "$L/hardlinks.log"
mount /dev/vdc /mnt/b
mkdir -p /mnt/b/vm2
(time python3 /root/finder.py export "$L/scan.json" /mnt/b/vm2) > "$L/export.log" 2>&1
python3 /root/finder.py find /mnt/b/vm2 > "$L/find.json"
P=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[0]["path"])' "$L/find.json")
for ID in 1000 2000; do
  D=/mnt/a/vm2/import$ID
  mkdir -p "$D/home/benni"
  chown "$ID:$ID" "$D/home/benni"
  (time python3 /root/finder.py import "$P" "$D/home/benni" --target-root "$D" --uid "$ID" --gid "$ID") > "$L/import$ID.log" 2>&1
  if [ "$ID" = 1000 ]; then python3 /root/verify.py /mnt/a/vm2/reference "$D" > "$L/verify$ID.log" 2>&1; else python3 /root/verify.py /mnt/a/vm2/reference "$D" --uid-map 1000:2000 --gid-map 1000:2000 > "$L/verify$ID.log" 2>&1; fi
  stat -c '%n %u:%g' "$D"/home/benni/{.config,.local,.local/share,.mozilla,.var,.var/app} > "$L/owners$ID.log"
done
du -sh "$P" /mnt/a/vm2/direct /mnt/a/vm2/import1000 /mnt/a/vm2/import2000 > "$L/sizes.log"
umount /mnt/b
python3 /root/mirror.py partitions > "$L/partitions.json" 2> "$L/partitions.err"
mount > "$L/mounts-after-partitions.log"
P=$(python3 -c 'import json,sys; x=[v["device"] for v in json.load(open(sys.argv[1])) if v.get("device", "").startswith("package:") and "/vm2/" in v["device"]]; print(x[0])' "$L/partitions.json")
python3 /root/mirror.py scan "$P" > "$L/plan.json" 2> "$L/scan-package.err"
python3 - "$L/plan.json" "$L/selected.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); loc=next(x for x in p['locations'] if x['id']=='firefox');loc['selected']=False
json.dump(p,open(sys.argv[2],'w'))
PY
D=/mnt/a/vm2/installer
mkdir -p "$D/home/neu"
chown 2000:2000 "$D/home/neu"
(time printf '\n' | python3 /root/mirror.py copy "$L/selected.json" "$D/home/neu" --target-root "$D" --progress-json --secret-stdin) > "$L/installer.log" 2>&1
stat -c '%n %u:%g' "$D"/home/neu/{.config,.local,.local/share,.var,.var/app} > "$L/installer-owners.log" 2>&1
find "$D/home/neu/.mozilla" -print > "$L/installer-firefox.log" 2>&1
# Tamper a private copy, preserving the discovered read-only mount.
mkdir -p /mnt/a/vm2/tamper
cp -a "${P#package:}" /mnt/a/vm2/tamper/package
python3 - <<'PY'
p='/mnt/a/vm2/tamper/package/data/firefox.tar'
with open(p,'r+b') as f: b=f.read(1); f.seek(0); f.write(bytes([b[0]^1]))
PY
python3 - "$L/plan.json" "$L/tamper-plan.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]));p['package']='/mnt/a/vm2/tamper/package';json.dump(p,open(sys.argv[2],'w'))
PY
D=/mnt/a/vm2/tamper-target
mkdir -p "$D/home/neu"; chown 1000:1000 "$D/home/neu"
printf '\n' | python3 /root/mirror.py copy "$L/tamper-plan.json" "$D/home/neu" --target-root "$D" --progress-json --secret-stdin > "$L/tamper.log" 2>&1
printf '%s\n' "$?" > "$L/tamper.status"
find "$D" -mindepth 1 -printf '%P\n' > "$L/tamper-tree.log"
touch "$L/phase1.done"
