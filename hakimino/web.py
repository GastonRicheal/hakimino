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
from .vault import VaultError, StaleRevisionError, generate_password

ROOT = Path(__file__).parent


class StaleVaultError(VaultError):
    """The request was made from a view of a previous unlock."""


IDLE_SECONDS = 300
CLIENT_TTL_SECONDS = 3600
MAX_CLIENTS = 32
MAX_CONNECTIONS = 8
REQUEST_TIMEOUT = 5


class BrowserState:
    """One browser cookie owns one unlock state; same-profile tabs still share it."""

    def __init__(self, data_dir):
        self.token = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.session = VaultSession()
        self.vault_epoch = 0
        self.last_use = self.last_seen = time.monotonic()
        self.data_dir = data_dir

    def dispatch(self, data):
        action = data.get("action")
        if not isinstance(action, str) or action not in {
                "create", "unlock", "lock", "generate", "add", "delete", "show", "status"}:
            raise VaultError("Unsupported operation.")
        if time.monotonic() - self.last_use >= IDLE_SECONDS:
            self.session.lock()
        if self.session.unlocked and action in {"add", "delete", "show", "generate", "lock"}:
            epoch = data.get("vault_epoch")
            if type(epoch) is not int or epoch != self.vault_epoch:
                raise StaleVaultError("The open vault changed. Unlock the intended vault to continue.")
        if action != "status":
            self.last_use = time.monotonic()
        if action in {"create", "unlock"}:
            self.session.lock()
            name = data.get("name", "")
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}\.vault", name):
                raise VaultError("Use a simple .vault filename: letters, numbers, hyphens or underscores.")
            self.session.open(self.data_dir / name, data.get("master"), create=action == "create")
            self.vault_epoch += 1
        elif action == "lock":
            self.session.lock()
        elif action == "generate":
            if not self.session.unlocked:
                raise VaultError("Unlock a vault first.")
            return {"password": generate_password(data.get("length", 24))}
        elif action in {"add", "delete", "show"}:
            if not self.session.unlocked:
                raise VaultError("Unlock a vault first.")
            revision = data.get("vault_revision")
            if action in {"show", "delete"} and not isinstance(revision, str):
                raise StaleRevisionError("Missing vault revision. Unlock the vault again.")
            label = data.get("label")
            if not isinstance(label, str) or not label.strip() or len(label) > 256:
                raise VaultError("Entry label must contain 1 to 256 characters.")
            if action == "add":
                self.session.run("add", label=label, username=data.get("username", ""), entry_password=data.get("password"))
            elif action == "show":
                entry = self.session.run("show", label=label, expected_revision=revision)
                return {"username": entry["username"], **({"password": entry["password"]} if data.get("reveal") is True else {})}
            else:
                self.session.run("delete", label=label, expected_revision=revision)
        elif action != "status":
            raise VaultError("Unsupported operation.")
        snapshot = self.session.run("snapshot") if self.session.unlocked else None
        return {"unlocked": self.session.unlocked,
                "vault_revision": snapshot["revision"] if snapshot else None,
                "vault_epoch": self.vault_epoch if self.session.unlocked else None,
                "name": self.session.path.name if self.session.unlocked else None,
                "labels": snapshot["labels"] if snapshot else []}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.clients = {}
        self.mutex = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        # Separate app instances must not overwrite each other's cookie names.
        # Cookies are not port-isolated security boundaries against local malware.
        self.cookie_name = f"hakimino_{self.server_port}"

    def _expire_clients(self):
        now = time.monotonic()
        for token, client in list(self.clients.items()):
            if now - client.last_use >= IDLE_SECONDS:
                client.session.lock()
            if now - client.last_seen >= CLIENT_TTL_SECONDS:
                client.session.lock()
                del self.clients[token]

    def browser(self, token, *, create=False):
        """Called under mutex. Never disclose an existing client's token to a newcomer."""
        self._expire_clients()
        client = self.clients.get(token)
        if client is None and create:
            if len(self.clients) >= MAX_CLIENTS:
                return None
            client = BrowserState(self.data_dir)
            self.clients[client.token] = client
        if client is not None:
            client.last_seen = time.monotonic()
        return client

    def service_actions(self):
        with self.mutex:
            self._expire_clients()

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(REQUEST_TIMEOUT)  # Includes request-line/header reads.
        return request, address

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def server_close(self):
        with self.mutex:
            for client in self.clients.values():
                client.session.lock()
            self.clients.clear()
        super().server_close()


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate request field")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Non-finite JSON value")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log request bodies, credentials or entry names.

    def reply(self, status, body, content_type="application/json", cookie=None):
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
        if cookie is not None:
            self.send_header("Set-Cookie", f"{self.server.cookie_name}={cookie}; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def cookie_token(self):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            item = cookie.get(self.server.cookie_name)
            return item.value if item is not None else None
        except Exception:
            return None

    def valid_host(self):
        return self.headers.get("Host") == self.server.origin.removeprefix("http://")

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {"error": "Invalid host."})
        if self.path in {"/", "/index.html"}:
            with self.server.mutex:
                client = self.server.browser(self.cookie_token(), create=True)
                if client is None:
                    return self.reply(503, {"error": "Too many local browser sessions. Try again later."})
                csrf, token = client.csrf, client.token
            page = (ROOT / "web" / "index.html").read_bytes().replace(b"__CSRF__", csrf.encode())
            return self.reply(200, page, "text/html; charset=utf-8", cookie=token)
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
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding") is not None:
                raise ValueError()
            size = int(lengths[0])
            if not 0 < size <= 32768 or self.headers.get("Content-Type") != "application/json":
                raise ValueError()
            raw_body = self.rfile.read(size)
            if len(raw_body) != size:
                raise ValueError()
        except (ValueError, OSError):
            return self.reply(400, {"error": "Invalid request.", "kind": "input"})
        with self.server.mutex:
            client = self.server.browser(self.cookie_token())
            csrf = self.headers.get("X-Hakimino-CSRF", "").encode("utf-8")
            if (not self.valid_host() or client is None or
                    self.headers.get("Origin") != self.server.origin or
                    not secrets.compare_digest(csrf, client.csrf.encode("ascii"))):
                return self.reply(403, {"error": "Request rejected. Reload the local app.",
                                        "kind": "access", "unlocked": False})
            if self.path != "/api":
                return self.reply(404, {"error": "Not found."})
            try:
                data = json.loads(raw_body, object_pairs_hook=unique_fields,
                                  parse_constant=invalid_constant)
                if not isinstance(data, dict):
                    raise ValueError()
            except (ValueError, UnicodeError, RecursionError):
                return self.reply(400, {"error": "Invalid request.", "kind": "input"})
            try:
                result = client.dispatch(data)
            except (StaleVaultError, StaleRevisionError) as exc:
                return self.reply(409, {"error": str(exc), "kind": "access", "unlocked": False})
            except VaultError as exc:
                kind = "access" if data.get("action") in ("unlock", "create") or not client.session.unlocked else "input"
                return self.reply(400, {"error": str(exc), "kind": kind, "unlocked": client.session.unlocked})
            except OSError:
                client.session.lock()
                return self.reply(400, {"error": "Could not access the vault file. Check the file and try again.", "kind": "access", "unlocked": False})
            except Exception:
                client.session.lock()
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
        server.server_close()


if __name__ == "__main__":
    main()
