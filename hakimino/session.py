"""UI-independent unlocked session; the existing vault module owns persistence."""
from pathlib import Path

from .vault import VaultError, operate


class VaultSession:
    def __init__(self):
        self.path = None
        self._master = None

    @property
    def unlocked(self):
        return self._master is not None

    def lock(self):
        # Release references; Python cannot promise secure memory erasure.
        self._master = None
        self.path = None

    def open(self, path, master, *, create=False):
        self.lock()
        path = Path(path).absolute()
        if create:
            operate(path, master, "init")
        labels = operate(path, master, "list")
        self.path, self._master = path, master
        return labels

    def run(self, action, **kwargs):
        if not self.unlocked:
            raise VaultError("Unlock a vault first.")
        if action not in {"list", "show", "add", "delete"}:
            raise VaultError("Unsupported session operation.")
        return operate(self.path, self._master, action, **kwargs)
