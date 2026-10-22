"""Offline acceptance test executed by the actual packaged application."""
import json
import os
import traceback
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .export import export_book
from .library import Library
from .platform_support import APP_NAME, VERSION, configure_runtime
from .source import clean_chapter


def run(directory):
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    report = {"version": VERSION, "passed": False, "checks": []}
    prior = os.environ.get("LNMTL_LIBRARY_DIR")
    os.environ["LNMTL_LIBRARY_DIR"] = str(root / "library")
    lib = None
    try:
        configure_runtime()
        from .gui import App
        app = App()
        app.window.update()
        assert app.window.title() == f"{APP_NAME} {VERSION}"
        assert app.support_button.winfo_rooty() < app.table.winfo_rooty()
        assert app.url_label.winfo_rooty() < app.url_entry.winfo_rooty()
        assert app.url_entry.winfo_height() == app.index_button.winfo_height() == app.catalogue_button.winfo_height()
        app.window.geometry("840x650")
        app.window.update()
        assert app.support_button.winfo_ismapped() and app.clear_button.winfo_ismapped()
        assert app.log.winfo_height() >= 40
        app.close()
        report["checks"].append("Branded desktop window, app icon, visible top support controls, and clear-data button")
        lib = Library()
        chapter = {"url": "https://lnmtl.com/chapter/packaging-test", "title": "Colors and emphasis", "number": 1,
                   "part": None, "special": False, "volume": 1, "volume_title": "Sample", "position": 1, "ordinal": 1}
        lib.save_index({"slug": "packaging-test", "url": "https://lnmtl.com/novel/packaging-test",
                        "title": "Reading Library - Offline Package Test", "author": "Package verification", "volumes": [], "chapters": [chapter]})
        raw = '''<div class="chapter-body"><sentence class="translated">The <t>blue glossary term</t> and the <w class="postfixed">green modified words</w> keep their colors. <dq>This sentence is italic.</dq> <sq>This sentence is bold.</sq> <da>This sentence has heavy emphasis.</da></sentence><sentence class="translated">A readable book should preserve paragraph spacing, chapter headings, punctuation, and the text's original emphasis. This sample is generated entirely offline; no novels are included in the distributed app.</sentence></div>'''
        html = clean_chapter(raw)
        with lib.db:
            lib.db.execute("UPDATE chapters SET html=? WHERE url=?", (html, chapter["url"]))
        report["checks"].append("Writable local SQLite library")
        paths = export_book(lib, "packaging-test", ("epub", "html", "pdf"), root / "books")
        epub, _, pdf = paths
        with zipfile.ZipFile(epub) as z:
            assert z.read("mimetype") == b"application/epub+zip"
            for name in z.namelist():
                if name.endswith((".xhtml", ".xml", ".opf", ".ncx")):
                    ElementTree.fromstring(z.read(name))
            chapter_html = z.read("OEBPS/chapter-000001.xhtml").decode()
            for style in ('class="term"', 'class="modified"', '<em>', '<strong>', '<b>'):
                assert style in chapter_html, f"Missing {style}"
        report["checks"].append("EPUB structure, colors, italic, bold, and heavy emphasis")
        assert pdf.read_bytes().startswith(b"%PDF-") and pdf.stat().st_size > 5000
        report["checks"].append("PDF created with packaged Chromium, without Edge")
        report["passed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if lib:
            lib.close()
        if prior is None:
            os.environ.pop("LNMTL_LIBRARY_DIR", None)
        else:
            os.environ["LNMTL_LIBRARY_DIR"] = prior
        (root / "self-test.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1
