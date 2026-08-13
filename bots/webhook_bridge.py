import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from dotenv import load_dotenv
from nexus_dispatch import NexusDispatch

load_dotenv()

BRIDGE_TOKEN = os.getenv("NEXUS_BRIDGE_TOKEN", "").strip()
PORT = int(os.getenv("NEXUS_BRIDGE_PORT", "8787"))


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not BRIDGE_TOKEN:
            return True
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {BRIDGE_TOKEN}"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._json(200, {"status": "ok", "service": "nexus-bridge"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/webhook":
            self._json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "invalid JSON body"})
            return

        prompt = (payload.get("prompt") or "").strip()
        mode = (payload.get("mode") or "full").strip()
        if not prompt:
            self._json(400, {"error": "missing 'prompt' field"})
            return

        try:
            dispatch = NexusDispatch()
            run = dispatch.dispatch(prompt, mode=mode)
            print(f"[Bridge] Dispatched run #{run['id']}: {prompt[:80]}")
            self._json(202, {
                "status": "dispatched",
                "run_id": run["id"],
                "run_number": run.get("run_number"),
                "html_url": run.get("html_url"),
            })
        except Exception as e:
            print(f"[Bridge] Dispatch failed: {e}")
            self._json(500, {"error": str(e)})


def main():
    print(f"[Bridge] Nexus webhook bridge listening on :{PORT} (POST /webhook)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
