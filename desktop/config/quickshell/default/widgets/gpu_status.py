#!/usr/bin/env python3
"""Prints one JSON object with live GPU readings for the graphics tray popup.

Source is LACT (`lact cli`), which covers NVIDIA, AMD and Intel the same way.
LACT has no utilisation figure, so that one value is added from nvidia-smi or
sysfs. If the LACT daemon is not running, only that fact is reported and the
popup offers to start it.
"""
import glob
import json
import os
import re
import shutil
import subprocess


def run(cmd, timeout=4):
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return done.returncode, done.stdout
    except Exception:
        return 1, ""


def number(text):
    match = re.search(r"-?\d+(?:\.\d+)?", text or "")
    return float(match.group()) if match else None


def read(path):
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return None


def list_gpus():
    code, out = run(["lact", "cli", "list"])
    if code != 0:
        return None
    gpus = []
    for line in out.splitlines():
        m = re.match(r"(\d+): (\S+) \((.*)\) \[(.*)\]", line)
        if m:
            slot = m.group(2).rsplit("-", 1)[-1].lower()
            gpus.append({"index": int(m.group(1)), "id": slot, "name": m.group(3), "kind": m.group(4)})
    return gpus


def lact_stats(index):
    code, out = run(["lact", "cli", "-g", str(index), "stats"])
    stats = {}
    if code != 0:
        return stats
    for line in out.splitlines():
        key, _, value = line.partition(": ")
        if key == "GPU Clockspeed":
            stats["clockCore"] = number(value)
        elif key == "VRAM Clockspeed":
            stats["clockMem"] = number(value)
        elif key == "Power Usage":
            used, _, limit = value.partition("/")
            stats["power"], stats["powerLimit"] = number(used), number(limit)
        elif key == "Temperatures":
            temps = dict(re.findall(r"([\w ]+?): (-?\d+)", value))
            first = temps.get("GPU") or temps.get("edge") or next(iter(temps.values()), None)
            stats["temp"] = number(first)
            stats["tempHotspot"] = number(temps.get("GPU Hotspot") or temps.get("junction"))
        elif key == "VRAM Usage":
            used, _, total = value.partition("/")
            stats["vramUsed"], stats["vramTotal"] = number(used), number(total)
        elif key == "Fan Speed":
            stats["fanPct"] = number(value.split("%")[0])
            rpm = re.search(r"\((\d+) RPM\)", value)
            stats["fanRpm"] = float(rpm.group(1)) if rpm else None
        elif key == "Throttling":
            stats["throttling"] = value.strip() not in ("No", "")
        elif key == "Fan Control Mode":
            stats["fanMode"] = value.strip()
    return stats


def utilisation():
    """Slot suffix (e.g. 0000:01:00.0) -> percent."""
    result = {}
    if shutil.which("nvidia-smi"):
        _, out = run(["nvidia-smi", "--query-gpu=pci.bus_id,utilization.gpu", "--format=csv,noheader,nounits"])
        for line in out.splitlines():
            bus, _, util = line.partition(",")
            if util.strip():
                result[bus.strip().lower()[-12:]] = number(util)
    for dev in glob.glob("/sys/class/drm/card[0-9]*/device"):
        busy = read(os.path.join(dev, "gpu_busy_percent"))
        if busy:
            result[os.path.basename(os.path.realpath(dev)).lower()[-12:]] = number(busy)
    return result


def processes():
    if not shutil.which("nvidia-smi"):
        return []
    _, out = run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"])
    procs = []
    for line in out.splitlines():
        f = [x.strip() for x in line.split(",")]
        if len(f) >= 3:
            procs.append({"name": read(f"/proc/{f[0]}/comm") or os.path.basename(f[1]), "vram": number(f[2])})
    procs.sort(key=lambda p: -(p["vram"] or 0))
    return procs[:3]


def service():
    _, listing = run(["systemctl", "list-unit-files", "lactd.service", "--no-legend"])
    return "lactd.service" in listing


def main():
    info = {"lact": bool(shutil.which("lact")), "unit": service()}
    gpus = list_gpus() if info["lact"] else None
    if gpus is None:
        print(json.dumps({**info, "running": False, "gpus": [], "processes": []}))
        return
    util = utilisation()
    for gpu in gpus:
        gpu.update(lact_stats(gpu["index"]))
        if gpu["id"] in util:
            gpu["util"] = util[gpu["id"]]
    print(json.dumps({**info, "running": True, "gpus": gpus, "processes": processes()}))


main()
