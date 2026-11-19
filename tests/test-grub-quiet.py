#!/usr/bin/env python3
"""The 'Loading Linux' messages are removed from grub.cfg, nothing else is touched."""
import importlib.util
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('grub_quiet', root / 'desktop/lib/windoesnot/grub_quiet.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

CFG = """menuentry 'WinDoesNot' --class arch {
\tload_video
\tinsmod gzio
\techo\t'Loading Linux linux-cachyos ...'
\tlinux\t/vmlinuz-linux-cachyos root=UUID=1 rw quiet
\techo\t'Loading initial ramdisk ...'
\tinitrd\t/initramfs-linux-cachyos.img
}
submenu 'Advanced' {
\tmenuentry 'Fallback' {
\t\techo\t'Loading Linux linux-cachyos-lts ...'
\t\tlinux\t/vmlinuz-linux-cachyos-lts root=UUID=1 rw
\t\techo\t'Starting something else'
\t}
}
"""
out = g.quiet_text(CFG)
assert 'Loading' not in out and out.count('menuentry') == CFG.count('menuentry')
assert "echo\t'Starting something else'" in out and 'linux\t/vmlinuz-linux-cachyos root=UUID=1 rw quiet' in out and 'initrd' in out
assert g.quiet_text(out) == out, 'idempotent'
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'grub.cfg'
    path.write_text(CFG)
    path.chmod(0o600)
    assert g.filter_file(path) is True and 'Loading' not in path.read_text() and path.stat().st_mode & 0o777 == 0o600
    assert g.filter_file(path) is False, 'nothing left to do'
    # A file without menu entries is never rewritten.
    only = Path(tmp) / 'odd.cfg'
    only.write_text("echo 'Loading Linux x ...'\n")
    assert g.filter_file(only) is False and 'Loading' in only.read_text()
    assert g.filter_file(Path(tmp) / 'missing.cfg') is False
print('PASS grub quiet')
