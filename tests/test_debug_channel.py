#!/usr/bin/env python3
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "debug-channel"
sys.path.insert(0, str(TOOL))
from server import DebugChannelServer  # noqa: E402
from debug_channel import emit_agent_output, render  # noqa: E402


class DebugChannelHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.token = "a" * 48
        (self.base / "files").mkdir()
        (self.base / "files" / "s").write_text("echo setup")
        try:
            self.server = DebugChannelServer("127.0.0.1", 0, self.base, self.token, 256)
        except PermissionError as exc:
            self.skipTest(f"Sandbox verbietet Loopback-Sockets: {exc}")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, data=None, method=None):
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        return urllib.request.urlopen(req, timeout=2)

    def test_queue_is_delivered_and_output_can_be_read(self):
        payload = json.dumps({"command": "printf 'safe output'"}).encode()
        with self.request(f"/{self.token}/queue", payload, "POST") as response:
            command_id = response.read().decode()
            self.assertEqual(response.status, 201)
        with self.request(f"/{self.token}/cmd") as response:
            message = response.read().decode()
        self.assertEqual(message, command_id + "\nprintf 'safe output'")
        self.assertFalse(list((self.base / "queue").glob("*.json")))
        with self.request(f"/{self.token}/out/{command_id}", b"result", "POST") as response:
            self.assertEqual(response.status, 201)
        with self.request(f"/{self.token}/out/{command_id}") as response:
            self.assertEqual(response.read(), b"result")

    def test_upload_and_tokenized_download(self):
        with self.request(f"/{self.token}/file/payload-1", b"payload", "POST") as response:
            self.assertEqual(response.status, 201)
        with self.request(f"/{self.token}/dl/payload-1") as response:
            self.assertEqual(response.read(), b"payload")

    def test_wrong_token_is_rejected(self):
        for method, path, data in (
            (None, f"/{'b' * 48}/s", None),
            ("POST", f"/{'b' * 48}/queue", b'{"command":"id"}'),
        ):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.request(path, data, method)
            self.assertEqual(caught.exception.code, 403)

    def test_upload_limit_and_path_validation(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(f"/{self.token}/file/large", b"x" * 257, "POST")
        self.assertEqual(caught.exception.code, 413)
        for path in (f"/{self.token}/up/../../escape", f"/{self.token}/out/a%2F..%2Fbad"):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.request(path, b"x", "POST")
            self.assertEqual(caught.exception.code, 400)
        self.assertFalse((self.base.parent / "escape").exists())


class DebugChannelHandlerUnitTests(unittest.TestCase):
    """Exercise the real HTTP handlers even where sandbox policy blocks sockets."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

        class FakeHTTPServer:
            def __init__(inner, address, handler):
                inner.server_address = (address[0], address[1])
                inner.handler_class = handler

            def server_close(inner):
                pass

        with patch("server.http.server.ThreadingHTTPServer", FakeHTTPServer):
            self.server = DebugChannelServer("127.0.0.1", 8000, self.base, "c" * 48, 256)
        self.handler_class = self.server.httpd.handler_class

    def tearDown(self):
        self.temp.cleanup()

    def dispatch(self, method, path, data=b""):
        handler = self.handler_class.__new__(self.handler_class)
        handler.path = path
        handler.headers = {"Content-Length": str(len(data))}
        handler.rfile = io.BytesIO(data)
        handler.client_address = ("127.0.0.1", 12345)
        response = {}
        handler.reply = lambda status, body=b"": response.update(status=status, body=body)
        getattr(handler, method)()
        return response["status"], response["body"]

    def test_queue_output_upload_token_and_path_guards_without_socket(self):
        token = "c" * 48
        status, command_id = self.dispatch("do_POST", f"/{token}/queue", b'{"command":"id"}')
        self.assertEqual(status, 201)
        status, queued = self.dispatch("do_GET", f"/{token}/cmd")
        self.assertEqual(status, 200)
        self.assertEqual(queued, command_id + b"\nid")
        self.assertEqual(self.dispatch("do_POST", f"/{token}/out/{command_id.decode()}", b"result"), (201, b"ok"))
        self.assertEqual(self.dispatch("do_GET", f"/{token}/out/{command_id.decode()}"), (200, b"result"))
        self.assertEqual(self.dispatch("do_POST", f"/{token}/file/patch-1", b"patch"), (201, b"ok"))
        self.assertEqual(self.dispatch("do_GET", f"/{token}/dl/patch-1"), (200, b"patch"))
        self.assertEqual(self.dispatch("do_GET", f"/{'d' * 48}/cmd")[0], 403)
        self.assertEqual(self.dispatch("do_POST", f"/{token}/up/../../escape", b"x")[0], 400)
        self.assertEqual(self.dispatch("do_POST", f"/{token}/out/a%2F..%2Fbad", b"x")[0], 400)
        self.assertFalse((self.base.parent / "escape").exists())

    def test_access_log_redacts_bearer_token(self):
        handler = self.handler_class.__new__(self.handler_class)
        handler.client_address = ("127.0.0.1", 12345)
        handler.log_message("request %s", "/" + "c" * 48 + "/cmd")
        log = (self.base / "access.log").read_text()
        self.assertNotIn("c" * 48, log)
        self.assertIn("<token>", log)

    def test_payload_limit_without_socket(self):
        status, _ = self.dispatch("do_POST", f"/{'c' * 48}/file/large", b"x" * 257)
        self.assertEqual(status, 413)


class DebugChannelGeneratorTests(unittest.TestCase):
    def test_rendered_setup_and_agent_have_no_placeholders_and_parse(self):
        values = {
            "SERVER_URL": "'http://192.0.2.4:8000'",
            "TOKEN": "'abc123'",
            "PUBLIC_KEY": "'ssh-ed25519 AAAA test-key'",
            "MARKER": "'windoesnot-debug-channel-abc'",
            "RUN_SECONDS": "7200",
        }
        for name, shell in (("s.in", "sh"), ("agent.sh.in", "bash")):
            output = render(TOOL / name, values)
            self.assertNotIn("@@", output)
            with tempfile.NamedTemporaryFile("w", delete=False) as f:
                f.write(output)
                temp_path = f.name
            try:
                check = subprocess.run([shell, "-n", temp_path], capture_output=True, text=True)
                self.assertEqual(check.returncode, 0, check.stderr)
            finally:
                os.unlink(temp_path)

    def test_agent_status_is_returned_and_removed_from_output(self):
        class Stdout:
            def __init__(self):
                self.data = b""

            def write(self, value):
                self.data += value

        import debug_channel
        original = debug_channel.sys.stdout
        output = Stdout()
        try:
            debug_channel.sys.stdout = type("BinaryStdout", (), {"buffer": output})()
            self.assertEqual(emit_agent_output(b"exit status: 7\nproblem\n"), 7)
            self.assertEqual(output.data, b"problem\n")
        finally:
            debug_channel.sys.stdout = original


if __name__ == "__main__":
    unittest.main()
