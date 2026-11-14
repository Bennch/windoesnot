#!/usr/bin/env python3
"""Exercise the live legacy-NVIDIA gate with isolated command fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'desktop/lib/windoesnot/old-gpu-setup'
unit = (ROOT / 'desktop/share/systemd/system/windoesnot-old-gpu.service').read_text()
assert 'ConditionPathExists=/etc/windoesnot-image-build' in unit
assert 'Before=display-manager.service' in unit
finalize = (ROOT / 'iso/finalize-install.sh').read_text()
assert 'systemctl disable windoesnot-old-gpu.service' not in finalize, 'the service must stay enabled on the installed system'

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    bindir = root / 'bin'; bindir.mkdir()
    lspci = bindir / 'lspci'
    lspci.write_text('''#!/bin/sh
case "$*" in
  *0300*) cat "$GPU_0300" ;;
  *0302*) cat "$GPU_0302" ;;
esac
''')
    lspci.chmod(0o755)
    modprobe_log = root / 'modprobe.log'
    modprobe = bindir / 'modprobe'
    modprobe.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MODPROBE_LOG"\n')
    modprobe.chmod(0o755)
    logger = bindir / 'logger'
    logger.write_text('#!/bin/sh\nexit 0\n'); logger.chmod(0o755)
    ids = root / 'nouveau.ids'; ids.write_text('0a74 0a20 05e2 06c0 0dc4\n')
    old = root / 'nvidia-utils.conf'
    lite_flag = root / 'windoesnot/lite-mode'
    lite_marker = root / 'state/old-gpu-lite-decided'
    blacklist = root / 'legacy-nvidia.conf'
    old.write_text('blacklist nouveau\n')
    gpu0300, gpu0302 = root / '0300', root / '0302'

    def run(primary='', secondary=''):
        gpu0300.write_text(primary); gpu0302.write_text(secondary)
        env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                   GPU_0300=str(gpu0300), GPU_0302=str(gpu0302),
                   MODPROBE_LOG=str(modprobe_log), WINDOESNOT_NOUVEAU_IDS=str(ids),
                   WINDOESNOT_MODPROBE_OVERRIDE=str(old), WINDOESNOT_LITE_FLAG=str(lite_flag), WINDOESNOT_LITE_MARKER=str(lite_marker), WINDOESNOT_NVIDIA_BLACKLIST=str(blacklist))
        subprocess.run([str(SCRIPT)], env=env, check=True)

    run('01:00.0 0300: 10de:0a74 (rev a2)\n')
    assert old.read_text() == ''
    assert lite_flag.is_file()
    assert modprobe_log.read_text() == 'nouveau\n'
    assert 'blacklist nvidia_drm' in blacklist.read_text() and 'blacklist nvidia\n' in blacklist.read_text()

    old.write_text('blacklist nouveau\n'); modprobe_log.unlink()
    run('02:00.0 0300: 10de:1e04 (rev a1)\n')
    assert old.read_text() == 'blacklist nouveau\n' and not modprobe_log.exists()
    assert lite_flag.is_file()  # unmatched hardware does not erase a user/live choice
    run('', '03:00.0 0302: 8086:1234 (rev 01)\n')
    assert old.read_text() == 'blacklist nouveau\n' and not modprobe_log.exists()

    # The secondary display controller class is checked too.
    run('', '04:00.0 0302: 10de:0dc4 (rev a1)\n')
    assert old.read_text() == '' and modprobe_log.read_text() == 'nouveau\n'

    # A user who switched lite mode off keeps that choice on later boots; nouveau is still freed.
    lite_flag.unlink(); old.write_text('blacklist nouveau\n'); modprobe_log.unlink(missing_ok=True)
    run('01:00.0 0300: 10de:0a74 (rev a2)\n')
    assert old.read_text() == '' and not lite_flag.exists() and modprobe_log.read_text() == 'nouveau\n'

print('PASS: nouveau IDs trigger blacklist override and modprobe; newer NVIDIA/Intel are untouched')
