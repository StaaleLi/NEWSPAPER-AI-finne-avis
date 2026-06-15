from __future__ import annotations

import re

from .models import DigestItem


AI_KEYWORDS = [
    "人工智能",
    "AI",
    "AIGC",
    "大模型",
    "生成式",
    "算法",
    "算力",
    "智能体",
    "Agent",
    "机器人",
    "自动驾驶",
    "芯片",
    "数据中心",
    "数字化",
    "数字经济",
    "云计算",
    "深度学习",
    "机器学习",
    "模型",
    "智能",
]

POLICY_KEYWORDS = [
    "时政",
    "政策",
    "监管",
    "治理",
    "国家",
    "中国",
    "中方",
    "中央",
    "国务院",
    "人大",
    "政协",
    "政府",
    "党委",
    "省委",
    "市委",
    "外交部",
    "国防部",
    "部委",
    "法规",
    "标准",
    "安全",
    "数据",
    "网络安全",
    "产业",
    "发展",
    "国际",
    "全球",
    "中美",
    "美方",
    "欧盟",
    "联合国",
    "安理会",
    "外交",
    "政治",
    "选举",
    "议会",
    "总统",
    "总理",
    "首相",
    "外长",
    "防长",
    "部长",
    "访华",
    "访问",
    "会见",
    "谈判",
    "声明",
    "表态",
    "危机",
    "俄乌",
    "乌克兰",
    "俄罗斯",
    "美国",
    "制裁",
    "关税",
    "移民",
    "能源",
    "清单",
    "关系",
    "合作",
    "峰会",
    "会议",
    "发布",
    "意见",
    "办法",
    "条例",
]

CHINA_POLITICS_CATEGORIES = {"国内时政", "国际时政"}

CHINA_SOFT_EXCLUDE_TITLE_KEYWORDS = [
    "体育",
    "足球",
    "篮球",
    "比赛",
    "电影",
    "电视剧",
    "综艺",
    "娱乐",
    "明星",
    "时尚",
    "美食",
    "旅游",
    "村超",
]

NORWAY_KEYWORDS = [
    "Norge",
    "Noreg",
    "Norges",
    "norsk",
    "norske",
    "regjering",
    "regjeringen",
    "Stortinget",
    "NATO",
    "EØS",
    "EØS-avtalen",
    "EU",
    "Europa",
    "forsvar",
    "Forsvaret",
    "forsvars",
    "sikkerhet",
    "beredskap",
    "trussel",
    "politi",
    "PST",
    "Norges Bank",
    "rente",
    "økonomi",
    "børsen",
    "Kongsberg",
    "Telenor",
    "Oslo",
    "kommune",
    "helse",
    "Helsetilsynet",
    "arbeids",
    "bolig",
    "nødvarsel",
    "krise",
    "hendelse",
    "pågrepet",
    "Bergen",
    "Trondheim",
    "Stavanger",
    "Tromsø",
    "Kristiansand",
    "Drammen",
]

NORWAY_CONTEXT_KEYWORDS = [
    "politikk",
    "nyheter",
    "krig",
    "Ukraina",
    "Russland",
    "USA",
    "Trump",
    "Kina",
    "handel",
    "toll",
    "energi",
    "olje",
    "gass",
    "klima",
    "data",
    "teknologi",
    "beredskap",
    "nødvarsel",
]

NORWAY_HIGH_SIGNAL = {
    "NATO",
    "EØS",
    "EØS-avtalen",
    "EU",
    "regjering",
    "regjeringen",
    "Stortinget",
    "forsvar",
    "Forsvaret",
    "forsvars",
    "sikkerhet",
    "beredskap",
    "trussel",
    "PST",
    "Norges Bank",
    "rente",
    "økonomi",
}

NORWAY_WEAK_LOCATION_OR_IDENTITY = {
    "Norge",
    "Noreg",
    "Norges",
    "norsk",
    "norske",
    "Oslo",
    "Bergen",
    "Trondheim",
    "Stavanger",
    "Tromsø",
    "Kristiansand",
    "Drammen",
}

NORWAY_EXCLUDE_LINK_PARTS = [
    "/sport/",
    "/rampelys/",
    "/tv/",
    "/forbruker/",
]

NORWAY_EXCLUDE_TITLE_KEYWORDS = [
    "Toppserien",
    "Eliteserien",
    "Champions League",
    "Messi",
    "VM",
    "finalefest",
    "mote",
    "moteuken",
    "museum",
    "kunst",
    "konsert",
    "festival",
    "kjendis",
]

NORWAY_PUBLIC_LINK_PARTS = [
    "/innlandet/",
    "/stor-oslo/",
    "/vestfoldogtelemark/",
    "/vestland/",
    "/trondelag/",
    "/nordland/",
    "/tromsogfinnmark/",
    "/sorlandet/",
    "/moreogromsdal/",
    "/rogaland/",
]

NORWAY_POSSESSIVE_KEYWORDS = {
    "NATO",
    "EU",
    "Stortinget",
    "regjering",
    "regjeringen",
    "Forsvaret",
}

NORWAY_PREFIX_KEYWORDS = {
    "forsvars",
}


def _hits(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    result: list[str] = []
    for keyword in keywords:
        if keyword in NORWAY_PREFIX_KEYWORDS:
            if re.search(rf"(?<![A-Za-zÆØÅæøå]){re.escape(keyword)}", text, flags=re.IGNORECASE):
                result.append(keyword)
            continue
        if needs_word_match(keyword):
            suffix = "s?" if keyword in NORWAY_POSSESSIVE_KEYWORDS else ""
            if re.search(
                rf"(?<![A-Za-zÆØÅæøå]){re.escape(keyword)}{suffix}(?![A-Za-zÆØÅæøå])",
                text,
                flags=re.IGNORECASE,
            ):
                result.append(keyword)
            continue
        if keyword.lower() in lower:
            result.append(keyword)
    return _drop_subsumed_hits(result)


def _drop_subsumed_hits(hits: list[str]) -> list[str]:
    kept: list[str] = []
    for hit in hits:
        if any(hit != other and hit in other for other in hits):
            continue
        kept.append(hit)
    return kept


def needs_word_match(keyword: str) -> bool:
    return keyword.isascii() and keyword.isalpha()


def classify_item(item: DigestItem) -> DigestItem | None:
    if item.category == "挪威/NATO/EØS" or item.source.startswith(("NRK", "VG")):
        return classify_norway_item(item)
    return classify_china_item(item)


def classify_china_item(item: DigestItem) -> DigestItem | None:
    text = f"{item.title} {item.summary}"
    ai_hits = _hits(text, AI_KEYWORDS)
    policy_hits = _hits(text, POLICY_KEYWORDS)

    category_bonus = 2 if item.category in {"国内时政", "国际时政", "AI产业", "评论", "时政", "国际", "观点", "财经"} else 0
    if item.category in CHINA_POLITICS_CATEGORIES:
        if should_exclude_china_politics_item(item.title):
            return None
        score = len(policy_hits) * 3 + len(ai_hits) * 2 + category_bonus
        if score < 5:
            score = 5
            if not policy_hits:
                policy_hits = [item.category]
    else:
        if not ai_hits:
            return None
        score = len(ai_hits) * 3 + len(policy_hits) * 2 + category_bonus

    if score < 5:
        return None

    item.ai_keywords = ai_hits
    item.policy_keywords = policy_hits
    item.stream = "china-ai-policy"
    item.score = score
    item.reason = _build_china_reason(ai_hits, policy_hits, item.category)
    return item


def should_exclude_china_politics_item(title: str) -> bool:
    return any(keyword in title for keyword in CHINA_SOFT_EXCLUDE_TITLE_KEYWORDS)


def classify_norway_item(item: DigestItem) -> DigestItem | None:
    text = f"{item.title} {item.summary} {item.link}"
    norway_hits = _hits(text, NORWAY_KEYWORDS)
    context_hits = _hits(text, NORWAY_CONTEXT_KEYWORDS)

    if should_exclude_norway_item(item.title, item.link):
        return None

    public_news_hit = any(part in item.link for part in NORWAY_PUBLIC_LINK_PARTS)
    high_signal_hits = [hit for hit in norway_hits if hit in NORWAY_HIGH_SIGNAL]
    weak_only = bool(norway_hits) and all(hit in NORWAY_WEAK_LOCATION_OR_IDENTITY for hit in norway_hits)
    if not norway_hits and not public_news_hit:
        return None
    if weak_only and not public_news_hit and not context_hits:
        return None

    high_signal_bonus = 6 if high_signal_hits else 0
    public_news_bonus = 4 if public_news_hit else 0
    score = len(norway_hits) * 3 + len(context_hits) * 2 + high_signal_bonus + public_news_bonus
    if score < 5:
        return None

    item.ai_keywords = norway_hits or ["VG/NRK offentlig nyhet"]
    item.policy_keywords = context_hits
    item.stream = "norway-nato-eos"
    item.score = score
    item.reason = _build_norway_reason(norway_hits, context_hits)
    return item


def should_exclude_norway_item(title: str, link: str) -> bool:
    lower_title = title.lower()
    if any(part in link for part in NORWAY_EXCLUDE_LINK_PARTS):
        return True
    return any(keyword.lower() in lower_title for keyword in NORWAY_EXCLUDE_TITLE_KEYWORDS)


def _build_china_reason(ai_hits: list[str], policy_hits: list[str], category: str) -> str:
    parts: list[str] = []
    if ai_hits:
        parts.append("AI相关：" + "、".join(ai_hits[:4]))
    if policy_hits:
        parts.append("时政/政策相关：" + "、".join(policy_hits[:4]))
    if not parts:
        parts.append(f"栏目相关：{category}")
    return "；".join(parts)


def _build_norway_reason(norway_hits: list[str], context_hits: list[str]) -> str:
    core_hits = norway_hits[:5] or ["VG/NRK公共新闻入口"]
    core = "挪威/NATO/EØS命中：" + "、".join(core_hits)
    context = "上下文：" + ("、".join(context_hits[:5]) if context_hits else "VG/NRK最新新闻")
    return f"{core}；{context}"
