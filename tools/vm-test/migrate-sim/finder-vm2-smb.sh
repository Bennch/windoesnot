#!/bin/bash
set -u
L=/mnt/a/vm2/log
exec > >(tee "$L/smb-run.log") 2>&1
set -x
cat /root/vm2-pacman.log > "$L/pacman.log"
cat /root/vm2-pacman.status > "$L/pacman.status"
mkdir -p /mnt/a/vm2/smb-share /mnt/a/vm2/smb-empty /run/samba-vm2
P=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["package"])' "$L/plan.json")
cp -a "$P" /mnt/a/vm2/smb-share/
chmod 755 /mnt/a /mnt/a/vm2 /mnt/a/vm2/smb-share /mnt/a/vm2/smb-empty
useradd -M -s /usr/bin/nologin smbtest
printf 'vm2-test-password\nvm2-test-password\n' | smbpasswd -s -a smbtest
cat > /run/samba-vm2/smb.conf <<'CONF'
[global]
  server role = standalone server
  security = user
  map to guest = Bad User
  guest account = nobody
  interfaces = 127.0.0.1
  bind interfaces only = yes
  pid directory = /run/samba-vm2
  log file = /run/samba-vm2/log.%m
  passdb backend = tdbsam
[umzug]
  path = /mnt/a/vm2/smb-share
  read only = yes
  guest ok = yes
[secure]
  path = /mnt/a/vm2/smb-share
  read only = yes
  guest ok = no
  valid users = smbtest
[empty]
  path = /mnt/a/vm2/smb-empty
  read only = yes
  guest ok = yes
CONF
smbd -D -s /run/samba-vm2/smb.conf
python3 /root/mirror.py smb smb://127.0.0.1/umzug > "$L/smb-guest.json" 2> "$L/smb-guest.err"; echo $? > "$L/smb-guest.status"
printf 'vm2-test-password\n' | python3 /root/mirror.py smb smb://127.0.0.1/secure --user smbtest --password-stdin > "$L/smb-user.json" 2> "$L/smb-user.err"; echo $? > "$L/smb-user.status"
printf 'wrong-password\n' | python3 /root/mirror.py smb smb://127.0.0.1/secure --user smbtest --password-stdin > "$L/smb-wrong.json" 2> "$L/smb-wrong.err"; echo $? > "$L/smb-wrong.status"
python3 /root/mirror.py smb smb://127.0.0.1/empty > "$L/smb-empty.json" 2> "$L/smb-empty.err"; echo $? > "$L/smb-empty.status"
mount > "$L/smb-mounts.log"
if python3 - "$L/smb-guest.json" "$L/smb-plan.json" <<'PY'
import json,sys,subprocess
x=json.load(open(sys.argv[1]));assert x
subprocess.run(['python3','/root/mirror.py','scan',x[0]['device']],stdout=open(sys.argv[2],'w'),check=True)
p=json.load(open(sys.argv[2]));next(x for x in p['locations'] if x['id']=='firefox')['selected']=False
json.dump(p,open(sys.argv[2],'w'))
PY
then
 D=/mnt/a/vm2/smb-target; mkdir -p "$D/home/neu"; chown 2000:2000 "$D/home/neu"
 (time printf '\n' | python3 /root/mirror.py copy "$L/smb-plan.json" "$D/home/neu" --target-root "$D" --progress-json --secret-stdin) > "$L/smb-copy.log" 2>&1
 stat -c '%n %u:%g' "$D"/home/neu/{.config,.local,.local/share,.var,.var/app} > "$L/smb-owners.log" 2>&1
 find "$D/home/neu/.mozilla" -print > "$L/smb-firefox.log" 2>&1
fi
dmesg | tail -150 > "$L/smb-dmesg.log"
cp -a /run/samba-vm2/log.* "$L/" 2>/dev/null || true
touch "$L/smb.done"
