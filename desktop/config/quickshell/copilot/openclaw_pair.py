#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import uuid
from urllib.parse import urlparse

import websockets

url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:18789"
token = sys.argv[2] if len(sys.argv) > 2 else ""

token_file = os.path.expanduser("~/.config/quickshell/copilot/openclaw-token.txt")
os.makedirs(os.path.dirname(token_file), exist_ok=True)

if not token and os.path.exists(token_file):
    with open(token_file, "r", encoding="utf-8") as f:
        token = f.read().strip()

if not token:
    print(json.dumps({"status": "error", "message": "No token provided"}))
    sys.exit(1)


def origin_for(ws_url: str) -> str:
    p = urlparse(ws_url)
    if not p.hostname:
        return "http://127.0.0.1:18789"
    scheme = "https" if p.scheme == "wss" else "http"
    port = p.port if p.port is not None else (443 if p.scheme == "wss" else 80)
    return f"{scheme}://{p.hostname}:{port}"


async def recv_until_response(ws, req_id: str, timeout: float = 10.0):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") == "res" and msg.get("id") == req_id:
            return msg


async def connect():
    try:
        origin = origin_for(url)
        async with websockets.connect(url, origin=origin, open_timeout=10) as ws:
            first = await asyncio.wait_for(ws.recv(), timeout=5)
            first_msg = json.loads(first)

            if not (
                first_msg.get("type") == "event"
                and first_msg.get("event") == "connect.challenge"
            ):
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "message": f"Unexpected first frame: {first_msg}",
                        }
                    )
                )
                return

            connect_id = str(uuid.uuid4())
            connect_frame = {
                "type": "req",
                "id": connect_id,
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id": "openclaw-control-ui",
                        "version": "1.0.0",
                        "platform": "linux",
                        "mode": "webchat",
                    },
                    "role": "operator",
                    "scopes": ["operator.read", "operator.write", "operator.admin"],
                    "auth": {"token": token},
                },
            }

            await ws.send(json.dumps(connect_frame))
            connect_res = await recv_until_response(ws, connect_id)

            if not connect_res.get("ok"):
                err = connect_res.get("error", {})
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "phase": "connect",
                            "message": err.get("message", "Connection failed"),
                            "code": err.get("code", ""),
                            "details": err.get("details", {}),
                        }
                    )
                )
                return

            list_id = str(uuid.uuid4())
            await ws.send(
                json.dumps(
                    {
                        "type": "req",
                        "id": list_id,
                        "method": "models.list",
                        "params": {},
                    }
                )
            )
            list_res = await recv_until_response(ws, list_id)

            if not list_res.get("ok"):
                err = list_res.get("error", {})
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "phase": "models.list",
                            "message": err.get("message", "models.list failed"),
                            "code": err.get("code", ""),
                            "details": err.get("details", {}),
                        }
                    )
                )
                return

            with open(token_file, "w", encoding="utf-8") as f:
                f.write(token)

            models = (list_res.get("payload") or {}).get("models") or []
            print(
                json.dumps(
                    {
                        "status": "success",
                        "message": "Connected + models.list OK",
                        "modelCount": len(models),
                        "models": [m.get("name", m.get("id", "unknown")) for m in models],
                    }
                )
            )

    except asyncio.TimeoutError:
        print(json.dumps({"status": "error", "message": "Timeout waiting for response"}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"{type(e).__name__}: {str(e)}"}))


asyncio.run(connect())
