"""Desktop presentation: focused library, downloads, and settings views."""
import base64
import io
import json
import tkinter as tk
from tkinter import ttk
from tkinter.font import nametofont

from PIL import Image, ImageDraw, ImageTk

from .library import Library
from .platform_support import APP_NAME, VERSION, asset_path, library_directory

BG = "#f3f6f4"
INK = "#18352f"
MUTED = "#697c74"
ACCENT = "#247456"
LINE = "#e2e9e4"
WHITE = "#ffffff"


class DesktopUI:
    def _load_preferences(self):
        lib = Library()
        try:
            row = lib.db.execute("SELECT value FROM settings WHERE name='ui_preferences'").fetchone()
            try:
                values = json.loads(row[0]) if row else {}
                if not isinstance(values, dict):
                    values = {}
            except (ValueError, TypeError):
                values = {}
            for key, variable in (("sample", self.sample), ("auto_export", self.auto_export)):
                if isinstance(values.get(key), bool):
                    variable.set(values[key])
            for fmt, variable in self.formats.items():
                if isinstance(values.get(fmt), bool):
                    variable.set(values[fmt])
            row = lib.db.execute("SELECT value FROM settings WHERE name='auto_resume_queue'").fetchone()
            self.auto_resume.set(bool(row and row[0] == "true"))
        finally:
            lib.close()

    def _save_preferences(self):
        values = {"sample": self.sample.get(), "auto_export": self.auto_export.get(),
                  **{fmt: value.get() for fmt, value in self.formats.items()}}
        lib = Library()
        try:
            with lib.db:
                lib.db.execute("INSERT OR REPLACE INTO settings VALUES ('ui_preferences',?)", (json.dumps(values),))
                lib.db.execute("INSERT OR REPLACE INTO settings VALUES ('auto_resume_queue',?)", ("true" if self.auto_resume.get() else "false",))
        finally:
            lib.close()
        self.update_actions()

    def _build_ui(self):
        self.font = nametofont("TkDefaultFont").actual("family")
        self.window.configure(bg=BG)
        self.style = style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=WHITE)
        style.configure("TLabel", background=BG, foreground=INK, font=(self.font, 10))
        style.configure("Card.TLabel", background=WHITE)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("CardMuted.TLabel", background=WHITE, foreground=MUTED)
        style.configure("Title.TLabel", font=(self.font, 25, "bold"))
        style.configure("Section.TLabel", background=WHITE, font=(self.font, 12, "bold"))
        style.configure("TButton", background=WHITE, foreground=INK, bordercolor=LINE,
                        lightcolor=WHITE, darkcolor=WHITE, relief="flat", padding=(14, 10), font=(self.font, 10))
        style.map("TButton", background=[("active", "#edf3ef"), ("disabled", "#f2f4f2")],
                  foreground=[("disabled", "#a2ada6")], bordercolor=[("focus", ACCENT)])
        style.configure("Primary.TButton", background=ACCENT, foreground=WHITE, bordercolor=ACCENT)
        style.map("Primary.TButton", background=[("disabled", "#dce8e0"), ("active", "#1a6046")],
                  foreground=[("disabled", "#7c9686"), ("!disabled", WHITE)], bordercolor=[("focus", "#154f3c")])
        style.configure("Quiet.TButton", background=BG, bordercolor=BG, foreground=MUTED)
        style.configure("Danger.TButton", foreground="#a03e3e", bordercolor="#ead9d9")
        style.configure("TEntry", padding=(10, 10), bordercolor=LINE, lightcolor=WHITE, fieldbackground=WHITE, font=(self.font, 10))
        style.map("TEntry", bordercolor=[("focus", ACCENT)])
        style.configure("TCheckbutton", background=WHITE, foreground=INK, padding=(0, 6), font=(self.font, 10))
        style.map("TCheckbutton", background=[("active", WHITE)])
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=INK,
                        borderwidth=0, relief="flat", rowheight=78, font=(self.font, 10), bordercolor=WHITE, lightcolor=WHITE, darkcolor=WHITE)
        style.configure("Treeview.Heading", background="#edf2ee", foreground=MUTED,
                        relief="flat", padding=(10, 12), font=(self.font, 9, "bold"))
        style.map("Treeview", background=[("selected", "#e1efe5")], foreground=[("selected", INK)])
        style.configure("Queue.Treeview", rowheight=46)
        style.configure("Horizontal.TProgressbar", troughcolor="#e6eee8", background=ACCENT,
                        borderwidth=0, bordercolor="#e6eee8", lightcolor=ACCENT, darkcolor=ACCENT, thickness=8)
        style.configure("Vertical.TScrollbar", background="#d7e2d9", troughcolor=WHITE,
                        borderwidth=0, arrowsize=12, bordercolor=WHITE, lightcolor=WHITE, darkcolor=WHITE)

        self.window.columnconfigure(1, weight=1)
        self.window.rowconfigure(0, weight=1)
        sidebar = tk.Frame(self.window, bg="#163d33", width=170)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        self.header_logo = tk.PhotoImage(file=str(asset_path("app-48.png")))
        tk.Label(sidebar, image=self.header_logo, bg="#163d33").pack(anchor="w", padx=22, pady=(28, 10))
        tk.Label(sidebar, text="LNMTL", bg="#163d33", fg=WHITE, font=(self.font, 20, "bold")).pack(anchor="w", padx=22)
        tk.Label(sidebar, text="WEB TO EBOOK", bg="#163d33", fg="#a3c1af", font=(self.font, 8, "bold")).pack(anchor="w", padx=23, pady=(3, 35))
        self.nav_buttons = {}
        for name in ("Library", "Downloads", "Settings"):
            button = tk.Button(sidebar, text=name, anchor="w", bg="#163d33", fg="#c8d9cd",
                               activebackground="#2b5747", activeforeground=WHITE, relief="flat", borderwidth=0,
                               font=(self.font, 11), padx=18, pady=13, cursor="hand2", takefocus=True,
                               command=lambda page=name: self.show_page(page))
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[name] = button
        tk.Label(sidebar, text=f"Version {VERSION}\nSaved on your computer", justify="left", bg="#163d33",
                 fg="#a3c1af", font=(self.font, 8), anchor="w").pack(side="bottom", fill="x", padx=22, pady=24)

        container = ttk.Frame(self.window, padding=(28, 26, 28, 12))
        container.grid(row=0, column=1, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        self.pages = {}
        for name in ("Library", "Downloads", "Settings"):
            page = ttk.Frame(container)
            page.grid(row=0, column=0, sticky="nsew")
            page.columnconfigure(0, weight=1)
            self.pages[name] = page
        self._build_library(self.pages["Library"])
        self._build_downloads(self.pages["Downloads"])
        self._build_settings(self.pages["Settings"])
        footer = ttk.Frame(container)
        footer.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        self.footer_status = tk.StringVar(value="Your library stays on this computer.")
        ttk.Label(footer, textvariable=self.footer_status, style="Muted.TLabel", wraplength=700).grid(row=0, column=0, sticky="w")
        self.controls = [self.index_button, self.catalogue_button, self.download_button, self.export_button,
                         self.location_button, self.clear_button, self.archive_button, self.resume_button,
                         self.refresh_button]
        self.show_page("Library")

    def _heading(self, page, title, subtitle):
        heading = ttk.Frame(page)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 22))
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(heading, text=subtitle, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))
        return heading

    def _card(self, parent, **grid):
        border = tk.Frame(parent, bg=LINE)
        border.grid(**grid)
        card = ttk.Frame(border, style="Card.TFrame", padding=20)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        return card

    def _build_library(self, page):
        page.rowconfigure(2, weight=1)
        heading = self._heading(page, "Your library", "Find a story. Save it once. Read it anywhere.")
        self.index_button = ttk.Button(heading, text="Add novel", style="Primary.TButton", command=self.open_add_dialog)
        self.index_button.grid(row=0, column=2, rowspan=2, sticky="e")
        self.catalogue_button = ttk.Button(heading, text="Load catalogue", command=self.load_catalogue)
        self.catalogue_button.grid(row=0, column=1, rowspan=2, padx=(12, 10))
        search = ttk.Frame(page)
        search.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Search", style="Muted.TLabel").grid(row=0, column=0, padx=(0, 12))
        self.search_entry = ttk.Entry(search, textvariable=self.search)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.library_count = tk.StringVar(value="0 novels")
        ttk.Label(search, textvariable=self.library_count, style="Muted.TLabel").grid(row=0, column=2, padx=(16, 0))
        self.search.trace_add("write", lambda *_: self.refresh())

        content = ttk.Frame(page)
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, minsize=242)
        content.rowconfigure(0, weight=1)
        table_frame = tk.Frame(content, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=("saved", "state"), show="tree headings", selectmode="extended", height=4)
        self.table.heading("#0", text="NOVEL / AUTHOR", anchor="w")
        self.table.column("#0", width=280, minwidth=160)
        for col, title, width in (("saved", "CHAPTERS", 96), ("state", "STATUS", 115)):
            self.table.heading(col, text=title, anchor="w")
            self.table.column(col, width=width, minwidth=80, stretch=False)
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_frame, command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<<TreeviewSelect>>", self.select_novel)
        self.table.bind("<Double-1>", lambda _: self.render_selection())
        self.empty_label = tk.Label(table_frame, text="A home for your next read\n\nAdd a novel link, or load the catalogue to browse.",
                                    bg=WHITE, fg=MUTED, font=(self.font, 11), justify="center", wraplength=320)
        detail = self._card(content, row=0, column=1, sticky="nsew")
        detail.configure(width=242)
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(5, weight=1)
        self.detail_poster = ttk.Label(detail, style="Card.TLabel", anchor="center")
        self.detail_poster.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self.detail_title = ttk.Label(detail, text="Make it your library", style="Section.TLabel", wraplength=202, justify="left")
        self.detail_title.grid(row=1, column=0, sticky="ew")
        self.detail_author = ttk.Label(detail, text="Select a novel to see its details.", style="CardMuted.TLabel", wraplength=202)
        self.detail_author.grid(row=2, column=0, sticky="ew", pady=(8, 16))
        self.detail_chapters = ttk.Label(detail, text="", style="CardMuted.TLabel", wraplength=202)
        self.detail_chapters.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        ttk.Label(detail, text="SYNOPSIS", style="CardMuted.TLabel", font=(self.font, 8, "bold")).grid(row=4, column=0, sticky="w", pady=(0, 8))
        synopsis_frame = ttk.Frame(detail, style="Card.TFrame")
        synopsis_frame.grid(row=5, column=0, sticky="nsew")
        synopsis_frame.columnconfigure(0, weight=1)
        synopsis_frame.rowconfigure(0, weight=1)
        self.detail_synopsis = tk.Text(synopsis_frame, width=22, height=5, wrap="word", bg=WHITE, fg=MUTED,
                                       borderwidth=0, highlightthickness=0, font=(self.font, 10), padx=0, pady=0, state="disabled", cursor="arrow")
        self.detail_synopsis.grid(row=0, column=0, sticky="nsew")
        synopsis_scroll = ttk.Scrollbar(synopsis_frame, command=self.detail_synopsis.yview)
        synopsis_scroll.grid(row=0, column=1, sticky="ns")
        self.detail_synopsis.configure(yscrollcommand=synopsis_scroll.set)
        self.refresh_button = ttk.Button(detail, text="Refresh details", command=self.refresh_selected)
        self.refresh_button.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        actions = ttk.Frame(page)
        actions.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(0, weight=1)
        self.selection_text = tk.StringVar(value="Select a novel to get started")
        ttk.Label(actions, textvariable=self.selection_text, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.export_button = ttk.Button(actions, text="Export", command=self.export)
        self.export_button.grid(row=0, column=1, padx=(8, 10))
        self.download_button = ttk.Button(actions, text="Download", style="Primary.TButton", command=self.download)
        self.download_button.grid(row=0, column=2)
        self.row_images = []
        self.poster_cache = {}

    def _build_downloads(self, page):
        page.rowconfigure(3, weight=1)
        heading = self._heading(page, "Downloads", "Pick up where you left off. Every saved chapter stays saved.")
        self.archive_button = ttk.Button(heading, text="Download entire catalogue", command=self.archive_all)
        self.archive_button.grid(row=2, column=0, sticky="w", pady=(16, 0))
        self.resume_button = ttk.Button(heading, text="Resume queue", style="Primary.TButton", command=self.resume_queue)
        self.resume_button.grid(row=2, column=1, sticky="e", padx=(12, 0), pady=(16, 0))
        current = self._card(page, row=1, column=0, sticky="ew", pady=(0, 20))
        current.columnconfigure(0, weight=1)
        ttk.Label(current, text="CURRENT NOVEL", style="CardMuted.TLabel", font=(self.font, 8, "bold")).grid(row=0, column=0, sticky="w")
        self.current_title = tk.StringVar(value="Ready when you are")
        self.current_label = ttk.Label(current, textvariable=self.current_title, style="Section.TLabel", wraplength=570)
        self.current_label.grid(row=1, column=0, sticky="ew", pady=(10, 6))
        self.pause_button = ttk.Button(current, text="Pause", command=self.pause_downloads)
        self.pause_button.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(18, 0))
        self.pause_button.grid_remove()
        self.chapter_status = tk.StringVar(value="Start a download from your library or resume your saved queue.")
        ttk.Label(current, textvariable=self.chapter_status, style="CardMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 12))
        self.percent = tk.StringVar(value="")
        ttk.Label(current, textvariable=self.percent, style="Section.TLabel").grid(row=2, column=1, sticky="e")
        self.progress = ttk.Progressbar(current, mode="determinate", maximum=100, value=0)
        self.progress.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.current_status_label = ttk.Label(current, textvariable=self.status, style="CardMuted.TLabel", wraplength=650)
        self.current_status_label.grid(row=4, column=0, columnspan=2, sticky="ew")
        current.bind("<Configure>", lambda event: (self.current_label.configure(wraplength=max(240, event.width - 150)),
                                                     self.current_status_label.configure(wraplength=max(240, event.width - 40))))
        summary = ttk.Frame(page)
        summary.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        summary.columnconfigure(0, weight=1)
        ttk.Label(summary, text="YOUR QUEUE", font=(self.font, 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.queue_status, style="Muted.TLabel").grid(row=0, column=1, sticky="e")
        table_frame = ttk.Frame(page)
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.queue_table = ttk.Treeview(table_frame, columns=("title", "state"), show="headings", height=3, style="Queue.Treeview", selectmode="browse")
        for col, title, width in (("title", "NOVEL", 450), ("state", "STATUS", 150)):
            self.queue_table.heading(col, text=title, anchor="w")
            self.queue_table.column(col, width=width, minwidth=120, stretch=col == "title")
        self.queue_table.grid(row=0, column=0, sticky="nsew")
        self.queue_table.tag_configure("running", foreground=ACCENT)
        self.queue_table.tag_configure("failed", foreground="#a03e3e")
        scrollbar = ttk.Scrollbar(table_frame, command=self.queue_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.queue_table.configure(yscrollcommand=scrollbar.set)
        self.queue_items = {}
        self.queue_error = tk.StringVar(value="Select a queued novel to see its saved status.")
        self.queue_table.bind("<<TreeviewSelect>>", self.show_queue_error)
        ttk.Label(page, textvariable=self.queue_error, style="Muted.TLabel", wraplength=720).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.activity_button = ttk.Button(page, text="Show activity", style="Quiet.TButton", command=self.toggle_activity)
        self.activity_button.grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.activity_frame = ttk.Frame(page)
        self.activity_frame.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        self.activity_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(self.activity_frame, height=4, wrap="word", bg=WHITE, fg=MUTED, relief="flat",
                           borderwidth=0, padx=12, pady=10, font=(self.font, 9), state="disabled")
        self.log.grid(row=0, column=0, sticky="ew")
        self.activity_frame.grid_remove()

    def _build_settings(self, page):
        self._heading(page, "Settings", "A few preferences. A library that stays yours.")
        columns = ttk.Frame(page)
        columns.grid(row=1, column=0, sticky="nsew")
        columns.columnconfigure(0, weight=1, uniform="settings")
        columns.columnconfigure(1, weight=1, uniform="settings")
        exports = self._card(columns, row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 14))
        ttk.Label(exports, text="Downloads & exports", style="Section.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Checkbutton(exports, text="Sample mode: 3 new chapters per novel", variable=self.sample, command=self._save_preferences).pack(anchor="w")
        ttk.Checkbutton(exports, text="Export each completed novel", variable=self.auto_export, command=self._save_preferences).pack(anchor="w")
        ttk.Checkbutton(exports, text="Resume queue when the app opens", variable=self.auto_resume, command=self._save_preferences).pack(anchor="w")
        ttk.Label(exports, text="Export formats", style="CardMuted.TLabel").pack(anchor="w", pady=(18, 6))
        formats = ttk.Frame(exports, style="Card.TFrame")
        formats.pack(fill="x")
        for fmt, label in (("epub", "EPUB"), ("pdf", "PDF"), ("html", "HTML")):
            ttk.Checkbutton(formats, text=label, variable=self.formats[fmt], command=self._save_preferences).pack(side="left", padx=(0, 16))
        ttk.Label(exports, text="Whole-catalogue downloads always save full novels.\nQueued exports keep the formats chosen when added.", style="CardMuted.TLabel", wraplength=310).pack(anchor="w", pady=(14, 0))
        storage = self._card(columns, row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 14))
        ttk.Label(storage, text="Library & storage", style="Section.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(storage, text="Your current library", style="CardMuted.TLabel").pack(anchor="w")
        self.library_path = ttk.Label(storage, text=str(library_directory()), style="Card.TLabel", wraplength=290)
        self.library_path.pack(anchor="w", pady=(6, 16))
        self.location_button = ttk.Button(storage, text="Choose library folder", command=self.choose_library)
        self.location_button.pack(fill="x", pady=(0, 8))
        self.books_button = ttk.Button(storage, text="Open books folder", command=self.open_output)
        self.books_button.pack(fill="x")
        about = self._card(columns, row=1, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(about, text="Made for offline reading", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(about, text=f"{APP_NAME} {VERSION}\nFree to use. If it helps, you can support the project.", style="CardMuted.TLabel", wraplength=310).pack(anchor="w")
        self.support_button = ttk.Button(about, text="Support the project", command=self.open_support)
        self.support_button.pack(anchor="w", pady=(14, 0))
        cleanup = self._card(columns, row=1, column=1, sticky="nsew", padx=(10, 0))
        ttk.Label(cleanup, text="Manage saved data", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(cleanup, text="Clear downloads or reset your library.\nYou choose whether exported books are removed.", style="CardMuted.TLabel", wraplength=290).pack(anchor="w")
        self.clear_button = ttk.Button(cleanup, text="Clear app data…", style="Danger.TButton", command=self.clear_data)
        self.clear_button.pack(anchor="w", pady=(14, 0))

    def show_page(self, name):
        self.active_page = name
        for page, frame in self.pages.items():
            if page == name:
                frame.grid()
            else:
                frame.grid_remove()
        self.pages[name].tkraise()
        for page, button in self.nav_buttons.items():
            button.configure(bg="#2b5747" if page == name else "#163d33", fg=WHITE if page == name else "#c8d9cd")
        if name == "Settings":
            self.library_path.configure(text=str(library_directory()))

    def poster_photo(self, novel, size=(42, 60)):
        poster = novel.get("poster") or {}
        data = poster.get("data", "")
        key = (novel.get("url", ""), hash(data), size)
        if key in self.poster_cache:
            return self.poster_cache[key]
        image = None
        if data:
            try:
                raw = base64.b64decode(data, validate=True)
                with Image.open(io.BytesIO(raw)) as opened:
                    if opened.width * opened.height > 20_000_000:
                        raise ValueError("Poster too large for a thumbnail")
                    image = opened.convert("RGB")
                image.thumbnail(size, Image.Resampling.LANCZOS)
            except (ValueError, OSError, Image.DecompressionBombError):
                image = None
        if image is None:
            image = Image.new("RGB", size, "#dce7df")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, max(2, size[0] // 10), size[1]), fill="#adc5b6")
            for fraction in (.30, .42, .54):
                y = int(size[1] * fraction)
                draw.line((size[0] * .27, y, size[0] * .78, y), fill="#8cae9a", width=max(1, size[0] // 30))
        photo = ImageTk.PhotoImage(image, master=self.window)
        if len(self.poster_cache) >= 256:
            self.poster_cache.pop(next(iter(self.poster_cache)))
        self.poster_cache[key] = photo
        return photo

    def render_selection(self):
        selection = [self.items[i] for i in self.table.selection() if i in self.items]
        self.selection_text.set(f"{len(selection)} novel{'s' if len(selection) != 1 else ''} selected" if selection else "Select a novel to get started")
        novel = selection[0] if len(selection) == 1 else {}
        self.detail_photo = self.poster_photo(novel, (106, 148))
        self.detail_poster.configure(image=self.detail_photo)
        self.detail_title.configure(text=novel.get("title", "Your next great read" if not selection else f"{len(selection)} novels selected"))
        self.detail_author.configure(text=novel.get("author", "Add or refresh a novel to collect its author and synopsis." if len(selection) == 1 else "Choose one novel to see its details."))
        summary = novel.get("_summary")
        self.detail_chapters.configure(text=f"{summary['saved']:,} of {summary['total']:,} chapters saved" if summary else "")
        text = "\n\n".join(novel.get("synopsis", [])) or "The synopsis will appear here when you add or refresh this novel."
        self.detail_synopsis.configure(state="normal")
        self.detail_synopsis.delete("1.0", "end")
        self.detail_synopsis.insert("1.0", text)
        self.detail_synopsis.configure(state="disabled")
        self.update_actions()

    def update_actions(self):
        if not hasattr(self, "download_button"):
            return
        selected = [self.items[i] for i in self.table.selection() if i in self.items]
        self.download_button.configure(text="Download sample" if self.sample.get() else "Download")
        self.download_button.configure(state="normal" if selected and not self.busy else "disabled")
        self.export_button.configure(state="normal" if selected and not self.busy and all(n.get("_summary", {}).get("saved", 0) for n in selected) else "disabled")
        self.refresh_button.configure(state="normal" if len(selected) == 1 and not self.busy else "disabled")
        has_pending = any(row["state"] != "completed" for row in self.queue_items.values())
        self.resume_button.configure(state="normal" if has_pending and not self.busy else "disabled")

    def toggle_activity(self):
        if self.activity_frame.winfo_manager():
            self.activity_frame.grid_remove()
            self.activity_button.configure(text="Show activity")
        else:
            self.activity_frame.grid()
            self.activity_button.configure(text="Hide activity")

    def show_queue_error(self, _=None):
        selected = self.queue_table.selection()
        item = self.queue_items.get(selected[0]) if selected else None
        self.queue_error.set(item.get("error") or "Saved in your queue. Resume continues unfinished chapters." if item else "Select a queued novel to see its saved status.")

    def open_add_dialog(self):
        if self.busy:
            return
        self.url.set("")
        dialog = tk.Toplevel(self.window)
        dialog.title("Add a novel")
        dialog.transient(self.window)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Add a story to your library", font=(self.font, 15, "bold")).pack(anchor="w")
        self.url_label = ttk.Label(body, text="LNMTL novel link or short name")
        self.url_label.pack(anchor="w", pady=(18, 8))
        self.url_entry = ttk.Entry(body, textvariable=self.url, width=48)
        self.url_entry.pack(fill="x")
        ttk.Label(body, text="For example: against-the-gods", style="Muted.TLabel").pack(anchor="w", pady=(8, 18))
        actions = ttk.Frame(body)
        actions.pack(fill="x")
        def submit():
            if self.url.get().strip():
                dialog.destroy()
                self.add_novel()
        ttk.Button(actions, text="Add novel", style="Primary.TButton", command=submit).pack(side="right")
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right", padx=10)
        dialog.bind("<Return>", lambda _: submit())
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        self.url_entry.focus_set()
        dialog.grab_set()

    def refresh_selected(self):
        selection = self.table.selection()
        if len(selection) == 1 and selection[0] in self.items:
            self.url.set(self.items[selection[0]]["url"])
            self.add_novel()

    def pause_downloads(self):
        self.stop.set()
        self.pause_button.configure(text="Pausing…", state="disabled")
        self.status.set("Finishing the current request. Your saved chapters are safe.")
