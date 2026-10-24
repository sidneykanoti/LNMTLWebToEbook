"""Offline acceptance test executed by the actual packaged application."""
import base64
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
        assert app.active_page == "Library" and app.table.winfo_ismapped()
        assert not app.support_button.winfo_ismapped() and not app.clear_button.winfo_ismapped()
        assert "disabled" in app.download_button.state()
        app.window.geometry("1040x700")
        app.window.update()
        assert app.index_button.winfo_ismapped() and app.catalogue_button.winfo_ismapped()
        assert list(app.nav_buttons) == ["Library", "Downloads", "Help", "Donate", "Settings"]
        app.nav_buttons["Help"].invoke()
        app.window.update()
        assert app.active_page == "Help" and app.pages["Help"].winfo_ismapped()
        from unittest.mock import patch
        from .platform_support import SUPPORT_URL
        with patch("lnmtl.gui.webbrowser.open_new_tab", return_value=True) as browser:
            app.nav_buttons["Donate"].invoke()
            browser.assert_called_once_with(SUPPORT_URL)
        assert app.active_page == "Help"
        app.show_page("Settings")
        app.window.update()
        assert app.support_button.winfo_ismapped() and app.clear_button.winfo_ismapped()
        with patch("lnmtl.gui.webbrowser.open_new_tab", return_value=True) as browser:
            app.support_button.invoke()
            browser.assert_called_once_with(SUPPORT_URL)
        assert app.clear_button.winfo_rooty() + app.clear_button.winfo_height() < app.window.winfo_rooty() + app.window.winfo_height()
        app.show_page("Downloads")
        app.window.update()
        assert app.archive_button.winfo_ismapped() and app.resume_button.winfo_ismapped()
        assert not app.log.winfo_ismapped()
        app.toggle_activity()
        app.window.update()
        assert app.log.winfo_height() >= 40 and app.log.winfo_ismapped()
        app.show_current_progress({"title": "Example novel", "total": 767, "saved": 176, "phase": "downloading"})
        assert app.percent.get() == "23%"
        assert app.progress["value"] == 176 and str(app.progress["mode"]) == "determinate"
        app.toggle_activity()
        app.close()
        report["checks"].append("Library/Downloads/Settings navigation, compact layout, chapter percentage, and collapsed activity")
        lib = Library()
        chapter = {"url": "https://lnmtl.com/chapter/packaging-test", "title": "Colors and emphasis", "number": 1,
                   "part": None, "special": False, "volume": 1, "volume_title": "Sample", "position": 1, "ordinal": 1}
        lib.save_index({"slug": "packaging-test", "url": "https://lnmtl.com/novel/packaging-test",
                        "title": "Reading Library - Offline Package Test", "author": "Package verification",
                        "synopsis": ["An offline synopsis with preserved paragraphs.", "A second paragraph for export verification."],
                        "poster": {"mime": "image/png", "data": base64.b64encode((Path(__file__).resolve().parent.parent / "assets" / "app-64.png").read_bytes()).decode("ascii")},
                        "volumes": [], "chapters": [chapter]})
        raw = '''<div class="chapter-body"><sentence class="translated">The <t>blue glossary term</t> and the <w class="postfixed">green modified words</w> keep their colors. <dq>This sentence is italic.</dq> <sq>This sentence is bold.</sq> <da>This sentence has heavy emphasis.</da></sentence><sentence class="translated">A readable book should preserve paragraph spacing, chapter headings, punctuation, and the text's original emphasis. This sample is generated entirely offline; no novels are included in the distributed app.</sentence></div>'''
        html = clean_chapter(raw)
        with lib.db:
            lib.db.execute("UPDATE chapters SET html=? WHERE url=?", (html, chapter["url"]))
        report["checks"].append("Writable local SQLite library")
        app = App()
        app.window.update()
        matching = [iid for iid, novel in app.items.items() if novel["url"] == "https://lnmtl.com/novel/packaging-test"]
        app.table.selection_set(matching[0])
        app.render_selection()
        assert app.detail_title["text"] == "Reading Library - Offline Package Test"
        assert "disabled" not in app.export_button.state()
        assert app.poster_photo(lib.novel("packaging-test")).height() == 42
        # Exercise JPEG decoding inside the frozen app as LNMTL posters use JPEG.
        import io
        from PIL import Image
        jpeg = io.BytesIO()
        with Image.open(Path(__file__).resolve().parent.parent / "assets" / "app-64.png") as poster:
            poster.convert("RGB").save(jpeg, format="JPEG")
        assert app.poster_photo({"url": "jpeg-test", "poster": {"data": base64.b64encode(jpeg.getvalue()).decode("ascii")}}).height() == 42
        app.sample.set(False)
        app.auto_export.set(True)
        app._save_preferences()
        app.sample.set(True)
        app.auto_export.set(False)
        app._load_preferences()
        assert app.sample.get() is False and app.auto_export.get() is True
        app.search.set("Package verification")
        app.window.update()
        assert len(app.items) == 1
        app.search.set("No matching title exists")
        app.window.update()
        assert len(app.items) == 0 and "disabled" in app.download_button.state()
        app.close()
        report["checks"].append("PNG/JPEG poster thumbnails, selection actions, author search, and saved preferences")
        from .download_queue import DownloadQueue
        queued = DownloadQueue(lib)
        queued.enqueue([lib.novel("packaging-test")])
        class OfflineClient:
            def check(self):
                pass
        assert queued.run(OfflineClient())["completed"] == 1
        report["checks"].append("Persistent bulk queue and completed novel recovery")
        paths = export_book(lib, "packaging-test", ("epub", "html", "pdf"), root / "books")
        epub, _, pdf = paths
        with zipfile.ZipFile(epub) as z:
            assert z.read("mimetype") == b"application/epub+zip"
            for name in z.namelist():
                if name.endswith((".xhtml", ".xml", ".opf", ".ncx")):
                    ElementTree.fromstring(z.read(name))
            assert z.read("OEBPS/poster.png").startswith(b"\x89PNG")
            assert b'properties="cover-image"' in z.read("OEBPS/content.opf")
            front = z.read("OEBPS/cover.xhtml")
            assert b'src="poster.png"' in front and b"An offline synopsis" in front
            chapter_html = z.read("OEBPS/chapter-000001.xhtml").decode()
            for style in ('class="term"', 'class="modified"', '<em>', '<strong>', '<b>'):
                assert style in chapter_html, f"Missing {style}"
        report["checks"].append("EPUB cover image, author, synopsis, structure, colors, italic, bold, and heavy emphasis")
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
