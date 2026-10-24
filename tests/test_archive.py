import base64
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from lnmtl.export import export_epub, export_html
from lnmtl.library import Library
from lnmtl.source import Client, Stopped, clean_chapter, embedded_json, novel_url, novel_details, poster_type
from bs4 import BeautifulSoup

HTML = '''<div class="chapter-body"><sentence class="translated">The <t>Blue Moon</t> met a <w class="postfixed">green dragon</w>. <dq>Italic words</dq> <sq>Bold words</sq> <da>Heavy words</da><br/>A &amp; B.</sentence><sentence class="original">DO NOT EXPORT CHINESE</sentence></div>'''


def chapter(number=401, volume=5):
    return {"url": f"https://lnmtl.com/chapter/test-{number}", "title": "A & B", "number": number,
        "part": None, "special": False, "volume": volume, "volume_title": "Boat", "position": number, "ordinal": number}


class ArchiveTests(unittest.TestCase):
    def test_styles_and_only_english(self):
        text = clean_chapter(HTML)
        self.assertIn('<span class="term">Blue Moon</span>', text)
        self.assertIn('<span class="modified">green dragon</span>.', text)
        for tag, word in (("em", "Italic"), ("strong", "Bold"), ("b", "Heavy")):
            self.assertIn(f"<{tag}>{word} words</{tag}>", text)
        self.assertIn("A &amp; B.", text)
        self.assertNotIn("DO NOT EXPORT", text)
        ElementTree.fromstring("<div>" + text + "</div>")

    def test_reject_invalid_content(self):
        for html in ("<title>Just a moment</title>", "<html>error</html>", '<div class="chapter-body"></div>'):
            with self.assertRaises(ValueError):
                clean_chapter(html)

    def test_url_validation(self):
        self.assertEqual(novel_url("against-the-gods"), "https://lnmtl.com/novel/against-the-gods")
        for url in ("https://evil.com/novel/a", "https://lnmtl.com/novel/../../a", "https://lnmtl.com/chapter/a"):
            with self.assertRaises(ValueError):
                novel_url(url)

    def test_json_is_parsed_without_executing_scripts(self):
        self.assertEqual(embedded_json('lnmtl.volumes = [{"title":"a; b"}];evil()', 'volumes'), [{"title": "a; b"}])

    def test_volume_boundary_and_page_discovery(self):
        volumes = [{"id": 5, "number": 5}, {"id": 6, "number": 6}]
        def response(page, vid, number):
            return {"current_page": page, "last_page": 2 if vid == 5 else 1, "total": 2 if vid == 5 else 1,
                "data": [{"volume_id": vid, "site_url": f"https://lnmtl.com/chapter/real-{vid}-{number}", "number": number, "title": "Test", "position": number}]}
        html = '<h2>Test</h2><script>lnmtl.volumes=' + json.dumps(volumes) + ';lnmtl.firstResponse=' + json.dumps(response(1, 5, 450)) + ';</script>'
        class FakeClient(Client):
            def get(self, url, **kwargs):
                class Response:
                    text = html
                    def json(inner):
                        p = kwargs["params"]
                        return response(p["page"], p["volumeId"], 451 if p["volumeId"] == 5 else 501)
                return Response()
        n = FakeClient().discover("test")
        self.assertEqual([c["number"] for c in n["chapters"]], [450, 451, 501])
        self.assertEqual([c["volume"] for c in n["chapters"]], [5, 5, 6])

    def test_resume_refresh_and_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = Library(Path(tmp) / "library")
            novel = {"slug": "test", "url": "https://lnmtl.com/novel/test", "title": "A & B", "author": "Author", "volumes": [], "chapters": [chapter(), chapter(501, 6)]}
            lib.save_index(novel)
            class FakeClient(Client):
                calls = 0
                def get(self, url, **kwargs):
                    self.calls += 1
                    class R:
                        text = HTML
                    return R()
            client = FakeClient()
            self.assertEqual(lib.download("test", client, limit=1)["saved"], 1)
            lib.save_index(novel)
            self.assertEqual(lib.summary("test")["saved"], 1)
            self.assertEqual(lib.download("test", client)["saved"], 2)
            lib.download("test", client)
            self.assertEqual(client.calls, 2)
            book = lib.book("test")
            path = export_epub(book, Path(tmp) / "test.epub")
            with zipfile.ZipFile(path) as z:
                self.assertEqual(z.namelist()[0], "mimetype")
                self.assertEqual(z.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
                for name in z.namelist():
                    if name.endswith((".xhtml", ".opf", ".xml", ".ncx")):
                        ElementTree.fromstring(z.read(name))
                self.assertIn(b"#006c36", z.read("OEBPS/book.css"))
                self.assertIn(b"Volume 6", z.read("OEBPS/nav.xhtml"))
            export_html(book, Path(tmp) / "test.html")
            lib.close()

    def test_novel_details_and_local_poster(self):
        image = (Path(__file__).resolve().parents[1] / "assets" / "app-64.png").read_bytes()
        html = '<div class="media"><div class="media-left"><img src="/poster.png" /></div><h2>Test</h2><div class="description"><p>First &amp; second.</p><p>Next paragraph.</p><script>unsafe()</script><div class="source">Description from Example</div></div></div><script>lnmtl.volumes=[];</script>'
        class FakeClient(Client):
            def get(self, url, **kwargs):
                class Response:
                    text = html
                    def iter_content(inner, size):
                        yield image
                    def close(inner):
                        pass
                return Response()
        novel = FakeClient().discover("test")
        self.assertEqual(novel["synopsis"], ["First & second.", "Next paragraph."])
        self.assertEqual(novel["synopsis_source"], "Description from Example")
        self.assertEqual(novel["poster_url"], "https://lnmtl.com/poster.png")
        self.assertEqual(base64.b64decode(novel["poster"]["data"]), image)
        with tempfile.TemporaryDirectory() as tmp:
            with_lib = Library(Path(tmp) / "library")
            try:
                novel["chapters"] = [chapter()]
                with_lib.save_index(novel)
                with with_lib.db:
                    with_lib.db.execute("UPDATE chapters SET html=?", (clean_chapter(HTML),))
                book = with_lib.book("test")
                html_path = export_html(book, Path(tmp) / "book.html")
                markup = html_path.read_text(encoding="utf-8")
                self.assertIn("data:image/png;base64,", markup)
                self.assertIn("First &amp; second.", markup)
                self.assertLess(markup.index('class="poster"'), markup.index('id="synopsis"'))
                self.assertLess(markup.index('id="synopsis"'), markup.index('<nav>'))
                with zipfile.ZipFile(export_epub(book, Path(tmp) / "book.epub")) as z:
                    self.assertEqual(z.read("OEBPS/poster.png"), image)
                    self.assertIn(b'properties="cover-image"', z.read("OEBPS/content.opf"))
                    self.assertIn(b'src="poster.png"', z.read("OEBPS/cover.xhtml"))
                    self.assertNotIn(b'data:image', z.read("OEBPS/cover.xhtml"))
                    for name in z.namelist():
                        if name.endswith((".xhtml", ".opf")):
                            ElementTree.fromstring(z.read(name))
                # A refresh with an unavailable poster keeps the saved offline image.
                novel.pop("poster")
                with_lib.save_index(novel)
                self.assertEqual(with_lib.novel("test")["poster"], book["poster"])
            finally:
                with_lib.close()

    def test_missing_and_invalid_posters(self):
        self.assertEqual(novel_details(BeautifulSoup('<h2>Title</h2>', "html.parser"), "https://lnmtl.com/novel/test")["synopsis"], [])
        with self.assertRaises(ValueError):
            poster_type(b"<html>blocked</html>")
        class MissingPosterClient(Client):
            def get(self, url, **kwargs):
                if kwargs.get("stream"):
                    raise ValueError("Unavailable")
                class Response:
                    text = '<div class="media-left"><img src="/missing.jpg" /></div><h2>Test</h2><script>lnmtl.volumes=[];</script>'
                return Response()
        messages = []
        novel = MissingPosterClient().discover("test", messages.append)
        self.assertNotIn("poster", novel)
        self.assertTrue(any("Poster unavailable" in message for message in messages))

    def test_pause(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(Stopped):
            Client(stop=stop).check()


if __name__ == "__main__":
    unittest.main()
