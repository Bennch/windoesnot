#!/usr/bin/env python3
"""Stage only build DNS, never a host search domain, in the private build profile."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
profile = Path(sys.argv[1]).resolve()
if ROOT / 'build' not in profile.parents or not (profile / 'airootfs/etc/windoesnot-image-build').is_file():
    raise SystemExit('Expected a project-owned image profile')
lines = [line for line in Path('/etc/resolv.conf').read_text().splitlines()
         if line.split() and line.split()[0] == 'nameserver']
if not lines:
    raise SystemExit('Host resolver has no nameserver; cannot prepare offline app packages')
p = profile / 'airootfs/root/.windoesnot-build-resolv.conf'
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('\n'.join(lines) + '\n')
p.chmod(0o600)
