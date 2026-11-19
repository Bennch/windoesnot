#!/usr/bin/env python3
"""Exercise missing synthetic scan fixtures without changing the read-only disk."""
import json, os, pathlib, socket, subprocess
r = pathlib.Path('/mnt/a/probe-source'); h = r / 'home/benni'
for p in (r/'etc', h/'.ssh', h/'Projekte/demo/.git', h/'Projekte/demo/node_modules', h/'Daten'):
    p.mkdir(parents=True, exist_ok=True)
(r/'etc/passwd').write_text('benni:x:1000:1000::/home/benni:/bin/bash\nanna:x:1001:1001::/home/anna:/bin/bash\n')
(h/'.ssh').chmod(0o700)
(h/'.ssh/id_test').write_text('fixture\n')
(h/'Projekte/demo/node_modules/rebuild').write_text('rebuild\n')
subprocess.run(['mount','-t','tmpfs','-o','size=1m','tmpfs',str(h/'Daten')],check=True)
(h/'Daten/mounted').write_text('nested mount\n')
sock=socket.socket(socket.AF_UNIX); sock.bind(str(h/'Projekte/demo/test.sock'))
try:
    subprocess.run(['python3','/root/finder.py','scan','--root',str(r),'--user','benni','--output','/mnt/a/log/probe-scan.json'],check=True)
    d=json.load(open('/mnt/a/log/probe-scan.json'))
    print(json.dumps([{'id':f['id'],'paths':f['paths'],'selected':f['selected'],'warnings':f['warnings']} for f in d['findings']],indent=2))
    out=pathlib.Path('/mnt/a/probe-copy/home/benni'); out.mkdir(parents=True,exist_ok=True)
    subprocess.run(['python3','/root/finder.py','copy','/mnt/a/log/probe-scan.json',str(out),'--target-root','/mnt/a/probe-copy'],check=True)
    print('nested_content:',(out/'Daten/mounted').exists(),'socket_copied:',(out/'Projekte/demo/test.sock').exists(),'node_modules_copied:',(out/'Projekte/demo/node_modules').exists())
finally:
    sock.close()
    subprocess.run(['umount',str(h/'Daten')],check=True)
