#!/usr/bin/env python3
"""Regression tests for the non-GL swaybg wallpaper launcher."""

import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "desktop/bin/windoesnot-wallpaper"
LOADER = importlib.machinery.SourceFileLoader("windoesnot_wallpaper", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
wallpaper = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(wallpaper)


class WallpaperLauncherTests(unittest.TestCase):
    def test_legacy_config_starts_cover_wallpaper_for_each_monitor(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            first = temp / "one.jpg"
            second = temp / "two.png"
            first.touch()
            second.touch()
            config = temp / "hyprpaper.conf"
            original = (
                "# personal config\nsplash = false\n\n"
                "wallpaper {\n monitor = DP-1\n path = " + str(first) +
                "\n fit_mode = cover\n}\nwallpaper {\n monitor = HDMI-A-1\n path = " +
                str(second) + "\n fit_mode = cover\n}\n")
            config.write_text(original)
            pidfile = temp / "runtime/pids"

            class Proc:
                def __init__(self, command, **kwargs):
                    self.pid = 4100 + len(calls)
                    calls.append((command, kwargs))

                def poll(self):
                    return None

            calls = []
            with (patch.dict(wallpaper.os.environ, {"XDG_CACHE_HOME": str(temp / "cache"), "WINDOESNOT_WALLPAPER_CHECK_DELAY": "0"}),
                  patch.object(wallpaper, "CONFIG", config),
                  patch.object(wallpaper, "PIDFILE", pidfile),
                  patch.object(wallpaper, "shutil_which", return_value="/usr/bin/swaybg"),
                  patch.object(wallpaper.subprocess, "Popen", Proc)):
                self.assertEqual(wallpaper.main(), 0)

            self.assertEqual([item[0] for item in calls], [
                ["swaybg", "-i", str(first), "-m", "fill", "-o", "DP-1"],
                ["swaybg", "-i", str(second), "-m", "fill", "-o", "HDMI-A-1"],
            ])
            self.assertTrue(all(item[1]["start_new_session"] for item in calls))
            self.assertEqual(pidfile.read_text(), "4100\n4101\n")
            self.assertEqual(config.read_text(), original)

    def test_swaybg_that_exits_at_once_is_restarted(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            image = temp / "one.png"
            image.touch()
            config = temp / "hyprpaper.conf"
            config.write_text("wallpaper {\n monitor = DP-1\n path = " + str(image) + "\n}\n")
            pidfile = temp / "runtime/pids"
            calls = []

            class Proc:
                def __init__(self, command, **kwargs):
                    self.pid = 5000 + len(calls)
                    self.first = not calls
                    calls.append(command)

                def poll(self):
                    return 1 if self.first else None

            with (patch.dict(wallpaper.os.environ, {"XDG_CACHE_HOME": str(temp / "cache"), "WINDOESNOT_WALLPAPER_CHECK_DELAY": "0"}),
                  patch.object(wallpaper, "CONFIG", config),
                  patch.object(wallpaper, "PIDFILE", pidfile),
                  patch.object(wallpaper, "shutil_which", return_value="/usr/bin/swaybg"),
                  patch.object(wallpaper.subprocess, "Popen", Proc)):
                self.assertEqual(wallpaper.main(), 0)
            self.assertEqual(len(calls), 2, "a swaybg that exits right away must be started again")
            self.assertEqual(pidfile.read_text(), "5001\n")

    def test_missing_images_are_skipped_without_destroying_config(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config = temp / "hyprpaper.conf"
            config.write_text("wallpaper {\n monitor = DP-1\n path = /missing/image.jpg\n}\n")
            pidfile = temp / "runtime/pids"
            with (patch.object(wallpaper, "CONFIG", config),
                  patch.object(wallpaper, "PIDFILE", pidfile),
                  patch.object(wallpaper, "shutil_which", return_value="/usr/bin/swaybg"),
                  patch.object(wallpaper.subprocess, "Popen") as popen):
                self.assertEqual(wallpaper.main(), 0)
            popen.assert_not_called()
            self.assertFalse(pidfile.exists())
            self.assertTrue(config.exists())

    def test_desktop_uses_swaybg_and_keeps_legacy_settings_format(self):
        script = (ROOT / "desktop/bin/windoesnot-wallpaper").read_text()
        qml = (ROOT / "desktop/config/quickshell/default/settings/BackgroundCategory.qml").read_text()
        self.assertIn('"swaybg"', script)
        self.assertIn('"-m", "fill"', script)
        self.assertIn('"windoesnot-wallpaper", "--restart"', qml)
        self.assertIn(".config/hypr/hyprpaper.conf", qml)
        self.assertIn("fit_mode = cover", qml)


if __name__ == "__main__":
    unittest.main()
