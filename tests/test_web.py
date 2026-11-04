"""Local HTTP integration tests against the actual encrypted storage."""
import http.client
import json
import threading
import time

import pytest

from hakimino.web import LocalServer
from hakimino.vault import unseal

MASTER = "web-test-only master passphrase"


@pytest.fixture
def server(tmp_path):
    app = LocalServer(0, tmp_path)
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    yield app
    app.shutdown()
    app.session.lock()
    app.server_close()
    thread.join()


def request(server, action=None, *, path="/api", headers=None, **fields):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    h = {"Cookie": f"hakimino={server.cookie}", "Origin": server.origin,
         "X-Hakimino-CSRF": server.csrf, "Content-Type": "application/json"}
    h.update(headers or {})
    conn.request("POST" if action else "GET", path, json.dumps({"action": action, **fields}) if action else None, h)
    response = conn.getresponse()
    body = response.read()
    result = (response.status, dict(response.getheaders()), json.loads(body) if response.getheader("Content-Type") == "application/json" else body)
    conn.close()
    return result


def test_real_persistence_lifecycle(server):
    assert request(server, "create", name="test.vault", master=MASTER)[0] == 200
    password = request(server, "generate", length=32)[2]["password"]
    assert len(password) == 32
    assert request(server, "add", label="school", username="test-user", password=password)[0] == 200
    path = server.data_dir / "test.vault"
    original = path.read_bytes()
    assert password.encode() not in original and b"test-user" not in original
    assert unseal(original, MASTER)["school"]["password"] == password
    assert "password" not in request(server, "show", label="school")[2]
    assert request(server, "lock")[2]["unlocked"] is False
    assert request(server, "show", label="school", reveal=True)[0] == 400
    assert request(server, "unlock", name="test.vault", master="wrong")[0] == 400
    assert path.read_bytes() == original
    assert request(server, "unlock", name="test.vault", master=MASTER)[2]["labels"] == ["school"]
    assert request(server, "show", label="school", reveal=True)[2]["password"] == password
    assert request(server, "delete", label="school")[2]["labels"] == []
    assert unseal(path.read_bytes(), MASTER) == {}


def test_validation_preserves_vault(server):
    request(server, "create", name="test.vault", master=MASTER)
    request(server, "add", label="school", password="test-only")
    path = server.data_dir / "test.vault"
    original = path.read_bytes()
    assert request(server, "add", label="school", password="replacement")[0] == 400
    assert request(server, "generate", length=2)[0] == 400
    assert path.read_bytes() == original
    assert request(server, "create", name="test.vault", master=MASTER)[0] == 400
    assert path.read_bytes() == original


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Host": "evil.example"}, {"Cookie": ""}, {"X-Hakimino-CSRF": "invalid"}])
def test_cross_site_and_unauthenticated_requests_denied(server, headers):
    assert request(server, "create", name="bad.vault", master=MASTER, headers=headers)[0] == 403
    assert not (server.data_dir / "bad.vault").exists()


@pytest.mark.parametrize("name", ["../outside.vault", "/tmp/outside.vault", "wrong.json", "a/b.vault"])
def test_path_restriction(server, name):
    assert request(server, "create", name=name, master=MASTER)[0] == 400
    assert not list(server.data_dir.iterdir())


def test_assets_and_private_routes(server):
    status, headers, body = request(server, path="/")
    assert status == 200 and b"__CSRF__" not in body
    assert headers["Cache-Control"] == "no-store"
    assert "HttpOnly" in headers["Set-Cookie"] and "SameSite=Strict" in headers["Set-Cookie"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert request(server, path="/assets/critical-error.png")[0] == 200
    assert request(server, path="/assets/cheer.png")[0] == 200
    assert request(server, path="/assets/concierge.png")[0] == 200
    assert b"/assets/concierge.png" in body
    assert request(server, path="/assets/rose.png")[0] == 200
    assert request(server, path="/assets/bodyguard.png")[0] == 200
    assert b"/assets/bodyguard.png" in request(server, path="/app.js")[2]
    assert b"/assets/rose.png" in request(server, path="/app.js")[2]
    assert b"/assets/cheer.png" in body
    for path in ["/../vault.py", "/vaults/test.vault", "/.git/config", "/assets/../vault.py"]:
        assert request(server, path=path)[0] == 404


def test_inactivity_and_unexpected_failure_lock(server, monkeypatch):
    request(server, "create", name="test.vault", master=MASTER)
    server.last_use = time.monotonic() - 301
    assert request(server, "status")[2]["unlocked"] is False
    request(server, "unlock", name="test.vault", master=MASTER)
    before = (server.data_dir / "test.vault").read_bytes()
    def fail(*args, **kwargs):
        raise RuntimeError("secret-must-not-be-returned")
    monkeypatch.setattr(server.session, "run", fail)
    status, _, body = request(server, "show", label="school")
    assert status == 500 and body["kind"] == "critical"
    assert "secret-must-not-be-returned" not in json.dumps(body)
    assert not server.session.unlocked
    assert (server.data_dir / "test.vault").read_bytes() == before
