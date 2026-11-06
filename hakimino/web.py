"""Loopback-only web UI for testing the real encrypted vault, not public hosting."""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time

from .session import VaultSession
from .vault import VaultError, generate_password

ROOT = Path(__file__).parent


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, data_dir):
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.cookie = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.session = VaultSession()
        self.mutex = threading.Lock()
        self.last_use = time.monotonic()
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def service_actions(self):
        with self.mutex:
            if time.monotonic() - self.last_use >= 300:
                self.session.lock()

    def dispatch(self, data):
        action = data.get("action")
        if time.monotonic() - self.last_use >= 300:
            self.session.lock()
        if action != "status":
            self.last_use = time.monotonic()
        if action in {"create", "unlock"}:
            self.session.lock()
            name = data.get("name", "")
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}\.vault", name):
                raise VaultError("Use a simple .vault filename: letters, numbers, hyphens or underscores.")
            self.session.open(self.data_dir / name, data.get("master"), create=action == "create")
        elif action == "lock":
            self.session.lock()
        elif action == "generate":
            if not self.session.unlocked:
                raise VaultError("Unlock a vault first.")
            return {"password": generate_password(data.get("length", 24))}
        elif action in {"add", "delete", "show"}:
            label = data.get("label")
            if not isinstance(label, str) or not label.strip() or len(label) > 256:
                raise VaultError("Entry label must contain 1 to 256 characters.")
            if action == "add":
                self.session.run("add", label=label, username=data.get("username", ""), entry_password=data.get("password"))
            elif action == "show":
                entry = self.session.run("show", label=label)
                return {"username": entry["username"], **({"password": entry["password"]} if data.get("reveal") is True else {})}
            else:
                self.session.run("delete", label=label)
        elif action != "status":
            raise VaultError("Unsupported operation.")
        return {"unlocked": self.session.unlocked,
                "name": self.session.path.name if self.session.unlocked else None,
                "labels": self.session.run("list") if self.session.unlocked else []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log request bodies, credentials or entry names.

    def reply(self, status, body, content_type="application/json", cookie=False):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        if cookie:
            self.send_header("Set-Cookie", f"hakimino={self.server.cookie}; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == self.server.origin.removeprefix("http://")

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {"error": "Invalid host."})
        if self.path in {"/", "/index.html"}:
            page = (ROOT / "web" / "index.html").read_bytes().replace(b"__CSRF__", self.server.csrf.encode())
            return self.reply(200, page, "text/html; charset=utf-8", cookie=True)
        if self.path == "/app.js":
            return self.reply(200, (ROOT / "web" / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        if re.fullmatch(r"/assets/[a-z-]+\.png", self.path):
            asset = ROOT / self.path.lstrip("/")
            if asset.is_file():
                return self.reply(200, asset.read_bytes(), "image/png")
        self.reply(404, {"error": "Not found."})

    def do_POST(self):
        # Consume a bounded body before replying. Closing an HTTP/1.0 socket
        # with unread request bytes can reset it on Windows and discard a 403.
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768 or self.headers.get("Content-Type") != "application/json":
                raise ValueError()
            self.connection.settimeout(5)
            raw_body = self.rfile.read(size)
        except (ValueError, OSError):
            return self.reply(400, {"error": "Invalid request.", "kind": "input"})
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            authorized = cookie.get("hakimino") and secrets.compare_digest(cookie["hakimino"].value, self.server.cookie)
        except Exception:
            authorized = False
        if (not self.valid_host() or not authorized or
                self.headers.get("Origin") != self.server.origin or
                not secrets.compare_digest(self.headers.get("X-Hakimino-CSRF", ""), self.server.csrf)):
            return self.reply(403, {"error": "Request rejected. Reload the local app.", "kind": "access"})
        if self.path != "/api":
            return self.reply(404, {"error": "Not found."})
        try:
            data = json.loads(raw_body)
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, OSError):
            return self.reply(400, {"error": "Invalid request.", "kind": "input"})
        with self.server.mutex:
            try:
                result = self.server.dispatch(data)
            except VaultError as exc:
                kind = "access" if data.get("action") in {"unlock", "create"} or not self.server.session.unlocked else "input"
                return self.reply(400, {"error": str(exc), "kind": kind, "unlocked": self.server.session.unlocked})
            except OSError:
                self.server.session.lock()
                return self.reply(400, {"error": "Could not access the vault file. Check the file and try again.", "kind": "access", "unlocked": False})
            except Exception:
                self.server.session.lock()
                return self.reply(500, {"error": "An unexpected error occurred. The vault is locked. Restart the local app.", "kind": "critical", "unlocked": False})
        self.reply(200, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".hakimino" / "web-test-vaults")
    args = parser.parse_args()
    server = LocalServer(args.port, args.data_dir)
    print(f"Hakimino local web app: {server.origin}", flush=True)
    print(f"Encrypted test vault directory: {server.data_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.session.lock()
        server.server_close()


if __name__ == "__main__":
    main()
