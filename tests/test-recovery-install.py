#!/usr/bin/env python3
"""The CachyOS recovery image is placed on the ESP after install, UEFI only, and never aborts the install."""
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'iso'))
import installation

with tempfile.TemporaryDirectory(prefix='wdn-recovery-') as temporary:
    root = Path(temporary)
    assert not installation.install_recovery('efi', root)  # package absent
    for name in (installation.RECOVERY_INSTALLER, installation.RECOVERY_IMAGE):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).touch()
    with patch.object(installation.subprocess, 'run') as run:
        assert not installation.install_recovery('bios', root) and not run.called
        run.return_value = SimpleNamespace(returncode=0)
        assert installation.install_recovery('efi', root)
        assert run.call_args.args[0] == [str(root / installation.RECOVERY_INSTALLER), 'install']
        run.return_value = SimpleNamespace(returncode=1)
        assert not installation.install_recovery('efi', root)
        run.side_effect = subprocess.TimeoutExpired('x', 300)
        assert not installation.install_recovery('efi', root)
packages = (ROOT / 'iso/packages-extra.txt').read_text().split()
assert {'cachyos-recovery', 'gvfs-mtp', 'gst-plugin-dav1d', 'ghostty-terminfo'} <= set(packages)
print('PASS: recovery image install is UEFI-only and non-fatal')
