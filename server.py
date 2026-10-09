#!/usr/bin/env python3
"""Local scoreboard server: serves the site and syncs /control -> /show live.

Run:  python3 server.py   (then open http://localhost:8765/control/)
OBS:  Browser Source -> http://localhost:8765/show/?bg=transparent  (1920x1080)
"""
import json
import os
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", "8765"))
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(ROOT, "state.json")

lock = threading.Condition()
games = {}      # game id -> state dict
version = 0

try:
    with open(STATE_FILE) as f:
        games = json.load(f)
except Exception:
    games = {}


def save():
    try:
        with open(STATE_FILE + ".tmp", "w") as f:
            json.dump(games, f)
        os.replace(STATE_FILE + ".tmp", STATE_FILE)
    except Exception as e:
        print("could not save state:", e)


def apply_patch(obj, patch):
    for path, val in patch.items():
        keys = path.split("/")
        o = obj
        for k in keys[:-1]:
            if not isinstance(o.get(k), dict):
                o[k] = {}
            o = o[k]
        o[keys[-1]] = val


def now_ms():
    return int(time.time() * 1000)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def game(self):
        g = parse_qs(urlparse(self.path).query).get("game", ["fulton"])[0]
        return "".join(c for c in g if c.isalnum() or c in "-_") or "fulton"

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/api/state", "/gas"):
            with lock:
                return self.send_json({"state": games.get(self.game(), {}), "now": now_ms()})
        if path == "/api/events":
            return self.events()
        return super().do_GET()

    def events(self):
        g = self.game()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        seen = -1
        try:
            while True:
                with lock:
                    if seen == version:
                        lock.wait(timeout=15)
                    changed = seen != version
                    seen = version
                    payload = json.dumps({"state": games.get(g, {}), "now": now_ms()})
                if changed:
                    self.wfile.write(f"data: {payload}\n\n".encode())
                else:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_POST(self):
        global version
        path = urlparse(self.path).path
        if path not in ("/api/update", "/api/set", "/gas"):
            return self.send_json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.send_json({"error": "bad json"}, 400)
        g = self.game()
        with lock:
            if path == "/gas":  # same shape as the Apps Script API (for testing)
                if "set" in data:
                    games[g] = data["set"]
                else:
                    apply_patch(games.setdefault(g, {}), data.get("patch", {}))
            elif path == "/api/set":
                games[g] = data
            else:
                apply_patch(games.setdefault(g, {}), data)
            version += 1
            lock.notify_all()
            save()
        self.send_json({"ok": True, "state": games.get(g, {}), "now": now_ms()})


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


if __name__ == "__main__":
    ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    ip = lan_ip()
    print("\n  FULTON SCOREBOARD is running\n")
    print(f"  Control:   http://localhost:{PORT}/control/")
    print(f"  OBS show:  http://localhost:{PORT}/show/?bg=transparent   (Browser Source 1920x1080)")
    if ip:
        print(f"  Phone/tablet control on same Wi-Fi:  http://{ip}:{PORT}/control/")
    print("\n  Leave this window open during the game. Ctrl+C to stop.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
