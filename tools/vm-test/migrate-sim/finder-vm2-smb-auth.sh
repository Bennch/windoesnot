#!/bin/bash
L=/mnt/a/vm2/log
printf 'vm2-test-password\nvm2-test-password\n' | smbpasswd -s -a -c /run/samba-vm2/smb.conf smbtest > "$L/smb-user-setup.log" 2>&1
printf 'wrong-password\n' | python3 /root/mirror.py smb smb://127.0.0.1/secure --user smbtest --password-stdin > "$L/smb-wrong.json" 2> "$L/smb-wrong.err"; echo $? > "$L/smb-wrong.status"
printf 'vm2-test-password\n' | python3 /root/mirror.py smb smb://127.0.0.1/secure --user smbtest --password-stdin > "$L/smb-user.json" 2> "$L/smb-user.err"; echo $? > "$L/smb-user.status"
mount > "$L/smb-auth-mounts.log"
dmesg | tail -80 > "$L/smb-auth-dmesg.log"
