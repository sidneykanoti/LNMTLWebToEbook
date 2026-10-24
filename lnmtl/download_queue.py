"""Persistent, sequential bulk downloads with bounded retries and offline exports."""
import json
import time
from contextlib import contextmanager

from .export import export_book
from .source import AccessBlocked, Client, Stopped, novel_url


@contextmanager
def runner_lock(root):
    """An OS lock releases automatically if a process exits or crashes."""
    stream = (root / "download-queue.lock").open("a+b")
    try:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            import os
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("This library's queue is already running in another app window.") from exc
        yield
    finally:
        stream.close()


class DownloadQueue:
    MAX_ATTEMPTS = 3

    def __init__(self, library):
        self.library = library
        self.db = library.db

    def enqueue(self, novels, formats=()):
        formats = list(formats)
        if any(fmt not in ("epub", "pdf", "html") for fmt in formats):
            raise ValueError("Choose EPUB, PDF, or HTML for automatic export.")
        items = []
        for novel in novels:
            url = novel_url(novel["url"])
            items.append((url, novel["title"], url.rsplit("/", 1)[-1], json.dumps(formats)))
        with runner_lock(self.library.root), self.db:
            for item in items:
                self.db.execute("""INSERT INTO download_queue(url,title,slug,formats) VALUES (?,?,?,?)
                    ON CONFLICT(url) DO UPDATE SET title=excluded.title, formats=excluded.formats,
                    state='pending', attempts=0, retry_at=0, error=NULL""", item)

    def items(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM download_queue ORDER BY id")]

    def progress(self):
        states = {row[0]: row[1] for row in self.db.execute(
            "SELECT state, COUNT(*) FROM download_queue GROUP BY state")}
        chapters = self.db.execute("""SELECT COUNT(*), COALESCE(SUM(c.html IS NOT NULL),0)
            FROM chapters c INDEXED BY chapter_download_progress
            JOIN download_queue q ON q.slug=c.slug""").fetchone()
        indexed = self.db.execute("""SELECT COUNT(*) FROM download_queue q
            JOIN novels n ON n.slug=q.slug""").fetchone()[0]
        return {"total": sum(states.values()), "completed": states.get("completed", 0),
                "failed": states.get("failed", 0), "indexed": indexed,
                "chapters": chapters[0], "saved": chapters[1]}

    def _update(self, url, **values):
        with self.db:
            self.db.execute("UPDATE download_queue SET " + ",".join(key + "=?" for key in values)
                            + " WHERE url=?", (*values.values(), url))

    def run(self, client=None, report=lambda _: None, progress=lambda _: None, exporter=export_book):
        client = client or Client()
        with runner_lock(self.library.root):
            # In-progress rows belong to an interrupted process: preserve saved chapters
            # and do not charge a retry for the interruption.
            with self.db:
                self.db.execute("""UPDATE download_queue SET state='pending',
                    attempts=MAX(0,attempts-1), retry_at=0 WHERE state='running'""")
                self.db.execute("""UPDATE download_queue SET state='pending', attempts=0,
                    retry_at=0 WHERE state='failed'""")
            progress(self.progress())
            while True:
                client.check()
                row = self.db.execute("""SELECT * FROM download_queue WHERE state='pending'
                    ORDER BY retry_at,id LIMIT 1""").fetchone()
                if row is None:
                    break
                row = dict(row)
                delay = row["retry_at"] - time.time()
                if delay > 0:
                    report(f"Waiting {int(delay) + 1}s before retrying {row['title']}…")
                    if client.stop.wait(min(delay, 30)):
                        client.check()
                    continue
                attempt = row["attempts"] + 1
                self._update(row["url"], state="running", attempts=attempt, error=None)
                try:
                    report(f"Queue: {row['title']} (attempt {attempt}/{self.MAX_ATTEMPTS})")
                    exists = self.db.execute("SELECT 1 FROM novels WHERE slug=?", (row["slug"],)).fetchone()
                    if not exists:
                        self.library.save_index(client.discover(row["url"], report))

                    last_progress = [0.0]

                    def chapter_progress(message):
                        report(message)
                        now = time.monotonic()
                        if now - last_progress[0] >= 5:
                            progress(self.progress())
                            last_progress[0] = now

                    summary = self.library.download(row["slug"], client, chapter_progress)
                    if summary["saved"] < summary["total"]:
                        raise RuntimeError(f"{summary['total'] - summary['saved']} chapters still need downloading")
                    formats = json.loads(row["formats"])
                    if formats and summary["saved"]:
                        client.check()
                        report(f"Exporting {row['title']}…")
                        exporter(self.library, row["slug"], formats)
                    self._update(row["url"], state="completed", retry_at=0, error=None)
                except (Stopped, AccessBlocked) as exc:
                    self._update(row["url"], state="pending", attempts=attempt - 1, retry_at=0, error=str(exc))
                    progress(self.progress())
                    raise
                except Exception as exc:
                    state = "failed" if attempt >= self.MAX_ATTEMPTS else "pending"
                    self._update(row["url"], state=state, error=str(exc), retry_at=time.time() + 15 * 2 ** (attempt - 1))
                    report(f"{row['title']}: {exc}. " + ("Retry limit reached; use Resume queue to try again." if state == "failed" else "Saved for automatic retry; continuing with other novels."))
                progress(self.progress())
            result = self.progress()
            report(f"Queue finished: {result['completed']}/{result['total']} novels completed, {result['failed']} need attention.")
            return result
