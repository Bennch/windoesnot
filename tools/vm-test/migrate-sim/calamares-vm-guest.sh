#!/bin/bash
set -euo pipefail
mkdir -p /root/checklogs /mnt/pkg/Transfers
L=/root/checklogs
if mountpoint -q /mnt/pkg; then mv /mnt/pkg/Umzug-* /mnt/pkg/Transfers/ 2>/dev/null || true; fi
find /mnt/pkg/Transfers -name windoesnot-umzug.json -print > "$L/package-path.txt"
mountpoint -q /mnt/pkg && umount /mnt/pkg
for n in 1 2; do
  TIMEFORMAT="%3R seconds"; time python3 /root/mirror.py partitions > "$L/partitions$n.json" 2> "$L/partitions$n.err"
  findmnt -rn -o TARGET,SOURCE,OPTIONS | grep '^/run/windoesnot/packages' > "$L/mounts$n.txt" || true
  find /run/windoesnot/packages -maxdepth 2 -type d -print | sort > "$L/dirs$n.txt" || true
done
python3 - "$L" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); a=json.loads((p/'partitions1.json').read_text()); b=json.loads((p/'partitions2.json').read_text())
for n,x in enumerate((a,b),1):
 hits=[v['device'] for v in x if v.get('device','').startswith('package:')]
 print(n,hits,'unique',len(hits)==len(set(hits)))
print('same',a==b)
(p/'compare.txt').write_text('same=%s\n'% (a==b))
hits=[v['device'] for v in b if '/Transfers/Umzug-' in v.get('device','')]
if not hits: sys.exit('nested package missing')
(p/'selected-device.txt').write_text(hits[0])
PY
P=$(cat "$L/selected-device.txt")
python3 /root/mirror.py scan "$P" > "$L/plan.json"
mkdir -p /tmp/calamares-target/home/neu
chown 2000:2000 /tmp/calamares-target/home/neu
time bash -c "printf '\\n' | python3 /root/mirror.py copy /root/checklogs/plan.json /tmp/calamares-target/home/neu --target-root /tmp/calamares-target --progress-json --secret-stdin" > "$L/copy.log" 2>&1
for p in hash-home.py Daten Daten/lost+found Daten/mounted.txt; do stat -c '%n %u:%g' "/tmp/calamares-target/home/neu/$p" || true; done > "$L/owners.txt" 2>&1
find /tmp/calamares-target/home/neu -xdev \( ! -uid 2000 -o ! -gid 2000 \) -printf '%P %u:%g\n' > "$L/foreign-owners.txt"
touch "$L/done"
