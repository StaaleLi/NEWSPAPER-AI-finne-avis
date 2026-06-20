from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .fetchers import fetch_text, normalize_text, strip_html


class ArchivedArticleError(RuntimeError):
    """Raised when a source page is an archive/unavailable notice, not an article."""


@dataclass(frozen=True)
class ArticleTextResult:
    text: str
    status: str
    note: str = ""


ARCHIVED_PAGE_MARKERS = [
    "您查看的内容已过期归档",
    "内容已过期归档",
    "已过期归档",
    "快速进入新华网首页",
]

CONTENT_CONTAINER_MARKERS = (
    "article-content",
    "article_content",
    "articlecontent",
    "articletext",
    "article-text",
    "text-content",
    "content-main",
    "main-content",
)
REPEATED_TEMPLATE_TERMS = ("新闻摘要",)


def fetch_article_text(url: str, max_chars: int = 6000) -> str:
    return fetch_article_result(url, max_chars).text


def fetch_article_result(url: str, max_chars: int = 6000) -> ArticleTextResult:
    content = fetch_text(url)
    if is_archived_or_unavailable_page(content):
        raise ArchivedArticleError("article page is archived or unavailable")
    result = extract_article_text_result(content)
    return ArticleTextResult(result.text[:max_chars], result.status, result.note)


def is_archived_or_unavailable_page(content: str) -> bool:
    if any(marker in content for marker in ARCHIVED_PAGE_MARKERS):
        return True
    visible_text = normalize_text(strip_html(html.unescape(content)))
    return any(marker in visible_text for marker in ARCHIVED_PAGE_MARKERS)


def extract_article_text(content: str) -> str:
    return extract_article_text_result(content).text


def extract_article_text_result(content: str) -> ArticleTextResult:
    content = re.sub(r"(?is)<script.*?</script>", " ", content)
    content = re.sub(r"(?is)<style.*?</style>", " ", content)
    content = re.sub(r"(?is)<noscript.*?</noscript>", " ", content)

    meta = extract_meta_description(content)
    for container in extract_primary_content_containers(content):
        text, cleaned_templates = extract_paragraph_text(container)
        if is_usable_article_text(text):
            note = "removed repeated template text" if cleaned_templates else ""
            status = "cleaned" if cleaned_templates else "ok"
            return ArticleTextResult(text, status, note)

    text, cleaned_templates = extract_paragraph_text(content)
    if is_usable_article_text(text):
        note = "removed repeated template text" if cleaned_templates else "used page-wide paragraph fallback"
        status = "cleaned" if cleaned_templates else "fallback"
        return ArticleTextResult(text, status, note)
    if meta and is_informative_paragraph(meta):
        return ArticleTextResult(meta, "fallback", "used page metadata because no readable article body was found")

    body = re.search(r"(?is)<body[^>]*>(.*?)</body>", content)
    fallback = body.group(1) if body else content
    fallback_text = normalize_text(strip_html(html.unescape(fallback)))
    if is_usable_article_text(fallback_text):
        return ArticleTextResult(fallback_text, "fallback", "used page text because no readable article body was found")
    return ArticleTextResult("", "low_quality", "no readable article text after boilerplate filtering")


def extract_primary_content_containers(content: str) -> list[str]:
    containers: list[str] = []
    for match in re.finditer(r"(?is)<(?P<tag>article|div)\b(?P<attrs>[^>]*)>", content):
        attrs = match.group("attrs").lower()
        if not any(marker in attrs for marker in CONTENT_CONTAINER_MARKERS):
            continue
        container = extract_balanced_element(content, match.start(), match.group("tag"))
        if container:
            containers.append(container)
    return containers


def extract_balanced_element(content: str, start: int, tag: str) -> str:
    depth = 0
    pattern = re.compile(rf"(?is)</?{re.escape(tag)}\b[^>]*>")
    for match in pattern.finditer(content, start):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return content[start : match.end()]
        elif not token.rstrip().endswith("/>"):
            depth += 1
    return ""


def extract_paragraph_text(content: str) -> tuple[str, bool]:
    seen: set[str] = set()
    cleaned_templates = False
    paragraphs: list[str] = []
    for raw in re.findall(r"(?is)<p[^>]*>(.*?)</p>", content):
        value = strip_html(html.unescape(raw))
        value, was_cleaned = remove_repeated_template_text(value)
        cleaned_templates = cleaned_templates or was_cleaned
        if not is_informative_paragraph(value):
            continue
        normalized = normalize_text(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        paragraphs.append(normalized)
    return normalize_text(" ".join(paragraphs)), cleaned_templates


def remove_repeated_template_text(value: str) -> tuple[str, bool]:
    changed = False
    for term in REPEATED_TEMPLATE_TERMS:
        pattern = rf"(?:{re.escape(term)}[\s\u3000]*){{2,}}"
        value, replacements = re.subn(pattern, "", value)
        changed = changed or replacements > 0
    return normalize_text(value), changed


def is_usable_article_text(value: str) -> bool:
    return len(normalize_text(value)) >= 60 and is_informative_paragraph(value)


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
