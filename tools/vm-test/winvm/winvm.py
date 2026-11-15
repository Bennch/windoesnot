#!/usr/bin/env python3
"""Disposable Windows test VMs (7, 8.1, 10, 11) for the migration tool.

Everything is unattended and uses synthetic data only. The VMs live in vm/winmig-<version>/.

  winvm.py create 10          disk, unattend ISO, payload ISO, results disk
  winvm.py install 10         boot the Windows ISO; Windows installs itself (about 15-30 minutes)
  winvm.py run 10             boot the installed system
  winvm.py payload 10         rebuild payload.iso from windows/ and the job script (VM may be running only after stop)
  winvm.py shot 10 out.png    screenshot through QMP
  winvm.py results 10 [dir]   copy files from the results disk
  winvm.py stop 10            power off the VM
  winvm.py status

The payload ISO carries firstlogon.cmd and job.cmd. firstlogon.cmd runs once after the automatic setup, copies the
payload to C:\\wdn-test and registers a logon hook that runs job.cmd from whichever CD holds WDN_PAYLOAD.txt.
job.cmd writes its output to the results disk (marker WDN_RESULTS.txt) and ends with DONE.txt.
Windows media come from the user's own collection; no keys are stored here (only the public generic edition keys).
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
MEDIA = Path(os.environ.get('WDN_WINDOWS_MEDIA', Path.home() / 'Schreibtisch/Versand/Windows Versionen'))
OVMF_CODE = Path('/usr/share/edk2/x64/OVMF_CODE.4m.fd')
OVMF_VARS = Path('/usr/share/edk2/x64/OVMF_VARS.4m.fd')
PASSWORD = 'Test12345'  # disposable test VMs only
USER = 'tester'

# Public generic edition-selection keys (Microsoft KMS client setup keys). They do not activate Windows.
VERSIONS = {
    '7': dict(iso='Windows 7/de_windows_7_professional_with_sp1_x64_dvd_u_676919.iso', boot='bios', name='Windows 7 PROFESSIONAL',
              key='FJ82H-XT6CR-J8D7P-XQJJ2-GPDD4', disk=40, mem=3072, nic='e1000'),
    '8.1': dict(iso='Windows 8.1/Win8.1_German_x64.iso', boot='bios', name='Windows 8.1 Pro',
                key='GCRJD-8NW9H-F2CDX-CCM8D-9D6T9', disk=40, mem=3072, nic='e1000'),
    '10': dict(iso='Windows 10/Win10_22H2_German_x64.iso', boot='uefi', name='Windows 10 Pro',
               key='W269N-WFGWX-YVC9B-4J6C9-T83GX', disk=50, mem=4096, nic='e1000'),
    '11': dict(iso='Windows 11/Win11_24H2_German_x64.iso', boot='uefi', name='Windows 11 Pro',
               key='W269N-WFGWX-YVC9B-4J6C9-T83GX', disk=64, mem=4096, nic='e1000', bypass=True),
}
NS = ('xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" '
      'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
COMP = 'processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"'


def vmdir(version):
    return ROOT / 'vm' / ('winmig-' + version)


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def unattend_xml(version):
    c = VERSIONS[version]
    uefi = c['boot'] == 'uefi'
    if uefi:
        partitions = ('<CreatePartition wcm:action="add"><Order>1</Order><Type>EFI</Type><Size>100</Size></CreatePartition>'
                      '<CreatePartition wcm:action="add"><Order>2</Order><Type>MSR</Type><Size>16</Size></CreatePartition>'
                      '<CreatePartition wcm:action="add"><Order>3</Order><Type>Primary</Type><Extend>true</Extend></CreatePartition>')
        modify = ('<ModifyPartition wcm:action="add"><Order>1</Order><PartitionID>1</PartitionID><Format>FAT32</Format><Label>System</Label></ModifyPartition>'
                  '<ModifyPartition wcm:action="add"><Order>2</Order><PartitionID>2</PartitionID></ModifyPartition>'
                  '<ModifyPartition wcm:action="add"><Order>3</Order><PartitionID>3</PartitionID><Format>NTFS</Format><Label>Windows</Label><Letter>C</Letter></ModifyPartition>')
        target = 3
    else:
        partitions = '<CreatePartition wcm:action="add"><Order>1</Order><Type>Primary</Type><Extend>true</Extend></CreatePartition>'
        modify = ('<ModifyPartition wcm:action="add"><Order>1</Order><PartitionID>1</PartitionID><Format>NTFS</Format>'
                  '<Label>Windows</Label><Letter>C</Letter><Active>true</Active></ModifyPartition>')
        target = 1
    bypass = ''
    if c.get('bypass'):
        cmds = ['BypassTPMCheck', 'BypassSecureBootCheck', 'BypassRAMCheck', 'BypassCPUCheck', 'BypassStorageCheck']
        bypass = '<RunSynchronous>' + ''.join(
            f'<RunSynchronousCommand wcm:action="add"><Order>{i}</Order><Path>reg add HKLM\\SYSTEM\\Setup\\LabConfig /v {n} /t REG_DWORD /d 1 /f</Path></RunSynchronousCommand>'
            for i, n in enumerate(cmds, 1)) + '</RunSynchronous>'
    modern = version in ('8.1', '10', '11')
    oobe = ('<HideEULAPage>true</HideEULAPage><NetworkLocation>Work</NetworkLocation><ProtectYourPC>3</ProtectYourPC>'
            '<SkipMachineOOBE>true</SkipMachineOOBE><SkipUserOOBE>true</SkipUserOOBE>')
    if modern:
        oobe += '<HideLocalAccountScreen>true</HideLocalAccountScreen><HideOnlineAccountScreens>true</HideOnlineAccountScreens><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>'
    intl = '<InputLocale>de-DE</InputLocale><SystemLocale>de-DE</SystemLocale><UILanguage>de-DE</UILanguage><UserLocale>de-DE</UserLocale>'
    hook = r'cmd /c for %d in (D E F G H I J K) do if exist %d:\WDN_PAYLOAD.txt call %d:\firstlogon.cmd'
    return f'''<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
 <settings pass="windowsPE">
  <component name="Microsoft-Windows-International-Core-WinPE" {COMP} {NS}>
   <SetupUILanguage><UILanguage>de-DE</UILanguage></SetupUILanguage>{intl}
  </component>
  <component name="Microsoft-Windows-Setup" {COMP} {NS}>
   {bypass}
   <DiskConfiguration><WillShowUI>OnError</WillShowUI><Disk wcm:action="add"><DiskID>0</DiskID><WillWipeDisk>true</WillWipeDisk>
    <CreatePartitions>{partitions}</CreatePartitions><ModifyPartitions>{modify}</ModifyPartitions></Disk></DiskConfiguration>
   <ImageInstall><OSImage><InstallFrom><MetaData wcm:action="add"><Key>/IMAGE/NAME</Key><Value>{c['name']}</Value></MetaData></InstallFrom>
    <InstallTo><DiskID>0</DiskID><PartitionID>{target}</PartitionID></InstallTo><WillShowUI>OnError</WillShowUI></OSImage></ImageInstall>
   <UserData><AcceptEula>true</AcceptEula><ProductKey><Key>{c['key']}</Key><WillShowUI>OnError</WillShowUI></ProductKey></UserData>
  </component>
 </settings>
 <settings pass="specialize">
  <component name="Microsoft-Windows-Shell-Setup" {COMP} {NS}><ComputerName>WDN-TEST</ComputerName><TimeZone>W. Europe Standard Time</TimeZone></component>
 </settings>
 <settings pass="oobeSystem">
  <component name="Microsoft-Windows-International-Core" {COMP} {NS}>{intl}</component>
  <component name="Microsoft-Windows-Shell-Setup" {COMP} {NS}>
   <AutoLogon><Password><Value>{PASSWORD}</Value><PlainText>true</PlainText></Password><Enabled>true</Enabled><LogonCount>9999</LogonCount><Username>{USER}</Username></AutoLogon>
   <UserAccounts><LocalAccounts><LocalAccount wcm:action="add"><Password><Value>{PASSWORD}</Value><PlainText>true</PlainText></Password>
    <Group>Administrators</Group><DisplayName>{USER}</DisplayName><Name>{USER}</Name></LocalAccount></LocalAccounts></UserAccounts>
   <OOBE>{oobe}</OOBE>
   <FirstLogonCommands><SynchronousCommand wcm:action="add"><Order>1</Order><CommandLine>{hook}</CommandLine><RequiresUserInput>false</RequiresUserInput></SynchronousCommand></FirstLogonCommands>
  </component>
 </settings>
</unattend>
'''


FIRSTLOGON = r'''@echo off
rem Runs once after the unattended setup (disposable test VM).
set SRC=%~dp0
if not exist C:\wdn-test mkdir C:\wdn-test
xcopy /E /Y /I "%SRC%windows" C:\wdn-test\windows >nul
rem No UAC prompts for administrators, so scripted runs and screenshots stay clean (full effect after the next restart).
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v EnableLUA /t REG_DWORD /d 0 /f >nul
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f >nul
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f >nul
rem Boot task (SYSTEM, highest privileges) that runs job.cmd from the payload CD, no logon needed.
schtasks /create /tn WdnJob /sc onstart /ru SYSTEM /rl highest /f /tr "cmd /c for %%d in (D E F G H I J K) do if exist %%d:\WDN_PAYLOAD.txt call %%d:\job.cmd" >nul
call "%SRC%job.cmd"
'''

JOB_DEFAULT = r'''@echo off
rem Default job: record that the VM is up. Results go to the disk that holds WDN_RESULTS.txt.
set RES=
for %%d in (D E F G H I J K L M) do if exist %%d:\WDN_RESULTS.txt set RES=%%d:
if "%RES%"=="" goto :eof
ver > %RES%\ready.txt
echo DONE > %RES%\DONE.txt
'''


def make_iso(src, out, label):
    run('genisoimage', '-quiet', '-o', out, '-J', '-r', '-V', label, src)


def build_payload(version, job=None, gui=False):
    d = vmdir(version)
    tmp = d / 'payload-src'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    (tmp / 'WDN_PAYLOAD.txt').write_text('payload\r\n')
    (tmp / 'firstlogon.cmd').write_text(FIRSTLOGON.replace('\n', '\r\n'))
    (tmp / 'job.cmd').write_text((Path(job).read_text() if job else JOB_DEFAULT).replace('\r\n', '\n').replace('\n', '\r\n'))
    shutil.copytree(ROOT / 'windows', tmp / 'windows', ignore=shutil.ignore_patterns('__pycache__'))
    jobs = Path(__file__).resolve().parent / 'jobs'
    shutil.copyfile(jobs / 'gui.cmd', tmp / 'gui.cmd')
    if gui:
        (tmp / 'WDN_GUI.txt').write_text('gui\r\n')
    make_iso(tmp, d / 'payload.iso', 'WDNPAYLOAD')
    shutil.rmtree(tmp)


def create(version, args):
    c = VERSIONS[version]
    d = vmdir(version)
    d.mkdir(parents=True, exist_ok=True)
    run('qemu-img', 'create', '-q', '-f', 'qcow2', d / 'disk.qcow2', f"{c['disk']}G")
    if c['boot'] == 'uefi':
        shutil.copyfile(OVMF_VARS, d / 'OVMF_VARS.fd')
    tmp = d / 'unattend-src'
    tmp.mkdir(exist_ok=True)
    (tmp / 'autounattend.xml').write_text(unattend_xml(version))
    make_iso(tmp, d / 'unattend.iso', 'UNATTEND')
    shutil.rmtree(tmp)
    build_payload(version)
    results = d / 'results.img'
    run('truncate', '-s', '96M', results)
    run('sfdisk', '--quiet', results, input=b'label: dos\nstart=2048, type=c\n')
    run('mformat', '-i', f'{results}@@1M', '-F', '-v', 'WDNRESULTS', '::')
    marker = d / 'WDN_RESULTS.txt'
    marker.write_text('results\r\n')
    run('mcopy', '-i', f'{results}@@1M', marker, '::')
    marker.unlink()
    print('created', d)


def qemu_command(version, install):
    c = VERSIONS[version]
    d = vmdir(version)
    media = Path(os.environ.get('WDN_ISO_' + version.replace('.', ''), MEDIA / c['iso']))
    cmd = ['qemu-system-x86_64', '-name', 'winmig-' + version, '-accel', 'kvm', '-cpu', 'host', '-smp', '4', '-m', str(c['mem']),
           '-rtc', 'base=localtime', '-vga', 'std', '-display', 'none', '-daemonize',
           '-pidfile', d / 'qemu.pid', '-qmp', f'unix:{d / "qmp.sock"},server=on,wait=off']
    if c['boot'] == 'uefi':
        cmd += ['-machine', 'q35', '-drive', f'if=pflash,format=raw,readonly=on,file={OVMF_CODE}',
                '-drive', f'if=pflash,format=raw,file={d / "OVMF_VARS.fd"}']
    else:
        cmd += ['-machine', 'pc']
    cmd += ['-device', 'ahci,id=ahci',
            '-drive', f'file={d / "disk.qcow2"},if=none,id=hd0,format=qcow2', '-device', 'ide-hd,drive=hd0,bus=ahci.0,bootindex=2']
    cdroms = []
    if install:
        cdroms.append((media, 'inst', 1))
    cdroms += [(d / 'unattend.iso', 'una', None), (d / 'payload.iso', 'pay', None)]
    for i, (path, ident, boot) in enumerate(cdroms):
        cmd += ['-drive', f'file={path},media=cdrom,if=none,id={ident},readonly=on', '-device', f'ide-cd,drive={ident},bus=ahci.{i + 1}'
                + (f',bootindex={boot}' if boot else '')]
    cmd += ['-device', 'usb-ehci,id=ehci', '-device', 'usb-tablet,bus=ehci.0', '-device', 'usb-kbd,bus=ehci.0',
            '-drive', f'file={d / "results.img"},if=none,id=res,format=raw', '-device', 'usb-storage,bus=ehci.0,drive=res',
            '-nic', f'user,model={c["nic"]}']
    return cmd


def qmp(version, command, **arguments):
    d = vmdir(version)
    s = socket.socket(socket.AF_UNIX)
    s.connect(str(d / 'qmp.sock'))
    f = s.makefile('rw')
    f.readline()
    f.write(json.dumps({'execute': 'qmp_capabilities'}) + '\n'); f.flush(); f.readline()
    f.write(json.dumps({'execute': command, 'arguments': arguments}) + '\n'); f.flush()
    while True:
        line = json.loads(f.readline())
        if 'return' in line or 'error' in line:
            s.close()
            return line


def sendkey(version, key):
    qmp(version, 'human-monitor-command', **{'command-line': 'sendkey ' + key})


def start(version, install):
    d = vmdir(version)
    if (d / 'qemu.pid').exists():
        try:
            os.kill(int((d / 'qemu.pid').read_text()), 0)
            sys.exit('already running')
        except (OSError, ValueError):
            pass
    run(*qemu_command(version, install))
    print('started', version)
    if install:
        # "Press any key to boot from CD or DVD" appears briefly.
        for _ in range(22):
            time.sleep(1)
            try:
                sendkey(version, 'ret')
            except OSError:
                pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('action', choices=['create', 'install', 'run', 'payload', 'shot', 'results', 'clear', 'stop', 'status', 'key', 'type'])
    p.add_argument('version', nargs='?', choices=list(VERSIONS))
    p.add_argument('arg', nargs='?')
    p.add_argument('--job', help='job script for the payload')
    p.add_argument('--gui', action='store_true', help='payload starts the exporter window at logon (needs the WdnGui task)')
    a = p.parse_args()
    if a.action == 'status':
        for v in VERSIONS:
            d = vmdir(v)
            state = 'missing'
            if d.exists():
                state = 'created'
                if (d / 'qemu.pid').exists():
                    try:
                        os.kill(int((d / 'qemu.pid').read_text()), 0)
                        state = 'running'
                    except (OSError, ValueError):
                        pass
            print(v, state)
        return
    if not a.version:
        p.error('version required')
    v = a.version
    if a.action == 'create':
        create(v, a)
    elif a.action == 'install':
        start(v, True)
    elif a.action == 'run':
        start(v, False)
    elif a.action == 'payload':
        build_payload(v, a.job, a.gui)
    elif a.action == 'shot':
        out = Path(a.arg or vmdir(v) / 'screen.png').resolve()
        print(qmp(v, 'screendump', filename=str(out), format='png'))
    elif a.action == 'key':
        sendkey(v, a.arg)
    elif a.action == 'type':
        for ch in a.arg:
            sendkey(v, {' ': 'spc', '\n': 'ret'}.get(ch, ch if ch.islower() or ch.isdigit() else ('shift-' + ch.lower() if ch.isalpha() else ch)))
    elif a.action == 'results':
        out = Path(a.arg or vmdir(v) / 'results-out')
        out.mkdir(parents=True, exist_ok=True)
        run('mcopy', '-n', '-s', '-i', f'{vmdir(v) / "results.img"}@@1M', '::/', out)
        print(out)
    elif a.action == 'clear':
        listing = subprocess.run(['mdir', '-b', '-i', f'{vmdir(v) / "results.img"}@@1M', '::/'], capture_output=True, text=True).stdout.split()
        for name in listing:
            if not name.upper().endswith('WDN_RESULTS.TXT'):
                subprocess.run(['mdeltree', '-i', f'{vmdir(v) / "results.img"}@@1M', name], capture_output=True)
    elif a.action == 'stop':
        # Clean ACPI shutdown first (a hard quit leaves Windows in recovery after a few rounds), hard quit as a fallback.
        try:
            qmp(v, 'system_powerdown')
            pid = int((vmdir(v) / 'qemu.pid').read_text())
            for _ in range(90):
                time.sleep(1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                qmp(v, 'quit')
        except (OSError, ValueError):
            pass


if __name__ == '__main__':
    main()
