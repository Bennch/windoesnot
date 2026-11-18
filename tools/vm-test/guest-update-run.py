#!/usr/bin/env python3
"""Run an update in the guest and atomically record the real command exits."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

state = Path('/var/lib/windoesnot-update-gate')
state.mkdir(mode=0o700, parents=True, exist_ok=True)
result = {'started': datetime.now(timezone.utc).isoformat(), 'steps': {}}

def save():
    temporary = state / 'result.json.tmp'
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    os.replace(temporary, state / 'result.json')

def main():
    # Remove any previous result before starting: stale success must not pass.
    (state / 'result.json').unlink(missing_ok=True)
    with (state / 'update.log').open('w') as log:
        for name, command in [('bootstrap', ['/usr/bin/python3', '/var/lib/windoesnot-update-gate/bootstrap.py']),
                              ('update', ['/usr/local/bin/windoesnot-update', '--noconfirm'])]:
            log.write('\n=== ' + name + ' ===\n')
            log.flush()
            result['steps'][name] = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT).returncode
            if result['steps'][name] != 0:
                break
    result['finished'] = datetime.now(timezone.utc).isoformat()
    result['success'] = result['steps'].get('bootstrap') == 0 and result['steps'].get('update') == 0
    save()
    return 0 if result['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
