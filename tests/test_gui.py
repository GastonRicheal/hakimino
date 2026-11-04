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



def test_theme_assets_and_english_brand(app):
    assert app.root.title() == "Hakimino | Your private vault"
    for picture in (app.cat_portrait, app.cat_empty, app.cat_error, app.cat_access_error, app.cat_welcome, app.cat_new):
        assert picture is not None
        assert 0 < picture.width() <= 180
        assert 0 < picture.height() <= 180
    assert app._load_sticker("missing.png", 150) is None


def test_empty_search_and_count_states(app):
    unlock(app)
    assert app.count.get() == "0 entries"
    assert "No secrets yet" in app.empty_message.get()
    assert app.empty_label.place_info()
    add(app)
    assert app.count.get() == "1 entry"
    assert not app.empty_label.place_info()
    app.query.set("not present")
    app.root.update()
    assert app.count.get() == "0 / 1 entries"
    assert "No matching" in app.empty_message.get()
    app.clear_search_button.invoke()
    app.root.update()
    assert app.query.get() == ""
    assert len(app.tree.get_children()) == 1
    app.lock_button.invoke()
    assert app.count.get() == "0 entries"
    assert app.session_state.get() == "VAULT LOCKED"


def test_custom_length_and_invalid_input_preserve_password(app):
    unlock(app)
    app.length.set("32")
    app.generate_button.invoke()
    previous = app.password.get()
    assert len(previous) == 32
    for value in ("15", "129", "abc", "24.5", ""):
        app.length.set(value)
        app.generate_button.invoke()
        assert app.password.get() == previous
        assert app.cat_mood == "error"
    assert len(app.test_errors) == 5
    app.length.set("16")
    app.generate_button.invoke()
    assert len(app.password.get()) == 16
    assert app.cat_mood == "guard"


def test_wrong_password_shows_error_art_and_success_recovers(app):
    app.master.set("wrong")
    app.unlock_button.invoke()
    assert app.cat_mood == "error"
    assert str(app.cat_access_error) in str(app.mascot.cget("image"))
    assert app.error_kind == "access"
    assert "Oops!" in app.status.get()
    assert "wrong" not in app.status.get().lower()
    assert app.session_state.get() == "VAULT LOCKED"
    unlock(app)
    assert app.cat_mood == "guard"
    assert app.session_state.get() == "VAULT UNLOCKED"


def test_duplicate_save_shows_error_art_without_data_loss(app):
    unlock(app)
    add(app)
    original = app.session.path.read_bytes()
    add(app)
    assert app.cat_mood == "error"
    assert app.session.path.read_bytes() == original
    assert "synthetic" not in app.status.get()
    add(app, "Another")
    assert app.cat_mood == "guard"
    assert len(app.tree.get_children()) == 2


def test_read_only_details_disable_generator_length(app):
    unlock(app)
    add(app)
    select_first(app)
    assert app.length_picker.instate(["disabled"])
    assert "Read-only" in app.detail_hint.get()
    app.new_button.invoke()
    assert not app.length_picker.instate(["disabled"])


def test_missing_art_does_not_block_error_feedback(app):
    app.cat_error = None
    app.error(VaultError("Synthetic test error"))
    assert app.cat_mood == "error"
    assert "Oops!" in app.mascot_caption.cget("text")
    assert app.test_errors == ["Synthetic test error"]
    unlock(app)
    assert app.session.unlocked



def test_english_interface_text(app):
    import re
    def descendants(widget):
        yield widget
        for child in widget.winfo_children():
            yield from descendants(child)
    for widget in descendants(app.content):
        if "text" in widget.keys():
            assert not re.search(r"[\u4e00-\u9fff]", str(widget.cget("text")))


def test_primary_controls_fit_minimum_window(app):
    # Real Tk geometry validation, not a claim of human visual review.
    root = app.root
    root.geometry("1000x740")
    root.deiconify()
    root.update()
    def inside(widget):
        assert widget.winfo_ismapped()
        left = widget.winfo_rootx() - root.winfo_rootx()
        top = widget.winfo_rooty() - root.winfo_rooty()
        assert left >= 0 and top >= 0
        assert left + widget.winfo_width() <= root.winfo_width()
        assert top + widget.winfo_height() <= root.winfo_height()
    try:
        for widget in (app.path_entry, app.master_entry, app.create_button, app.unlock_button, app.status_label):
            inside(widget)
        unlock(app)
        for widget in (app.search_entry, app.new_button, app.save_button, app.delete_button,
                       app.generate_button, app.length_picker, app.lock_button, app.status_label):
            inside(widget)
    finally:
        root.withdraw()



def test_new_entry_decoration_follows_form_mode(app):
    unlock(app)
    assert str(app.cat_new) in str(app.new_entry_art.cget("image"))
    add(app)
    select_first(app)
    assert not app.new_entry_art.cget("image")
    app.new_button.invoke()
    assert str(app.cat_new) in str(app.new_entry_art.cget("image"))



def test_validation_and_file_errors_use_distinct_reactions(app):
    app.error(VaultError("Invalid input"))
    assert app.error_kind == "input"
    assert str(app.cat_error) in str(app.mascot.cget("image"))
    app.error(OSError("Synthetic read failure"), kind="access")
    assert app.error_kind == "access"
    assert str(app.cat_access_error) in str(app.mascot.cget("image"))
    unlock(app)
    assert app.error_kind is None
    assert str(app.cat_portrait) in str(app.mascot.cget("image"))
