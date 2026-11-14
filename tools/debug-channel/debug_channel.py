#!/usr/bin/env python3
"""Start and control a temporary LAN debug channel for WinDoesNot test systems."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from server import DebugChannelServer

HERE = Path(__file__).resolve().parent
STATE_NAME = "debug-channel-session.json"


def runtime_root() -> Path:
    value = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(value) if value else Path(tempfile.gettempdir())
    if not root.is_dir() or not os.access(root, os.W_OK | os.X_OK):
        raise RuntimeError("XDG_RUNTIME_DIR ist nicht beschreibbar")
    return root


def endpoint(host: str, port: int) -> str:
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{port}"


def render(template: Path, values: dict[str, str]) -> str:
    content = template.read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace(f"@@{key}@@", value)
    if "@@" in content:
        raise RuntimeError(f"Nicht ersetzter Platzhalter in {template.name}")
    return content


def curl_request(url: str, data: bytes | None = None, timeout: float = 10,
                 content_type: str = "application/octet-stream") -> bytes:
    request = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    if data is not None:
        request.add_header("Content-Type", content_type)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def load_state() -> dict:
    path = runtime_root() / STATE_NAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError("Kein aktiver Kanal gefunden; zuerst 'debug-channel start' ausführen") from exc


def new_command(state: dict, command: str) -> str:
    payload = json.dumps({"command": command}).encode()
    return curl_request(f"{state['base_url']}/{state['token']}/queue", payload,
                       timeout=10, content_type="application/json").decode()


def wait_output(state: dict, command_id: str, wait_seconds: float) -> bytes:
    deadline = time.monotonic() + wait_seconds
    url = f"{state['base_url']}/{state['token']}/out/{command_id}"
    while time.monotonic() < deadline:
        try:
            return curl_request(url, timeout=5)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    raise TimeoutError(f"Keine Agent-Ausgabe innerhalb von {wait_seconds:g} Sekunden (ID {command_id})")


def emit_agent_output(output: bytes) -> int:
    status_line, separator, body = output.partition(b"\n")
    if separator and status_line.startswith(b"exit status: "):
        try:
            status = int(status_line.removeprefix(b"exit status: "))
        except ValueError:
            status = 1
        sys.stdout.buffer.write(body)
        return status if 0 <= status <= 255 else 1
    sys.stdout.buffer.write(output)
    return 0


def command_run(args):
    state = load_state()
    command_id = new_command(state, args.command)
    try:
        output = wait_output(state, command_id, args.timeout)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return emit_agent_output(output)


def checked_target(target: str) -> str:
    if "\x00" in target:
        raise ValueError("Zielpfad enthält ein ungültiges NUL-Zeichen")
    if target.startswith("~/"):
        target = "/home/liveuser/" + target[2:]
    elif not target.startswith("/"):
        target = "/home/liveuser/" + target
    if any(part == ".." for part in Path(target).parts):
        raise ValueError("Zielpfad darf kein '..' enthalten")
    return target


def send_file(state: dict, path: Path, remote_name: str) -> None:
    # /file stages an authenticated download for the test device.
    request = urllib.request.Request(
        f"{state['base_url']}/{state['token']}/file/{remote_name}",
        data=path.read_bytes(), method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 201:
            raise RuntimeError(f"Server lehnte Upload ab: HTTP {response.status}")


def remote_download_command(state: dict, remote_name: str, target: str) -> str:
    dest = checked_target(target)
    temp_path = "/tmp/wdn-dl-" + remote_name
    url = f"{state['base_url']}/{state['token']}/dl/{remote_name}"
    return (f"curl --fail --silent --show-error --max-time 30 {shlex.quote(url)} -o {shlex.quote(temp_path)} "
            f"&& install -D -m 0644 {shlex.quote(temp_path)} {shlex.quote(dest)} "
            f"&& chown liveuser:liveuser {shlex.quote(dest)} "
            f"&& rm -f {shlex.quote(temp_path)}")


def command_push(args):
    source = Path(args.file).resolve(strict=True)
    if not source.is_file():
        raise ValueError("push erwartet eine reguläre Datei")
    target = checked_target(args.target)
    state = load_state()
    remote_name = "upload-" + os.urandom(16).hex()
    send_file(state, source, remote_name)
    command_id = new_command(state, remote_download_command(state, remote_name, target))
    output = wait_output(state, command_id, args.timeout)
    status = emit_agent_output(output)
    if status == 0:
        print(f"Datei auf Testgerät abgelegt: {target}", file=sys.stderr)
    return status


def make_patch_archive(paths: list[str], destination: Path) -> None:
    seen = set()
    with tarfile.open(destination, "w") as archive:
        for raw in paths:
            path = Path(raw).resolve(strict=True)
            if not path.is_file():
                raise ValueError(f"Nur einzelne reguläre Dateien sind erlaubt: {raw}")
            name = path.name
            if name in seen:
                raise ValueError(f"Doppelter Dateiname im Patch: {name}")
            seen.add(name)
            archive.add(path, arcname=name, recursive=False)


def command_hot_patch(args):
    state = load_state()
    with tempfile.TemporaryDirectory(prefix="wdn-hot-patch-") as scratch:
        archive = Path(scratch) / "quickshell-patch.tar"
        make_patch_archive(args.files, archive)
        remote_name = "patch-" + os.urandom(16).hex()
        send_file(state, archive, remote_name)
        target = "/tmp/wdn-quickshell-patch-" + os.urandom(6).hex() + ".tar"
        command_id = new_command(state, remote_download_command(state, remote_name, target))
        status = emit_agent_output(wait_output(state, command_id, args.timeout))
        if status:
            return status
        config = "/home/liveuser/.config/quickshell"
        apply = (f"mkdir -p {shlex.quote(config)} && tar -xf {shlex.quote(target)} -C {shlex.quote(config)} "
                 f"&& chown -R liveuser:liveuser {shlex.quote(config)} "
                 f"&& rm -f {shlex.quote(target)} && G windoesnot-restart-shell")
        command_id = new_command(state, apply)
        return emit_agent_output(wait_output(state, command_id, args.timeout))


def command_start(args):
    try:
        ip = ipaddress.ip_address(args.bind)
    except ValueError:
        ip = None
    if args.bind in ("0.0.0.0", "::", "") and not args.allow_any:
        raise ValueError("Wildcard-Bind braucht die ausdrückliche Option --allow-any")
    if ip is not None and ip.is_unspecified and not args.allow_any:
        raise ValueError("Wildcard-Bind braucht die ausdrückliche Option --allow-any")
    if ip is not None and ip.is_unspecified and not args.advertise:
        raise ValueError("Bei Wildcard-Bind muss --advertise die vom Testgerät erreichbare Adresse angeben")
    if not ip and not args.allow_any:
        try:
            address = socket.gethostbyname(args.bind)
        except OSError as exc:
            raise ValueError(f"Bind-Adresse nicht auflösbar: {args.bind}") from exc
        if address == "0.0.0.0":
            raise ValueError("Wildcard-Bind braucht die ausdrückliche Option --allow-any")
    if args.runtime <= 0:
        raise ValueError("--runtime muss positiv sein")
    if args.max_upload_bytes <= 0:
        raise ValueError("--max-upload-bytes muss positiv sein")

    runtime = runtime_root()
    if runtime.resolve().is_relative_to(HERE.parents[1]):
        raise ValueError("XDG_RUNTIME_DIR muss außerhalb des Repositorys liegen")
    token = os.urandom(24).hex()
    base = Path(args.data_dir).expanduser().resolve() if args.data_dir else Path(
        tempfile.mkdtemp(prefix="windoesnot-debug-channel-", dir=runtime))
    base.mkdir(parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    keydir = Path(tempfile.mkdtemp(prefix="wdn-debug-key-", dir=runtime))
    private_key = keydir / "id_ed25519"
    try:
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C",
                        "windoesnot-debug-channel", "-f", str(private_key)], check=True)
        public_key = (keydir / "id_ed25519.pub").read_text(encoding="utf-8").strip()
        server = DebugChannelServer(args.bind, args.port, base, token, args.max_upload_bytes)
        _actual_host, actual_port = server.address[:2]
        # The advertised address defaults to the bind address; a host label can
        # override it when binding to a concrete interface name.
        advertised = args.advertise or args.bind
        base_url = endpoint(advertised, actual_port)
        marker = "windoesnot-debug-channel-" + token[:16]
        values = {
            "SERVER_URL": shlex.quote(base_url),
            "TOKEN": shlex.quote(token),
            "PUBLIC_KEY": shlex.quote(public_key),
            "MARKER": shlex.quote(marker),
            "RUN_SECONDS": str(int(args.runtime)),
        }
        (base / "files" / "s").write_text(render(HERE / "s.in", values), encoding="utf-8")
        (base / "files" / "agent.sh").write_text(render(HERE / "agent.sh.in", values), encoding="utf-8")
        state = {"base_url": base_url, "token": token, "base_dir": str(base),
                 "expires_at": time.time() + args.runtime}
        state_path = runtime / STATE_NAME
        tmp_state = state_path.with_suffix(".tmp")
        tmp_state.write_text(json.dumps(state), encoding="utf-8")
        os.chmod(tmp_state, 0o600)
        tmp_state.replace(state_path)

        print(f"Debug-Kanal läuft unter {base_url} für höchstens {int(args.runtime)} Sekunden.")
        print(f"Token: {token}")
        print(f"Temporärer SSH-Schlüssel (bis Server-Ende): {private_key}")
        print(f"SSH-Befehl nach Anzeige der Testgeräte-Adresse: ssh -i {shlex.quote(str(private_key))} liveuser@<IP>")
        print(f"Daten, Queue und Zugriffslog: {base}")
        print("Auf dem Testgerät als liveuser an der Text-Konsole (Strg+Alt+F2) ausführen:")
        print(f"  curl --fail --silent --show-error {shlex.quote(base_url + '/' + token + '/s')} | sh")
        stop = __import__("threading").Event()
        previous = {}

        def request_stop(signum, _frame):
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, request_stop)
        thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stop.wait(args.runtime)
        server.shutdown()
        thread.join(timeout=3)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        try:
            if json.loads(state_path.read_text()).get("token") == token:
                state_path.unlink()
        except (OSError, ValueError):
            pass
        print("Debug-Kanal beendet; temporärer SSH-Schlüssel wird entfernt.")
    finally:
        shutil.rmtree(keydir, ignore_errors=True)
    return 0


def parser():
    root = argparse.ArgumentParser(prog="debug-channel", description="Temporärer WinDoesNot LAN-Debug-Kanal")
    commands = root.add_subparsers(dest="subcommand", required=True)
    start = commands.add_parser("start", help="Token, SSH-Schlüssel und Server starten")
    start.add_argument("--bind", required=True, help="Konkrete lokale Bind-Adresse")
    start.add_argument("--advertise", help="Vom Testgerät erreichbare Server-Adresse")
    start.add_argument("--port", type=int, default=8000)
    start.add_argument("--runtime", type=int, default=7200, help="Maximale Laufzeit in Sekunden (Standard: 2 h)")
    start.add_argument("--data-dir", help="Queue, Uploads, Ausgaben und Zugrifflog")
    start.add_argument("--max-upload-bytes", type=int, default=5_000_000)
    start.add_argument("--allow-any", action="store_true", help="Wildcard-Bind (0.0.0.0/::) ausdrücklich erlauben")
    start.set_defaults(func=command_start)

    run = commands.add_parser("run", help="Befehl einstellen und Ausgabe abwarten")
    run.add_argument("command")
    run.add_argument("--timeout", type=float, default=240)
    run.set_defaults(func=command_run)

    push = commands.add_parser("push", help="Datei auf das Gerät übertragen")
    push.add_argument("file")
    push.add_argument("target")
    push.add_argument("--timeout", type=float, default=240)
    push.set_defaults(func=command_push)

    patch = commands.add_parser("hot-patch", help="Quickshell-Dateien übertragen und Shell neu starten")
    patch.add_argument("files", nargs="+")
    patch.add_argument("--timeout", type=float, default=240)
    patch.set_defaults(func=command_hot_patch)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, RuntimeError, ValueError, urllib.error.URLError, TimeoutError,
            subprocess.CalledProcessError) as exc:
        print(f"debug-channel: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
