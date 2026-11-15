#!/usr/bin/env python3
"""Synthetic Windows handoff contracts; no real Windows data."""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('migrate', ROOT / 'desktop/lib/windoesnot/migrate.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp); root = base / 'windows'; home = base / 'home'
    home.mkdir(); handoff = root / 'WinDoesNotHandoff'; handoff.mkdir(parents=True)
    profile = root / 'Users/Jörg & Ada'; (profile / 'Documents').mkdir(parents=True)
    (profile / 'Documents/Grüße.txt').write_text('synthetic')
    (profile / 'Documents/My Music').symlink_to(base, target_is_directory=True)
    manifest = handoff / 'manifest.json'
    for version in ('Windows 7', 'Windows 10', 'Windows 11'):
        data = {'schema': 1, 'windows_version': version, 'locale': 'de_DE', 'profiles': {'Jörg & Ada': ['Documents']}, 'wlan': False}
        manifest.write_bytes(b'\xef\xbb\xbf' + (json.dumps(data, ensure_ascii=False, indent=2).replace('\n', '\r\n')).encode())
        plan = m.scan_tree(root, locale='de')
        assert plan['handoff']['windows_version'] == version
        assert m.copy_manifest(plan, home, source_root=root)['errors'] == []
        assert (home / 'Dokumente/Grüße.txt').read_text() == 'synthetic'
    (home / 'Dokumente/Grüße.txt').write_text('existing!')
    assert m.copy_manifest(plan, home, source_root=root)['errors']
    assert (home / 'Dokumente/Grüße.txt').read_text() == 'existing!'
    data['profiles'] = {}
    manifest.write_text(json.dumps(data))
    assert not m.scan_tree(root)['profiles'][0]['items'][0]['selected']
    for name, folders in (('..', ['Documents']), ('/tmp', ['Documents']), ('x\\y', ['Documents']), ('Ada', ['Documents', 'Documents']), ('Ada', ['../secret'])):
        data['profiles'] = {name: folders}; manifest.write_text(json.dumps(data))
        try: m.read_handoff(root)
        except ValueError: pass
        else: raise AssertionError((name, folders))
    manifest.write_text('{"schema":1,"schema":1}')
    try: m.read_handoff(root)
    except ValueError: pass
    else: raise AssertionError('duplicate JSON key')
    for bad in ('../secret', '/etc', 'Users/Jörg & Ada/Documents/../../../../etc'):
        forged = json.loads(json.dumps(plan)); forged['profiles'][0]['items'][0]['source'] = bad
        try: m.copy_manifest(forged, home, source_root=root)
        except ValueError: pass
        else: raise AssertionError(bad)
    # Redirected OneDrive folders and intermediate Firefox components are never traversed.
    (profile / 'Pictures').symlink_to(base, target_is_directory=True)
    (profile / 'OneDrive').mkdir(); (profile / 'OneDrive/Documents').mkdir()
    (profile / 'AppData').symlink_to(base, target_is_directory=True)
    manifest.unlink(); discovered = m.scan_tree(root)
    assert [i['kind'] for i in discovered['profiles'][0]['items']] == ['Documents']
    assert 'onedrive_files_may_be_online_only' in discovered['profiles'][0]['warnings']
    wlan = handoff / 'wlan'; wlan.mkdir()
    for auth, encryption in [('WPA2PSK', 'AES'), ('open', 'none'), ('shared', 'WEP')]:
        xml = f'<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"><SSIDConfig><SSID><name>{auth}</name></SSID></SSIDConfig><MSM><security><authEncryption><authentication>{auth}</authentication><encryption>{encryption}</encryption></authEncryption><sharedKey><protected>false</protected><keyMaterial>synthetic-secret</keyMaterial></sharedKey></security></MSM></WLANProfile>'
        (wlan / f'WLAN-{auth}.xml').write_text(xml)
    result = m.import_wlan(wlan, base / 'nm')
    assert result['imported'] == 1 and len(result['errors']) == 2
    assert 'synthetic-secret' not in str(result)
    firefox = base / 'firefox'; fp = firefox / 'Profiles/test'; fp.mkdir(parents=True)
    (firefox / 'profiles.ini').write_text('[Profile0]\nName=Test\nIsRelative=1\nPath=Profiles/test\n')
    assert m.firefox_profiles(firefox)
    (fp / 'key4.db-wal').touch()
    try: m.firefox_profiles(firefox)
    except ValueError: pass
    else: raise AssertionError('database WAL accepted')
print('PASS migrate handoff')
