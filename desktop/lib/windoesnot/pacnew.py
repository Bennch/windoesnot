#!/usr/bin/python3 -I
"""Read-only inventory and bounded diffs for pacman .pacnew/.pacsave files."""
import argparse
import datetime
import difflib
import json
import os
from pathlib import Path
import subprocess

MAX_DIFF_BYTES = 64 * 1024
MAX_DIFF_CHARS = 16_000


def run(args):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return None


def owner(path, pacman):
    result = run([pacman, "-Qo", str(path)])
    if result and result.returncode == 0:
        # pacman output: `path is owned by package version`
        marker = " is owned by "
        if marker in result.stdout:
            return result.stdout.rsplit(marker, 1)[1].strip().rsplit(" ", 1)[0]
    return None


def modified(path, package, pacman):
    if not package:
        return None
    result = run([pacman, "-Qkk", package])
    if not result:
        return None
    # pacman reports specific changed files as warnings. A package-wide clean
    # result can verify the target; otherwise avoid guessing from aggregate data.
    target = str(path)
    lines = [line for line in result.stdout.splitlines() if target in line]
    if lines:
        return True
    if "0 altered files" in result.stdout:
        return False
    return None


def safe_diff(original, sidecar):
    if original.is_symlink() or sidecar.is_symlink():
        return {"status": "unreadable", "text": ""}
    if not original.is_file():
        return {"status": "missing-original", "text": ""}
    try:
        a = original.read_bytes()
        b = sidecar.read_bytes()
    except OSError:
        return {"status": "unreadable", "text": ""}
    if len(a) > MAX_DIFF_BYTES or len(b) > MAX_DIFF_BYTES:
        return {"status": "too-large", "text": ""}
    if b"\0" in a or b"\0" in b:
        return {"status": "binary", "text": ""}
    try:
        old, new = a.decode("utf-8").splitlines(keepends=True), b.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return {"status": "binary", "text": ""}
    text = "".join(difflib.unified_diff(old, new, fromfile=str(original), tofile=str(sidecar)))
    if len(text) > MAX_DIFF_CHARS:
        text = text[:MAX_DIFF_CHARS] + "\n… diff truncated …\n"
    return {"status": "ok", "text": text}


def scan(etc_root="/etc", pacman="pacman"):
    root = Path(etc_root)
    entries = []
    if not root.is_dir():
        return entries
    for path in sorted((*root.rglob("*.pacnew"), *root.rglob("*.pacsave"))):
        try:
            relative = path.relative_to(root)
            # These subtrees are generated and maintained by WinDoesNot.
            if any(part.lower().startswith("windoesnot") for part in relative.parts):
                continue
            if path.is_symlink():
                continue
            stat = path.stat()
        except OSError:
            continue
        suffix = ".pacnew" if path.name.endswith(".pacnew") else ".pacsave"
        original = path.with_name(path.name[:-len(suffix)])
        package = owner(original, pacman)
        if package and package.lower().startswith("windoesnot"):
            continue
        diff = safe_diff(original, path) if suffix == ".pacnew" else {"status": "not-applicable", "text": ""}
        entries.append({
            "path": "/etc/" + relative.as_posix(), "kind": suffix[1:],
            "date": datetime.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
            "size": stat.st_size, "package": package,
            "locally_modified": modified(original, package, pacman) if suffix == ".pacnew" else None,
            "diff_status": diff["status"], "diff": diff["text"],
        })
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--etc-root", default=os.environ.get("WINDOESNOT_PACNEW_ETC", "/etc"))
    parser.add_argument("--pacman", default=os.environ.get("WINDOESNOT_PACNEW_PACMAN", "pacman"))
    args = parser.parse_args()
    print(json.dumps({"files": scan(args.etc_root, args.pacman)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
