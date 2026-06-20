from ai_builder_digest.classifier import classify_item
from datetime import date, datetime
from pathlib import Path
import sqlite3

from ai_builder_digest.cli import cache_is_fresh, effective_date_window_days, is_outside_date_window, is_too_old, parse_date
from ai_builder_digest.article import ArticleTextResult, ArchivedArticleError, extract_article_text_result, fetch_article_text
from ai_builder_digest.enrich import ARCHIVED_ARTICLE_MARKER, enrich_item, enrich_items
from ai_builder_digest.fetchers import (
    extract_date_from_url,
    fetch_huanqiu_hidden_items,
    is_probable_news_link,
    parse_anchor_items,
)
from ai_builder_digest.models import DigestItem
from ai_builder_digest.models import Source
from ai_builder_digest.render import (
    count_keywords,
    format_delta,
    render_archive,
    render_keyword_trends,
    render_top_stories,
)
from ai_builder_digest.storage import load_recent_items, save_run


def test_classifies_ai_policy_item() -> None:
    item = DigestItem(
        title="人工智能治理政策发布",
        link="https://example.com/news/1",
        source="测试",
        category="时政",
    )

    result = classify_item(item)

    assert result is not None
    assert "人工智能" in result.ai_keywords
    assert "政策" in result.policy_keywords
    assert result.score >= 5


def test_filters_non_ai_item() -> None:
    item = DigestItem(
        title="地方文旅活动启动",
        link="https://example.com/news/2",
        source="测试",
        category="时政",
    )

    assert classify_item(item) is None


def test_keeps_china_policy_without_ai_keyword() -> None:
    item = DigestItem(
        title="外交部：中国愿继续推动国际合作",
        link="https://example.com/news/5",
        source="环球网-国际",
        category="国际时政",
    )

    result = classify_item(item)

    assert result is not None
    assert result.stream == "china-ai-policy"


def test_keeps_international_politics_without_ai_keyword() -> None:
    item = DigestItem(
        title="安理会讨论政治解决乌克兰危机，中方提出四点期待",
        link="https://example.com/news/6",
        source="环球网-国际",
        category="国际时政",
    )

    result = classify_item(item)

    assert result is not None
    assert result.score >= 5


def test_filters_old_dated_item() -> None:
    assert is_too_old("2021-10-08", max_age_days=730)


def test_filters_item_outside_target_date_window() -> None:
    assert is_outside_date_window("2026-06-09", date(2026, 6, 10), date_window_days=0)
    assert not is_outside_date_window("2026-06-10", date(2026, 6, 10), date_window_days=0)
    assert not is_outside_date_window("", date(2026, 6, 10), date_window_days=0)


def test_xinhua_sources_get_one_day_freshness_grace() -> None:
    xinhua = Source("新华网-时政", "https://www.news.cn/politics/", "html", "国内时政")
    other = Source("环球网-国际", "https://world.huanqiu.com/", "html", "国际时政")

    assert effective_date_window_days(xinhua, 0) == 1
    assert effective_date_window_days(other, 0) == 0


def test_rejects_stale_cache_timestamp() -> None:
    assert not cache_is_fresh("2020-01-01T00:00:00", ttl_minutes=60)


def test_classifies_norway_nato_item() -> None:
    item = DigestItem(
        title="Norge diskuterer NATO og EØS",
        link="https://www.nrk.no/nyheter/norge-nato-eos-1.1",
        source="NRK-最新新闻",
        category="挪威/NATO/EØS",
    )

    result = classify_item(item)

    assert result is not None
    assert result.stream == "norway-nato-eos"


def test_classifies_norway_possessive_security_terms() -> None:
    item = DigestItem(
        title="NATOs vurdering av Forsvarets beredskap i nord",
        link="https://www.nrk.no/nyheter/natos-forsvarets-beredskap-1.1",
        source="NRK-最新新闻",
        category="挪威/NATO/EØS",
    )

    result = classify_item(item)

    assert result is not None
    assert "NATO" in result.ai_keywords
    assert "Forsvaret" in result.ai_keywords


def test_classifies_norway_defense_compound_terms() -> None:
    item = DigestItem(
        title="Forsvarsministeren varsler nytt forsvarsbudsjett for Norge",
        link="https://www.nrk.no/nyheter/forsvarsminister-forsvarsbudsjett-1.1",
        source="NRK-最新新闻",
        category="挪威/NATO/EØS",
    )

    result = classify_item(item)

    assert result is not None
    assert "forsvars" in result.ai_keywords
    assert result.score >= 5


def test_short_keyword_matching_is_case_insensitive() -> None:
    item = DigestItem(
        title="eu foreslår ny sikkerhetspolitikk",
        link="https://www.nrk.no/nyheter/eu-sikkerhet-1.1",
        source="NRK-最新新闻",
        category="挪威/NATO/EØS",
    )

    result = classify_item(item)

    assert result is not None
    assert "EU" in result.ai_keywords


def test_excludes_vg_sports_item() -> None:
    item = DigestItem(
        title="Messi-scoring etter to minutter",
        link="https://www.vg.no/sport/i/example",
        source="VG-最新新闻",
        category="挪威/NATO/EØS",
    )

    assert classify_item(item) is None


def test_excludes_norway_sports_title_even_without_sport_path() -> None:
    item = DigestItem(
        title="Krise i Toppserien: Røa trenger penger",
        link="https://www.vg.no/i/example",
        source="VG-最新新闻",
        category="挪威/NATO/EØS",
    )

    assert classify_item(item) is None


def test_enriches_china_item_with_brief_and_claim_check() -> None:
    item = DigestItem(
        title="某公司发布全球首个AI平台",
        link="https://example.com/news/3",
        source="环球网-科技",
        category="AI产业",
        summary="某公司发布全球首个AI平台，宣称能够赋能多个行业。",
    )
    classified = classify_item(item)
    assert classified is not None

    enrich_item(classified, date(2026, 6, 10))

    assert classified.brief
    assert "宣传性表述" in classified.claim_check
    assert classified.judge in {"keep", "review"}


def test_saves_digest_to_sqlite(tmp_path: Path) -> None:
    item = DigestItem(
        title="人工智能治理政策发布",
        link="https://example.com/news/4",
        source="测试",
        category="国内时政",
        brief="摘要",
        importance="重要性",
    )
    db_path = tmp_path / "digest.sqlite"

    save_run(db_path, date(2026, 6, 10), [item], [])

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM digest_items").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_probable_news_link_uses_source_host_not_hardcoded_domains() -> None:
    assert is_probable_news_link("https://example.org/news/20260610/story.html", "https://example.org/")
    assert not is_probable_news_link("https://other.org/news/20260610/story.html", "https://example.org/")


def test_xinhua_topic_pages_are_not_treated_as_news_articles() -> None:
    source_url = "https://www.news.cn/politics/"

    assert not is_probable_news_link("http://www.news.cn/talking/2022-07/02/c_1128796615.htm", source_url)
    assert not is_probable_news_link("https://www.news.cn/zt/2026lhjskls/index.html", source_url)
    assert is_probable_news_link(
        "https://www.news.cn/politics/20260612/9875e84188754f73b53ac67ca9b97198/c.html",
        source_url,
    )


def test_extract_date_from_xinhua_hyphenated_url() -> None:
    assert extract_date_from_url("http://www.news.cn/talking/2022-07/02/c_1128796615.htm") == "2022-07-02"


def test_extract_date_from_compact_url() -> None:
    assert extract_date_from_url("https://www.news.cn/politics/20260612/abc123/c.html") == "2026-06-12"


def test_extract_date_from_full_hyphenated_url() -> None:
    assert extract_date_from_url("https://example.com/news/2026-06-12/story.html") == "2026-06-12"


def test_extract_date_returns_empty_for_no_match() -> None:
    assert extract_date_from_url("https://example.com/news/no-date-here/story.html") == ""


def test_article_extraction_prefers_content_container_and_cleans_repeated_template() -> None:
    content = """
    <html><head><meta name="description" content="备用摘要，不应优先使用。"></head><body>
      <p>页面导航内容，不应成为正文。</p>
      <div class="article-content">
        <p>新闻摘要新闻摘要新闻摘要新闻摘要12月20日，2026环球时报年会在北京举行，与会者围绕国际安全和全球治理展开讨论。</p>
        <p>会议还讨论了国际合作与多边机制，为后续政策观察提供了公开信息。</p>
      </div>
    </body></html>
    """

    result = extract_article_text_result(content)

    assert result.status == "cleaned"
    assert "新闻摘要新闻摘要" not in result.text
    assert result.text.startswith("12月20日")
    assert "页面导航内容" not in result.text


def test_article_extraction_falls_back_to_metadata_when_body_is_low_quality() -> None:
    content = """
    <html><head><meta name="description" content="这是可用的页面摘要，说明会议围绕国际合作、全球治理和安全议题展开讨论。"></head>
    <body><div class="article-content"><p>新闻摘要新闻摘要新闻摘要</p></div></body></html>
    """

    result = extract_article_text_result(content)

    assert result.status == "fallback"
    assert result.text.startswith("这是可用的页面摘要")


def test_rss_date_is_converted_to_source_local_timezone() -> None:
    parsed = parse_date("Wed, 10 Jun 2026 22:30:00 GMT", "NO")

    assert parsed is not None
    assert parsed.date() == date(2026, 6, 11)


def test_huanqiu_hidden_parser_can_fall_back_to_anchor_parser() -> None:
    source = Source("示例源", "https://example.org/", "html", "国际时政")
    html = '<html><body><a href="https://example.org/news/20260610/story.html">国际政策新闻</a></body></html>'

    assert fetch_huanqiu_hidden_items(source, html, 10) == []
    assert parse_anchor_items(source, html, 10)[0].title == "国际政策新闻"


def test_archived_xinhua_page_is_rejected(monkeypatch) -> None:
    def fake_fetch_text(url: str) -> str:
        return "<html><body>您查看的内容已过期归档，谢谢关注新华网。快速进入新华网首页</body></html>"

    monkeypatch.setattr("ai_builder_digest.article.fetch_text", fake_fetch_text)

    try:
        fetch_article_text("https://www.news.cn/politics/example/c.html")
        assert False, "archived article should raise"
    except ArchivedArticleError:
        pass


def test_enrich_items_drops_archived_article_marker() -> None:
    item = DigestItem(
        title="政策新闻",
        link="https://www.news.cn/politics/example/c.html",
        source="新华网-时政",
        category="国内时政",
        published="2026-06-12",
    )

    result = enrich_items(
        [item],
        date(2026, 6, 12),
        article_cache={item.link: ARCHIVED_ARTICLE_MARKER},
        max_article_fetches=0,
    )

    assert result == []


def test_enrich_items_refetches_empty_cached_xinhua_validation(monkeypatch) -> None:
    item = DigestItem(
        title="政策新闻",
        link="https://www.news.cn/politics/example/c.html",
        source="新华网-时政",
        category="国内时政",
        published="2026-06-12",
    )
    calls = {"count": 0}

    def fake_fetch_article_result(url: str) -> ArticleTextResult:
        calls["count"] += 1
        raise ArchivedArticleError("archived")

    monkeypatch.setattr("ai_builder_digest.enrich.fetch_article_result", fake_fetch_article_result)

    result = enrich_items([item], date(2026, 6, 12), {item.link: ""}, max_article_fetches=0)

    assert result == []
    assert calls["count"] == 1


def test_enrich_items_drops_unreadable_xinhua_article(monkeypatch) -> None:
    item = DigestItem(
        title="政策新闻",
        link="https://www.news.cn/politics/example/c.html",
        source="新华网-时政",
        category="国内时政",
        published="2026-06-12",
    )

    monkeypatch.setattr(
        "ai_builder_digest.enrich.fetch_article_result",
        lambda url: ArticleTextResult("", "low_quality", "test empty body"),
    )

    result = enrich_items([item], date(2026, 6, 12), {item.link: ""}, max_article_fetches=0)

    assert result == []


def test_legacy_article_cache_is_refreshed_with_quality_metadata(monkeypatch) -> None:
    item = DigestItem(
        title="国际会议讨论全球治理",
        link="https://world.huanqiu.com/article/example",
        source="环球网-国际",
        category="国际时政",
        published="2026-06-12",
    )
    cache: dict[str, object] = {item.link: "新闻摘要新闻摘要新闻摘要"}
    calls = {"count": 0}

    def fake_fetch_article_result(url: str) -> ArticleTextResult:
        calls["count"] += 1
        return ArticleTextResult("这是一段清理后的可读正文，用于验证旧缓存会在升级后重新抓取并写入质量状态。", "cleaned", "removed repeated template text")

    monkeypatch.setattr("ai_builder_digest.enrich.fetch_article_result", fake_fetch_article_result)

    result = enrich_items([item], date(2026, 6, 12), cache, max_article_fetches=1)

    assert result[0].article_quality_status == "cleaned"
    assert calls["count"] == 1
    assert isinstance(cache[item.link], dict)


def test_ai_does_not_match_inside_english_word() -> None:
    for title in ["Spain economy update", "campaign launch", "email security report"]:
        item = DigestItem(
            title=title,
            link="https://example.com/news/ai-boundary",
            source="参考消息-产经",
            category="AI产业",
        )

        result = classify_item(item)

        assert result is None or "AI" not in result.ai_keywords


def test_real_ai_keyword_still_matches() -> None:
    item = DigestItem(
        title="AI产业政策与AIGC发展",
        link="https://example.com/news/real-ai",
        source="参考消息-产经",
        category="AI产业",
    )

    result = classify_item(item)

    assert result is not None
    assert "AI" in result.ai_keywords or "AIGC" in result.ai_keywords


def test_substring_keyword_not_double_counted() -> None:
    item = DigestItem(
        title="大模型技术发展",
        link="https://example.com/news/model",
        source="参考消息-科技应用",
        category="AI产业",
    )

    result = classify_item(item)

    assert result is not None
    assert "大模型" in result.ai_keywords
    assert "模型" not in result.ai_keywords


def test_load_recent_items_returns_window_in_date_desc_order(tmp_path: Path) -> None:
    db_path = tmp_path / "digest.sqlite"
    for target, link in [
        (date(2026, 6, 8), "a"),
        (date(2026, 6, 10), "b"),
        (date(2026, 6, 12), "c"),
        (date(2026, 5, 20), "old"),
    ]:
        item = DigestItem(title=f"标题-{link}", link=f"https://example.com/{link}", source="测试", category="国内时政")
        save_run(db_path, target, [item], [])

    recent = load_recent_items(db_path, date(2026, 6, 12), days=7)

    links = [item.link for _, item in recent]
    assert "https://example.com/old" not in links
    dates = [d for d, _ in recent]
    assert dates == sorted(dates, reverse=True)
    assert len(recent) == 3


def test_load_recent_items_returns_empty_when_db_missing(tmp_path: Path) -> None:
    assert load_recent_items(tmp_path / "missing.sqlite", date(2026, 6, 12), days=7) == []


def test_render_archive_handles_empty_history() -> None:
    html = render_archive([], [], "本周回顾", datetime(2026, 6, 12, 9, 0), date(2026, 6, 12), 7)
    assert "本周回顾" in html
    assert "还没有历史数据" in html


def test_render_archive_groups_items_by_date() -> None:
    items = [
        (date(2026, 6, 12), DigestItem(title="今日新闻", link="https://example.com/today", source="测试", category="国内时政")),
        (date(2026, 6, 10), DigestItem(title="两天前的新闻", link="https://example.com/older", source="测试", category="AI产业")),
    ]
    html = render_archive(items, [], "本周回顾", datetime(2026, 6, 12, 9, 0), date(2026, 6, 12), 7)
    assert "2026-06-12" in html
    assert "2026-06-10" in html
    assert "今日新闻" in html
    assert "两天前的新闻" in html


def test_count_keywords_combines_ai_and_policy() -> None:
    a = DigestItem(title="A", link="a", source="s", category="AI产业")
    a.ai_keywords = ["AI", "大模型"]
    a.policy_keywords = ["监管"]
    b = DigestItem(title="B", link="b", source="s", category="国内时政")
    b.ai_keywords = ["AI"]
    b.policy_keywords = ["监管", "政策"]

    counts = count_keywords([a, b])

    assert counts["AI"] == 2
    assert counts["监管"] == 2
    assert counts["大模型"] == 1
    assert counts["政策"] == 1


def test_format_delta_marks_new_keyword_when_no_previous() -> None:
    label, cls = format_delta(5, 0)
    assert label == "新出现"
    assert cls == "delta-new"


def test_format_delta_uses_neutral_for_small_change() -> None:
    label, cls = format_delta(100, 102)
    assert label == "持平"
    assert cls == "delta-neutral"


def test_format_delta_signs_increase_and_decrease() -> None:
    up_label, up_cls = format_delta(150, 100)
    down_label, down_cls = format_delta(50, 100)
    assert up_label.startswith("+")
    assert up_cls == "delta-up"
    assert down_label.startswith("-")
    assert down_cls == "delta-down"


def test_render_keyword_trends_shows_top_keywords_with_delta() -> None:
    current = []
    for _ in range(3):
        item = DigestItem(title="t", link="x", source="s", category="AI产业")
        item.ai_keywords = ["AI", "大模型"]
        current.append(item)
    prev = []
    for _ in range(2):
        item = DigestItem(title="t", link="x", source="s", category="AI产业")
        item.ai_keywords = ["AI"]
        prev.append(item)

    html_str = render_keyword_trends(current, prev, days=7)

    assert "AI" in html_str
    assert "大模型" in html_str
    assert "关键词热度排行" in html_str


def test_render_keyword_trends_returns_empty_for_empty_items() -> None:
    assert render_keyword_trends([], [], days=7) == ""


def test_render_top_stories_ranks_by_score_and_dedupes_links() -> None:
    high = DigestItem(title="高分", link="https://a", source="s", category="国内时政", score=80)
    mid = DigestItem(title="中分", link="https://b", source="s", category="AI产业", score=40)
    duplicate_lower = DigestItem(title="高分旧版", link="https://a", source="s", category="国内时政", score=30)

    html_str = render_top_stories([high, mid, duplicate_lower], days=30)

    assert "高分" in html_str
    assert "中分" in html_str
    assert "高分旧版" not in html_str
    assert html_str.index("高分") < html_str.index("中分")


def test_render_top_stories_returns_empty_when_no_items() -> None:
    assert render_top_stories([], days=30) == ""
