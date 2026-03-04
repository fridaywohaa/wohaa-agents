#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Mission Control mini server (local-first, cross-device sync).

Serves:
- Static files from this directory (index.html)
- JSON state API:
  - GET  /api/state  -> returns persisted JSON
  - POST /api/state  -> replaces persisted JSON

Storage:
- data.json (same folder). Intended for LAN/Tailscale use.

Notes:
- No authentication (keep it on LAN/Tailscale only).
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data.json")
LOCK = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_state() -> dict:
    if not os.path.exists(DATA_PATH):
        return {"updatedAt": None, "eveningReviewLast": None, "todayPlanToday": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_state(state: dict) -> None:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_PATH)


def send_json(handler: SimpleHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    # Same-origin should be enough; keep permissive for iOS/Safari edge cases.
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(SimpleHTTPRequestHandler):
    # Python 3.14: SimpleHTTPRequestHandler supports directory=... via init

    def do_OPTIONS(self):
        # Minimal CORS preflight support
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/api/ping":
            return send_json(self, 200, {"ok": True, "ts": utc_now_iso()})
        if p.path == "/api/state":
            with LOCK:
                state = read_state()
            return send_json(self, 200, state)
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path)
        if p.path != "/api/state":
            return send_json(self, 404, {"error": "not_found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""

        try:
            incoming = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return send_json(self, 400, {"error": "invalid_json"})

        # Soft validation: only keep expected keys
        state = {
            "updatedAt": utc_now_iso(),
            "eveningReviewLast": incoming.get("eveningReviewLast"),
            "todayPlanToday": incoming.get("todayPlanToday"),
        }

        with LOCK:
            write_state(state)

        return send_json(self, 200, {"ok": True, "updatedAt": state["updatedAt"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8081)
    args = ap.parse_args()

    httpd = ThreadingHTTPServer((args.bind, args.port), lambda *a, **kw: Handler(*a, directory=HERE, **kw))
    print(f"Mission Control server running on http://{args.bind}:{args.port}/ (dir={HERE})")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
