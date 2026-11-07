#!/usr/bin/env python3
"""Performance snapshot of a running WinDoesNot system (host, VM or test laptop).

Measures what a freshly booted, idle desktop costs: RAM, CPU, boot time,
process groups, services. Read-only; prints Markdown and optionally writes JSON,
so runs on different machines and after each optimisation can be compared with
--compare old.json.

  perf-audit.py --label laptop-2012 --seconds 30 --json out/perf/laptop.json
  perf-audit.py --compare out/perf/before.json out/perf/after.json

Run right after login, without touching anything. Start it as the desktop user:
a normal user only sees its own processes in the per-process figures; the totals
(RAM, CPU, load) are always system wide.
"""
import argparse
import collections
import json
import os
import platform
import re
import subprocess
import sys
import time


def run(cmd, timeout=15):
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return done.stdout.strip()
    except Exception:
        return ""


def meminfo():
    values = {}
    with open("/proc/meminfo") as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            values[key] = int(rest.split()[0])  # kB
    total, avail = values["MemTotal"], values["MemAvailable"]
    return {
        "total_mb": round(total / 1024),
        "used_mb": round((total - avail) / 1024),
        "available_mb": round(avail / 1024),
        "cached_mb": round((values.get("Cached", 0) + values.get("Buffers", 0)) / 1024),
        "swap_used_mb": round((values.get("SwapTotal", 0) - values.get("SwapFree", 0)) / 1024),
    }


def cpu_times():
    with open("/proc/stat") as handle:
        fields = [int(x) for x in handle.readline().split()[1:]]
    idle = fields[3] + fields[4]
    return sum(fields), idle


def proc_ticks():
    ticks = {}
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/stat") as handle:
                data = handle.read()
            rest = data[data.rindex(")") + 2:].split()
            ticks[pid] = (int(rest[11]) + int(rest[12]), data[data.index("(") + 1:data.rindex(")")])
        except (OSError, ValueError, IndexError):
            continue
    return ticks


def smaps_pss_kb(pid):
    try:
        with open(f"/proc/{pid}/smaps_rollup") as handle:
            for line in handle:
                if line.startswith("Pss:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return None


def groups():
    """RAM (PSS where readable, else RSS) summed by process name."""
    sums = collections.defaultdict(lambda: [0, 0])
    page = os.sysconf("SC_PAGE_SIZE") // 1024
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/comm") as handle:
                name = handle.read().strip()
            kb = smaps_pss_kb(pid)
            if kb is None:
                with open(f"/proc/{pid}/statm") as handle:
                    kb = int(handle.read().split()[1]) * page
        except (OSError, ValueError, IndexError):
            continue
        sums[name][0] += kb
        sums[name][1] += 1
    rows = [{"name": n, "mb": round(v[0] / 1024, 1), "count": v[1]} for n, v in sums.items()]
    return sorted(rows, key=lambda r: -r["mb"])


def sample_cpu(seconds):
    total0, idle0 = cpu_times()
    ticks0 = proc_ticks()
    time.sleep(seconds)
    total1, idle1 = cpu_times()
    ticks1 = proc_ticks()
    busy = 100.0 * (1 - (idle1 - idle0) / max(1, total1 - total0))
    hz = os.sysconf("SC_CLK_TCK")
    per = collections.defaultdict(float)
    for pid, (t1, name) in ticks1.items():
        t0 = ticks0.get(pid, (t1, name))[0]
        per[name] += 100.0 * (t1 - t0) / hz / seconds
    top = sorted(({"name": n, "cpu_percent": round(v, 2)} for n, v in per.items()), key=lambda r: -r["cpu_percent"])
    return round(busy, 2), top


def boot_time():
    out = run(["systemd-analyze"])
    match = re.search(r"= ([\d.]+)(ms|s|min)(?: ([\d.]+)s)?", out)
    text = out.splitlines()[0] if out else ""
    return {"summary": text}


def collect(label, seconds):
    cpu_name = ""
    with open("/proc/cpuinfo") as handle:
        for line in handle:
            if line.startswith("model name"):
                cpu_name = line.split(":", 1)[1].strip()
                break
    uptime = float(open("/proc/uptime").read().split()[0])
    busy, top_cpu = sample_cpu(seconds)
    return {
        "label": label,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "machine": {"cpu": cpu_name, "cores": os.cpu_count(), "kernel": platform.release(),
                    "gpu": run(["bash", "-c", "lspci | grep -iE 'vga|3d' | cut -d: -f3 | paste -sd';'"])},
        "uptime_s": round(uptime),
        "ram": meminfo(),
        "cpu_idle_busy_percent": busy,
        "sample_seconds": seconds,
        "loadavg": os.getloadavg(),
        "processes": len(list(filter(str.isdigit, os.listdir("/proc")))),
        "boot": boot_time(),
        "services_running": len(run(["systemctl", "list-units", "--type=service", "--state=running", "--no-legend"]).splitlines()),
        "user_services_running": len(run(["systemctl", "--user", "list-units", "--type=service", "--state=running", "--no-legend"]).splitlines()),
        "top_ram": groups()[:15],
        "top_cpu": top_cpu[:10],
        "hyprland": run(["bash", "-c", "pacman -Q hyprland 2>/dev/null"]),
    }


def markdown(d):
    m, r = d["machine"], d["ram"]
    lines = [f"## Performance snapshot: {d['label']}", "",
             f"{d['time']} · {m['cpu']} · {m['cores']} Kerne · {m['gpu']} · Kernel {m['kernel']}", "",
             "| Messwert | Wert |", "|---|---|",
             f"| RAM belegt | {r['used_mb']} MB von {r['total_mb']} MB (Cache {r['cached_mb']} MB, Swap {r['swap_used_mb']} MB) |",
             f"| CPU im Leerlauf | {d['cpu_idle_busy_percent']} % (über {d['sample_seconds']} s) |",
             f"| Load average | {', '.join(f'{x:.2f}' for x in d['loadavg'])} |",
             f"| Prozesse | {d['processes']} |",
             f"| Dienste (System / Benutzer) | {d['services_running']} / {d['user_services_running']} |",
             f"| Uptime bei Messung | {d['uptime_s']} s |",
             f"| Boot | {d['boot']['summary']} |", "",
             "### Größte RAM-Verbraucher (PSS, nach Prozessname)", "", "| Prozess | MB | Anzahl |", "|---|---:|---:|"]
    lines += [f"| {p['name']} | {p['mb']} | {p['count']} |" for p in d["top_ram"]]
    lines += ["", "### CPU im Messzeitraum", "", "| Prozess | % eines Kerns |", "|---|---:|"]
    lines += [f"| {p['name']} | {p['cpu_percent']} |" for p in d["top_cpu"] if p["cpu_percent"] > 0]
    return "\n".join(lines)


def compare(a, b):
    def delta(x, y, unit=""):
        return f"{x}{unit} → {y}{unit} ({y - x:+.1f}{unit})"
    lines = [f"## Vergleich: {a['label']} → {b['label']}", "", "| Messwert | Änderung |", "|---|---|",
             f"| RAM belegt | {delta(a['ram']['used_mb'], b['ram']['used_mb'], ' MB')} |",
             f"| CPU im Leerlauf | {delta(a['cpu_idle_busy_percent'], b['cpu_idle_busy_percent'], ' %')} |",
             f"| Prozesse | {delta(a['processes'], b['processes'])} |",
             f"| Dienste | {delta(a['services_running'], b['services_running'])} |", "",
             "| Prozess | RAM vorher | RAM nachher |", "|---|---:|---:|"]
    before = {p["name"]: p["mb"] for p in a["top_ram"]}
    after = {p["name"]: p["mb"] for p in b["top_ram"]}
    for name in sorted(set(before) | set(after), key=lambda n: -max(before.get(n, 0), after.get(n, 0))):
        lines.append(f"| {name} | {before.get(name, '-')} | {after.get(name, '-')} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default=platform.node())
    parser.add_argument("--seconds", type=int, default=30, help="CPU sampling window")
    parser.add_argument("--json", help="write the raw result here")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()
    if args.compare:
        a, b = (json.load(open(p)) for p in args.compare)
        print(compare(a, b))
        return
    data = collect(args.label, max(2, args.seconds))
    print(markdown(data))
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as handle:
            json.dump(data, handle, indent=2)


if __name__ == "__main__":
    sys.exit(main())
