#!/usr/bin/env python3
"""Exercise real upgrade/migration behavior in a disposable user home."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

tool = Path(__file__).resolve().parent.parent / 'desktop/bin/windoesnot-desktop-sync'
with tempfile.TemporaryDirectory(prefix='windoesnot-upgrade-test-') as temp:
    root = Path(temp); home = root/'home'; home.mkdir()
    source = root/'source'; code = source/'desktop/config/quickshell/default'
    code.mkdir(parents=True)
    (source/'VERSION').write_text('0.1.0-1\n')
    (code/'shell.qml').write_text('version one\n')
    (code/'old.qml').write_text('retired\n')
    (code/'custom.qml').write_text('upstream original\n')
    env = {**os.environ, 'HOME':str(home), 'XDG_CONFIG_HOME':str(home/'.config'), 'XDG_STATE_HOME':str(home/'.local/state')}
    def sync(*args, success=True):
        p=subprocess.run(['python3',str(tool),'--source',str(source),'--native',str(root/'empty-native'),*args],env=env,text=True,capture_output=True)
        if success: assert p.returncode==0,(p.stdout,p.stderr)
        else: assert p.returncode!=0
        return p
    sync()
    config=home/'.config/quickshell/default'
    private={'settings.txt':'darkMode=false\nprivate=value\n','calendar_notes.json':'{"private":"note"}','pins.txt':'user pins\n'}
    private['IconMap.js']='// Generated for this user\nvar MAP = {"userapp":"user-icon"};\n'
    for name,text in private.items(): (config/name).write_text(text)
    (config/'custom.qml').write_text('my local code\n')
    (source/'VERSION').write_text('0.1.0-2\n')
    (code/'shell.qml').write_text('version two\n')
    (code/'new.qml').write_text('new component\n')
    (code/'custom.qml').write_text('changed upstream\n')
    (code/'old.qml').unlink()
    p=sync()
    report=json.loads(p.stdout)
    assert (config/'shell.qml').read_text()=='version two\n'
    assert (config/'new.qml').exists() and not (config/'old.qml').exists()
    assert (config/'custom.qml').read_text()=='my local code\n'
    assert report['conflicts']==['quickshell/default/custom.qml']
    assert all((config/name).read_text()==text for name,text in private.items())
    # An older package accidentally tracked this generated cache as code.
    ledger=home/'.local/state/windoesnot/desktop-files.json'
    old_record=json.loads(ledger.read_text())
    import hashlib
    old_record['files']['quickshell/default/IconMap.js']=hashlib.sha256((config/'IconMap.js').read_bytes()).hexdigest()
    ledger.write_text(json.dumps(old_record))
    sync()
    assert (config/'IconMap.js').read_text()==private['IconMap.js']
    assert 'quickshell/default/IconMap.js' not in json.loads(ledger.read_text())['files']
    backup=Path(report['backup'])/'quickshell/default'
    assert (backup/'shell.qml').read_text()=='version one\n' and (backup/'old.qml').read_text()=='retired\n'
    again=json.loads(sync().stdout)
    assert not again['changed'] and not again['removed']
    # Existing unrelated symlink targets are never written through.
    outside=root/'outside'; outside.mkdir(); (outside/'escape.qml').write_text('private\n')
    (code/'linked').mkdir(); (code/'linked/escape.qml').write_text('must not escape\n')
    (config/'linked').symlink_to(outside,target_is_directory=True)
    sync()
    assert (outside/'escape.qml').read_text()=='private\n'
    # Invalid retired entries cannot traverse outside XDG_CONFIG_HOME.
    ledger=home/'.local/state/windoesnot/desktop-files.json'
    record=json.loads(ledger.read_text())
    record['files']['../sentinel']=hashlib.sha256(b'sentinel').hexdigest()
    (home/'sentinel').write_bytes(b'sentinel'); ledger.write_text(json.dumps(record))
    sync(success=False)
    assert (home/'sentinel').read_bytes()==b'sentinel'
    # Adoption records the legacy baseline without changing existing files.
    ledger.unlink(); (config/'shell.qml').write_text('legacy local override\n')
    sync('--adopt')
    assert (config/'shell.qml').read_text()=='legacy local override\n'
    assert 'quickshell/default/shell.qml' not in json.loads(ledger.read_text())['files']
print('PASS: code update, addition/removal, personal-state preservation, local edits, backup, idempotency, symlink/path escape and legacy adoption')
