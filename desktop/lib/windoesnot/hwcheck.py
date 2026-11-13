#!/usr/bin/python3
"""Small, read-only hardware summary for WinDoesNot. Emits privacy-safe JSON."""
import json
import os
from pathlib import Path
import re
import subprocess

PROC = Path(os.environ.get('WINDOESNOT_PROC_ROOT', '/proc'))
SYS = Path(os.environ.get('WINDOESNOT_SYS_ROOT', '/sys'))
NOUVEAU_IDS = Path(os.environ.get('WINDOESNOT_NOUVEAU_IDS', '/var/lib/chwd/ids/nouveau.ids'))
HYPR_LOG = Path(os.environ.get('WINDOESNOT_HYPRLAND_LOG', '')) if os.environ.get('WINDOESNOT_HYPRLAND_LOG') else None
LSPCI = os.environ.get('WINDOESNOT_LSPCI', '/usr/bin/lspci')
FEATURES = ('sse4_1', 'sse4_2', 'avx', 'avx2')


def text(path, default=''):
    try:
        return path.read_text(errors='replace').strip()
    except (OSError, ValueError):
        return default


def lspci_output():
    try:
        return subprocess.run([LSPCI, '-nn'], stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=1.5, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ''


def chwd_ids():
    return {x.lower() for x in re.findall(r'(?i)(?:10de:)?([0-9a-f]{4})', text(NOUVEAU_IDS))}


def gpus():
    known = chwd_ids()
    result = []
    for line in lspci_output().splitlines():
        if not re.search(r'(?i)(VGA compatible controller|3D controller|Display controller)', line):
            continue
        ids = re.search(r'\[([0-9a-f]{4}):([0-9a-f]{4})\]', line, re.I)
        if not ids:
            continue
        vendor, device = ids.group(1).lower(), ids.group(2).lower()
        address = line.split(None, 1)[0]
        description = line.split(': ', 1)[-1].split(' [', 1)[0]
        driver_path = SYS / 'bus/pci/devices' / address / 'driver'
        try:
            driver = driver_path.resolve(strict=True).name
        except OSError:
            driver = ''
        result.append({'name': description[:120], 'vendor_id': vendor, 'device_id': device,
                       'legacy_nouveau': vendor == '10de' and device in known,
                       'driver': driver})
    return result


def cpu_info():
    raw = text(PROC / 'cpuinfo')
    first = raw.split('\n\n', 1)[0]
    fields = {key.strip(): value.strip() for key, value in re.findall(r'^([^:\n]+)\s*:\s*(.*?)\s*$', first, re.M)}
    flags = set(fields.get('flags', '').split())
    model = fields.get('model name') or fields.get('Hardware') or fields.get('Processor') or 'unknown'
    cores = len(re.findall(r'^processor\s*:', raw, re.M)) or os.cpu_count() or 0
    return {'model': model[:120], 'cores': cores,
            'missing_instruction_sets': [feature for feature in FEATURES if feature not in flags]}


def memory_kib(key):
    raw = text(PROC / 'meminfo')
    match = re.search(r'^' + re.escape(key) + r':\s+(\d+)\s+kB', raw, re.M)
    return int(match.group(1)) * 1024 if match else 0


def disks():
    result = []
    block = SYS / 'block'
    try:
        entries = sorted(block.iterdir())
    except OSError:
        return result
    for dev in entries:
        # Ignore partitions; rotational is a property of whole block devices.
        if (dev / 'partition').exists():
            continue
        rotational = text(dev / 'queue/rotational')
        if rotational in ('0', '1'):
            result.append({'kind': 'hdd' if rotational == '1' else 'ssd_or_flash'})
    return result


def controllers():
    # Presence only. Never read MAC addresses or network interface names.
    net = SYS / 'class/net'
    try:
        wlan = any(p.name.startswith(('wl', 'wlan')) for p in net.iterdir())
    except OSError:
        wlan = False
    try:
        bluetooth = (SYS / 'class/bluetooth').is_dir() and any((SYS / 'class/bluetooth').iterdir())
    except OSError:
        bluetooth = False
    return {'wifi': wlan, 'bluetooth': bluetooth}


def software_renderer():
    paths = [HYPR_LOG] if HYPR_LOG else []
    runtime = os.environ.get('XDG_RUNTIME_DIR', '')
    signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
    if runtime and signature and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', signature):
        paths.append(Path(runtime) / 'hypr' / signature / 'hyprland.log')
    paths.extend((Path.home() / '.local/share/hyprland/hyprland.log',
                  Path.home() / '.local/state/hyprland/hyprland.log'))
    log = ''
    for path in paths:
        if not path:
            continue
        try:
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 1024 * 1024))
                log += stream.read(1024 * 1024).decode('utf-8', 'replace').lower()
        except OSError:
            continue
    if 'llvmpipe' in log:
        return 'llvmpipe'
    if 'softpipe' in log:
        return 'softpipe'
    # A virtual GPU alone does not prove 3D is unavailable; report separately.
    return ''


def build_report():
    cpu = cpu_info()
    memory = memory_kib('MemTotal')
    swap = memory_kib('SwapTotal')
    gpu_list = gpus()
    renderer = software_renderer()
    recommendations = []
    reasons = []
    if any(g['legacy_nouveau'] for g in gpu_list):
        reasons.append('legacy_gpu')
    if renderer:
        reasons.append('software_renderer')
    if memory and memory < 3 * 1024**3:
        reasons.append('low_ram')
    if 'sse4_1' in cpu['missing_instruction_sets']:
        reasons.append('no_sse4_1')
    if reasons:
        recommendations.append({'id': 'lite_mode', 'reasons': reasons})
    if 'sse4_1' in cpu['missing_instruction_sets'] or 'sse4_2' in cpu['missing_instruction_sets']:
        recommendations.append({'id': 'x86_64_v1_packages', 'reasons': ['older_cpu']})
    if memory and memory < 3 * 1024**3:
        recommendations.append({'id': 'low_ram', 'reasons': ['low_ram']})
    try:
        battery = any(p.name.startswith('BAT') for p in (SYS / 'class/power_supply').iterdir())
    except OSError:
        battery = False
    return {'cpu': cpu, 'memory_bytes': memory, 'swap_bytes': swap, 'gpus': gpu_list,
            'renderer': renderer, 'disks': disks(), 'battery': battery,
            'controllers': controllers(), 'recommendations': recommendations}


if __name__ == '__main__':
    print(json.dumps(build_report(), ensure_ascii=False, sort_keys=True))
