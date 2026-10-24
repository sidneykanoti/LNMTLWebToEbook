"""Generate self-contained HTML, EPUB 3, and PDF from the local archive."""
import base64
import json
import uuid
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

CSS = """
body { font-family: Georgia, 'Times New Roman', serif; color: #242526;
  line-height: 1.65; margin: 0 auto; padding: 2em; max-width: 42em; background: white; }
h1, h2, h3 { font-weight: normal; line-height: 1.25; color: #183d3b; }
h1 { font-size: 2.3em; } h2 { font-size: 1.65em; margin-top: 1em; }
p { margin: 0 0 1em; orphans: 3; widows: 3; }
.term { color: #0a3568; } .modified { color: #006c36; }
em { font-style: italic; font-weight: normal; } strong { font-weight: 600; } b { font-weight: 800; }
.chapter { break-before: page; } .volume { break-before: page; padding-top: 3em; }
.muted, .source { color: #626868; font-size: .8em; }
.cover { padding: 1em 0; break-after: page; text-align: center; }
.poster { display: block; margin: 0 auto 1.5em; max-width: 100%; width: auto;
  height: auto; max-height: 100mm; object-fit: contain; }
.synopsis, .export-details { break-after: page; }
a { color: #0a3568; text-decoration: none; } li { margin: .35em 0; }
@page { size: A5; margin: 18mm 16mm 20mm; }
@media print { body { padding: 0; max-width: none; font-size: 11pt; }
 h1,h2,h3 { break-after: avoid; } a { color: inherit; } }
"""


def chapter_label(c):
    prefix = "Special " if c.get("special") else ""
    part = f" (part {c['part']})" if c.get("part") is not None else ""
    return f"{prefix}#{c['number']}{part}: {c['title']}"


def document(title, body, css="book.css", epub=False):
    namespace = ' xmlns:epub="http://www.idpf.org/2007/ops"' if epub else ""
    return f'<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml"{namespace} lang="en"><head><meta charset="utf-8" /><title>{escape(title)}</title><link rel="stylesheet" href="{css}" /></head><body>{body}</body></html>'


def cover(book, poster_src=None):
    s = book["summary"]
    partial = " This export is partial; download the remaining indexed chapters and export again." if s["saved"] < s["total"] else ""
    poster = book.get("poster")
    image = ""
    if poster:
        src = poster_src or f"data:{poster['mime']};base64,{poster['data']}"
        image = f'<img class="poster" src="{escape(src, quote=True)}" alt="{escape(book["title"], quote=True)} cover" />'
    synopsis = ""
    if book.get("synopsis"):
        paragraphs = "".join('<p>' + escape(p) + '</p>' for p in book["synopsis"])
        attribution = '<p class="source">' + escape(book["synopsis_source"]) + '</p>' if book.get("synopsis_source") else ""
        synopsis = f'<section class="synopsis" id="synopsis"><h2>Synopsis</h2>{paragraphs}{attribution}</section>'
    return (f'<section class="cover">{image}<h1>{escape(book["title"])}</h1><p>{escape(book["author"])}</p></section>'
            + synopsis
            + f'<section class="export-details"><p class="muted">LNMTL WEB TO EBOOK</p><p>{s["saved"]:,} saved chapters of {s["total"]:,} indexed.{partial}</p><p class="muted">Contains chapters available on LNMTL. Earlier or missing chapters are not reconstructed. Original machine translation, colors, and emphasis are preserved.</p><p class="source">Source: <a href="{escape(book["url"], quote=True)}">{escape(book["url"])}</a></p></section>')



def chapter_body(row):
    c = row["chapter"]
    return f'<section class="chapter"><p class="muted">VOLUME {escape(str(c["volume"]))}</p><h2>{escape(chapter_label(c))}</h2>{row["html"]}</section>'


def volume_label(c):
    return f'Volume {c["volume"]}' + (f' — {c["volume_title"]}' if c["volume_title"] else "")


def export_html(book, path):
    path = Path(path)
    body, toc, last_volume = [cover(book)], [], None
    if book.get("synopsis"):
        toc.append('<li><a href="#synopsis">Synopsis</a></li>')
    for i, row in enumerate(book["chapters"]):
        c = row["chapter"]
        if c["volume"] != last_volume:
            body.append(f'<section class="volume"><h1>{escape(volume_label(c))}</h1></section>')
            toc.append(f'<li><strong>{escape(volume_label(c))}</strong></li>')
            last_volume = c["volume"]
        toc.append(f'<li><a href="#chapter-{i}">{escape(chapter_label(c))}</a></li>')
        body.append(chapter_body(row).replace('class="chapter"', f'class="chapter" id="chapter-{i}"', 1))
    body.insert(1, '<nav><h2>Contents</h2><ol>' + "".join(toc) + '</ol></nav>')
    html = document(book["title"], "".join(body)).replace('<link rel="stylesheet" href="book.css" />', '<style>' + CSS + '</style>')
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(html, encoding="utf-8")
    temp.replace(path)
    return path


def export_epub(book, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".epub.tmp")
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, book["url"]))
    poster = book.get("poster")
    poster_name = "poster." + {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif"}[poster["mime"]] if poster else None
    files = {"cover.xhtml": document(book["title"], cover(book, poster_name)), "book.css": CSS}
    if poster:
        files[poster_name] = base64.b64decode(poster["data"], validate=True)
    manifest = ['<item id="css" href="book.css" media-type="text/css"/>', '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>', '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>', '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>']
    if poster:
        manifest.append(f'<item id="poster" href="{poster_name}" media-type="{poster["mime"]}" properties="cover-image"/>')
    spine = ['<itemref idref="cover"/>']
    groups, last = [], None
    ncx = []
    for i, row in enumerate(book["chapters"], 1):
        c = row["chapter"]
        name = f"chapter-{i:06}.xhtml"
        content = chapter_body(row)
        if c["volume"] != last:
            groups.append([volume_label(c), []])
            content = f'<h1>{escape(volume_label(c))}</h1>' + content
            last = c["volume"]
        files[name] = document(chapter_label(c), content)
        groups[-1][1].append(f'<li><a href="{name}">{escape(chapter_label(c))}</a></li>')
        manifest.append(f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
        ncx.append(f'<navPoint id="c{i}" playOrder="{i}"><navLabel><text>{escape(chapter_label(c))}</text></navLabel><content src="{name}"/></navPoint>')
    front_nav = '<li><a href="cover.xhtml#synopsis">Synopsis</a></li>' if book.get("synopsis") else ""
    nav = '<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>' + front_nav + "".join('<li><span>' + escape(label) + '</span><ol>' + "".join(items) + '</ol></li>' for label, items in groups) + '</ol></nav>'
    files["nav.xhtml"] = document("Contents", nav, epub=True)
    files["toc.ncx"] = f'<?xml version="1.0" encoding="utf-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="{uid}"/></head><docTitle><text>{escape(book["title"])}</text></docTitle><navMap>{"".join(ncx)}</navMap></ncx>'
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files["content.opf"] = f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="book-id">{uid}</dc:identifier><dc:title>{escape(book["title"])}</dc:title><dc:creator>{escape(book["author"])}</dc:creator><dc:language>en</dc:language><dc:description>{escape(chr(10).join(book.get("synopsis", [])))}</dc:description><dc:source>{escape(book["url"])}</dc:source><meta property="dcterms:modified">{modified}</meta></metadata><manifest>{"".join(manifest)}</manifest><spine toc="ncx">{"".join(spine)}</spine></package>'
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        for name, content in files.items():
            z.writestr("OEBPS/" + name, content)
    temp.replace(path)
    return path


def export_pdf(book, path):
    from playwright.sync_api import sync_playwright
    from .platform_support import configure_runtime
    configure_runtime()
    path = Path(path).resolve()
    html_path = export_html(book, path.with_suffix(".html"))
    temp = path.with_suffix(".pdf.tmp")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, timeout=30000)
        except Exception as exc:
            raise RuntimeError("The PDF engine could not start. For a standalone app, download a fresh copy of the complete package. For a source checkout, run Setup.cmd or install the Playwright Chromium headless shell. Linux also needs the system libraries listed in PACKAGING.md.") from exc
        try:
            page = browser.new_page()
            page.goto(html_path.as_uri(), wait_until="load")
            page.pdf(path=str(temp), prefer_css_page_size=True, print_background=True,
                display_header_footer=True, header_template="<span></span>",
                footer_template='<div style="width:100%;text-align:center;font:9px Georgia;color:#777"><span class="pageNumber"></span></div>')
        finally:
            browser.close()
    temp.replace(path)
    return path


def export_book(library, slug, formats=("epub",), output=None):
    book = library.book(slug)
    root = Path(output) if output else library.root.parent / "output" / slug
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for fmt in formats:
        exporter = {"epub": export_epub, "html": export_html, "pdf": export_pdf}[fmt]
        result.append(exporter(book, root / f"{slug}.{fmt}"))
    # A transparent inventory of included chapters and any download failures.
    report = {"novel": book["title"], "source": book["url"], **book["summary"],
              "included": [r["url"] for r in book["chapters"]],
              "not_downloaded": [{"url": r["url"], "error": r["error"]} for r in library.chapters(slug) if not r["html"]]}
    (root / "archive-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
