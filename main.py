import json
import os
import random
import re
import secrets
import string
import tkinter as tk
from tkinter import ttk, messagebox

VAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault_demo.json")

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users_demo.json")

SECURITY_QUESTION = [
    "What is your mother's maiden name?",
    "What was the name of your first pet?",
    "What was the make and model of your first car?",
    "What city were you born in?",
    "What was the name of your first school?",
]

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
        self.entry = tk.Entry(
            self, textvariable=self.var, show=show,
            bg=COLORS["bg_input"], fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", font=(FONT, 13),
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        self.entry.pack(fill="x", ipady=8, pady=(4, 0))

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


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_vault():
    data = load_json(VAULT_FILE, {})
    if not isinstance(data, dict):
        return {}
    return data


def save_vault(vault):
    save_json(VAULT_FILE, vault)


def load_users():
    return load_json(USERS_FILE, {})


def save_users(users):
    save_json(USERS_FILE, users)

class MyPassDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MyPass — Demo (JSON storage, unencrypted)")
        self.geometry("900x600")
        self.minsize(820, 560)
        self.configure(bg=COLORS["bg"])
        self.vault = load_vault()
        self.entries = []
        self.users = load_users()
        self.logged_in_email = None
        self.logo_img = None
        self._load_logo()

        self.container = tk.Frame(self, bg=COLORS["bg"])
        self.container.pack(fill="both", expand=True)

        self.show_login()

    def _load_logo(self):
        try:
            img = tk.PhotoImage(file="assets/logo.png")
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

    def show_main(self):
        self._clear()
        MainScreen(self.container, self).pack(fill="both", expand=True)

    def show_register(self):
        self._clear()
        RegistrationScreen(self.container, self).pack(fill="both", expand=True)

    def load_user_entries(self, email):
        self.entries = self.vault.setdefault(email.lower(), [])

    def logout(self):
        self.logged_in_email = None
        self.entries = []
        self.show_login()


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    return EMAIL_PATTERN.match(email)


class LoginScreen(tk.Frame):

    def __init__(self, master, app: MyPassDemo):
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
            header, text="Demo mode — saved as plain JSON, not encrypted",
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
                 font=(FONT, 9), ).pack(side="left")
        register_link = tk.Label(register_row, text="Register", bg=COLORS["bg_card"], fg=COLORS["accent"],
                                 font=(FONT, 9, "bold"), cursor="hand2", )
        register_link.pack(side="left")
        register_link.bind("<Button-1>", lambda e: self.app.show_register())

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

        user = self.app.users.get(email.lower())
        if not user:
            self.error_label.config(text="No account found for this email. Please register below.")
            return
        if user["password"] != password:
            self.error_label.config(text="Incorrect password. Please try again.")
            return

        self.app.logged_in_email = email
        self.app.load_user_entries(email)
        self.app.show_main()

class RegistrationScreen(tk.Frame):
    def __init__(self, master, app: MyPassDemo):
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

        name_row = tk.Frame(card, bg=COLORS["bg_card"])
        name_row.pack(fill="x")
        self.first_name_field = LabeledEntry(name_row, "FIRST NAME")
        self.first_name_field.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.last_name_field = LabeledEntry(name_row, "LAST NAME")
        self.last_name_field.pack(side="left", fill="x", expand=True)

        self.email_field = LabeledEntry(card, "EMAIL")
        self.email_field.pack(fill="x", pady=(10, 0))

        pw_row = tk.Frame(card, bg=COLORS["bg_card"])
        pw_row.pack(fill="x", pady=(10, 0))
        self.password_field = LabeledEntry(pw_row, "PASSWORD", show="*")
        self.password_field.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.confirm_password_field = LabeledEntry(pw_row, "CONFIRM PASSWORD", show="*")
        self.confirm_password_field.pack(side="left", fill="x", expand=True)

        info_row = tk.Frame(card, bg=COLORS["bg_card"])
        info_row.pack(fill="x", pady=(10, 0))
        self.age_field = LabeledEntry(info_row, "AGE")
        self.age_field.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.state_field = LabeledEntry(info_row, "STATE")
        self.state_field.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.country_field = LabeledEntry(info_row, "COUNTRY")
        self.country_field.pack(side="left", fill="x", expand=True)

        tk.Label(
            card, text="SECURITY QUESTIONS — pick and answer 2", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=(FONT, 9, "bold"), anchor="w",
        ).pack(fill="x", pady=(10, 0))

        self._remaining_questions = list(SECURITY_QUESTION)
        self.security_answers = []

        question_row = tk.Frame(card, bg=COLORS["bg_card"])
        question_row.pack(fill="x", pady=(4, 0))
        self.security_listbox = tk.Listbox(
            question_row, height=4, exportselection=False,
            bg=COLORS["bg_input"], fg=COLORS["text"], relief="flat",
            highlightthickness=1, highlightbackground=COLORS["border"],
            selectbackground=COLORS["accent"], font=(FONT, 10),
        )
        for q in self._remaining_questions:
            self.security_listbox.insert(tk.END, q)
        self.security_listbox.pack(side="left", fill="x", expand=True)
        question_scroll = ttk.Scrollbar(question_row, orient="vertical", command=self.security_listbox.yview)
        self.security_listbox.configure(yscrollcommand=question_scroll.set)
        question_scroll.pack(side="right", fill="y")

        self.security_answer_field = LabeledEntry(card, "ANSWER")
        self.security_answer_field.pack(fill="x", pady=(10, 0))

        self.security_status_label = tk.Label(
            card, text="Pick a question above, answer it, then click Save (2 needed).",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"], font=(FONT, 9), anchor="w",
        )
        self.security_status_label.pack(fill="x", pady=(4, 0))

        CanvasButton(card, "Save Security Question", command=self.on_save_security_question,
                     width=380, height=36, primary=False).pack(pady=(8, 0))

        self.recovery_email_field = LabeledEntry(card, "RECOVERY EMAIL(leave blank to reuse email above)")
        self.recovery_email_field.pack(fill="x", pady=(10, 0))

        self.error_label = tk.Label(card, text="", bg=COLORS["bg_card"], fg=COLORS["danger"], font=(FONT, 9),
                                    wraplength=380, )
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

    def on_save_security_question(self):
        if len(self.security_answers) >= 2:
            self.security_status_label.config(text="You've already picked 2 security questions.")
            return
        selection = self.security_listbox.curselection()
        if not selection:
            self.security_status_label.config(text="Please select a question from the list first.")
            return
        answer = self.security_answer_field.get().strip()
        if not answer:
            self.security_status_label.config(text="Please enter an answer for this question.")
            return

        question = self._remaining_questions.pop(selection[0])
        self.security_answers.append({"question": question, "answer": answer})

        self.security_listbox.delete(0, tk.END)
        for q in self._remaining_questions:
            self.security_listbox.insert(tk.END, q)
        self.security_answer_field.clear()

        if len(self.security_answers) < 2:
            self.security_status_label.config(text="Saved. Now pick your second security question.")
        else:
            self.security_status_label.config(text="Both security questions saved.")

    def on_register(self):
        first_name = self.first_name_field.get().strip()
        last_name = self.last_name_field.get().strip()
        email = self.email_field.get().strip()
        password = self.password_field.get()
        confirm_password = self.confirm_password_field.get()
        age = self.age_field.get().strip()
        state = self.state_field.get().strip()
        country = self.country_field.get().strip()
        recovery_email = self.recovery_email_field.get().strip() or email

        checks = [
            (not all([first_name, last_name, email, password, confirm_password, age, state, country]),
             "Please fill in every field before creating your account."),
            (len(self.security_answers) < 2,
             "Please pick and answer two security questions."),
            (not is_valid_email(email),
             "Please enter a valid email address."),
            (not is_valid_email(recovery_email),
             "Please enter a valid recovery email address."),
            (not age.isdigit(),
             "Age must be a number."),
            (password != confirm_password,
             "Passwords do not match."),
        ]
        for failed, message in checks:
            if failed:
                self.error_label.config(text=message)
                return

        if email.lower() in self.app.users:
            self.error_label.config(text="An account with this email already exists. Taking you to Log In…")
            self.after(1500, self.app.show_login)
            return

        self.app.users[email.lower()] = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
            "age": age,
            "state": state,
            "country": country,
            "security_questions": self.security_answers,  # list of 2 {"question", "answer"}
            "recovery_email": recovery_email,
        }
        save_users(self.app.users)

        self.app.logged_in_email = email
        self.app.load_user_entries(email)
        self.app.show_main()


class MainScreen(tk.Frame):
    def __init__(self, master, app: MyPassDemo):
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
            left, text="MyPass Demo", bg=COLORS["bg_card"], fg=COLORS["text"],
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
        self.password_entry = tk.Entry(
            panel, textvariable=self.password_var, show="•",
            bg=COLORS["bg_input"], fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", font=(FONT, 11),
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        self.password_entry.pack(fill="x", ipady=6, pady=(4, 10))

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
        tk.Spinbox(
            gen_box, from_=8, to=64, textvariable=self.length_var, width=4,
            bg=COLORS["bg_card"], fg=COLORS["text"], relief="flat",
            highlightthickness=1, highlightbackground=COLORS["border"], buttonbackground=COLORS["bg_card"],
        ).grid(row=1, column=1, sticky="w", padx=(6, 0))

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

    def on_generate(self):
        pw = generate_password(
            length=self.length_var.get(),
            upper=self.upper_var.get(),
            digits=self.digits_var.get(),
            symbols=self.symbols_var.get(),
        )
        self.password_var.set(pw)
        self.password_entry.config(show="")
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
        save_vault(self.app.vault)

        self.website_field.clear()
        self.username_field.clear()
        self.password_var.set("")
        self.password_entry.config(show="•")

        self.set_status(f"Saved password for “{website}” to vault_demo.json.")
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
        self.set_status(f"Copied password for “{entry['website']}” to clipboard.")

    def on_delete(self):
        idx = self._selected_index()
        if idx is None:
            return
        entry = self.app.entries[idx]
        if messagebox.askyesno("Delete entry", f"Remove the saved password for “{entry['website']}”?"):
            del self.app.entries[idx]
            save_vault(self.app.vault)
            self.refresh_table()
            self.set_status(f"Deleted entry for “{entry['website']}”.")


if __name__ == "__main__":
    app = MyPassDemo()
    app.mainloop()
