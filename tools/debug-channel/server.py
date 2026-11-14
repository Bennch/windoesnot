#!/usr/bin/env python3
"""Token-protected, standard-library HTTP server for the debug channel."""
from __future__ import annotations

import hmac
import http.server
import json
import re
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
ID_RE = re.compile(r"[a-f0-9]{32}\Z")


class DebugChannelServer:
    def __init__(self, bind: str, port: int, base: Path, token: str, max_upload: int):
        self.base = Path(base)
        self.token = token
        self.max_upload = max_upload
        for name in ("queue", "out", "uploads", "files"):
            (self.base / name).mkdir(parents=True, exist_ok=True)

        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = "WinDoesNotDebugChannel/1"

            def log_message(self, fmt, *args):
                message = fmt % args
                message = message.replace(outer.token, "<token>")
                line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {self.client_address[0]} {message}\n"
                with (outer.base / "access.log").open("a", encoding="utf-8") as log:
                    log.write(line)

            def reply(self, status: int, body: bytes = b""):
                self.send_response(status)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def route(self):
                path = urlsplit(self.path).path
                pieces = path.split("/")
                if len(pieces) < 3 or not hmac.compare_digest(pieces[1], outer.token):
                    return None, None
                return pieces[2], pieces[3:]

            def do_GET(self):
                action, args = self.route()
                if action is None:
                    return self.reply(403, b"forbidden")
                if action in ("s", "agent.sh") and not args:
                    candidate = outer.base / "files" / action
                    if candidate.is_file():
                        return self.reply(200, candidate.read_bytes())
                if action == "cmd" and not args:
                    queue = sorted((outer.base / "queue").glob("*.json"), key=lambda p: p.name)
                    if not queue:
                        return self.reply(200)
                    item = queue[0]
                    try:
                        payload = json.loads(item.read_text(encoding="utf-8"))
                        item.unlink()
                    except (OSError, ValueError):
                        return self.reply(500, b"queue error")
                    return self.reply(200, (payload["id"] + "\n" + payload["command"]).encode())
                if action == "dl" and len(args) == 1 and NAME_RE.fullmatch(args[0]):
                    candidate = outer.base / "files" / args[0]
                    if candidate.is_file():
                        return self.reply(200, candidate.read_bytes())
                if action == "out" and len(args) == 1 and ID_RE.fullmatch(args[0]):
                    candidate = outer.base / "out" / args[0]
                    if candidate.is_file():
                        return self.reply(200, candidate.read_bytes())
                return self.reply(404, b"not found")

            def do_POST(self):
                action, args = self.route()
                if action is None:
                    return self.reply(403, b"forbidden")
                if action not in ("queue", "out", "up", "file") or (action == "queue" and args):
                    return self.reply(404, b"not found")
                if action in ("out", "up", "file") and (len(args) != 1 or not NAME_RE.fullmatch(args[0])):
                    return self.reply(400, b"invalid name")
                try:
                    length = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    return self.reply(400, b"invalid content length")
                if length < 0:
                    return self.reply(411, b"content length required")
                if length > outer.max_upload:
                    return self.reply(413, b"payload too large")
                body = self.rfile.read(length)
                if len(body) != length:
                    return self.reply(400, b"incomplete body")
                if action == "queue":
                    try:
                        payload = json.loads(body)
                        command = payload["command"]
                        if not isinstance(command, str) or not command or len(command.encode()) > 65536:
                            raise ValueError
                    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                        return self.reply(400, b"invalid command")
                    command_id = __import__("secrets").token_hex(16)
                    queue_name = f"{time.time_ns():020d}-{command_id}"
                    tmp = outer.base / "queue" / (queue_name + ".tmp")
                    tmp.write_text(json.dumps({"id": command_id, "command": command}), encoding="utf-8")
                    tmp.replace(outer.base / "queue" / (queue_name + ".json"))
                    return self.reply(201, command_id.encode())
                folder = {"out": "out", "up": "uploads", "file": "files"}[action]
                destination = outer.base / folder / args[0]
                tmp = destination.with_suffix(destination.suffix + ".tmp")
                tmp.write_bytes(body)
                tmp.replace(destination)
                return self.reply(201, b"ok")

        server_class = type("BoundThreadingHTTPServer", (http.server.ThreadingHTTPServer,), {
            "address_family": socket.AF_INET6 if ":" in bind else socket.AF_INET,
        })
        self.httpd = server_class((bind, port), Handler)
        self.httpd.daemon_threads = True
        self.httpd.allow_reuse_address = True

    @property
    def address(self):
        return self.httpd.server_address

    def serve_forever(self, poll_interval=0.2):
        self.httpd.serve_forever(poll_interval=poll_interval)

    def shutdown(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def run_server(server: DebugChannelServer, stop: threading.Event, duration: float):
    thread = threading.Thread(target=server.serve_forever, name="debug-channel", daemon=True)
    thread.start()
    stop.wait(duration)
    server.shutdown()
    thread.join(timeout=3)
