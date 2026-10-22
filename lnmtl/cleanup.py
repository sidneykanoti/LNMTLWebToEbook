"""Plan and remove known application files, never recursively delete a user folder."""
import json
import sqlite3
import shutil
from dataclasses import dataclass
from pathlib import Path

from .platform_support import library_directory, output_directory, user_data_directory


def remove_app_data_folder():
    """Remove only the explicitly named app-owned folder, after UI confirmation."""
    folder = user_data_directory()
    if folder.name != "LNMTLWebToEbook" or folder.is_symlink() or folder.is_junction():
        raise ValueError("Refusing to remove an unexpected or linked application-data folder.")
    target = folder.resolve()
    if target.name != "LNMTLWebToEbook" or target == target.parent:
        raise ValueError("Application-data folder validation failed.")
    if target.exists():
        shutil.rmtree(target)


@dataclass
class CleanupPlan:
    files: list
    library: Path
    output: Path
    size: int


def _safe_file(path, boundary):
    path, boundary = Path(path), Path(boundary).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(boundary) or path.resolve() == boundary:
        raise ValueError(f"Cleanup refused an unexpected path: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Cleanup expected a file: {path}")
    return path.resolve()


def plan_cleanup(include_books=False, include_preferences=False, root=None):
    library = Path(root or library_directory()).resolve()
    output = output_directory(library).resolve()
    entries = {}

    def add(path, boundary):
        path = _safe_file(path, boundary)
        if path.exists():
            entries[path] = Path(boundary).resolve()

    db = library / "archive.sqlite3"
    slugs = []
    if db.exists():
        _safe_file(db, library)
        connection = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
        try:
            slugs = [r[0] for r in connection.execute("SELECT slug FROM novels")]
            for (raw,) in connection.execute("SELECT raw_path FROM chapters WHERE raw_path IS NOT NULL"):
                path = library / raw
                # Archive entries cannot point outside the raw-pages directory.
                _safe_file(path, library)
                add(path, library / "raw")
        finally:
            connection.close()
    if include_books:
        if output_directory(library).is_symlink():
            raise ValueError("Cleanup cannot follow a linked output directory.")
        # Exports can outlive a previously cleared chapter database.
        if output.is_dir():
            for folder in output.iterdir():
                report = folder / "archive-report.json"
                if folder.is_dir() and not folder.is_symlink() and report.is_file():
                    _safe_file(report, output)
                    try:
                        metadata = json.loads(report.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    if isinstance(metadata, dict) and metadata.get("source") == "https://lnmtl.com/novel/" + folder.name:
                        slugs.append(folder.name)
        for slug in set(slugs):
            # Legacy exports are recognized by the report our exporter wrote.
            if Path(slug).name != slug or slug in (".", ".."):
                raise ValueError("Unexpected novel folder in the library.")
            folder = output / slug
            report_file = folder / "archive-report.json"
            if not report_file.exists():
                continue
            _safe_file(report_file, output)
            report = json.loads(report_file.read_text(encoding="utf-8"))
            if report.get("source") != "https://lnmtl.com/novel/" + slug:
                raise ValueError(f"Cannot verify this export belongs to the app: {folder}")
            for suffix in ("epub", "pdf", "html"):
                add(folder / f"{slug}.{suffix}", output)
            add(report_file, output)
    for name in ("archive.sqlite3", "archive.sqlite3-wal", "archive.sqlite3-shm", "archive.sqlite3-journal"):
        add(library / name, library)
    if include_preferences:
        data = user_data_directory()
        for name in ("preferences.json", "preferences.json.tmp", "startup-error.log"):
            add(data / name, data)
    return CleanupPlan(list(entries.items()), library, output, sum(p.stat().st_size for p in entries))


def clear_planned_data(plan):
    # Validate every target again before deleting the first file.
    for path, boundary in plan.files:
        _safe_file(path, boundary)
    removed = 0
    for path, _ in plan.files:
        if path.exists():
            path.unlink()
            removed += 1
    # Only remove empty folders inside the exact library/output boundaries.
    # No recursive deletion and no removal of unrelated files.
    parents = {p.parent for p, _ in plan.files}
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        for boundary in (plan.library, plan.output):
            while parent != boundary and parent.is_relative_to(boundary):
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    return removed
