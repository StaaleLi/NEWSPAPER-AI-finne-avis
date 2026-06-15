from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser

from .models import DigestItem, Source


USER_AGENT = "Mozilla/5.0 newslens-daily-cn/0.1"


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._href: str | None = None
        self._text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self._href = urllib.parse.urljoin(self.base_url, href)
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        text = normalize_text(" ".join(self._text_parts))
        if text and len(text) >= 6:
            self.links.append((text, self._href))
        self._href = None
        self._text_parts = []


def fetch_source(source: Source, limit: int = 80) -> list[DigestItem]:
    if source.source_type == "rss":
        return fetch_rss(source, limit)
    if source.source_type == "html":
        return fetch_html(source, limit)
    if source.source_type == "cankaoxiaoxi":
        return fetch_cankaoxiaoxi_json(source, limit)
    raise ValueError(f"Unsupported source type: {source.source_type}")


def fetch_rss(source: Source, limit: int = 80) -> list[DigestItem]:
    content = fetch_text(source.url)
    root = ET.fromstring(content)
    items: list[DigestItem] = []
    for node in root.findall(".//item")[:limit]:
        title = normalize_text(node.findtext("title") or "")
        link = normalize_text(node.findtext("link") or "")
        published = normalize_text(node.findtext("pubDate") or "")
        summary = strip_html(node.findtext("description") or "")[:240]
        if title and link:
            items.append(
                DigestItem(
                    title=title,
                    link=link,
                    source=source.name,
                    category=source.category,
                    published=published,
                    summary=summary,
                )
            )
    return items


def fetch_html(source: Source, limit: int = 80) -> list[DigestItem]:
    content = fetch_text(source.url)
    if "huanqiu.com" in urllib.parse.urlparse(source.url).netloc:
        hidden_items = fetch_huanqiu_hidden_items(source, content, limit)
        if hidden_items:
            return hidden_items
        return parse_anchor_items(source, content, limit)
    return parse_anchor_items(source, content, limit)


def fetch_cankaoxiaoxi_json(source: Source, limit: int = 80) -> list[DigestItem]:
    payload = json.loads(fetch_text(source.url))
    raw_items = payload.get("list", [])
    if not isinstance(raw_items, list):
        return []

    alias = source.url.rstrip("/").split("/")[-2] if "/channel/" in source.url else ""
    items: list[DigestItem] = []
    seen: set[str] = set()
    for raw in raw_items[:limit]:
        if not isinstance(raw, dict):
            continue
        data = raw.get("data", raw)
        if not isinstance(data, dict):
            continue
        article_id = str(data.get("id", "")).strip()
        title = normalize_text(str(data.get("shorttitle") or data.get("title") or ""))
        if not article_id or not title or article_id in seen:
            continue
        seen.add(article_id)
        content_type = str(data.get("contentType") or 1)
        published = normalize_text(str(data.get("publishTime") or data.get("createtime") or ""))
        create_date = normalize_cankaoxiaoxi_date(str(data.get("createtime") or published))
        link = build_cankaoxiaoxi_link(alias, article_id, content_type, create_date)
        summary = normalize_text(str(data.get("description") or data.get("keyword") or ""))
        items.append(
            DigestItem(
                title=title,
                link=link,
                source=source.name,
                category=source.category,
                published=published,
                summary=summary[:240],
            )
        )
    return items


def normalize_cankaoxiaoxi_date(value: str) -> str:
    if re.match(r"20\d{2}-\d{2}-\d{2}", value):
        return value[:10]
    return ""


def build_cankaoxiaoxi_link(alias: str, article_id: str, content_type: str, create_date: str) -> str:
    if alias and create_date:
        return f"https://www.cankaoxiaoxi.com/#/detailsPage/{alias}/{article_id}/{content_type}/{create_date}"
    return f"https://www.cankaoxiaoxi.com/#/detailsPage/{article_id}"


def parse_anchor_items(source: Source, content: str, limit: int = 80) -> list[DigestItem]:
    parser = LinkParser(source.url)
    parser.feed(content)
    items: list[DigestItem] = []
    seen: set[str] = set()
    for title, link in parser.links:
        if link in seen or not is_probable_news_link(link, source.url):
            continue
        seen.add(link)
        items.append(
            DigestItem(
                title=title,
                link=link,
                source=source.name,
                category=source.category,
                published=extract_date_from_url(link),
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_huanqiu_hidden_items(source: Source, content: str, limit: int = 80) -> list[DigestItem]:
    items: list[DigestItem] = []
    seen: set[str] = set()
    for block in re.findall(r'<div class="item">(.*?)</div>', content, flags=re.DOTALL):
        title = extract_textarea(block, "item-title")
        aid = extract_textarea(block, "item-aid")
        host = extract_textarea(block, "item-cnf-host") or urllib.parse.urlparse(source.url).netloc
        addltype = extract_textarea(block, "item-addltype") or "article"
        timestamp = extract_textarea(block, "item-time")
        if not title or not aid or aid in seen:
            continue
        seen.add(aid)
        path = "gallery" if addltype == "gallery" else "article"
        published = timestamp_to_date(timestamp)
        items.append(
            DigestItem(
                title=normalize_text(title),
                link=f"https://{host}/{path}/{aid}",
                source=source.name,
                category=source.category,
                published=published,
            )
        )
        if len(items) >= limit:
            break
    return items


def extract_textarea(block: str, class_name: str) -> str:
    match = re.search(
        rf'<textarea class="{re.escape(class_name)}">(.*?)</textarea>',
        block,
        flags=re.DOTALL,
    )
    if not match:
        return ""
    return normalize_text(match.group(1))


def timestamp_to_date(value: str) -> str:
    if not value or not value.isdigit():
        return ""
    try:
        stamp = int(value)
        if stamp > 10_000_000_000:
            stamp = stamp / 1000
        return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return ""


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20, context=context) as response:
                raw = response.read()
                charset = response.headers.get_content_charset()
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500 and exc.code != 429:
                raise
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"failed to fetch after retries: {last_error}")
    for encoding in [charset, "utf-8", "gb18030", "gbk"]:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return normalize_text(text)


def is_probable_news_link(link: str, source_url: str = "") -> bool:
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme not in {"http", "https"}:
        return False
    source_host = urllib.parse.urlparse(source_url).netloc
    if source_host and not same_site(parsed.netloc, source_host):
        return False
    if is_non_article_news_link(parsed):
        return False
    return bool(re.search(r"\d|/n1/|/article/|/c\.html$|/c/", parsed.path))


def is_non_article_news_link(parsed: urllib.parse.ParseResult) -> bool:
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if not (host.endswith("news.cn") or host.endswith("xinhuanet.com")):
        return False
    return path.startswith("/zt/") or "/zt/" in path or path.startswith("/talking/")


def same_site(link_host: str, source_host: str) -> bool:
    link_parts = link_host.lower().split(".")
    source_parts = source_host.lower().split(".")
    if len(link_parts) < 2 or len(source_parts) < 2:
        return link_host.lower() == source_host.lower()
    return link_parts[-2:] == source_parts[-2:]


def extract_date_from_url(link: str) -> str:
    match = re.search(r"/(20\d{2})(\d{2})(\d{2})/", link)
    if match:
        return "-".join(match.groups())
    match = re.search(r"/(20\d{2})-(\d{2})/(\d{2})/", link)
    if match:
        return "-".join(match.groups())
    match = re.search(r"/(20\d{2})-(\d{2})-(\d{2})/", link)
    if match:
        return "-".join(match.groups())
    return ""
