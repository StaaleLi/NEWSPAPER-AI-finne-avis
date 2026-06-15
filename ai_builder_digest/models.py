from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    source_type: str
    category: str
    region: str = "CN"


@dataclass
class DigestItem:
    title: str
    link: str
    source: str
    category: str
    published: str = ""
    summary: str = ""
    ai_keywords: list[str] = field(default_factory=list)
    policy_keywords: list[str] = field(default_factory=list)
    stream: str = "china-ai-policy"
    score: int = 0
    reason: str = ""
    article_text: str = ""
    chinese_title: str = ""
    brief: str = ""
    importance: str = ""
    credibility: str = ""
    claim_check: str = ""
    judge: str = ""
    judge_reason: str = ""
    title_en: str = ""
    brief_en: str = ""
    importance_en: str = ""
    reason_en: str = ""
    title_no: str = ""
    brief_no: str = ""
    importance_no: str = ""
    reason_no: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "category": self.category,
            "published": self.published,
            "summary": self.summary,
            "ai_keywords": self.ai_keywords,
            "policy_keywords": self.policy_keywords,
            "stream": self.stream,
            "score": self.score,
            "reason": self.reason,
            "article_excerpt": (self.brief or self.summary or self.article_text)[:240],
            "article_text_chars": len(self.article_text),
            "chinese_title": self.chinese_title,
            "brief": self.brief,
            "importance": self.importance,
            "credibility": self.credibility,
            "claim_check": self.claim_check,
            "judge": self.judge,
            "judge_reason": self.judge_reason,
            "title_en": self.title_en,
            "brief_en": self.brief_en,
            "importance_en": self.importance_en,
            "reason_en": self.reason_en,
            "title_no": self.title_no,
            "brief_no": self.brief_no,
            "importance_no": self.importance_no,
            "reason_no": self.reason_no,
        }


@dataclass
class SourceAudit:
    name: str
    url: str
    region: str
    status: str
    total_fetched: int = 0
    today_count: int = 0
    selected_count: int = 0
    error: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "url": self.url,
            "region": self.region,
            "status": self.status,
            "total_fetched": self.total_fetched,
            "today_count": self.today_count,
            "selected_count": self.selected_count,
            "error": self.error,
            "notes": self.notes,
        }
