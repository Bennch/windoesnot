#!/usr/bin/env python3
"""Open every taskbar panel in turn and check its placement.

For each panel the window geometry is sampled while it appears. The check fails when
  * the window moves or resizes after it first became visible (a visible "jump"), or
  * its bottom edge is not flush with the top of the taskbar, or
  * it sticks out of its monitor.

Run it inside a graphical WinDoesNot session (host, live ISO or installed VM):
    tools/verify-popup-placement.py [--panels battery,weather,...] [--verbose]
Panels are opened with `qs ipc call windoesnot-panels toggle <name>`.
"""
import argparse
import json
import subprocess
import sys
import time

TITLES = {
    "calendar": "quickshell-calendar", "audio": "quickshell-audio", "bluetooth": "quickshell-bluetooth",
    "battery": "quickshell-battery", "graphics": "quickshell-graphics", "network": "quickshell-network",
    "nearby": "quickshell-nearby", "weather": "quickshell-weather", "docker": "quickshell-docker",
    "ollama": "quickshell-ollama", "start": "quickshell-startmenu",
    "settings": "quickshell-settings", "search": "quickshell-search",
}
# Panels whose content stays invisible until they have been moved over their taskbar icon:
# one geometry change in the first 0.4 s is allowed (it is not visible to the user).
HIDDEN_MOVE = {"weather"}
# Panels that are allowed to float free of the taskbar edge (they are not anchored to it).
FREE_BOTTOM = {"search"}


def hypr(*args):
    return json.loads(subprocess.check_output(["hyprctl", *args, "-j"], timeout=5))


def ipc(*args):
    return subprocess.run(["qs", "ipc", "-c", "default", "call", "windoesnot-panels", *args],
                          capture_output=True, text=True, timeout=10).stdout.strip()


def taskbar(monitors):
    """Return (monitor, top of the taskbar layer) for the monitor carrying the Quickshell bar."""
    layers = hypr("layers")
    for name, data in layers.items():
        for items in data.get("levels", {}).values():
            for item in items:
                if item.get("namespace") == "quickshell" and item.get("h", 999) <= 100 and item.get("w", 0) > 400:
                    mon = next(m for m in monitors if m["name"] == name)
                    return mon, item["y"]
    raise SystemExit("verify-popup-placement: no taskbar layer found")


def find(title):
    for client in hypr("clients"):
        if client.get("title") == title:
            return (client["at"][0], client["at"][1], client["size"][0], client["size"][1])
    return None


def park_cursor(mon, bar_top):
    """A click on the taskbar leaves the pointer on the bar's monitor; new windows map there."""
    x, y = mon["x"] + mon["width"] // 2, bar_top + 20
    subprocess.run(["windoesnot-hyprctl", "dispatch", "movecursor", str(x), str(y)],
                   capture_output=True, timeout=5)


def check(name, bar_top, mon, verbose):
    title = TITLES[name]
    ipc("closeAll")
    park_cursor(mon, bar_top)
    time.sleep(0.6)
    state = ipc("toggle", name)
    if state != "open":
        return [f"{name}: IPC answered {state!r}"], []
    samples, first = [], None
    start = time.time()
    while time.time() - start < 3.0:
        geometry = find(title)
        if geometry and (not samples or samples[-1][1] != geometry):
            samples.append((round(time.time() - start, 2), geometry))
        time.sleep(0.025)
    ipc("closeAll")
    problems = []
    if not samples:
        return [f"{name}: window never appeared"], samples
    final = samples[-1][1]
    # Ignore the very first sample of a window that appears already correct.
    changes = samples[1:]
    if name in HIDDEN_MOVE:
        changes = [item for item in changes if item[0] > 0.4]
    if changes:
        problems.append(f"{name}: geometry changed {len(changes)}x after appearing: " +
                        " -> ".join(f"{g[0]},{g[1]} {g[2]}x{g[3]}" for _, g in samples))
    bottom = final[1] + final[3]
    if name not in FREE_BOTTOM and abs(bottom - bar_top) > 1:
        problems.append(f"{name}: bottom edge {bottom} but taskbar top is {bar_top} ({bar_top - bottom:+d})")
    mon_right, mon_bottom = mon["x"] + mon["width"], mon["y"] + mon["height"]
    if final[0] < mon["x"] or final[1] < mon["y"] or final[0] + final[2] > mon_right or bottom > mon_bottom:
        problems.append(f"{name}: leaves the monitor ({final} vs {mon['x']},{mon['y']} {mon['width']}x{mon['height']})")
    if verbose:
        print(f"  {name}: {len(samples)} geometry state(s), final {final}")
    return problems, samples


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--panels", default=",".join(TITLES))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    monitors = hypr("monitors")
    mon, bar_top = taskbar(monitors)
    print(f"monitor {mon['name']} {mon['width']}x{mon['height']} at {mon['x']},{mon['y']}; taskbar top {bar_top}")
    failures = []
    for name in args.panels.split(","):
        if name not in TITLES:
            raise SystemExit(f"unknown panel {name}")
        problems, _ = check(name, bar_top, mon, args.verbose)
        status = "FAIL" if problems else "ok"
        print(f"{status:4} {name}")
        failures.extend(problems)
    for problem in failures:
        print("  -", problem)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
