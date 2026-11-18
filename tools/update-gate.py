#!/usr/bin/env python3
"""Update-channel VM gate: currently incomplete, always fails closed."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from update_gate_common import package_set

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--iso', required=True, type=Path, help='predecessor ISO')
p.add_argument('--packages', required=True, type=Path, help='exact candidate package directory')
a = p.parse_args()
if not a.iso.is_file(): p.error(f'ISO not found: {a.iso}')
try:
    digest = package_set(a.packages)
except (OSError, ValueError) as exc:
    p.error(str(exc))
reason = ('VM automation is not implemented: offline installation, signed test repository, '
          'full upgrade, reboot and post-update checks were not executed')
result = {'timestamp': datetime.now(timezone.utc).isoformat(), 'package_set_sha256': digest,
          'exit_code': 1, 'checks': {}, 'error': reason, 'iso': str(a.iso.resolve())}
print(json.dumps(result, indent=2))
print('FAIL: ' + reason, file=sys.stderr)
raise SystemExit(1)
