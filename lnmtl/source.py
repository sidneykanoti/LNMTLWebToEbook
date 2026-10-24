"""Read public LNMTL pages without executing their scripts."""
import base64
import json
import re
import threading
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://lnmtl.com"


class Stopped(Exception):
    pass


class AccessBlocked(Exception):
    pass


def novel_url(value):
    value = value.strip()
    if "://" not in value:
        value = BASE + "/novel/" + value
    p = urlparse(value)
    if p.scheme != "https" or p.hostname != "lnmtl.com" or not re.fullmatch(r"/novel/[a-zA-Z0-9-]+/?", p.path):
        raise ValueError("Enter an LNMTL novel URL or its short name, such as against-the-gods.")
    return BASE + p.path.rstrip("/")


def embedded_json(html, name):
    match = re.search(r"lnmtl\." + re.escape(name) + r"\s*=\s*", html)
    if not match:
        raise ValueError(f"LNMTL did not provide {name}. The page format may have changed.")
    return json.JSONDecoder().raw_decode(html[match.end():])[0]


def novel_details(soup, url):
    description = soup.select_one(".description")
    synopsis = []
    source = description.select_one(".source") if description else None
    synopsis_source = source.get_text(" ", strip=True) if source else ""
    if description:
        for unwanted in description.select("script, style, iframe, .source"):
            unwanted.decompose()
        paragraphs = description.find_all("p")
        synopsis = [p.get_text(" ", strip=True) for p in paragraphs] if paragraphs else [description.get_text("\n", strip=True)]
    image = soup.select_one(".media-left img[src], .media img.media-object[src]")
    return {"synopsis": [p for p in synopsis if p], "synopsis_source": synopsis_source,
            "poster_url": urljoin(url, image["src"]) if image else ""}


def poster_type(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    raise ValueError("Poster is not a supported JPEG, PNG, or GIF image")


class Client:
    def __init__(self, delay=2.0, stop=None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "LNMTL-Local-Archive/0.1 (personal offline reading)", "Accept": "text/html,application/json"})
        self.delay = max(1.0, delay)
        self.last_request = 0
        self.stop = stop or threading.Event()

    def check(self):
        if self.stop.is_set():
            raise Stopped("Paused. Saved chapters are safe; resume to continue.")

    def get(self, url, **kwargs):
        p = urlparse(url)
        if p.scheme != "https" or p.hostname != "lnmtl.com":
            raise ValueError("Only HTTPS links on lnmtl.com are accepted.")
        for attempt in range(3):
            self.check()
            wait = max(0, self.delay - (time.monotonic() - self.last_request))
            if self.stop.wait(wait):
                self.check()
            try:
                self.last_request = time.monotonic()
                response = self.session.get(url, timeout=(15, 60), **kwargs)
                if response.status_code in (401, 403) or (not kwargs.get("stream") and "<title>Just a moment" in response.text):
                    raise AccessBlocked("LNMTL blocked this request. Downloads were stopped; try again later. No protection is bypassed.")
                if response.status_code == 429 or response.status_code >= 500:
                    if self.stop.wait(min(60, 5 * 2 ** attempt)):
                        self.check()
                    response.raise_for_status()
                response.raise_for_status()
                response.encoding = "utf-8"
                return response
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
                if attempt == 2:
                    raise
                if self.stop.wait(3 * (attempt + 1)):
                    self.check()

    def catalogue(self, report=lambda _: None):
        url = BASE + "/novel"
        visited, novels = set(), {}
        while url:
            self.check()
            if url in visited:
                raise ValueError("The catalogue repeated a page; collection stopped to avoid an incomplete list.")
            visited.add(url)
            soup = BeautifulSoup(self.get(url).text, "html.parser")
            links = soup.select("h4 a[href]")
            if not links:
                raise ValueError("No novels found on this catalogue page.")
            for a in links:
                link = novel_url(urljoin(BASE, a["href"]))
                novels[link] = {"url": link, "title": a.get_text(" ", strip=True)}
            report(f"Catalogue page {len(visited)}: {len(novels)} novels found")
            next_link = soup.select_one('a[rel="next"]')
            if not next_link:
                next_link = next((a for a in soup.select('.pagination a[href]') if a.get_text(strip=True) in ("»", "Next", "›")), None)
            url = urljoin(BASE, next_link["href"]) if next_link else None
        return list(novels.values())

    def discover(self, value, report=lambda _: None):
        url = novel_url(value)
        html = self.get(url).text
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.select_one("h2")
        if not heading:
            raise ValueError("This page has no novel title.")
        volumes = embedded_json(html, "volumes")
        # The first response belongs to the first volume. Other volumes must be requested explicitly.
        first = embedded_json(html, "firstResponse") if volumes else None
        author = soup.select_one('a[href*="author="]')
        if not author:
            author = next((d.find_next_sibling("dd") for d in soup.select("dt") if "Authors" in d.get_text()), None)
        novel = {"url": url, "slug": url.rsplit("/", 1)[-1], "title": heading.get_text(" ", strip=True),
                 "author": author.get_text(" ", strip=True) if author else "Unknown", "volumes": volumes, "chapters": []}
        novel.update(novel_details(soup, url))
        if novel["poster_url"]:
            try:
                response = self.get(novel["poster_url"], stream=True)
                try:
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        self.check()
                        data.extend(chunk)
                        if len(data) > 10 * 1024 * 1024:
                            raise ValueError("Poster exceeds 10 MB")
                    mime = poster_type(data)
                    novel["poster"] = {"mime": mime, "data": base64.b64encode(data).decode("ascii")}
                finally:
                    response.close()
            except (Stopped, AccessBlocked):
                raise
            except (requests.RequestException, ValueError) as exc:
                report(f"Poster unavailable; continuing without a new poster: {exc}")
        seen = set()
        for vi, volume in enumerate(volumes):
            page, last, count, expected = 1, 1, 0, None
            while page <= last:
                self.check()
                payload = first if vi == 0 and page == 1 else self.get(BASE + "/chapter", params={"volumeId": volume["id"], "page": page}, headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}).json()
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                    raise ValueError("Unexpected chapter-list response.")
                if int(payload["current_page"]) != page:
                    raise ValueError("LNMTL returned the wrong chapter page.")
                last = int(payload["last_page"])
                expected = int(payload["total"])
                for chapter in payload["data"]:
                    if int(chapter["volume_id"]) != int(volume["id"]):
                        raise ValueError("Chapter list belongs to a different volume.")
                    link = chapter["site_url"]
                    if link in seen:
                        raise ValueError("Duplicate chapter link in the source index. Refresh the index later.")
                    seen.add(link)
                    novel["chapters"].append({"url": link, "title": chapter["title"] or "Untitled", "number": chapter["number"],
                        "part": chapter.get("part"), "special": bool(chapter.get("is_special")), "volume": volume["number"],
                        "volume_title": volume.get("title") or "", "position": chapter.get("position"), "ordinal": len(seen)})
                    count += 1
                report(f"Volume {volume['number']}, page {page}/{last}: {len(seen)} chapters indexed")
                page += 1
            if count != expected:
                raise ValueError(f"Volume {volume['number']} has {count} indexed chapters, but LNMTL reports {expected}. Try refreshing.")
        return novel


def clean_chapter(html):
    """Convert LNMTL inline tokens to safe, portable XHTML, preserving whitespace."""
    from html import escape
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".chapter-body")
    sentences = body.select("sentence.translated") if body else []
    if not sentences:
        raise ValueError("No English chapter paragraphs found; the response was not saved as a chapter.")

    def render(node):
        if isinstance(node, NavigableString):
            return escape(re.sub(r"\s+", " ", str(node)))
        if not isinstance(node, Tag) or node.name in ("script", "style", "iframe"):
            return ""
        content = "".join(render(c) for c in node.children)
        if node.name == "t":
            return '<span class="term">' + content + '</span>'
        if node.name == "w" and "postfixed" in node.get("class", []):
            return '<span class="modified">' + content + '</span>'
        mapped = {"dq": "em", "sq": "strong", "da": "b", "i": "em", "b": "b", "em": "em", "strong": "strong", "sup": "sup", "sub": "sub"}
        if node.name in mapped:
            tag = mapped[node.name]
            return f"<{tag}>{content}</{tag}>"
        if node.name == "br":
            return "<br />"
        # Keep safe inline colors/emphasis when LNMTL supplies explicit formatting.
        styles = []
        for prop, val in re.findall(r"([\w-]+)\s*:\s*([^;]+)", node.get("style", "")):
            if prop == "color" and re.fullmatch(r"#[0-9a-fA-F]{3,8}|[a-zA-Z]+|rgba?\([0-9., %]+\)", val.strip()):
                styles.append(f"color:{val.strip()}")
            if prop in ("font-style", "font-weight") and re.fullmatch(r"italic|normal|bold|[1-9]00", val.strip()):
                styles.append(f"{prop}:{val.strip()}")
        return '<span style="' + ";".join(styles) + '">' + content + '</span>' if styles else content

    paragraphs = ["<p>" + "".join(render(c) for c in s.children).strip() + "</p>" for s in sentences]
    result = "\n".join(paragraphs)
    if len(BeautifulSoup(result, "html.parser").get_text(strip=True)) < 20:
        raise ValueError("Chapter text is unexpectedly empty.")
    return result
