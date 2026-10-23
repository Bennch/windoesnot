#!/usr/bin/env python3
"""Read-only runtime evidence; only selected PATH fields leave /proc."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
report = {'process_paths': {}}
for name in ('Hyprland', 'quickshell', 'qs'):
    result = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', name], capture_output=True, text=True)
    for pid in result.stdout.split():
        try:
            env = dict(part.split(b'=', 1) for part in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if b'=' in part)
            path = env.get(b'PATH', b'').decode()
            report['process_paths'][f'{name}:{pid}'] = {'local_bin': str(Path.home() / '.local/bin') in path.split(':'), 'path': path}
        except OSError as error:
            report['process_paths'][f'{name}:{pid}'] = {'error': str(error)}
instances_raw = subprocess.check_output(['hyprctl', 'instances', '-j'], text=True).strip()
instances = [] if instances_raw == ']' else json.loads(instances_raw)
if len(instances) == 1:
    signature = instances[0]['instance']
    for name, args in [('configerrors', ['configerrors']), ('plugins', ['plugin', 'list']), ('monitors', ['monitors', '-j'])]:
        result = subprocess.run(['hyprctl', '-i', signature, *args], capture_output=True, text=True)
        report[name] = {'exit': result.returncode, 'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}
(root / 'checks/host-runtime.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
