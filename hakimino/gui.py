"""Small Tk desktop client. UI -> session -> vault, with no crypto in widgets."""
import tkinter as tk
from importlib.resources import files
from math import ceil
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

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
        root.title("Hakimino | Your private vault")
        root.geometry("1120x780")
        root.minsize(1000, 740)
        self._configure_styles()
        self.cat_portrait = self._load_sticker("guardian.png", 150)
        self.cat_empty = self._load_sticker("empty-state.png", 180)
        self.cat_error = self._load_sticker("error-state.png", 180)
        self.cat_access_error = self._load_sticker("access-error.png", 150)
        self.cat_welcome = self._load_sticker("welcome.png", 120)
        self.cat_new = self._load_sticker("new-entry.png", 56)
        self.cat_mood = "guard"
        self.error_kind = None
        self.path = tk.StringVar(root)
        self.master = tk.StringVar(root)
        self.query = tk.StringVar(root)
        self.label = tk.StringVar(root)
        self.username = tk.StringVar(root)
        self.password = tk.StringVar(root)
        self.reveal = tk.BooleanVar(root, False)
        self.length = tk.StringVar(root, "24")
        self.count = tk.StringVar(root, "0 entries")
        self.empty_message = tk.StringVar(root, "No secrets yet.\nGive this cat something to guard.")
        self.session_state = tk.StringVar(root, "VAULT LOCKED")
        self.status = tk.StringVar(root, "Ready when you are. Open a vault or create a new one.")
        self.heading = tk.StringVar(root, "New entry")
        self.detail_hint = tk.StringVar(root, "Give this account a name you will recognize.")
        self.content = ttk.Frame(root)
        self.content.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(self.content, style="Sidebar.TFrame", width=210, padding=24)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ttk.Label(self.sidebar, text="/\\_/\\", style="Brand.TLabel").pack(anchor="w", pady=(4, 10))
        ttk.Label(self.sidebar, text="Hakimino", style="SidebarTitle.TLabel").pack(anchor="w")
        ttk.Label(self.sidebar, text="Small paws. Strong secrets.", style="SidebarMuted.TLabel").pack(anchor="w", pady=(4, 40))
        ttk.Label(self.sidebar, text="MAODIE EDITION", style="SidebarSmall.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(self.sidebar, text="  My vault", style="Nav.TLabel", padding=(12, 12)).pack(fill="x")
        ttk.Label(self.sidebar, textvariable=self.count, style="SidebarMuted.TLabel").pack(anchor="w", pady=(12, 0))
        self.mascot = ttk.Label(self.sidebar, image=self.cat_portrait or "", style="SidebarMuted.TLabel")
        self.mascot.pack(pady=(28, 10))
        self.mascot_caption = ttk.Label(self.sidebar, text="Head of vault security.\nNot accepting visitors.",
                                        style="SidebarMuted.TLabel", wraplength=160, justify="left")
        self.mascot_caption.pack(anchor="w")
        footer = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, text="LOCAL BY DESIGN", style="SidebarSmall.TLabel").pack(anchor="w")
        ttk.Label(footer, text="No cloud account.\nNo server connection.\nYour vault stays with you.",
                  style="SidebarMuted.TLabel", wraplength=160, justify="left").pack(anchor="w", pady=(10, 0))
        self.main_area = ttk.Frame(self.content, padding=(28, 22))
        self.main_area.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(self.main_area)
        header.pack(fill="x", pady=(0, 20))
        ttk.Label(header, text="Your cozy corner", style="PageTitle.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.session_state, style="Badge.TLabel", padding=(12, 7)).pack(side="right")
        status_bar = ttk.Frame(self.main_area)
        status_bar.pack(side="bottom", fill="x", pady=(16, 0))
        ttk.Separator(status_bar).pack(fill="x", pady=(0, 10))
        self.status_label = ttk.Label(status_bar, textvariable=self.status, style="Muted.TLabel", wraplength=700)
        self.status_label.pack(anchor="w")
        self._build_login()
        self._build_workspace()
        self.login.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind_all("<KeyPress>", self.touch, add="+")
        root.bind_all("<ButtonPress>", self.touch, add="+")
        self.master_entry.focus_set()

    def _load_sticker(self, name, maximum):
        """Load a bundled PNG sticker; no network or extra image dependency."""
        try:
            asset = files("hakimino").joinpath("assets", name)
            raw = tk.PhotoImage(master=self.root, data=asset.read_bytes(), format="png")
            factor = max(1, ceil(max(raw.width(), raw.height()) / maximum))
            return raw.subsample(factor, factor)
        except (OSError, tk.TclError):
            # Decorative art must never block access to an encrypted vault.
            return None

    def _configure_styles(self):
        family = tkfont.nametofont("TkDefaultFont").actual("family")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        bg, ink, muted, accent = "#fbf5eb", "#392b26", "#78675e", "#a54c2b"
        self.root.configure(background=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=ink, font=(family, 11))
        style.configure("Muted.TLabel", foreground=muted, font=(family, 10))
        style.configure("Error.TLabel", foreground="#a33422", font=(family, 10, "bold"))
        style.configure("PageTitle.TLabel", font=(family, 20, "bold"))
        style.configure("Hero.TLabel", font=(family, 29, "bold"))
        style.configure("Heading.TLabel", font=(family, 17, "bold"))
        style.configure("Small.TLabel", foreground=muted, font=(family, 9, "bold"))
        style.configure("Badge.TLabel", background="#f6e4ca", foreground="#79401e", font=(family, 9, "bold"))
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Card.TLabel", background="#ffffff")
        style.configure("CardHeading.TLabel", background="#ffffff", font=(family, 17, "bold"))
        style.configure("CardMuted.TLabel", background="#ffffff", foreground=muted, font=(family, 10))
        style.configure("Sidebar.TFrame", background="#35271f")
        for name, color, size, weight in [
            ("Brand", "#f2c98d", 26, "bold"), ("SidebarTitle", "#ffffff", 19, "bold"),
            ("SidebarMuted", "#e5d1ba", 10, "normal"), ("SidebarSmall", "#cbb297", 8, "bold")]:
            style.configure(name + ".TLabel", background="#35271f", foreground=color, font=(family, size, weight))
        style.configure("Nav.TLabel", background="#59402e", foreground="#ffffff", font=(family, 11, "bold"))
        style.configure("TEntry", padding=8, fieldbackground="#ffffff", foreground=ink,
                        bordercolor="#d5c4b4", lightcolor="#d5c4b4", darkcolor="#d5c4b4", insertcolor=ink)
        style.map("TEntry", bordercolor=[("focus", accent)],
                  fieldbackground=[("readonly", "#f4eee6")])
        style.configure("TButton", font=(family, 10, "bold"), padding=(12, 10),
                        background="#f1e7d8", foreground=ink, borderwidth=0)
        style.map("TButton", background=[("active", "#e4d4bd")], foreground=[("disabled", "#9b8879")])
        style.configure("Accent.TButton", background=accent, foreground="#ffffff")
        style.map("Accent.TButton", background=[("disabled", "#e7ddce"), ("active", "#81391d")],
                  foreground=[("disabled", "#8a7563")])
        style.configure("Danger.TButton", background="#f8ebe8", foreground="#8c3e32")
        style.map("Danger.TButton", background=[("active", "#f0d4cd")])
        style.configure("TCheckbutton", background="#ffffff", foreground=ink, font=(family, 10), padding=4)
        style.map("TCheckbutton", background=[("active", "#ffffff")])
        style.configure("TSpinbox", padding=6, fieldbackground="#ffffff", arrowsize=14)
        style.configure("Treeview", rowheight=42, font=(family, 11), background="#ffffff",
                        fieldbackground="#ffffff", foreground=ink, borderwidth=0)
        style.configure("Treeview.Heading", font=(family, 9, "bold"), background="#f6eddf",
                        foreground=muted, padding=8, relief="flat")
        style.map("Treeview", background=[("selected", "#f6dfbc")], foreground=[("selected", "#743b1c")])

    def _build_login(self):
        self.login = ttk.Frame(self.main_area)
        ttk.Label(self.login, text="MAODIE IS ON GUARD. YOUR SECRETS STAY LOCAL.", style="Small.TLabel").pack(anchor="w", pady=(4, 12))
        hero = ttk.Frame(self.login)
        hero.pack(fill="x")
        if self.cat_welcome is not None:
            ttk.Label(hero, image=self.cat_welcome).pack(side="right", padx=(16, 0))
        ttk.Label(hero, text="Big cat energy.\nLittle secret keeper.", style="Hero.TLabel", justify="left").pack(side="left", anchor="w")
        ttk.Label(self.login, text="A grumpy little guardian for your logins. Encrypted, right here on your device.",
                  style="Muted.TLabel", wraplength=650).pack(anchor="w", pady=(12, 22))
        card = ttk.Frame(self.login, style="Card.TFrame", padding=24)
        card.pack(fill="x")
        ttk.Label(card, text="Open your vault", style="CardHeading.TLabel").pack(anchor="w", pady=(0, 16))
        ttk.Label(card, text="Vault file", style="Card.TLabel").pack(anchor="w")
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", pady=(6, 14))
        self.path_entry = ttk.Entry(row, textvariable=self.path)
        self.path_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self.browse).pack(side="left", padx=(10, 0))
        ttk.Label(card, text="Master passphrase", style="Card.TLabel").pack(anchor="w")
        self.master_entry = ttk.Entry(card, textvariable=self.master, show="•")
        self.master_entry.pack(fill="x", pady=(6, 16))
        self.master_entry.bind("<Return>", lambda _: self.unlock())
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x")
        self.unlock_button = ttk.Button(row, text="Unlock vault", style="Accent.TButton", command=self.unlock)
        self.unlock_button.pack(side="left")
        self.create_button = ttk.Button(row, text="Create new vault…", command=self.create)
        self.create_button.pack(side="left", padx=12)
        ttk.Label(card, text="New here? Enter a passphrase of at least 12 characters, then create a vault.\nKeep it safe: a lost master passphrase cannot be recovered.",
                  style="CardMuted.TLabel", wraplength=600, justify="left").pack(anchor="w", pady=(18, 0))
        ttk.Label(self.login, text="ARGON2id KEY DERIVATION     /     AES-256-GCM ENCRYPTION",
                  style="Small.TLabel", wraplength=650).pack(anchor="w", pady=(20, 0))

    def _build_workspace(self):
        self.workspace = ttk.Frame(self.main_area)
        top = ttk.Frame(self.workspace)
        top.pack(fill="x", pady=(0, 18))
        self.vault_name = ttk.Label(top, style="Heading.TLabel", wraplength=420)
        self.vault_name.pack(side="left")
        self.lock_button = ttk.Button(top, text="Lock vault", command=self.lock)
        self.lock_button.pack(side="right")
        # Reserve space outside the form before allocating the expandable panes.
        # Safety guidance must not be clipped by a crowded entry-details card.
        self.lock_hint = ttk.Label(
            self.workspace,
            text="Auto-lock after 5 minutes without typing or clicks.\n"
                 "Locking clears displayed secrets and unsaved input.",
            style="Muted.TLabel", wraplength=700)
        self.lock_hint.pack(side="bottom", fill="x", pady=(10, 0))
        panes = ttk.Frame(self.workspace)
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=2, minsize=240)
        panes.columnconfigure(1, weight=3, minsize=380)
        panes.rowconfigure(0, weight=1)
        left = ttk.Frame(panes, style="Card.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ttk.Label(left, text="The secret stash", style="CardHeading.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(left, text="Search by entry name", style="CardMuted.TLabel").pack(anchor="w")
        search = ttk.Frame(left, style="Card.TFrame")
        search.pack(fill="x", pady=(6, 12))
        self.search_entry = ttk.Entry(search, textvariable=self.query, width=14)
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.clear_search_button = ttk.Button(search, text="Clear", command=lambda: self.query.set(""))
        self.clear_search_button.pack(side="right", padx=(6, 0))
        self.query.trace_add("write", lambda *_: self.filter_entries())
        self.new_button = ttk.Button(left, text="+ Add entry", style="Accent.TButton", command=self.new_entry)
        self.new_button.pack(side="bottom", fill="x", pady=(14, 0))
        self.list_area = ttk.Frame(left, style="Card.TFrame")
        self.list_area.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(self.list_area, columns=("label",), show="headings", selectmode="browse", height=7)
        self.tree.heading("label", text="ACCOUNT")
        self.tree.column("label", width=180, minwidth=100)
        scroll = ttk.Scrollbar(self.list_area, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.empty_label = ttk.Label(self.list_area, textvariable=self.empty_message, style="CardMuted.TLabel",
                                     wraplength=170, justify="center", anchor="center",
                                     image=self.cat_empty or "", compound="top", padding=8)
        right = ttk.Frame(panes, style="Card.TFrame", padding=14)
        right.grid(row=0, column=1, sticky="nsew")
        self.entry_header = ttk.Frame(right, style="Card.TFrame")
        self.entry_header.pack(fill="x")
        self.new_entry_art = ttk.Label(self.entry_header, image=self.cat_new or "", style="Card.TLabel")
        self.new_entry_art.pack(side="right", padx=(8, 0))
        ttk.Label(self.entry_header, textvariable=self.heading, style="CardHeading.TLabel").pack(side="left", anchor="w")
        ttk.Label(right, textvariable=self.detail_hint, style="CardMuted.TLabel", wraplength=320).pack(anchor="w", pady=(6, 8))
        self.fields = []
        for title, variable in [("Entry name", self.label), ("Username", self.username), ("Password", self.password)]:
            ttk.Label(right, text=title, style="Card.TLabel").pack(anchor="w")
            entry = ttk.Entry(right, textvariable=variable, show="•" if variable is self.password else "", width=24)
            entry.pack(fill="x", pady=(5, 6))
            self.fields.append(entry)
        self.reveal_button = ttk.Checkbutton(right, text="Show password for 15 seconds", variable=self.reveal, command=self.toggle_reveal)
        self.reveal_button.pack(anchor="w")
        generator = ttk.Frame(right, style="Card.TFrame")
        generator.pack(fill="x", pady=(6, 10))
        ttk.Label(generator, text="Length", style="CardMuted.TLabel").pack(side="left", padx=(0, 8))
        self.length_picker = ttk.Spinbox(generator, from_=16, to=128, textvariable=self.length, width=4)
        self.length_picker.pack(side="left")
        self.generate_button = ttk.Button(generator, text="Generate password", command=self.generate)
        self.generate_button.pack(side="right")
        row = ttk.Frame(right, style="Card.TFrame")
        row.pack(fill="x", pady=(4, 0))
        self.save_button = ttk.Button(row, text="Save new entry", style="Accent.TButton", command=self.save)
        self.save_button.pack(side="left")
        self.delete_button = ttk.Button(row, text="Delete entry", style="Danger.TButton", command=self.delete)
        self.delete_button.pack(side="left", padx=(8, 0))

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
            self._set_mood("guard")
            self.session_state.set("VAULT UNLOCKED")
            self.status.set(f"Unlocked · {len(self.labels)} entries")
            self.touch()
        except (VaultError, OSError) as exc:
            self.lock()
            self.error(exc, kind="access")
        finally:
            self.master.set("")

    def filter_entries(self):
        self.clear_form()
        self.tree.delete(*self.tree.get_children())
        for index, label in enumerate(self.labels):
            if self.query.get().casefold() in label.casefold():
                self.tree.insert("", "end", iid=str(index), values=(label,))
        visible = len(self.tree.get_children())
        total = len(self.labels)
        self.count.set(f"{visible} / {total} entries" if self.query.get() else
                       f"{total} " + ("entry" if total == 1 else "entries"))
        if visible:
            self.empty_label.place_forget()
        else:
            self.empty_message.set("No matching entries.\nTry another name or clear search." if total else
                                   "No secrets yet.\nGive this cat something to guard.")
            self.empty_label.place(relx=0.46, rely=0.5, anchor="center")

    def clear_form(self):
        self.selected = None
        self.hide_password()
        for var in (self.label, self.username, self.password):
            var.set("")
        self.heading.set("New entry")
        self.new_entry_art.configure(image=self.cat_new or "")
        self.detail_hint.set("Give this account a name you will recognize.")
        self.length_picker.configure(state="normal")
        for field in self.fields:
            field.configure(state="normal")
        self.save_button.configure(state="normal")
        self.generate_button.configure(state="normal")
        self.delete_button.configure(state="disabled")

    def new_entry(self):
        self.tree.selection_remove(*self.tree.selection())
        self.clear_form()
        self.fields[0].focus_set()

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
            self.new_entry_art.configure(image="")
            self.detail_hint.set("Read-only view. Passwords stay hidden until revealed.")
            self.length_picker.configure(state="disabled")
            for field in self.fields:
                field.configure(state="readonly")
            self.save_button.configure(state="disabled")
            self.generate_button.configure(state="disabled")
            self.delete_button.configure(state="normal")
        except (VaultError, OSError) as exc:
            self.error(exc, kind="access")

    def generate(self):
        if self.session.unlocked and self.selected is None:
            try:
                length = int(self.length.get())
                password = generate_password(length)
            except (ValueError, VaultError):
                self.error(VaultError("Choose a whole-number password length from 16 to 128."))
                return
            self.hide_password()
            self.password.set(password)
            self._set_mood("guard")
            self.status.set(f"Generated a {length}-character password. Save the entry to keep it.")

    def save(self):
        try:
            self.session.run("add", label=self.label.get(), username=self.username.get(), entry_password=self.password.get())
            self.labels = self.session.run("list")
            self.filter_entries()
            self._set_mood("guard")
            self.status.set("Entry saved. Another secret under cat protection.")
        except (VaultError, OSError) as exc:
            self.error(exc, kind="access" if isinstance(exc, OSError) else "input")

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
            self._set_mood("guard")
            self.status.set("Entry deleted.")
        except (VaultError, OSError) as exc:
            self.error(exc, kind="access" if isinstance(exc, OSError) else "input")

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
        self._set_mood("guard")
        self.session_state.set("VAULT LOCKED")
        self.status.set("Vault locked. Enter your master passphrase to continue.")
        self.master_entry.focus_set()

    def _set_mood(self, mood, kind=None):
        self.cat_mood = mood
        self.error_kind = kind if mood == "error" else None
        has_error = mood == "error"
        error_art = self.cat_access_error if kind == "access" else self.cat_error
        picture = error_art if has_error else self.cat_portrait
        self.mascot.configure(image=picture or "")
        self.mascot_caption.configure(text="Oops! Something went wrong.\nCheck the message and try again." if has_error else
                                      "Head of vault security.\nNot accepting visitors.")
        self.status_label.configure(style="Error.TLabel" if has_error else "Muted.TLabel")

    def error(self, exc, *, kind="input"):
        self._set_mood("error", kind)
        # Keep detailed diagnostics in the existing modal. Never copy input secrets
        # into the persistent status area or a screenshot-friendly mascot caption.
        self.status.set("Oops! The operation could not be completed. Review the error and try again.")
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
