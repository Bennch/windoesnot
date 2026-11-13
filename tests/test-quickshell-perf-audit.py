#!/usr/bin/env python3
"""Regression checks for the static Quickshell performance inventory."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools/audit-quickshell-perf.py"
SPEC = importlib.util.spec_from_file_location("audit_quickshell_perf", TOOL)
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class AuditTests(unittest.TestCase):
    def test_timer_counts_commands_and_reports_short_running_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "desktop/config/quickshell/default/shell.qml"
            source.parent.mkdir(parents=True)
            source.write_text("""Timer {
    interval: 100
    running: true
    repeat: true
    onTriggered: proc.running = true
}
Process {
    id: proc
    command: ["hyprctl", "jq"]
}
""", encoding="utf-8")
            findings = AUDIT.analyze(root)
        categories = {finding.category for finding in findings}
        self.assertIn("short-running-timer", categories)
        per_tick = next(f for f in findings if f.category == "process-per-tick")
        self.assertIn("hoch", per_tick.severity)
        self.assertIn("1 Prozessstart(s) je Tick", per_tick.reason)
        self.assertIn("hyprctl", per_tick.reason)

    def test_static_candidates_and_autostart_are_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            qml = root / "desktop/config/quickshell/default/Popup.qml"
            qml.parent.mkdir(parents=True)
            qml.write_text("""FloatingWindow {
    visible: false
    Image { source: \"banner.png\" }
    Repeater { model: 3 }
}
""", encoding="utf-8")
            ref = root / "desktop/config/hypr/lua/reference.lua"
            ref.parent.mkdir(parents=True)
            ref.write_text('{["autostart"]={"daemon --watch", "sleep 1"}}', encoding="utf-8")
            findings = AUDIT.analyze(root)
        categories = {finding.category for finding in findings}
        self.assertTrue({"eager-popup", "large-image-candidate", "eager-repeater", "autostart"} <= categories)
        self.assertEqual(sum(f.category == "autostart" for f in findings), 2)

    def test_markdown_output_is_stable_table(self):
        finding = AUDIT.Finding("desktop/test.qml", 7, "test", "niedrig", "Example | escaped")
        report = AUDIT.markdown([finding])
        self.assertIn("| Datei | Zeile | Befund | Last | Begründung |", report)
        self.assertIn("Example \\| escaped", report)


if __name__ == "__main__":
    unittest.main()
