#!/usr/bin/env python3

import os
import pathlib
import pwd
import select
import signal
import subprocess
import sys
import time
from typing import Dict, Iterable, List, Optional

from evdev import InputDevice, ecodes, list_devices


SUPER_KEYS = {ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def log(message: str) -> None:
    print(message, flush=True)


def list_device_paths() -> List[str]:
    configured = os.environ.get("SUPER_TAP_DEVICE", "").strip()
    if configured:
        return [configured]

    by_id = "/dev/input/by-id"
    if not os.path.isdir(by_id):
        return list_devices()

    paths = []
    for entry in sorted(os.listdir(by_id)):
        if entry.endswith("-event-kbd"):
            paths.append(os.path.join(by_id, entry))
    return paths or list_devices()


def open_devices(paths: Iterable[str]) -> Dict[int, InputDevice]:
    devices: Dict[int, InputDevice] = {}
    for path in paths:
        try:
            device = InputDevice(path)
            devices[device.fd] = device
            log(f"Listening on {path} ({device.name})")
        except OSError as exc:
            log(f"Skipping {path}: {exc}")
    return devices


def find_hypr_instance_signature() -> Optional[str]:
    configured = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "").strip()
    if configured:
        return configured

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if not runtime_dir:
        uid = str(pwd.getpwnam(os.environ["SUPER_TAP_USER"]).pw_uid) if os.environ.get("SUPER_TAP_USER") else str(env_int("SUPER_TAP_UID", os.getuid()))
        runtime_dir = f"/run/user/{uid}"

    hypr_dir = pathlib.Path(runtime_dir) / "hypr"
    if not hypr_dir.is_dir():
        return None

    candidates = []
    for entry in hypr_dir.iterdir():
        socket_path = entry / ".socket.sock"
        if socket_path.exists():
            try:
                candidates.append((socket_path.stat().st_mtime, entry.name))
            except OSError:
                continue

    if not candidates:
        return None

    candidates.sort()
    return candidates[-1][1]


def trigger_startmenu() -> None:
    signature = find_hypr_instance_signature()
    if not signature:
        log("No active Hyprland instance found.")
        return

    uid = str(pwd.getpwnam(os.environ["SUPER_TAP_USER"]).pw_uid) if os.environ.get("SUPER_TAP_USER") else str(env_int("SUPER_TAP_UID", os.getuid()))
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "").strip() or f"/run/user/{uid}"
    command = [
        "/usr/bin/hyprctl", "eval",
        'hl.dispatch(hl.dsp.global("quickshell:toggle-startmenu"))',
    ]
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = runtime_dir
    env["HYPRLAND_INSTANCE_SIGNATURE"] = signature
    if os.geteuid() == 0 and int(uid) != 0:
        command = ["/usr/bin/setpriv", "--reuid", uid, "--regid", str(pwd.getpwuid(int(uid)).pw_gid), "--init-groups", *command]
    subprocess.run(command, check=False, env=env)


def main() -> int:
    timeout_ms = env_int("SUPER_TAP_TIMEOUT_MS", 250)
    devices = open_devices(list_device_paths())
    if not devices:
        log("No keyboard devices found.")
        return 1

    running = True

    def stop_handler(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    super_pressed = False
    combo_used = False
    press_time: Optional[float] = None

    while running:
        readable, _, _ = select.select(list(devices.keys()), [], [], 1.0)
        for fd in readable:
            device = devices.get(fd)
            if device is None:
                continue

            for event in device.read():
                if event.type != ecodes.EV_KEY:
                    continue

                key_event = event
                key_code = key_event.code
                key_value = key_event.value

                if key_code in SUPER_KEYS:
                    if key_value == 1:
                        # Start a new tap candidate on the first Super press.
                        if not super_pressed:
                            super_pressed = True
                            combo_used = False
                            press_time = time.monotonic()
                    elif key_value == 0 and super_pressed:
                        held_ms = 0
                        if press_time is not None:
                            held_ms = int((time.monotonic() - press_time) * 1000)

                        if not combo_used and held_ms <= timeout_ms:
                            trigger_startmenu()

                        super_pressed = False
                        combo_used = False
                        press_time = None
                    continue

                if super_pressed and key_value == 1:
                    combo_used = True

    for device in devices.values():
        device.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
