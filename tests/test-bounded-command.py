#!/usr/bin/env python3
"""The desktop command deadline must also reap descendant processes."""
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDED = ROOT / "desktop/bin/windoesnot-bounded"


class BoundedCommandTests(unittest.TestCase):
    def test_hanging_command_exits_with_timeout_status(self):
        started = time.monotonic()
        result = subprocess.run(
            [str(BOUNDED), "0.2", sys.executable, "-c", "import time; time.sleep(30)"],
            capture_output=True, text=True, timeout=4)
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.monotonic() - started, 3)

    def test_descendant_is_killed_with_timed_out_process_group(self):
        marker = Path("/tmp") / f"windoesnot-bounded-child-{time.time_ns()}"
        code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); open(sys.argv[1],'w').write(str(p.pid)); time.sleep(30)"
        try:
            result = subprocess.run([str(BOUNDED), "0.2", sys.executable, "-c", code, str(marker)],
                                    capture_output=True, text=True, timeout=4)
            self.assertEqual(result.returncode, 124)
            pid = int(marker.read_text())
            # A killed child may briefly remain as a zombie until its parent is reaped.
            stat = Path(f"/proc/{pid}/stat")
            if stat.exists():
                self.assertEqual(stat.read_text().split()[2], "Z")
        finally:
            marker.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
