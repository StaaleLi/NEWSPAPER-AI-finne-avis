from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import DigestItem, SourceAudit


SCHEMA = """
CREATE TABLE IF NOT EXISTS digest_items (
  target_date TEXT NOT NULL,
  link TEXT NOT NULL,
  title TEXT NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  stream TEXT NOT NULL,
  published TEXT,
  score INTEGER NOT NULL,
  brief TEXT,
  importance TEXT,
  credibility TEXT,
  claim_check TEXT,
  judge TEXT,
  judge_reason TEXT,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (target_date, link)
);

CREATE TABLE IF NOT EXISTS source_audits (
  target_date TEXT NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  region TEXT NOT NULL,
  status TEXT NOT NULL,
  total_fetched INTEGER NOT NULL,
  today_count INTEGER NOT NULL,
  selected_count INTEGER NOT NULL,
  error TEXT,
  notes_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (target_date, name)
);
"""


def save_run(db_path: str | Path, target_date: date, items: list[DigestItem], audits: list[SourceAudit]) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        for item in items:
            conn.execute(
                """
                INSERT OR REPLACE INTO digest_items (
                  target_date, link, title, source, category, stream, published, score,
                  brief, importance, credibility, claim_check, judge, judge_reason,
                  payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_date.isoformat(),
                    item.link,
                    item.title,
                    item.source,
                    item.category,
                    item.stream,
                    item.published,
                    item.score,
                    item.brief,
                    item.importance,
                    item.credibility,
                    item.claim_check,
                    item.judge,
                    item.judge_reason,
                    json.dumps(item.as_dict(), ensure_ascii=False),
                    now,
                ),
            )
        for audit in audits:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_audits (
                  target_date, name, url, region, status, total_fetched, today_count,
                  selected_count, error, notes_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_date.isoformat(),
                    audit.name,
                    audit.url,
                    audit.region,
                    audit.status,
                    audit.total_fetched,
                    audit.today_count,
                    audit.selected_count,
                    audit.error,
                    json.dumps(audit.notes, ensure_ascii=False),
                    now,
                ),
            )


def load_recent_items(db_path: str | Path, end_date: date, days: int) -> list[tuple[date, DigestItem]]:
    path = Path(db_path)
    if not path.exists() or days <= 0:
        return []
    start_date = end_date - timedelta(days=days - 1)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        rows = conn.execute(
            """
            SELECT target_date, payload_json
            FROM digest_items
            WHERE target_date BETWEEN ? AND ?
            ORDER BY target_date DESC, score DESC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    results: list[tuple[date, DigestItem]] = []
    for target_date_str, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            item_date = date.fromisoformat(target_date_str)
        except ValueError:
            continue
        results.append((item_date, _item_from_payload(payload)))
    return results


def _item_from_payload(payload: dict[str, object]) -> DigestItem:
    item = DigestItem(
        title=str(payload.get("title", "")),
        link=str(payload.get("link", "")),
        source=str(payload.get("source", "")),
        category=str(payload.get("category", "")),
        published=str(payload.get("published", "")),
        summary=str(payload.get("summary", "")),
    )
    if isinstance(payload.get("ai_keywords"), list):
        item.ai_keywords = [str(x) for x in payload["ai_keywords"]]
    if isinstance(payload.get("policy_keywords"), list):
        item.policy_keywords = [str(x) for x in payload["policy_keywords"]]
    item.stream = str(payload.get("stream", "china-ai-policy"))
    score = payload.get("score", 0)
    item.score = int(score) if isinstance(score, int) else 0
    for field_name in (
        "reason", "chinese_title", "brief", "importance", "credibility",
        "claim_check", "judge", "judge_reason",
        "title_en", "brief_en", "importance_en", "reason_en",
        "title_no", "brief_no", "importance_no", "reason_no",
    ):
        setattr(item, field_name, str(payload.get(field_name, "")))
    return item
