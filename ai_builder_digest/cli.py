from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .classifier import classify_item
from .enrich import enrich_items
from .fetchers import fetch_source, is_probable_news_link
from .llm import llm_enrich_items, llm_translate_items
from .logging_utils import configure_logging, get_logger
from .models import DigestItem, Source, SourceAudit
from .render import render_archive, render_html
from .sources import SOURCES
from .storage import load_recent_items, save_run


LOGGER = get_logger(__name__)


def build_digest(
    limit_per_source: int = 80,
    max_items: int = 80,
    max_age_days: int = 730,
    date_window_days: int = 0,
    target_date: date | None = None,
    cache: dict[str, object] | None = None,
    cache_ttl_minutes: int = 60,
) -> tuple[list[DigestItem], list[SourceAudit]]:
    target_date = target_date or datetime.now().date()
    selected: list[DigestItem] = []
    audits: list[SourceAudit] = []
    for source in SOURCES:
        audit = SourceAudit(source.name, source.url, source.region, "ok")
        try:
            raw_items, used_cache = fetch_source_with_cache(source, limit_per_source, cache, cache_ttl_minutes)
        except Exception as exc:
            audit.status = "failed"
            audit.error = str(exc)
            audit.notes.append("source fetch failed; coverage is incomplete")
            audits.append(audit)
            LOGGER.warning("%s failed: %s", source.name, exc)
            continue
        if used_cache:
            audit.notes.append("used cached source response")
        audit.total_fetched = len(raw_items)
        audit.today_count = count_items_on_date(raw_items, target_date, source.region)
        audit.dated_count = count_dated_items(raw_items, source.region)
        audit.newest_published = newest_item_date(raw_items, source.region)
        audit.freshness_status = determine_freshness(audit, target_date)
        dated_count = audit.dated_count
        if source.source_type == "html" and dated_count == 0:
            audit.notes.append("html channel has no reliable per-item date; today coverage cannot be proven")
        elif source.source_type == "html" and dated_count < len(raw_items):
            audit.notes.append("some html items have no reliable date; daily completeness is partial")

        source_selected = 0
        fallback_selected = 0
        source_date_window_days = effective_date_window_days(source, date_window_days)
        for item in raw_items:
            if not is_probable_news_link(item.link, source.url):
                continue
            if is_too_old(item.published, max_age_days, source.region):
                continue
            if is_outside_date_window(item.published, target_date, source_date_window_days, source.region):
                continue
            classified = classify_item(item)
            if classified:
                selected.append(classified)
                source_selected += 1
                item_date = parse_date(item.published, source.region)
                if item_date and item_date.date() != target_date:
                    fallback_selected += 1
        audit.selected_count = source_selected
        audit.fallback_selected_count = fallback_selected
        if source_selected and source_date_window_days > date_window_days and audit.today_count == 0:
            audit.notes.append(
                f"used readable recent items within {source_date_window_days} day(s) because no target-date items were found"
            )
        if source.region == "CN":
            audit.notes.extend(china_coverage_notes(source.category, raw_items, source_selected, target_date, source.region))
        if source.region == "NO":
            audit.notes.extend(norway_coverage_notes(raw_items, source_selected, target_date, source.region))
        audits.append(audit)
    return dedupe_and_sort(selected)[:max_items], audits


def fetch_source_with_cache(
    source: Source,
    limit: int,
    cache: dict[str, object] | None,
    cache_ttl_minutes: int,
) -> tuple[list[DigestItem], bool]:
    key = source.url
    if cache is not None:
        cached = cache.get(key)
        if isinstance(cached, dict) and cache_is_fresh(str(cached.get("fetched_at", "")), cache_ttl_minutes):
            raw_items = cached.get("items", [])
            if isinstance(raw_items, list):
                return [item_from_dict(item) for item in raw_items if isinstance(item, dict)], True

    items = fetch_source(source, limit=limit)
    if cache is not None:
        cache[key] = {
            "source": source.name,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "items": [item.as_dict() for item in items],
        }
    return items, False


def effective_date_window_days(source: Source, requested_window_days: int) -> int:
    if source.name.startswith("新华网-"):
        return max(requested_window_days, 1)
    return requested_window_days


def cache_is_fresh(fetched_at: str, ttl_minutes: int) -> bool:
    if ttl_minutes <= 0:
        return False
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    return datetime.now() - fetched <= timedelta(minutes=ttl_minutes)


def item_from_dict(value: dict[str, object]) -> DigestItem:
    item = DigestItem(
        title=str(value.get("title", "")),
        link=str(value.get("link", "")),
        source=str(value.get("source", "")),
        category=str(value.get("category", "")),
        published=str(value.get("published", "")),
        summary=str(value.get("summary", "")),
    )
    item.ai_keywords = list(value.get("ai_keywords", [])) if isinstance(value.get("ai_keywords"), list) else []
    item.policy_keywords = (
        list(value.get("policy_keywords", [])) if isinstance(value.get("policy_keywords"), list) else []
    )
    item.stream = str(value.get("stream", "china-ai-policy"))
    item.score = int(value.get("score", 0)) if isinstance(value.get("score", 0), int) else 0
    item.reason = str(value.get("reason", ""))
    item.article_text = str(value.get("article_text", ""))
    item.article_quality_status = str(value.get("article_quality_status", "not_checked"))
    item.article_quality_note = str(value.get("article_quality_note", ""))
    item.chinese_title = str(value.get("chinese_title", ""))
    item.brief = str(value.get("brief", ""))
    item.importance = str(value.get("importance", ""))
    item.credibility = str(value.get("credibility", ""))
    item.claim_check = str(value.get("claim_check", ""))
    item.judge = str(value.get("judge", ""))
    item.judge_reason = str(value.get("judge_reason", ""))
    item.title_en = str(value.get("title_en", ""))
    item.brief_en = str(value.get("brief_en", ""))
    item.importance_en = str(value.get("importance_en", ""))
    item.reason_en = str(value.get("reason_en", ""))
    item.title_no = str(value.get("title_no", ""))
    item.brief_no = str(value.get("brief_no", ""))
    item.importance_no = str(value.get("importance_no", ""))
    item.reason_no = str(value.get("reason_no", ""))
    return item


def count_items_on_date(items: list[DigestItem], target_date: date, region: str = "") -> int:
    count = 0
    for item in items:
        parsed = parse_date(item.published, region)
        if parsed and parsed.date() == target_date:
            count += 1
    return count


def count_dated_items(items: list[DigestItem], region: str = "") -> int:
    return sum(1 for item in items if parse_date(item.published, region) is not None)


def newest_item_date(items: list[DigestItem], region: str = "") -> str:
    dates = [parsed.date() for item in items if (parsed := parse_date(item.published, region))]
    return max(dates).isoformat() if dates else ""


def determine_freshness(audit: SourceAudit, target_date: date) -> str:
    if audit.total_fetched == 0:
        return "empty"
    if audit.dated_count == 0:
        return "unknown"
    if audit.today_count > 0:
        return "current"
    if audit.newest_published:
        newest = date.fromisoformat(audit.newest_published)
        if newest == target_date - timedelta(days=1):
            return "recent"
    return "stale"


def china_coverage_notes(
    category: str, raw_items: list[DigestItem], selected_count: int, target_date: date, region: str = ""
) -> list[str]:
    notes: list[str] = []
    if category in {"国内时政", "国际时政", "AI产业"} and not raw_items:
        notes.append(f"required China channel {category} returned no items")
    if category in {"国内时政", "国际时政", "AI产业"} and selected_count == 0:
        notes.append(f"no selected items for required China channel {category}; review keywords or source")
    return notes


def norway_coverage_notes(
    raw_items: list[DigestItem], selected_count: int, target_date: date, region: str = ""
) -> list[str]:
    notes: list[str] = []
    if not raw_items:
        notes.append("required Norway source returned no items")
    if selected_count == 0:
        notes.append("no Norway/NATO/EØS items selected; inspect raw feed before assuming no news")
    return notes


def is_too_old(published: str, max_age_days: int, region: str = "") -> bool:
    if not published:
        return False
    parsed = parse_date(published, region)
    if parsed is None:
        return False
    return (datetime.now().date() - parsed.date()).days > max_age_days


def is_outside_date_window(published: str, target_date: date, date_window_days: int, region: str = "") -> bool:
    parsed = parse_date(published, region)
    if parsed is None:
        return False
    return abs((parsed.date() - target_date).days) > date_window_days


def parse_date(value: str, region: str = "") -> datetime | None:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed
        timezone = ZoneInfo("Europe/Oslo") if region == "NO" else ZoneInfo("Asia/Shanghai")
        return parsed.astimezone(timezone).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def dedupe_and_sort(items: list[DigestItem]) -> list[DigestItem]:
    by_link: dict[str, DigestItem] = {}
    for item in items:
        old = by_link.get(item.link)
        if old is None or item.score > old.score:
            by_link[item.link] = item
    stream_order = {"norway-nato-eos": 0, "china-ai-policy": 1}
    return sorted(
        by_link.values(),
        key=lambda item: (stream_order.get(item.stream, 9), -item.score, item.source, item.title),
    )


def record_article_quality(audits: list[SourceAudit], items: list[DigestItem]) -> None:
    by_source = {audit.name: audit for audit in audits}
    for item in items:
        audit = by_source.get(item.source)
        if audit is None or item.article_quality_status == "not_checked":
            continue
        audit.article_checked_count += 1
        if item.article_quality_status == "cleaned":
            audit.article_cleaned_count += 1
        if item.article_quality_status in {"fallback", "low_quality", "unavailable"}:
            audit.article_fallback_count += 1
    for audit in audits:
        if audit.article_cleaned_count:
            audit.notes.append(f"cleaned repeated template text in {audit.article_cleaned_count} article body/bodies")
        if audit.article_fallback_count:
            audit.notes.append(f"{audit.article_fallback_count} selected article(s) used a metadata/title fallback after body-quality checks")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a source-audited Chinese and Norway news digest.")
    parser.add_argument("--site", default="site/index.html", help="HTML output path.")
    parser.add_argument("--json", default="data/digest.json", help="JSON output path.")
    parser.add_argument("--audit-json", default="data/audit.json", help="Coverage audit output path.")
    parser.add_argument("--limit-per-source", type=int, default=80)
    parser.add_argument("--max-items", type=int, default=80)
    parser.add_argument("--max-age-days", type=int, default=730)
    parser.add_argument("--date-window-days", type=int, default=0)
    parser.add_argument("--target-date", default="", help="Coverage date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--cache", default="data/cache.json", help="Source cache path.")
    parser.add_argument("--cache-ttl-minutes", type=int, default=60)
    parser.add_argument("--no-cache", action="store_true", help="Disable source cache.")
    parser.add_argument("--article-cache", default="data/article_cache.json", help="Article text cache path.")
    parser.add_argument("--max-article-fetches", type=int, default=40)
    parser.add_argument("--db", default="data/digest.sqlite", help="SQLite history database path.")
    parser.add_argument("--no-db", action="store_true", help="Disable SQLite history writes.")
    parser.add_argument("--use-llm", action="store_true", help="Use OPENAI_API_KEY for optional LLM refinement.")
    parser.add_argument("--llm-max-items", type=int, default=20)
    parser.add_argument("--translate", action="store_true", help="Use OPENAI_API_KEY to add English and Norwegian text.")
    parser.add_argument("--translation-max-items", type=int, default=80)
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()
    configure_logging(args.verbose)

    target_date = datetime.strptime(args.target_date, "%Y-%m-%d").date() if args.target_date else datetime.now().date()
    cache_path = Path(args.cache)
    cache = None if args.no_cache else load_cache(cache_path)
    article_cache_path = Path(args.article_cache)
    article_cache = None if args.no_cache else load_cache(article_cache_path)
    items, audits = build_digest(
        args.limit_per_source,
        args.max_items,
        args.max_age_days,
        args.date_window_days,
        target_date,
        cache,
        args.cache_ttl_minutes,
    )
    enrich_items(items, target_date, article_cache, args.max_article_fetches)
    record_article_quality(audits, items)
    if args.use_llm:
        updated = llm_enrich_items(items, args.llm_max_items)
        if updated == 0:
            LOGGER.warning("LLM refinement skipped or failed; using heuristic enrichment.")
    if args.translate:
        translated = llm_translate_items(items, args.translation_max_items)
        if translated == 0:
            LOGGER.warning("Translation skipped or failed; multilingual page will use fallbacks.")
    generated_at = datetime.now()

    site_path = Path(args.site)
    json_path = Path(args.json)
    audit_path = Path(args.audit_json)
    site_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    site_path.write_text(render_html(items, generated_at, audits, target_date), encoding="utf-8")
    json_path.write_text(
        json.dumps([item.as_dict() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    audit_path.write_text(
        json.dumps([audit.as_dict() for audit in audits], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if cache is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    if article_cache is not None:
        article_cache_path.parent.mkdir(parents=True, exist_ok=True)
        article_cache_path.write_text(json.dumps(article_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.no_db:
        save_run(args.db, target_date, items, audits)
        weekly_items = load_recent_items(args.db, target_date, 7)
        weekly_prev = load_recent_items(args.db, target_date - timedelta(days=7), 7)
        monthly_items = load_recent_items(args.db, target_date, 30)
        monthly_prev = load_recent_items(args.db, target_date - timedelta(days=30), 30)
        weekly_path = site_path.parent / "weekly.html"
        monthly_path = site_path.parent / "monthly.html"
        weekly_path.write_text(
            render_archive(weekly_items, weekly_prev, "本周回顾（过去 7 天）", generated_at, target_date, 7),
            encoding="utf-8",
        )
        monthly_path.write_text(
            render_archive(monthly_items, monthly_prev, "本月回顾（过去 30 天）", generated_at, target_date, 30),
            encoding="utf-8",
        )
        LOGGER.info("Wrote weekly archive (%s items) and monthly archive (%s items)", len(weekly_items), len(monthly_items))
    LOGGER.info("Wrote %s items to %s, %s, and %s", len(items), site_path, json_path, audit_path)


def load_cache(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    main()
