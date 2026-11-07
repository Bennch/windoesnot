#!/usr/bin/env python3
"""Read-only migration contract, no root or block device needed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('migrate', ROOT / 'desktop/lib/windoesnot/migrate.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / 'windows'; home = Path(tmp) / 'home'
    (root / 'Users/Ada/Pictures').mkdir(parents=True)
    (root / 'Users/Public/Documents').mkdir(parents=True)
    (root / 'Users/Ada/Pictures/photo.txt').write_bytes(b'photo')
    (root / 'Users/Ada/OneDrive').mkdir()
    firefox = root / 'Users/Ada/AppData/Roaming/Mozilla/Firefox/Profiles/demo'
    firefox.mkdir(parents=True)
    (firefox / 'prefs.js').write_text('test')
    (firefox.parent.parent / 'profiles.ini').write_text('[Profile0]')
    (root / 'hiberfil.sys').touch()
    home.mkdir()
    manifest = m.scan_tree(root, '/dev/test', locale='de_DE.UTF-8')
    assert [p['name'] for p in manifest['profiles']] == ['Ada']
    assert manifest['profiles'][0]['items'][0]['bytes'] == 5
    assert any(item['kind'] == 'Firefox' for item in manifest['profiles'][0]['items'])
    assert 'onedrive_files_may_be_online_only' in manifest['profiles'][0]['warnings']
    assert 'hibernation_possible' in manifest['warnings']
    assert m.copy_manifest(manifest, home, source_root=root, dry_run=True)['bytes'] == 5
    m.copy_manifest(manifest, home, source_root=root)
    assert (home / 'Bilder/photo.txt').read_bytes() == b'photo'
    forged = json.loads(json.dumps(manifest)); forged['profiles'][0]['items'][0]['source'] = '../secret'
    try: m.copy_manifest(forged, home, source_root=root)
    except ValueError: pass
    else: raise AssertionError('forged source accepted')
    (root / 'Users/Ada/Pictures/link').symlink_to('/etc/passwd')
    linked = m.copy_manifest(manifest, home, source_root=root)
    assert any('link' in error['path'] for error in linked['errors'])
    assert not (home / 'Bilder/link').exists()
    if shutil.which('mkntfs') and shutil.which('blkid'):
        image = Path(tmp) / 'test.ntfs'
        image.write_bytes(bytes(16 * 1024 * 1024))
        subprocess.run(['mkntfs', '-F', '-Q', '-L', 'MIGRATE-TEST', str(image)], check=True, capture_output=True)
        assert 'TYPE="ntfs"' in subprocess.check_output(['blkid', '-p', str(image)], text=True)
    mounted = []
    def fake_mount(argv, **kwargs):
        mounted.append(argv)
        return Mock(returncode=1 if argv[0] == 'mount' else 0, stderr='fallback needed')
    with patch.object(m, 'command', fake_mount):
        m.mount_readonly('/dev/test', Path(tmp) / 'mount')
    assert [call[0] for call in mounted] == ['mount', 'ntfs-3g']
    assert 'ro,nosuid,nodev,noexec' in mounted[1]
    (root / 'Users/Ada/Pictures/link').unlink()
    (home / 'Bilder').rename(home / 'Bilder-old')
    (home / 'Bilder').symlink_to(home / 'Bilder-old')
    try: m.copy_manifest(manifest, home, source_root=root)
    except ValueError: pass
    else: raise AssertionError('redirected target accepted')
    with patch.object(m, 'subprocess') as proc:
        proc.check_output.return_value = json.dumps({'blockdevices':[{'path':'/dev/sda','type':'disk','children':[{'path':'/dev/sda1','type':'part','fstype':'BitLocker','size':1}]}]})
        assert m.partitions()[0]['filesystem'] == 'bitlocker'
    with patch.object(m.subprocess, 'run', return_value=Mock(returncode=0, stderr='')) as crypt:
        assert m.unlock_bitlocker('/dev/test', '123456-123456-123456-123456-123456-123456-123456-123456', 'migrate_test') == '/dev/mapper/migrate_test'
        argv = crypt.call_args.args[0]
        assert argv[:4] == ['cryptsetup', 'open', '--readonly', '--type']
        assert '--key-file' in argv and '-' in argv
        assert not any('123456' in part for part in argv)
    with patch.object(m.subprocess, 'run', return_value=Mock(returncode=2, stderr='wrong key')):
        try: m.unlock_bitlocker('/dev/test', 'password', 'migrate_test')
        except RuntimeError as error: assert 'wrong key' in str(error)
        else: raise AssertionError('cryptsetup failure accepted')
    for invalid in ('1234', 'foo\nbar', '12345-6123456-' + '123456-' * 6 + '123456'):
        try: m.unlock_bitlocker('/dev/test', invalid, 'migrate_test')
        except ValueError: pass
        else: raise AssertionError('invalid secret accepted')
    bitlocker_device = [{'device': '/dev/locked', 'filesystem': 'bitlocker'}]
    with patch.object(m, 'partitions', return_value=bitlocker_device):
        locked_plan = m.scan_device('/dev/locked')
        assert locked_plan['warnings'] == ['bitlocker_locked'] and locked_plan['profiles'] == []
        with patch.object(m.subprocess, 'run', return_value=Mock(returncode=2, stderr='wrong key')), patch.object(m, 'command', return_value=Mock(returncode=0)):
            try: m.scan_device('/dev/locked', secret='wrong-password')
            except RuntimeError as error: assert 'wrong key' in str(error)
            else: raise AssertionError('bad BitLocker password accepted')
        recovery = '-'.join(['123456'] * 8)
        with patch.object(m.subprocess, 'run', return_value=Mock(returncode=0, stderr='')) as crypt, patch.object(m, 'mount_readonly') as mounted_ok, patch.object(m, 'scan_tree', return_value={'profiles': []}), patch.object(m, 'command', return_value=Mock(returncode=0)):
            assert m.scan_device('/dev/locked', secret=recovery) == {'profiles': []}
            assert crypt.call_args.kwargs['input'] == recovery + '\n'
            assert mounted_ok.call_args.args[0].startswith('/dev/mapper/')
    with patch.object(m, 'command', return_value=Mock(returncode=1, stderr='Windows is hibernated')):
        try: m.mount_readonly('/dev/test', Path(tmp) / 'mount')
        except RuntimeError as error: assert 'Fast Startup or hibernation' in str(error)
        else: raise AssertionError('hibernation mount failure accepted')
    (home / 'Bilder').unlink()
    (root / 'Users/Ada/Pictures/Grüße.txt').write_text('äöü')
    long_name = 'ü' * 100 + '.txt'
    (root / 'Users/Ada/Pictures' / long_name).write_text('long')
    nested = root / 'Users/Ada/Pictures' / ('deep' * 30) / ('more' * 30)
    nested.mkdir(parents=True)
    (nested / 'deep.txt').write_text('nested')
    manifest = m.scan_tree(root, '/dev/test', locale='de')
    events = []
    original_command = m.command
    def flaky(argv, **kwargs):
        if argv[0] == 'rsync' and argv[-2].endswith('Grüße.txt'):
            return Mock(returncode=23, stderr='simulated per-file failure')
        return original_command(argv, **kwargs)
    with patch.object(m, 'command', flaky):
        result = m.copy_manifest(manifest, home, source_root=root, progress=events.append)
    assert len(result['errors']) == 1 and 'Grüße.txt' in result['errors'][0]['path']
    assert (home / 'Bilder' / long_name).read_text() == 'long'
    assert (home / 'Bilder' / nested.relative_to(root / 'Users/Ada/Pictures') / 'deep.txt').read_text() == 'nested'
    assert events[0]['event'] == 'start' and events[-1]['event'] == 'done'
    assert any(event['event'] == 'file_error' for event in events)
    outside = Path(tmp) / 'outside.txt'; outside.write_text('untouched')
    (home / 'Bilder/photo.txt').unlink()
    (home / 'Bilder/photo.txt').symlink_to(outside)
    redirected = m.copy_manifest(manifest, home, source_root=root)
    assert any('target file is redirected' == error['error'] for error in redirected['errors'])
    assert outside.read_text() == 'untouched'
    (home / 'Bilder/photo.txt').unlink()
    firefox_root = firefox.parent.parent
    (firefox_root / 'profiles.ini').write_text('[General]\nStartWithLastProfile=1\n\n[Profile0]\nName=Windows\nIsRelative=1\nPath=Profiles/demo\n')
    for name in ('places.sqlite', 'logins.json', 'key4.db'):
        (firefox / name).write_text('windows-' + name)
    existing = home / '.mozilla/firefox'
    (existing / 'Profiles/native').mkdir(parents=True)
    (existing / 'Profiles/native/places.sqlite').write_text('native-history')
    (existing / 'profiles.ini').write_text('[General]\nStartWithLastProfile=1\n\n[Profile0]\nName=Native\nIsRelative=1\nPath=Profiles/native\nDefault=1\n')
    firefox_manifest = m.scan_tree(root, '/dev/test')
    for item in firefox_manifest['profiles'][0]['items']:
        item['selected'] = item['kind'] == 'Firefox'
    migrated = m.copy_manifest(firefox_manifest, home, source_root=root)
    assert migrated['errors'] == []
    assert (existing / 'Profiles/native/places.sqlite').read_text() == 'native-history'
    assert (existing / 'Profiles/demo-windows/logins.json').read_text() == 'windows-logins.json'
    assert (existing / 'Profiles/demo-windows/key4.db').read_text() == 'windows-key4.db'
    merged = (existing / 'profiles.ini').read_text()
    assert 'Default=1' in merged and 'Path=Profiles/demo-windows' in merged
    m.copy_manifest(firefox_manifest, home, source_root=root)
    assert (existing / 'profiles.ini').read_text().count('Name=Windows (Windows)') == 1
    (firefox / 'parent.lock').touch()
    locked = m.copy_manifest(firefox_manifest, home, source_root=root)
    assert any('locked' in error['error'] for error in locked['errors'])
    (firefox / 'parent.lock').unlink()
    flatpak_home = Path(tmp) / 'flatpak-home'; flatpak_home.mkdir()
    (flatpak_home / '.var/app/org.mozilla.firefox').mkdir(parents=True)
    assert m.firefox_target(flatpak_home) == flatpak_home / '.var/app/org.mozilla.firefox/.mozilla/firefox'
    wlan = root / 'WinDoesNotHandoff/wlan'; wlan.mkdir(parents=True)
    def export(name, auth, key):
        (wlan / name).write_text('<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"><name>Test WLAN</name><MSM><security><authEncryption><authentication>' + auth + '</authentication><encryption>AES</encryption></authEncryption><sharedKey><protected>false</protected><keyMaterial>' + key + '</keyMaterial></sharedKey></security></MSM></WLANProfile>')
    export('WLAN-Test.xml', 'WPA2PSK', 'secret-passphrase')
    nm = Path(tmp) / 'system-connections'
    imported = m.import_wlan(wlan, nm)
    assert imported == {'imported': 1, 'errors': []}
    connection = next(nm.iterdir())
    assert connection.stat().st_mode & 0o777 == 0o600
    assert 'key-mgmt=wpa-psk' in connection.read_text()
    export('WLAN-Unknown.xml', 'WPA2ENT', 'never-print-this')
    rejected = m.import_wlan(wlan, nm)
    assert rejected['imported'] == 0 and len(rejected['errors']) == 2
    assert 'never-print-this' not in str(rejected)
    sae_dir = Path(tmp) / 'sae'; sae_dir.mkdir()
    (sae_dir / 'WLAN-SAE.xml').write_text((wlan / 'WLAN-Test.xml').read_text().replace('WPA2PSK', 'WPA3SAE').replace('Test WLAN', 'SAE WLAN'))
    sae_result = m.import_wlan(sae_dir, Path(tmp) / 'sae-target')
    assert sae_result['imported'] == 1 and 'key-mgmt=sae' in next((Path(tmp) / 'sae-target').iterdir()).read_text()
    handoff_root = Path(tmp) / 'handoff-windows'
    shutil.copytree(ROOT / 'tests/fixtures/migrate-handoff', handoff_root)
    (handoff_root / 'Users/Ada/Pictures').mkdir(parents=True)
    (handoff_root / 'Users/Ada/Documents').mkdir(parents=True)
    (handoff_root / 'Users/Ada/Pictures/photo.txt').write_text('handoff-photo')
    handoff_home = Path(tmp) / 'handoff-home'; handoff_home.mkdir()
    chosen = m.scan_tree(handoff_root, '/dev/test', locale='en')
    assert chosen['handoff']['windows_version'] == 'Windows 11 24H2'
    assert {item['kind']: item['selected'] for item in chosen['profiles'][0]['items']} == {'Documents': False, 'Pictures': True}
    network_target = Path(tmp) / 'handoff-nm'
    done = m.copy_manifest(chosen, handoff_home, source_root=handoff_root, nm_dir=network_target)
    assert done['errors'] == [] and done['wlan_imported'] == 1
    assert (handoff_home / 'Pictures/photo.txt').read_text() == 'handoff-photo'
    assert next(network_target.iterdir()).stat().st_mode & 0o777 == 0o600
    (handoff_root / 'WinDoesNotHandoff/manifest.json').write_text('{bad json')
    invalid_handoff = m.scan_tree(handoff_root, '/dev/test')
    assert 'handoff_invalid' in invalid_handoff['warnings'] and invalid_handoff['handoff'] is None
    browser_root = Path(tmp) / 'browser-windows'
    (browser_root / 'Users/Ada/AppData/Local/Google/Chrome/User Data').mkdir(parents=True)
    (browser_root / 'Users/Ada/AppData/Local/Microsoft/Edge/User Data').mkdir(parents=True)
    (browser_root / 'Users/Ada/AppData/Local/Google/Chrome/User Data/Login Data').write_text('do-not-copy')
    browser_plan = m.scan_tree(browser_root)
    assert browser_plan['profiles'][0]['browsers'] == ['Edge', 'Chrome']
    assert 'chromium_passwords_windows_export_only' in browser_plan['profiles'][0]['warnings']
    assert browser_plan['profiles'][0]['items'] == []
    target_root = Path(tmp) / 'installed'; (target_root / 'etc').mkdir(parents=True)
    (target_root / 'etc/windoesnot-image-build').touch()
    (target_root / 'home/ada').mkdir(parents=True)
    values = {'windoesnotMigrateManifest': json.dumps(chosen), 'username': 'ada', 'rootMountPoint': str(target_root)}
    warnings_logged = []
    storage = SimpleNamespace(value=lambda key: values.get(key), insert=lambda key, value: values.__setitem__(key, value))
    fake_calamares = SimpleNamespace(globalstorage=storage, utils=SimpleNamespace(warning=warnings_logged.append), job=SimpleNamespace(setprogress=lambda _: None))
    with patch.dict(sys.modules, {'libcalamares': fake_calamares, 'migrate': m}):
        job_spec = importlib.util.spec_from_file_location('migrate_job', ROOT / 'iso/modules/windoesnotmigrate_install/main.py')
        job = importlib.util.module_from_spec(job_spec); job_spec.loader.exec_module(job)
        for failure in (ValueError('Windows partition is no longer available'), OSError('Not enough free space')):
            with patch.object(job.migrate, 'copy_manifest', side_effect=failure):
                assert job.run() is None
                assert str(failure) in values['windoesnotMigrateWarning']
                assert values['windoesnotMigrateSecret'] == ''
    assert len(warnings_logged) == 2
    with patch.dict(sys.modules, {'libcalamares': fake_calamares, 'migrate': m}):
        with patch.object(job.migrate, 'copy_manifest', return_value={'errors': [{'path': 'Users/Ada/Pictures/photo.txt', 'error': 'rsync code 23'}]}):
            assert job.run() is None
            assert 'photo.txt' in values['windoesnotMigrateWarning'] and 'rsync code 23' in values['windoesnotMigrateWarning']
    with patch.object(m.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
        try: m.copy_manifest(manifest, home, source_root=root)
        except OSError as error: assert 'Not enough free space' in str(error)
        else: raise AssertionError('insufficient space accepted')
    with patch.object(m, 'command', side_effect=FileNotFoundError('Windows disk disappeared')):
        try: m.copy_manifest(manifest, home, source_root=root)
        except FileNotFoundError as error: assert 'disappeared' in str(error)
        else: raise AssertionError('vanished disk accepted')
print('PASS migrate')
