#!/usr/bin/env python3
"""Regression checks for the perf2 event-driven desktop updates."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
QS = ROOT / "desktop/config/quickshell/default"


def timer_blocks(text):
    for match in re.finditer(r"\bTimer\s*\{", text):
        depth = 0
        quote = None
        escaped = False
        line_comment = False
        block_comment = False
        i = match.end() - 1
        start = i
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
                    yield text[start + 1:i]
                    break
            i += 1


class Perf2EventPollingTests(unittest.TestCase):
    def test_notification_count_uses_one_event_subscription(self):
        bar = (QS / "TopNotificationBar.qml").read_text()
        self.assertIn('["swaync-client", "--subscribe-waybar"]', bar)
        self.assertIn("SplitParser", bar)
        self.assertIn("updateNotificationCount(line)", bar)
        self.assertNotIn('command: ["swaync-client", "-c"]', bar)
        self.assertFalse(any("checkNotificationsProc" in block for block in timer_blocks(bar)))

    def test_network_polling_is_visible_event_driven_and_debounced(self):
        network = (QS / "widgets/NetworkPanel.qml").read_text()
        self.assertIn('["nmcli", "monitor"]', network)
        self.assertRegex(network, r"running:\s*networkPanel\.windowVisible")
        self.assertIn("networkEventDebounce.restart()", network)
        self.assertIn("interval: 300", network)
        self.assertRegex(network, r"interval:\s*5000\s+running:\s*networkPanel\.windowVisible && networkPanel\.wifiEnabled")
        self.assertIn("updateNetworkState(false)", network)
        self.assertNotRegex(network, r"interval:\s*3000\b")

    def test_volume_osd_uses_pactl_events_instead_of_wpctl_polling(self):
        shell = (QS / "shell.qml").read_text()
        self.assertIn('["pactl", "subscribe"]', shell)
        self.assertIn("volumeEventDebounce.restart()", shell)
        self.assertIn('["windoesnot-bounded", "8", "wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]', shell)
        volume_section = shell.split("// Volume Overlay", 1)[1]
        self.assertNotIn("volumePollTimer", volume_section)
        self.assertFalse(any("interval: 100\n        running: true" in block for block in timer_blocks(volume_section)))

    def test_cava_stream_and_raster_images_avoid_repeated_work(self):
        player = (QS / "MediaPlayerWindow.qml").read_text()
        self.assertIn("stdout: SplitParser", player)
        self.assertIn("updateCavaData(line)", player)
        self.assertNotIn("cavaReadProc", player)
        welcome = (QS / "SetupWelcome.qml").read_text()
        self.assertIn("sourceSize.width: 316; sourceSize.height: 64", welcome)
        greeter = (ROOT / "desktop/share/sddm/themes/windoesnot/src/Main.qml").read_text()
        self.assertIn("sourceSize.width: Math.ceil(Layout.preferredWidth * Screen.devicePixelRatio)", greeter)


if __name__ == "__main__":
    unittest.main(verbosity=2)
