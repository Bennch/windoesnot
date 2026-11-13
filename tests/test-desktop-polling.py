#!/usr/bin/env python3
"""Static regression checks for desktop polling cost and panel visibility."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"


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
        self.assertRegex(bt, r"if\s*\(available\)\s*getAllDevicesProc\.running\s*=\s*true")
        scan_timer = next(body for _, body in bt_timers if "getAllDevicesProc.running = true" in body and "interval: 10000" in body)
        self.assertRegex(scan_timer, r"interval\s*:\s*10000\b")
        self.assertRegex(scan_timer, r"running\s*:\s*bluetoothPanel\.windowVisible\s*&&\s*bluetoothPanel\.bluetoothControllerAvailable")

        bar = (DESKTOP / "config/quickshell/default/TopNotificationBar.qml").read_text()
        self.assertIn('if (eventName === "openwindow" || eventName === "closewindow")', bar)
        bar_timers = list(timer_blocks(bar))
        self.assertFalse(any("checkSwayncVisibilityProc" in body for _, body in bar_timers))
        self.assertIn('["hyprctl", "-j", "clients"]', bar)
        shell = (DESKTOP / "config/quickshell/default/shell.qml").read_text()
        self.assertIn('["hyprctl", "-j", "clients"]', shell)
        self.assertNotIn('"windoesnot-hyprctl", "clients", "-j"', shell)
        self.assertIn('function onRawEvent(ev)', shell)
        self.assertIn('hyprlandWindowRefreshTimer.restart()', shell)
        self.assertIn('interval: 100\n        repeat: false\n        onTriggered: hyprlandWindowProc.running = true', shell)

        snap = (DESKTOP / "config/quickshell/default/SnapManager.qml").read_text()
        self.assertNotRegex(snap, r"windoesnot-hyprctl\s+(?:-j\s+)?(?:clients|monitors|activewindow|cursorpos)")
        overview = (DESKTOP / "config/quickshell/overview/services/HyprlandData.qml").read_text()
        self.assertNotIn('["windoesnot-hyprctl", "clients", "-j"]', overview)
        self.assertIn('["hyprctl", "-j", "clients"]', overview)

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
