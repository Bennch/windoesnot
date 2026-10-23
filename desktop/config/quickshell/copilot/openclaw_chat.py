#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import uuid
from urllib.parse import urlparse
import websockets

# Args: model, messages_json, url, token
MODEL = sys.argv[1] if len(sys.argv) > 1 else ""
MESSAGES_JSON = sys.argv[2] if len(sys.argv) > 2 else "[]"
URL = sys.argv[3] if len(sys.argv) > 3 else "ws://127.0.0.1:18789"
TOKEN = sys.argv[4] if len(sys.argv) > 4 else ""

TOKEN_FILE = os.path.expanduser("~/.config/quickshell/copilot/openclaw-token.txt")
if not TOKEN and os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        TOKEN = f.read().strip()

MESSAGES = json.loads(MESSAGES_JSON)


def origin_for(ws_url: str) -> str:
    p = urlparse(ws_url)
    if not p.hostname:
        return "http://127.0.0.1:18789"
    scheme = "https" if p.scheme == "wss" else "http"
    port = p.port if p.port is not None else (443 if p.scheme == "wss" else 80)
    return f"{scheme}://{p.hostname}:{port}"


async def main():
    try:
        origin = origin_for(URL)
        async with websockets.connect(URL, origin=origin, open_timeout=10) as ws:
            # 1) Connect
            first = await asyncio.wait_for(ws.recv(), timeout=5)
            first_msg = json.loads(first)
            if not (first_msg.get("type") == "event" and first_msg.get("event") == "connect.challenge"):
                print(f"ERROR: Unexpected first frame", file=sys.stderr)
                return

            connect_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req",
                "id": connect_id,
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {"id": "openclaw-control-ui", "version": "1.0.0", "platform": "linux", "mode": "webchat"},
                    "role": "operator",
                    "scopes": ["operator.read", "operator.write", "operator.admin"],
                    "auth": {"token": TOKEN},
                },
            }))

            # Wait for connect response
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if msg.get("type") == "res" and msg.get("id") == connect_id:
                    if not msg.get("ok"):
                        print(f"ERROR: Connect failed: {msg.get('error')}", file=sys.stderr)
                        return
                    break

            # 2) Create session
            create_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req",
                "id": create_id,
                "method": "sessions.create",
                "params": {
                    "model": MODEL,
                },
            }))

            session_id = None
            session_key = None
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if msg.get("type") == "res" and msg.get("id") == create_id:
                    if not msg.get("ok"):
                        print(f"ERROR: Session create failed: {msg.get('error')}", file=sys.stderr)
                        return
                    payload = msg.get("payload", {})
                    session_id = payload.get("sessionId") or payload.get("id")
                    session_key = payload.get("key") or payload.get("sessionKey") or session_id
                    break

            if not session_id:
                print("ERROR: No sessionId returned", file=sys.stderr)
                return

            # 3) Subscribe to messages
            sub_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req",
                "id": sub_id,
                "method": "sessions.messages.subscribe",
                "params": {"key": session_key},
            }))

            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if msg.get("type") == "res" and msg.get("id") == sub_id:
                    if not msg.get("ok"):
                        print(f"ERROR: Subscribe failed: {msg.get('error')}", file=sys.stderr)
                        return
                    break

            # 4) Send user message
            send_id = str(uuid.uuid4())
            user_msg = MESSAGES[-1]["content"] if len(MESSAGES) > 0 else "Hello"
            await ws.send(json.dumps({
                "type": "req",
                "id": send_id,
                "method": "sessions.send",
                "params": {
                    "key": session_key,
                    "message": user_msg,
                },
            }))

            # 5) Stream response
            done = False
            while not done:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))

                # Response to send request
                if msg.get("type") == "res" and msg.get("id") == send_id:
                    if not msg.get("ok"):
                        print(f"ERROR: Send failed: {msg.get('error')}", file=sys.stderr)
                        return
                    continue

                # Message events
                if msg.get("type") == "event":
                    event = msg.get("event", "")
                    payload = msg.get("payload", {})

                    if event == "agent":
                        # Agent event - check stream type
                        stream = payload.get("stream")
                        data = payload.get("data", {})

                        if stream == "assistant":
                            # Streaming token
                            delta = data.get("delta", "")
                            if delta:
                                print(delta, end="", flush=True)

                        elif stream == "lifecycle":
                            # Lifecycle event
                            phase = data.get("phase")
                            if phase == "end":
                                # Done streaming
                                done = True
                                print("", flush=True)  # Newline at end

                    elif "error" in event:
                        print(f"\nERROR: {payload}", file=sys.stderr)
                        done = True

    except asyncio.TimeoutError:
        print("\nERROR: Timeout", file=sys.stderr)
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
