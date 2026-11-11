#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import uuid
from urllib.parse import urlparse
import websockets

URLS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
TOKEN = sys.argv[2] if len(sys.argv) > 2 else ""

TOKEN_FILE = os.path.expanduser("~/.config/quickshell/copilot/openclaw-token.txt")
os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)

if not TOKEN and os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    print(json.dumps({"models": [], "results": [{"url": u, "status": "error", "count": 0, "error": "No token"} for u in URLS]}))
    sys.exit(0)


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


async def get_models(url: str, token: str):
    try:
        origin = origin_for(url)
        async with websockets.connect(url, origin=origin, open_timeout=10) as ws:
            # 1) connect.challenge
            first = await asyncio.wait_for(ws.recv(), timeout=5)
            first_msg = json.loads(first)
            if not (first_msg.get("type") == "event" and first_msg.get("event") == "connect.challenge"):
                return {"url": url, "status": "error", "count": 0, "models": [], "error": "unexpected first frame"}

            # 2) connect
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
                return {
                    "url": url,
                    "status": "error",
                    "count": 0,
                    "models": [],
                    "error": err.get("message", "connect failed"),
                }

            # 3) models.list
            list_id = str(uuid.uuid4())
            await ws.send(json.dumps({"type": "req", "id": list_id, "method": "models.list", "params": {}}))
            list_res = await recv_until_response(ws, list_id)

            if not list_res.get("ok"):
                err = list_res.get("error", {})
                return {
                    "url": url,
                    "status": "error",
                    "count": 0,
                    "models": [],
                    "error": err.get("message", "models.list failed"),
                }

            models = (list_res.get("payload") or {}).get("models") or []
            return {"url": url, "status": "ok", "count": len(models), "models": models}

    except asyncio.TimeoutError:
        return {"url": url, "status": "error", "count": 0, "models": [], "error": "timeout"}
    except Exception as e:
        return {"url": url, "status": "error", "count": 0, "models": [], "error": f"{type(e).__name__}: {e}"}


async def main():
    if not URLS:
        print(json.dumps({"models": [], "results": []}))
        return

    # Save token on first successful use
    if TOKEN and not os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(TOKEN)
        except:
            pass

    tasks = [get_models(url, TOKEN) for url in URLS]
    results = await asyncio.gather(*tasks)

    all_models = []
    status_results = []

    for r in results:
        status_results.append({"url": r["url"], "status": r["status"], "count": r.get("count", 0), "error": r.get("error")})
        for m in r.get("models", []):
            # Pass through all model fields from OpenClaw API
            model_entry = {
                "name": m.get("name", m.get("id", "unknown")),
                "url": r["url"],
                "id": m.get("id", ""),
                "provider": m.get("provider", ""),
                "contextWindow": m.get("contextWindow", 0),
                "reasoning": m.get("reasoning", False)
            }
            all_models.append(model_entry)

    print(json.dumps({"models": all_models, "results": status_results}))


if __name__ == "__main__":
    asyncio.run(main())
