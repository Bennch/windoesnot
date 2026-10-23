#!/usr/bin/env python3
"""Exercise atomic icon publication, failure retention and serialized startup."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / 'desktop/config/quickshell/default/generate-icon-map.sh'
LAUNCHER = ROOT / 'desktop/config/hypr/scripts/start-quickshell.sh'


def executable(path, text):
    path.write_text(text)
    path.chmod(0o755)


with tempfile.TemporaryDirectory(prefix='windoesnot-icons-test-') as temporary:
    home = Path(temporary)
    config = home / '.config/quickshell/default'
    config.mkdir(parents=True)
    runtime = home / 'run'
    runtime.mkdir(mode=0o700)
    js = config / 'IconMap.js'
    mapping = config / 'icon-map.json'
    bootstrap = '.pragma library\nvar MAP = {};\n'
    js.write_text(bootstrap)
    mapping.write_text('{}\n')
    env = {**os.environ, 'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_RUNTIME_DIR': str(runtime)}
    process = subprocess.Popen(['bash', GENERATOR], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    seen = set()
    started = time.monotonic()
    while process.poll() is None:
        seen.add(hashlib.sha256(js.read_bytes()).hexdigest())
        if time.monotonic() - started > 25:
            process.kill()
            raise RuntimeError('Generator timed out')
        time.sleep(0.005)
    assert process.returncode == 0, process.stderr.read().decode()
    final = js.read_bytes()
    allowed = {hashlib.sha256(bootstrap.encode()).hexdigest(), hashlib.sha256(final).hexdigest()}
    assert seen <= allowed, 'Reader observed partially written JavaScript'
    assert not list(config.glob('.icon-map.*')), 'Staging files were not cleaned'
    json.loads(mapping.read_text())
    check = home / 'check.js'
    check.write_text('\n'.join(line for line in final.decode().splitlines() if not line.startswith('.pragma ')))
    subprocess.run(['node', '--check', check], check=True)

    # A failed validator must not replace either previously usable file.
    before = {p.name: p.read_bytes() for p in (js, mapping)}
    mock = home / 'mock'
    mock.mkdir()
    executable(mock / 'python3', '#!/bin/sh\nexit 42\n')
    result = subprocess.run(['bash', GENERATOR], env={**env, 'PATH': str(mock) + ':' + env['PATH']}, capture_output=True)
    assert result.returncode != 0
    assert all(p.read_bytes() == before[p.name] for p in (js, mapping))
    assert not list(config.glob('.icon-map.*'))

    # Exercise the real launcher with stub compositor/Quickshell commands.
    (mock / 'python3').unlink()
    executable(config / 'generate-icon-map.sh', '#!/bin/bash\nbash ' + str(GENERATOR) + ' || exit 1\ntouch "$HOME/icons-ready"\n')
    executable(mock / 'windoesnot-hyprctl', '''#!/bin/sh
case "$1" in
monitors) printf '%s\n' '[{"name":"TEST","x":0,"y":0,"width":1280,"height":720,"scale":1,"transform":0}]' ;;
workspaces) printf '%s\n' '[{"id":1,"monitor":"TEST"}]' ;;
*) printf '%s\n' ok ;;
esac
''')
    (config / 'extras').mkdir()
    shutil.copy2(ROOT / 'desktop/config/quickshell/default/extras/start-quickshell.sh', config / 'extras/start-quickshell.sh')
    executable(mock / 'quickshell', '#!/bin/sh\n[ -f "$HOME/icons-ready" ] || exit 99\n[ "$1" = "--path" ] || exit 98\n[ "$2" = "$HOME/.config/quickshell/default/shell.qml" ] || exit 97\necho START_ORDER_OK\n')
    result = subprocess.run(['bash', LAUNCHER], env={**env, 'PATH': str(mock) + ':' + env['PATH']}, capture_output=True, timeout=25)
    assert result.returncode == 0, result.stderr.decode()
    assert 'START_ORDER_OK' in (runtime / 'start-quickshell.log').read_text()
    print(json.dumps({'atomic_publication': True, 'syntax_valid': True, 'failed_refresh_preserves_previous': True, 'serialized_startup': True, 'temporary_files_cleaned': True}, indent=2))
