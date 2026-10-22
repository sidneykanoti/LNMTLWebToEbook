import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .source import AccessBlocked, Client, Stopped, clean_chapter
from .platform_support import SOURCE_ROOT, library_directory

ROOT = SOURCE_ROOT


class Library:
    def __init__(self, root=None):
        self.root = Path(root).expanduser().resolve() if root else library_directory()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "archive.sqlite3", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS novels (slug TEXT PRIMARY KEY, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS chapters (url TEXT PRIMARY KEY, slug TEXT NOT NULL,
                ordinal INTEGER NOT NULL, metadata TEXT NOT NULL, html TEXT, raw_path TEXT,
                sha256 TEXT, downloaded_at TEXT, error TEXT);
            CREATE INDEX IF NOT EXISTS chapter_novel ON chapters(slug, ordinal);
            CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def catalogue(self, items=None):
        if items is not None:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO settings VALUES ('catalogue', ?)", (json.dumps(items, ensure_ascii=False),))
        row = self.db.execute("SELECT value FROM settings WHERE name='catalogue'").fetchone()
        return json.loads(row[0]) if row else []

    def save_index(self, novel):
        # Commit only complete, validated discovery results. Existing chapter bodies survive refreshes.
        with self.db:
            metadata = {k: v for k, v in novel.items() if k != "chapters"}
            metadata["indexed_at"] = datetime.now(timezone.utc).isoformat()
            self.db.execute("INSERT OR REPLACE INTO novels VALUES (?,?)", (novel["slug"], json.dumps(metadata, ensure_ascii=False)))
            for c in novel["chapters"]:
                self.db.execute("""INSERT INTO chapters(url,slug,ordinal,metadata) VALUES (?,?,?,?)
                    ON CONFLICT(url) DO UPDATE SET ordinal=excluded.ordinal, metadata=excluded.metadata""",
                    (c["url"], novel["slug"], c["ordinal"], json.dumps(c, ensure_ascii=False)))
            # Previously saved chapters remain preserved if LNMTL later removes their links.

    def novels(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT metadata FROM novels ORDER BY slug")]

    def novel(self, slug):
        row = self.db.execute("SELECT metadata FROM novels WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise ValueError("Index this novel first.")
        return json.loads(row[0])

    def chapters(self, slug):
        # Source volume/position, then discovery order; do not assume contiguous chapter numbers.
        rows = [dict(r) for r in self.db.execute("SELECT * FROM chapters WHERE slug=? ORDER BY ordinal", (slug,))]
        for r in rows:
            r["chapter"] = json.loads(r.pop("metadata"))
        return sorted(rows, key=lambda r: (float(r["chapter"]["volume"]), float(r["chapter"].get("position") or r["ordinal"]), r["ordinal"]))

    def summary(self, slug):
        r = self.db.execute("SELECT COUNT(*), COUNT(html), SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) FROM chapters WHERE slug=?", (slug,)).fetchone()
        return {"total": r[0], "saved": r[1], "failed": r[2] or 0}

    def download(self, slug, client=None, report=lambda _: None, limit=None):
        client = client or Client()
        pending = [r for r in self.chapters(slug) if not r["html"]]
        if limit is not None:
            pending = pending[:limit]
        raw_dir = self.root / "raw" / slug
        raw_dir.mkdir(parents=True, exist_ok=True)
        for i, row in enumerate(pending, 1):
            client.check()
            c = row["chapter"]
            report(f"Downloading {i}/{len(pending)}: #{c['number']} {c['title']}")
            try:
                raw = client.get(row["url"]).text
                clean = clean_chapter(raw)
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                path = raw_dir / (hashlib.sha256(row["url"].encode()).hexdigest()[:24] + ".html")
                temp = path.with_suffix(".tmp")
                temp.write_text(raw, encoding="utf-8")
                temp.replace(path)
                with self.db:
                    self.db.execute("UPDATE chapters SET html=?,raw_path=?,sha256=?,downloaded_at=?,error=NULL WHERE url=?",
                        (clean, str(path.relative_to(self.root)), digest, datetime.now(timezone.utc).isoformat(), row["url"]))
            except (Stopped, AccessBlocked):
                raise
            except Exception as exc:
                with self.db:
                    self.db.execute("UPDATE chapters SET error=? WHERE url=?", (str(exc), row["url"]))
                report(f"Failed #{c['number']}: {exc}")
        return self.summary(slug)

    def book(self, slug):
        novel = self.novel(slug)
        rows = self.chapters(slug)
        saved = [r for r in rows if r["html"]]
        if not saved:
            raise ValueError("Download at least one chapter before exporting.")
        novel["chapters"] = saved
        novel["summary"] = self.summary(slug)
        return novel
