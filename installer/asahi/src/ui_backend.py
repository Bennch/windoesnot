"""Root-only, fixed-backend PTY bridge for the local macOS application."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import socket
import stat
import tempfile
import termios
from urllib.parse import urlparse


def validate_release(root):
    config = json.loads((root / 'release.json').read_text())
    if config.get('imageValidated') is not True:
        raise ValueError('No hardware-validated WinDoesNotMac image has been configured')
    for key in ('installerBase', 'repoBase'):
        value = urlparse(config.get(key, ''))
        if value.scheme != 'https' or not value.netloc or value.username or value.password:
            raise ValueError('Explicit HTTPS release endpoints are required')
    metadata = root / 'installer_data.json'
    if hashlib.sha256(metadata.read_bytes()).hexdigest() != config.get('metadataSha256'):
        raise ValueError('Bundled installer metadata checksum mismatch')
    choices = json.loads(metadata.read_text()).get('os_list', [])
    if not choices or any(not str(v.get('name', '')).startswith('WinDoesNotMac') for v in choices):
        raise ValueError('The app must offer only our own images')
    return config


def response(line):
    value = json.loads(line)
    if set(value) != {'text'} or not isinstance(value['text'], str):
        raise ValueError('Only a text response is accepted')
    text = value['text']
    if len(text) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError('Invalid response')
    return (text + '\n').encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gui-socket', required=True, type=Path)
    parser.add_argument('--gui-token', required=True)
    parser.add_argument('--gui-uid', required=True, type=int)
    parser.add_argument('--gui-language', choices=('de', 'en'), required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or args.gui_uid == 0:
        raise SystemExit('The bridge needs authorization from a regular macOS user')
    endpoint = args.gui_socket.resolve(strict=True)
    parent, target = endpoint.parent.stat(), endpoint.stat()
    if (parent.st_uid != args.gui_uid or stat.S_IMODE(parent.st_mode) != 0o700
            or target.st_uid != args.gui_uid or not stat.S_ISSOCK(target.st_mode)
            or stat.S_IMODE(target.st_mode) != 0o600 or len(args.gui_token) != 64):
        raise SystemExit('Invalid private GUI endpoint')
    root = Path(__file__).resolve().parent
    config = validate_release(root)
    peer = socket.socket(socket.AF_UNIX)
    peer.connect(str(endpoint))
    def send(value):
        nonlocal peer
        if peer is not None:
            try:
                peer.sendall((json.dumps(value, ensure_ascii=True) + '\n').encode())
            except OSError:
                peer.close()
                peer = None
    send({'type': 'auth', 'token': args.gui_token})
    # Work outside the signed application. Logs/firmware/cache must never modify it.
    with tempfile.TemporaryDirectory(prefix='windoesnot-install-') as work:
        work = Path(work)
        shutil.copytree(root, work / 'backend', symlinks=True)
        work = work / 'backend'
        child, master = pty.fork()
        if child == 0:
            os.chdir(work)
            attrs = termios.tcgetattr(0)
            attrs[3] &= ~(termios.ECHO | termios.ECHONL)
            termios.tcsetattr(0, termios.TCSANOW, attrs)
            os.environ.update(WINDOESNOT_GUI='1', WINDOESNOT_LANGUAGE=args.gui_language,
                              INSTALLER_BASE=config['installerBase'], REPO_BASE=config['repoBase'],
                              INSTALLER_DATA=(work / 'installer_data.json').as_uri())
            os.environ.pop('REPORT', None)
            os.environ.pop('REPORT_TAG', None)
            os.execv('/bin/sh', ['/bin/sh', './install.sh'])
        incoming, output = b'', b''
        waiting = False
        try:
            while True:
                ready, _, _ = select.select(([peer] if peer is not None else []) + [master], [], [])
                if peer is not None and peer in ready:
                    chunk = peer.recv(8192)
                    if not chunk:
                        # Drain the child without signaling it. If it reaches a
                        # prompt it waits; never guess an answer after GUI loss.
                        peer.close()
                        peer = None
                        continue
                    incoming += chunk
                    if len(incoming) > 16384:
                        raise ValueError('Oversized input')
                    while b'\n' in incoming:
                        line, incoming = incoming.split(b'\n', 1)
                        if not waiting:
                            raise ValueError('No response is pending')
                        os.write(master, response(line))
                        waiting = False
                if master in ready:
                    try:
                        chunk = os.read(master, 8192)
                    except OSError:
                        chunk = b''
                    if not chunk:
                        break
                    output += chunk
                    while b'\n' in output:
                        line, output = output.split(b'\n', 1)
                        text = line.decode('utf-8', errors='replace').rstrip('\r')
                        if text.startswith('@@WDN@@'):
                            event = json.loads(text[7:])
                            waiting = event.get('type') == 'prompt' or waiting
                            send(event)
                        elif text.strip():
                            send({'type': 'output', 'text': text})
                    if len(output) > 262144:
                        send({'type': 'output', 'text': output.decode('utf-8', errors='replace')})
                        output = b''
                    tail = output.decode('utf-8', errors='replace')
                    if not waiting and re.search(r'(?i)(password|passphrase|username|user name)[^\r\n:]*:\s*$', tail):
                        kind = 'password' if re.search(r'(?i)password|passphrase', tail) else 'text'
                        send({'type': 'prompt', 'kind': kind, 'label': tail, 'choices': []})
                        waiting = True
                        output = b''
            _, status = os.waitpid(child, 0)
            send({'type': 'exit', 'code': os.waitstatus_to_exitcode(status)})
        finally:
            os.close(master)
            if peer is not None:
                peer.close()


if __name__ == '__main__':
    main()
