from __future__ import annotations

import html
import re

from .fetchers import fetch_text, normalize_text, strip_html


class ArchivedArticleError(RuntimeError):
    """Raised when a source page is an archive/unavailable notice, not an article."""


ARCHIVED_PAGE_MARKERS = [
    "您查看的内容已过期归档",
    "内容已过期归档",
    "已过期归档",
    "快速进入新华网首页",
]


def fetch_article_text(url: str, max_chars: int = 6000) -> str:
    content = fetch_text(url)
    if is_archived_or_unavailable_page(content):
        raise ArchivedArticleError("article page is archived or unavailable")
    text = extract_article_text(content)
    return text[:max_chars]


def is_archived_or_unavailable_page(content: str) -> bool:
    if any(marker in content for marker in ARCHIVED_PAGE_MARKERS):
        return True
    visible_text = normalize_text(strip_html(html.unescape(content)))
    return any(marker in visible_text for marker in ARCHIVED_PAGE_MARKERS)


def extract_article_text(content: str) -> str:
    content = re.sub(r"(?is)<script.*?</script>", " ", content)
    content = re.sub(r"(?is)<style.*?</style>", " ", content)
    content = re.sub(r"(?is)<noscript.*?</noscript>", " ", content)

    meta = extract_meta_description(content)
    paragraphs = re.findall(r"(?is)<p[^>]*>(.*?)</p>", content)
    paragraph_text = [strip_html(html.unescape(p)) for p in paragraphs]
    paragraph_text = [p for p in paragraph_text if is_informative_paragraph(p)]

    if paragraph_text:
        return normalize_text(" ".join(paragraph_text))
    if meta and is_informative_paragraph(meta):
        return meta

    body = re.search(r"(?is)<body[^>]*>(.*?)</body>", content)
    fallback = body.group(1) if body else content
    fallback_text = normalize_text(strip_html(html.unescape(fallback)))
    return fallback_text if is_informative_paragraph(fallback_text) else ""


def extract_meta_description(content: str) -> str:
    patterns = [
        r'(?is)<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        r'(?is)<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']',
        r'(?is)<meta\s+content=["\'](.*?)["\']\s+name=["\']description["\']',
        r'(?is)<meta\s+content=["\'](.*?)["\']\s+property=["\']og:description["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return normalize_text(html.unescape(match.group(1)))
    return ""


def is_informative_paragraph(value: str) -> bool:
    value = normalize_text(value)
    if len(value) < 18:
        return False
    if re.match(r"^\d{1,2}:\d{2}\s+(Nyhetssenter|Politi- og brannloggen)\b", value):
        return False
    if re.match(r"^\d{1,2}:\d{2}\s+[\wÆØÅæøå -]{2,40}\s+[A-ZÆØÅ]", value):
        return False
    noisy = [
        "责任编辑",
        "Copyright",
        "版权所有",
        "扫一扫",
        "下载客户端",
        "分享来自参考消息客户端",
        "Nyhetssenter",
        "Politi- og brannloggen",
    ]
    return not any(token in value for token in noisy)
