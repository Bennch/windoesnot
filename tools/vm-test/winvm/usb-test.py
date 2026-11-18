#!/usr/bin/env python3
"""USB writer test in a disposable Windows VM (10 or 11, UEFI): virtual USB stick + an extra internal disk.

  usb-test.py prepare 11 --iso ISO --sha256 HEX    overlay, payload CD (harness + ISO), results disk
  usb-test.py run 11                               boot it (the boot task runs usb-run.ps1, then powers off)
  usb-test.py results 11 [dir]                     copy the results
  usb-test.py boot-stick 11 uefi|bios [--4k]       boot the written stick alone (screenshot via QMP)
"""
import argparse, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import winvm

ROOT = winvm.ROOT
HARNESS = ROOT / 'build/usb-harness'


def wd(v):
    return ROOT / 'vm' / f'usb-e2-{v}'


def run(*a, **k):
    return subprocess.run([str(x) for x in a], check=True, **k)


def prepare(v, iso, sha, fourk=False, ps=False):
    d = wd(v)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    base = winvm.vmdir(v)
    run('qemu-img', 'create', '-q', '-f', 'qcow2', '-b', base / 'disk.qcow2', '-F', 'qcow2', d / 'disk.qcow2')
    if (base / 'OVMF_VARS.fd').exists():
        shutil.copyfile(base / 'OVMF_VARS.fd', d / 'OVMF_VARS.fd')
    run('qemu-img', 'create', '-q', '-f', 'qcow2', d / 'stick.qcow2', '16G')
    (d / 'fourk').write_text('1' if fourk else '0')
    run('qemu-img', 'create', '-q', '-f', 'qcow2', d / 'internal.qcow2', '16G')
    src = d / 'payload-src'
    src.mkdir()
    (src / 'WDN_PAYLOAD.txt').write_text('payload\r\n')
    jobs = winvm.Path(__file__).resolve().parent / 'jobs'
    if ps:
        shutil.copyfile(jobs / 'usb-ps-job.cmd', src / 'job.cmd')
        shutil.copyfile(jobs / 'usb-ps-run.ps1', src / 'usb-ps-run.ps1')
        shutil.copytree(ROOT / 'windows', src / 'windows', ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    else:
        shutil.copyfile(jobs / 'usb-job.cmd', src / 'job.cmd')
        shutil.copyfile(jobs / 'usb-run.ps1', src / 'usb-run.ps1')
    (src / 'iso.sha256').write_text(sha + '\r\n')
    if not ps:
        shutil.copytree(HARNESS, src / 'harness')
    # The 5 GB ISO does not fit a plain ISO9660 payload CD: the VM downloads it from the host (http://10.0.2.2:8130/).
    (src / 'iso.name').write_text(Path(iso).name + '\r\n')
    run('genisoimage', '-quiet', '-J', '-r', '-V', 'WDNPAYLOAD', '-o', d / 'payload.iso', src)
    shutil.rmtree(src)
    res = d / 'results.img'
    run('truncate', '-s', '96M', res)
    run('sfdisk', '--quiet', res, input=b'label: dos\nstart=2048, type=c\n')
    run('mformat', '-i', f'{res}@@1M', '-F', '-v', 'WDNRESULTS', '::')
    marker = d / 'WDN_RESULTS.txt'
    marker.write_text('results\r\n')
    run('mcopy', '-i', f'{res}@@1M', marker, '::')
    marker.unlink()
    print('prepared', d)


def qemu(v):
    c = winvm.VERSIONS[v]
    d = wd(v)
    usbc = 'qemu-xhci' if c['boot'] == 'uefi' else 'usb-ehci'
    cmd = ['qemu-system-x86_64', '-name', f'usb-e2-{v}', '-accel', 'kvm', '-cpu', 'host', '-smp', '4', '-m', str(c['mem']),
           '-rtc', 'base=localtime', '-vga', 'std', '-display', 'none', '-daemonize',
           '-pidfile', d / 'qemu.pid', '-qmp', f'unix:{d / "qmp.sock"},server=on,wait=off',
           ] + (['-machine', 'q35', '-drive', f'if=pflash,format=raw,readonly=on,file={winvm.OVMF_CODE}',
           '-drive', f'if=pflash,format=raw,file={d / "OVMF_VARS.fd"}'] if c['boot'] == 'uefi' else ['-machine', 'pc']) + [
           '-device', 'ahci,id=ahci',
           '-drive', f'file={d / "disk.qcow2"},if=none,id=hd0,format=qcow2', '-device', 'ide-hd,drive=hd0,bus=ahci.0,bootindex=1',
           '-drive', f'file={d / "internal.qcow2"},if=none,id=hd1,format=qcow2', '-device', 'ide-hd,drive=hd1,bus=ahci.1',
           '-drive', f'file={d / "payload.iso"},media=cdrom,if=none,id=pay,readonly=on', '-device', 'ide-cd,drive=pay,bus=ahci.2',
           '-device', usbc + ',id=xhci', '-device', 'usb-tablet,bus=xhci.0', '-device', 'usb-kbd,bus=xhci.0',
           '-drive', f'file={d / "stick.qcow2"},if=none,id=stick,format=qcow2', '-device', 'usb-storage,bus=xhci.0,drive=stick,removable=on' + (',logical_block_size=4096,physical_block_size=4096' if (d / 'fourk').read_text() == '1' else ''),
           '-drive', f'file={d / "results.img"},if=none,id=res,format=raw', '-device', 'usb-storage,bus=xhci.0,drive=res',
           '-nic', 'user,model=e1000']
    return cmd


def qmp(v, cmd, **a):
    d = wd(v)
    import socket, json
    s = socket.socket(socket.AF_UNIX)
    s.connect(str(d / 'qmp.sock'))
    f = s.makefile('rw')
    f.readline()
    f.write(json.dumps({'execute': 'qmp_capabilities'}) + '\n'); f.flush(); f.readline()
    f.write(json.dumps({'execute': cmd, 'arguments': a}) + '\n'); f.flush()
    while True:
        line = json.loads(f.readline())
        if 'return' in line or 'error' in line:
            s.close()
            return line


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('action', choices=['prepare', 'run', 'results', 'shot', 'boot-stick'])
    p.add_argument('version', choices=['7', '8.1', '10', '11'])
    p.add_argument('--ps', action='store_true', help='test the PowerShell stick writer (windows/WinDoesNotStick.ps1)')
    p.add_argument('arg', nargs='?')
    p.add_argument('--iso')
    p.add_argument('--sha256')
    p.add_argument('--4k', dest='fourk', action='store_true')
    a = p.parse_args()
    v = a.version
    d = wd(v)
    if a.action == 'prepare':
        prepare(v, a.iso, a.sha256, a.fourk, a.ps)
    elif a.action == 'run':
        run(*qemu(v))
        print('started')
    elif a.action == 'results':
        out = Path(a.arg or d / 'results-out')
        out.mkdir(parents=True, exist_ok=True)
        run('mcopy', '-n', '-s', '-i', f'{d / "results.img"}@@1M', '::/', out)
        print(out)
    elif a.action == 'shot':
        print(qmp(v, 'screendump', filename=str(Path(a.arg).resolve()), format='png'))
    elif a.action == 'boot-stick':
        mode = a.arg or 'uefi'
        bd = ROOT / 'vm' / f'usb-e2-boot-{v}-{mode}'
        bd.mkdir(exist_ok=True)
        blk = ',logical_block_size=4096,physical_block_size=4096' if a.fourk else ''
        cmd = ['qemu-system-x86_64', '-name', 'usb-boot', '-accel', 'kvm', '-cpu', 'host', '-smp', '2', '-m', '4096', '-vga', 'std',
               '-display', 'none', '-daemonize', '-pidfile', bd / 'qemu.pid', '-qmp', f'unix:{bd / "qmp.sock"},server=on,wait=off',
               '-device', 'qemu-xhci,id=xhci', '-device', 'usb-tablet,bus=xhci.0',
               '-drive', f'file={d / "stick.qcow2"},if=none,id=stick,format=qcow2', '-device', f'usb-storage,bus=xhci.0,drive=stick,bootindex=1{blk}']
        if mode == 'uefi':
            shutil.copyfile(winvm.OVMF_VARS, bd / 'vars.fd')
            cmd += ['-machine', 'q35', '-drive', f'if=pflash,format=raw,readonly=on,file={winvm.OVMF_CODE}', '-drive', f'if=pflash,format=raw,file={bd / "vars.fd"}']
        else:
            cmd += ['-machine', 'pc']
        run(*cmd)
        print('boot started', bd)


main()
