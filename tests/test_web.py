"""Local HTTP integration tests against the actual encrypted storage."""
import http.client
from http.cookies import SimpleCookie
from types import SimpleNamespace
import re
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
    app.test_client = new_client(app)
    yield app
    app.shutdown()
    app.server_close()
    thread.join()


def new_client(server):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    conn.request("GET", "/")
    response = conn.getresponse()
    assert response.status == 200
    cookie = SimpleCookie(response.getheader("Set-Cookie"))
    token = cookie[server.cookie_name].value
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', response.read().decode()).group(1)
    conn.close()
    return SimpleNamespace(token=token, csrf=csrf, state=server.clients[token])


def request(server, action=None, *, path="/api", headers=None, client=None, **fields):
    client = client or server.test_client
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    h = {"Cookie": f"{server.cookie_name}={client.token}", "Origin": server.origin,
         "X-Hakimino-CSRF": client.csrf, "Content-Type": "application/json"}
    h.update(headers or {})
    payload = {"action": action, "vault_epoch": client.state.vault_epoch, "vault_revision": client.state.session.revision, **fields}
    conn.request("POST" if action else "GET", path, json.dumps(payload) if action else None, h)
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


@pytest.mark.parametrize("next_vault", ["first.vault", "second.vault"])
def test_stale_vault_view_cannot_read_or_modify_current_vault(server, next_vault):
    previous = request(server, "create", name="first.vault", master=MASTER)[2]["vault_epoch"]
    assert request(server, "add", label="school", password="first-test-password")[0] == 200
    action = "unlock" if next_vault == "first.vault" else "create"
    current = request(server, action, name=next_vault, master=MASTER)[2]["vault_epoch"]
    if action == "create":
        assert request(server, "add", label="school", password="second-test-password")[0] == 200
    assert previous != current
    path = server.data_dir / next_vault
    before = path.read_bytes()
    for action, fields in [
        ("show", {"label": "school", "reveal": True}),
        ("delete", {"label": "school"}),
        ("add", {"label": "extra", "password": "synthetic"}),
        ("generate", {}),
        ("lock", {}),
    ]:
        status, _, result = request(server, action, vault_epoch=previous, **fields)
        assert status == 409 and result["unlocked"] is False
        assert "password" not in result
    assert request(server, "show", label="school", vault_epoch=None)[0] == 409
    assert path.read_bytes() == before
    status = request(server, "status")[2]
    assert status["unlocked"] and status["labels"] == ["school"]


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Host": "evil.example"}, {"Cookie": ""}, {"X-Hakimino-CSRF": "invalid"}])
def test_cross_site_and_unauthenticated_requests_denied(server, headers):
    assert request(server, "create", name="bad.vault", master=MASTER, headers=headers)[0] == 403
    assert not (server.data_dir / "bad.vault").exists()


def test_unauthenticated_split_body_receives_complete_rejection(server):
    # Send headers and body separately, like http.client.request does internally.
    # The server must not close/reset before the client finishes the bounded body.
    import socket
    body = json.dumps({"action": "create", "name": "denied.vault", "master": MASTER}).encode()
    with socket.create_connection(server.server_address, timeout=5) as sock:
        headers = (f"POST /api HTTP/1.1\r\nHost: 127.0.0.1:{server.server_port}\r\n"
                   f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n")
        sock.sendall(headers.encode())
        time.sleep(0.05)
        sock.sendall(body)
        response = http.client.HTTPResponse(sock)
        response.begin()
        assert response.status == 403
        assert json.loads(response.read())["kind"] == "access"
    assert not (server.data_dir / "denied.vault").exists()


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
    server.test_client.state.last_use = time.monotonic() - 301
    assert request(server, "status")[2]["unlocked"] is False
    request(server, "unlock", name="test.vault", master=MASTER)
    before = (server.data_dir / "test.vault").read_bytes()
    def fail(*args, **kwargs):
        raise RuntimeError("secret-must-not-be-returned")
    monkeypatch.setattr(server.test_client.state.session, "run", fail)
    status, _, body = request(server, "show", label="school")
    assert status == 500 and body["kind"] == "critical"
    assert "secret-must-not-be-returned" not in json.dumps(body)
    assert not server.test_client.state.session.unlocked
    assert (server.data_dir / "test.vault").read_bytes() == before


@pytest.mark.parametrize("external", [False, True])
def test_same_unlock_stale_view_cannot_delete_or_reveal_replacement(server, external):
    from hakimino.session import VaultSession
    request(server, "create", name="test.vault", master=MASTER)
    old = request(server, "add", label="school", username="student", password="synthetic")[2]
    path = server.data_dir / "test.vault"
    if external:
        other = VaultSession()
        other.open(path, MASTER)
        other.run("delete", label="school")
        other.run("add", label="school", username="student", entry_password="synthetic")
        other.lock()
    else:
        assert request(server, "delete", label="school")[0] == 200
        assert request(server, "add", label="school", username="student", password="synthetic")[0] == 200
    replacement = path.read_bytes()
    current = request(server, "status")[2]  # Another tab's polling must not authorize the stale tab.
    assert current["vault_epoch"] == old["vault_epoch"]
    assert current["vault_revision"] != old["vault_revision"]
    for action in ("delete", "show"):
        code, _, body = request(server, action, label="school", reveal=True,
                                vault_revision=old["vault_revision"])
        assert code == 409 and body["unlocked"] is False
        assert "password" not in body and "username" not in body
        assert path.read_bytes() == replacement
    assert request(server, "show", label="school", vault_revision=current["vault_revision"])[0] == 200
    assert request(server, "delete", label="school", vault_revision=current["vault_revision"])[0] == 200


@pytest.mark.parametrize("revision", [None, "", 12, {}])
def test_web_missing_or_invalid_revision_cannot_delete_or_reveal(server, revision):
    request(server, "create", name="test.vault", master=MASTER)
    request(server, "add", label="school", password="synthetic")
    path = server.data_dir / "test.vault"
    before = path.read_bytes()
    for action in ("delete", "show"):
        assert request(server, action, label="school", reveal=True, vault_revision=revision)[0] == 409
        assert path.read_bytes() == before


# Security regressions use only the fixture's disposable loopback server.
def test_independent_browser_cannot_inherit_unlocked_vault(server):
    request(server, "create", name="owner.vault", master=MASTER)
    request(server, "add", label="school", password="synthetic owner secret")
    owner = server.test_client
    other = new_client(server)
    assert other.token != owner.token and other.csrf != owner.csrf
    status = request(server, "status", client=other)[2]
    assert status["unlocked"] is False and status["labels"] == []
    for action in ("show", "delete"):
        code, _, body = request(server, action, client=other, label="school", reveal=True,
                                vault_epoch=owner.state.vault_epoch,
                                vault_revision=owner.state.session.revision)
        assert code == 400 and "password" not in body
    assert request(server, "unlock", client=other, name="owner.vault", master="wrong")[0] == 400
    assert owner.state.session.unlocked
    assert request(server, "show", label="school", reveal=True)[2]["password"] == "synthetic owner secret"
    assert request(server, "unlock", client=other, name="owner.vault", master=MASTER)[0] == 200
    assert request(server, "show", client=other, label="school", reveal=True)[2]["password"] == "synthetic owner secret"
    request(server, "lock", client=other)
    assert owner.state.session.unlocked


def test_cookie_and_csrf_are_bound_to_same_browser(server):
    other = new_client(server)
    assert request(server, "status", client=other,
                   headers={"X-Hakimino-CSRF": server.test_client.csrf})[0] == 403
    assert request(server, "status", headers={"X-Hakimino-CSRF": "\u00e9"})[0] == 403
    # Refresh with the existing browser cookie retains that browser's context.
    code, headers, page = request(server, path="/")
    assert code == 200
    assert SimpleCookie(headers["Set-Cookie"])[server.cookie_name].value == server.test_client.token
    assert server.test_client.csrf.encode() in page
    assert other.csrf.encode() not in page


def test_browser_idle_lock_is_independent(server):
    request(server, "create", name="first.vault", master=MASTER)
    other = new_client(server)
    request(server, "create", client=other, name="second.vault", master=MASTER)
    server.test_client.state.last_use = time.monotonic() - 301
    assert request(server, "status")[2]["unlocked"] is False
    assert request(server, "status", client=other)[2]["unlocked"] is True


@pytest.mark.parametrize("action", [[], {}, 3, None, "unsupported"])
def test_invalid_action_is_non_destructive_client_error(server, action):
    request(server, "create", name="test.vault", master=MASTER)
    before = (server.data_dir / "test.vault").read_bytes()
    last_use = server.test_client.state.last_use
    assert raw_request(server, json.dumps({"action": action}).encode())[0] == 400
    assert server.test_client.state.session.unlocked
    assert server.test_client.state.last_use == last_use
    assert (server.data_dir / "test.vault").read_bytes() == before


def raw_request(server, body, extra=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    c = server.test_client
    headers = {"Cookie": f"{server.cookie_name}={c.token}", "Origin": server.origin,
               "X-Hakimino-CSRF": c.csrf, "Content-Type": "application/json"}
    headers.update(extra or {})
    conn.request("POST", "/api", body, headers)
    response = conn.getresponse()
    result = response.status, json.loads(response.read())
    conn.close()
    return result


@pytest.mark.parametrize("body", [
    b'{"action":"status","action":"lock"}', b'{"action":NaN}',
    b'[' * 1100 + b'0' + b']' * 1100, b'\xff', b'[]',
])
def test_malformed_json_does_not_lock_or_rewrite_vault(server, body):
    request(server, "create", name="test.vault", master=MASTER)
    before = (server.data_dir / "test.vault").read_bytes()
    assert raw_request(server, body)[0] == 400
    assert server.test_client.state.session.unlocked
    assert (server.data_dir / "test.vault").read_bytes() == before


def test_nonfinite_and_invalid_unicode_inputs_fail_safely(server):
    assert request(server, "create", name="bad.vault", master="synthetic master \ud800")[0] == 400
    assert not (server.data_dir / "bad.vault").exists()
    request(server, "create", name="good.vault", master=MASTER)
    before = (server.data_dir / "good.vault").read_bytes()
    assert request(server, "add", label="synthetic", password="bad\ud800")[0] == 400
    assert server.test_client.state.session.unlocked
    assert (server.data_dir / "good.vault").read_bytes() == before


def test_context_capacity_and_expiry(server, monkeypatch):
    from hakimino import web
    monkeypatch.setattr(web, "MAX_CLIENTS", 1)
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
    conn.request("GET", "/")
    response = conn.getresponse()
    assert response.status == 503
    response.read(); conn.close()
    assert request(server, "status")[0] == 200
    old = server.test_client.state
    old.last_seen = time.monotonic() - web.CLIENT_TTL_SECONDS - 1
    other = new_client(server)
    assert len(server.clients) == 1 and other.token != server.test_client.token
    assert not old.session.unlocked
    assert request(server, "status")[0] == 403


def test_idle_header_connection_times_out(server, monkeypatch):
    import socket
    from hakimino import web
    monkeypatch.setattr(web, "REQUEST_TIMEOUT", 0.05)
    with socket.create_connection(server.server_address, timeout=2) as conn:
        conn.sendall(b"GET / HTTP/1.1\r\n")
        assert conn.recv(1) == b""
    assert request(server, "status")[0] == 200


def test_connection_capacity_closes_excess_socket(server):
    import socket
    from hakimino import web
    for _ in range(web.MAX_CONNECTIONS):
        assert server._slots.acquire(timeout=2)
    try:
        with socket.create_connection(server.server_address, timeout=2) as conn:
            assert conn.recv(1) == b""
    finally:
        for _ in range(web.MAX_CONNECTIONS):
            server._slots.release()
    assert request(server, "status")[0] == 200
