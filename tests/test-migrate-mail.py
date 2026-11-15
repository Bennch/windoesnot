#!/usr/bin/env python3
"""Synthetic Thunderbird migration and safety checks."""
import importlib.util
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('migrate_mail', root / 'desktop/lib/windoesnot/migrate.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    windows, home = base / 'windows', base / 'home'
    home.mkdir()
    tb = windows / 'Users/Ada/AppData/Roaming/Thunderbird'
    profile = tb / 'Profiles/demo'
    (profile / 'Mail').mkdir(parents=True)
    (profile / 'ImapMail').mkdir()
    (profile / 'Mail/Inbox').write_text('mail')
    (tb / 'profiles.ini').write_text('[Profile0]\nName=Demo\nIsRelative=1\nPath=Profiles/demo\n')
    (profile / 'prefs.js').write_text('user_pref("mail.account.account1.server", "server1");\nuser_pref("mail.account.account1.identities", "id1");\nuser_pref("mail.server.server1.type", "imap");\nuser_pref("mail.server.server1.hostname", "mail.example.test");\nuser_pref("mail.identity.id1.useremail", "ada@example.test");\n')
    manifest = m.scan_tree(windows)
    item = manifest['profiles'][0]['items'][0]
    assert item['kind'] == 'Thunderbird' and item['selected']
    result = m.copy_manifest(manifest, home, source_root=windows)
    assert result['mail_imported'] and not result['errors']
    assert (home / '.thunderbird/Profiles/demo-windows/Mail/Inbox').read_text() == 'mail'
    assert 'Demo (Windows)' in (home / '.thunderbird/profiles.ini').read_text()
    assert 'ada@example.test | mail.example.test | imap' in (home / 'Umzug-Windows/Mail-Konten.txt').read_text()
    assert not m.copy_manifest(manifest, home, source_root=windows)['errors']
    (profile / 'parent.lock').touch()
    assert 'thunderbird_unavailable' in m.scan_tree(windows)['profiles'][0]['items'][0]['warnings']
    assert m.copy_manifest(manifest, home, source_root=windows)['errors']
    (profile / 'parent.lock').unlink()
    (profile / 'key4.db-wal').touch()
    assert m.copy_manifest(manifest, home, source_root=windows)['errors']
    (profile / 'key4.db-wal').unlink()
    (profile / 'Mail/link').symlink_to(base / 'outside')
    assert m.copy_manifest(manifest, home, source_root=windows)['errors']

# EML, Outlook, repeat runs and redirected paths.
import os
with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    windows, home = base / 'windows', base / 'home'
    home.mkdir()
    store = windows / 'Users/Äda/AppData/Local/Microsoft/Windows Live Mail'
    (store / 'Posteingang' / 'Unterordner').mkdir(parents=True)
    (store / 'Posteingang' / 'a.eml').write_bytes(b'Subject: =?utf-8?Q?Gr=C3=BC=C3=9Fe?=\r\nContent-Type: multipart/mixed; boundary=x\r\n\r\nFrom danger\r\n--x\r\nContent-Transfer-Encoding: base64\r\n\r\nYW5oYW5n\r\n--x--\r\n')
    (store / 'Posteingang/Unterordner/b.eml').write_text('Subject: nested\n\nhello\n')
    outlook = windows / 'Users/Äda/Documents/Outlook Files'
    outlook.mkdir(parents=True)
    (outlook / 'Archiv.pst').write_bytes(b'fake')
    (outlook / 'Cache.ost').write_bytes(b'fake')
    fakebin = base / 'bin'
    fakebin.mkdir()
    readpst = fakebin / 'readpst'
    readpst.write_text('#!/usr/bin/python3\nimport pathlib,sys\nassert sys.argv[1:3] == ["-r", "-o"]\np = pathlib.Path(sys.argv[3]); assert p.parent.parent.name == "home"\n(p / "Inbox").write_text("From - test\\nSubject: PST\\n\\nhello\\n")\n')
    readpst.chmod(0o755)
    old_path = os.environ['PATH']
    os.environ['PATH'] = str(fakebin) + os.pathsep + old_path
    try:
        manifest = m.scan_tree(windows, locale='de')
        kinds = {i['kind'] for i in manifest['profiles'][0]['items']}
        assert {'Windows Live Mail', 'Outlook PST', 'Outlook OST'} <= kinds
        result = m.copy_manifest(manifest, home, source_root=windows)
        assert not result['errors'], result
        local = home / '.thunderbird/Profiles/windows-mail/Mail/Local Folders'
        mailbox = local / 'Äda-Windows Live Mail.sbd/Posteingang'
        assert b'>From danger\n' in mailbox.read_bytes()
        assert b'YW5oYW5n' in mailbox.read_bytes()
        assert (Path(str(mailbox) + '.sbd') / 'Unterordner').exists()
        assert list((home / '.thunderbird/PST-Import').glob('*/Inbox'))
        assert 'OST' in (home / 'Umzug-Windows/Mail-Konten.txt').read_text()
        again = m.copy_manifest(manifest, home, source_root=windows)
        assert not again['errors'], again
        (store / 'Posteingang/link.eml').symlink_to(base / 'outside')
        assert m.copy_manifest(manifest, home, source_root=windows)['errors']
        bad = m.scan_tree(windows)
        pst = next(i for i in bad['profiles'][0]['items'] if i['kind'] == 'Outlook PST')
        pst['source'] = 'Users/Äda/Documents/Outlook Files/../../../../escape.pst'
        try:
            m.copy_manifest(bad, home, source_root=windows)
            assert False, 'path traversal accepted'
        except ValueError:
            pass
    finally:
        os.environ['PATH'] = old_path

with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    windows, home = base / 'win', base / 'home'
    home.mkdir()
    outlook = windows / 'Users/Bob/Documents/Outlook Files'
    outlook.mkdir(parents=True)
    (outlook / 'broken.pst').write_bytes(b'bad')
    fakebin = base / 'bin'
    fakebin.mkdir()
    script = fakebin / 'readpst'
    script.write_text('#!/bin/sh\necho conversion-failed >&2\nexit 1\n')
    script.chmod(0o755)
    old_path = os.environ['PATH']
    os.environ['PATH'] = str(fakebin) + os.pathsep + old_path
    try:
        result = m.copy_manifest(m.scan_tree(windows, locale='en'), home, source_root=windows)
        assert not result['errors'] and any('conversion-failed' in w['error'] for w in result['warnings'])
        assert not list(home.glob('.readpst-*'))
        assert 'Mail accounts' in (home / 'Umzug-Windows/Mail-Konten.txt').read_text()
    finally:
        os.environ['PATH'] = old_path
