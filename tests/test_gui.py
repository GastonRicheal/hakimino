"""Real Tk widget tests with synthetic vaults; OS dialogs are supplied test inputs."""
import tkinter as tk

import pytest

from hakimino import gui
from hakimino.session import VaultSession
from hakimino.vault import VaultError, operate

MASTER = "synthetic GUI test passphrase"


def test_session_fails_closed_and_locks(tmp_path):
    path = tmp_path / "sample.vault"
    session = VaultSession()
    assert session.open(path, MASTER, create=True) == []
    session.run("add", label="school", username="tester", entry_password="synthetic")
    assert session.run("list") == ["school"]
    with pytest.raises(VaultError):
        session.open(path, "incorrect")
    assert not session.unlocked
    assert session.path is None
    with pytest.raises(VaultError):
        session.run("list")
    session.open(path, MASTER)
    session.lock()
    assert session._master is None
    with pytest.raises(VaultError):
        session.run("delete", label="school")
    assert operate(path, MASTER, "list") == ["school"]


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        if "no display" in str(exc).lower() or "couldn't connect to display" in str(exc).lower():
            pytest.skip(f"Tk display unavailable: {exc}")
        raise
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def app(tmp_path, monkeypatch, tk_root):
    root = tk_root
    instance = gui.VaultApp(root)
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, text, **_: errors.append(text))
    instance.test_errors = errors
    instance.path.set(str(tmp_path / "sample.vault"))
    operate(instance.path.get(), MASTER, "init")
    yield instance
    instance.lock()
    instance.content.destroy()
    root.unbind_all("<KeyPress>")
    root.unbind_all("<ButtonPress>")


def unlock(app):
    app.master.set(MASTER)
    app.unlock_button.invoke()
    app.root.update()
    assert app.session.unlocked
    assert app.master.get() == ""


def add(app, label="School"):
    app.new_button.invoke()
    app.root.update()
    app.label.set(label)
    app.username.set("synthetic-user")
    app.generate_button.invoke()
    assert len(app.password.get()) == 24
    app.save_button.invoke()
    app.root.update()


def select_first(app):
    app.tree.selection_set(app.tree.get_children()[0])
    app.root.update()


def test_create_via_window(app, tmp_path, monkeypatch):
    path = tmp_path / "created.vault"
    monkeypatch.setattr(gui.simpledialog, "askstring", lambda *a, **k: MASTER)
    monkeypatch.setattr(gui.filedialog, "asksaveasfilename", lambda **k: str(path))
    app.master.set(MASTER)
    app.create_button.invoke()
    assert app.session.unlocked
    assert operate(path, MASTER, "list") == []
    assert app.master.get() == ""


def test_wrong_password_stays_locked(app):
    app.master.set("wrong")
    app.unlock_button.invoke()
    assert not app.session.unlocked
    assert app.master.get() == ""
    assert len(app.test_errors) == 1


def test_add_search_reveal_and_lock(app):
    unlock(app)
    add(app)
    select_first(app)
    assert app.username.get() == "synthetic-user"
    assert app.fields[2].cget("show") == "•"
    assert app.save_button.instate(["disabled"])
    app.reveal_button.invoke()
    assert app.fields[2].cget("show") == ""
    assert app.reveal_job is not None
    app.hide_password()
    assert app.fields[2].cget("show") == "•"
    app.query.set("missing")
    app.root.update()
    assert app.tree.get_children() == ()
    assert app.password.get() == ""
    app.query.set("school")
    app.root.update()
    assert len(app.tree.get_children()) == 1
    select_first(app)
    app.lock_button.invoke()
    assert not app.session.unlocked
    assert app.password.get() == app.username.get() == app.label.get() == ""
    assert app.tree.get_children() == ()
    assert app.idle_job is None
    assert app.reveal_job is None
    assert not app.test_errors


def test_duplicate_entry_preserves_vault(app):
    unlock(app)
    add(app)
    original = app.session.path.read_bytes()
    add(app)
    assert app.session.path.read_bytes() == original
    assert len(app.test_errors) == 1


def test_delete_cancel_and_confirm(app, monkeypatch):
    unlock(app)
    add(app)
    select_first(app)
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: False)
    app.delete_button.invoke()
    assert app.session.run("list") == ["School"]
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: True)
    app.delete_button.invoke()
    assert app.session.run("list") == []
    assert app.password.get() == ""


def test_lock_during_confirmation_prevents_delete(app, monkeypatch):
    unlock(app)
    add(app)
    select_first(app)
    path = app.session.path
    def confirm(*a, **k):
        app.lock()
        return True
    monkeypatch.setattr(gui.messagebox, "askyesno", confirm)
    app.delete_button.invoke()
    assert not app.session.unlocked
    assert operate(path, MASTER, "list") == ["School"]


def test_idle_and_reveal_timers(app, monkeypatch):
    unlock(app)
    add(app)
    select_first(app)
    monkeypatch.setattr(gui, "REVEAL_MS", 1)
    app.reveal_button.invoke()
    app.root.after(20, app.root.quit)
    app.root.mainloop()
    assert app.fields[2].cget("show") == "•"
    monkeypatch.setattr(gui, "IDLE_MS", 1)
    app.touch()
    app.root.after(20, app.root.quit)
    app.root.mainloop()
    assert not app.session.unlocked
    assert app.password.get() == ""
