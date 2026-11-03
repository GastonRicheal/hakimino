"""Small Tk desktop client. UI -> session -> vault, with no crypto in widgets."""
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .session import VaultSession
from .vault import VaultError, generate_password

IDLE_MS = 5 * 60 * 1000
REVEAL_MS = 15 * 1000


class VaultApp:
    def __init__(self, root, session=None):
        self.root = root
        self.session = session or VaultSession()
        self.labels = []
        self.selected = None
        self.idle_job = self.reveal_job = None
        root.title("Hakimino | Password Manager")
        root.geometry("1000x680")
        root.minsize(860, 620)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f5f9")
        style.configure("TLabel", background="#f3f5f9", foreground="#243047", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Accent.TButton", background="#244bc1", foreground="white")
        style.map("Accent.TButton", background=[("active", "#18368c")])
        style.configure("Treeview", rowheight=32, font=("Segoe UI", 10))
        self.path = tk.StringVar(root)
        self.master = tk.StringVar(root)
        self.query = tk.StringVar(root)
        self.label = tk.StringVar(root)
        self.username = tk.StringVar(root)
        self.password = tk.StringVar(root)
        self.reveal = tk.BooleanVar(root, False)
        self.status = tk.StringVar(root, "Locked — open an existing vault or create your first one.")
        self.heading = tk.StringVar(root, "New entry")
        self.content = ttk.Frame(root, padding=28)
        self.content.pack(fill="both", expand=True)
        ttk.Label(self.content, text="Hakimino", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.content, text="Your passwords, stored locally.").pack(anchor="w", pady=(2, 22))
        self._build_login()
        self._build_workspace()
        ttk.Label(self.content, textvariable=self.status, wraplength=900).pack(side="bottom", anchor="w", pady=(14, 0))
        self.login.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind_all("<KeyPress>", self.touch, add="+")
        root.bind_all("<ButtonPress>", self.touch, add="+")

    def _build_login(self):
        self.login = ttk.Frame(self.content, padding=(0, 20))
        ttk.Label(self.login, text="Open your vault", style="Heading.TLabel").pack(anchor="w", pady=(0, 18))
        ttk.Label(self.login, text="Vault file").pack(anchor="w")
        row = ttk.Frame(self.login)
        row.pack(fill="x", pady=(6, 18))
        ttk.Entry(row, textvariable=self.path).pack(side="left", fill="x", expand=True, ipady=6)
        ttk.Button(row, text="Browse…", command=self.browse).pack(side="left", padx=(10, 0))
        ttk.Label(self.login, text="Master password").pack(anchor="w")
        self.master_entry = ttk.Entry(self.login, textvariable=self.master, show="•")
        self.master_entry.pack(fill="x", pady=(6, 18), ipady=6)
        self.master_entry.bind("<Return>", lambda _: self.unlock())
        row = ttk.Frame(self.login)
        row.pack(anchor="w")
        self.unlock_button = ttk.Button(row, text="Unlock vault", style="Accent.TButton", command=self.unlock)
        self.unlock_button.pack(side="left")
        self.create_button = ttk.Button(row, text="Create new vault…", command=self.create)
        self.create_button.pack(side="left", padx=12)
        ttk.Label(self.login, text="For a new vault, enter a master passphrase of at least 12 characters.\nKeep it safe: there is no password recovery.", wraplength=760).pack(anchor="w", pady=24)

    def _build_workspace(self):
        self.workspace = ttk.Frame(self.content)
        top = ttk.Frame(self.workspace)
        top.pack(fill="x", pady=(0, 14))
        self.vault_name = ttk.Label(top, style="Heading.TLabel")
        self.vault_name.pack(side="left")
        self.lock_button = ttk.Button(top, text="Lock vault", command=self.lock)
        self.lock_button.pack(side="right")
        panes = ttk.Frame(self.workspace)
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=2)
        panes.columnconfigure(1, weight=3)
        panes.rowconfigure(0, weight=1)
        left = ttk.Frame(panes, padding=(0, 0, 24, 0))
        left.grid(row=0, column=0, sticky="nsew")
        ttk.Label(left, text="Search entries").pack(anchor="w")
        ttk.Entry(left, textvariable=self.query).pack(fill="x", pady=(6, 12), ipady=4)
        self.query.trace_add("write", lambda *_: self.filter_entries())
        self.tree = ttk.Treeview(left, columns=("label",), show="headings", selectmode="browse", height=8)
        self.tree.heading("label", text="Entry")
        self.tree.column("label", width=220)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.new_button = ttk.Button(left, text="+ Add entry", command=self.new_entry)
        self.new_button.pack(fill="x", pady=(12, 0))
        right = ttk.Frame(panes)
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(right, textvariable=self.heading, style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        self.fields = []
        for title, variable in [("Entry name", self.label), ("Username", self.username), ("Password", self.password)]:
            ttk.Label(right, text=title).pack(anchor="w")
            entry = ttk.Entry(right, textvariable=variable, show="•" if variable is self.password else "")
            entry.pack(fill="x", pady=(4, 12), ipady=5)
            self.fields.append(entry)
        self.reveal_button = ttk.Checkbutton(right, text="Show password (15 seconds)", variable=self.reveal, command=self.toggle_reveal)
        self.reveal_button.pack(anchor="w")
        self.generate_button = ttk.Button(right, text="Generate strong password", command=self.generate)
        self.generate_button.pack(anchor="w", pady=12)
        row = ttk.Frame(right)
        row.pack(fill="x", pady=(6, 0))
        self.save_button = ttk.Button(row, text="Save new entry", style="Accent.TButton", command=self.save)
        self.save_button.pack(side="left")
        self.delete_button = ttk.Button(row, text="Delete entry", command=self.delete)
        self.delete_button.pack(side="left", padx=10)
        ttk.Label(right, text="Locks after 5 minutes without keyboard or mouse clicks.", wraplength=380).pack(anchor="w", pady=18)

    def browse(self):
        path = filedialog.askopenfilename(parent=self.root, title="Open vault", filetypes=[("Encrypted vault", "*.vault")])
        if path:
            self.path.set(path)

    def unlock(self):
        self._open(False)

    def create(self):
        self._open(True)

    def _open(self, create):
        try:
            if create:
                if len(self.master.get()) < 12:
                    raise VaultError("Enter a master passphrase of at least 12 characters first.")
                confirm = simpledialog.askstring("Confirm master password", "Repeat your master password:", show="•", parent=self.root)
                if confirm is None:
                    return
                if confirm != self.master.get():
                    raise VaultError("Master passwords do not match.")
                path = filedialog.asksaveasfilename(parent=self.root, title="Create vault", defaultextension=".vault", filetypes=[("Encrypted vault", "*.vault")])
                if not path:
                    return
                self.path.set(path)
            if not self.path.get():
                raise VaultError("Choose a vault file first.")
            self.labels = self.session.open(self.path.get(), self.master.get(), create=create)
            self.login.pack_forget()
            self.workspace.pack(fill="both", expand=True)
            self.vault_name.configure(text=self.session.path.name)
            self.query.set("")
            self.filter_entries()
            self.new_entry()
            self.status.set(f"Unlocked · {len(self.labels)} entries")
            self.touch()
        except (VaultError, OSError) as exc:
            self.lock()
            self.error(exc)
        finally:
            self.master.set("")

    def filter_entries(self):
        self.clear_form()
        self.tree.delete(*self.tree.get_children())
        for index, label in enumerate(self.labels):
            if self.query.get().casefold() in label.casefold():
                self.tree.insert("", "end", iid=str(index), values=(label,))

    def clear_form(self):
        self.selected = None
        self.hide_password()
        for var in (self.label, self.username, self.password):
            var.set("")
        self.heading.set("New entry")
        for field in self.fields:
            field.configure(state="normal")
        self.save_button.configure(state="normal")
        self.generate_button.configure(state="normal")
        self.delete_button.configure(state="disabled")

    def new_entry(self):
        self.tree.selection_remove(*self.tree.selection())
        self.clear_form()

    def select(self, _=None):
        selection = self.tree.selection()
        if not selection or not self.session.unlocked:
            return
        self.clear_form()
        try:
            label = self.labels[int(selection[0])]
            entry = self.session.run("show", label=label)
            self.selected = label
            self.label.set(label)
            self.username.set(entry["username"])
            self.password.set(entry["password"])
            self.heading.set("Entry details")
            for field in self.fields:
                field.configure(state="readonly")
            self.save_button.configure(state="disabled")
            self.generate_button.configure(state="disabled")
            self.delete_button.configure(state="normal")
        except (VaultError, OSError) as exc:
            self.error(exc)

    def generate(self):
        if self.session.unlocked and self.selected is None:
            self.hide_password()
            self.password.set(generate_password())
            self.status.set("Generated a 24-character password. Save the entry to keep it.")

    def save(self):
        try:
            self.session.run("add", label=self.label.get(), username=self.username.get(), entry_password=self.password.get())
            self.labels = self.session.run("list")
            self.filter_entries()
            self.status.set("Entry saved.")
        except (VaultError, OSError) as exc:
            self.error(exc)

    def delete(self):
        label = self.selected
        if label is None:
            return
        if not messagebox.askyesno("Delete entry", "Permanently delete the selected entry?", parent=self.root):
            return
        try:
            # Auto-lock can run during a modal confirmation; run() rechecks session state.
            self.session.run("delete", label=label)
            self.labels = self.session.run("list")
            self.filter_entries()
            self.status.set("Entry deleted.")
        except (VaultError, OSError) as exc:
            self.error(exc)

    def toggle_reveal(self):
        self._cancel("reveal_job")
        self.fields[2].configure(show="" if self.reveal.get() else "•")
        if self.reveal.get():
            self.reveal_job = self.root.after(REVEAL_MS, self.hide_password)

    def hide_password(self):
        self._cancel("reveal_job")
        self.reveal.set(False)
        self.fields[2].configure(show="•")

    def _cancel(self, name):
        job = getattr(self, name)
        if job is not None:
            self.root.after_cancel(job)
            setattr(self, name, None)

    def touch(self, _=None):
        if self.session.unlocked:
            self._cancel("idle_job")
            self.idle_job = self.root.after(IDLE_MS, self.lock)

    def lock(self):
        self._cancel("idle_job")
        self.session.lock()
        self.labels = []
        self.query.set("")
        self.clear_form()
        self.master.set("")
        self.tree.delete(*self.tree.get_children())
        self.vault_name.configure(text="")
        self.workspace.pack_forget()
        self.login.pack(fill="both", expand=True)
        self.status.set("Vault locked. Enter your master password to continue.")

    def error(self, exc):
        messagebox.showerror("Could not complete operation", str(exc), parent=self.root)

    def close(self):
        self.lock()
        self.root.destroy()


def main():
    root = tk.Tk()
    VaultApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
