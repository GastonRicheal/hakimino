"""UI-independent unlocked session; the existing vault module owns persistence."""
from pathlib import Path

from .vault import VaultError, operate


class VaultSession:
    def __init__(self):
        self.path = None
        self._master = None
        self.revision = None

    @property
    def unlocked(self):
        return self._master is not None

    def lock(self):
        # Release references; Python cannot promise secure memory erasure.
        self._master = None
        self.revision = None
        self.path = None

    def open(self, path, master, *, create=False):
        self.lock()
        path = Path(path).absolute()
        if create:
            operate(path, master, "init")
        snapshot = operate(path, master, "snapshot")
        self.path, self._master = path, master
        self.revision = snapshot["revision"]
        return snapshot["labels"]

    def run(self, action, **kwargs):
        if not self.unlocked:
            raise VaultError("Unlock a vault first.")
        if action not in {"list", "snapshot", "show", "add", "delete"}:
            raise VaultError("Unsupported session operation.")
        if action in {"list", "snapshot"}:
            snapshot = operate(self.path, self._master, "snapshot")
            self.revision = snapshot["revision"]
            return snapshot["labels"] if action == "list" else snapshot
        if action in {"show", "delete"}:
            kwargs.setdefault("expected_revision", self.revision)
        return operate(self.path, self._master, action, **kwargs)
