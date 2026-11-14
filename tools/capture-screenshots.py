#!/usr/bin/env python3
"""Capture repeatable WinDoesNot screenshots from an already-running VM.

This script never starts or stops a VM. UI clicks are sent through QMP via
tools/vmctl.py; guest commands use the QEMU guest agent.
"""
from __future__ import annotations

import shutil
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

# Settings navigation uses the shell's IPC, so the selected page is independent
# of font metrics, translations, and input-device coordinate mapping.
SCENES = [
    {"id": "desktop", "label": "Empty desktop", "kind": "desktop"},
    {"id": "start-menu", "label": "Start menu", "kind": "shortcut", "key": "meta-r"},
    {"id": "file-manager", "label": "File manager", "kind": "launch", "command": ["/usr/bin/nautilus"]},
    {"id": "settings-desktop", "label": "Settings / Desktop", "kind": "settings", "category": "desktop"},
    {"id": "settings-background", "label": "Settings / Background", "kind": "settings", "category": "background"},
    {"id": "settings-appearance", "label": "Settings / Appearance", "kind": "settings", "category": "appearance"},
    {"id": "settings-taskbar-start", "label": "Settings / Taskbar and Start menu", "kind": "settings", "category": "alignment"},
    {"id": "settings-input-language-time", "label": "Settings / Input, language and time", "kind": "settings", "category": "input"},
    {"id": "settings-battery", "label": "Settings / Battery", "kind": "settings", "category": "power"},
    {"id": "settings-apps", "label": "Settings / Apps", "kind": "settings", "category": "apps"},
    {"id": "settings-maintenance", "label": "Settings / Maintenance", "kind": "settings", "category": "maintenance", "section": 1},
    {"id": "settings-backups", "label": "Settings / Backups", "kind": "settings", "category": "backups"},
    {"id": "settings-updates", "label": "Settings / Updates", "kind": "settings", "category": "updates"},
    {"id": "store", "label": "Store home", "kind": "launch", "command": ["/usr/bin/windoesnot-store"]},
    {"id": "volume-popup", "label": "Volume popup", "kind": "volume"},
    {"id": "network-popup", "label": "Network popup", "kind": "ipc", "handler": "network"},
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
    session = ('entry=$(getent passwd "${WINDOESNOT_CAPTURE_USER:-liveuser}" || getent passwd liveuser || getent passwd vmtest || getent passwd "$(ls /home | head -n1)") || exit 1; '
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
    user = ('entry=$(getent passwd "${WINDOESNOT_CAPTURE_USER:-liveuser}" || getent passwd liveuser || getent passwd vmtest || getent passwd "$(ls /home | head -n1)") || exit 1; '
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
    # The QEMU device must start at the target mode. Runtime changes leave
    # Hyprland's generated window geometry stale until its monitor watcher runs.
    raw = guest(vm_name, "hyprctl monitors -j", dry_run)
    if not dry_run:
        monitors = json.loads(raw)
        monitor = next((m for m in monitors if m.get("name") == "Virtual-1"), None)
        if not monitor or monitor.get("width") != 1920 or monitor.get("height") != 1080:
            raise RuntimeError(f"Virtual-1 must start at 1920x1080; got {monitor}")
    # The guest's HMP mouse mode makes absolute QMP clicks map correctly.
    run_vmctl(vm_name, "hmp", "mouse_set", "4", dry_run=dry_run)


def capture(vm_name: str, output: Path, scene: dict, dry_run: bool) -> None:
    guest_path = f"/tmp/windoesnot-capture-{scene['id']}.png"
    cmd = "grim " + shlex.quote(guest_path)
    if scene["kind"] == "volume":
        # The on-screen volume display hides itself after a moment: show it again right before the shot.
        cmd = ipc_call("windoesnot-capture", "volume") + "; sleep 2.5; " + cmd
    guest(vm_name, cmd, dry_run)
    if dry_run:
        run_vmctl(vm_name, "pull", guest_path, f"capture-{scene['id']}.png", dry_run=True)
        return
    pulled = run_vmctl(vm_name, "pull", guest_path,
                       f"capture-{scene['id']}.png")
    source = Path(pulled)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(output))
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
               "| while read -r address; do hyprctl dispatch \"hl.dsp.window.close({window=\\\"address:$address\\\"})\"; done")
    guest(vm_name, cleanup, dry_run)
    if kind == "desktop":
        return
    if kind == "shortcut":
        press(vm_name, scene["key"], dry_run)
        if not dry_run:
            time.sleep(1.5)
    elif kind == "click":
        for x, y in scene["clicks"]:
            click(vm_name, x, y, dry_run)
    elif kind == "launch":
        command = shlex.join(scene["command"])
        guest(vm_name, "setsid -f " + command + " >/tmp/windoesnot-capture-app.log 2>&1", dry_run)
        # GTK apps take several seconds on a software-rendered VM: wait for their window.
        wait = ("i=0; while [ $i -lt 60 ]; do n=$(hyprctl -j clients | python3 -c 'import json,sys; "
                "print(sum(1 for x in json.load(sys.stdin) if not x.get(\"class\", \"\").lower().startswith(\"quickshell\")))'); "
                "[ \"$n\" -gt 0 ] && break; sleep 0.5; i=$((i+1)); done; sleep 3")
        guest(vm_name, wait, dry_run)
    elif kind == "settings":
        press(vm_name, "meta-i", dry_run)
        if not dry_run:
            time.sleep(1.5)
        guest(vm_name, ipc_call("windoesnot-settings", "setCategory", scene["category"]), dry_run)
        if "section" in scene:
            if not dry_run:
                time.sleep(2)
            guest(vm_name, ipc_call("windoesnot-settings", "setSection", str(scene["section"])), dry_run)
        if not dry_run:
            time.sleep(2)
    elif kind == "volume":
        guest(vm_name, ipc_call("windoesnot-capture", "volume"), dry_run)
    elif kind == "ipc":
        guest(vm_name, ipc_call("windoesnot-capture", scene["handler"]), dry_run)
    else:
        raise RuntimeError(f"Unknown scene kind: {kind}")



GLOBAL_SHORTCUTS = {"meta-r": "quickshell:toggle-startmenu", "meta-i": "quickshell:show-settings"}


def ipc_call(target: str, method: str, *args: str) -> str:
    entry = 'entry=$(getent passwd "${WINDOESNOT_CAPTURE_USER:-liveuser}" || getent passwd liveuser || getent passwd vmtest || getent passwd "$(ls /home | head -n1)") || exit 1; IFS=: read -r name _ uid _ _ home _ <<<"$entry"; '
    quoted = " ".join(shlex.quote(value) for value in args)
    return entry + 'quickshell ipc --path "$home/.config/quickshell/default/shell.qml" call ' + shlex.quote(target) + " " + shlex.quote(method) + (" " + quoted if quoted else "")


def press(vm_name, key, dry_run):
    """Headless GL VMs do not always deliver synthetic key presses to Hyprland binds; use the global shortcut directly."""
    name = GLOBAL_SHORTCUTS.get(key)
    if name:
        guest(vm_name, "hyprctl dispatch 'hl.dsp.global(\"" + name + "\")'", dry_run)
    else:
        run_vmctl(vm_name, "hmp", "sendkey", key, "10", dry_run=dry_run)


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
