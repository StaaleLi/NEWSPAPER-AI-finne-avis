from __future__ import annotations

import html
from datetime import date, datetime

from .models import DigestItem, SourceAudit


def render_html(
    items: list[DigestItem],
    generated_at: datetime,
    audits: list[SourceAudit] | None = None,
    target_date: date | None = None,
) -> str:
    audits = audits or []
    target_date = target_date or generated_at.date()
    norway = [item for item in items if item.stream == "norway-nato-eos"]
    china = [item for item in items if item.stream != "norway-nato-eos"]
    politics = [item for item in china if item.category in {"国内时政", "国际时政", "评论"}]
    ai = [item for item in china if item.category not in {"国内时政", "国际时政", "评论"}]
    return f"""<!doctype html>
<html lang="zh-CN" data-lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NewsLens Daily</title>
  <style>
    :root{{--bg:#eef2f3;--paper:#fbfaf7;--panel:#fff;--ink:#111827;--text:#17202a;--muted:#667085;--border:#d7dde5;--accent:#0f766e;--soft:#e6f5f2;--warn:#9a3412;--good:#067647;--bad:#b42318;--shadow:0 18px 45px rgba(20,35,48,.08)}}
    *{{box-sizing:border-box}} body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.55}}
    header{{padding:28px 20px 22px;border-bottom:1px solid var(--border);background:linear-gradient(90deg,rgba(15,118,110,.10),rgba(183,121,31,.08)),var(--paper)}} .wrap{{max-width:1120px;margin:0 auto}}
    .masthead{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:end}} .brand-line{{margin-bottom:10px;color:var(--accent);font-size:13px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}}
    h1{{margin:0 0 8px;font-size:44px;line-height:1;color:var(--ink)}} .subtitle{{margin:0;color:#526173;max-width:820px;font-size:17px}}
    .date-stamp{{min-width:150px;padding:12px 14px;border-left:4px solid var(--accent);background:rgba(255,255,255,.72);color:#344054;font-size:13px;text-align:right}} .date-stamp strong{{display:block;color:var(--ink);font-size:24px;line-height:1.1}}
    .meta,.filter-bar{{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px;color:var(--muted);font-size:14px}} .pill,.filter-button{{border:1px solid var(--border);background:rgba(255,255,255,.82);border-radius:999px;padding:6px 12px}}
    main{{padding:28px 20px 54px}} .toolbar{{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px;margin-bottom:22px;padding:16px 18px;border:1px solid var(--border);border-radius:8px;background:var(--panel);box-shadow:var(--shadow);color:var(--muted);font-size:14px}}
    .toolbar strong{{display:block;color:var(--ink);font-size:18px}} .toolbar a{{color:var(--accent);font-weight:700;text-decoration:none}}
    .language-switcher{{display:inline-flex;gap:6px;padding:4px;border:1px solid var(--border);border-radius:999px;background:rgba(255,255,255,.76)}} .language-switcher button,.filter-button{{appearance:none;cursor:pointer;font:inherit;font-size:13px;font-weight:800}}
    .language-switcher button{{border:0;border-radius:999px;background:transparent;color:var(--muted);padding:5px 10px}} .language-switcher button.active,.filter-button.active{{background:var(--ink);color:#fff;border-color:var(--ink)}} .filter-bar{{margin:0 0 22px}}
    .lang-text,.lang-block,.filter-empty{{display:none}} html[data-lang=zh] .lang-zh.lang-text,html[data-lang=no] .lang-no.lang-text,html[data-lang=en] .lang-en.lang-text{{display:inline}} html[data-lang=zh] .lang-zh.lang-block,html[data-lang=no] .lang-no.lang-block,html[data-lang=en] .lang-en.lang-block{{display:block}}
    .filter-empty.is-visible{{display:block;margin-bottom:22px;padding:14px 16px;border:1px dashed var(--border);border-radius:8px;background:rgba(255,255,255,.72);color:var(--muted)}}
    .issue-section{{margin-top:32px;padding:22px;border:1px solid var(--border);border-radius:8px;background:var(--paper);box-shadow:var(--shadow)}} .issue-section.is-hidden,article.is-hidden{{display:none}}
    .section-title{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:end;margin:0 0 18px;padding-bottom:12px;border-bottom:3px double #aeb8c5;font-size:28px;color:var(--ink)}} .section-title small,.section-kicker{{color:var(--muted);font-size:14px;font-weight:500}} .section-kicker{{display:block;margin-top:4px}}
    .issue-grid,.story-river,.audit-grid{{display:grid;gap:12px}} .issue-grid{{grid-template-columns:1fr}} .story-river{{grid-template-columns:repeat(auto-fit,minmax(290px,1fr));margin-top:12px}}
    article{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:18px;min-height:260px;display:flex;flex-direction:column;gap:10px;box-shadow:0 10px 30px rgba(20,35,48,.06)}} article.lead-story{{min-height:0;padding:22px;border-top:5px solid var(--ink);background:#fffdf8}} article.lead-story h2{{font-size:28px;line-height:1.22}} article.compact-story{{min-height:0;padding:15px;box-shadow:none}} article.compact-story h2{{font-size:17px}} article.compact-story .credibility,article.compact-story .claim-check,article.compact-story .judge-row,article.compact-story .reason{{display:none}}
    article h2{{margin:0;font-size:19px;line-height:1.35}} article h2 a{{color:var(--text);text-decoration:none}} article h2 a:hover{{color:var(--accent);text-decoration:underline}} .source{{display:flex;flex-wrap:wrap;align-items:center;gap:7px;color:var(--muted);font-size:13px}} .label{{display:block;color:var(--muted);font-size:12px;font-weight:700;margin-bottom:2px}} .source .label,h2 .label{{display:none}}
    .summary,.analysis{{color:#344054;font-size:14px}} .analysis{{border-top:1px solid var(--border);padding-top:9px}} .reason{{padding:10px 11px;border-radius:6px;border-left:3px solid var(--accent);background:var(--soft);color:#115e59;font-size:14px}} .judge{{display:inline-flex;width:fit-content;border-radius:999px;padding:3px 8px;font-size:12px;font-weight:700;background:#ecfdf3;color:var(--good)}} .judge-review{{background:#fff7ed;color:var(--warn)}} .tags{{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto}} .tag{{background:#f3f6f7;color:#3d4b5c;border-radius:999px;padding:4px 9px;font-size:12px}} .score{{display:inline-flex;border-radius:999px;background:#fff7ed;color:var(--warn);font-weight:800;padding:2px 8px}}
    .empty,.audit{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:18px;box-shadow:var(--shadow)}} .audit{{margin-top:28px}} .audit summary{{cursor:pointer;color:var(--ink);font-size:18px;font-weight:800}} .audit-grid{{grid-template-columns:repeat(auto-fit,minmax(260px,1fr));margin-top:14px}} .audit-card{{border:1px solid var(--border);border-radius:6px;padding:10px;background:#fbfcfe}} .audit-line,.audit-summary-note{{color:var(--muted);font-size:13px}} .status-ok{{color:var(--good);font-weight:700}} .status-failed{{color:var(--bad);font-weight:700}} .notes{{margin:6px 0 0;padding-left:18px;color:var(--warn);font-size:13px}}
    @media(max-width:720px){{.masthead,.section-title{{grid-template-columns:1fr}}.date-stamp{{text-align:left}}h1{{font-size:36px}}.issue-section{{padding:16px}}.story-river{{grid-template-columns:1fr}}article.lead-story h2{{font-size:22px}}}}
  </style>
</head>
<body>
  <header><div class="wrap"><div class="masthead"><div><div class="brand-line">Curated public-source briefing</div><h1>NewsLens Daily</h1><p class="subtitle">{lang_block("从参考消息、新华社、环球网、NRK、VG 等公开信源中筛选“中国时政/AI产业”和“挪威/NATO/EØS”相关内容。每条保留原文跳转、入选理由和来源提示。","Utvalgte saker fra Cankaoxiaoxi, Xinhua, Global Times, NRK og VG om kinesisk politikk, AI-industri og Norge/NATO/EØS. Hver sak beholder lenke til originalkilden, utvalgsgrunn og kildehint.","Selected items from Cankaoxiaoxi, Xinhua, Global Times, NRK, and VG on China politics, AI industry, and Norway/NATO/EØS. Each card keeps the original link, selection reason, and source note.")}</p></div><div class="date-stamp">今日审查<strong>{html.escape(target_date.strftime("%m.%d"))}</strong>{html.escape(target_date.isoformat())}</div></div><div class="meta"><span class="pill">生成时间：{html.escape(generated_at.strftime("%Y-%m-%d %H:%M"))}</span><span class="pill">审查日期：{html.escape(target_date.isoformat())}</span><span class="pill">命中：{len(items)} 条</span><span class="pill">中国时政：{len(politics)} 条</span><span class="pill">AI产业：{len(ai)} 条</span><span class="pill">挪威：{len(norway)} 条</span></div></div></header>
  <main><div class="wrap"><div class="toolbar"><span><strong>{lang_inline("今日新闻摘要","Dagens nyhetsbrief","Daily briefing")}</strong>{lang_inline("优先展示符合主题且相关性更高的内容，点击标题可直接跳转原文。","Sakene er sortert etter tema og relevans. Klikk på tittelen for å åpne originalen.","Items are sorted by theme and relevance. Click a headline to open the original source.")}</span><div class="language-switcher" aria-label="Language"><button class="active" type="button" data-lang-button="zh" aria-pressed="true">中文</button><button type="button" data-lang-button="no" aria-pressed="false">Norsk</button><button type="button" data-lang-button="en" aria-pressed="false">English</button></div><a href="#source-audit">{lang_inline("查看来源审查","Se kildekontroll","View source audit")}</a></div>
  <nav class="filter-bar">{filter_button("全部","all","全部","Alle","All",True)}{filter_button("国内时政","china-domestic","国内时政","Innenrikspolitikk","China domestic")}{filter_button("国际时政","international","国际时政","Internasjonal politikk","International")}{filter_button("AI产业","ai-industry","AI产业","AI-industri","AI industry")}{filter_button("挪威/NATO/EØS","norway-nato-eos","挪威/NATO/EØS","Norge/NATO/EØS","Norway/NATO/EØS")}{filter_button("评论","commentary","评论","Kommentar","Commentary")}</nav><div class="filter-empty" aria-live="polite">{lang_block("该分类今天没有命中内容。","Ingen saker i denne kategorien i dag.","No items matched this category today.")}</div>
  {render_section("中国国内 / 国际时政",politics,"今日重点政治、外交、国际关系与公共政策线索","没有命中中国时政内容；请查看审查区判断是否是源失败、日期不匹配或关键词过窄。")}
  {render_section("AI产业 / 科技政策",ai,"人工智能、芯片、算力、数据中心与科技监管动态","没有命中AI产业内容；请查看审查区判断是否是源失败或关键词过窄。")}
  {render_section("挪威 / NATO / EØS",norway,"VG / NRK 中的挪威公共事务、安全、经济与欧洲制度关系","没有命中挪威/NATO/EØS内容；请查看审查区判断是否是源失败或确实无相关项。")}
  {render_audit(audits)}</div></main>
  <script>(()=>{{const f=[...document.querySelectorAll(".filter-button")],l=[...document.querySelectorAll("[data-lang-button]")],s=[...document.querySelectorAll(".issue-section")],a=[...document.querySelectorAll("article[data-category]")],e=document.querySelector(".filter-empty"),m={{zh:"zh-CN",no:"nb-NO",en:"en"}};function F(slug,hash=true){{const b=f.find(x=>x.dataset.slug===slug)||f[0],cat=b.dataset.filter||"全部",all=cat==="全部";let n=0,first=null;a.forEach(x=>{{const v=all||x.dataset.category===cat;x.classList.toggle("is-hidden",!v);if(v)n++}});s.forEach(x=>{{const v=x.querySelectorAll("article[data-category]:not(.is-hidden)").length>0;x.classList.toggle("is-hidden",!v);if(v&&!first)first=x}});if(e)e.classList.toggle("is-visible",n===0);f.forEach(x=>{{const v=x===b;x.classList.toggle("active",v);x.setAttribute("aria-pressed",v?"true":"false")}});if(hash)history.replaceState(null,"",all?window.location.pathname+window.location.search:`#${{b.dataset.slug}}`);if(!all&&first)first.scrollIntoView({{behavior:"smooth",block:"start"}})}}function L(lang){{const next=m[lang]?lang:"zh";document.documentElement.dataset.lang=next;document.documentElement.lang=m[next];localStorage.setItem("newslens-language",next);l.forEach(x=>{{const v=x.dataset.langButton===next;x.classList.toggle("active",v);x.setAttribute("aria-pressed",v?"true":"false")}})}}f.forEach(b=>b.addEventListener("click",()=>F(b.dataset.slug)));l.forEach(b=>b.addEventListener("click",()=>L(b.dataset.langButton)));const h=decodeURIComponent((location.hash||"").replace(/^#/,"")).trim();if(h&&f.some(b=>b.dataset.slug===h))F(h,false);L(localStorage.getItem("newslens-language")||"zh")}})();</script>
</body></html>"""


def filter_button(category: str, slug: str, zh: str, no: str, en: str, active: bool = False) -> str:
    return f'<button class="filter-button{" active" if active else ""}" type="button" data-filter="{html.escape(category, quote=True)}" data-slug="{html.escape(slug, quote=True)}" aria-pressed="{"true" if active else "false"}">{lang_inline(zh, no, en)}</button>'


def render_section(title: str, items: list[DigestItem], kicker: str, empty_text: str) -> str:
    if not items:
        return f'<section class="issue-section"><h2 class="section-title">{html.escape(title)} <small>0 条</small><span class="section-kicker">{html.escape(kicker)}</span></h2><section class="empty">{html.escape(empty_text)}</section></section>'
    lead = render_card(items[0], True)
    more = "".join(render_card(item) for item in items[1:])
    return f'<section class="issue-section"><h2 class="section-title"><span>{html.escape(title)}<span class="section-kicker">{html.escape(kicker)}</span></span><small>{len(items)} 条</small></h2><div class="issue-grid">{lead}</div>{"<div class=\"story-river\">" + more + "</div>" if more else ""}</section>'


def render_card(item: DigestItem, featured: bool = False) -> str:
    title_zh = item.chinese_title if item.stream == "norway-nato-eos" and item.chinese_title else item.title
    brief_zh = item.brief or build_brief(item)
    importance_zh = item.importance or "建议点击原文查看影响。"
    tags = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in (item.ai_keywords[:4] + item.policy_keywords[:4]))
    judge_class = "judge judge-review" if item.judge == "review" else "judge"
    published = f" · {html.escape(item.published)}" if item.published else ""
    original = f'<div class="summary lang-block lang-zh"><span class="label">原题</span>{html.escape(item.title)}</div>' if item.stream == "norway-nato-eos" and item.chinese_title and item.chinese_title != item.title else ""
    return f"""<article class="{"lead-story" if featured else "compact-story"}" data-category="{html.escape(item.category, quote=True)}">
  <div class="source"><span class="label">{lang_inline("来源","Kilde","Source")}</span>{html.escape(item.source)} · {localized_category(item.category)}{published} · <span class="score">score {item.score}</span></div>
  <h2><span class="label">{lang_inline("标题","Tittel","Title")}</span><a href="{html.escape(item.link)}" target="_blank" rel="noopener noreferrer">{lang_inline(title_zh, item.title_no or item.title, item.title_en or item.title)}</a></h2>{original}
  <div class="summary"><span class="label">{lang_inline("内容概要","Sammendrag","Summary")}</span>{lang_block(brief_zh, item.brief_no or brief_zh, item.brief_en or brief_zh)}</div>
  <div class="analysis"><span class="label">{lang_inline("为什么重要","Hvorfor viktig","Why it matters")}</span>{lang_block(importance_zh, item.importance_no or importance_zh, item.importance_en or importance_zh)}</div>
  <div class="analysis credibility"><span class="label">可信度 / 来源提示</span>{html.escape(item.credibility or "需要结合原文和其他来源判断。")}</div>
  <div class="analysis claim-check"><span class="label">Claim check</span>{html.escape(item.claim_check or "未发现明显高风险断言。")}</div>
  <div class="analysis judge-row"><span class="label">二次判断</span><span class="{judge_class}">{html.escape(item.judge or "keep")}</span> {html.escape(item.judge_reason)}</div>
  <div class="reason"><span class="label">{lang_inline("为什么入选","Hvorfor valgt","Why selected")}</span>{lang_block(item.reason, item.reason_no or item.reason, item.reason_en or item.reason)}</div><div class="tags">{tags}</div></article>"""


def lang_inline(zh: str, no: str, en: str) -> str:
    return f'<span class="lang-text lang-zh">{html.escape(zh)}</span><span class="lang-text lang-no">{html.escape(no)}</span><span class="lang-text lang-en">{html.escape(en)}</span>'


def lang_block(zh: str, no: str, en: str) -> str:
    return f'<span class="lang-block lang-zh">{html.escape(zh)}</span><span class="lang-block lang-no">{html.escape(no)}</span><span class="lang-block lang-en">{html.escape(en)}</span>'


def localized_category(category: str) -> str:
    labels = {"国内时政": ("国内时政", "Innenrikspolitikk", "China domestic"), "国际时政": ("国际时政", "Internasjonal politikk", "International"), "AI产业": ("AI产业", "AI-industri", "AI industry"), "挪威/NATO/EØS": ("挪威/NATO/EØS", "Norge/NATO/EØS", "Norway/NATO/EØS"), "评论": ("评论", "Kommentar", "Commentary")}
    return lang_inline(*labels.get(category, (category, category, category)))


def build_brief(item: DigestItem) -> str:
    if item.summary:
        return item.summary[:220]
    title = item.title.rstrip("。")
    keywords = "、".join((item.ai_keywords + item.policy_keywords)[:4])
    if item.stream == "norway-nato-eos":
        return f"这条来自 VG/NRK 的新闻主要涉及“{title}”，与挪威公共事务、NATO/EØS、安全或经济议题有关；命中线索包括：{keywords or '挪威公共事务'}。"
    return f"这条中文新闻主要讲“{title}”。它被归入{item.category}，因为标题或摘要中出现了这些线索：{keywords or item.category}。"


def render_audit(audits: list[SourceAudit]) -> str:
    if not audits:
        return ""
    return '<details class="audit" id="source-audit"><summary>来源与完整性审查 <span class="audit-summary-note">展开查看每个来源的抓取状态</span></summary><div class="audit-grid">' + "".join(render_audit_card(audit) for audit in audits) + "</div></details>"


def display_source_url(url: str) -> str:
    if "ckxxapp.ckxx.net/json/channel/" in url:
        return f"https://www.cankaoxiaoxi.com/#/generalColumns/{url.rstrip('/').split('/')[-2]}"
    if "nrk.no/nyheter/siste.rss" in url:
        return "https://www.nrk.no/nyheter/"
    if "vg.no/rss/feed" in url:
        return "https://www.vg.no/nyheter/"
    return url


def render_audit_card(audit: SourceAudit) -> str:
    notes = []
    raw = " ".join(audit.notes)
    if audit.status != "ok":
        notes.append("这个来源暂时抓取失败，今天结果可能不完整。")
    if "no reliable per-item date" in raw or "some html items have no reliable date" in raw:
        notes.append("部分条目没有稳定日期，今日完整性只能部分确认。")
    if audit.total_fetched == 0:
        notes.append("这个来源没有抓到内容。")
    elif audit.today_count == 0:
        notes.append("今天没有识别到该来源的当日新闻。")
    elif audit.selected_count == 0:
        notes.append("今天有更新，但没有内容符合当前筛选主题。")
    notes_html = '<ul class="notes">' + "".join(f"<li>{html.escape(note)}</li>" for note in dict.fromkeys(notes)) + "</ul>" if notes else ""
    status_class = "status-ok" if audit.status == "ok" else "status-failed"
    return f'<div class="audit-card"><strong>{html.escape(audit.name)}</strong><div class="{status_class}">{html.escape(audit.status)}</div><div class="audit-line">抓取：{audit.total_fetched} · 今日：{audit.today_count} · 入选：{audit.selected_count}</div><div class="audit-line">{html.escape(audit.region)} · <a href="{html.escape(display_source_url(audit.url))}" target="_blank" rel="noopener noreferrer">打开来源页</a></div>{notes_html}</div>'
