#!/usr/bin/env python3
"""Inspect the project's own QEMU VM through its local QMP/guest-agent sockets."""
import argparse
import base64
import json
from pathlib import Path
import socket
import time

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--vm-name',default='debug')
parser.add_argument('action',choices=['status','screenshot','stop','hmp','exec','agent-info','push','pull','click','type'])
parser.add_argument('arguments',nargs=argparse.REMAINDER)
args=parser.parse_args()
if not args.vm_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.vm_name):parser.error('Invalid VM name')
vm=ROOT/'vm'/args.vm_name
agent=args.action in ['exec','agent-info','push','pull']
connection=socket.socket(socket.AF_UNIX);connection.settimeout(15)
connection.connect(str(vm/('guest-agent.sock' if agent else 'qmp.sock')))
stream=connection.makefile('rwb',buffering=0)

def command(name,arguments=None):
    payload={'execute':name}
    if arguments is not None:payload['arguments']=arguments
    stream.write(json.dumps(payload).encode()+b'\n')
    while True:
        line=stream.readline()
        if not line:raise RuntimeError('VM connection closed')
        result=json.loads(line)
        if 'error' in result:raise RuntimeError(result['error'])
        if 'return' in result:return result['return']

if not agent:
    json.loads(stream.readline());command('qmp_capabilities')
if args.action=='click':
    if len(args.arguments) not in [2,4]:parser.error('click x y [screen-width screen-height]')
    values=list(map(int,args.arguments));x,y=values[:2];width,height=values[2:] if len(values)==4 else [1280,800]
    command('input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':round(x*32767/width)}},{'type':'abs','data':{'axis':'y','value':round(y*32767/height)}}]})
    command('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':True}}]})
    command('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':False}}]})
elif args.action=='type':
    text=' '.join(args.arguments)
    for character in text:
        if character==' ':key='spc'
        elif character=='-':key='minus'
        elif character.isascii() and character.isalnum():key=('shift-' if character.isupper() else '')+character.lower()
        else:parser.error('Supported text: ASCII letters, numbers, spaces and hyphens')
        command('human-monitor-command',{'command-line':'sendkey '+key+' 10'})
        time.sleep(.04)
elif args.action=='status':print(json.dumps(command('query-status'),indent=2))
elif args.action=='screenshot':
    # Write only inside this VM's directory.
    path=vm/'screen.png';command('screendump',{'filename':str(path),'format':'png'});print(path)
elif args.action=='stop':command('quit');print('VM stopped')
elif args.action=='hmp':print(command('human-monitor-command',{'command-line':' '.join(args.arguments)}))
elif args.action=='pull':
    if len(args.arguments)!=2:parser.error('pull needs guest source and filename inside the VM directory')
    source,name=args.arguments
    if Path(name).name!=name:parser.error('Use a plain output filename')
    dest=vm/name
    handle=command('guest-file-open',{'path':source,'mode':'rb'})
    try:
        with dest.open('wb') as output:
            while True:
                chunk=command('guest-file-read',{'handle':handle,'count':65536})
                output.write(base64.b64decode(chunk.get('buf-b64','')))
                if chunk.get('eof'):break
    finally:command('guest-file-close',{'handle':handle})
    print(dest)
elif args.action=='push':
    if len(args.arguments)!=2:parser.error('push needs host source and absolute guest destination')
    source,dest=args.arguments
    if not dest.startswith('/'):parser.error('Guest destination must be absolute')
    content=Path(source).read_bytes()
    handle=command('guest-file-open',{'path':dest,'mode':'wb'})
    try:
        for offset in range(0,len(content),65536):
            command('guest-file-write',{'handle':handle,'buf-b64':base64.b64encode(content[offset:offset+65536]).decode()})
    finally:command('guest-file-close',{'handle':handle})
    print('Transferred',len(content),'bytes to guest',dest)
elif args.action=='agent-info':print(json.dumps(command('guest-info'),indent=2))
elif args.action=='exec':
    if not args.arguments:parser.error('exec needs an absolute guest executable and arguments')
    if not args.arguments[0].startswith('/'):parser.error('Use an absolute guest executable')
    result=command('guest-exec',{'path':args.arguments[0],'arg':args.arguments[1:],'capture-output':True})
    for attempt in range(60):
        status=command('guest-exec-status',{'pid':result['pid']})
        if status.get('exited'):
            for field in ['out-data','err-data']:
                if field in status:print(base64.b64decode(status[field]).decode(errors='replace'),end='')
            raise SystemExit(status.get('exitcode',1))
        time.sleep(.5)
    raise SystemExit('Guest command still running after 30 seconds')
