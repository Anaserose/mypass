import base64
import hashlib
import json
import os
import random
import re
import secrets
import string
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import ttk, messagebox

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
VAULTS_DIR = os.path.join(DATA_DIR, "vaults")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
LOGO_PATH = os.path.join(APP_DIR, "assets", "logo.png")

KDF_ITERATIONS = 390_000
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_HOURS = 24

os.makedirs(VAULTS_DIR, exist_ok=True)

COLORS = {
    "bg": "#1B1F27",
    "bg_card": "#242A35",
    "bg_input": "#2E3542",
    "accent": "#00A896",
    "accent_dark": "#028090",
    "text": "#EDEDED",
    "text_muted": "#8B93A1",
    "border": "#3A4150",
    "success": "#5FA37A",
    "danger": "#D9534F",
    "warning": "#F0AD4E",
}

FONT = "Helvetica"

def round_rect_points(x1, y1, x2, y2, r):
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


class CanvasButton(tk.Canvas):

    def __init__(self, master, text, command=None, width=200, height=40,
                 primary=True, radius=10, font_size=11):
        bg = COLORS["bg_card"] if isinstance(master, (tk.Frame,)) else COLORS["bg"]
        super().__init__(master, width=width, height=height, bg=bg,
                          highlightthickness=0, cursor="hand2")
        self.command = command
        self.fill = COLORS["accent"] if primary else COLORS["bg_input"]
        self.hover_fill = COLORS["accent_dark"] if primary else COLORS["border"]
        self.text_color = "#FFFFFF" if primary else COLORS["text"]

        self.shape = self.create_polygon(
            round_rect_points(1, 1, width - 1, height - 1, radius),
            smooth=True, fill=self.fill, outline="",
        )
        self.label = self.create_text(
            width / 2, height / 2, text=text,
            fill=self.text_color, font=(FONT, font_size, "bold"),
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event):
        self.itemconfig(self.shape, fill=self.hover_fill)

    def _on_leave(self, _event):
        self.itemconfig(self.shape, fill=self.fill)

    def _on_click(self, _event):
        if self.command:
            self.command()

    def set_text(self, text):
        self.itemconfig(self.label, text=text)

class LabeledEntry(tk.Frame):
    def __init__(self, master, label_text, show=None):
        super().__init__(master, bg=COLORS["bg_card"])
        tk.Label(
            self, text=label_text, bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=(FONT, 10, "bold"), anchor="w",
        ).pack(fill="x")

        self.var = tk.StringVar()
        row = tk.Frame(self, bg=COLORS["bg_card"])
        row.pack(fill="x", pady=(4, 0))

        self._hidden_char = show
        self.entry = tk.Entry(
            row, textvariable=self.var, show=show,
            bg=COLORS["bg_input"], fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", font=(FONT, 13),
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=8)

        if show:
            self._visible = False
            self.toggle_btn = tk.Label(
                row, text="👁", bg=COLORS["bg_input"], fg=COLORS["text_muted"],
                font=(FONT, 12), cursor="hand2", padx=8,
            )
            self.toggle_btn.pack(side="left", fill="y")
            self.toggle_btn.bind("<Button-1>", self._toggle_visibility)

    def _toggle_visibility(self, _event=None):
        self._visible = not self._visible
        self.entry.config(show="" if self._visible else self._hidden_char)
        self.toggle_btn.config(fg=COLORS["accent"] if self._visible else COLORS["text_muted"])

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)

    def clear(self):
        self.var.set("")

def generate_password(length=16, upper=True, digits=True, symbols=True):
    pool = list(string.ascii_lowercase)
    required = [secrets.choice(string.ascii_lowercase)]

    if upper:
        pool += list(string.ascii_uppercase)
        required.append(secrets.choice(string.ascii_uppercase))
    if digits:
        pool += list(string.digits)
        required.append(secrets.choice(string.digits))
    if symbols:
        sym = "!@#$%^&*()-_=+?"
        pool += list(sym)
        required.append(secrets.choice(sym))

    length = max(length, len(required))
    remaining = length - len(required)
    chars = required + [secrets.choice(pool) for _ in range(remaining)]
    random.SystemRandom().shuffle(chars)
    return "".join(chars)

def derive_key(secret: str, salt: bytes, iterations=KDF_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))


def vault_path_for(email: str) -> str:
    safe_name = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()
    return os.path.join(VAULTS_DIR, f"{safe_name}.enc")


def atomic_write(path: str, data: bytes):
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)


class VaultCorrupted(Exception):
    """Raised when a vault file exists but can't be decrypted or parsed."""


def load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def save_users(users: dict):
    atomic_write(USERS_FILE, json.dumps(users, indent=2).encode("utf-8"))


def load_vault(fernet: Fernet, email: str) -> list:
    path = vault_path_for(email)
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        token = f.read()
    if not token:
        return []
    try:
        return json.loads(fernet.decrypt(token).decode("utf-8"))
    except (InvalidToken, ValueError) as exc:
        raise VaultCorrupted(f"Could not read the vault for {email}.") from exc


def save_vault(fernet: Fernet, email: str, entries: list):
    atomic_write(vault_path_for(email), fernet.encrypt(json.dumps(entries).encode("utf-8")))


def register_user(users, email, password, recovery_passphrase) -> bytes:
    vault_key = Fernet.generate_key()

    pw_salt = secrets.token_bytes(16)
    pw_key = derive_key(password, pw_salt, KDF_ITERATIONS)
    wrapped_by_password = Fernet(pw_key).encrypt(vault_key).decode("utf-8")

    rec_salt = secrets.token_bytes(16)
    rec_key = derive_key(recovery_passphrase.strip().lower(), rec_salt, KDF_ITERATIONS)
    wrapped_by_recovery = Fernet(rec_key).encrypt(vault_key).decode("utf-8")

    users[email.lower()] = {
        "email": email,
        "pw_kdf_iterations": KDF_ITERATIONS,
        "rec_kdf_iterations": KDF_ITERATIONS,
        "pw_salt": base64.b64encode(pw_salt).decode("utf-8"),
        "wrapped_by_password": wrapped_by_password,
        "rec_salt": base64.b64encode(rec_salt).decode("utf-8"),
        "wrapped_by_recovery": wrapped_by_recovery,
    }
    save_users(users)
    save_vault(Fernet(vault_key), email, [])
    return vault_key


def login_user(users, email, password):
    record = users.get(email.lower())
    if not record:
        return None
    pw_salt = base64.b64decode(record["pw_salt"])
    iterations = record.get("pw_kdf_iterations", KDF_ITERATIONS)
    pw_key = derive_key(password, pw_salt, iterations)
    try:
        return Fernet(pw_key).decrypt(record["wrapped_by_password"].encode("utf-8"))
    except InvalidToken:
        return None


def lockout_remaining(record):
    until = record.get("lockout_until")
    if not until:
        return None
    remaining = datetime.fromisoformat(until) - datetime.now(timezone.utc)
    return remaining if remaining.total_seconds() > 0 else None


def format_remaining(delta):
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    minutes = rem // 60
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def record_failed_attempt(users, email):
    record = users[email.lower()]
    record["failed_attempts"] = record.get("failed_attempts", 0) + 1
    if record["failed_attempts"] >= MAX_LOGIN_ATTEMPTS:
        record["lockout_until"] = (datetime.now(timezone.utc) + timedelta(hours=LOCKOUT_HOURS)).isoformat()
    save_users(users)


def clear_failed_attempts(users, email):
    record = users[email.lower()]
    record["failed_attempts"] = 0
    record["lockout_until"] = None
    save_users(users)


def clear_lockout_if_expired(users, email):
    record = users[email.lower()]
    if record.get("lockout_until") and lockout_remaining(record) is None:
        clear_failed_attempts(users, email)


def attempt_recovery(users, email, passphrase):
    record = users.get(email.lower())
    if not record:
        return None
    rec_salt = base64.b64decode(record["rec_salt"])
    iterations = record.get("rec_kdf_iterations", KDF_ITERATIONS)
    rec_key = derive_key(passphrase.strip().lower(), rec_salt, iterations)
    try:
        return Fernet(rec_key).decrypt(record["wrapped_by_recovery"].encode("utf-8"))
    except InvalidToken:
        return None


def reset_password(users, email, new_password, vault_key: bytes):
    record = users[email.lower()]
    pw_salt = secrets.token_bytes(16)
    pw_key = derive_key(new_password, pw_salt, KDF_ITERATIONS)
    record["pw_salt"] = base64.b64encode(pw_salt).decode("utf-8")
    record["wrapped_by_password"] = Fernet(pw_key).encrypt(vault_key).decode("utf-8")
    record["pw_kdf_iterations"] = KDF_ITERATIONS
    record["failed_attempts"] = 0
    record["lockout_until"] = None
    save_users(users)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    return EMAIL_PATTERN.match(email)

class MyPassApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MyPass")
        self.geometry("900x600")
        self.minsize(820, 560)
        self.configure(bg=COLORS["bg"])

        self.users = load_users()
        self.vault_key = None
        self.fernet = None
        self.entries = []
        self.logged_in_email = None
        self.logo_img = None
        self._load_logo()

        self.container = tk.Frame(self, bg=COLORS["bg"])
        self.container.pack(fill="both", expand=True)

        self.show_login()

    def _load_logo(self):
        try:
            img = tk.PhotoImage(file=LOGO_PATH)
            factor = max(1, img.width() // 90)
            self.logo_img = img.subsample(factor, factor) if factor > 1 else img
        except Exception:
            self.logo_img = None

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_login(self):
        self._clear()
        LoginScreen(self.container, self).pack(fill="both", expand=True)

    def show_register(self):
        self._clear()
        RegistrationScreen(self.container, self).pack(fill="both", expand=True)

    def show_recovery(self):
        self._clear()
        RecoveryScreen(self.container, self).pack(fill="both", expand=True)

    def show_main(self):
        self._clear()
        MainScreen(self.container, self).pack(fill="both", expand=True)

    def complete_login(self, email, vault_key):
        fernet = Fernet(vault_key)
        try:
            entries = load_vault(fernet, email)
        except VaultCorrupted:
            messagebox.showerror(
                "Vault unreadable",
                "Your vault file appears to be corrupted and couldn't be read. "
                "Your account password is correct, but the saved entries could not be loaded.",
            )
            self.show_login()
            return

        self.logged_in_email = email
        self.vault_key = vault_key
        self.fernet = fernet
        self.entries = entries
        self.show_main()

    def logout(self):
        self.logged_in_email = None
        self.vault_key = None
        self.fernet = None
        self.entries = []
        self.show_login()

    def persist_vault(self):
        save_vault(self.fernet, self.logged_in_email, self.entries)

class LoginScreen(tk.Frame):
    def __init__(self, master, app: MyPassApp):
        super().__init__(master, bg=COLORS["bg"])
        self.app = app

        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(outer, bg=COLORS["bg_card"], padx=40, pady=32)
        card.pack()

        header = tk.Frame(card, bg=COLORS["bg_card"])
        header.pack(pady=(0, 18))
        if self.app.logo_img:
            tk.Label(header, image=self.app.logo_img, bg=COLORS["bg_card"]).pack()
        tk.Label(
            header, text="MyPass", bg=COLORS["bg_card"], fg=COLORS["text"],
            font=(FONT, 22, "bold"),
        ).pack(pady=(8, 0))
        tk.Label(
            header, text="Your offline, encrypted password vault",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"], font=(FONT, 10),
        ).pack()

        self.email_field = LabeledEntry(card, "EMAIL")
        self.email_field.pack(fill="x", pady=(4, 10))

        self.password_field = LabeledEntry(card, "PASSWORD", show="•")
        self.password_field.pack(fill="x", pady=(0, 10))
        self.password_field.entry.bind("<Return>", lambda e: self.on_login())

        self.error_label = tk.Label(
            card, text="", bg=COLORS["bg_card"], fg=COLORS["danger"], font=(FONT, 9),
        )
        self.error_label.pack(fill="x", pady=(2, 10))

        CanvasButton(card, "Log In", command=self.on_login, width=320, height=42).pack()

        register_row = tk.Frame(card, bg=COLORS["bg_card"])
        register_row.pack(pady=(14, 0))
        tk.Label(register_row, text="Don't have an account?", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                 font=(FONT, 9)).pack(side="left")
        register_link = tk.Label(register_row, text="Register", bg=COLORS["bg_card"], fg=COLORS["accent"],
                                  font=(FONT, 9, "bold"), cursor="hand2")
        register_link.pack(side="left")
        register_link.bind("<Button-1>", lambda e: self.app.show_register())

        forgot_link = tk.Label(
            card, text="Forgot password?", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=(FONT, 9, "underline"), cursor="hand2",
        )
        forgot_link.pack(pady=(6, 0))
        forgot_link.bind("<Button-1>", lambda e: self.app.show_recovery())

    def on_login(self):
        email = self.email_field.get().strip()
        password = self.password_field.get()
        checks = [
            (not email or not password, "Please enter both an email and a password."),
            (not is_valid_email(email), "Please enter a valid email address."),
        ]
        for failed, message in checks:
            if failed:
                self.error_label.config(text=message)
                return

        record = self.app.users.get(email.lower())
        if not record:
            self.error_label.config(text="No account found with this email.")
            return

        clear_lockout_if_expired(self.app.users, email)
        remaining = lockout_remaining(record)
        if remaining:
            self.error_label.config(
                text=f"Too many failed attempts. Try again in {format_remaining(remaining)}."
            )
            return

        vault_key = login_user(self.app.users, email, password)
        if vault_key is None:
            record_failed_attempt(self.app.users, email)
            attempts_left = MAX_LOGIN_ATTEMPTS - record["failed_attempts"]
            if attempts_left <= 0:
                self.error_label.config(
                    text="Incorrect password. Account locked for 24 hours."
                )
            else:
                self.error_label.config(
                    text=f"Incorrect password. {attempts_left} attempt(s) left before a 24-hour lock."
                )
            return

        clear_failed_attempts(self.app.users, email)
        self.app.complete_login(email, vault_key)

class RegistrationScreen(tk.Frame):
    def __init__(self, master, app: MyPassApp):
        super().__init__(master, bg=COLORS["bg"])
        self.app = app

        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(outer, bg=COLORS["bg_card"], padx=40, pady=28)
        card.pack()

        tk.Label(
            card, text="Create your MyPass account", bg=COLORS["bg_card"],
            fg=COLORS["text"], font=(FONT, 18, "bold"),
        ).pack(pady=(0, 16))

        self.email_field = LabeledEntry(card, "EMAIL")
        self.email_field.pack(fill="x", pady=(0, 0))

        pw_row = tk.Frame(card, bg=COLORS["bg_card"])
        pw_row.pack(fill="x", pady=(10, 0))
        self.password_field = LabeledEntry(pw_row, "PASSWORD", show="*")
        self.password_field.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.confirm_password_field = LabeledEntry(pw_row, "CONFIRM PASSWORD", show="*")
        self.confirm_password_field.pack(side="left", fill="x", expand=True)

        tk.Label(
            card, text="RECOVERY PASSPHRASE", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=(FONT, 9, "bold"), anchor="w",
        ).pack(fill="x", pady=(10, 0))
        tk.Label(
            card, text="Used only if you forget your password. Make it a sentence you'll\n"
                       "remember — at least 16 characters, longer is safer.",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"], font=(FONT, 8), justify="left", anchor="w",
        ).pack(fill="x")
        self.passphrase_field = LabeledEntry(card, "PASSPHRASE", show="•")
        self.passphrase_field.pack(fill="x", pady=(6, 0))
        self.confirm_passphrase_field = LabeledEntry(card, "CONFIRM PASSPHRASE", show="•")
        self.confirm_passphrase_field.pack(fill="x", pady=(10, 0))

        self.error_label = tk.Label(card, text="", bg=COLORS["bg_card"], fg=COLORS["danger"], font=(FONT, 9),
                                     wraplength=380)
        self.error_label.pack(fill="x", pady=(10, 10))

        CanvasButton(card, "Create Account", command=self.on_register, width=380, height=42).pack()

        back_row = tk.Frame(card, bg=COLORS["bg_card"])
        back_row.pack(pady=(14, 0))
        tk.Label(
            back_row, text="Already have an account?", bg=COLORS["bg_card"],
            fg=COLORS["text_muted"], font=(FONT, 9),
        ).pack(side="left")
        login_link = tk.Label(
            back_row, text=" Log In", bg=COLORS["bg_card"], fg=COLORS["accent"],
            font=(FONT, 9, "bold"), cursor="hand2",
        )
        login_link.pack(side="left")
        login_link.bind("<Button-1>", lambda e: self.app.show_login())


    def on_register(self):
        email = self.email_field.get().strip()
        password = self.password_field.get()
        confirm_password = self.confirm_password_field.get()
        passphrase = self.passphrase_field.get()
        confirm_passphrase = self.confirm_passphrase_field.get()

        checks = [
            (not all([email, password, confirm_password, passphrase, confirm_passphrase]),
             "Please fill in every field before creating your account."),
            (not is_valid_email(email),
             "Please enter a valid email address."),
            (len(password) < 8,
             "Password must be at least 8 characters."),
            (password != confirm_password,
             "Passwords do not match."),
            (len(passphrase) < 16,
             "Recovery passphrase must be at least 16 characters."),
            (passphrase != confirm_passphrase,
             "Recovery passphrases do not match."),
        ]
        for failed, message in checks:
            if failed:
                self.error_label.config(text=message)
                return

        if email.lower() in self.app.users:
            self.error_label.config(text="An account with this email already exists. Taking you to Log In…")
            self.after(1500, self.app.show_login)
            return

        vault_key = register_user(self.app.users, email, password, passphrase)
        self.app.complete_login(email, vault_key)

class RecoveryScreen(tk.Frame):

    def __init__(self, master, app: MyPassApp):
        super().__init__(master, bg=COLORS["bg"])
        self.app = app
        self.record = None
        self.recovered_vault_key = None

        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.place(relx=0.5, rely=0.5, anchor="center")

        self.card = tk.Frame(outer, bg=COLORS["bg_card"], padx=40, pady=32)
        self.card.pack()

        self._render_email_step()

    def _clear_card(self):
        for w in self.card.winfo_children():
            w.destroy()

    def _back_to_login_link(self):
        link = tk.Label(
            self.card, text="Back to Log In", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=(FONT, 9, "underline"), cursor="hand2",
        )
        link.pack(pady=(14, 0))
        link.bind("<Button-1>", lambda e: self.app.show_login())

    def _render_email_step(self):
        self._clear_card()
        tk.Label(
            self.card, text="Recover your account", bg=COLORS["bg_card"],
            fg=COLORS["text"], font=(FONT, 18, "bold"),
        ).pack(pady=(0, 16))

        self.email_field = LabeledEntry(self.card, "EMAIL")
        self.email_field.pack(fill="x", pady=(0, 10))

        self.error_label = tk.Label(self.card, text="", bg=COLORS["bg_card"], fg=COLORS["danger"], font=(FONT, 9))
        self.error_label.pack(fill="x", pady=(2, 10))

        CanvasButton(self.card, "Continue", command=self.on_email_submit, width=320, height=42).pack()
        self._back_to_login_link()

    def on_email_submit(self):
        email = self.email_field.get().strip()
        record = self.app.users.get(email.lower())
        if not record:
            self.error_label.config(text="No account found for this email.")
            return

        clear_lockout_if_expired(self.app.users, email)
        remaining = lockout_remaining(record)
        if remaining:
            self.error_label.config(
                text=f"This account is locked. Try again in {format_remaining(remaining)}."
            )
            return

        self.record = record
        self.record_email = email
        self._render_passphrase_step()  
        
    def _render_passphrase_step(self):
        self._clear_card()
        tk.Label(
            self.card, text="Enter your recovery passphrase", bg=COLORS["bg_card"],
            fg=COLORS["text"], font=(FONT, 18, "bold"),
        ).pack(pady=(0, 16))

        self.passphrase_field = LabeledEntry(self.card, "RECOVERY PASSPHRASE", show="•")
        self.passphrase_field.pack(fill="x", pady=(0, 10))

        self.error_label = tk.Label(self.card, text="", bg=COLORS["bg_card"], fg=COLORS["danger"], font=(FONT, 9))
        self.error_label.pack(fill="x", pady=(10, 10))

        CanvasButton(self.card, "Verify Passphrase", command=self.on_passphrase_submit, width=380, height=42).pack()
        self._back_to_login_link()

    def on_passphrase_submit(self):
        passphrase = self.passphrase_field.get()
        if not passphrase:
            self.error_label.config(text="Please enter your recovery passphrase.")
            return

        vault_key = attempt_recovery(self.app.users, self.record_email, passphrase)
        if vault_key is None:
            record_failed_attempt(self.app.users, self.record_email)
            attempts_left = MAX_LOGIN_ATTEMPTS - self.record["failed_attempts"]
            if attempts_left <= 0:
                self.error_label.config(text="Too many wrong attempts. Locked for 24 hours.")
                self.after(1500, self.app.show_login)
            else:
                self.error_label.config(
                    text=f"That passphrase doesn't match our records. {attempts_left} attempt(s) left."
                )
            return

        clear_failed_attempts(self.app.users, self.record_email)
        self.recovered_vault_key = vault_key
        self._render_new_password_step()

    def _render_new_password_step(self):
        self._clear_card()
        tk.Label(
            self.card, text="Set a new password", bg=COLORS["bg_card"],
            fg=COLORS["text"], font=(FONT, 18, "bold"),
        ).pack(pady=(0, 16))

        self.new_password_field = LabeledEntry(self.card, "NEW PASSWORD", show="•")
        self.new_password_field.pack(fill="x", pady=(0, 10))
        self.confirm_password_field = LabeledEntry(self.card, "CONFIRM NEW PASSWORD", show="•")
        self.confirm_password_field.pack(fill="x", pady=(0, 10))

        self.error_label = tk.Label(self.card, text="", bg=COLORS["bg_card"], fg=COLORS["danger"], font=(FONT, 9))
        self.error_label.pack(fill="x", pady=(2, 10))

        CanvasButton(self.card, "Reset Password & Log In", command=self.on_reset_submit,
                     width=380, height=42).pack()
        self._back_to_login_link()

    def on_reset_submit(self):
        new_password = self.new_password_field.get()
        confirm = self.confirm_password_field.get()

        checks = [
            (len(new_password) < 8, "Password must be at least 8 characters."),
            (new_password != confirm, "Passwords do not match."),
        ]
        for failed, message in checks:
            if failed:
                self.error_label.config(text=message)
                return

        reset_password(self.app.users, self.record_email, new_password, self.recovered_vault_key)
        self.app.complete_login(self.record_email, self.recovered_vault_key)


class MainScreen(tk.Frame):
    def __init__(self, master, app: MyPassApp):
        super().__init__(master, bg=COLORS["bg"])
        self.app = app

        self._build_topbar()
        self._build_status_banner()

        self.body = tk.Frame(self, bg=COLORS["bg"])
        self.body.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        body = self.body
        body.columnconfigure(0, weight=0, minsize=320)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_add_panel(body)
        self._build_vault_panel(body)

        self.refresh_table()

    def _build_topbar(self):
        bar = tk.Frame(self, bg=COLORS["bg_card"], padx=20, pady=12)
        bar.pack(fill="x")

        left = tk.Frame(bar, bg=COLORS["bg_card"])
        left.pack(side="left")
        if self.app.logo_img:
            tk.Label(left, image=self.app.logo_img, bg=COLORS["bg_card"]).pack(side="left", padx=(0, 8))
        tk.Label(
            left, text="MyPass", bg=COLORS["bg_card"], fg=COLORS["text"],
            font=(FONT, 15, "bold"),
        ).pack(side="left")

        CanvasButton(bar, "Log Out", command=self.app.logout, width=110, height=34,
                     primary=False, font_size=10).pack(side="right")

    def _build_status_banner(self):
        self.status_var = tk.StringVar(value="")
        self.status_banner = tk.Label(
            self, textvariable=self.status_var, bg=COLORS["accent"], fg="#FFFFFF",
            font=(FONT, 10, "bold"), anchor="center", pady=8,
        )

    def set_status(self, text):
        self.status_var.set(text)
        self.status_banner.pack(fill="x", before=self.body)
        self.after(2500, self._hide_status_banner)

    def _hide_status_banner(self):
        self.status_banner.pack_forget()

    def _build_add_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["bg_card"], padx=20, pady=18)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        tk.Label(
            panel, text="Add New Password", bg=COLORS["bg_card"], fg=COLORS["text"],
            font=(FONT, 13, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        self.website_field = LabeledEntry(panel, "WEBSITE")
        self.website_field.pack(fill="x", pady=(0, 10))

        self.username_field = LabeledEntry(panel, "USERNAME / EMAIL")
        self.username_field.pack(fill="x", pady=(0, 10))

        tk.Label(
            panel, text="PASSWORD", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=(FONT, 9, "bold"), anchor="w",
        ).pack(fill="x")

        self.password_var = tk.StringVar()
        pw_row = tk.Frame(panel, bg=COLORS["bg_card"])
        pw_row.pack(fill="x", pady=(4, 10))
        self.password_entry = tk.Entry(
            pw_row, textvariable=self.password_var, show="•",
            bg=COLORS["bg_input"], fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", font=(FONT, 11),
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        self.password_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self._pw_visible = False
        self.pw_toggle_btn = tk.Label(
            pw_row, text="👁", bg=COLORS["bg_input"], fg=COLORS["text_muted"],
            font=(FONT, 12), cursor="hand2", padx=8,
        )
        self.pw_toggle_btn.pack(side="left", fill="y")
        self.pw_toggle_btn.bind("<Button-1>", self._toggle_password_visibility)

        gen_box = tk.Frame(panel, bg=COLORS["bg_input"], padx=12, pady=10)
        gen_box.pack(fill="x", pady=(0, 6))

        tk.Label(
            gen_box, text="Password Generator", bg=COLORS["bg_input"], fg=COLORS["text"],
            font=(FONT, 10, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        tk.Label(
            gen_box, text="Length", bg=COLORS["bg_input"], fg=COLORS["text_muted"], font=(FONT, 9),
        ).grid(row=1, column=0, sticky="w")
        self.length_var = tk.IntVar(value=16)
        length_row = tk.Frame(gen_box, bg=COLORS["bg_input"])
        length_row.grid(row=1, column=1, sticky="w", padx=(6, 0))
        CanvasButton(length_row, "−", command=self._decrease_length, width=28, height=28,
                     primary=False, font_size=12).pack(side="left")
        tk.Label(
            length_row, textvariable=self.length_var, bg=COLORS["bg_input"], fg=COLORS["text"],
            font=(FONT, 11, "bold"), width=3, anchor="center",
        ).pack(side="left", padx=4)
        CanvasButton(length_row, "+", command=self._increase_length, width=28, height=28,
                     primary=False, font_size=12).pack(side="left")

        opts = tk.Frame(gen_box, bg=COLORS["bg_input"])
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 10))
        self.upper_var = tk.BooleanVar(value=True)
        self.digits_var = tk.BooleanVar(value=True)
        self.symbols_var = tk.BooleanVar(value=True)
        for text, var in (("A-Z", self.upper_var), ("0-9", self.digits_var), ("!@#", self.symbols_var)):
            tk.Checkbutton(
                opts, text=text, variable=var, bg=COLORS["bg_input"], fg=COLORS["text_muted"],
                selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_input"],
                font=(FONT, 9), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 10))

        CanvasButton(gen_box, "Generate Password", command=self.on_generate,
                     width=250, height=34, primary=False, font_size=10).grid(
            row=3, column=0, columnspan=3, sticky="w")

        CanvasButton(panel, "＋  Add to Vault", command=self.on_add_entry,
                     width=280, height=42).pack(pady=(16, 0))

    def _increase_length(self):
        self.length_var.set(min(64, self.length_var.get() + 1))

    def _decrease_length(self):
        self.length_var.set(max(8, self.length_var.get() - 1))

    def _toggle_password_visibility(self, _event=None):
        self._pw_visible = not self._pw_visible
        self.password_entry.config(show="" if self._pw_visible else "•")
        self.pw_toggle_btn.config(fg=COLORS["accent"] if self._pw_visible else COLORS["text_muted"])

    def on_generate(self):
        pw = generate_password(
            length=self.length_var.get(),
            upper=self.upper_var.get(),
            digits=self.digits_var.get(),
            symbols=self.symbols_var.get(),
        )
        self.password_var.set(pw)
        self._pw_visible = True
        self.password_entry.config(show="")
        self.pw_toggle_btn.config(fg=COLORS["accent"])
        self.set_status(f"Generated a {self.length_var.get()}-character password.")

    def on_add_entry(self):
        website = self.website_field.get().strip()
        username = self.username_field.get().strip()
        password = self.password_var.get()

        if not website or not username or not password:
            messagebox.showwarning(
                "Missing information",
                "Please provide a website, a username/email, and a password "
                "(or click Generate) before adding to the vault.",
            )
            return

        self.app.entries.append({"website": website, "username": username, "password": password})
        self.app.persist_vault()

        self.website_field.clear()
        self.username_field.clear()
        self.password_var.set("")
        self.password_entry.config(show="•")
        self._pw_visible = False
        self.pw_toggle_btn.config(fg=COLORS["text_muted"])

        self.set_status(f"Saved password for “{website}” to your encrypted vault.")
        self.refresh_table()

    def _build_vault_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["bg_card"], padx=20, pady=18)
        panel.grid(row=0, column=1, sticky="nsew")

        tk.Label(
            panel, text="Saved Passwords", bg=COLORS["bg_card"], fg=COLORS["text"],
            font=(FONT, 13, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(
            panel, text="Recover by website:", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=(FONT, 9, "bold"), anchor="w",
        ).pack(fill="x")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_table())
        tk.Entry(
            panel, textvariable=self.search_var,
            bg=COLORS["bg_input"], fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", font=(FONT, 11),
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        ).pack(fill="x", ipady=6, pady=(4, 10))

        table_frame = tk.Frame(panel, bg=COLORS["bg_card"])
        table_frame.pack(fill="both", expand=True, pady=(0, 10))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "MyPass.Treeview", background=COLORS["bg_input"], fieldbackground=COLORS["bg_input"],
            foreground=COLORS["text"], rowheight=28, borderwidth=0, font=(FONT, 10),
        )
        style.configure(
            "MyPass.Treeview.Heading", background=COLORS["bg_card"], foreground=COLORS["text_muted"],
            font=(FONT, 9, "bold"), borderwidth=0,
        )
        style.map("MyPass.Treeview", background=[("selected", COLORS["accent"])],
                  foreground=[("selected", "#FFFFFF")])

        columns = ("website", "username", "password")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                 style="MyPass.Treeview", selectmode="browse")
        self.tree.heading("website", text="WEBSITE")
        self.tree.heading("username", text="USERNAME / EMAIL")
        self.tree.heading("password", text="PASSWORD")
        self.tree.column("website", width=160)
        self.tree.column("username", width=180)
        self.tree.column("password", width=140)
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        actions = tk.Frame(panel, bg=COLORS["bg_card"])
        actions.pack(fill="x")
        CanvasButton(actions, "Reveal", command=self.on_reveal, width=90, height=34,
                     primary=False, font_size=10).pack(side="left")
        CanvasButton(actions, "Copy", command=self.on_copy, width=90, height=34,
                     primary=False, font_size=10).pack(side="left", padx=8)
        CanvasButton(actions, "Delete", command=self.on_delete, width=90, height=34,
                     primary=False, font_size=10).pack(side="left")

    def _filtered(self):
        query = self.search_var.get().strip().lower()
        if not query:
            return list(enumerate(self.app.entries))
        return [
            (i, e) for i, e in enumerate(self.app.entries)
            if query in e["website"].lower() or query in e["username"].lower()
        ]

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, e in self._filtered():
            self.tree.insert("", "end", iid=str(i),
                             values=(e["website"], e["username"], "•" * 10))

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select an entry from the list first.")
            return None
        return int(sel[0])

    def on_reveal(self):
        idx = self._selected_index()
        if idx is None:
            return
        entry = self.app.entries[idx]
        row_id = str(idx)
        currently_shown = self.tree.set(row_id, "password")
        if currently_shown == entry["password"]:
            self.tree.set(row_id, "password", "•" * 10)
            self.set_status("Password hidden.")
        else:
            self.tree.set(row_id, "password", entry["password"])
            self.set_status("Password revealed.")

    def on_copy(self):
        idx = self._selected_index()
        if idx is None:
            return
        entry = self.app.entries[idx]
        self.clipboard_clear()
        self.clipboard_append(entry["password"])
        self.app.after(30000, lambda pw=entry["password"]: self._clear_clipboard_if_unchanged(pw))
        self.set_status(f"Copied password for “{entry['website']}” to clipboard. "
                         f"Clipboard clears in 30s.")

    def _clear_clipboard_if_unchanged(self, copied_password):
        try:
            if self.app.clipboard_get() == copied_password:
                self.app.clipboard_clear()
        except tk.TclError:
            pass  

    def on_delete(self):
        idx = self._selected_index()
        if idx is None:
            return
        entry = self.app.entries[idx]
        if messagebox.askyesno("Delete entry", f"Remove the saved password for “{entry['website']}”?"):
            del self.app.entries[idx]
            self.app.persist_vault()
            self.refresh_table()
            self.set_status(f"Deleted entry for “{entry['website']}”.")


if __name__ == "__main__":
    app = MyPassApp()
    app.mainloop()
