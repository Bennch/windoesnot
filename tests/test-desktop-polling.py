#!/usr/bin/env python3
"""Static regression checks for desktop polling cost and panel visibility."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"

# Explicitly reviewed boundaries for this static command audit. Each entry
# explains why it is not an unbounded subprocess call and is kept in test code
# so a future audit does not silently broaden the exclusions.
COMMAND_AUDIT_EXCEPTIONS = {
    "UPower QML API": "UPower.displayDevice/onBattery are Quickshell D-Bus properties, not QML Process launches.",
    "MPRIS QML API": "Media controls use Quickshell.Services.Mpris, not a playerctl subprocess.",
    "Bluetooth scanner": "bt_scan.py checks /sys/class/bluetooth, runs a finite 30 s scan, and its QML owner has a 35 s process-group deadline.",
    "Python command helpers": "system_tools.command/query (60 s), snapshots.run (120 s), migrate.command (20 s), and gpu_status.run (4 s) centralize subprocess deadlines.",
    "HTTP requests": "curl callers are accepted only when their command includes --max-time or is inside windoesnot-bounded.",
    "Snappy C capture": "The vendored renderer launches one grim/timeout process group at a time; coreutils timeout kills it after 8 s.",
    "Nautilus application launch": "User-selected file-manager launches intentionally start a GUI application; they are not polling/query Process calls.",
}

PYTHON_TIMEOUT_HELPERS = {
    "desktop/config/quickshell/default/bt_scan.py": ("/sys/class/bluetooth", "time.time() - start_time < 30", "start_new_session=True"),
    "desktop/lib/windoesnot/system_tools.py": ("def command(*args, allowed=(0,), timeout=60)", "def query(*args, allowed=(0,), timeout=60)"),
    "desktop/lib/windoesnot/snapshots.py": ("timeout=120", "timeout=5"),
    "desktop/lib/windoesnot/migrate.py": ("kwargs.setdefault('timeout', 20)", "timeout=20"),
    "desktop/config/quickshell/default/widgets/gpu_status.py": ("def run(cmd, timeout=4)", "timeout=timeout"),
    "desktop/config/hypr/lua/bin/hypr_bridge.py": ("capture_output=True, timeout=5"),
    "desktop/config/hyprdesk/hyprdesk.py": ("capture_output=True, timeout=5"),
    "iso/boot_environment.py": ("timeout=15",),
    "iso/software/repository.py": ("'--max-time', '600'", "timeout=620"),
}


def timer_blocks(text):
    """Yield (line, body) for Timer blocks, respecting QML strings/comments."""
    for match in re.finditer(r"\bTimer\s*\{", text):
        start = match.end() - 1
        depth = 0
        quote = None
        escaped = False
        line_comment = False
        block_comment = False
        i = start
        while i < len(text):
            ch = text[i]
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if line_comment:
                if ch == "\n":
                    line_comment = False
            elif block_comment:
                if ch == "*" and nxt == "/":
                    block_comment = False
                    i += 1
            elif quote:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    quote = None
            elif ch == "/" and nxt == "/":
                line_comment = True
                i += 1
            elif ch == "/" and nxt == "*":
                block_comment = True
                i += 1
            elif ch in "\"'`":
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    yield text.count("\n", 0, match.start()) + 1, text[start + 1:i]
                    break
            i += 1


class DesktopPollingTests(unittest.TestCase):
    def test_hot_polling_changes_are_visible_and_bounded(self):
        bt = (DESKTOP / "config/quickshell/default/widgets/BluetoothPanel.qml").read_text()
        bt_timers = list(timer_blocks(bt))
        poll_timer = next(body for _, body in bt_timers if "updateBluetoothState()" in body)
        self.assertRegex(poll_timer, r"interval\s*:\s*10000\b")
        self.assertRegex(poll_timer, r"running\s*:\s*bluetoothPanel\.windowVisible\s*&&\s*bluetoothPanel\.bluetoothControllerAvailable")
        self.assertNotIn("Component.onCompleted", bt)
        self.assertIn("onWindowVisibleChanged", bt)
        self.assertRegex(bt, r"if\s*\(available\s*&&\s*!getAllDevicesProc\.running\)\s*getAllDevicesProc\.running\s*=\s*true")
        self.assertIn('"windoesnot-bounded", "6", "bash", "-c", "test -d /sys/class/bluetooth && bluetoothctl show"', bt)
        scan_timer = next(body for _, body in bt_timers if "getAllDevicesProc.running = true" in body and "interval: 10000" in body)
        self.assertRegex(scan_timer, r"interval\s*:\s*10000\b")
        self.assertRegex(scan_timer, r"running\s*:\s*bluetoothPanel\.windowVisible\s*&&\s*bluetoothPanel\.bluetoothControllerAvailable")

        bar = (DESKTOP / "config/quickshell/default/TopNotificationBar.qml").read_text()
        self.assertIn('if ((eventName === "openwindow" || eventName === "closewindow") && !checkSwayncVisibilityProc.running)', bar)
        bar_timers = list(timer_blocks(bar))
        self.assertTrue(any("checkNotificationsProc.running = false" in body for _, body in bar_timers))
        self.assertIn('["windoesnot-bounded", "8", "hyprctl", "-j", "clients"]', bar)
        shell = (DESKTOP / "config/quickshell/default/shell.qml").read_text()
        self.assertIn('["windoesnot-bounded", "8", "hyprctl", "-j", "clients"]', shell)
        self.assertNotIn('"windoesnot-hyprctl", "clients", "-j"', shell)
        self.assertIn('function onRawEvent(ev)', shell)
        self.assertIn('hyprlandWindowRefreshTimer.restart()', shell)
        self.assertRegex(shell, r'interval: 100\s+repeat: false\s+onTriggered: if \(!hyprlandWindowProc\.running\) hyprlandWindowProc\.running = true')

        snap = (DESKTOP / "config/quickshell/default/SnapManager.qml").read_text()
        self.assertNotRegex(snap, r"windoesnot-hyprctl\s+(?:-j\s+)?(?:clients|monitors|activewindow|cursorpos)")
        overview = (DESKTOP / "config/quickshell/overview/services/HyprlandData.qml").read_text()
        self.assertNotIn('["windoesnot-hyprctl", "clients", "-j"]', overview)
        self.assertIn('["windoesnot-bounded", "8", "hyprctl", "-j", "clients"]', overview)

    def test_audited_qml_process_commands_are_bounded(self):
        audited = re.compile(r"\b(?:bluetoothctl|nmcli|upower|powerprofilesctl|brightnessctl|ddcutil|wpctl|pactl|playerctl|systemctl|hyprctl|windoesnot-hyprctl|swaync-client|grim|nautilus|udisks(?:ctl)?|curl|wget|lspci|lsblk)\b", re.I)
        unbounded = []
        launches = 0
        for path in DESKTOP.rglob("*.qml"):
            lines = path.read_text(errors="replace").splitlines()
            for index, line in enumerate(lines):
                context = " ".join(lines[index:min(index + 6, len(lines))])
                if audited.search(context) and re.search(r"\b(?:command|\.command)\s*(?:=|:)", line):
                    launches += 1
                    if "windoesnot-bounded" not in context and "--max-time" not in context and "timeout " not in context:
                        unbounded.append(f"{path.relative_to(ROOT)}:{index + 1}: {line.strip()}")
        self.assertEqual(unbounded, [], "Audited QML Process commands need a deadline or an explicit transport timeout")
        self.assertGreater(launches, 30)

    def test_poll_processes_have_one_possible_instance(self):
        cases = {
            "BluetoothPanel.qml": ("getBluetoothPowerProc", "getAllDevicesProc"),
            "NetworkPanel.qml": ("getWifiStatusProc", "getCurrentConnectionProc", "getActiveWifiProc", "getAvailableNetworksProc"),
            "AudioPanel.qml": ("getDefaultSinkProc", "getVolumeProc", "getMuteStatusProc", "getOutputDevicesProc", "getAppStreamsProc"),
            "TopNotificationBar.qml": ("checkNotificationsProc", "checkSwayncVisibilityProc"),
            "SnapManager.qml": ("activeWindowProc", "snapGroupQueryProc"),
            "shell.qml": ("hyprlandWindowProc", "volumeCheckProc"),
        }
        for filename, process_ids in cases.items():
            path = next(DESKTOP.rglob(filename))
            source = path.read_text()
            for process_id in process_ids:
                guarded = rf"if\s*\([^)]*!{process_id}\.running[^)]*\)\s*\{{?\s*{process_id}\.running\s*=\s*true"
                self.assertRegex(source, guarded,
                                 f"{path.relative_to(ROOT)} {process_id}: simultaneous maximum must stay 1")

    def test_static_audit_exceptions_are_explicit(self):
        self.assertEqual(set(COMMAND_AUDIT_EXCEPTIONS), {
            "UPower QML API", "MPRIS QML API", "Bluetooth scanner", "Python command helpers", "HTTP requests",
            "Snappy C capture", "Nautilus application launch"})
        self.assertTrue(all(reason.strip() for reason in COMMAND_AUDIT_EXCEPTIONS.values()))
        renderer = (ROOT / "desktop/vendor/snappy-switcher/src/render.c").read_text()
        self.assertIn("#define MAX_CAPTURE_JOBS 1", renderer)
        self.assertIn('execlp("timeout", "timeout", "--kill-after=1", "8", "grim"', renderer)
        wrapper = (ROOT / "desktop/vendor/snappy-switcher/scripts/snappy-wrapper.sh").read_text()
        self.assertIn("timeout --kill-after=1 3 hyprctl monitors", wrapper)

    def test_python_external_command_timeout_helpers_are_present(self):
        audited = re.compile(r"\b(?:bluetoothctl|nmcli|upower|powerprofilesctl|brightnessctl|ddcutil|wpctl|pactl|playerctl|systemctl|hyprctl|windoesnot-hyprctl|swaync-client|grim|nautilus|udisks(?:ctl)?|curl|wget|lspci|lsblk)\b", re.I)
        subprocess_call = re.compile(r"subprocess\.(?:run|check_output|Popen)\s*\(")
        unchecked = []
        seen = set()
        for base in (DESKTOP, ROOT / "iso"):
            for path in base.rglob("*.py"):
                rel = path.relative_to(ROOT).as_posix()
                lines = path.read_text(errors="replace").splitlines()
                for i, line in enumerate(lines):
                    if not subprocess_call.search(line):
                        continue
                    call = "\n".join(lines[i:min(i + 4, len(lines))])
                    snippet = "\n".join(lines[i:min(i + 12, len(lines))])
                    if not audited.search(call):
                        continue
                    seen.add(rel)
                    if "timeout=" not in snippet and "--max-time" not in snippet and rel not in PYTHON_TIMEOUT_HELPERS:
                        unchecked.append(f"{rel}:{i + 1}")
        self.assertEqual(unchecked, [], "Python calls to audited command classes need subprocess timeout or bounded helper")
        for rel, markers in PYTHON_TIMEOUT_HELPERS.items():
            source = (ROOT / rel).read_text(errors="replace")
            self.assertTrue(all(marker in source for marker in markers), f"Missing timeout/precheck contract in {rel}")
        self.assertGreater(len(seen), 4)

    def test_short_running_timers_are_reported(self):
        found = []
        for path in DESKTOP.rglob("*.qml"):
            text = path.read_text(errors="replace")
            for line, body in timer_blocks(text):
                interval = re.search(r"\binterval\s*:\s*([^\n;]+)", body)
                running = re.search(r"\brunning\s*:\s*([^\n;]+)", body)
                repeat = re.search(r"\brepeat\s*:\s*true\b", body)
                if interval and running:
                    value = re.fullmatch(r"\s*(\d+)\s*", interval.group(1))
                    if value and int(value.group(1)) < 5000:
                        found.append((path.relative_to(ROOT), line, interval.group(1).strip(), running.group(1).strip(), bool(repeat)))
        for path, line, interval, running, repeat in found:
            print(f"{path}:{line}: interval={interval}ms running={running!r} repeat={repeat}")
        self.assertTrue(found, "Expected a visible inventory of short running timers")


if __name__ == "__main__":
    unittest.main(verbosity=2)
