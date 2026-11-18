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
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ("de", "en")
THEMES = ("dark", "light")
CAPTURE_USER = None

# Settings navigation uses the shell's IPC, so the selected page is independent
# of font metrics, translations, and input-device coordinate mapping.
SCENES = [
    {"id": "shortcuts-overlay", "label": "Keyboard shortcuts", "kind": "ipc", "handler": "shortcuts", "target": "windoesnot-welcome"},
    {"id": "looks", "label": "Settings / Looks", "kind": "settings", "category": "appearance"},
    {"id": "welcome", "label": "Welcome checklist", "kind": "welcome"},
    {"id": "kernel", "label": "Settings / Kernel", "kind": "settings", "category": "maintenance", "section": 2},
    {"id": "media-check", "label": "Settings / Media formats", "kind": "settings", "category": "maintenance", "section": 1},
    {"id": "apps-permissions", "label": "Settings / Flatpak permissions", "kind": "settings", "category": "apps"},
    {"id": "power", "label": "Settings / Power", "kind": "settings", "category": "power"},
    {"id": "updates", "label": "Settings / Updates", "kind": "settings", "category": "updates"},
    {"id": "calendar", "label": "Calendar", "kind": "panel", "handler": "calendar"},
    {"id": "windows-programs", "label": "Windows programs helper", "kind": "launch", "command": ["windoesnot-windows-program"], "localized": True},
    {"id": "snap-layouts", "label": "Snap layouts (floating mode)", "kind": "snap"},
    {"id": "weather", "label": "Weather", "kind": "panel", "handler": "weather"},
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
    session = ((('WINDOESNOT_CAPTURE_USER=' + shlex.quote(CAPTURE_USER) + '; ') if CAPTURE_USER else '') + 'entry=$(getent passwd "${WINDOESNOT_CAPTURE_USER:-liveuser}" || getent passwd liveuser || getent passwd vmtest || getent passwd "$(ls /home | head -n1)") || exit 1; '
               'IFS=: read -r name _ uid _ _ home _ <<<"$entry"; '
               'sig=$(find "/run/user/$uid/hypr" -mindepth 1 -maxdepth 1 -type d '
               '-printf "%f\\n" | head -n1); '
               '[ -n "$sig" ] || { echo "Hyprland session not found for $name" >&2; exit 1; }; '
               'runuser -u "$name" -- env XDG_RUNTIME_DIR="/run/user/$uid" '
               'WAYLAND_DISPLAY=wayland-1 HYPRLAND_INSTANCE_SIGNATURE="$sig" WINDOESNOT_CAPTURE_USER="$name" '
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


def move_pointer(vm_name: str, x: int, y: int, dry_run: bool) -> None:
    if dry_run:
        print(f"    QMP pointer move to {x},{y}")
        return
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(15)
        connection.connect(str(ROOT / "vm" / vm_name / "qmp.sock"))
        stream = connection.makefile("rwb", buffering=0)
        stream.readline()
        for payload in ({"execute": "qmp_capabilities"}, {"execute": "input-send-event", "arguments": {
                "events": [{"type": "abs", "data": {"axis": "x", "value": round(x * 32767 / 1920)}},
                           {"type": "abs", "data": {"axis": "y", "value": round(y * 32767 / 1080)}}]}}):
            stream.write(json.dumps(payload).encode() + b"\n")
            while True:
                response = json.loads(stream.readline())
                if "error" in response:
                    raise RuntimeError(f"QMP pointer: {response['error']}")
                if "return" in response:
                    break


def set_display(vm_name: str, dry_run: bool) -> None:
    # The QEMU device must start at the target mode. Runtime changes leave
    # Hyprland's generated window geometry stale until its monitor watcher runs.
    raw = guest(vm_name, "hyprctl monitors -j", dry_run)
    if not dry_run:
        monitors = json.loads(raw)
        monitor = next((m for m in monitors if m.get("name") == "Virtual-1"), None)
        if not monitor or monitor.get("width") != 1920 or monitor.get("height") != 1080:
            raise RuntimeError(f"Virtual-1 must start at 1920x1080; got {monitor}")


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
        if scene.get("localized"):
            lang = scene["language"]
            command = f"env LANGUAGE={lang} LANG={lang}_{'DE' if lang == 'de' else 'US'}.UTF-8 " + command
        pid = guest(vm_name, "setsid " + command + " >/tmp/windoesnot-capture-app.log 2>&1 </dev/null & echo $!", dry_run)
        if not dry_run:
            if not pid.strip().isdigit():
                raise RuntimeError(f"Invalid launched process ID: {pid!r}")
            scene["capture_pid"] = int(pid.strip())
        # GTK apps take several seconds on a software-rendered VM: wait for their window.
        wait = ("i=0; while [ $i -lt 60 ]; do n=$(hyprctl -j clients | python3 -c 'import json,sys; "
                "print(sum(1 for x in json.load(sys.stdin) if not x.get(\"class\", \"\").lower().startswith(\"quickshell\")))'); "
                "[ \"$n\" -gt 0 ] && break; sleep 0.5; i=$((i+1)); done; sleep 3")
        guest(vm_name, wait, dry_run)
        if scene.get("localized"):
            click(vm_name, 900, 300, dry_run)
            guest(vm_name, 'windoesnot-hyprctl dispatch togglefloating; '
                  'windoesnot-hyprctl dispatch resizewindowpixel "exact 800 550"; '
                  'windoesnot-hyprctl dispatch movewindowpixel "exact 560 220"', dry_run)
            if not dry_run:
                time.sleep(1)
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
        guest(vm_name, ipc_call(scene.get("target", "windoesnot-capture"), scene["handler"]), dry_run)
        if not dry_run:
            time.sleep(1)
    elif kind == "panel":
        guest(vm_name, ipc_call("windoesnot-panels", "toggle", scene["handler"]), dry_run)
        if not dry_run:
            time.sleep(1)
    elif kind == "welcome":
        # Only for a disposable guest: the first-start notice otherwise runs once.
        guest(vm_name, 'rm -f "$HOME/.local/state/windoesnot/setup-notice-shown"; '
              'setsid -f windoesnot-setup-notice >/tmp/windoesnot-capture-welcome.log 2>&1', dry_run)
        if not dry_run:
            time.sleep(5)
    elif kind == "snap":
        lang = scene["language"]
        guest(vm_name, f"setsid -f env LANGUAGE={lang} LANG={lang}_{'DE' if lang == 'de' else 'US'}.UTF-8 nautilus >/tmp/windoesnot-capture-app.log 2>&1", dry_run)
        if not dry_run:
            time.sleep(5)
        click(vm_name, 950, 246, dry_run)
        move_pointer(vm_name, 1332, 246, dry_run)
        guest(vm_name, ipc_call("windoesnot-snap", "hover"), dry_run)
        if not dry_run:
            time.sleep(2)
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


def read_json(vm_name: str, command: str, dry_run: bool, default):
    raw = guest(vm_name, command, dry_run)
    if dry_run:
        return default
    try:
        return json.loads(raw.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid session state: {raw!r}") from exc


def read_panels(vm_name: str, dry_run: bool) -> dict:
    state = read_json(vm_name, ipc_call("windoesnot-panels", "state"), dry_run, {})
    if not isinstance(state, dict):
        raise RuntimeError("Invalid panel state")
    return state


def cleanup_scene(vm_name: str, scene: dict, dry_run: bool) -> None:
    kind = scene["kind"]
    name = (scene.get("handler") if kind == "panel" else
            "network" if kind == "ipc" and scene.get("handler") == "network" else
            "settings" if kind == "settings" else
            "start" if kind == "shortcut" and scene.get("key") == "meta-r" else None)
    if name and (dry_run or read_panels(vm_name, False).get(name)):
        guest(vm_name, ipc_call("windoesnot-panels", "toggle", name), dry_run)
    if kind == "ipc" and scene.get("handler") == "shortcuts":
        if dry_run or read_panels(vm_name, False).get("shortcuts"):
            guest(vm_name, ipc_call("windoesnot-welcome", "closeShortcuts"), dry_run)
    pid = scene.get("capture_pid")
    if pid:
        for client in read_json(vm_name, "windoesnot-hyprctl clients -j", False, []):
            address = client.get("address", "")
            if client.get("pid") == pid and address.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in address[2:]):
                guest(vm_name, "windoesnot-hyprctl dispatch closewindow " + shlex.quote("address:" + address), False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm-name", required=True, help="Existing VM folder name under vm/")
    parser.add_argument("--guest-user", help="User with the guest desktop session")
    parser.add_argument("--output", type=Path, default=ROOT / "out/screenshots")
    parser.add_argument("--scene", action="append", dest="scenes", help="Scene id; repeat to select. Defaults to all.")
    parser.add_argument("--language", choices=LANGUAGES, action="append", dest="languages")
    parser.add_argument("--theme", choices=THEMES, action="append", dest="themes")
    parser.add_argument("--dry-run", action="store_true", help="Print the complete capture plan without contacting a VM")
    args = parser.parse_args()
    global CAPTURE_USER
    CAPTURE_USER = args.guest_user

    scenes = [scene for scene in SCENES if (scene["id"] in args.scenes if args.scenes else
              scene["kind"] not in {"click", "welcome", "snap"} and not scene.get("localized"))]
    unknown = set(args.scenes or ()) - {scene["id"] for scene in SCENES}
    if unknown:
        parser.error("unknown scene id(s): " + ", ".join(sorted(unknown)))
    languages, themes = args.languages or LANGUAGES, args.themes or THEMES
    # Coordinate-driven and first-run scenes cannot be undone safely.
    unsafe = {s["id"] for s in scenes if s["kind"] in {"click", "welcome", "snap"}
              or s.get("localized")}
    if unsafe:
        raise RuntimeError("Scenes require unsafe clicks or persistent state changes: " + ", ".join(sorted(unsafe)))
    set_display(args.vm_name, args.dry_run)
    original = read_state(args.vm_name, args.dry_run)
    panels = read_panels(args.vm_name, args.dry_run)
    if any(panels.values()):
        raise RuntimeError("Open panels may close on focus change; use an empty test session")
    clients = read_json(args.vm_name, "windoesnot-hyprctl clients -j", args.dry_run, [])
    # Existing windows can receive synthetic shortcuts or application activation.
    if clients:
        raise RuntimeError("Open windows may be affected by scene actions; use an empty test session")
    monitors = read_json(args.vm_name, "windoesnot-hyprctl monitors -j", args.dry_run, [])
    focused = next ( (m for m in monitors if m.get("focused")), None)
    print(f"VM={args.vm_name}; output={args.output}; scenes={len(scenes)}; variants={len(languages)*len(themes)}")
    try:
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
                    scene = {**scene, "language": language}
                    destination = args.output / f"{language}-{theme}" / f"{scene['id']}.png"
                    print(f"  {scene['id']}: {destination}")
                    try:
                        prepare_scene(args.vm_name, scene, args.dry_run)
                        capture(args.vm_name, destination, scene, args.dry_run)
                    finally:
                        cleanup_scene(args.vm_name, scene, args.dry_run)
    finally:
        if not args.dry_run:
            try:
                guest(args.vm_name, ipc_command(language=original["language"],
                      theme="dark" if original["dark"] else "light"), False)
            finally:
                if focused:
                    guest(args.vm_name, "windoesnot-hyprctl dispatch focusmonitor " + shlex.quote(str(focused["name"])), False)
                    workspace = focused.get("activeWorkspace", {}).get("id")
                    if isinstance(workspace, int):
                        guest(args.vm_name, "windoesnot-hyprctl dispatch workspace " + str(workspace), False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.SubprocessError, OSError) as error:
        raise SystemExit(f"capture-screenshots: error: {error}")
