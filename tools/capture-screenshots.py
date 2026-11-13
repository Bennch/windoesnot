#!/usr/bin/env python3
"""Capture repeatable WinDoesNot screenshots from an already-running VM.

This script never starts or stops a VM. UI clicks are sent through QMP via
tools/vmctl.py; guest commands use the QEMU guest agent.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ("de", "en")
THEMES = ("dark", "light")

# Coordinates refer to the requested 1920x1080 Virtual-1 output. The settings
# sidebar points are intentionally data: adjust them if the installed image's
# category order/geometry changes. A page failure cannot produce a silent fake.
SCENES = [
    {"id": "desktop", "label": "Empty desktop", "kind": "desktop"},
    {"id": "start-menu", "label": "Start menu", "kind": "shortcut", "key": "meta-r"},
    {"id": "file-manager", "label": "File manager", "kind": "launch", "command": ["/usr/bin/nautilus"]},
    {"id": "settings-desktop", "label": "Settings / Desktop", "kind": "settings", "category": "desktop", "point": (620, 245)},
    {"id": "settings-background", "label": "Settings / Background", "kind": "settings", "category": "background", "point": (620, 335)},
    {"id": "settings-appearance", "label": "Settings / Appearance", "kind": "settings", "category": "appearance", "point": (620, 380)},
    {"id": "settings-taskbar-start", "label": "Settings / Taskbar and Start menu", "kind": "settings", "category": "alignment", "point": (620, 425)},
    {"id": "settings-input-language-time", "label": "Settings / Input, language and time", "kind": "settings", "category": "input", "point": (620, 470)},
    {"id": "settings-battery", "label": "Settings / Battery", "kind": "settings", "category": "power", "point": (620, 515)},
    {"id": "settings-apps", "label": "Settings / Apps", "kind": "settings", "category": "apps", "point": (620, 560)},
    {"id": "settings-maintenance", "label": "Settings / Maintenance", "kind": "settings", "category": "maintenance", "point": (620, 605)},
    {"id": "settings-backups", "label": "Settings / Backups", "kind": "settings", "category": "backups", "point": (620, 650)},
    {"id": "settings-updates", "label": "Settings / Updates", "kind": "settings", "category": "updates", "point": (620, 695)},
    {"id": "store", "label": "Store home", "kind": "launch", "command": ["/usr/bin/windoesnot-store", "--open-desktop"]},
    {"id": "volume-popup", "label": "Volume popup", "kind": "volume"},
    {"id": "network-popup", "label": "Network popup", "kind": "click", "clicks": [(1815, 1045)]},
    {"id": "task-manager", "label": "Task manager", "kind": "launch", "command": ["/usr/bin/gnome-system-monitor"]},
]


def run_vmctl(vm_name: str, action: str, *args: str, dry_run: bool = False,
              timeout: int = 45) -> str:
    command = [sys.executable, str(ROOT / "tools/vmctl.py"), "--vm-name", vm_name,
               action, *map(str, args)]
    if dry_run:
        print("    $ " + shlex.join(command))
        return ""
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                            timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"vmctl {action} failed ({result.returncode}): "
                           f"{result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def guest(vm_name: str, script: str, dry_run: bool = False) -> str:
    session = ('entry=$(getent passwd vmtest || getent passwd liveuser) || exit 1; '
               'IFS=: read -r name _ uid _ _ home _ <<<"$entry"; '
               'sig=$(find "/run/user/$uid/hypr" -mindepth 1 -maxdepth 1 -type d '
               '-printf "%f\\n" | head -n1); '
               '[ -n "$sig" ] || { echo "Hyprland session not found for $name" >&2; exit 1; }; '
               'runuser -u "$name" -- env XDG_RUNTIME_DIR="/run/user/$uid" '
               'WAYLAND_DISPLAY=wayland-1 HYPRLAND_INSTANCE_SIGNATURE="$sig" '
               '/usr/bin/bash -lc ' + shlex.quote(script))
    return run_vmctl(vm_name, "exec", "/usr/bin/bash", "-lc", session,
                     dry_run=dry_run)


def ipc_command(language: str | None = None, theme: str | None = None,
                state: bool = False) -> str:
    user = ('entry=$(getent passwd vmtest || getent passwd liveuser) || exit 1; '
            'IFS=: read -r name _ uid _ _ home _ <<<"$entry"; ')
    target = '"$home/.config/quickshell/default/shell.qml"'
    calls = []
    if language:
        calls.append("quickshell ipc --path " + target +
                     " call windoesnot-settings setLanguage " + language)
    if theme:
        calls.append("quickshell ipc --path " + target +
                     " call windoesnot-settings setDarkMode " +
                     ("true" if theme == "dark" else "false"))
    if state:
        calls.append("quickshell ipc --path " + target +
                     " call windoesnot-settings state")
    return user + " && ".join(calls)


def read_state(vm_name: str, dry_run: bool) -> dict:
    raw = guest(vm_name, ipc_command(state=True), dry_run)
    if dry_run:
        return {"language": "<verified-at-runtime>", "dark": "<verified-at-runtime>", "loading": False}
    try:
        state = json.loads(raw.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Settings IPC returned invalid state: {raw!r}") from exc
    if state.get("loading"):
        raise RuntimeError("Settings IPC reports loading=true")
    return state


def click(vm_name: str, x: int, y: int, dry_run: bool) -> None:
    run_vmctl(vm_name, "click", str(x), str(y), "1920", "1080", dry_run=dry_run)
    time.sleep(0.7 if not dry_run else 0)


def set_display(vm_name: str, dry_run: bool) -> None:
    script = 'hyprctl eval \'hl.monitor({output="Virtual-1", mode="1920x1080@60", position="0x0", scale=1})\''
    guest(vm_name, script, dry_run)
    if not dry_run:
        time.sleep(1.5)
    # The guest's HMP mouse mode makes absolute QMP clicks map correctly.
    run_vmctl(vm_name, "hmp", "mouse_set", "4", dry_run=dry_run)


def capture(vm_name: str, output: Path, scene: dict, dry_run: bool) -> None:
    guest_path = f"/tmp/windoesnot-capture-{scene['id']}.png"
    cmd = "grim " + shlex.quote(guest_path)
    guest(vm_name, cmd, dry_run)
    if dry_run:
        run_vmctl(vm_name, "pull", guest_path, f"capture-{scene['id']}.png", dry_run=True)
        return
    pulled = run_vmctl(vm_name, "pull", guest_path,
                       f"capture-{scene['id']}.png")
    source = Path(pulled)
    output.parent.mkdir(parents=True, exist_ok=True)
    source.replace(output)
    with output.open("rb") as image:
        header = image.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        output.unlink(missing_ok=True)
        raise RuntimeError(f"{scene['id']}: grim did not produce a PNG")
    width, height = struct.unpack(">II", header[16:24])
    if (width, height) != (1920, 1080):
        output.unlink(missing_ok=True)
        raise RuntimeError(f"{scene['id']}: expected 1920x1080, got {width}x{height}")


def prepare_scene(vm_name: str, scene: dict, dry_run: bool) -> None:
    kind = scene["kind"]
    # Dismiss Quickshell popups left by the previous scene, then close app windows.
    run_vmctl(vm_name, "hmp", "sendkey", "esc", "10", dry_run=dry_run)
    cleanup = ("hyprctl -j clients | python3 -c 'import json,sys; "
               "[print(x[\"address\"]) for x in json.load(sys.stdin) "
               "if not x.get(\"class\", \"\").lower().startswith(\"quickshell\")]' "
               "| while read -r address; do hyprctl dispatch closewindow \"address:$address\"; done")
    guest(vm_name, cleanup, dry_run)
    if kind == "desktop":
        return
    if kind == "shortcut":
        run_vmctl(vm_name, "hmp", "sendkey", scene["key"], "10", dry_run=dry_run)
        if not dry_run:
            time.sleep(1.5)
    elif kind == "click":
        for x, y in scene["clicks"]:
            click(vm_name, x, y, dry_run)
    elif kind == "launch":
        command = shlex.join(scene["command"])
        guest(vm_name, "setsid -f " + command + " >/tmp/windoesnot-capture-app.log 2>&1", dry_run)
        if not dry_run:
            time.sleep(2)
    elif kind == "settings":
        # Existing Super+I global binding opens Settings; then select its category.
        run_vmctl(vm_name, "hmp", "sendkey", "meta-i", "10", dry_run=dry_run)
        if not dry_run:
            time.sleep(1.5)
        x, y = scene["point"]
        click(vm_name, x, y, dry_run)
    elif kind == "volume":
        guest(vm_name, "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 0.02+", dry_run)
        if not dry_run:
            time.sleep(0.8)
    else:
        raise RuntimeError(f"Unknown scene kind: {kind}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm-name", required=True, help="Existing VM folder name under vm/")
    parser.add_argument("--output", type=Path, default=ROOT / "out/screenshots")
    parser.add_argument("--scene", action="append", dest="scenes", help="Scene id; repeat to select. Defaults to all.")
    parser.add_argument("--language", choices=LANGUAGES, action="append", dest="languages")
    parser.add_argument("--theme", choices=THEMES, action="append", dest="themes")
    parser.add_argument("--dry-run", action="store_true", help="Print the complete capture plan without contacting a VM")
    args = parser.parse_args()

    scenes = [scene for scene in SCENES if not args.scenes or scene["id"] in args.scenes]
    unknown = set(args.scenes or ()) - {scene["id"] for scene in SCENES}
    if unknown:
        parser.error("unknown scene id(s): " + ", ".join(sorted(unknown)))
    languages, themes = args.languages or LANGUAGES, args.themes or THEMES
    set_display(args.vm_name, args.dry_run)
    print(f"VM={args.vm_name}; output={args.output}; scenes={len(scenes)}; variants={len(languages)*len(themes)}")
    for language in languages:
        for theme in themes:
            print(f"\n[{language}/{theme}]")
            guest(args.vm_name, ipc_command(language=language, theme=theme), args.dry_run)
            if not args.dry_run:
                time.sleep(1.0)
            state = read_state(args.vm_name, args.dry_run)
            if not args.dry_run and (state.get("language") != language or state.get("dark") != (theme == "dark")):
                raise RuntimeError(f"Preference verification failed for {language}/{theme}: {state}")
            for scene in scenes:
                destination = args.output / f"{language}-{theme}" / f"{scene['id']}.png"
                print(f"  {scene['id']}: {destination}")
                if args.dry_run:
                    print(f"    scene action: {scene['kind']}" + (f" / {scene.get('category')}" if scene.get("category") else ""))
                    prepare_scene(args.vm_name, scene, True)
                    capture(args.vm_name, destination, scene, True)
                    continue
                prepare_scene(args.vm_name, scene, False)
                current = read_state(args.vm_name, False)
                if current.get("language") != language or current.get("dark") != (theme == "dark"):
                    raise RuntimeError(f"Preferences changed before {scene['id']}: {current}")
                capture(args.vm_name, destination, scene, False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.SubprocessError, OSError) as error:
        raise SystemExit(f"capture-screenshots: error: {error}")
