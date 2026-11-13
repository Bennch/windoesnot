#!/usr/bin/env python3
"""Host-only fixture coverage for hardware detection and privacy-safe output."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('hwcheck', ROOT / 'desktop/lib/windoesnot/hwcheck.py')
hw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hw)


def fixture(cpu, mem, swap='0', ids='', log='', pci='', cards=()):
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    proc = root / 'proc'; proc.mkdir()
    sys = root / 'sys'; sys.mkdir()
    (proc / 'cpuinfo').write_text(cpu)
    (proc / 'meminfo').write_text(f'MemTotal:       {mem} kB\nSwapTotal:      {swap} kB\n')
    idfile = root / 'nouveau.ids'; idfile.write_text(ids)
    logfile = root / 'hyprland.log'; logfile.write_text(log)
    (sys / 'block').mkdir(parents=True)
    (sys / 'bus/pci/drivers').mkdir(parents=True)
    (sys / 'class/net').mkdir(parents=True)
    (sys / 'class/power_supply').mkdir(parents=True)
    for name, kind in cards:
        (sys / 'bus/pci/drivers' / kind).mkdir(parents=True, exist_ok=True)
        device = sys / 'bus/pci/devices' / name
        device.mkdir(parents=True)
        (device / 'driver').symlink_to(sys / 'bus/pci/drivers' / kind)
    for disk, rotating in [('sda', '1'), ('nvme0n1', '0')]:
        q = sys / 'block' / disk / 'queue'; q.mkdir(parents=True)
        (q / 'rotational').write_text(rotating)
    (sys / 'class/net/wlan0').mkdir()
    (sys / 'class/bluetooth').mkdir()
    (sys / 'class/bluetooth/hci0').mkdir()
    (sys / 'class/power_supply/BAT0').mkdir()
    env = {'WINDOESNOT_PROC_ROOT': str(proc), 'WINDOESNOT_SYS_ROOT': str(sys),
           'WINDOESNOT_NOUVEAU_IDS': str(idfile), 'WINDOESNOT_HYPRLAND_LOG': str(logfile)}
    return temp, mock.patch.dict(os.environ, env, clear=False), pci


def run(case):
    temp, envpatch, pci = case
    with envpatch, mock.patch.object(hw, 'PROC', Path(os.environ['WINDOESNOT_PROC_ROOT'])), \
            mock.patch.object(hw, 'SYS', Path(os.environ['WINDOESNOT_SYS_ROOT'])), \
            mock.patch.object(hw, 'NOUVEAU_IDS', Path(os.environ['WINDOESNOT_NOUVEAU_IDS'])), \
            mock.patch.object(hw, 'HYPR_LOG', Path(os.environ['WINDOESNOT_HYPRLAND_LOG'])), \
            mock.patch.object(hw.subprocess, 'run', return_value=mock.Mock(stdout=pci, returncode=0)):
        try:
            return hw.build_report()
        finally:
            temp.cleanup()


modern = 'processor : 0\nmodel name : Modern CPU\nflags : fpu sse4_1 sse4_2 avx avx2\n\nprocessor : 1\n'
gpu_mix = '''00:02.0 VGA compatible controller [0300]: NVIDIA Modern [10de:2684]
01:00.0 VGA compatible controller [0300]: AMD Modern [1002:744c]
02:00.0 VGA compatible controller [0300]: Intel Modern [8086:56a0]
'''
report = run(fixture(modern, 16384000, pci=gpu_mix, cards=(('00:02.0', 'nvidia'),)))
assert [g['vendor_id'] for g in report['gpus']] == ['10de', '1002', '8086']
assert report['gpus'][0]['driver'] == 'nvidia' and not report['recommendations'], report
assert report['battery'] and report['controllers'] == {'wifi': True, 'bluetooth': True}
assert {d['kind'] for d in report['disks']} == {'hdd', 'ssd_or_flash'}

tesla = '00:0d.0 VGA compatible controller [0300]: NVIDIA GT218M [10de:0a70]\n'
report = run(fixture(modern, 8192000, ids='0a70\n', pci=tesla))
assert report['gpus'][0]['legacy_nouveau']
assert any(r['id'] == 'lite_mode' and 'legacy_gpu' in r['reasons'] for r in report['recommendations'])

virtio = '00:02.0 VGA compatible controller [0300]: Red Hat Virtio GPU [1af4:1050]\n'
report = run(fixture(modern, 8192000, log='OpenGL renderer: llvmpipe (LLVM 18.1.8)\n', pci=virtio))
assert report['renderer'] == 'llvmpipe'
assert any(r['id'] == 'lite_mode' and 'software_renderer' in r['reasons'] for r in report['recommendations'])

pentium = 'processor : 0\nmodel name : Pentium(R) Dual-Core CPU T4500\nflags : fpu sse sse2\n\nprocessor : 1\nmodel name : Pentium(R) Dual-Core CPU T4500\nflags : fpu sse sse2\n'
report = run(fixture(pentium, 2097152, swap='1048576', pci=tesla, ids=''))
assert report['cpu']['model'].startswith('Pentium') and report['cpu']['cores'] == 2
assert report['cpu']['missing_instruction_sets'] == ['sse4_1', 'sse4_2', 'avx', 'avx2']
recommendations = {r['id']: r for r in report['recommendations']}
assert {'lite_mode', 'x86_64_v1_packages', 'low_ram'} <= recommendations.keys()
assert recommendations['lite_mode']['reasons'] == ['low_ram', 'no_sse4_1']

serialized = json.dumps(report)
for forbidden in ('serial', 'mac', 'ip_address', 'username', 'user_name', 'hostname'):
    assert forbidden not in serialized.lower()
print('PASS: modern NVIDIA/AMD/Intel, legacy Tesla, virtio without GL, Pentium low-RAM and privacy-safe report')
