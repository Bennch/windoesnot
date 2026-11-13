#!/usr/bin/env python3
"""Read-only pacnew scanner behavior using a temporary /etc and fake pacman."""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pacnew", ROOT / "desktop/lib/windoesnot/pacnew.py")
pacnew = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pacnew)

with tempfile.TemporaryDirectory(prefix="wdn-pacnew-") as tmp:
    base = Path(tmp)
    etc = base / "etc"
    (etc / "ssh").mkdir(parents=True)
    (etc / "windoesnot").mkdir()
    original = etc / "ssh/config"
    sidecar = etc / "ssh/config.pacnew"
    original.write_text("# local\nPermitRootLogin no\n")
    sidecar.write_text("# default\nPermitRootLogin yes\n")
    (etc / "ssh/removed.pacsave").write_bytes(b"saved bytes\n")
    (etc / "windoesnot/internal.conf.pacnew").write_text("managed\n")
    (etc / "ssh/binary").write_bytes(b"text\x00original")
    (etc / "ssh/binary.pacnew").write_bytes(b"\x00\xff")
    (etc / "ssh/large").write_text("small original")
    (etc / "ssh/large.pacnew").write_text("x" * (pacnew.MAX_DIFF_BYTES + 1))
    pacman = base / "pacman"
    pacman.write_text("""#!/bin/sh
if [ "$1" = -Qo ]; then
  case "$2" in */ssh/config) echo "$2 is owned by openssh 1.0";; *) exit 1;; esac
elif [ "$1" = -Qkk ]; then
  echo "warning: openssh: PLACEHOLDER (modified)"
else exit 2
fi
""")
    pacman.write_text(pacman.read_text().replace("PLACEHOLDER", str(original)))
    pacman.chmod(0o755)
    rows = pacnew.scan(etc, str(pacman))
    by_path = {row["path"]: row for row in rows}
    assert set(by_path) == {"/etc/ssh/config.pacnew", "/etc/ssh/removed.pacsave",
                           "/etc/ssh/binary.pacnew", "/etc/ssh/large.pacnew"}
    row = by_path["/etc/ssh/config.pacnew"]
    assert row["package"] == "openssh" and row["locally_modified"] is True
    assert "-PermitRootLogin no" in row["diff"] and "+PermitRootLogin yes" in row["diff"]
    assert row["size"] == sidecar.stat().st_size and row["date"]
    assert by_path["/etc/ssh/removed.pacsave"]["diff_status"] == "not-applicable"
    assert by_path["/etc/ssh/binary.pacnew"]["diff_status"] == "binary"
    assert by_path["/etc/ssh/large.pacnew"]["diff_status"] == "too-large"
    output = __import__("subprocess").check_output(
        ["/usr/bin/python3", str(ROOT / "desktop/lib/windoesnot/pacnew.py"),
         "--etc-root", str(etc), "--pacman", str(pacman)], text=True)
    assert len(json.loads(output)["files"]) == 4
print("PASS: pacnew inventory, fake ownership/integrity, bounded text diff, binary and pacsave cases")
