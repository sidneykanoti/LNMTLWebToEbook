"""Native desktop interface; network and export jobs run off the UI thread."""
import queue
import os
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.font import nametofont

from .export import export_book
from .library import Library
from .platform_support import APP_NAME, SUPPORT_URL, VERSION, asset_path, choose_library_directory, library_directory, open_folder, output_directory, user_data_directory
from .cleanup import clear_planned_data, plan_cleanup, remove_app_data_folder
from .source import Client, Stopped


class App:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title(f"{APP_NAME} {VERSION}")
        self.app_icon = tk.PhotoImage(file=str(asset_path("app-256.png")))
        self.window.iconphoto(True, self.app_icon)
        self.window.geometry("1060x760")
        self.window.minsize(840, 650)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.items = {}
        self.catalogue = []
        self.search = tk.StringVar()
        self.url = tk.StringVar()
        self.status = tk.StringVar(value="Add a novel link, or load LNMTL's catalogue to get started.")
        self.formats = {"epub": tk.BooleanVar(value=True), "pdf": tk.BooleanVar(value=False), "html": tk.BooleanVar(value=False)}
        self.sample = tk.BooleanVar(value=True)
        ui_font = nametofont("TkDefaultFont").actual("family")
        self.window.option_add("*Font", (ui_font, 10))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f3ee")
        style.configure("TLabel", background="#f4f3ee", foreground="#203c39", font=(ui_font, 10))
        style.configure("TButton", font=(ui_font, 10), padding=(12, 8))
        style.configure("Treeview", rowheight=31, font=(ui_font, 10))
        style.configure("Treeview.Heading", font=(ui_font, 10, "bold"))
        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill="both", expand=True)
        header = ttk.Frame(frame)
        header.pack(fill="x")
        self.header_logo = tk.PhotoImage(file=str(asset_path("app-64.png")))
        ttk.Label(header, image=self.header_logo).pack(side="left", padx=(0, 12))
        titles = ttk.Frame(header)
        titles.pack(side="left", fill="x", expand=True)
        ttk.Label(titles, text=APP_NAME, font=("Georgia", 25)).pack(anchor="w")
        self.subtitle = ttk.Label(titles, text="Backup and archive your novels, Almost similar style to website and  Read Offline", wraplength=780)
        self.subtitle.pack(anchor="w", pady=(5, 0))
        header.bind("<Configure>", lambda event: self.subtitle.configure(wraplength=max(250, event.width - 90)))
        support = ttk.Frame(frame)
        support.pack(fill="x", pady=(12, 8))
        support.columnconfigure(0, weight=1)
        self.support_text = ttk.Label(support, text="Free to use. Feel free to donate if you've found this software useful", wraplength=570)
        self.support_text.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.support_button = ttk.Button(support, text="Donate", command=self.open_support)
        self.support_button.grid(row=0, column=1, sticky="e")
        support.bind("<Configure>", lambda event: self.support_text.configure(wraplength=max(250, event.width - self.support_button.winfo_reqwidth() - 24)))
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        bar.columnconfigure(0, weight=1)
        self.url_label = ttk.Label(bar, text="Novel URL or short name, e.g. against-the-gods", font=(ui_font, 9))
        self.url_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.url_entry = ttk.Entry(bar, textvariable=self.url)
        self.url_entry.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.index_button = ttk.Button(bar, text="Add / refresh novel", command=self.add_novel)
        self.index_button.grid(row=1, column=1, sticky="ns")
        self.catalogue_button = ttk.Button(bar, text="Load catalogue", command=self.load_catalogue)
        self.catalogue_button.grid(row=1, column=2, sticky="ns", padx=(8, 0))
        search_bar = ttk.Frame(frame)
        search_bar.pack(fill="x", pady=(12, 8))
        ttk.Label(search_bar, text="Find a novel  ").pack(side="left")
        ttk.Entry(search_bar, textvariable=self.search).pack(side="left", fill="x", expand=True)
        self.search.trace_add("write", lambda *_: self.refresh())
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=("title", "saved", "state"), show="headings", selectmode="extended", height=3)
        for col, title, width in (("title", "Novel", 550), ("saved", "Saved / indexed", 125), ("state", "Status", 160)):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, minwidth=90)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<<TreeviewSelect>>", self.select_novel)
        options = ttk.Frame(frame)
        options.pack(fill="x", pady=12)
        ttk.Checkbutton(options, text="Sample first: download 3 new chapters per selected novel", variable=self.sample).pack(side="left")
        for fmt, label in (("epub", "EPUB"), ("pdf", "PDF"), ("html", "HTML")):
            ttk.Checkbutton(options, text=label, variable=self.formats[fmt]).pack(side="right", padx=5)
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        self.download_button = ttk.Button(actions, text="Download / resume selected", command=self.download)
        self.download_button.pack(side="left")
        self.export_button = ttk.Button(actions, text="Export selected", command=self.export)
        self.export_button.pack(side="left", padx=8)
        self.pause_button = ttk.Button(actions, text="Pause downloads", command=self.stop.set, state="disabled")
        self.pause_button.pack(side="left")
        library_actions = ttk.Frame(frame)
        library_actions.pack(fill="x", pady=(8, 0))
        self.books_button = ttk.Button(library_actions, text="Open books folder", command=self.open_output)
        self.books_button.pack(side="right")
        self.location_button = ttk.Button(library_actions, text="Choose library folder", command=self.choose_library)
        self.location_button.pack(side="right", padx=8)
        self.clear_button = ttk.Button(library_actions, text="Clear app data…", command=self.clear_data)
        self.clear_button.pack(side="right")
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(14, 6))
        ttk.Label(frame, textvariable=self.status, wraplength=950).pack(anchor="w")
        self.log = tk.Text(frame, height=3, font=nametofont("TkFixedFont"), bg="#fffefa", relief="flat", state="disabled")
        self.log.pack(fill="x", pady=(10, 0))
        self.controls = [self.index_button, self.catalogue_button, self.download_button, self.export_button, self.location_button, self.clear_button]
        self.refresh()
        self.window.after(150, self.poll)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def refresh(self):
        selected_urls = {self.items[i]["url"] for i in self.table.selection() if i in self.items}
        lib = Library()
        try:
            self.catalogue = lib.catalogue()
            indexed = {n["url"]: n for n in lib.novels()}
            all_items = {n["url"]: n for n in self.catalogue}
            all_items.update(indexed)
            self.table.delete(*self.table.get_children())
            self.items = {}
            for i, n in enumerate(sorted(all_items.values(), key=lambda n: n["title"].lower())):
                if self.search.get().lower() not in n["title"].lower():
                    continue
                iid = str(i)
                s = lib.summary(n["slug"]) if n.get("slug") else None
                state = ("Retry needed" if s["failed"] else "Downloaded" if s["saved"] == s["total"] and s["total"] else "Ready to download") if s else "Not indexed"
                self.table.insert("", "end", iid=iid, values=(n["title"], f'{s["saved"]:,} / {s["total"]:,}' if s else "—", state))
                self.items[iid] = n
                if n["url"] in selected_urls:
                    self.table.selection_add(iid)
        finally:
            lib.close()

    def select_novel(self, _):
        selection = self.table.selection()
        if len(selection) == 1 and selection[0] in self.items:
            self.url.set(self.items[selection[0]]["url"])

    def run_job(self, job):
        if self.busy:
            return
        self.busy = True
        self.stop.clear()
        for b in self.controls:
            b.configure(state="disabled")
        self.pause_button.configure(state="normal")
        self.progress.start(12)

        def work():
            lib = None
            try:
                lib = Library()
                job(lib, Client(stop=self.stop), lambda msg: self.events.put(("status", msg)))
            except Stopped as exc:
                self.events.put(("status", str(exc)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                if lib:
                    lib.close()
                self.events.put(("done", ""))
        threading.Thread(target=work, daemon=True).start()

    def add_novel(self):
        value = self.url.get()
        if not value.strip():
            messagebox.showinfo("Add a novel", "Paste an LNMTL novel URL or enter its short name.")
            return
        def job(lib, client, report):
            report("Collecting the available chapter index…")
            n = client.discover(value, report)
            lib.save_index(n)
            report(f'Indexed {len(n["chapters"]):,} available chapters for {n["title"]}. Select it to download.')
        self.run_job(job)

    def load_catalogue(self):
        def job(lib, client, report):
            lib.catalogue(client.catalogue(report))
            report("Catalogue saved. Select one or more novels to download.")
        self.run_job(job)

    def selected(self):
        selected = [dict(self.items[i]) for i in self.table.selection() if i in self.items]
        if not selected:
            messagebox.showinfo("Choose a novel", "Select one or more novels in the library. Use Ctrl or Shift to select several.")
        return selected

    def download(self):
        selected = self.selected()
        if not selected:
            return
        limit = 3 if self.sample.get() else None
        def job(lib, client, report):
            for n in selected:
                client.check()
                if not n.get("slug"):
                    n = client.discover(n["url"], report)
                    lib.save_index(n)
                s = lib.download(n["slug"], client, report, limit)
                report(f'{n["title"]}: {s["saved"]:,}/{s["total"]:,} saved, {s["failed"]} failed. Use Export selected to create books.')
        self.run_job(job)

    def export(self):
        selected = self.selected()
        formats = [f for f, v in self.formats.items() if v.get()]
        if not selected:
            return
        if not formats:
            messagebox.showinfo("Choose a format", "Select EPUB, PDF, or HTML.")
            return
        def job(lib, client, report):
            for n in selected:
                client.check()
                if not n.get("slug"):
                    raise ValueError("Download the selected novel first.")
                report(f'Creating books for {n["title"]}…')
                paths = export_book(lib, n["slug"], formats)
                report("Created: " + ", ".join(str(p.name) for p in paths))
        self.run_job(job)

    def poll(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "done":
                    self.busy = False
                    self.progress.stop()
                    for b in self.controls:
                        b.configure(state="normal")
                    self.pause_button.configure(state="disabled")
                    self.refresh()
                else:
                    self.status.set(text)
                    self.log.configure(state="normal")
                    self.log.insert("end", text + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                    if kind == "error":
                        messagebox.showerror("Job stopped", text)
        except queue.Empty:
            pass
        self.window.after(150, self.poll)

    def open_output(self):
        try:
            open_folder(output_directory())
        except OSError as exc:
            messagebox.showerror("Cannot open folder", str(exc))

    def open_support(self):
        try:
            if webbrowser.open_new_tab(SUPPORT_URL):
                return
        except (OSError, webbrowser.Error):
            pass
        messagebox.showinfo("Support this project", f"Open this PayPal link in your browser:\n\n{SUPPORT_URL}\n\nContributions are optional. Thank you for supporting development.")

    def clear_data(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self.window)
        dialog.title("Clear app data")
        dialog.transient(self.window)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Clear the current library", font=("Georgia", 18)).pack(anchor="w")
        ttk.Label(body, text="Removes the saved catalogue, chapter index, downloaded chapter pages, and download progress.", wraplength=510).pack(anchor="w", pady=(10, 8))
        ttk.Label(body, text=f"Library: {library_directory()}", wraplength=510).pack(anchor="w", pady=(0, 10))
        books = tk.BooleanVar(value=False)
        preferences = tk.BooleanVar(value=False)
        remove_folder = tk.BooleanVar(value=False)
        books_check = ttk.Checkbutton(body, text="Also delete exported EPUB, PDF, and HTML books", variable=books)
        books_check.pack(anchor="w")
        preferences_check = ttk.Checkbutton(body, text="Also reset saved preferences and clear the startup log", variable=preferences)
        preferences_check.pack(anchor="w", pady=(4, 10))

        def folder_option():
            for control in (books_check, preferences_check):
                control.configure(state="disabled" if remove_folder.get() else "normal")

        ttk.Checkbutton(body, text="Remove the app data folder completely and exit", variable=remove_folder, command=folder_option).pack(anchor="w")
        ttk.Label(body, text=f"Deletes everything inside {user_data_directory()}, including books and preferences. Custom libraries outside this folder are kept.", wraplength=510).pack(anchor="w", pady=(4, 10))
        ttk.Label(body, text="This cannot be undone. Exported books are kept unless selected above. The application and unrelated files are kept.", wraplength=510).pack(anchor="w", pady=(0, 12))
        actions = ttk.Frame(body)
        actions.pack(fill="x")
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right")

        def perform():
            try:
                if remove_folder.get():
                    if not messagebox.askyesno("Remove app data folder and exit", f"Permanently delete this folder and EVERYTHING inside it, then close the app?\n\n{user_data_directory()}\n\nThis includes downloaded chapters, exported books, and preferences stored here. External library folders are kept.\n\nThe executable remains; you can delete it afterward. Opening the app again creates a fresh data folder.", parent=dialog, default="no"):
                        return
                    remove_app_data_folder()
                    self.window.destroy()
                    return
                plan = plan_cleanup(books.get(), preferences.get())
                if not messagebox.askyesno("Confirm data removal", f"Permanently remove {len(plan.files)} app files ({plan.size / 1024 / 1024:.1f} MB)?\n\nLibrary: {plan.library}\n\nExported books: {'delete app-generated books' if books.get() else 'keep'}", parent=dialog, default="no"):
                    return
                count = clear_planned_data(plan)
                os.environ["LNMTL_LIBRARY_DIR"] = str(plan.library)
                self.url.set("")
                self.search.set("")
                self.log.configure(state="normal")
                self.log.delete("1.0", "end")
                self.log.configure(state="disabled")
                self.refresh()
                self.status.set(f"Cleared {count} app files. The library is empty and ready to use.")
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Could not clear all data", f"Some files may be in use by another app window. Close other copies and try again.\n\n{exc}", parent=dialog)

        ttk.Button(actions, text="Clear data", command=perform).pack(side="right", padx=8)
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        dialog.update_idletasks()
        x = max(0, self.window.winfo_rootx() + (self.window.winfo_width() - dialog.winfo_reqwidth()) // 2)
        y = max(0, self.window.winfo_rooty() + (self.window.winfo_height() - dialog.winfo_reqheight()) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.grab_set()

    def choose_library(self):
        chosen = filedialog.askdirectory(title="Choose the library folder (contains archive.sqlite3)", initialdir=str(library_directory().parent))
        if not chosen:
            return
        try:
            # Verify the directory is usable before changing the saved preference.
            lib = Library(chosen)
            lib.novels()
            lib.close()
            choose_library_directory(chosen)
            self.url.set("")
            self.search.set("")
            self.refresh()
            self.status.set(f"Library: {chosen}")
        except Exception as exc:
            messagebox.showerror("Cannot use this library", str(exc))

    def close(self):
        if self.busy:
            self.stop.set()
            self.status.set("Stopping safely. Close the window again once the current job finishes.")
            return
        self.window.destroy()

    def mainloop(self):
        self.window.mainloop()
