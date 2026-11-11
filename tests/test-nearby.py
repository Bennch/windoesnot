#!/usr/bin/env python3
"""Host-safe LocalSend adapter checks. No listener or real desktop is started."""
import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('nearby', str(ROOT / 'desktop/bin/windoesnot-nearby'))
spec = importlib.util.spec_from_loader('nearby', loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class Nearby(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.downloads = self.root / 'downloads'
        self.downloads.mkdir()
        self.adapter = m.Adapter(self.root / 'state', self.downloads, emit=lambda _: None)
        self.peer = {'alias': 'Other computer', 'fingerprint': 'test-device', 'protocol': 'http', 'port': 53317}

    def transfer(self, content=b'hello', name='hello.txt', digest=None):
        files = m.manifest({'file': {'fileName': name, 'size': len(content), 'sha256': digest}})
        peer = self.adapter.remember(self.peer, '192.168.77.11')
        transfer = m.Transfer('receive', peer, files)
        transfer.status = 'transferring'
        self.adapter.incoming = transfer
        handler = object.__new__(m.Handler)
        handler.server = types.SimpleNamespace(adapter=self.adapter)
        handler.client_address = ('192.168.77.11', 50000)
        handler.headers = {'Content-Length': str(len(content))}
        handler.rfile = io.BytesIO(content)
        handler.responses = []
        handler.respond = lambda code, value=None: handler.responses.append((code, value))
        query = {'sessionId': transfer.id, 'fileId': 'file', 'token': files['file']['token']}
        return handler, transfer, query

    def test_metadata_rejects_paths_and_invalid_sizes(self):
        for name in ('../secret', '/etc/passwd', 'folder/file', 'folder\\file', '..', '.', 'bad\x00name', 'bad\nname'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                m.manifest({'id': {'fileName': name, 'size': 0}})
        for size in (-1, True, '10', 2**51):
            with self.subTest(size=size), self.assertRaises(ValueError):
                m.manifest({'id': {'fileName': 'okay', 'size': size}})
        with self.assertRaises(ValueError):
            m.manifest({'id': {'fileName': 'okay', 'size': 0, 'sha256': 'bad'}})

    def test_local_file_urls_and_command_metacharacters_are_data(self):
        file = self.root / 'a space $(not-a-command) ü.txt'
        file.write_text('test')
        self.assertEqual(m.local_paths([file.as_uri(), str(file)]), [file])
        with self.assertRaises(ValueError):
            m.local_paths(['file://remotehost/etc/passwd'])
        with self.assertRaises(ValueError):
            m.local_paths([str(self.root)])
        with patch.object(m.sys, 'argv', ['windoesnot-nearby', 'share', str(file)]), patch.object(m.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual(m.main(), 0)
            args = run.call_args.args[0]
            self.assertEqual(json.loads(args[-1]), [str(file)])
            self.assertIn('windoesnot-nearby', args)
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_receiving_default_and_personal_history(self):
        self.assertFalse(self.adapter.receiving)
        handler, transfer, query = self.transfer()
        handler.upload(self.adapter, query)
        restored = m.Adapter(self.root / 'state', self.downloads)
        self.assertFalse(restored.receiving)
        self.assertEqual(restored.history[-1]['status'], 'done')
        self.assertEqual((self.root / 'state/history.json').stat().st_mode & 0o777, 0o600)

    def test_unapproved_wrong_token_and_wrong_origin_cannot_write(self):
        for change in ('waiting', 'token', 'origin', 'session'):
            with self.subTest(change=change):
                handler, transfer, query = self.transfer()
                if change == 'waiting': transfer.status = 'waiting'
                if change == 'token': query['token'] = 'wrong'
                if change == 'origin': handler.client_address = ('192.168.77.12', 1)
                if change == 'session': query['sessionId'] = 'wrong'
                handler.upload(self.adapter, query)
                self.assertEqual(handler.responses[0][0], 403)
                self.assertEqual(list(self.downloads.iterdir()), [])

    def test_receiving_off_declines_without_prompt(self):
        handler, _, _ = self.transfer()
        self.adapter.incoming = None
        handler.read_json = lambda: {'info': self.peer, 'files': {'file': {'fileName': 'test', 'size': 1}}}
        handler.prepare(self.adapter)
        self.assertEqual(handler.responses[0][0], 403)
        self.assertIsNone(self.adapter.incoming)

    def test_size_mismatch_replay_and_symlink_collision(self):
        handler, transfer, query = self.transfer()
        handler.headers['Content-Length'] = '1000'
        handler.upload(self.adapter, query)
        self.assertEqual(handler.responses[0][0], 400)
        self.assertFalse(transfer.files['file']['claimed'])
        outside = self.root / 'personal'
        outside.write_text('keep')
        (self.downloads / 'hello.txt').symlink_to(outside)
        handler.headers['Content-Length'] = '5'
        handler.upload(self.adapter, query)
        self.assertEqual((self.downloads / 'hello (1).txt').read_bytes(), b'hello')
        self.assertEqual(outside.read_text(), 'keep')
        self.assertFalse(list(self.downloads.glob('*.part')))
        handler.upload(self.adapter, query)
        self.assertEqual(handler.responses[-1][0], 403)

    def test_checksum_failure_discards_partial_file(self):
        handler, transfer, query = self.transfer(digest=hashlib.sha256(b'different').hexdigest())
        with self.assertRaises(ValueError): handler.upload(self.adapter, query)
        self.assertEqual(handler.responses[0][0], 422)
        self.assertEqual(list(self.downloads.iterdir()), [])
        self.assertEqual(self.adapter.history[-1]['status'], 'failed')

    def test_cancel_during_upload_discards_partial_file(self):
        handler, transfer, query = self.transfer()
        class CancellingStream(io.BytesIO):
            def read(stream, count):
                self.adapter.cancel(transfer)
                return super().read(count)
        handler.rfile = CancellingStream(b'hello')
        with self.assertRaises(ValueError): handler.upload(self.adapter, query)
        self.assertEqual(list(self.downloads.iterdir()), [])
        self.assertEqual(self.adapter.history[-1]['status'], 'cancelled')
        # A sender's cancel HTTP request can follow the interrupted upload socket.
        handler, transfer, query = self.transfer()
        self.adapter.finish(transfer, 'failed')
        self.adapter.cancel(self.adapter.recent[transfer.id])
        self.assertEqual(self.adapter.history[-1]['status'], 'cancelled')
        self.assertEqual(sum(entry['id'] == transfer.id for entry in self.adapter.history), 1)


    def test_discovery_is_lan_only_and_bounded(self):
        self.assertEqual(self.adapter.remember(self.peer, '192.168.77.11')['alias'], 'Other computer')
        for address in ('8.8.8.8', '224.0.0.167', '0.0.0.0', '::1'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                self.adapter.remember(self.peer, address)
        with self.assertRaises(ValueError):
            self.adapter.remember({**self.peer, 'protocol': 'https'}, '192.168.77.11')
        for index in range(200):
            self.adapter.remember({**self.peer, 'fingerprint': str(index)}, '192.168.77.11')
        self.assertEqual(len(self.adapter.peers), 100)

    def test_https_pins_the_discovered_certificate(self):
        peer = {'id': 'a' * 64, 'protocol': 'https', 'address': '192.168.77.11', 'port': 53317}
        with patch.object(m.http.client, 'HTTPSConnection') as connection:
            connection.return_value.sock.getpeercert.return_value = b'other certificate'
            with self.assertRaisesRegex(ValueError, 'certificate'):
                self.adapter.connect(peer)
            connection.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
