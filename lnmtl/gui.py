"""Native desktop interface; network and export jobs run off the UI thread."""
import queue
import os
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .ui import DesktopUI
from .export import export_book
from .library import Library
from .download_queue import DownloadQueue
from .platform_support import APP_NAME, SUPPORT_URL, VERSION, asset_path, choose_library_directory, library_directory, open_folder, output_directory, user_data_directory
from .cleanup import clear_planned_data, plan_cleanup, remove_app_data_folder
from .source import Client, Stopped


class App(DesktopUI):

    def __init__(self):
        self.window = tk.Tk()
        self.window.title(f"{APP_NAME} {VERSION}")
        self.app_icon = tk.PhotoImage(file=str(asset_path("app-256.png")))
        self.window.iconphoto(True, self.app_icon)
        width = min(1280, max(1040, self.window.winfo_screenwidth() - 64))
        height = min(840, max(700, self.window.winfo_screenheight() - 100))
        self.window.geometry(f"{width}x{height}")
        self.window.minsize(1040, 700)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.items = {}
        self.catalogue = []
        self.current = {}
        self.search = tk.StringVar()
        self.url = tk.StringVar()
        self.status = tk.StringVar(value="Choose a novel from your library to begin.")
        self.formats = {"epub": tk.BooleanVar(value=True), "pdf": tk.BooleanVar(value=False), "html": tk.BooleanVar(value=False)}
        self.sample = tk.BooleanVar(value=True)
        self.auto_export = tk.BooleanVar(value=False)
        self.auto_resume = tk.BooleanVar(value=False)
        self.queue_status = tk.StringVar(value="Queue is empty")
        self._load_preferences()
        self._build_ui()
        self.refresh()
        lib = Library()
        try:
            row = lib.db.execute("SELECT value FROM settings WHERE name='auto_resume_queue'").fetchone()
            self.auto_resume.set(bool(row and row[0] == "true"))
            pending = lib.db.execute("SELECT 1 FROM download_queue WHERE state IN ('pending','running') LIMIT 1").fetchone()
        finally:
            lib.close()
        if self.auto_resume.get() and pending:
            self.resume_timer = self.window.after(500, self.resume_queue)
        self.poll_timer = self.window.after(150, self.poll)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def refresh(self):
        selected_urls = {self.items[i]["url"] for i in self.table.selection() if i in self.items}
        lib = Library()
        try:
            self.catalogue = lib.catalogue()
            preference = lib.db.execute("SELECT value FROM settings WHERE name='auto_resume_queue'").fetchone()
            self.auto_resume.set(bool(preference and preference[0] == "true"))
            self.show_queue_progress(DownloadQueue(lib).progress())
            indexed = {n["url"]: n for n in lib.novels()}
            queued = {n["url"]: n for n in DownloadQueue(lib).items()}
            all_items = {n["url"]: n for n in self.catalogue}
            all_items.update({url: {"url": url, "title": n["title"]} for url, n in queued.items()})
            all_items.update(indexed)
            self.table.delete(*self.table.get_children())
            self.items = {}
            self.row_images = []
            for i, n in enumerate(sorted(all_items.values(), key=lambda n: n["title"].lower())):
                if self.search.get().lower() not in (n["title"] + " " + n.get("author", "")).lower():
                    continue
                iid = str(i)
                s = lib.summary(n["slug"]) if n.get("slug") else None
                state = ("Retry needed" if s["failed"] else "Downloaded" if s["saved"] == s["total"] and s["total"] else "Ready to download") if s else "Not indexed"
                if n["url"] in queued:
                    state = {"pending": "Queued", "running": "In progress", "failed": "Queue needs attention", "completed": "Queue completed"}[queued[n["url"]]["state"]]
                state = {"Ready to download": "Ready", "Queue needs attention": "Needs attention", "Queue completed": "Completed"}.get(state, state)
                item = dict(n)
                if s:
                    item["_summary"] = s
                photo = self.poster_photo(item)
                self.row_images.append(photo)
                self.table.insert("", "end", iid=iid, text="  " + n["title"] + "\n  " + n.get("author", "Add novel to load author"), image=photo,
                                  values=(f'{s["saved"]:,} / {s["total"]:,}' if s else "—", state))
                self.items[iid] = item
                if n["url"] in selected_urls:
                    self.table.selection_add(iid)
            self.library_count.set(f"{len(self.items):,} novels")
            if self.items:
                self.empty_label.place_forget()
            else:
                self.empty_label.configure(text="No novels found\n\nTry another title or author." if self.search.get() else "A home for your next read\n\nAdd a novel link, or load the catalogue to browse.")
                self.empty_label.place(relx=.5, rely=.5, anchor="center")
            self.render_selection()
        finally:
            lib.close()

    def select_novel(self, _):
        selection = self.table.selection()
        if len(selection) == 1 and selection[0] in self.items:
            self.url.set(self.items[selection[0]]["url"])
        self.render_selection()

    def run_job(self, job, title="Preparing your download", return_page=None):
        if self.busy:
            return
        self.busy = True
        self.job_error = False
        self.job_return_page = return_page
        self.stop.clear()
        for b in self.controls:
            b.configure(state="disabled")
        self.pause_button.configure(text="Pause", state="normal")
        self.pause_button.grid()
        self.current = {}
        self.show_current_progress({"title": title, "saved": 0, "total": 0, "phase": "preparing"})
        self.footer_status.set("Working · You can browse Library and Settings while this job runs.")
        self.show_page("Downloads")
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
        self.run_job(job, title="Adding your novel", return_page="Library")

    def load_catalogue(self):
        def job(lib, client, report):
            lib.catalogue(client.catalogue(report))
            report("Catalogue saved. Select one or more novels to download.")
        self.run_job(job, title="Loading the catalogue", return_page="Library")

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
        formats = [f for f, value in self.formats.items() if value.get()] if self.auto_export.get() else []
        if self.auto_export.get() and not formats:
            messagebox.showinfo("Choose a format", "Select EPUB, PDF, or HTML for automatic export.")
            return
        def job(lib, client, report):
            if limit is None:
                queued = DownloadQueue(lib)
                queued.enqueue(selected, formats)
                queued.run(client, report, lambda value: self.events.put(("queue", value)), current=lambda value: self.events.put(("current", value)))
                return
            for n in selected:
                client.check()
                if not n.get("slug"):
                    n = client.discover(n["url"], report)
                    lib.save_index(n)
                s = lib.download(n["slug"], client, report, limit, progress=lambda value: self.events.put(("current", value)))
                report(f'{n["title"]}: {s["saved"]:,}/{s["total"]:,} saved, {s["failed"]} failed. Use Export selected to create books.')
                if formats and s["saved"] and s["saved"] == s["total"]:
                    client.check()
                    export_book(lib, n["slug"], formats)
        self.run_job(job)

    def show_queue_progress(self, value):
        self.queue_status.set(f"{value['completed']}/{value['total']} completed · {value['failed']} need attention")
        lib = Library()
        try:
            items = DownloadQueue(lib).items()
        finally:
            lib.close()
        self.queue_items = {item["url"]: item for item in items}
        states = {"pending": "Waiting", "running": "Downloading", "failed": "Needs attention", "completed": "Completed"}
        for item in items:
            values = (item["title"], states[item["state"]])
            if self.queue_table.exists(item["url"]):
                self.queue_table.item(item["url"], values=values, tags=(item["state"],))
            else:
                self.queue_table.insert("", "end", iid=item["url"], values=values, tags=(item["state"],))
        for iid in self.queue_table.get_children():
            if iid not in self.queue_items:
                self.queue_table.delete(iid)
        self.show_queue_error()
        self.update_actions()

    def show_current_progress(self, value):
        self.current = value
        self.current_title.set(value.get("title", "Working…"))
        total, saved = value.get("total", 0), value.get("saved", 0)
        phase = value.get("phase", "downloading")
        self.progress.stop()
        if total:
            percent = min(100, saved * 100 / total)
            self.progress.configure(mode="determinate", maximum=total, value=saved)
            self.percent.set(f"{percent:.0f}%")
            self.chapter_status.set(f"{saved:,} of {total:,} chapters saved" + (" · Exporting" if phase == "exporting" else ""))
        else:
            self.percent.set("")
            self.chapter_status.set({"indexing": "Collecting this novel’s chapter index…", "completed": "No chapters available", "preparing": "Getting things ready…"}.get(phase, "Working…"))
            self.progress.configure(mode="indeterminate", maximum=100, value=0)
            if self.busy:
                self.progress.start(12)
        if value.get("chapter"):
            self.status.set(value["chapter"])
        for iid, novel in self.items.items():
            if novel.get("slug") == value.get("slug") and value.get("slug"):
                novel["_summary"] = {"saved": saved, "total": total, "failed": value.get("failed", 0)}
                state = {"completed": "Completed", "exporting": "Exporting", "indexing": "Indexing"}.get(phase, "Downloading")
                self.table.item(iid, values=(f"{saved:,} / {total:,}", state))
                if self.table.selection() == (iid,):
                    self.detail_chapters.configure(text=f"{saved:,} of {total:,} chapters saved")

    def archive_all(self):
        formats = [f for f, value in self.formats.items() if value.get()] if self.auto_export.get() else []
        if self.auto_export.get() and not formats:
            messagebox.showinfo("Choose a format", "Select EPUB, PDF, or HTML for automatic export.")
            return
        def job(lib, client, report):
            report("Loading the entire catalogue. This downloads full novels; sample mode does not apply.")
            items = client.catalogue(report)
            lib.catalogue(items)
            queued = DownloadQueue(lib)
            queued.enqueue(items, formats)
            queued.run(client, report, lambda value: self.events.put(("queue", value)), current=lambda value: self.events.put(("current", value)))
        self.run_job(job)

    def resume_queue(self):
        def job(lib, client, report):
            DownloadQueue(lib).run(client, report, lambda value: self.events.put(("queue", value)), current=lambda value: self.events.put(("current", value)))
        self.run_job(job)

    def queue_details(self):
        lib = Library()
        try:
            items = DownloadQueue(lib).items()
        finally:
            lib.close()
        problems = [f"{item['title']}: {item['error']}" for item in items if item["error"]]
        messagebox.showinfo("Saved download queue", "Resume queue continues unfinished novels and retries failed ones. Export choices are saved per novel.\n\n"
                            + ("\n\n".join(problems[:20]) if problems else "No saved errors."))

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
                self.events.put(("current", {"slug": n["slug"], "title": n["title"], **lib.summary(n["slug"]), "phase": "exporting"}))
                paths = export_book(lib, n["slug"], formats)
                report("Created: " + ", ".join(str(p.name) for p in paths))
        self.run_job(job, title="Preparing your books")

    def poll(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "queue":
                    self.show_queue_progress(text)
                elif kind == "current":
                    self.show_current_progress(text)
                elif kind == "done":
                    self.busy = False
                    self.progress.stop()
                    for b in self.controls:
                        b.configure(state="normal")
                    self.pause_button.grid_remove()
                    self.refresh()
                    self.update_actions()
                    self.footer_status.set("Job stopped · See Downloads for details." if self.job_error else "Paused · Your progress is saved." if self.stop.is_set() else "Job finished · Your progress is saved.")
                    if self.stop.is_set() and self.current:
                        self.chapter_status.set(self.chapter_status.get() + " · Paused")
                    if self.job_return_page and not self.job_error and not self.stop.is_set():
                        self.show_page(self.job_return_page)
                else:
                    self.status.set(text)
                    self.log.configure(state="normal")
                    self.log.insert("end", text + "\n")
                    if int(self.log.index("end-1c").split(".")[0]) > 1000:
                        self.log.delete("1.0", "101.0")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                    if kind == "error":
                        self.job_error = True
                        self.footer_status.set("Job stopped · See Downloads for details.")
                        messagebox.showerror("Job stopped", text)
        except queue.Empty:
            pass
        self.poll_timer = self.window.after(150, self.poll)

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
        ttk.Label(body, text="Clear the current library", font=(self.font, 16, "bold")).pack(anchor="w")
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
            self._load_preferences()
            self.library_path.configure(text=str(library_directory()))
            self.refresh()
            self.status.set(f"Library: {chosen}")
        except Exception as exc:
            messagebox.showerror("Cannot use this library", str(exc))

    def close(self):
        if self.busy:
            self.stop.set()
            self.status.set("Stopping safely. Close the window again once the current job finishes.")
            return
        for timer in (getattr(self, "poll_timer", None), getattr(self, "resume_timer", None)):
            if timer:
                try:
                    self.window.after_cancel(timer)
                except tk.TclError:
                    pass
        self.window.destroy()

    def mainloop(self):
        self.window.mainloop()
