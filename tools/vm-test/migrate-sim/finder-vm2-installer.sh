#!/bin/bash
set -u
L=/mnt/a/vm2/log
exec > >(tee "$L/installer-run.log") 2>&1
set -x
umount /run/windoesnot/packages/vdc
mount /dev/vdc /mnt/b
mv /mnt/b/vm2/Umzug-* /mnt/b/
umount /mnt/b
python3 /root/mirror.py partitions > "$L/partitions.json" 2> "$L/partitions.err"
mount > "$L/mounts-after-partitions.log"
P=$(python3 -c 'import json,sys; x=[v["device"] for v in json.load(open(sys.argv[1])) if v.get("device", "").startswith("package:")]; print(x[-1])' "$L/partitions.json")
python3 /root/mirror.py scan "$P" > "$L/plan.json" 2> "$L/scan-package.err"
python3 - "$L/plan.json" "$L/selected.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); next(x for x in p['locations'] if x['id']=='firefox')['selected']=False
json.dump(p,open(sys.argv[2],'w'))
PY
D=/mnt/a/vm2/installer
(time printf '\n' | python3 /root/mirror.py copy "$L/selected.json" "$D/home/neu" --target-root "$D" --progress-json --secret-stdin) > "$L/installer.log" 2>&1
echo $? > "$L/installer.status"
stat -c '%n %u:%g' "$D"/home/neu/{.config,.local,.local/share,.var,.var/app} > "$L/installer-owners.log" 2>&1
find "$D/home/neu/.mozilla" -print > "$L/installer-firefox.log" 2>&1
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
printf '\n' | python3 /root/mirror.py copy "$L/tamper-plan.json" "$D/home/neu" --target-root "$D" --progress-json --secret-stdin > "$L/tamper.log" 2>&1
echo $? > "$L/tamper.status"
find "$D" -mindepth 1 -printf '%P\n' > "$L/tamper-tree.log"
touch "$L/installer.done"
