from __future__ import annotations

import re
from datetime import date
from email.utils import parsedate_to_datetime

from .article import ArchivedArticleError, fetch_article_text
from .models import DigestItem


MARKETING_TERMS = [
    "全球首个",
    "行业领先",
    "重磅发布",
    "赋能",
    "生态",
    "标杆",
    "突破性",
    "革命性",
    "第一",
    "唯一",
    "AI+",
]

OFFICIAL_SOURCE_TERMS = ["新华社", "新华网", "NRK"]
COMMENT_SOURCE_TERMS = ["观点", "评论"]
COMPANY_TERMS = ["发布会", "峰会", "白皮书", "品牌", "公司", "企业"]
NORWAY_HIGH_SIGNAL_TERMS = ["NATO", "EØS", "Forsvaret", "Norges Bank", "Stortinget", "regjering", "sikkerhet"]
ARCHIVED_ARTICLE_MARKER = "__ARCHIVED_OR_UNAVAILABLE_ARTICLE__"


def enrich_items(
    items: list[DigestItem],
    target_date: date,
    article_cache: dict[str, object] | None = None,
    max_article_fetches: int = 40,
) -> list[DigestItem]:
    fetch_budget = build_fetch_budget(items, max_article_fetches)
    fetched_by_stream = {"china-ai-policy": 0, "norway-nato-eos": 0}
    enriched: list[DigestItem] = []
    for item in items:
        stream = item.stream or "china-ai-policy"
        should_fetch_for_summary = fetched_by_stream.get(stream, 0) < fetch_budget.get(stream, 0)
        should_validate = requires_original_validation(item)
        if should_fetch_for_summary or should_validate:
            item.article_text = get_article_text(
                item.link,
                article_cache,
                refresh_empty=should_validate,
            )
            if should_fetch_for_summary:
                fetched_by_stream[stream] = fetched_by_stream.get(stream, 0) + 1
        if is_unreadable_original(item):
            continue
        enrich_item(item, target_date)
        enriched.append(item)
    items[:] = enriched
    return items


def build_fetch_budget(items: list[DigestItem], max_article_fetches: int) -> dict[str, int]:
    if max_article_fetches <= 0:
        return {}
    china_count = sum(1 for item in items if item.stream != "norway-nato-eos")
    norway_count = sum(1 for item in items if item.stream == "norway-nato-eos")
    if china_count and norway_count:
        norway_quota = min(norway_count, max(1, max_article_fetches // 3))
        china_quota = min(china_count, max_article_fetches - norway_quota)
        spare = max_article_fetches - norway_quota - china_quota
        if spare > 0:
            if china_count > china_quota:
                china_quota += min(spare, china_count - china_quota)
            elif norway_count > norway_quota:
                norway_quota += min(spare, norway_count - norway_quota)
        return {"china-ai-policy": china_quota, "norway-nato-eos": norway_quota}
    if norway_count:
        return {"norway-nato-eos": min(norway_count, max_article_fetches)}
    return {"china-ai-policy": min(china_count, max_article_fetches)}


def get_article_text(
    url: str,
    article_cache: dict[str, object] | None,
    refresh_empty: bool = False,
) -> str:
    if article_cache is not None:
        cached = article_cache.get(url)
        if isinstance(cached, str) and (cached or not refresh_empty):
            return cached
    try:
        text = fetch_article_text(url)
    except ArchivedArticleError:
        text = ARCHIVED_ARTICLE_MARKER
    except Exception:
        text = ""
    if article_cache is not None:
        article_cache[url] = text
    return text


def requires_original_validation(item: DigestItem) -> bool:
    return "新华网" in item.source or "news.cn" in item.link or "xinhuanet.com" in item.link


def is_unreadable_original(item: DigestItem) -> bool:
    return item.article_text == ARCHIVED_ARTICLE_MARKER or (
        requires_original_validation(item) and not item.article_text.strip()
    )


def enrich_item(item: DigestItem, target_date: date) -> None:
    content = item.article_text or item.summary
    item.chinese_title = build_chinese_title(item)
    item.brief = summarize_item(item, content)
    item.importance = build_importance(item)
    item.credibility = assess_credibility(item)
    item.claim_check = build_claim_check(item, content)
    item.judge, item.judge_reason = judge_item(item, content, target_date)


def build_chinese_title(item: DigestItem) -> str:
    if item.stream != "norway-nato-eos":
        return item.title
    if any(term in item.title for term in NORWAY_HIGH_SIGNAL_TERMS):
        return f"挪威公共事务线索：{item.title}"
    return f"挪威新闻线索：{item.title}"


def summarize_item(item: DigestItem, content: str) -> str:
    if content:
        sentences = split_sentences(content)
        if sentences:
            summary = " ".join(sentences[:2])
            return summary[:260]

    title = item.title.rstrip("。")
    if item.stream == "norway-nato-eos":
        keywords = "、".join((item.ai_keywords + item.policy_keywords)[:4])
        return f"这条 VG/NRK 新闻主要涉及“{title}”。相关线索包括：{keywords or '挪威公共事务'}。"

    topic = infer_china_topic(item)
    keywords = "、".join((item.ai_keywords + item.policy_keywords)[:4])
    return f"这条中文新闻主要讲“{title}”。它被归入{topic}，命中线索包括：{keywords or item.category}。"


def split_sentences(content: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])\s+", content)
    clean = []
    for part in parts:
        part = clean_noise_prefix(part.strip())
        if 20 <= len(part) <= 260:
            clean.append(part)
    return clean


def clean_noise_prefix(value: str) -> str:
    value = re.sub(r"^\d{1,2}:\d{2}\s+", "", value)
    value = re.sub(r"^(Nyhetssenter|Politi- og brannloggen)\s+[\wÆØÅæøå -]*\s+", "", value)
    return value.strip()


def build_importance(item: DigestItem) -> str:
    if item.stream == "norway-nato-eos":
        if any(key in item.title for key in NORWAY_HIGH_SIGNAL_TERMS):
            return "这条可能影响对挪威安全、国防、经济或欧洲制度关系的观察，适合进入每日挪威/NATO/EØS跟踪。"
        return "这条属于挪威公共新闻，可作为理解当地政治、经济和社会运行状态的背景信号。"

    if any(key in item.ai_keywords for key in ["大模型", "人工智能", "机器人", "算力", "数据中心"]):
        return "这条可能影响对技术趋势、产业落地或政策环境的判断，适合继续跟踪原文和相关政策背景。"
    if item.category in {"国内时政", "国际时政"}:
        return "这条提供政策或国际环境信号，适合和产业、监管或跨境业务风险一起观察。"
    return "这条提供产业或政策背景，可作为后续人工阅读和交叉验证入口。"


def assess_credibility(item: DigestItem) -> str:
    if any(term in item.source for term in OFFICIAL_SOURCE_TERMS):
        return "来源为官方或公共媒体，适合引用事实线索；仍需区分新闻事实、政策表述和评论判断。"
    if "VG" in item.source:
        return "来源为挪威商业媒体 VG，适合跟踪公共议题和突发新闻；重要判断建议和 NRK 或官方来源交叉核对。"
    if "环球网" in item.source:
        return "来源为中文媒体频道页，适合做议题线索；涉及企业宣传或国际判断时建议交叉验证。"
    if "参考消息" in item.source:
        return "来源为参考消息，常见内容来自外媒编译和国际议题观察；适合做线索入口，关键事实仍建议回到原文和多源核查。"
    return "来源可信度需结合原文和其他来源进一步判断。"


def build_claim_check(item: DigestItem, content: str) -> str:
    text = f"{item.title} {content}"
    marketing_hits = [term for term in MARKETING_TERMS if term.lower() in text.lower()]
    company_hits = [term for term in COMPANY_TERMS if term in text]
    if marketing_hits:
        return "可能含宣传性表述：" + "、".join(marketing_hits[:4]) + "。建议查看原文是否给出第三方数据或官方依据。"
    if company_hits and item.category == "AI产业":
        return "可能是企业/产业稿。可作为动态线索，但不宜直接当作技术结论。"
    if any(term in item.source for term in COMMENT_SOURCE_TERMS):
        return "这更像观点/评论，应和事实报道分开使用。"
    return "未发现明显营销化或高风险断言；仍建议点击原文核对上下文。"


def judge_item(item: DigestItem, content: str, target_date: date) -> tuple[str, str]:
    text = f"{item.title} {content}"
    item_date = parse_item_date(item.published)
    if item_date and item_date != target_date:
        return "review", "发布日期不完全等于目标日期，需要人工确认是否应进入当日简报。"
    if item.stream == "norway-nato-eos":
        if any(key in text for key in ["Norge", "Noreg", "Norges", "NATO", "EØS", "Forsvaret", "Stortinget", "Norges Bank"]):
            return "keep", "命中挪威/NATO/EØS核心线索。"
        return "review", "只命中弱公共新闻线索，建议人工复核。"
    if item.ai_keywords and item.policy_keywords:
        return "keep", "同时命中 AI/产业线索和政策/时政线索。"
    if item.category in {"国内时政", "国际时政"} and item.policy_keywords:
        return "keep", "纯时政条目命中政策/国际关系线索。"
    return "review", "命中关键词较少，建议人工复核相关性。"


def parse_item_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            from datetime import datetime

            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return None


def infer_china_topic(item: DigestItem) -> str:
    if item.category == "AI产业":
        return "AI产业/科技动态"
    if item.category == "国内时政":
        return "国内时政"
    if item.category == "国际时政":
        return "国际时政"
    if item.category == "评论":
        return "观点评论"
    return item.category
